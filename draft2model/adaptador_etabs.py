"""Adaptador local hacia la API de ETABS mediante un puente Windows PowerShell 5.1.

Python prepara una solicitud JSON en una carpeta de corrida nueva, ejecuta el puente
(`scripts/puente_etabs.ps1`) con tiempo límite y bloqueo exclusivo, y valida la
respuesta JSON que el puente publica sin sobrescribir. PowerShell 7 no sirve: la API
de CSI depende de Marshal.GetActiveObject, ausente en .NET Core.

Modos de una solicitud:
- `preparado`: solicitud y comando escritos; nada se ejecuta.
- `doble`: ejecutada por un proceso sustituto (pruebas); nunca se presenta como real.
- `real`: ejecutada por el puente PowerShell contra la API CSI instalada.

Operaciones iniciales: diagnosticar (lectura), abrir_copia_plantilla, leer_tablas y
guardar_como. Ninguna ejecuta análisis, cierra ETABS, cambia unidades ni sobrescribe.
Abrir una copia de plantilla NO construye un modelo: la conversión del contrato
estructural en objetos ETABS todavía no existe.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from .gestion_extraccion import ErrorGestion, json_desde_bytes
from .ingreso import file_hash

CONTRATO_SOLICITUD = "draft2model.etabs_solicitud"
CONTRATO_RESPUESTA = "draft2model.etabs_respuesta"
VERSION_CONTRATO = "0.1.0"
MODOS = ("real", "doble")
RAIZ_PROYECTO = Path(__file__).resolve().parents[1]
SCRIPT_PUENTE = RAIZ_PROYECTO / "scripts" / "puente_etabs.ps1"
POWERSHELL_51 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
DLL_ETABS = Path(r"C:\Program Files\Computers and Structures\ETABS 21\ETABSv1.dll")
SHA256 = r"[0-9a-f]{64}"
MAX_SALIDA_PROCESO = 1024 * 1024  # bytes de stdout/stderr que se conservan en la corrida


@dataclass(frozen=True)
class Operacion:
    descripcion: str
    modifica_instancia: bool  # cambia el estado de ETABS (modelo abierto, archivo actual)
    escribe_archivos: bool


OPERACIONES = {
    "diagnosticar": Operacion("Versión, unidades, modelo abierto y procesos; solo lectura.", False, False),
    "abrir_copia_plantilla": Operacion("Abre una copia verificada de una plantilla .edb; nunca el original.", True, True),
    "leer_tablas": Operacion("Tablas de resultados por DatabaseTables para casos o combinaciones explícitos.", False, False),
    "guardar_como": Operacion("Guarda el modelo abierto en un destino .edb nuevo.", True, True),
}

# Interfaz prevista, no implementada: el adaptador las rechaza hasta que existan.
OPERACIONES_FUTURAS = {
    "aplicar_modelo_estructural": (
        "Consumirá un contrato draft2model.modelo_estructural con apto_para_adaptador verdadero, su "
        "huella_contenido y la versión geométrica exacta, sobre una copia abierta. No implementada."
    ),
}

# Códigos de retorno para la futura CLI.
CODIGO_SOLICITUD, CODIGO_EVIDENCIA, CODIGO_PUENTE, CODIGO_TIEMPO, CODIGO_BLOQUEO = 1, 2, 3, 4, 5

# Códigos de salida del puente -> tipo de error.
SALIDAS_PUENTE = {10: "solicitud", 20: "api_no_disponible", 30: "api", 40: "precondicion", 41: "evidencia", 50: "inesperado"}


# -- errores -------------------------------------------------------------------

class ErrorAdaptador(ValueError):
    """Solicitud inválida: argumentos, rutas o destinos existentes. No se ejecutó nada."""

    codigo = CODIGO_SOLICITUD


class ErrorEvidenciaEtabs(ErrorAdaptador):
    """Plantilla, copia o archivo guardado que no coincide con la huella esperada."""

    codigo = CODIGO_EVIDENCIA


class ErrorPuente(RuntimeError):
    """El puente terminó con error, sin respuesta válida o con una respuesta incoherente."""

    codigo = CODIGO_PUENTE

    def __init__(self, mensaje: str, *, tipo: str = "puente", corrida: Path | None = None,
                 respuesta: dict | None = None, codigo_proceso: int | None = None):
        super().__init__(mensaje)
        self.tipo = tipo
        self.corrida = corrida
        self.respuesta = respuesta
        self.codigo_proceso = codigo_proceso


class ErrorTiempo(ErrorPuente):
    """El puente superó el tiempo límite y se terminó; el estado de ETABS es desconocido."""

    codigo = CODIGO_TIEMPO


class ErrorBloqueo(RuntimeError):
    """Otra corrida mantiene el bloqueo exclusivo del puente."""

    codigo = CODIGO_BLOQUEO


def codigo_salida(error: BaseException) -> int:
    """Código de retorno de CLI para un error del adaptador (0 si no es un error)."""
    return getattr(error, "codigo", CODIGO_PUENTE) if error is not None else 0


# -- bloqueo exclusivo -------------------------------------------------------

class BloqueoExclusivo:
    """Bloqueo del sistema operativo sobre un archivo; se libera solo si el proceso muere.

    No se borra el archivo al liberar (evita carreras); su contenido es informativo.
    """

    def __init__(self, ruta: Path):
        self.ruta = Path(ruta)
        self._fd: int | None = None

    def adquirir(self) -> "BloqueoExclusivo":
        if not self.ruta.parent.is_dir():
            raise ErrorAdaptador(f"No existe la carpeta del bloqueo: {self.ruta.parent}")
        fd = os.open(self.ruta, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            if os.name == "nt":
                import msvcrt

                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            os.close(fd)
            raise ErrorBloqueo(f"Otra corrida del puente ETABS está activa (bloqueo {self.ruta}).") from error
        self._fd = fd
        info = json.dumps({"pid": os.getpid(), "desde_utc": datetime.now(timezone.utc).isoformat()}).encode()
        os.lseek(fd, 1, os.SEEK_SET)  # el byte 0 es el bloqueado
        os.ftruncate(fd, 1)
        os.write(fd, info)
        return self

    def liberar(self) -> None:
        if self._fd is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                os.lseek(self._fd, 0, os.SEEK_SET)
                msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fd, fcntl.LOCK_UN)
        finally:
            os.close(self._fd)
            self._fd = None

    def __enter__(self):
        return self.adquirir()

    def __exit__(self, *exc):
        self.liberar()


# -- configuración y resultados ----------------------------------------------

@dataclass
class ConfiguracionPuente:
    """`comando` es el prefijo del proceso; se le añaden -Solicitud y -Respuesta."""

    trabajo: Path
    bloqueo: Path
    modo: str
    comando: tuple[str, ...]
    timeout_s: float = 120.0
    dll: Path | None = None
    entorno: dict[str, str] | None = None
    max_respuesta_bytes: int = 256 * 1024 * 1024

    @classmethod
    def real(cls, trabajo: Path, bloqueo: Path | None = None, *, timeout_s: float = 120.0,
             dll: Path | None = None, powershell: Path = POWERSHELL_51, script: Path = SCRIPT_PUENTE):
        comando = (str(powershell), "-NoProfile", "-NonInteractive", "-File", str(script))
        trabajo = Path(trabajo)
        return cls(trabajo, Path(bloqueo) if bloqueo else trabajo / "puente_etabs.lock", "real", comando,
                   timeout_s, dll)

    @classmethod
    def doble(cls, trabajo: Path, comando: tuple[str, ...], bloqueo: Path | None = None, *,
              timeout_s: float = 30.0, entorno: dict[str, str] | None = None):
        trabajo = Path(trabajo)
        return cls(trabajo, Path(bloqueo) if bloqueo else trabajo / "puente_etabs.lock", "doble", tuple(comando),
                   timeout_s, None, entorno)


@dataclass
class SolicitudPreparada:
    """Solicitud escrita en su carpeta de corrida; `modo` es 'preparado' hasta ejecutarla."""

    id: str
    operacion: str
    carpeta: Path
    solicitud: Path
    respuesta: Path
    argv: list[str]
    contenido: dict[str, Any]
    modo: str = "preparado"
    artefactos: dict[str, Any] = field(default_factory=dict)


@dataclass
class RespuestaPuente:
    id: str
    operacion: str
    modo_ejecucion: str  # 'real' o 'doble'
    datos: dict[str, Any]
    avisos: list[str]
    corrida: Path
    codigo_proceso: int
    duracion_s: float
    respuesta: dict[str, Any]
    artefactos: dict[str, Any] = field(default_factory=dict)


class PuenteEtabs(Protocol):
    """Interfaz que consumirán módulos futuros (p. ej. el contrato estructural)."""

    def ejecutar_operacion(self, operacion: str, parametros: dict[str, Any]) -> RespuestaPuente: ...


# -- validación de parámetros -------------------------------------------------

def _texto(valor: Any, nombre: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ErrorAdaptador(f"'{nombre}' debe ser texto no vacío.")
    return valor


def _lista(valor: Any, nombre: str) -> list[str]:
    if isinstance(valor, str) or not isinstance(valor, (list, tuple)):
        raise ErrorAdaptador(f"'{nombre}' debe ser una lista de textos.")
    lista = [_texto(v, nombre) for v in valor]
    if len(set(lista)) != len(lista):
        raise ErrorAdaptador(f"'{nombre}' contiene nombres repetidos.")
    return lista


def _id_proceso(valor: Any) -> int | None:
    if valor is None:
        return None
    if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
        raise ErrorAdaptador("'id_proceso' debe ser un entero positivo.")
    return valor


def _ruta_edb(valor: Any, nombre: str) -> Path:
    ruta = Path(_texto(str(valor) if isinstance(valor, Path) else valor, nombre))
    if not ruta.is_absolute():
        raise ErrorAdaptador(f"'{nombre}' debe ser una ruta absoluta.")
    if ruta.suffix.lower() != ".edb":
        raise ErrorAdaptador(f"'{nombre}' debe ser un archivo .edb.")
    return Path(os.path.abspath(ruta))


def _sha(valor: Any, nombre: str) -> str:
    if not isinstance(valor, str) or not re.fullmatch(SHA256, valor):
        raise ErrorAdaptador(f"'{nombre}' debe ser un SHA256 hexadecimal en minúsculas.")
    return valor


def _misma(a: Path, b: Path) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _destino_nuevo(destino: Path) -> None:
    if os.path.lexists(destino):
        raise ErrorAdaptador(f"El destino ya existe; no se sobrescribe: {destino}")
    if not destino.parent.is_dir():
        raise ErrorAdaptador(f"No existe la carpeta de destino: {destino.parent}")


def validar_parametros(operacion: str, parametros: Any) -> dict[str, Any]:
    """Normaliza los parámetros de una operación; no toca ETABS. Lanza ErrorAdaptador."""
    if operacion in OPERACIONES_FUTURAS:
        raise ErrorAdaptador(f"La operación '{operacion}' está prevista pero no implementada: {OPERACIONES_FUTURAS[operacion]}")
    if operacion not in OPERACIONES:
        raise ErrorAdaptador(f"Operación no admitida: '{operacion}'.")
    if not isinstance(parametros, dict):
        raise ErrorAdaptador("'parametros' debe ser un objeto.")
    p = dict(parametros)
    permitidas = {
        "diagnosticar": {"id_proceso"},
        "abrir_copia_plantilla": {"copia", "sha256_copia", "instancia", "reemplazar_modelo_activo", "id_proceso"},
        "leer_tablas": {"modelo_esperado", "tablas", "casos", "combinaciones", "id_proceso"},
        "guardar_como": {"modelo_esperado", "destino", "id_proceso"},
    }[operacion]
    sobrantes = sorted(set(p) - permitidas)
    if sobrantes:
        raise ErrorAdaptador(f"Parámetros no admitidos para '{operacion}': {', '.join(sobrantes)}.")
    salida: dict[str, Any] = {}
    if operacion == "abrir_copia_plantilla":
        salida["copia"] = str(_ruta_edb(p.get("copia"), "copia"))
        salida["sha256_copia"] = _sha(p.get("sha256_copia"), "sha256_copia")
        instancia = p.get("instancia")
        if instancia not in ("activa", "nueva"):
            raise ErrorAdaptador("'instancia' debe ser 'activa' o 'nueva'.")
        salida["instancia"] = instancia
        reemplazar = p.get("reemplazar_modelo_activo", False)
        if not isinstance(reemplazar, bool):
            raise ErrorAdaptador("'reemplazar_modelo_activo' debe ser booleano.")
        if instancia == "activa" and not reemplazar:
            raise ErrorAdaptador("Abrir en la instancia activa descarta su modelo actual sin guardarlo; "
                                 "exige reemplazar_modelo_activo=True.")
        if instancia == "nueva" and p.get("id_proceso") is not None:
            raise ErrorAdaptador("'id_proceso' no se admite con instancia 'nueva'.")
        salida["reemplazar_modelo_activo"] = reemplazar
    elif operacion == "leer_tablas":
        salida["modelo_esperado"] = str(_ruta_edb(p.get("modelo_esperado"), "modelo_esperado"))
        salida["tablas"] = _lista(p.get("tablas"), "tablas")
        salida["casos"] = _lista(p.get("casos", []), "casos")
        salida["combinaciones"] = _lista(p.get("combinaciones", []), "combinaciones")
        if not salida["tablas"]:
            raise ErrorAdaptador("'tablas' no puede estar vacía.")
        if not salida["casos"] and not salida["combinaciones"]:
            raise ErrorAdaptador("Indique casos o combinaciones explícitos.")
    elif operacion == "guardar_como":
        modelo = _ruta_edb(p.get("modelo_esperado"), "modelo_esperado")
        destino = _ruta_edb(p.get("destino"), "destino")
        if _misma(modelo, destino):
            raise ErrorAdaptador("El destino debe ser distinto del modelo abierto.")
        _destino_nuevo(destino)
        salida.update(modelo_esperado=str(modelo), destino=str(destino))
    id_proceso = _id_proceso(p.get("id_proceso"))
    if id_proceso is not None:
        salida["id_proceso"] = id_proceso
    return salida


# -- adaptador ---------------------------------------------------------------

def _json_bytes(data: Any) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _escribir_nuevo(ruta: Path, contenido: bytes) -> None:
    with open(ruta, "xb") as archivo:
        archivo.write(contenido)


def _terminar_arbol(proceso: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proceso.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if proceso.poll() is None:
        proceso.kill()


class AdaptadorEtabs:
    """Ejecuta operaciones del puente, una corrida a la vez, con trazabilidad por carpeta."""

    def __init__(self, configuracion: ConfiguracionPuente):
        if configuracion.modo not in MODOS:
            raise ErrorAdaptador(f"Modo no admitido: {configuracion.modo!r}; use 'real' o 'doble'.")
        if not configuracion.comando:
            raise ErrorAdaptador("El comando del puente está vacío.")
        if not (type(configuracion.timeout_s) in (int, float) and math.isfinite(configuracion.timeout_s) and configuracion.timeout_s > 0):
            raise ErrorAdaptador("'timeout_s' debe ser positivo.")
        # El proceso se ejecuta dentro de la corrida; las rutas de transporte deben
        # seguir apuntando al mismo archivo aunque el llamador use trabajo relativo.
        self.config = replace(configuracion, trabajo=Path(configuracion.trabajo).absolute(),
                              bloqueo=Path(configuracion.bloqueo).absolute())

    # -- preparación y ejecución genéricas --
    def preparar(self, operacion: str, parametros: dict[str, Any]) -> SolicitudPreparada:
        """Escribe la solicitud en una carpeta de corrida nueva; no ejecuta nada."""
        validados = validar_parametros(operacion, parametros)
        trabajo = Path(self.config.trabajo)
        if not trabajo.is_dir():
            raise ErrorAdaptador(f"No existe la carpeta de trabajo: {trabajo}")
        identificador = uuid4().hex
        carpeta = trabajo / identificador
        carpeta.mkdir()  # nueva; falla si existiera
        contenido = {
            "contrato": CONTRATO_SOLICITUD, "version_contrato": VERSION_CONTRATO, "id": identificador,
            "operacion": operacion, "parametros": validados, "creado_utc": datetime.now(timezone.utc).isoformat(),
            "modo_configurado": self.config.modo,
        }
        if self.config.dll is not None:
            contenido["dll"] = str(self.config.dll)
        solicitud, respuesta = carpeta / "solicitud.json", carpeta / "respuesta.json"
        _escribir_nuevo(solicitud, _json_bytes(contenido))
        argv = [*self.config.comando, "-Solicitud", str(solicitud), "-Respuesta", str(respuesta)]
        return SolicitudPreparada(identificador, operacion, carpeta, solicitud, respuesta, argv, contenido)

    def ejecutar(self, preparada: SolicitudPreparada) -> RespuestaPuente:
        """Ejecuta una solicitud preparada bajo el bloqueo exclusivo y valida su respuesta."""
        if preparada.modo != "preparado" or os.path.lexists(preparada.respuesta):
            raise ErrorAdaptador("La solicitud ya se ejecutó; prepare una nueva corrida.")
        if self.config.modo == "real":
            if os.name != "nt" or not Path(self.config.comando[0]).is_file():
                raise ErrorPuente("El modo real requiere Windows PowerShell 5.1 (powershell.exe).", tipo="entorno",
                                  corrida=preparada.carpeta)
        with BloqueoExclusivo(self.config.bloqueo):
            if preparada.operacion != 'diagnosticar' and self.estado_incierto.exists():
                raise ErrorBloqueo('El estado de ETABS quedó incierto tras una interrupción. Comprobar el motor y registrar recuperación antes de otra operación.')
            preparada.modo = self.config.modo
            return self._lanzar(preparada)

    @property
    def estado_incierto(self):
        return Path(str(Path(self.config.bloqueo).absolute()) + '.incierto.json')

    def confirmar_recuperacion(self, *, motor_inactivo_declarado: bool, revisor_declarado: str, motivo: str):
        """Registrar comprobación externa; no afirma comprobar ni cerrar ETABS por sí mismo."""
        if motor_inactivo_declarado is not True or not all(isinstance(v,str) and v.strip() for v in (revisor_declarado,motivo)):
            raise ErrorAdaptador('Recuperación exige motor inactivo declarado, revisor y motivo.')
        with BloqueoExclusivo(self.config.bloqueo):
            if not self.estado_incierto.is_file() or self.estado_incierto.resolve() != self.estado_incierto:
                raise ErrorAdaptador('No hay un registro de incertidumbre regular para recuperar.')
            historial = self.estado_incierto.with_name(self.estado_incierto.name + '.resuelto.' + uuid4().hex)
            registro = {'motor_inactivo_declarado': True, 'revisor_declarado': revisor_declarado,
                        'motivo': motivo, 'fecha_utc': datetime.now(timezone.utc).isoformat(),
                        'identidad_revisor': 'declarada_no_verificada'}
            _escribir_nuevo(historial.with_suffix(historial.suffix+'.recuperacion.json'), _json_bytes(registro))
            self.estado_incierto.rename(historial)  # conservar la evidencia, sin sobrescribir
            return historial

    def ejecutar_operacion(self, operacion: str, parametros: dict[str, Any]) -> RespuestaPuente:
        return self.ejecutar(self.preparar(operacion, parametros))

    def _lanzar(self, preparada: SolicitudPreparada) -> RespuestaPuente:
        entorno = dict(os.environ)
        entorno.update(self.config.entorno or {})
        inicio = time.monotonic()
        registro: dict[str, Any] = {"id": preparada.id, "operacion": preparada.operacion, "modo": self.config.modo,
                                    "argv": preparada.argv, "inicio_utc": datetime.now(timezone.utc).isoformat()}
        # El servidor COM puede heredar stdout/stderr. Con PIPE, communicate()
        # espera EOF del descendiente aun cuando el puente ya terminó. Archivos
        # regulares permiten esperar solo el proceso del puente, sin ese falso timeout.
        with (preparada.carpeta/'stdout_proceso.bin').open('xb+') as stdout_file, (preparada.carpeta/'stderr_proceso.bin').open('xb+') as stderr_file:
            try:
                proceso = subprocess.Popen(preparada.argv, stdout=stdout_file, stderr=stderr_file,
                                           stdin=subprocess.DEVNULL, env=entorno, cwd=str(preparada.carpeta))
            except OSError as error:
                self._registrar(preparada, registro, inicio, "error", f"No se pudo iniciar el puente: {error}")
                raise ErrorPuente(f"No se pudo iniciar el puente: {error}", tipo="entorno", corrida=preparada.carpeta) from error
            try:
                proceso.wait(timeout=self.config.timeout_s)
            except subprocess.TimeoutExpired:
                _terminar_arbol(proceso)
                proceso.wait(timeout=30)
                stdout_file.seek(0); stderr_file.seek(0)
                salida, errores = stdout_file.read(), stderr_file.read()
                self._guardar_salida(preparada, salida, errores)
                if preparada.operacion != 'diagnosticar' and not self.estado_incierto.exists():
                    _escribir_nuevo(self.estado_incierto, _json_bytes({'corrida': preparada.id,
                        'operacion': preparada.operacion, 'modo': self.config.modo,
                        'estado': 'motor_incierto', 'fecha_utc': datetime.now(timezone.utc).isoformat()}))
                mensaje = (f"El puente superó {self.config.timeout_s} s y se terminó. El estado de ETABS es desconocido: "
                           "compruébelo antes de otra corrida; una instancia iniciada por COM no se cierra.")
                self._registrar(preparada, registro, inicio, "tiempo_agotado", mensaje, proceso.returncode)
                raise ErrorTiempo(mensaje, tipo="tiempo", corrida=preparada.carpeta, codigo_proceso=proceso.returncode)
            stdout_file.seek(0); stderr_file.seek(0)
            salida, errores = stdout_file.read(), stderr_file.read()
        self._guardar_salida(preparada, salida, errores)
        codigo = proceso.returncode
        try:
            respuesta = self._leer_respuesta(preparada, codigo)
        except ErrorPuente as error:
            self._registrar(preparada, registro, inicio, "error", str(error), codigo)
            raise
        if codigo != 0 or respuesta["estado"] != "ok":
            fallo = respuesta.get("error") or {}
            tipo = fallo.get("tipo") if isinstance(fallo, dict) else None
            tipo = tipo or SALIDAS_PUENTE.get(codigo, "puente")
            mensaje = f"Puente ETABS: {tipo}: {fallo.get('mensaje') if isinstance(fallo, dict) else fallo} (salida {codigo})."
            self._registrar(preparada, registro, inicio, "error", mensaje, codigo)
            if codigo == 0 or respuesta["estado"] == "ok":
                raise ErrorPuente("Código de salida y estado de la respuesta incoherentes. " + mensaje, tipo="incoherente",
                                  corrida=preparada.carpeta, respuesta=respuesta, codigo_proceso=codigo)
            if tipo == "evidencia":
                raise ErrorEvidenciaEtabs(mensaje)
            raise ErrorPuente(mensaje, tipo=tipo, corrida=preparada.carpeta, respuesta=respuesta, codigo_proceso=codigo)
        datos = respuesta.get("datos")
        if not isinstance(datos, dict):
            self._registrar(preparada, registro, inicio, "error", "Respuesta correcta sin 'datos'.", codigo)
            raise ErrorPuente("La respuesta correcta no contiene 'datos' como objeto.", corrida=preparada.carpeta,
                              respuesta=respuesta, codigo_proceso=codigo)
        duracion = self._registrar(preparada, registro, inicio, "ok", None, codigo)
        avisos = [a for a in respuesta.get("avisos") or [] if isinstance(a, str)]
        return RespuestaPuente(preparada.id, preparada.operacion, respuesta["modo_ejecucion"], datos, avisos,
                               preparada.carpeta, codigo, duracion, respuesta, dict(preparada.artefactos))

    def _leer_respuesta(self, preparada: SolicitudPreparada, codigo: int) -> dict[str, Any]:
        def fallo(mensaje: str):
            return ErrorPuente(f"{mensaje} (salida {codigo}).", tipo=SALIDAS_PUENTE.get(codigo, "puente"),
                               corrida=preparada.carpeta, codigo_proceso=codigo)

        ruta = preparada.respuesta
        if not ruta.is_file():
            raise fallo("El puente no publicó respuesta")
        if ruta.stat().st_size > self.config.max_respuesta_bytes:
            raise fallo("La respuesta supera el tamaño máximo admitido")
        try:
            respuesta = json_desde_bytes(ruta.read_bytes(), "respuesta.json")
        except ErrorGestion as error:
            raise fallo(f"Respuesta ilegible: {error}") from error
        if not isinstance(respuesta, dict):
            raise fallo("La respuesta no es un objeto JSON")
        esperado = {"contrato": CONTRATO_RESPUESTA, "version_contrato": VERSION_CONTRATO, "id_solicitud": preparada.id}
        for clave, valor in esperado.items():
            if respuesta.get(clave) != valor:
                raise fallo(f"La respuesta no corresponde: '{clave}' distinto de {valor!r}")
        if respuesta.get("operacion") not in (preparada.operacion, None):
            raise fallo("La respuesta corresponde a otra operación")
        if respuesta.get("modo_ejecucion") != self.config.modo:
            raise fallo(f"La respuesta declara modo {respuesta.get('modo_ejecucion')!r}; se configuró {self.config.modo!r}")
        if respuesta.get("estado") not in ("ok", "error"):
            raise fallo("Estado de respuesta desconocido")
        if respuesta["estado"] == "ok" and respuesta.get("operacion") != preparada.operacion:
            raise fallo("La respuesta correcta no indica su operación")
        return respuesta

    def _guardar_salida(self, preparada: SolicitudPreparada, salida: bytes, errores: bytes) -> None:
        texto = b"--- stdout ---\n" + (salida or b"")[-MAX_SALIDA_PROCESO:] + b"\n--- stderr ---\n" + (errores or b"")[-MAX_SALIDA_PROCESO:]
        _escribir_nuevo(preparada.carpeta / "salida_puente.txt", texto)

    def _registrar(self, preparada, registro, inicio, estado, mensaje, codigo=None) -> float:
        duracion = round(time.monotonic() - inicio, 3)
        registro.update(estado=estado, mensaje=mensaje, codigo_proceso=codigo, duracion_s=duracion,
                        fin_utc=datetime.now(timezone.utc).isoformat(), artefactos=preparada.artefactos)
        _escribir_nuevo(preparada.carpeta / "registro.json", _json_bytes(registro))
        return duracion

    # -- operaciones --
    def diagnosticar(self, *, id_proceso: int | None = None, solo_preparar: bool = False):
        parametros = {} if id_proceso is None else {"id_proceso": id_proceso}
        preparada = self.preparar("diagnosticar", parametros)
        return preparada if solo_preparar else self.ejecutar(preparada)

    def abrir_copia_plantilla(self, plantilla: Path, sha256_esperado: str, destino: Path, *, instancia: str,
                              reemplazar_modelo_activo: bool = False, id_proceso: int | None = None,
                              solo_preparar: bool = False):
        """Copia la plantilla verificada a `destino` (carpeta nueva) y abre solo la copia.

        La plantilla se verifica antes y después de copiar; si no coincide, no queda copia.
        Abrir la copia no construye ni modifica un modelo estructural.
        """
        plantilla = _ruta_edb(plantilla, "plantilla")
        sha256_esperado = _sha(sha256_esperado, "sha256_esperado")
        destino = Path(destino)
        if not destino.is_absolute():
            raise ErrorAdaptador("'destino' debe ser una carpeta absoluta nueva.")
        if os.path.islink(plantilla) or not plantilla.is_file():
            raise ErrorAdaptador(f"La plantilla no existe o es un enlace: {plantilla}")
        if os.path.lexists(destino):
            raise ErrorAdaptador(f"La carpeta de destino ya existe; no se sobrescribe: {destino}")
        if not destino.parent.is_dir():
            raise ErrorAdaptador(f"No existe la carpeta contenedora del destino: {destino.parent}")
        copia = destino / plantilla.name
        if _misma(copia, plantilla):
            raise ErrorAdaptador("La copia no puede coincidir con la plantilla.")
        # Valida la solicitud antes de crear nada (la huella de la copia aún no existe).
        validar_parametros("abrir_copia_plantilla", {
            "copia": str(copia), "sha256_copia": sha256_esperado, "instancia": instancia,
            "reemplazar_modelo_activo": reemplazar_modelo_activo, "id_proceso": id_proceso})
        if file_hash(plantilla) != sha256_esperado:
            raise ErrorEvidenciaEtabs("La plantilla no coincide con la huella esperada; no se copia ni se abre.")
        destino.mkdir()
        try:
            with open(plantilla, "rb") as origen, open(copia, "xb") as salida:
                shutil.copyfileobj(origen, salida, 1024 * 1024)
            sha_copia, sha_plantilla = file_hash(copia), file_hash(plantilla)
            if sha_copia != sha256_esperado or sha_plantilla != sha256_esperado:
                raise ErrorEvidenciaEtabs("La plantilla cambió durante la copia o la copia es distinta; se descarta la copia.")
        except BaseException:
            shutil.rmtree(destino, ignore_errors=True)  # solo la carpeta creada en esta llamada
            raise
        parametros = {"copia": str(copia), "sha256_copia": sha_copia, "instancia": instancia,
                      "reemplazar_modelo_activo": reemplazar_modelo_activo}
        if id_proceso is not None:
            parametros["id_proceso"] = id_proceso
        preparada = self.preparar("abrir_copia_plantilla", parametros)
        preparada.artefactos = {"plantilla": str(plantilla), "sha256_plantilla": sha256_esperado,
                                "copia": str(copia), "sha256_copia": sha_copia}
        if solo_preparar:
            return preparada
        respuesta = self.ejecutar(preparada)
        if not _misma(Path(str(respuesta.datos.get("modelo_abierto", ""))), copia):
            raise ErrorPuente("El puente no confirma que el modelo abierto sea la copia.", corrida=respuesta.corrida,
                              respuesta=respuesta.respuesta)
        if file_hash(plantilla) != sha256_esperado:
            raise ErrorEvidenciaEtabs("La plantilla original cambió durante la corrida.")
        return respuesta

    def leer_tablas(self, modelo_esperado: Path, tablas: list[str], *, casos: list[str] = (),
                    combinaciones: list[str] = (), id_proceso: int | None = None, solo_preparar: bool = False):
        parametros = {"modelo_esperado": str(modelo_esperado), "tablas": list(tablas), "casos": list(casos),
                      "combinaciones": list(combinaciones)}
        if id_proceso is not None:
            parametros["id_proceso"] = id_proceso
        preparada = self.preparar("leer_tablas", parametros)
        return preparada if solo_preparar else self.ejecutar(preparada)

    def guardar_como(self, modelo_esperado: Path, destino: Path, *, id_proceso: int | None = None,
                     solo_preparar: bool = False):
        parametros = {"modelo_esperado": str(modelo_esperado), "destino": str(destino)}
        if id_proceso is not None:
            parametros["id_proceso"] = id_proceso
        preparada = self.preparar("guardar_como", parametros)
        if solo_preparar:
            return preparada
        respuesta = self.ejecutar(preparada)
        guardado = Path(preparada.contenido["parametros"]["destino"])
        if not guardado.is_file():
            raise ErrorPuente("El puente informó éxito pero el destino no existe.", corrida=respuesta.corrida,
                              respuesta=respuesta.respuesta)
        sha = file_hash(guardado)
        if sha != respuesta.datos.get("sha256"):
            raise ErrorEvidenciaEtabs("El archivo guardado no coincide con la huella informada por el puente.")
        respuesta.artefactos["guardado"] = {"ruta": str(guardado), "sha256": sha}
        return respuesta
