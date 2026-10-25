"""Almacenamiento local de extracciones preliminares y comprobación de su evidencia.

Importa, valida, corrige y exporta registros de `extraccion_preliminar` dentro de
`<raiz>/<caso>/`. Antes de cada operación comprueba el SHA256 de los originales e
imágenes citados y la concordancia de revisiones y recortes con el expediente
vigente. No ejecuta OCR, visión, geometría ni ETABS, y no aprueba ingeniería.
"""

from __future__ import annotations

import hashlib
import copy
import json
import math
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .extraccion_preliminar import (
    PATRON_SHA256,
    SISTEMA_COORDENADAS,
    VERSION_EXTRACCION,
    VERSION_SEMANTICA,
    ErrorExtraccion,
    corregir,
    es_numero,
    exportar_revisados,
    huella,
    inventario_desde,
    validar_extraccion,
)
from .ingreso import RESERVED, file_hash

RAIZ_PRIVADA = Path(__file__).resolve().parents[1] / "data" / "private"
VERSION_REGISTRO = "0.1.0"
PATRON_CASO = r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}"
PATRON_VERSION = r"[0-9a-f]{32}"
PATRON_RECORTE = r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}"
CARPETA_VERSIONES = "extracciones"
CARPETA_EXPORTACIONES = "extracciones_exportadas"
ARCHIVO_FUENTE = "fuente_importada.json"

SIN_VALOR = object()


class ErrorGestion(ValueError):
    """Solicitud que no puede completarse (argumentos, rutas, archivos ausentes)."""


class ErrorEvidencia(ErrorGestion):
    """Registro o evidencia ausente, alterada o contradictoria; no se persiste nada."""

    def __init__(self, mensaje: str, problemas: list[str]):
        super().__init__(mensaje + "\n" + "\n".join(f"  - {p}" for p in problemas))
        self.problemas = problemas


@dataclass
class Comprobacion:
    """Resultado de contrastar un registro con la evidencia local vigente."""

    problemas: list[str] = field(default_factory=list)
    resultado: Any = None  # ResultadoExtraccion con inventario, si pudo construirse
    inventario: dict[str, Any] | None = None
    expediente_sha256: str | None = None
    archivos_verificados: list[dict[str, str]] = field(default_factory=list)

    @property
    def correcta(self) -> bool:
        return not self.problemas and self.resultado is not None and self.resultado.consistente

    def a_dict(self) -> dict[str, Any]:
        return {
            "correcta": self.correcta,
            "problemas_evidencia": list(self.problemas),
            "expediente_sha256": self.expediente_sha256,
            "archivos_verificados": [dict(a) for a in self.archivos_verificados],
            "validacion": self.resultado.a_dict() if self.resultado is not None else None,
        }


@dataclass
class ResultadoOperacion:
    ruta: Path
    identificador: str
    comprobacion: Comprobacion
    datos: dict[str, Any]


# -- lectura y escritura -----------------------------------------------------

def json_desde_bytes(contenido: bytes, nombre: str) -> Any:
    """JSON estricto desde bytes exactos: rechaza claves repetidas y NaN/Infinity."""

    def sin_duplicados(pares: list[tuple[str, Any]]) -> dict[str, Any]:
        resultado: dict[str, Any] = {}
        for clave, valor in pares:
            if clave in resultado:
                raise ErrorGestion(f"{nombre}: clave JSON repetida '{clave}'.")
            resultado[clave] = valor
        return resultado

    def constante(valor: str) -> Any:
        raise ErrorGestion(f"{nombre}: valor no finito '{valor}' no admitido.")

    try:
        return json.loads(contenido.decode("utf-8"), object_pairs_hook=sin_duplicados, parse_constant=constante)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ErrorGestion(f"No se pudo leer {nombre}: {exc}") from exc


def leer_json(path: Path) -> Any:
    try:
        contenido = path.read_bytes()
    except FileNotFoundError as exc:
        raise ErrorGestion(f"Archivo no encontrado: {path.name}") from exc
    except OSError as exc:
        raise ErrorGestion(f"No se pudo leer {path.name}: {exc}") from exc
    return json_desde_bytes(contenido, path.name)


def _json_bytes(data: Any) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _sha256(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


def _publicar(caso_dir: Path, carpeta: str, identificador: str, archivos: dict[str, bytes]) -> Path:
    """Escribe en un temporal del mismo volumen y publica la carpeta completa con rename.

    El destino se comprueba antes de crear temporales: una carpeta enlazada
    (symlink o junction) se rechaza sin escribir nada. Ante cualquier fallo el
    temporal se elimina y no queda una versión visible.
    """
    destino_padre = _carpeta_destino(caso_dir, carpeta)
    destino = destino_padre / identificador
    with tempfile.TemporaryDirectory(prefix=".tmp-", dir=destino_padre) as staging:
        if not _misma_ruta(Path(staging).resolve().parent, destino_padre):
            raise ErrorGestion("El temporal resuelve fuera de la carpeta de destino; no se escribe.")
        preparado = Path(staging) / identificador
        preparado.mkdir()
        for nombre, contenido in archivos.items():
            (preparado / nombre).write_bytes(contenido)
        if os.path.lexists(destino):
            raise ErrorGestion("Colisión de identificador; no se sobrescribe.")
        preparado.rename(destino)
    return destino


# -- rutas -------------------------------------------------------------------

def _misma_ruta(a: Path, b: Path) -> bool:
    return os.path.normcase(str(a)) == os.path.normcase(str(b))


def _carpeta_propia(caso_dir: Path, nombre: str) -> Path:
    """Ruta de una carpeta directa del caso que no sea enlace (symlink o junction).

    `caso_dir` ya está resuelto; si la carpeta resuelve a otro lugar, es un enlace,
    apunte fuera del caso o a otra carpeta interna.
    """
    esperado = caso_dir / nombre
    if os.path.lexists(esperado) and not _misma_ruta(esperado.resolve(), esperado):
        raise ErrorGestion(
            f"La carpeta '{nombre}' es un enlace o resuelve fuera del caso; no se lee ni se escribe en ella."
        )
    return esperado


def _carpeta_destino(caso_dir: Path, nombre: str) -> Path:
    esperado = _carpeta_propia(caso_dir, nombre)
    if os.path.lexists(esperado):
        if not esperado.is_dir():
            raise ErrorGestion(f"'{nombre}' existe y no es una carpeta; no se escribe.")
    else:
        esperado.mkdir()
        _carpeta_propia(caso_dir, nombre)  # comprueba de nuevo tras crearla
    return esperado


def carpeta_caso(raiz: Path, caso: str) -> Path:
    if not isinstance(caso, str) or not re.fullmatch(PATRON_CASO, caso) or caso.upper() in RESERVED:
        raise ErrorGestion("Identificador de caso inválido; use letras, números, guion o guion bajo.")
    base = Path(raiz).resolve()
    carpeta = (base / caso).resolve()
    if carpeta == base or not carpeta.is_relative_to(base):
        raise ErrorGestion("El caso resuelve fuera de la carpeta privada.")
    if not (carpeta / "expediente.json").is_file():
        raise ErrorGestion(f"No existe el expediente del caso '{caso}'.")
    return carpeta


def _subcarpeta(caso_dir: Path, nombre: str, identificador: str) -> Path:
    if not isinstance(identificador, str) or not re.fullmatch(PATRON_VERSION, identificador):
        raise ErrorGestion("Identificador de extracción inválido; se esperan 32 caracteres hexadecimales.")
    base = _carpeta_propia(caso_dir, nombre)
    carpeta = (base / identificador).resolve()
    if not _misma_ruta(carpeta, base / identificador):
        raise ErrorGestion("La extracción es un enlace o resuelve fuera del caso.")
    if not carpeta.is_dir():
        raise ErrorGestion(f"No existe la extracción '{identificador}'.")
    return carpeta


def _archivo_del_caso(caso_dir: Path, relativo: Any, problemas: list[str], descripcion: str) -> Path | None:
    if not isinstance(relativo, str) or not relativo:
        problemas.append(f"{descripcion}: ruta no registrada.")
        return None
    ruta = (caso_dir / relativo).resolve()
    if not ruta.is_relative_to(caso_dir):
        problemas.append(f"{descripcion}: la ruta resuelve fuera del caso.")
        return None
    if not ruta.is_file():
        problemas.append(f"{descripcion}: archivo ausente ({relativo}).")
        return None
    return ruta


# -- estructura de registros auxiliares -------------------------------------
# Se valida lo que esta integración consume antes de usarlo; un registro con
# forma inesperada se informa como problema y nunca alimenta el inventario.

_AUSENTE = object()


def _tipo(valor: Any) -> str:
    if valor is None:
        return "null"
    if isinstance(valor, bool):
        return "booleano"
    return {int: "entero", float: "número", str: "texto", list: "lista", dict: "objeto"}.get(type(valor), type(valor).__name__)


def _entero_positivo(valor: Any) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool) and valor >= 1


def _entradas_expediente(expediente: Any, caso: str, problemas: list[str]) -> dict[str, dict] | None:
    if not isinstance(expediente, dict) or expediente.get("id") != caso:
        problemas.append("expediente.json inválido o de otro caso.")
        return None
    archivos = expediente.get("archivos")
    if not isinstance(archivos, list):
        problemas.append(f"expediente.json: 'archivos' debe ser una lista; se recibió {_tipo(archivos)}.")
        return None
    entradas: dict[str, dict] = {}
    for i, entrada in enumerate(archivos):
        if (
            not isinstance(entrada, dict)
            or not isinstance(entrada.get("id"), str)
            or not isinstance(entrada.get("archivo"), str)
            or not isinstance(entrada.get("sha256"), str)
        ):
            problemas.append(f"expediente.json: archivos[{i}] requiere 'id', 'archivo' y 'sha256' de tipo texto.")
            return None
        if entrada["id"] in entradas:
            problemas.append(f"expediente.json: archivo '{entrada['id']}' repetido.")
            return None
        entradas[entrada["id"]] = entrada
    return entradas


def _problemas_revision(revision: Any, caso: str, expediente_sha256: str, entradas: dict[str, dict]) -> list[str]:
    if not isinstance(revision, dict):
        return [f"se esperaba un objeto JSON; se recibió {_tipo(revision)}."]
    problemas = []
    if revision.get("caso") != caso:
        problemas.append("pertenece a otro caso.")
    if revision.get("expediente_sha256") != expediente_sha256:
        problemas.append("se generó con otro expediente; el expediente cambió.")
    documentos = revision.get("documentos", _AUSENTE)
    if not isinstance(documentos, list):
        recibido = "ausente" if documentos is _AUSENTE else _tipo(documentos)
        return problemas + [f"'documentos' debe ser una lista; se recibió {recibido}."]
    for i, documento in enumerate(documentos):
        ruta = f"documentos[{i}]"
        if not isinstance(documento, dict):
            problemas.append(f"{ruta} debe ser un objeto; se recibió {_tipo(documento)}.")
            continue
        ident = documento.get("id")
        if not isinstance(ident, str) or ident not in entradas:
            problemas.append(f"{ruta}.id {ident!r} no corresponde a un archivo del expediente.")
            continue
        if documento.get("archivo") != entradas[ident]["archivo"]:
            problemas.append(f"{ruta}.archivo no coincide con el expediente.")
        error = documento.get("error")
        if error is not None and not isinstance(error, str):
            problemas.append(f"{ruta}.error debe ser texto o null; se recibió {_tipo(error)}.")
        if "paginas_declaradas" in documento and not _entero_positivo(documento["paginas_declaradas"]):
            problemas.append(
                f"{ruta}.paginas_declaradas debe ser un entero positivo; se recibió {documento['paginas_declaradas']!r}."
            )
    return problemas


def _problemas_recorte(
    meta: Any, recorte_id: str, caso: str, expediente_sha256: str, entradas: dict[str, dict]
) -> list[str]:
    if not isinstance(meta, dict):
        return [f"se esperaba un objeto JSON; se recibió {_tipo(meta)}."]
    problemas = []
    if meta.get("id") != recorte_id:
        problemas.append("su 'id' no coincide con la carpeta del recorte.")
    if meta.get("caso") != caso:
        problemas.append("pertenece a otro caso.")
    sistema = meta.get("sistema_coordenadas", _AUSENTE)
    if sistema is _AUSENTE:
        problemas.append(f"sistema de coordenadas ausente; se requiere '{SISTEMA_COORDENADAS}'. No se convierten coordenadas.")
    elif sistema != SISTEMA_COORDENADAS:
        problemas.append(
            f"sistema de coordenadas {sistema!r} incompatible con '{SISTEMA_COORDENADAS}' del contrato y de la "
            "extracción. No se convierten coordenadas ni se reescriben metadatos."
        )
    if meta.get("expediente_sha256") != expediente_sha256:
        problemas.append("se generó con otro expediente; el expediente cambió.")
    archivo_id = meta.get("archivo_id")
    if not isinstance(archivo_id, str) or archivo_id not in entradas:
        problemas.append(f"'archivo_id' {archivo_id!r} no corresponde a un archivo del expediente.")
    elif meta.get("origen_sha256") != entradas[archivo_id]["sha256"]:
        problemas.append("su original no coincide con el expediente (origen_sha256).")
    if not _entero_positivo(meta.get("pagina")):
        problemas.append(f"'pagina' debe ser un entero positivo; se recibió {meta.get('pagina')!r}.")
    bbox = meta.get("bbox_normalizada")
    if (
        not isinstance(bbox, list)
        or len(bbox) != 4
        or not all(es_numero(v) and math.isfinite(v) for v in bbox)
        or not (0 <= bbox[0] < bbox[2] <= 1 and 0 <= bbox[1] < bbox[3] <= 1)
    ):
        problemas.append("'bbox_normalizada' debe ser [x0, y0, x1, y1] finita, entre 0 y 1 y con área positiva.")
    if not isinstance(meta.get("imagen_sha256"), str) or not re.fullmatch(PATRON_SHA256, meta["imagen_sha256"]):
        problemas.append("'imagen_sha256' debe ser un SHA256 hexadecimal en minúsculas.")
    if not isinstance(meta.get("imagen"), str) or not meta["imagen"]:
        problemas.append("'imagen' debe indicar el archivo de la imagen del recorte.")
    return problemas


# -- comprobación de evidencia ----------------------------------------------

def comprobar_evidencia(caso_dir: Path, caso: str, data: Any) -> Comprobacion:
    """Contrasta `data` con expediente, revisiones y recortes vigentes y sus hashes reales.

    No modifica archivos ni genera vistas. Los problemas se acumulan para informarlos juntos.
    """
    comp = Comprobacion()
    problemas = comp.problemas
    previo = validar_extraccion(data)
    if not previo.consistente:
        comp.resultado = previo
        return comp
    if data["caso"] != caso:
        problemas.append(f"El registro pertenece al caso '{data['caso']}', no a '{caso}'.")
    if data["procedencia"]["tipo"] != "expediente":
        problemas.append("La procedencia debe ser 'expediente'; los registros sintéticos no se importan a un caso.")

    expediente_path = caso_dir / "expediente.json"
    try:
        expediente_bytes = expediente_path.read_bytes()
    except OSError as exc:
        problemas.append(f"expediente.json ilegible: {exc}")
        return comp
    comp.expediente_sha256 = _sha256(expediente_bytes)
    try:
        expediente = json_desde_bytes(expediente_bytes, "expediente.json")
    except ErrorGestion as exc:
        problemas.append(str(exc))
        return comp
    entradas = _entradas_expediente(expediente, caso, problemas)
    if entradas is None:
        return comp
    declarado = data["procedencia"].get("expediente_sha256")
    if declarado is not None and declarado != comp.expediente_sha256:
        problemas.append("procedencia.expediente_sha256 no coincide con el expediente vigente.")

    citados_archivos = {ev["archivo_id"] for c in data["candidatos"] for ev in c["evidencia"]}
    citados_recortes = {ev["recorte_id"] for c in data["candidatos"] for ev in c["evidencia"] if "recorte_id" in ev}

    for archivo_id in sorted(citados_archivos):
        entrada = entradas.get(archivo_id)
        if entrada is None:
            problemas.append(f"Archivo citado '{archivo_id}' no registrado en el expediente.")
            continue
        ruta = _archivo_del_caso(caso_dir, entrada.get("archivo"), problemas, f"Original {archivo_id}")
        if ruta is None:
            continue
        real = file_hash(ruta)
        if real != entrada.get("sha256"):
            problemas.append(f"Original {archivo_id} alterado: su SHA256 no coincide con el expediente.")
            continue
        comp.archivos_verificados.append({"tipo": "original", "id": archivo_id, "sha256": real})

    revisiones = []
    carpeta_revisiones = caso_dir / "revision_documental"
    for ruta in sorted(carpeta_revisiones.glob("*/revision.json")) if carpeta_revisiones.is_dir() else []:
        nombre = f"Revisión {ruta.parent.name}"
        if not ruta.resolve().is_relative_to(caso_dir):
            problemas.append(f"{nombre}: resuelve fuera del caso.")
            continue
        try:
            revision = leer_json(ruta)
        except ErrorGestion as exc:
            problemas.append(f"{nombre}: registro ilegible. {exc}")
            continue
        errores_revision = _problemas_revision(revision, caso, comp.expediente_sha256, entradas)
        if errores_revision:
            problemas.extend(f"{nombre} (revision.json): {p}" for p in errores_revision)
            continue  # una revisión inválida no alimenta el inventario
        revisiones.append(revision)

    recortes = []
    for recorte_id in sorted(citados_recortes):
        if not re.fullmatch(PATRON_RECORTE, recorte_id):
            problemas.append(f"Recorte '{recorte_id}': identificador inválido.")
            continue
        nombre = f"Recorte {recorte_id}"
        ruta = _archivo_del_caso(caso_dir, f"recortes/{recorte_id}/recorte.json", problemas, nombre)
        if ruta is None:
            continue
        try:
            meta = leer_json(ruta)
        except ErrorGestion as exc:
            problemas.append(f"{nombre}: registro ilegible. {exc}")
            continue
        errores_recorte = _problemas_recorte(meta, recorte_id, caso, comp.expediente_sha256, entradas)
        if errores_recorte:
            problemas.extend(f"{nombre} (recorte.json): {p}" for p in errores_recorte)
            continue
        imagen = _archivo_del_caso(ruta.parent, meta["imagen"], problemas, f"Imagen del recorte {recorte_id}")
        if imagen is None:
            continue
        real = file_hash(imagen)
        if real != meta.get("imagen_sha256"):
            problemas.append(f"Imagen del recorte {recorte_id} alterada: su SHA256 no coincide con el registro.")
            continue
        comp.archivos_verificados.append({"tipo": "imagen_recorte", "id": recorte_id, "sha256": real})
        recortes.append(meta)

    try:
        comp.inventario = inventario_desde(expediente, revisiones, recortes)
    except ErrorExtraccion as exc:
        problemas.append(f"Inventario de evidencia contradictorio: {exc}")
        return comp
    comp.resultado = validar_extraccion(data, comp.inventario)
    return comp


def _exigir(comp: Comprobacion, accion: str) -> None:
    if comp.correcta:
        return
    problemas = list(comp.problemas)
    if comp.resultado is not None:
        problemas += [str(e) for e in comp.resultado.errores]
    raise ErrorEvidencia(f"{accion}: la evidencia o el registro no superan la comprobación.", problemas)


# -- versiones ---------------------------------------------------------------

def _huella_segura(data: Any) -> str | None:
    try:
        return huella(data)
    except (TypeError, ValueError):
        return None


def _problemas_fuente(carpeta: Path, meta: dict, data: Any, etiqueta: str) -> list[str]:
    """Comprueba fuente_importada.json de una versión de importación.

    El SHA256 se calcula sobre los bytes exactos conservados; el contenido se
    compara por huella canónica con extraccion.json, que puede tener otro formato.
    """
    fuente = meta.get("fuente")
    if (
        not isinstance(fuente, dict)
        or fuente.get("archivo") != ARCHIVO_FUENTE
        or not isinstance(fuente.get("sha256"), str)
    ):
        return [f"{etiqueta}: el registro de la fuente importada en version.json falta o es inválido."]
    ruta = carpeta / ARCHIVO_FUENTE
    if os.path.lexists(ruta) and not _misma_ruta(ruta.resolve(), ruta):
        return [f"{etiqueta}: la fuente importada es un enlace o resuelve fuera de la versión."]
    try:
        contenido = ruta.read_bytes()
    except FileNotFoundError:
        return [f"{etiqueta}: fuente importada ausente ({ARCHIVO_FUENTE})."]
    except OSError as exc:
        return [f"{etiqueta}: fuente importada ilegible: {exc}"]
    if _sha256(contenido) != fuente["sha256"]:
        return [f"{etiqueta}: fuente importada alterada; su SHA256 no coincide con version.json."]
    try:
        original = json_desde_bytes(contenido, ARCHIVO_FUENTE)
    except ErrorGestion as exc:
        return [f"{etiqueta}: fuente importada ilegible. {exc}"]
    referencia = _huella_segura(data)
    if referencia is None or _huella_segura(original) != referencia:
        return [f"{etiqueta}: la fuente importada no corresponde al registro extraccion.json."]
    return []


def _problemas_operacion(carpeta: Path, meta: dict, data: Any, etiqueta: str) -> list[str]:
    operacion = meta.get("operacion")
    if operacion == "importacion":
        if meta.get("padre") is not None:
            return [f"{etiqueta}: una importación no puede tener versión padre."]
        return _problemas_fuente(carpeta, meta, data, etiqueta)
    if operacion in ("correccion", "migracion_semantica", "reubicacion_evidencia", "lectura_manual"):
        if not isinstance(meta.get("padre"), dict):
            return [f"{etiqueta}: una {operacion} requiere versión padre."]
        return []  # las versiones derivadas no guardan fuente importada
    return [f"{etiqueta}: operación {operacion!r} desconocida en version.json."]


def _leer_version(carpeta: Path) -> tuple[Any, Any]:
    try:
        return leer_json(carpeta / "version.json"), leer_json(carpeta / "extraccion.json")
    except ErrorGestion as exc:
        raise ErrorEvidencia(f"Versión {carpeta.name} ilegible.", [str(exc)]) from exc


def cargar_version(caso_dir: Path, caso: str, extraccion_id: str) -> tuple[Any, dict[str, Any], list[str]]:
    """Lee una versión y comprueba su huella, su fuente y la cadena de versiones padre.

    Devuelve (registro, metadatos, problemas). Detecta cambios accidentales; no
    protege contra una edición deliberada que también rehaga las huellas.
    """
    carpeta = _subcarpeta(caso_dir, CARPETA_VERSIONES, extraccion_id)
    meta, data = _leer_version(carpeta)
    if not isinstance(meta, dict) or meta.get("id") != extraccion_id or meta.get("caso") != caso:
        raise ErrorEvidencia(f"Versión {extraccion_id} rechazada.", ["version.json inválido o de otro caso."])
    problemas: list[str] = []
    if _huella_segura(data) != meta.get("huella_extraccion"):
        problemas.append("extraccion.json cambió después de registrarse (huella distinta).")
    problemas += _problemas_operacion(carpeta, meta, data, f"Versión {extraccion_id}")
    vistos = {extraccion_id}
    padre = meta.get("padre")
    while padre is not None:
        pid = padre.get("id") if isinstance(padre, dict) else None
        if not isinstance(pid, str) or pid in vistos:
            problemas.append("Vínculo con la versión padre inválido o circular.")
            break
        vistos.add(pid)
        try:
            pcarpeta = _subcarpeta(caso_dir, CARPETA_VERSIONES, pid)
            pmeta, pdata = _leer_version(pcarpeta)
        except ErrorGestion as exc:
            problemas.append(f"Versión padre {pid}: {exc}")
            break
        esperado = padre.get("huella_extraccion")
        if not isinstance(pmeta, dict) or _huella_segura(pdata) != esperado or pmeta.get("huella_extraccion") != esperado:
            problemas.append(f"Versión padre {pid} no coincide con la huella registrada.")
            break
        problemas += _problemas_operacion(pcarpeta, pmeta, pdata, f"Versión padre {pid}")
        padre = pmeta.get("padre")
    return data, meta, problemas


def _metadatos(caso: str, operacion: str, data: dict, comp: Comprobacion, **extra: Any) -> dict[str, Any]:
    return {
        "version_registro": VERSION_REGISTRO,
        "caso": caso,
        "operacion": operacion,
        "creado_utc": datetime.now(timezone.utc).isoformat(),
        "huella_extraccion": huella(data),
        "expediente_sha256": comp.expediente_sha256,
        "archivos_verificados": comp.archivos_verificados,
        "revision_tecnica": "pendiente",
        "aprobacion_ingenieria": None,
        **extra,
    }


def _guardar_version(caso_dir: Path, data: dict, meta: dict, comp: Comprobacion, extra: dict[str, bytes]) -> ResultadoOperacion:
    identificador = uuid4().hex
    meta = {"id": identificador, **meta}
    archivos = {
        "extraccion.json": _json_bytes(data),
        "reporte.json": _json_bytes(comp.a_dict()),
        "version.json": _json_bytes(meta),
        **extra,
    }
    destino = _publicar(caso_dir, CARPETA_VERSIONES, identificador, archivos)
    return ResultadoOperacion(destino, identificador, comp, meta)


# -- operaciones -------------------------------------------------------------

def importar_extraccion(raiz: Path, caso: str, entrada: Path) -> ResultadoOperacion:
    """Valida una extracción con la evidencia vigente y la guarda como versión nueva."""
    caso_dir = carpeta_caso(raiz, caso)
    entrada = Path(entrada)
    try:
        fuente = entrada.read_bytes()
    except OSError as exc:
        raise ErrorGestion(f"No se pudo leer la entrada {entrada.name}: {exc}") from exc
    data = json_desde_bytes(fuente, entrada.name)  # mismos bytes que se conservan como fuente
    comp = comprobar_evidencia(caso_dir, caso, data)
    _exigir(comp, "Importación rechazada")
    meta = _metadatos(
        caso, "importacion", data, comp, padre=None,
        fuente={"nombre": entrada.name, "sha256": _sha256(fuente), "archivo": ARCHIVO_FUENTE},
    )
    return _guardar_version(caso_dir, data, meta, comp, {ARCHIVO_FUENTE: fuente})


def _comprobar_version(caso_dir: Path, caso: str, extraccion_id: str) -> tuple[Any, dict, Comprobacion]:
    data, meta, problemas = cargar_version(caso_dir, caso, extraccion_id)
    comp = comprobar_evidencia(caso_dir, caso, data)
    comp.problemas[:0] = problemas
    if comp.expediente_sha256 is not None and comp.expediente_sha256 != meta.get("expediente_sha256"):
        comp.problemas.append("El expediente cambió desde que se registró esta versión.")
    return data, meta, comp


def validar_version(raiz: Path, caso: str, extraccion_id: str) -> Comprobacion:
    """Vuelve a comprobar una versión registrada sin modificar nada."""
    return _comprobar_version(carpeta_caso(raiz, caso), caso, extraccion_id)[2]


def _cargar_comprobada(raiz: Path, caso: str, extraccion_id: str, accion: str) -> tuple[Path, dict, dict, Comprobacion]:
    caso_dir = carpeta_caso(raiz, caso)
    data, meta, comp = _comprobar_version(caso_dir, caso, extraccion_id)
    _exigir(comp, accion)
    return caso_dir, data, meta, comp


def corregir_version(
    raiz: Path,
    caso: str,
    extraccion_id: str,
    candidato_id: str,
    *,
    estado: str,
    motivo: str,
    fecha: str,
    revisor_declarado: str,
    valor_revisado: Any = SIN_VALOR,
    unidad_revisada: Any = SIN_VALOR,
    tipo_revisado: Any = SIN_VALOR,
) -> ResultadoOperacion:
    """Crea una versión hija con la corrección; la versión padre queda intacta."""
    caso_dir, data, meta, _ = _cargar_comprobada(raiz, caso, extraccion_id, "Corrección rechazada")
    argumentos: dict[str, Any] = {}
    if valor_revisado is not SIN_VALOR:
        argumentos["valor_revisado"] = valor_revisado
    if unidad_revisada is not SIN_VALOR:
        argumentos["unidad_revisada"] = unidad_revisada
    if tipo_revisado is not SIN_VALOR:
        argumentos["tipo_revisado"] = tipo_revisado
    try:
        nuevo = corregir(
            data, candidato_id, estado=estado, motivo=motivo, fecha=fecha,
            revisor_declarado=revisor_declarado, **argumentos,
        )
    except ErrorExtraccion as exc:
        raise ErrorEvidencia("Corrección rechazada.", [str(exc)]) from exc
    comp = comprobar_evidencia(caso_dir, caso, nuevo)
    _exigir(comp, "Corrección rechazada")
    nueva_meta = _metadatos(
        caso, "correccion", nuevo, comp,
        padre={"id": extraccion_id, "huella_extraccion": meta["huella_extraccion"]},
        correccion={"candidato": candidato_id, "estado": estado, "revisor_declarado": revisor_declarado,
                    "identidad_revisor": "declarada_no_verificada"},
    )
    return _guardar_version(caso_dir, nuevo, nueva_meta, comp, {})


def migrar_version(raiz: Path, caso: str, extraccion_id: str, propuestas: Any, *, origen: str,
                   cobertura: Any = None) -> ResultadoOperacion:
    """Deriva una versión 0.2.0 de otra 0.1.0 sin alterar lecturas ni revisiones.

    `propuestas` ({candidato: {tipo, valor, unidad, motivo[, simbolo]}}) se guardan como
    `clasificacion_propuesta` pendiente: no cambian tipo/valor/unidad leídos ni aprueban nada; el
    revisor las acepta o corrige con `tipo_revisado`. `cobertura` opcional: lista por recorte.
    """
    caso_dir, data, meta, _ = _cargar_comprobada(raiz, caso, extraccion_id, "Migración rechazada")
    if data.get("version_contrato") != VERSION_EXTRACCION:
        raise ErrorEvidencia("Migración rechazada.", ["Solo se migran versiones 0.1.0."])
    if not isinstance(origen, str) or not origen.strip():
        raise ErrorEvidencia("Migración rechazada.", ["Declara el origen de las propuestas."])
    if not isinstance(propuestas, dict):
        raise ErrorEvidencia("Migración rechazada.", ["Las propuestas deben ser un objeto por candidato."])
    nuevo = copy.deepcopy(data)
    nuevo["version_contrato"] = VERSION_SEMANTICA
    por_id = {c["id"]: c for c in nuevo["candidatos"]}
    ajenos = sorted(set(propuestas) - set(por_id))
    if ajenos:
        raise ErrorEvidencia("Migración rechazada.", [f"Candidatos inexistentes: {', '.join(map(str, ajenos))}."])
    for ident, propuesta in propuestas.items():
        if not isinstance(propuesta, dict):
            raise ErrorEvidencia("Migración rechazada.", [f"{ident}: propuesta inválida."])
        por_id[ident]["clasificacion_propuesta"] = {**copy.deepcopy(propuesta), "origen": origen}
    if cobertura is not None:
        nuevo["cobertura"] = copy.deepcopy(cobertura)
    comp = comprobar_evidencia(caso_dir, caso, nuevo)
    _exigir(comp, "Migración rechazada")
    nueva_meta = _metadatos(
        caso, "migracion_semantica", nuevo, comp,
        padre={"id": extraccion_id, "huella_extraccion": meta["huella_extraccion"]},
        migracion={"de": VERSION_EXTRACCION, "a": VERSION_SEMANTICA, "propuestas": len(propuestas),
                   "origen_declarado": origen, "aprueba_lecturas": False},
    )
    return _guardar_version(caso_dir, nuevo, nueva_meta, comp, {})


def _version_semantica(data: dict, accion: str) -> None:
    if data.get("version_contrato") != VERSION_SEMANTICA:
        raise ErrorEvidencia(f"{accion} rechazada.", ["Requiere una versión 0.2.0; use migrar-extraccion primero."])


def reubicar_evidencia(raiz: Path, caso: str, extraccion_id: str, candidato_id: str, *, bbox: Any, motivo: str,
                       fecha: str, revisor_declarado: str, indice: int = 0) -> ResultadoOperacion:
    """Versión hija con la región corregida sobre la misma página original; conserva la región anterior.

    No cambia valor, unidad, tipo ni estado de revisión: corregir la evidencia no aprueba la lectura.
    """
    caso_dir, data, meta, _ = _cargar_comprobada(raiz, caso, extraccion_id, "Reubicación rechazada")
    _version_semantica(data, "Reubicación")
    nuevo = copy.deepcopy(data)
    cand = next((c for c in nuevo["candidatos"] if c["id"] == candidato_id), None)
    if cand is None or type(indice) is not int or not 0 <= indice < len(cand["evidencia"]):
        raise ErrorEvidencia("Reubicación rechazada.", ["Candidato o índice de evidencia inexistente."])
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        raise ErrorEvidencia("Reubicación rechazada.", ["bbox requiere [x0, y0, x1, y1] en página visible normalizada."])
    anterior = cand["evidencia"][indice]["bbox_normalizada"]
    cand["evidencia"][indice]["bbox_normalizada"] = list(bbox)
    cand.setdefault("historial_evidencia", []).append({
        "indice": indice, "bbox_anterior": copy.deepcopy(anterior), "bbox_nueva": list(bbox), "motivo": motivo,
        "fecha": fecha, "revisor_declarado": revisor_declarado})
    comp = comprobar_evidencia(caso_dir, caso, nuevo)
    _exigir(comp, "Reubicación rechazada")
    nueva_meta = _metadatos(
        caso, "reubicacion_evidencia", nuevo, comp,
        padre={"id": extraccion_id, "huella_extraccion": meta["huella_extraccion"]},
        reubicacion={"candidato": candidato_id, "indice": indice, "revisor_declarado": revisor_declarado,
                     "identidad_revisor": "declarada_no_verificada", "aprueba_lectura": False})
    return _guardar_version(caso_dir, nuevo, nueva_meta, comp, {})


def agregar_lectura(raiz: Path, caso: str, extraccion_id: str, *, tipo: str, valor: Any, unidad: str,
                    texto_fuente: str, archivo_id: str, pagina: int, bbox: Any, motivo: str, fecha: str,
                    revisor_declarado: str, simbolo: str | None = None) -> ResultadoOperacion:
    """Alta manual de una lectura visible omitida: procedencia manual explícita, ID «M###» nuevo y revisión pendiente.

    Exige texto literal y evidencia en el original con hash comprobado. No sirve para declarar datos que no constan
    en el original (E, alturas, apoyos…): eso es una hipótesis técnica, no una lectura.
    """
    caso_dir, data, meta, _ = _cargar_comprobada(raiz, caso, extraccion_id, "Lectura manual rechazada")
    _version_semantica(data, "Lectura manual")
    if not isinstance(texto_fuente, str) or not texto_fuente.strip():
        raise ErrorEvidencia("Lectura manual rechazada.", ["Transcribe el texto literal impreso (texto_fuente)."])
    expediente = leer_json(caso_dir / "expediente.json")
    entrada = next((a for a in expediente.get("archivos", []) if isinstance(a, dict) and a.get("id") == archivo_id), None)
    if entrada is None:
        raise ErrorEvidencia("Lectura manual rechazada.", [f"Original {archivo_id!r} inexistente en el expediente."])
    nuevo = copy.deepcopy(data)
    ids = {c["id"] for c in nuevo["candidatos"]}
    n = 1
    while f"M{n:03d}" in ids:
        n += 1
    ident = f"M{n:03d}"
    cand = {"id": ident, "tipo": tipo, "valor_propuesto": copy.deepcopy(valor), "unidad": unidad,
            "texto_fuente": texto_fuente,
            "metodo": {"tipo": "manual", "herramienta": "lectura_manual_revisor",
                       "descripcion": f"Ingreso manual declarado por {revisor_declarado} ({fecha}): {motivo}. "
                                      "No proviene de un modelo de IA."},
            "evidencia": [{"archivo_id": archivo_id, "pagina": pagina, "original_sha256": entrada.get("sha256"),
                           "bbox_normalizada": list(bbox) if isinstance(bbox, (list, tuple)) else bbox}],
            "revision": {"estado": "pendiente", "historial": []}}
    if simbolo is not None:
        cand["simbolo"] = simbolo
    nuevo["candidatos"].append(cand)
    comp = comprobar_evidencia(caso_dir, caso, nuevo)
    _exigir(comp, "Lectura manual rechazada")
    nueva_meta = _metadatos(
        caso, "lectura_manual", nuevo, comp,
        padre={"id": extraccion_id, "huella_extraccion": meta["huella_extraccion"]},
        lectura={"candidato": ident, "revisor_declarado": revisor_declarado,
                 "identidad_revisor": "declarada_no_verificada", "aprueba_lectura": False})
    return _guardar_version(caso_dir, nuevo, nueva_meta, comp, {})


def _firma_candidato(c: dict) -> str:
    return huella({k: c.get(k) for k in ("tipo", "valor_propuesto", "unidad", "evidencia", "revision", "texto_fuente")})


def vigencia(raiz: Path, caso: str, extraccion_id: str) -> dict[str, Any]:
    """Versiones descendientes y exportaciones de esta versión cuyos candidatos cambiaron después.

    Una exportación queda «superada» si algún candidato exportado cambió (evidencia, valor, tipo o revisión) en una
    versión descendiente: sus derivados (geometría, configuración…) no heredan vigencia de la versión nueva.
    """
    caso_dir = carpeta_caso(raiz, caso)
    data, _, _ = cargar_version(caso_dir, caso, extraccion_id)
    base = {c["id"]: _firma_candidato(c) for c in data["candidatos"]}
    hijos: dict[str, list[str]] = {}
    for meta_path in (caso_dir / CARPETA_VERSIONES).glob("*/version.json"):
        try:
            m = leer_json(meta_path)
        except ErrorGestion:
            continue
        padre = m.get("padre") if isinstance(m, dict) else None
        if isinstance(padre, dict) and isinstance(padre.get("id"), str):
            hijos.setdefault(padre["id"], []).append(meta_path.parent.name)
    descendientes, pendientes = [], list(hijos.get(extraccion_id, []))
    while pendientes:
        vid = pendientes.pop()
        d, m, _ = cargar_version(caso_dir, caso, vid)
        firmas = {c["id"]: _firma_candidato(c) for c in d["candidatos"]}
        descendientes.append({"id": vid, "operacion": m.get("operacion"),
                              "cambiados": sorted(k for k in base if k in firmas and firmas[k] != base[k]),
                              "nuevos": sorted(set(firmas) - set(base))})
        pendientes += hijos.get(vid, [])
    cambiados = {k for d in descendientes for k in d["cambiados"]}
    exportaciones = []
    for exp_path in (caso_dir / CARPETA_EXPORTACIONES).glob("*/exportacion.json"):
        try:
            exp = leer_json(exp_path)
        except ErrorGestion:
            continue
        if isinstance(exp, dict) and exp.get("origen", {}).get("extraccion_id") == extraccion_id:
            afectados = sorted(cambiados & {c.get("id") for c in exp.get("candidatos", [])})
            exportaciones.append({"id": exp_path.parent.name, "estado": "superada" if afectados else "vigente",
                                  "candidatos_afectados": afectados})
    return {"extraccion": extraccion_id, "descendientes": descendientes, "exportaciones": exportaciones,
            "aviso": "Una versión nueva no traslada vigencia a derivados de versiones anteriores."}


def exportar_version(raiz: Path, caso: str, extraccion_id: str) -> ResultadoOperacion:
    """Exporta solo candidatos revisados con inventario comprobado, en carpeta nueva."""
    caso_dir, data, meta, comp = _cargar_comprobada(raiz, caso, extraccion_id, "Exportación rechazada")
    try:
        exportacion = exportar_revisados(data, comp.inventario)
    except ErrorExtraccion as exc:
        raise ErrorEvidencia("Exportación rechazada.", [str(exc)]) from exc
    exportacion["origen"] = {
        "extraccion_id": extraccion_id,
        "huella_extraccion": meta["huella_extraccion"],
        "expediente_sha256": comp.expediente_sha256,
        "archivos_verificados": comp.archivos_verificados,
        "exportado_utc": datetime.now(timezone.utc).isoformat(),
    }
    identificador = uuid4().hex
    destino = _publicar(
        caso_dir, CARPETA_EXPORTACIONES, identificador, {"exportacion.json": _json_bytes(exportacion)}
    )
    return ResultadoOperacion(destino / "exportacion.json", identificador, comp, exportacion)
