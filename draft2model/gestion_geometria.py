"""Versiones inmutables de geometría dentro de los expedientes privados.

Importa, consulta, revisa y aprueba contratos `draft2model.geometria` en
`<raiz>/<caso>/geometrias/<uuid>/`. Cada operación crea una carpeta nueva; las
anteriores no se modifican. Antes de escribir y al comprobar se verifican el
expediente, los SHA256 de sus originales, la geometría, los metadatos, la fuente
importada y la cadena de versiones padre.

No convierte lecturas en geometría, no genera planes ni modelos y no ejecuta
ETABS. La identidad del revisor es declarada: una aprobación registrada no
certifica seguridad estructural ni aprueba artefactos derivados.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from . import contratos as c
from .gestion_extraccion import (
    ErrorEvidencia,
    ErrorGestion,
    _archivo_del_caso,
    _carpeta_propia,
    _entradas_expediente,
    _misma_ruta,
    _publicar,
    carpeta_caso,
    json_desde_bytes,
)
from .ingreso import file_hash
from .validacion_geometria import validar_geometria

__all__ = [
    "ErrorGestion",
    "ErrorEvidencia",
    "ComprobacionGeometria",
    "ResultadoGeometria",
    "ConsultaGeometria",
    "importar_geometria",
    "comprobar_version",
    "consultar_version",
    "revisar_geometria",
    "migrar_geometria_superficies",
    "aprobar_geometria",
]

TIPO_REGISTRO = "draft2model.version_geometria"
VERSION_REGISTRO = "0.1.0"
CARPETA_GEOMETRIAS = "geometrias"
ARCHIVO_GEOMETRIA = "geometria.json"
ARCHIVO_METADATOS = "version.json"
ARCHIVO_FUENTE = "fuente_importada.json"
PATRON_VERSION = r"[0-9a-f]{32}"
OPERACIONES = ("importacion", "revision", "aprobacion")
IDENTIDAD_REVISOR = "declarada_no_verificada"

AVISO = (
    "Versión geométrica registrada localmente. La identidad y competencia del revisor no están "
    "autenticadas; una aprobación no certifica seguridad estructural ni aprueba planes, modelos o "
    "resultados derivados. Todo artefacto derivado debe citar la versión y la huella exactas."
)


@dataclass
class ComprobacionGeometria:
    """Resultado de comprobar una versión y su cadena de padres con la evidencia vigente."""

    caso: str
    version_id: str
    problemas: list[str] = field(default_factory=list)
    expediente_sha256: str | None = None
    originales_verificados: list[dict[str, str]] = field(default_factory=list)
    sha256_geometria: str | None = None
    huella_contenido: str | None = None
    cadena: list[str] = field(default_factory=list)  # versión comprobada y sus padres, en ese orden
    validacion: dict[str, Any] | None = None

    @property
    def correcta(self) -> bool:
        return not self.problemas

    def a_dict(self) -> dict[str, Any]:
        return {
            "caso": self.caso,
            "version_id": self.version_id,
            "correcta": self.correcta,
            "problemas": list(self.problemas),
            "expediente_sha256": self.expediente_sha256,
            "originales_verificados": [dict(o) for o in self.originales_verificados],
            "sha256_geometria": self.sha256_geometria,
            "huella_contenido": self.huella_contenido,
            "cadena": list(self.cadena),
            "validacion": copy.deepcopy(self.validacion),
        }


@dataclass
class ResultadoGeometria:
    caso: str
    identificador: str
    ruta: Path
    comprobacion: ComprobacionGeometria
    metadatos: dict[str, Any]


@dataclass
class ConsultaGeometria:
    caso: str
    identificador: str
    ruta: Path
    geometria: Any
    metadatos: Any
    comprobacion: ComprobacionGeometria


# -- utilidades --------------------------------------------------------------

def _sha256(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


def _json_bytes(data: Any) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _canonico(data: Any) -> str | None:
    """SHA256 del JSON canónico completo; None si no es serializable de forma estricta."""
    try:
        texto = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError):
        return None
    return _sha256(texto.encode("utf-8"))


def _aprobacion_geometrica_vigente(resultado):
    if resultado.version_contrato in (c.VERSION_GEOMETRIA_SUPERFICIES, c.VERSION_GEOMETRIA_ABERTURAS):
        return resultado.aprobacion_geometrica_vigente
    return resultado.disponible_para_modelado  # compatibilidad exacta de v0.1


def _resumen_validacion(resultado) -> dict[str, Any]:
    salida = resultado.a_dict()
    return {
        clave: salida[clave]
        for clave in ("consistente", "disponible_para_modelado", "datos_sinteticos",
                      "errores", "advertencias", "faltantes", "bloqueos", "huella_contenido")
    }


def _texto(valor: Any, nombre: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ErrorGestion(f"'{nombre}' es obligatorio y debe ser texto no vacío.")
    return valor


def _fecha(valor: Any) -> str:
    try:
        if isinstance(valor, str) and len(valor) == 10 and date.fromisoformat(valor):
            return valor
    except ValueError:
        pass
    raise ErrorGestion("'fecha' debe tener formato AAAA-MM-DD.")


def _carpeta_version(caso_dir: Path, version_id: str) -> Path:
    if not isinstance(version_id, str) or not re.fullmatch(PATRON_VERSION, version_id):
        raise ErrorGestion("Identificador de versión geométrica inválido; se esperan 32 caracteres hexadecimales.")
    base = _carpeta_propia(caso_dir, CARPETA_GEOMETRIAS)  # rechaza symlinks y junctions
    carpeta = base / version_id
    if os.path.lexists(carpeta) and not _misma_ruta(carpeta.resolve(), carpeta):
        raise ErrorGestion("La versión geométrica es un enlace o resuelve fuera del caso.")
    if not carpeta.is_dir():
        raise ErrorGestion(f"No existe la versión geométrica '{version_id}'.")
    return carpeta


def _leer_archivo(carpeta: Path, nombre: str, problemas: list[str], etiqueta: str) -> bytes | None:
    ruta = carpeta / nombre
    if os.path.lexists(ruta) and not _misma_ruta(ruta.resolve(), ruta):
        problemas.append(f"{etiqueta}: {nombre} es un enlace o resuelve fuera de la versión.")
        return None
    try:
        return ruta.read_bytes()
    except FileNotFoundError:
        problemas.append(f"{etiqueta}: {nombre} ausente.")
    except OSError as exc:
        problemas.append(f"{etiqueta}: {nombre} ilegible: {exc}")
    return None


def _parsear(contenido: bytes, nombre: str, problemas: list[str], etiqueta: str) -> Any:
    try:
        return json_desde_bytes(contenido, nombre)
    except ErrorGestion as exc:
        problemas.append(f"{etiqueta}: {exc}")
        return None


# -- expediente --------------------------------------------------------------

@dataclass
class _Expediente:
    sha256: str | None
    alcance: Any
    originales: list[dict[str, str]]
    problemas: list[str]


def _comprobar_expediente(caso_dir: Path, caso: str) -> _Expediente:
    """Huella de expediente.json y SHA256 recalculado de cada original registrado."""
    problemas: list[str] = []
    try:
        contenido = (caso_dir / "expediente.json").read_bytes()
    except OSError as exc:
        return _Expediente(None, None, [], [f"expediente.json ilegible: {exc}"])
    sha = _sha256(contenido)
    expediente = _parsear(contenido, "expediente.json", problemas, "Expediente")
    if expediente is None:
        return _Expediente(sha, None, [], problemas)
    entradas = _entradas_expediente(expediente, caso, problemas)
    if entradas is None:
        return _Expediente(sha, None, [], problemas)
    if not entradas:
        problemas.append("expediente.json no registra originales.")
    originales = []
    for ident, entrada in entradas.items():
        ruta = _archivo_del_caso(caso_dir, entrada["archivo"], problemas, f"Original {ident}")
        if ruta is None:
            continue
        real = file_hash(ruta)
        if real != entrada["sha256"]:
            problemas.append(f"Original {ident} alterado: su SHA256 no coincide con el expediente.")
            continue
        originales.append({"id": ident, "sha256": real})
    return _Expediente(sha, copy.deepcopy(expediente.get("alcance")), originales, problemas)


# -- comprobación de versiones ----------------------------------------------

def _comprobar_una(
    caso_dir: Path, caso: str, version_id: str, problemas: list[str], expediente: _Expediente,
) -> tuple[Any, Any, Any]:
    """Comprueba una versión sin recorrer sus padres. Devuelve (geometria, metadatos, resultado)."""
    etiqueta = f"Versión {version_id}"
    try:
        carpeta = _carpeta_version(caso_dir, version_id)
    except ErrorGestion as exc:
        problemas.append(f"{etiqueta}: {exc}")
        return None, None, None
    bytes_meta = _leer_archivo(carpeta, ARCHIVO_METADATOS, problemas, etiqueta)
    bytes_geo = _leer_archivo(carpeta, ARCHIVO_GEOMETRIA, problemas, etiqueta)
    if bytes_meta is None or bytes_geo is None:
        return None, None, None
    meta = _parsear(bytes_meta, ARCHIVO_METADATOS, problemas, etiqueta)
    geometria = _parsear(bytes_geo, ARCHIVO_GEOMETRIA, problemas, etiqueta)
    if not isinstance(meta, dict) or geometria is None:
        if meta is not None and not isinstance(meta, dict):
            problemas.append(f"{etiqueta}: {ARCHIVO_METADATOS} no es un objeto.")
        return geometria, None, None

    esperado = {
        "tipo": TIPO_REGISTRO, "version_registro": VERSION_REGISTRO,
        "id": version_id, "caso": caso,
        "contrato_geometria": {"contrato": c.CONTRATO_GEOMETRIA, "version_contrato": geometria.get("version_contrato") if isinstance(geometria, dict) else None},
        "identidad_revisor": IDENTIDAD_REVISOR, "aviso": AVISO,
        "originales_verificados": expediente.originales,
    }
    for clave, valor in esperado.items():
        if clave not in meta or _canonico(meta[clave]) != _canonico(valor):
            problemas.append(f"{etiqueta}: metadato '{clave}' no corresponde ({valor!r} esperado).")
    if meta.get("expediente_sha256") != expediente.sha256:
        problemas.append(f"{etiqueta}: el expediente cambió desde que se registró esta versión.")
    if _canonico(meta.get("alcance")) != _canonico(expediente.alcance):
        problemas.append(f"{etiqueta}: el alcance de la versión no coincide con el del expediente.")
    operacion = meta.get("operacion")
    if operacion not in OPERACIONES:
        problemas.append(f"{etiqueta}: operación desconocida en {ARCHIVO_METADATOS}.")
    if _sha256(bytes_geo) != meta.get("sha256_geometria"):
        problemas.append(f"{etiqueta}: {ARCHIVO_GEOMETRIA} alterado; su SHA256 no coincide con los metadatos.")

    resultado = validar_geometria(geometria)
    if not resultado.consistente:
        problemas.append(f"{etiqueta}: la geometría guardada es inconsistente.")
        problemas.extend(f"{etiqueta}: {e}" for e in resultado.errores)
        return geometria, meta, resultado
    if resultado.huella_contenido != meta.get("huella_contenido"):
        problemas.append(f"{etiqueta}: la huella del contenido no coincide con los metadatos.")
    if geometria.get("id") != caso:
        problemas.append(f"{etiqueta}: la geometría pertenece al caso '{geometria.get('id')}'.")
    if meta.get("datos_sinteticos") is not resultado.datos_sinteticos:
        problemas.append(f"{etiqueta}: la marca de datos sintéticos no corresponde a la procedencia.")
    for clave, valor in {
        "procedencia": geometria["procedencia"],
        "validacion": _resumen_validacion(resultado),
        "estado_revision_geometria": geometria["revision"]["estado"],
    }.items():
        if clave not in meta or _canonico(meta[clave]) != _canonico(valor):
            problemas.append(f"{etiqueta}: metadato '{clave}' no corresponde a la geometría validada.")

    revision = geometria["revision"]
    padre = meta.get("padre")
    if operacion == "importacion":
        if padre is not None:
            problemas.append(f"{etiqueta}: una importación no tiene versión padre.")
        if revision["estado"] == "aprobado" or revision["aprobacion"] is not None:
            problemas.append(f"{etiqueta}: una importación no puede contener una aprobación.")
        problemas.extend(_problemas_fuente(carpeta, meta, geometria, etiqueta))
    elif operacion == "revision":
        if not isinstance(padre, dict):
            problemas.append(f"{etiqueta}: una revisión requiere versión padre.")
        if revision["estado"] != "borrador" or revision["aprobacion"] is not None:
            problemas.append(f"{etiqueta}: una revisión debe quedar en borrador y sin aprobación.")
        registro = meta.get("revision")
        if not isinstance(registro, dict) or not all(
            isinstance(registro.get(k), str) and registro[k].strip() for k in ("motivo", "fecha", "revisor_declarado")
        ):
            problemas.append(f"{etiqueta}: faltan motivo, fecha o revisor de la revisión.")
        elif registro.get("identidad_revisor") != IDENTIDAD_REVISOR:
            problemas.append(f"{etiqueta}: identidad del revisor de la revisión inválida.")
        else:
            try:
                _fecha(registro["fecha"])
            except ErrorGestion:
                problemas.append(f"{etiqueta}: fecha de revisión inválida.")
    elif operacion == "aprobacion":
        if not isinstance(padre, dict):
            problemas.append(f"{etiqueta}: una aprobación requiere versión padre.")
        registro = meta.get("aprobacion")
        if not _aprobacion_geometrica_vigente(resultado):
            problemas.append(f"{etiqueta}: la aprobación no está vigente para el contenido guardado.")
        if not isinstance(registro, dict) or registro.get("huella_contenido") != resultado.huella_contenido:
            problemas.append(f"{etiqueta}: el registro de aprobación no corresponde a la huella del contenido.")
        aprobacion = revision["aprobacion"]
        esperado_aprobacion = {
            "huella_contenido": resultado.huella_contenido,
            "huella_esperada": resultado.huella_contenido,
            "revisor_declarado": aprobacion["declarada_por"], "fecha": aprobacion["fecha"],
            "motivo": aprobacion.get("observaciones"), "alcance_revision": aprobacion.get("alcance"),
            "identidad_revisor": IDENTIDAD_REVISOR,
            "certifica_seguridad_estructural": False, "aprueba_artefactos_derivados": False,
        } if isinstance(aprobacion, dict) else None
        if esperado_aprobacion is None or _canonico(registro) != _canonico(esperado_aprobacion):
            problemas.append(f"{etiqueta}: los metadatos de aprobación no corresponden a la geometría y su alcance declarado.")
        if isinstance(padre, dict) and padre.get("huella_contenido") != resultado.huella_contenido:
            problemas.append(f"{etiqueta}: la aprobación cambió el contenido geométrico de su padre.")
    return geometria, meta, resultado


def _problemas_fuente(carpeta: Path, meta: dict, geometria: Any, etiqueta: str) -> list[str]:
    problemas: list[str] = []
    fuente = meta.get("fuente")
    if not isinstance(fuente, dict) or fuente.get("archivo") != ARCHIVO_FUENTE or not isinstance(fuente.get("sha256"), str):
        return [f"{etiqueta}: el registro de la fuente importada falta o es inválido."]
    contenido = _leer_archivo(carpeta, ARCHIVO_FUENTE, problemas, etiqueta)
    if contenido is None:
        return problemas  # ausente, ilegible o enlazada
    if _sha256(contenido) != fuente["sha256"]:
        return [f"{etiqueta}: fuente importada alterada; su SHA256 no coincide con los metadatos."]
    original = _parsear(contenido, ARCHIVO_FUENTE, problemas, etiqueta)
    if original is None:
        return problemas
    if _canonico(original) is None or _canonico(original) != _canonico(geometria):
        return [f"{etiqueta}: la fuente importada no corresponde a {ARCHIVO_GEOMETRIA}."]
    return []


def _comprobar(caso_dir: Path, caso: str, version_id: str) -> tuple[ComprobacionGeometria, Any, Any, Any]:
    _carpeta_version(caso_dir, version_id)  # identificador o carpeta inválidos: solicitud rechazada
    comp = ComprobacionGeometria(caso=caso, version_id=version_id)
    expediente = _comprobar_expediente(caso_dir, caso)
    comp.expediente_sha256 = expediente.sha256
    comp.originales_verificados = expediente.originales
    comp.problemas.extend(expediente.problemas)

    geometria, meta, resultado = _comprobar_una(caso_dir, caso, version_id, comp.problemas, expediente)
    comp.cadena.append(version_id)
    if resultado is not None:
        comp.validacion = _resumen_validacion(resultado)
        comp.huella_contenido = resultado.huella_contenido
    if isinstance(meta, dict):
        comp.sha256_geometria = meta.get("sha256_geometria")

    # Cadena de padres: cada eslabón se comprueba completo y el vínculo por SHA256.
    actual = meta
    while isinstance(actual, dict) and actual.get("padre") is not None:
        padre = actual["padre"]
        pid = padre.get("id") if isinstance(padre, dict) else None
        if not isinstance(pid, str) or pid in comp.cadena:
            comp.problemas.append("Vínculo con la versión padre inválido o circular.")
            break
        _, pmeta, _ = _comprobar_una(caso_dir, caso, pid, comp.problemas, expediente)
        comp.cadena.append(pid)
        if not isinstance(pmeta, dict):
            break
        if pmeta.get("sha256_geometria") != padre.get("sha256_geometria"):
            comp.problemas.append(f"Versión padre {pid}: no coincide con el SHA256 registrado por su hija.")
        if pmeta.get("huella_contenido") != padre.get("huella_contenido"):
            comp.problemas.append(f"Versión padre {pid}: no coincide con la huella del contenido registrada por su hija.")
        if actual.get("datos_sinteticos") is not pmeta.get("datos_sinteticos"):
            comp.problemas.append(f"Versión padre {pid}: la marca sintética difiere de su hija.")
        actual = pmeta
    return comp, geometria, meta, resultado


def comprobar_version(raiz: Path, caso: str, version_id: str) -> ComprobacionGeometria:
    """Comprueba una versión, su cadena de padres, el expediente y sus originales. No escribe nada."""
    return _comprobar(carpeta_caso(raiz, caso), caso, version_id)[0]


def consultar_version(raiz: Path, caso: str, version_id: str) -> ConsultaGeometria:
    """Devuelve geometría y metadatos guardados junto con su comprobación (copias independientes)."""
    caso_dir = carpeta_caso(raiz, caso)
    comp, geometria, meta, _ = _comprobar(caso_dir, caso, version_id)
    return ConsultaGeometria(
        caso, version_id, caso_dir / CARPETA_GEOMETRIAS / version_id, copy.deepcopy(geometria), copy.deepcopy(meta), comp
    )


def _exigir(comp: ComprobacionGeometria, accion: str) -> None:
    if not comp.correcta:
        raise ErrorEvidencia(f"{accion}: la versión, el expediente o sus originales no superan la comprobación.", comp.problemas)


# -- escritura ---------------------------------------------------------------

def _guardar(
    caso_dir: Path, caso: str, geometria: dict, resultado, expediente: _Expediente, operacion: str,
    extra_meta: dict[str, Any], extra_archivos: dict[str, bytes],
) -> ResultadoGeometria:
    identificador = uuid4().hex
    bytes_geo = _json_bytes(geometria)
    meta = {
        "tipo": TIPO_REGISTRO,
        "version_registro": VERSION_REGISTRO,
        "id": identificador,
        "caso": caso,
        "operacion": operacion,
        "creado_utc": datetime.now(timezone.utc).isoformat(),
        "sha256_geometria": _sha256(bytes_geo),
        "huella_contenido": resultado.huella_contenido,
        "contrato_geometria": {"contrato": c.CONTRATO_GEOMETRIA, "version_contrato": geometria.get("version_contrato") if isinstance(geometria, dict) else None},
        "expediente_sha256": expediente.sha256,
        "originales_verificados": expediente.originales,
        "alcance": copy.deepcopy(expediente.alcance),
        "procedencia": copy.deepcopy(geometria["procedencia"]),
        "datos_sinteticos": resultado.datos_sinteticos,
        "validacion": _resumen_validacion(resultado),
        "estado_revision_geometria": geometria["revision"]["estado"],
        "identidad_revisor": IDENTIDAD_REVISOR,
        "aviso": AVISO,
        **extra_meta,
    }
    archivos = {ARCHIVO_GEOMETRIA: bytes_geo, ARCHIVO_METADATOS: _json_bytes(meta), **extra_archivos}
    destino = _publicar(caso_dir, CARPETA_GEOMETRIAS, identificador, archivos)
    comp = _comprobar(caso_dir, caso, identificador)[0]  # comprobación posterior a la publicación
    return ResultadoGeometria(caso, identificador, destino, comp, meta)


def _validar_entrada(geometria: Any, caso: str, accion: str):
    resultado = validar_geometria(geometria)
    if not resultado.consistente:
        raise ErrorEvidencia(f"{accion}: geometría inconsistente; no se guarda.", [str(e) for e in resultado.errores])
    if geometria["id"] != caso:
        raise ErrorEvidencia(f"{accion}.", [f"La geometría pertenece al caso '{geometria['id']}', no a '{caso}'."])
    return resultado


def _expediente_vigente(caso_dir: Path, caso: str, accion: str) -> _Expediente:
    expediente = _comprobar_expediente(caso_dir, caso)
    if expediente.problemas:
        raise ErrorEvidencia(f"{accion}: el expediente o sus originales no superan la comprobación.", expediente.problemas)
    return expediente


# -- operaciones -------------------------------------------------------------

def importar_geometria(raiz: Path, caso: str, entrada: Path) -> ResultadoGeometria:
    """Registra una geometría consistente (admite faltantes declarados) como versión raíz.

    Rechaza geometrías con estado 'aprobado' o aprobación no nula: la aprobación solo
    se registra con `aprobar_geometria`. Conserva los bytes exactos de la fuente.
    """
    accion = "Importación rechazada"
    caso_dir = carpeta_caso(raiz, caso)
    entrada = Path(entrada)
    try:
        fuente = entrada.read_bytes()
    except OSError as exc:
        raise ErrorGestion(f"No se pudo leer la entrada {entrada.name}: {exc}") from exc
    geometria = json_desde_bytes(fuente, entrada.name)  # mismos bytes que se conservan
    resultado = _validar_entrada(geometria, caso, accion)
    revision = geometria["revision"]
    if revision["estado"] == "aprobado" or revision["aprobacion"] is not None:
        raise ErrorEvidencia(accion + ".", [
            "La geometría de entrada declara una aprobación. Una aprobación importada no autoriza "
            "automáticamente: importe la geometría en borrador y registre la aprobación con la "
            "operación explícita aprobar_geometria. Los campos no se borran ni se reescriben."
        ])
    expediente = _expediente_vigente(caso_dir, caso, accion)
    return _guardar(
        caso_dir, caso, geometria, resultado, expediente, "importacion",
        {"padre": None, "fuente": {"nombre": entrada.name, "archivo": ARCHIVO_FUENTE, "sha256": _sha256(fuente)}},
        {ARCHIVO_FUENTE: fuente},
    )


def revisar_geometria(
    raiz: Path, caso: str, padre_id: str, geometria_propuesta: Any, *,
    motivo: str, fecha: str, revisor_declarado: str,
) -> ResultadoGeometria:
    """Guarda la geometría completa propuesta como versión hija de `padre_id`.

    La propuesta debe estar en 'borrador' y sin aprobación: nunca hereda la
    aprobación del padre. El padre no cambia; varias hijas del mismo padre son ramas.
    """
    accion = "Revisión rechazada"
    motivo, revisor_declarado, fecha = _texto(motivo, "motivo"), _texto(revisor_declarado, "revisor_declarado"), _fecha(fecha)
    caso_dir = carpeta_caso(raiz, caso)
    comp_padre, _, meta_padre, resultado_padre = _comprobar(caso_dir, caso, padre_id)
    _exigir(comp_padre, accion)
    propuesta = copy.deepcopy(geometria_propuesta)
    resultado = _validar_entrada(propuesta, caso, accion)
    revision = propuesta["revision"]
    if revision["estado"] != "borrador" or revision["aprobacion"] is not None:
        raise ErrorEvidencia(accion + ".", [
            "La geometría propuesta debe tener revision.estado 'borrador' y aprobacion null; "
            "una revisión no hereda ni declara aprobaciones."
        ])
    if resultado.datos_sinteticos != resultado_padre.datos_sinteticos:
        raise ErrorEvidencia(accion + ".", [
            "La procedencia sintética de la propuesta no coincide con la del padre; no se convierten "
            "datos sintéticos en reales ni al revés."
        ])
    expediente = _expediente_vigente(caso_dir, caso, accion)
    return _guardar(
        caso_dir, caso, propuesta, resultado, expediente, "revision",
        {
            "padre": {"id": padre_id, "sha256_geometria": meta_padre["sha256_geometria"],
                      "huella_contenido": meta_padre["huella_contenido"]},
            "revision": {"motivo": motivo, "fecha": fecha, "revisor_declarado": revisor_declarado,
                         "identidad_revisor": IDENTIDAD_REVISOR},
        },
        {},
    )


def migrar_geometria_superficies(
    raiz: Path, caso: str, padre_id: str, *, huella_esperada: str,
    motivo: str, fecha: str, revisor_declarado: str,
) -> ResultadoGeometria:
    """Crea hija v0.2 borrador de una v0.1 comprobada; conserva padre y huellas."""
    from .geometria_superficies import migrar_a_superficies
    consulta = consultar_version(raiz, caso, padre_id)
    _exigir(consulta.comprobacion, "Migración rechazada")
    if consulta.comprobacion.huella_contenido != huella_esperada:
        raise ErrorEvidencia("Migración rechazada.", ["La huella esperada no corresponde a la versión abierta."])
    propuesta = migrar_a_superficies(consulta.geometria)
    return revisar_geometria(raiz, caso, padre_id, propuesta,
                            motivo=motivo, fecha=fecha, revisor_declarado=revisor_declarado)


def aprobar_geometria(
    raiz: Path, caso: str, version_id: str, *, huella_esperada: str, revisor_declarado: str,
    fecha: str, motivo: str, alcance_revision: str,
) -> ResultadoGeometria:
    """Registra una aprobación explícita como versión hija de `version_id`.

    Exige geometría consistente y sin faltantes, expediente y originales vigentes y
    que `huella_esperada` coincida con la huella actual del contenido. El registro de
    aprobación se construye con esa huella y se vuelve a validar antes de guardar.
    """
    accion = "Aprobación rechazada"
    revisor_declarado = _texto(revisor_declarado, "revisor_declarado")
    motivo, alcance_revision, fecha = _texto(motivo, "motivo"), _texto(alcance_revision, "alcance_revision"), _fecha(fecha)
    if not isinstance(huella_esperada, str) or not re.fullmatch(r"[0-9a-f]{64}", huella_esperada):
        raise ErrorGestion("'huella_esperada' debe ser un SHA256 hexadecimal en minúsculas.")
    caso_dir = carpeta_caso(raiz, caso)
    comp, geometria, meta, resultado = _comprobar(caso_dir, caso, version_id)
    _exigir(comp, accion)
    if resultado.faltantes:
        raise ErrorEvidencia(accion + ".", [
            f"La geometría tiene {len(resultado.faltantes)} faltante(s); solo se aprueba geometría completa."
        ])
    if huella_esperada != resultado.huella_contenido:
        raise ErrorEvidencia(accion + ".", [
            "La huella esperada no coincide con la huella actual del contenido; revise la versión que pretende aprobar."
        ])
    if geometria["revision"]["estado"] == "aprobado":
        raise ErrorEvidencia(accion + ".", ["La versión ya contiene una aprobación; no se registra otra sobre ella."])

    aprobada = copy.deepcopy(geometria)
    aprobada["revision"] = {
        "estado": "aprobado",
        "aprobacion": {
            "declarada_por": revisor_declarado,
            "fecha": fecha,
            "huella_contenido": resultado.huella_contenido,
            "alcance": alcance_revision,
            "observaciones": motivo,
        },
    }
    nuevo = validar_geometria(aprobada)
    if not nuevo.consistente or not _aprobacion_geometrica_vigente(nuevo) or nuevo.huella_contenido != huella_esperada:
        raise ErrorEvidencia(accion + ".", ["La geometría aprobada no supera la validación final."]
                             + [str(e) for e in nuevo.errores] + list(nuevo.bloqueos))
    expediente = _expediente_vigente(caso_dir, caso, accion)
    return _guardar(
        caso_dir, caso, aprobada, nuevo, expediente, "aprobacion",
        {
            "padre": {"id": version_id, "sha256_geometria": meta["sha256_geometria"],
                      "huella_contenido": meta["huella_contenido"]},
            "aprobacion": {"huella_contenido": nuevo.huella_contenido, "huella_esperada": huella_esperada,
                           "revisor_declarado": revisor_declarado, "fecha": fecha, "motivo": motivo,
                           "alcance_revision": alcance_revision, "identidad_revisor": IDENTIDAD_REVISOR,
                           "certifica_seguridad_estructural": False, "aprueba_artefactos_derivados": False},
        },
        {},
    )
