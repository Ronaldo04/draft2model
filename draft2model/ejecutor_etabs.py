"""Ejecución del plan estático de operaciones ETABS sobre la copia abierta de la plantilla.

Flujo explícito en dos pasos:
1. `preparar`: valida el plan (`validar_plan`), lo REGENERA desde la configuración y sus
   opciones y exige igualdad exacta con el recibido (una huella rehecha no basta), verifica
   configuración y geometría vigentes, la huella de la copia frente a la plantilla del plan,
   que el modelo abierto esperado sea esa copia y que el destino de guardado no exista.
   Escribe la solicitud en una corrida nueva; no ejecuta nada (modo `preparado`).
2. `ejecutar`: lanza `scripts/ejecutar_plan_etabs.ps1` (Windows PowerShell 5.1) mediante el
   adaptador, con su bloqueo compartido, tiempo límite y marca persistente de incertidumbre.
   En modo real exige `confirmar_mutacion=True`.

El script repite las comprobaciones antes de mutar, despacha cada llamada por reflexión
tipada, se detiene en el primer error y deja `traza.jsonl`. Tras un fallo con mutaciones o
un tiempo agotado, el estado de ETABS queda marcado como incierto hasta registrar una
recuperación (`AdaptadorEtabs.confirmar_recuperacion`).

Construir y guardar el modelo no ejecuta análisis ni aprueba el modelo.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from . import adaptador_etabs as ad
from . import operaciones_etabs as op
from .adaptador_etabs import (
    AdaptadorEtabs,
    ConfiguracionPuente,
    ErrorAdaptador,
    ErrorBloqueo,
    ErrorEvidenciaEtabs,
    ErrorPuente,
    ErrorTiempo,
    SolicitudPreparada,
    codigo_salida,
)
from .ingreso import file_hash

__all__ = [
    "SCRIPT_EJECUTOR", "configuracion_real", "configuracion_doble", "configuracion_doble_powershell",
    "EjecutorPlanEtabs", "EjecucionPreparada", "ResultadoEjecucion", "leer_traza", "codigo_salida",
    "ErrorAdaptador", "ErrorEvidenciaEtabs", "ErrorPuente", "ErrorTiempo", "ErrorBloqueo",
]

SCRIPT_EJECUTOR = ad.RAIZ_PROYECTO / "scripts" / "ejecutar_plan_etabs.ps1"
OPERACION = "ejecutar_plan"
TIMEOUT_PREDETERMINADO = 900.0


def configuracion_real(trabajo: Path, bloqueo: Path | None = None, *, timeout_s: float = TIMEOUT_PREDETERMINADO,
                       dll: Path | None = None) -> ConfiguracionPuente:
    """PowerShell 5.1 con -File, sin eludir la directiva de ejecución. Comparta `bloqueo` con el adaptador."""
    return ConfiguracionPuente.real(trabajo, bloqueo, timeout_s=timeout_s, dll=dll, script=SCRIPT_EJECUTOR)


def configuracion_doble(trabajo: Path, comando: tuple[str, ...], bloqueo: Path | None = None, *,
                        timeout_s: float = 60.0, entorno: dict[str, str] | None = None,
                        dll: Path | None = None) -> ConfiguracionPuente:
    """Proceso sustituto arbitrario (pruebas). Su respuesta debe declarar modo 'doble'."""
    return replace(ConfiguracionPuente.doble(trabajo, comando, bloqueo, timeout_s=timeout_s, entorno=entorno), dll=dll)


def configuracion_doble_powershell(trabajo: Path, dll_prueba: Path, bloqueo: Path | None = None, *,
                                   timeout_s: float = 120.0, entorno: dict[str, str] | None = None) -> ConfiguracionPuente:
    """El script real en modo doble contra un ensamblado de prueba; el script rechaza la DLL de CSI en este modo."""
    comando = (str(ad.POWERSHELL_51), "-NoProfile", "-NonInteractive", "-File", str(SCRIPT_EJECUTOR))
    return configuracion_doble(trabajo, comando, bloqueo, timeout_s=timeout_s, entorno=entorno, dll=Path(dll_prueba))


@dataclass
class EjecucionPreparada:
    solicitud: SolicitudPreparada
    huella_plan: str
    copia: Path
    destino: Path
    salidas_esperadas: dict[str, str]
    operaciones_totales: int

    @property
    def modo(self) -> str:
        return self.solicitud.modo

    @property
    def carpeta(self) -> Path:
        return self.solicitud.carpeta


@dataclass
class ResultadoEjecucion:
    modo_ejecucion: str
    corrida: Path
    huella_plan: str
    guardado: dict[str, str]
    mapeo_nombres: dict[str, str]
    operaciones_ejecutadas: int
    traza: list[dict[str, Any]]
    datos: dict[str, Any]
    avisos: list[str]
    analisis_ejecutado: bool = False
    aprueba_modelo: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


def _canonico(datos: Any) -> str:
    return json.dumps(datos, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _json_bytes(datos: Any) -> bytes:
    return (json.dumps(datos, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _escribir_nuevo(ruta: Path, contenido: bytes) -> None:
    with open(ruta, "xb") as archivo:
        archivo.write(contenido)


def leer_traza(carpeta: Path) -> list[dict[str, Any]]:
    """Líneas de traza.jsonl; una línea ilegible se conserva como {'ilegible': texto}."""
    ruta = Path(carpeta) / "traza.jsonl"
    if not ruta.is_file():
        return []
    lineas = []
    for texto in ruta.read_text(encoding="utf-8", errors="replace").splitlines():
        if not texto.strip():
            continue
        try:
            lineas.append(json.loads(texto))
        except ValueError:
            lineas.append({"ilegible": texto})
    return lineas


def _mutacion_iniciada(traza: list[dict[str, Any]]) -> bool:
    """Conservador: una línea ilegible o el inicio de una operación que no es lectura implican posible mutación."""
    return any("ilegible" in l or (l.get("evento") == "inicio" and l.get("lectura") is not True) for l in traza)


class EjecutorPlanEtabs:
    """Prepara y ejecuta planes; una corrida a la vez mediante el bloqueo compartido del adaptador."""

    def __init__(self, configuracion: ConfiguracionPuente):
        self.adaptador = AdaptadorEtabs(configuracion)
        self.config = self.adaptador.config

    @property
    def estado_incierto(self) -> Path:
        return self.adaptador.estado_incierto

    # -- preparación --
    def preparar(self, raiz: Path, configuracion: Any, plan: Any, *, copia: Path, modelo_esperado: Path,
                 id_proceso: int | None = None) -> EjecucionPreparada:
        if not isinstance(plan, dict):
            raise ErrorAdaptador("El plan debe ser un objeto JSON.")
        problemas = op.validar_plan_por_version(plan)  # 0.1 o 0.4; los planes de desarrollo se rechazan
        if problemas:
            raise ErrorEvidenciaEtabs("El plan no supera validar_plan: " + "; ".join(problemas))
        opciones = plan.get("opciones")
        if not isinstance(opciones, dict):
            raise ErrorEvidenciaEtabs("El plan no declara sus opciones.")
        try:
            regenerado = op.generar_plan_por_version(Path(raiz), configuracion, **opciones)
        except op.ErrorPlanRechazado as error:
            raise ErrorEvidenciaEtabs("La configuración ya no permite regenerar el plan: " + "; ".join(error.motivos)) from error
        except op.ErrorPlan as error:
            raise ErrorEvidenciaEtabs(f"Opciones del plan no regenerables: {error}") from error
        if _canonico(regenerado.datos) != _canonico(plan):
            raise ErrorEvidenciaEtabs("El plan recibido no es idéntico al regenerado desde la configuración y sus "
                                      "opciones; no se ejecuta (una huella rehecha no lo acredita).")

        copia = ad._ruta_edb(copia, "copia")
        modelo = ad._ruta_edb(modelo_esperado, "modelo_esperado")
        if not ad._misma(copia, modelo):
            raise ErrorAdaptador("El modelo abierto esperado debe ser la copia de la plantilla.")
        if os.path.islink(copia) or not copia.is_file():
            raise ErrorAdaptador(f"La copia no existe o es un enlace: {copia}")
        sha_copia = file_hash(copia)
        if sha_copia != plan["origen"]["plantilla"]["sha256"]:
            raise ErrorEvidenciaEtabs("La copia no coincide con el SHA256 de la plantilla declarada en el plan.")
        destino = ad._ruta_edb(opciones["destino_guardado"], "destino_guardado")
        if ad._misma(destino, copia):
            raise ErrorAdaptador("El destino de guardado no puede ser la copia.")
        ad._destino_nuevo(destino)
        id_proceso = ad._id_proceso(id_proceso)

        trabajo = Path(self.config.trabajo)
        if not trabajo.is_dir():
            raise ErrorAdaptador(f"No existe la carpeta de trabajo: {trabajo}")
        identificador = uuid4().hex
        carpeta = trabajo / identificador
        carpeta.mkdir()
        _escribir_nuevo(carpeta / "plan.json", _json_bytes(plan))
        dll = str(self.config.dll) if self.config.dll is not None else plan["api"]["dll"]
        contenido = {
            "contrato": ad.CONTRATO_SOLICITUD, "version_contrato": ad.VERSION_CONTRATO, "id": identificador,
            "operacion": OPERACION, "modo_configurado": self.config.modo, "creado_utc": datetime.now(timezone.utc).isoformat(),
            "dll": dll, "version_dll_esperada": plan["api"]["version_archivo_verificada"],
            "modelo_esperado": str(modelo), "sha256_copia": sha_copia, "destino": str(destino),
            "id_proceso": id_proceso, "huella_plan": plan["huella_plan"], "origen": plan["origen"],
            "operaciones": plan["operaciones"],
        }
        bytes_solicitud = _json_bytes(contenido)
        solicitud, respuesta = carpeta / "solicitud.json", carpeta / "respuesta.json"
        _escribir_nuevo(solicitud, bytes_solicitud)
        argv = [*self.config.comando, "-Solicitud", str(solicitud), "-Respuesta", str(respuesta),
                "-Sha256Solicitud", hashlib.sha256(bytes_solicitud).hexdigest(), "-Modo", self.config.modo]
        salidas = {s["registra"]: s["debe_ser"] for o in plan["operaciones"] for s in o.get("salidas", [])}
        preparada = SolicitudPreparada(identificador, OPERACION, carpeta, solicitud, respuesta, argv, contenido)
        preparada.artefactos = {"copia": str(copia), "sha256_copia": sha_copia, "destino": str(destino),
                                "huella_plan": plan["huella_plan"]}
        return EjecucionPreparada(preparada, plan["huella_plan"], copia, destino, salidas, len(plan["operaciones"]))

    # -- ejecución --
    def ejecutar(self, preparada: EjecucionPreparada, *, confirmar_mutacion: bool = False) -> ResultadoEjecucion:
        """Ejecuta una preparación. En modo real, `confirmar_mutacion=True` es obligatorio."""
        if self.config.modo == "real" and confirmar_mutacion is not True:
            raise ErrorAdaptador("La ejecución real modifica ETABS: exige confirmar_mutacion=True.")
        if preparada.modo != "preparado":
            raise ErrorAdaptador("La preparación ya se ejecutó; prepare una corrida nueva.")
        ad._destino_nuevo(preparada.destino)
        if file_hash(preparada.copia) != preparada.solicitud.contenido["sha256_copia"]:
            raise ErrorEvidenciaEtabs("La copia cambió después de preparar.")
        try:
            respuesta = self.adaptador.ejecutar(preparada.solicitud)
        except ErrorBloqueo:
            raise
        except ErrorTiempo as error:
            self._anotar(error, preparada, None)  # el adaptador ya registró la incertidumbre
            raise
        except (ErrorPuente, ErrorEvidenciaEtabs) as error:
            progreso = (getattr(error, "respuesta", None) or {}).get("progreso")
            self._anotar(error, preparada, progreso)
            raise
        return self._verificar(preparada, respuesta)

    def _anotar(self, error: BaseException, preparada: EjecucionPreparada, progreso: Any) -> None:
        traza = leer_traza(preparada.carpeta)
        if isinstance(progreso, dict) and isinstance(progreso.get("mutaciones_realizadas"), bool):
            mutado = progreso["mutaciones_realizadas"] or _mutacion_iniciada(traza)
        else:
            mutado = _mutacion_iniciada(traza)
        incierto = isinstance(error, ErrorTiempo) or mutado
        if incierto and not self.estado_incierto.exists():
            try:
                _escribir_nuevo(self.estado_incierto, _json_bytes({
                    "corrida": preparada.solicitud.id, "operacion": OPERACION, "modo": self.config.modo,
                    "estado": "motor_incierto", "motivo": "fallo_parcial_del_plan",
                    "orden_fallida": progreso.get("orden_fallida") if isinstance(progreso, dict) else None,
                    "fecha_utc": datetime.now(timezone.utc).isoformat()}))
            except FileExistsError:
                pass
        error.traza = traza
        error.progreso = progreso
        error.incierto = incierto
        error.corrida = preparada.carpeta

    def _verificar(self, preparada: EjecucionPreparada, respuesta) -> ResultadoEjecucion:
        datos, progreso = respuesta.datos, respuesta.respuesta.get("progreso") or {}
        traza = leer_traza(preparada.carpeta)
        problemas = []
        guardado = datos.get("guardado") or {}
        if not ad._misma(Path(str(guardado.get("ruta", ""))), preparada.destino) or not preparada.destino.is_file():
            problemas.append("El destino informado no existe o no es el preparado.")
        elif file_hash(preparada.destino) != guardado.get("sha256"):
            problemas.append("El archivo guardado no coincide con la huella informada.")
        if progreso.get("operaciones_ejecutadas") != preparada.operaciones_totales:
            problemas.append("No se informaron todas las operaciones como ejecutadas.")
        if progreso.get("mapeo_nombres") != preparada.salidas_esperadas:
            problemas.append("El mapeo de nombres no coincide con las salidas del plan.")
        if datos.get("huella_plan") != preparada.huella_plan:
            problemas.append("La respuesta cita otra huella de plan.")
        if datos.get("analisis_ejecutado") is not False or datos.get("aprueba_modelo") is not False:
            problemas.append("La respuesta debe declarar analisis_ejecutado y aprueba_modelo falsos.")
        if sum(1 for l in traza if l.get("evento") == "fin") != preparada.operaciones_totales:
            problemas.append("La traza no registra el fin de todas las operaciones.")
        if problemas:
            raise ErrorEvidenciaEtabs("Ejecución informada como correcta pero no verificable: " + "; ".join(problemas))
        resultado = ResultadoEjecucion(
            respuesta.modo_ejecucion, preparada.carpeta, preparada.huella_plan,
            {"ruta": str(preparada.destino), "sha256": guardado["sha256"]}, dict(progreso["mapeo_nombres"]),
            progreso["operaciones_ejecutadas"], traza, datos, respuesta.avisos)
        _escribir_nuevo(preparada.carpeta / "resultado_ejecucion.json", _json_bytes({
            "modo_ejecucion": resultado.modo_ejecucion, "huella_plan": resultado.huella_plan,
            "guardado": resultado.guardado, "operaciones_ejecutadas": resultado.operaciones_ejecutadas,
            "analisis_ejecutado": False, "aprueba_modelo": False,
            "aviso": "Modelo construido y guardado según el plan; requiere revisión. No se ejecutó análisis."}))
        return resultado
