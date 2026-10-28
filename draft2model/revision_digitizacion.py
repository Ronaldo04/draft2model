"""Servicio persistente y versionado de digitización calibrada local en borrador.

Vincula originales comprobados por bytes, geometría 0.3 vigente y el núcleo puro
`draft2model.digitizacion_calibrada`. Nunca acepta coordenadas métricas desde el
navegador o IA, no fabrica referencias documentales, no modifica geometría, no
crea superficies/barras y nunca aprueba ingeniería ni habilita ETABS.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import math
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any
from uuid import uuid4

from PIL import Image

from . import contratos as c
from . import digitizacion_calibrada as dc
from . import gestion_extraccion as g
from . import gestion_geometria as gg
from .validacion_geometria import validar_geometria

CONTRATO = "draft2model.revision_digitizacion"
VERSION = "0.1.0"
CARPETA = "digitizaciones"
MAX_JSON_BYTES = 4 * 1024 * 1024

CLAVES_METRICAS_PROHIBIDAS = frozenset({
    "puntos_resueltos",
    "coordenadas",
    "coordenadas_m",
    "xy",
    "xy_m",
    "xyz",
    "x",
    "y",
    "z",
    "metros",
})

AVISO_BORRADOR = (
    "Resultado en BORRADOR no normativo. Tres anclas con residuo cero solo ajustan "
    "exactamente seis parámetros afines y NO constituyen verificación independiente. "
    "Las anclas son propuestas de correspondencia sin aprobación humana; los puntos "
    "calculados no se incorporan al modelo ni habilitan ETABS."
)


class ErrorRevisionDigitizacion(ValueError):
    """Rechazo seguro de validación, vigencia o cálculo en el servicio de digitización."""

    def __init__(self, codigo: str, mensaje: str, **detalles: Any) -> None:
        super().__init__(mensaje)
        self.codigo = codigo
        self.detalles = detalles


def _exigir(condicion: bool, codigo: str, mensaje: str, **detalles: Any) -> None:
    if not condicion:
        raise ErrorRevisionDigitizacion(codigo, mensaje, **detalles)


def _bytes(valor: Any) -> bytes:
    return (
        json.dumps(valor, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _sha(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def _huella(valor: Any) -> str:
    return _sha(
        json.dumps(valor, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")).encode("utf-8")
    )


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp_utc_valido(valor: Any) -> str:
    _exigir(isinstance(valor, str) and 10 <= len(valor) <= 64, "registro_alterado", "Marca temporal UTC inválida.")
    try:
        dt = datetime.fromisoformat(valor)
    except ValueError as exc:
        raise ErrorRevisionDigitizacion("registro_alterado", "Marca temporal ISO-8601 inválida.") from exc
    _exigir(dt.tzinfo is not None, "registro_alterado", "La marca temporal requiere zona explícita.")
    return valor


def _hex64(valor: Any, ruta: str) -> str:
    _exigir(
        isinstance(valor, str) and re.fullmatch(r"[0-9a-f]{64}", valor) is not None,
        "huella_invalida",
        f"{ruta}: se requiere huella SHA-256 hexadecimal en minúsculas.",
    )
    return valor


def _uuid(valor: Any, ruta: str = "id") -> str:
    _exigir(
        isinstance(valor, str) and re.fullmatch(r"[0-9a-f]{32}", valor) is not None,
        "identificador_version_invalido",
        f"{ruta}: se requiere identificador hexadecimal de 32 caracteres.",
    )
    return valor


def _id_texto(valor: Any, ruta: str) -> str:
    _exigir(
        isinstance(valor, str)
        and ".." not in valor
        and "/" not in valor
        and "\\" not in valor
        and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", valor) is not None,
        "identificador_invalido",
        f"{ruta}: identificador inválido o con separadores de ruta no permitidos.",
    )
    return valor


def _numero(valor: Any, ruta: str, *, positivo: bool = False) -> float:
    es_num = type(valor) in (int, float)
    if not es_num:
        _exigir(False, "numero_invalido", f"{ruta}: se requiere número finito representable.")
    try:
        conv = float(valor)
    except (OverflowError, ValueError):
        conv = math.nan
    _exigir(
        math.isfinite(conv) and (not isinstance(valor, int) or conv == valor) and (not positivo or conv > 0),
        "numero_invalido",
        f"{ruta}: número fuera de rango o no admisible.",
    )
    return conv


def _sin_enlace(path: Path, *, falta: bool = False) -> Path:
    path = Path(path)
    if falta and not os.path.lexists(path):
        if path.parent.resolve() != path.parent:
            raise ErrorRevisionDigitizacion("enlace_no_permitido", "Ruta contenedora enlazada no permitida.")
        return path
    try:
        info = path.lstat()
    except OSError as exc:
        raise ErrorRevisionDigitizacion("artefacto_ausente", "Artefacto requerido ausente o inaccesible.") from exc
    reparse = bool(getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
    if path.resolve() != path or stat.S_ISLNK(info.st_mode) or reparse:
        raise ErrorRevisionDigitizacion("enlace_no_permitido", "Archivo o directorio enlazado no permitido.")
    return path


def _leer_json_seguro(path: Path, etiqueta: str) -> tuple[bytes, Any]:
    limpio = _sin_enlace(path)
    _exigir(limpio.is_file(), "artefacto_ausente", f"No existe {etiqueta}.")
    tam = limpio.stat().st_size
    _exigir(0 < tam <= MAX_JSON_BYTES, "tamano_invalido", f"Tamaño inválido para {etiqueta}.")
    raw = limpio.read_bytes()
    try:
        datos = g.json_desde_bytes(raw, etiqueta)
    except ValueError as exc:
        raise ErrorRevisionDigitizacion("json_invalido", f"JSON inválido en {etiqueta}.") from exc
    return raw, datos


def _codigo_actual() -> dict[str, str]:
    archivos = (
        Path(__file__).resolve(),
        Path(__file__).with_name("digitizacion_calibrada.py").resolve(),
        Path(__file__).with_name("revision_superposicion.py").resolve(),
    )
    return {ruta.name: _sha(ruta.read_bytes()) for ruta in archivos}


CODIGO_CARGADO = _codigo_actual()


def _exigir_codigo_vigente() -> dict[str, str]:
    actual = _codigo_actual()
    _exigir(
        actual == CODIGO_CARGADO,
        "codigo_modificado_en_sesion",
        "El código de digitización cambió durante la sesión; reinicia el proceso antes de continuar.",
    )
    return actual


def _rechazar_claves_metricas(obj: Any, ruta: str = "$") -> None:
    """Impide que navegador o IA inyecten coordenadas métricas físicas."""
    if isinstance(obj, dict):
        prohibidas = sorted(set(obj) & CLAVES_METRICAS_PROHIBIDAS)
        _exigir(
            not prohibidas,
            "coordenadas_metricas_no_admitidas",
            f"{ruta}: no se aceptan coordenadas métricas enviadas por el navegador o IA ({', '.join(prohibidas)}).",
            claves=prohibidas,
        )
        for clave, valor in obj.items():
            _rechazar_claves_metricas(valor, f"{ruta}.{clave}")
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            _rechazar_claves_metricas(item, f"{ruta}[{idx}]")


def _campos_exactos(obj: Any, obligatorios: set[str], opcionales: set[str], ruta: str) -> dict[str, Any]:
    _exigir(isinstance(obj, dict), "contrato_solicitud_invalido", f"{ruta}: se esperaba un objeto JSON.")
    presentes = set(obj)
    faltan = sorted(obligatorios - presentes)
    sobran = sorted(presentes - (obligatorios | opcionales))
    _exigir(
        not faltan and not sobran,
        "contrato_solicitud_invalido",
        f"{ruta}: campos inválidos (faltan={faltan}, no_admitidos={sobran}).",
    )
    return obj


def _rango_2d_no_colineal(puntos_2d: list[list[float]]) -> bool:
    if len(puntos_2d) < 3:
        return False
    n = len(puntos_2d)
    centro = [math.fsum(p[k] for p in puntos_2d) / n for k in (0, 1)]
    delta = [[p[k] - centro[k] for k in (0, 1)] for p in puntos_2d]
    a = math.fsum(p[0] ** 2 for p in delta)
    b = math.fsum(p[0] * p[1] for p in delta)
    d = math.fsum(p[1] ** 2 for p in delta)
    mayor, menor = dc._espectro(a, b, d)
    escala = max(mayor, 1e-30)
    return menor > 1e-18 * escala


def _derivar_pendientes_y_resumen_preparada(
    ctx_geo: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Deriva de forma pura `pendientes` y `resumen` para la etapa `preparada`."""
    catalogo_pub = ctx_geo["catalogo_publico"]
    utilizables = [r for r in catalogo_pub if r["utilizable_en_fuente"]]
    pendientes: list[dict[str, Any]] = []
    if not ctx_geo["suficientes_referencias"]:
        pendientes.append({
            "codigo": "referencias_coplanares_insuficientes",
            "detalle": ctx_geo["motivo_insuficiencia"],
            "mensaje": (
                "El registro geométrico vigente carece de al menos tres referencias coplanares no colineales "
                "utilizables en este plano; no se fabrican referencias para forzar el cálculo."
            ),
        })
    sin_doc = [r["id"] for r in utilizables if not r["tiene_referencia_documental"]]
    if sin_doc:
        pendientes.append({
            "codigo": "carencia_vinculo_documental_puntos",
            "puntos": sin_doc,
            "mensaje": (
                "La geometría no contiene referencias documentales hacia el dibujo para estos puntos; "
                "solo disponen de descriptor geométrico numérico y la exactitud documental NO está acreditada."
            ),
        })
    pendientes.append({
        "codigo": "correspondencia_en_borrador",
        "mensaje": "Preparación en borrador: no aprueba geometría ni ingeniería ni habilita ETABS.",
    })
    exactitud_doc = bool(utilizables) and all(r["ubicacion_en_dibujo_acreditada"] is True for r in utilizables)
    resumen = {
        "etapa": "preparada",
        "estado_revision": "borrador",
        "calculo_ejecutado": False,
        "calculo_posible": False,
        "referencias_suficientes_para_ajuste": bool(ctx_geo["suficientes_referencias"]),
        "referencias_coplanares_utilizables": len(utilizables),
        "referencias_con_vinculo_documental": sum(1 for r in utilizables if r["tiene_referencia_documental"]),
        "carencia_vinculo_documental": bool(sin_doc) or not any(r["evidencia_fuente_pagina"] for r in utilizables),
        "exactitud_verificada_en_controles": False,
        "exactitud_documental_acreditada": exactitud_doc,
        "datos_sinteticos": bool(ctx_geo["datos_sinteticos"]),
        "aprueba_ingenieria": False,
        "disponible_para_modelado": False,
        "ejecuta_etabs": False,
        "integra_al_modelo": False,
    }
    return pendientes, resumen


def _derivar_pendientes_y_resumen_pendiente_referencias(
    ctx_geo: dict[str, Any],
    propuesta: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Deriva de forma pura `pendientes` y `resumen` para `pendiente_referencias`."""
    pendientes = [
        {
            "codigo": "referencias_coplanares_insuficientes",
            "detalle": ctx_geo["motivo_insuficiencia"],
            "mensaje": (
                "La geometría 0.3 vigente carece de referencias coplanares no colineales suficientes "
                "en el plano declarado; se conserva resultado con pendiente sin fabricar referencias."
            ),
        },
        {
            "codigo": "integracion_contornos_pendiente",
            "mensaje": "No se calculan ni incorporan puntos al modelo.",
        },
    ]
    resumen = {
        "etapa": "pendiente_referencias",
        "estado_revision": "borrador",
        "calculo_ejecutado": False,
        "calculo_posible": False,
        "referencias_suficientes_para_ajuste": False,
        "contraste_en_controles": False,
        "exactitud_verificada_en_controles": False,
        "controles_distribuidos": False,
        "num_anclas": len(propuesta["anclas"]),
        "num_controles": len(propuesta["controles"]),
        "num_puntos_borrador": 0,
        "puntos_extrapolados": 0,
        "puntos_incertidumbre_fuera_limite": 0,
        "residuo_ajuste_max_m": None,
        "error_control_max_m": None,
        "ajuste_tres_anclas_sin_verificacion": False,
        "tiene_referencias_documentales": False,
        "carencia_vinculo_documental": True,
        "exactitud_documental_acreditada": False,
        "datos_sinteticos": bool(ctx_geo["datos_sinteticos"]),
        "aprueba_ingenieria": False,
        "disponible_para_modelado": False,
        "ejecuta_etabs": False,
        "integra_al_modelo": False,
    }
    return pendientes, resumen


def _derivar_pendientes_y_resumen_calculada(
    ctx_geo: dict[str, Any],
    resultado: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Deriva de forma pura `pendientes` y `resumen` para la etapa `calculada`."""
    usados_ids = sorted({item["punto_resuelto"] for item in [*resultado["anclas"], *resultado["controles"]]})
    catalogo_int = ctx_geo["catalogo_interno"]
    sin_ref_doc = [pid for pid in usados_ids if not catalogo_int[pid]["tiene_referencia_documental"]]
    sin_ev_pagina = [pid for pid in usados_ids if not catalogo_int[pid]["evidencia_fuente_pagina"]]
    ubicacion_acreditada = bool(usados_ids) and all(
        catalogo_int[pid]["ubicacion_en_dibujo_acreditada"] is True for pid in usados_ids
    )
    extrapolados = [p["id"] for p in resultado["puntos"] if p["extrapolacion"]]
    fuera_incert = [p["id"] for p in resultado["puntos"] if not p["incertidumbre"]["dentro_limite"]]

    pendientes: list[dict[str, Any]] = []
    if sin_ref_doc:
        pendientes.append({
            "codigo": "carencia_vinculo_documental_puntos",
            "puntos": sin_ref_doc,
            "mensaje": (
                "Los puntos de referencia usados carecen de referencias documentales en la geometría/lectura; "
                "se usó únicamente descriptor numérico de geometría y su ubicación en el dibujo NO es verificable ni acreditada."
            ),
        })
    elif sin_ev_pagina:
        pendientes.append({
            "codigo": "ubicacion_en_dibujo_no_acreditada",
            "puntos": sin_ev_pagina,
            "mensaje": (
                "Las referencias documentales del vértice no acreditan su posición uv_local dentro del dibujo; "
                "la correspondencia queda como propuesta en borrador."
            ),
        })
    else:
        pendientes.append({
            "codigo": "correspondencia_uv_propuesta_sin_aprobacion",
            "puntos": usados_ids,
            "mensaje": (
                "Las ubicaciones normalizadas uv_local declaradas en anclas y controles son propuestas de "
                "correspondencia en borrador, no aprobación de ingeniería."
            ),
        })

    contraste_controles = bool(resultado["exactitud_verificada_en_controles"] and not sin_ref_doc)
    if len(resultado["anclas"]) == 3 and not contraste_controles:
        pendientes.append({
            "codigo": "ajuste_exacto_tres_anclas_sin_verificacion",
            "mensaje": (
                "Tres anclas con residuo nulo resuelven exactamente la afinidad de seis parámetros; "
                "NO constituyen verificación independiente."
            ),
        })
    elif not contraste_controles:
        pendientes.append({
            "codigo": "sin_contraste_independiente_en_controles",
            "mensaje": "No se dispone de al menos tres controles independientes verificados dentro de tolerancia.",
        })
    if extrapolados:
        pendientes.append({
            "codigo": "puntos_fuera_casco_anclas",
            "puntos": extrapolados,
            "mensaje": "Existen puntos propuestos en extrapolación fuera del casco convexo de las anclas.",
        })
    if fuera_incert:
        pendientes.append({
            "codigo": "incertidumbre_indicativa_excede_limite",
            "puntos": fuera_incert,
            "mensaje": "El indicador conservador de incertidumbre supera el límite declarado en al menos un punto.",
        })
    pendientes.append({
        "codigo": "integracion_contornos_pendiente",
        "mensaje": "Coordenadas calculadas en BORRADOR; no modifican geometría ni crean superficies o frames.",
    })

    resumen = {
        "etapa": "calculada",
        "estado_revision": "borrador",
        "calculo_ejecutado": True,
        "calculo_posible": True,
        "referencias_suficientes_para_ajuste": True,
        "contraste_en_controles": contraste_controles,
        "exactitud_verificada_en_controles": contraste_controles,
        "controles_distribuidos": bool(resultado["controles_distribuidos"]),
        "num_anclas": len(resultado["anclas"]),
        "num_controles": len(resultado["controles"]),
        "num_puntos_borrador": len(resultado["puntos"]),
        "puntos_extrapolados": len(extrapolados),
        "puntos_incertidumbre_fuera_limite": len(fuera_incert),
        "residuo_ajuste_max_m": resultado["residuo_ajuste_max_m"],
        "error_control_max_m": resultado["error_control_max_m"],
        "ajuste_tres_anclas_sin_verificacion": len(resultado["anclas"]) == 3 and not contraste_controles,
        "tiene_referencias_documentales": not sin_ref_doc,
        "carencia_vinculo_documental": bool(sin_ref_doc or sin_ev_pagina or not ubicacion_acreditada),
        "exactitud_documental_acreditada": ubicacion_acreditada,
        "datos_sinteticos": bool(ctx_geo["datos_sinteticos"]),
        "aprueba_ingenieria": False,
        "disponible_para_modelado": False,
        "ejecuta_etabs": False,
        "integra_al_modelo": False,
    }
    return pendientes, resumen


def _construir_registro_preparada(
    *,
    ident: str,
    creado_utc: str,
    caso: str,
    fp: str,
    origen_prop: dict[str, Any],
    ctx_geo: dict[str, Any],
    fuente_solicitud: dict[str, Any],
    fuente_vigente: dict[str, Any],
    evidencia_fuente: dict[str, Any],
    codigos: dict[str, str],
) -> dict[str, Any]:
    pendientes, resumen = _derivar_pendientes_y_resumen_preparada(ctx_geo)
    return {
        "contrato": CONTRATO,
        "version": VERSION,
        "id": ident,
        "etapa": "preparada",
        "caso": caso,
        "expediente_sha256": fp,
        "creado_utc": creado_utc,
        "datos_sinteticos": bool(ctx_geo["datos_sinteticos"]),
        "origen_propuesta": copy.deepcopy(origen_prop),
        "geometria_origen": copy.deepcopy(ctx_geo["geometria_origen"]),
        "fuente_solicitud": copy.deepcopy(fuente_solicitud),
        "fuente_vigente": copy.deepcopy(fuente_vigente),
        "evidencia_fuente": copy.deepcopy(evidencia_fuente),
        "plano": copy.deepcopy(ctx_geo["plano"]),
        "cotas_disponibles_eje": list(ctx_geo["cotas_disponibles_eje"]),
        "catalogo_referencias": copy.deepcopy(ctx_geo["catalogo_publico"]),
        "propuesta": None,
        "resultado": None,
        "pendientes": pendientes,
        "resumen": resumen,
        "hashes_entradas": {
            "expediente_sha256": fp,
            "original_sha256": fuente_vigente["sha256"],
            "preview_sha256": evidencia_fuente["preview_sha256"],
            "geometria_id": ctx_geo["geometria_origen"]["version_id"],
            "sha256_geometria": ctx_geo["geometria_origen"]["sha256_geometria"],
            "huella_geometria": ctx_geo["geometria_origen"]["huella_contenido"],
            "huella_catalogo_referencias": ctx_geo["huella_catalogo_referencias"],
            "huella_entrada_modulo": None,
            "preparacion_id": None,
            "huella_preparacion": None,
        },
        "hashes_codigo": copy.deepcopy(codigos),
        "revision": {"estado": "borrador", "aprobacion": None},
        "aprueba_ingenieria": False,
        "disponible_para_modelado": False,
        "ejecuta_etabs": False,
        "aviso": AVISO_BORRADOR,
    }


def _construir_registro_pendiente_referencias(
    *,
    ident: str,
    creado_utc: str,
    caso: str,
    fp: str,
    origen_prop: dict[str, Any],
    ctx_geo: dict[str, Any],
    fuente_solicitud: dict[str, Any],
    fuente_vigente: dict[str, Any],
    evidencia_fuente: dict[str, Any],
    propuesta: dict[str, Any],
    prep_id: str | None,
    huella_prep: str | None,
    codigos: dict[str, str],
) -> dict[str, Any]:
    pendientes, resumen = _derivar_pendientes_y_resumen_pendiente_referencias(ctx_geo, propuesta)
    return {
        "contrato": CONTRATO,
        "version": VERSION,
        "id": ident,
        "etapa": "pendiente_referencias",
        "caso": caso,
        "expediente_sha256": fp,
        "creado_utc": creado_utc,
        "datos_sinteticos": bool(ctx_geo["datos_sinteticos"]),
        "origen_propuesta": copy.deepcopy(origen_prop),
        "geometria_origen": copy.deepcopy(ctx_geo["geometria_origen"]),
        "fuente_solicitud": copy.deepcopy(fuente_solicitud),
        "fuente_vigente": copy.deepcopy(fuente_vigente),
        "evidencia_fuente": copy.deepcopy(evidencia_fuente),
        "plano": copy.deepcopy(ctx_geo["plano"]),
        "cotas_disponibles_eje": list(ctx_geo["cotas_disponibles_eje"]),
        "catalogo_referencias": copy.deepcopy(ctx_geo["catalogo_publico"]),
        "propuesta": copy.deepcopy(propuesta),
        "resultado": None,
        "pendientes": pendientes,
        "resumen": resumen,
        "hashes_entradas": {
            "expediente_sha256": fp,
            "original_sha256": fuente_vigente["sha256"],
            "preview_sha256": evidencia_fuente["preview_sha256"],
            "geometria_id": ctx_geo["geometria_origen"]["version_id"],
            "sha256_geometria": ctx_geo["geometria_origen"]["sha256_geometria"],
            "huella_geometria": ctx_geo["geometria_origen"]["huella_contenido"],
            "huella_catalogo_referencias": ctx_geo["huella_catalogo_referencias"],
            "huella_entrada_modulo": None,
            "preparacion_id": prep_id,
            "huella_preparacion": huella_prep,
        },
        "hashes_codigo": copy.deepcopy(codigos),
        "revision": {"estado": "borrador", "aprobacion": None},
        "aprueba_ingenieria": False,
        "disponible_para_modelado": False,
        "ejecuta_etabs": False,
        "aviso": AVISO_BORRADOR,
    }


def _construir_registro_calculada(
    *,
    ident: str,
    creado_utc: str,
    caso: str,
    fp: str,
    origen_prop: dict[str, Any],
    ctx_geo: dict[str, Any],
    fuente_solicitud: dict[str, Any],
    fuente_vigente: dict[str, Any],
    evidencia_fuente: dict[str, Any],
    propuesta: dict[str, Any],
    resultado: dict[str, Any],
    prep_id: str | None,
    huella_prep: str | None,
    codigos: dict[str, str],
) -> dict[str, Any]:
    pendientes, resumen = _derivar_pendientes_y_resumen_calculada(ctx_geo, resultado)
    return {
        "contrato": CONTRATO,
        "version": VERSION,
        "id": ident,
        "etapa": "calculada",
        "caso": caso,
        "expediente_sha256": fp,
        "creado_utc": creado_utc,
        "datos_sinteticos": bool(ctx_geo["datos_sinteticos"]),
        "origen_propuesta": copy.deepcopy(origen_prop),
        "geometria_origen": copy.deepcopy(ctx_geo["geometria_origen"]),
        "fuente_solicitud": copy.deepcopy(fuente_solicitud),
        "fuente_vigente": copy.deepcopy(fuente_vigente),
        "evidencia_fuente": copy.deepcopy(evidencia_fuente),
        "plano": copy.deepcopy(ctx_geo["plano"]),
        "cotas_disponibles_eje": list(ctx_geo["cotas_disponibles_eje"]),
        "catalogo_referencias": copy.deepcopy(ctx_geo["catalogo_publico"]),
        "propuesta": copy.deepcopy(propuesta),
        "resultado": copy.deepcopy(resultado),
        "sha256_resultado": _sha(_bytes(resultado)),
        "pendientes": pendientes,
        "resumen": resumen,
        "hashes_entradas": {
            "expediente_sha256": fp,
            "original_sha256": fuente_vigente["sha256"],
            "preview_sha256": evidencia_fuente["preview_sha256"],
            "geometria_id": ctx_geo["geometria_origen"]["version_id"],
            "sha256_geometria": ctx_geo["geometria_origen"]["sha256_geometria"],
            "huella_geometria": ctx_geo["geometria_origen"]["huella_contenido"],
            "huella_catalogo_referencias": ctx_geo["huella_catalogo_referencias"],
            "huella_entrada_modulo": resultado["huella_entrada"],
            "preparacion_id": prep_id,
            "huella_preparacion": huella_prep,
        },
        "hashes_codigo": copy.deepcopy(codigos),
        "revision": {"estado": "borrador", "aprobacion": None},
        "aprueba_ingenieria": False,
        "disponible_para_modelado": False,
        "ejecuta_etabs": False,
        "aviso": AVISO_BORRADOR,
    }


def _validar_invariantes_borrador(registro_sin_huella: dict[str, Any]) -> None:
    res = registro_sin_huella.get("resumen")
    cat = registro_sin_huella.get("catalogo_referencias")
    pends = registro_sin_huella.get("pendientes")
    _exigir(
        isinstance(res, dict)
        and isinstance(cat, list)
        and isinstance(pends, list)
        and len(pends) >= 1
        and registro_sin_huella.get("revision") == {"estado": "borrador", "aprobacion": None}
        and registro_sin_huella.get("aprueba_ingenieria") is False
        and registro_sin_huella.get("disponible_para_modelado") is False
        and registro_sin_huella.get("ejecuta_etabs") is False
        and res.get("estado_revision") == "borrador"
        and res.get("exactitud_documental_acreditada") is False
        and res.get("aprueba_ingenieria") is False
        and res.get("disponible_para_modelado") is False
        and res.get("ejecuta_etabs") is False
        and res.get("integra_al_modelo") is False
        and all(isinstance(item, dict) and item.get("ubicacion_en_dibujo_acreditada") is False for item in cat),
        "registro_alterado",
        "Invariantes de borrador, no aprobación o no acreditación documental vulnerados.",
    )


class ServicioDigitizacion:
    """Servicio local versionado para preparar, calcular, consultar y listar digitizaciones."""

    def __init__(self, app: Any) -> None:
        self.app = app

    def _raiz(self) -> Path:
        return _sin_enlace(Path(self.app.raiz).resolve())

    def _caso(self, caso: Any, fp: Any) -> tuple[Path, dict[str, Any]]:
        _exigir(
            isinstance(caso, str) and re.fullmatch(g.PATRON_CASO, caso) is not None,
            "caso_invalido",
            "Identificador de expediente inválido.",
        )
        fp_limpio = _hex64(fp, "expediente_sha256")
        raiz = self._raiz()
        candidato = raiz / caso
        if os.path.lexists(candidato):
            _sin_enlace(candidato)
        try:
            folder_raw, manifest, actual_fp = self.app.expediente(caso)
        except (ValueError, OSError) as exc:
            raise ErrorRevisionDigitizacion("expediente_invalido", "Expediente ausente, enlazado o inválido.") from exc
        folder = _sin_enlace(Path(folder_raw))
        _exigir(folder.parent == raiz, "expediente_fuera_raiz", "El expediente queda fuera de la raíz autorizada.")
        _sin_enlace(folder / "expediente.json")
        _exigir(
            actual_fp == fp_limpio,
            "expediente_cambiado",
            "El expediente cambió respecto de la huella declarada; vuelve a abrirlo.",
        )
        for entrada in manifest.get("archivos", []):
            _exigir(isinstance(entrada, dict) and isinstance(entrada.get("id"), str), "manifiesto_invalido", "Entrada de original inválida.")
            try:
                self.app._original(caso, entrada["id"])
            except (ValueError, OSError) as exc:
                raise ErrorRevisionDigitizacion(
                    "fuente_alterada",
                    f"El original '{entrada['id']}' fue alterado, enlazado o perdió vigencia.",
                ) from exc
        return folder, manifest

    def _base(self, folder: Path, *, crear: bool = False) -> Path:
        base = _sin_enlace(folder / CARPETA, falta=True)
        if os.path.lexists(base):
            _exigir(base.is_dir(), "directorio_invalido", "Ruta de digitizaciones inválida.")
        elif crear:
            base.mkdir()
        return base

    def _fuente_comprobada(
        self,
        caso: str,
        fp: str,
        folder: Path,
        manifest: dict[str, Any],
        fuente_req: Any,
        *,
        exigir_sha: bool,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        obligatorios = {"original_id", "pagina", "dibujo_id", "bbox_pagina"}
        if exigir_sha:
            obligatorios.add("sha256")
        opcionales = {"sha256", "revision_documental", "recorte"} - obligatorios
        fuente_obj = _campos_exactos(fuente_req, obligatorios, opcionales, "fuente")
        original_id = _id_texto(fuente_obj["original_id"], "fuente.original_id")
        dibujo_id = _id_texto(fuente_obj["dibujo_id"], "fuente.dibujo_id")
        pagina = fuente_obj["pagina"]
        _exigir(type(pagina) is int and pagina >= 1, "pagina_invalida", "fuente.pagina debe ser entero >= 1.")
        bbox_raw = fuente_obj["bbox_pagina"]
        _exigir(isinstance(bbox_raw, list) and len(bbox_raw) == 4, "bbox_invalido", "fuente.bbox_pagina requiere 4 números.")
        bbox = [_numero(v, f"fuente.bbox_pagina[{i}]") for i, v in enumerate(bbox_raw)]
        _exigir(
            0.0 <= bbox[0] < bbox[2] <= 1.0 and 0.0 <= bbox[1] < bbox[3] <= 1.0,
            "bbox_invalido",
            "fuente.bbox_pagina debe cumplir 0 <= x0 < x1 <= 1 y 0 <= y0 < y1 <= 1.",
        )

        entradas = [a for a in manifest["archivos"] if a.get("id") == original_id]
        _exigir(len(entradas) == 1, "original_ausente", "El original solicitado no pertenece al manifiesto del caso.")
        rel = entradas[0].get("archivo")
        _exigir(
            isinstance(rel, str) and not Path(rel).is_absolute() and ".." not in Path(rel).parts,
            "ruta_original_invalida",
            "Ruta de original inválida en el manifiesto.",
        )
        ruta_original = _sin_enlace(folder / rel)
        _exigir(ruta_original.is_relative_to(folder), "ruta_original_invalida", "Original fuera del expediente.")

        try:
            raw, suffix, fp_actual = self.app._original(caso, original_id)
        except (ValueError, OSError) as exc:
            raise ErrorRevisionDigitizacion("fuente_alterada", "No se pudo verificar los bytes del original.") from exc
        _exigir(fp_actual == fp, "expediente_cambiado", "El expediente cambió durante la verificación del original.")
        real_sha = _sha(raw)
        _exigir(real_sha == entradas[0].get("sha256"), "fuente_alterada", "La huella real del original no coincide con el manifiesto.")
        if "sha256" in fuente_obj:
            declarado_sha = _hex64(fuente_obj["sha256"], "fuente.sha256")
            _exigir(
                declarado_sha == real_sha,
                "sha256_original_no_coincide",
                "El SHA-256 enviado no coincide con los bytes reales del original.",
            )

        try:
            png_bytes = self.app.pagina(caso, original_id, pagina, fp)
            with Image.open(BytesIO(png_bytes)) as img:
                img.load()
                preview_px = [int(img.width), int(img.height)]
        except (ValueError, OSError, RuntimeError) as exc:
            raise ErrorRevisionDigitizacion("pagina_invalida", "La página solicitada no existe o no es procesable.") from exc
        _exigir(preview_px[0] > 0 and preview_px[1] > 0, "pagina_invalida", "Dimensiones de vista previa inválidas.")

        rev_id_usada = None
        dir_rev = _sin_enlace(folder / "revision_documental", falta=True)
        if "revision_documental" in fuente_obj and fuente_obj["revision_documental"] is not None:
            rev_id_usada = _uuid(fuente_obj["revision_documental"], "fuente.revision_documental")
            _, rev_data = _leer_json_seguro(_sin_enlace(dir_rev / rev_id_usada) / "revision.json", "revision.json")
            self._validar_entrada_revision_doc(rev_data, caso, fp, original_id, pagina)
        elif "revision_documental" not in fuente_obj and os.path.lexists(dir_rev) and dir_rev.is_dir():
            for sub in sorted(dir_rev.iterdir()):
                if re.fullmatch(r"[0-9a-f]{32}", sub.name) is None:
                    continue
                cand_json = _sin_enlace(sub) / "revision.json"
                if not cand_json.is_file():
                    continue
                _, rev_data = _leer_json_seguro(cand_json, "revision.json")
                if rev_data.get("caso") == caso and rev_data.get("expediente_sha256") == fp:
                    self._validar_entrada_revision_doc(rev_data, caso, fp, original_id, pagina)
                    rev_id_usada = sub.name

        rec_id_usado = None
        if "recorte" in fuente_obj and fuente_obj["recorte"] is not None:
            rec_id_usado = _uuid(fuente_obj["recorte"], "fuente.recorte")
            dir_rec = _sin_enlace(folder / "recortes")
            sub_rec = _sin_enlace(dir_rec / rec_id_usado)
            _, rec_data = _leer_json_seguro(sub_rec / "recorte.json", "recorte.json")
            img_rec = _sin_enlace(sub_rec / "recorte.png")
            _exigir(
                img_rec.is_file()
                and rec_data.get("caso") == caso
                and rec_data.get("expediente_sha256") == fp
                and rec_data.get("archivo_id") == original_id
                and rec_data.get("origen_sha256") == real_sha
                and rec_data.get("pagina") == pagina
                and [float(v) for v in (rec_data.get("bbox_normalizada") or [])] == bbox
                and _sha(img_rec.read_bytes()) == rec_data.get("imagen_sha256"),
                "recorte_inconsistente",
                "El recorte vinculado no corresponde al original, página, SHA-256 o bbox declarados.",
            )

        fuente_vigente = {
            "original_id": original_id,
            "sha256": real_sha,
            "pagina": pagina,
            "dibujo_id": dibujo_id,
            "bbox_pagina": bbox,
        }
        fuente_solicitud = {
            **copy.deepcopy(fuente_vigente),
            "revision_documental": rev_id_usada,
            **({"recorte": rec_id_usado} if rec_id_usado else {}),
        }
        evidencia_fuente = {
            "suffix": suffix,
            "preview_px": preview_px,
            "preview_sha256": _sha(png_bytes),
            "revision_documental_id": rev_id_usada,
            "recorte_id": rec_id_usado,
        }
        return fuente_vigente, fuente_solicitud, evidencia_fuente

    @staticmethod
    def _validar_entrada_revision_doc(
        rev_data: Any,
        caso: str,
        fp: str,
        original_id: str,
        pagina: int,
    ) -> None:
        _exigir(
            isinstance(rev_data, dict)
            and rev_data.get("caso") == caso
            and rev_data.get("expediente_sha256") == fp
            and isinstance(rev_data.get("documentos"), list),
            "revision_documental_invalida",
            "Revisión documental inválida o de otro estado del expediente.",
        )
        docs_match = [d for d in rev_data["documentos"] if isinstance(d, dict) and d.get("id") == original_id]
        _exigir(len(docs_match) == 1 and not docs_match[0].get("error"), "pagina_con_error_documental", "Original con error en revisión documental.")
        pags_match = [p for p in docs_match[0].get("paginas", []) if isinstance(p, dict) and p.get("numero") == pagina]
        _exigir(len(pags_match) == 1 and not pags_match[0].get("error"), "pagina_con_error_documental", "Página ausente o con error en revisión documental.")

    def _candidatos_conversion(
        self,
        folder: Path,
        caso: str,
        fp: str,
        sha_geometria: str,
    ) -> dict[str, dict[str, Any]] | None:
        dir_conv = _sin_enlace(folder / "conversiones_geometria", falta=True)
        if not os.path.lexists(dir_conv) or not dir_conv.is_dir():
            return None
        for sub in sorted(dir_conv.iterdir()):
            if re.fullmatch(r"[0-9a-f]{32}", sub.name) is None:
                continue
            sub_limpio = _sin_enlace(sub)
            traza_path = sub_limpio / "trazabilidad.json"
            exp_path = sub_limpio / "exportacion.json"
            if not traza_path.is_file() or not exp_path.is_file():
                continue
            _, traza = _leer_json_seguro(traza_path, "trazabilidad.json")
            if (
                traza.get("caso") == caso
                and traza.get("expediente_sha256") == fp
                and traza.get("geometria_sha256") == sha_geometria
            ):
                _, exportacion = _leer_json_seguro(exp_path, "exportacion.json")
                cands = exportacion.get("candidatos")
                if isinstance(cands, list):
                    return {item["id"]: item for item in cands if isinstance(item, dict) and isinstance(item.get("id"), str)}
        return None

    def _geometria_y_referencias(
        self,
        caso: str,
        fp: str,
        folder: Path,
        manifest: dict[str, Any],
        geo_id_raw: Any,
        huella_raw: Any,
        sha_raw: Any,
        plano_req: Any,
        fuente_vigente: dict[str, Any],
    ) -> dict[str, Any]:
        geo_id = _uuid(geo_id_raw, "geometria")
        huella_esp = _hex64(huella_raw, "huella_geometria")
        sha_esp = _hex64(sha_raw, "sha256_geometria")
        _sin_enlace(folder / gg.CARPETA_GEOMETRIAS / geo_id)
        try:
            actual = self.app.geometria(caso, geo_id)
        except (ValueError, OSError) as exc:
            raise ErrorRevisionDigitizacion("geometria_no_vigente", "Geometría ausente, enlazada o sin vigencia.") from exc
        _exigir(actual.get("expediente_sha256") == fp, "expediente_cambiado", "El expediente cambió al consultar la geometría.")
        _exigir(
            actual.get("huella") == huella_esp and actual.get("sha256_geometria") == sha_esp,
            "geometria_alterada",
            "La versión geométrica o su huella cambiaron respecto de la solicitud.",
        )
        datos = actual["datos"]
        _exigir(
            isinstance(datos, dict)
            and datos.get("contrato") == c.CONTRATO_GEOMETRIA
            and datos.get("version_contrato") == c.VERSION_GEOMETRIA_ABERTURAS
            and datos.get("id") == caso,
            "version_geometria_no_admitida",
            "Se requiere una versión vigente del contrato de geometría 0.3.0 del mismo expediente.",
        )
        vg = validar_geometria(datos)
        _exigir(
            vg.consistente and vg.huella_contenido == huella_esp and isinstance(vg.geometria_m, dict),
            "geometria_inconsistente",
            "La geometría 0.3.0 no supera la validación interna.",
        )

        plano_obj = _campos_exactos(
            plano_req,
            {"id", "ejes", "eje_constante", "valor_constante", "unidad_longitud"},
            set(),
            "plano",
        )
        plano_id = _id_texto(plano_obj["id"], "plano.id")
        ejes = plano_obj["ejes"]
        _exigir(
            isinstance(ejes, list)
            and ejes in (["x", "y"], ["x", "z"], ["y", "z"])
            and plano_obj["eje_constante"] in ({"x", "y", "z"} - set(ejes)),
            "plano_invalido",
            "plano debe declarar dos ejes cartesianos válidos y el tercer eje constante.",
        )
        unidad_plano = plano_obj["unidad_longitud"]
        _exigir(
            isinstance(unidad_plano, str) and unidad_plano in dc.DIVISORES,
            "unidad_invalida",
            "plano.unidad_longitud debe ser m, cm o mm.",
        )
        _exigir(
            unidad_plano == datos["unidad_longitud"],
            "unidad_distinta_de_geometria",
            "La unidad del plano debe coincidir exactamente con unidad_longitud de la geometría vigente; no se inventan ni mezclan unidades.",
        )
        valor_constante = _numero(plano_obj["valor_constante"], "plano.valor_constante")
        cota_m = valor_constante / dc.DIVISORES[unidad_plano]
        _exigir(valor_constante == 0 or cota_m != 0, "normalizacion_cota", "La cota del plano pierde precisión al normalizar a metros.")
        plano = {
            "id": plano_id,
            "ejes": list(ejes),
            "eje_constante": plano_obj["eje_constante"],
            "valor_constante": valor_constante,
            "unidad_longitud": unidad_plano,
        }

        eje_c = plano["eje_constante"]
        vertices_raw = datos.get("vertices", [])
        vertices_m_map = {v["id"]: v for v in vg.geometria_m.get("vertices", [])}
        todos_vertices = {v["id"]: v for v in vertices_raw}
        cotas_niveles = {
            float(n["cota"])
            for n in datos.get("niveles", [])
            if isinstance(n, dict) and type(n.get("cota")) in (int, float) and math.isfinite(float(n["cota"]))
        }
        coplanares_raw = [v for v in vertices_raw if float(v[eje_c]) == valor_constante]
        existe_cota = bool(coplanares_raw) or (eje_c == "z" and valor_constante in cotas_niveles)
        _exigir(
            existe_cota,
            "cota_plano_inexistente_en_geometria",
            "La cota constante declarada no existe en los vértices ni niveles de la geometría vigente; no se inventan cotas.",
        )

        ids_originales = {a["id"] for a in manifest["archivos"] if isinstance(a, dict) and isinstance(a.get("id"), str)}
        candidatos_conv = self._candidatos_conversion(folder, caso, fp, sha_esp)

        catalogo: list[dict[str, Any]] = []
        catalogo_map: dict[str, dict[str, Any]] = {}
        puntos_resueltos: dict[str, dict[str, Any]] = {}

        for v in coplanares_raw:
            vid = v["id"]
            vm = vertices_m_map[vid]
            coords_plano = [float(v[ejes[0]]), float(v[ejes[1]])]
            coords_m_plano = [float(vm[ejes[0]]), float(vm[ejes[1]])]
            proc = v.get("procedencia") if isinstance(v.get("procedencia"), dict) else {}
            lamina = proc.get("lamina")
            contradice_fuente = isinstance(lamina, str) and lamina in ids_originales and lamina != fuente_vigente["original_id"]

            raw_refs = proc.get("referencias")
            tiene_ref_doc = False
            evidencia_en_pagina = False
            refs_doc: list[str] = []
            if isinstance(raw_refs, list) and len(raw_refs) > 0:
                refs_limpias: list[str] = []
                for idx, ref in enumerate(raw_refs):
                    refs_limpias.append(_id_texto(ref, f"vertice.{vid}.referencias[{idx}]"))
                _exigir(len(set(refs_limpias)) == len(refs_limpias), "referencia_duplicada", f"Referencias duplicadas en vértice {vid}.")
                tiene_ref_doc = True
                refs_doc = refs_limpias
                if candidatos_conv is not None:
                    en_pagina_todos = True
                    for cid in refs_limpias:
                        cand = candidatos_conv.get(cid)
                        if not cand or not isinstance(cand.get("evidencia"), list):
                            en_pagina_todos = False
                            continue
                        evs = cand["evidencia"]
                        if evs and all(
                            (ev.get("archivo_id"), ev.get("pagina")) != (fuente_vigente["original_id"], fuente_vigente["pagina"])
                            for ev in evs
                            if isinstance(ev, dict)
                        ):
                            contradice_fuente = True
                            en_pagina_todos = False
                    evidencia_en_pagina = en_pagina_todos and not contradice_fuente
                refs_modulo = list(refs_doc)
                naturaleza_ref = "conversion_lecturas_comprobada" if evidencia_en_pagina else "referencia_documental_geometria"
            else:
                refs_modulo = [f"descriptor_geometrico:{geo_id}"]
                naturaleza_ref = "descriptor_geometrico_sin_vinculo_documental"

            huella_res = _huella({
                "caso": caso,
                "geometria_id": geo_id,
                "sha256_geometria": sha_esp,
                "huella_geometria": huella_esp,
                "vertice_id": vid,
                "coordenadas": coords_plano,
                "unidad_longitud": unidad_plano,
                "plano": plano,
                "procedencia": proc,
            })

            ficha = {
                "id": vid,
                "coordenadas": coords_plano,
                "unidad_longitud": unidad_plano,
                "coordenadas_m": {"x": float(vm["x"]), "y": float(vm["y"]), "z": float(vm["z"])},
                "huella_resolucion": huella_res,
                "tiene_referencia_documental": tiene_ref_doc,
                "referencias_documentales": refs_doc,
                "referencias_modulo": refs_modulo,
                "naturaleza_referencia": naturaleza_ref,
                "evidencia_fuente_pagina": evidencia_en_pagina,
                "ubicacion_en_dibujo_acreditada": False,
                "contradice_fuente": contradice_fuente,
            }
            catalogo.append(ficha)
            catalogo_map[vid] = ficha
            if not contradice_fuente:
                puntos_resueltos[vid] = {
                    "coordenadas": coords_plano,
                    "unidad_longitud": unidad_plano,
                    "plano": copy.deepcopy(plano),
                    "fuente": copy.deepcopy(fuente_vigente),
                    "huella_resolucion": huella_res,
                    "referencias": list(refs_modulo),
                }

        utilizables = [item for item in catalogo if not item["contradice_fuente"]]
        coords_2d_m = [[item["coordenadas_m"][ejes[0]], item["coordenadas_m"][ejes[1]]] for item in utilizables]
        if len(utilizables) < 3:
            suficientes = False
            motivo_insuficiencia = "menos_de_tres_referencias_coplanares"
        elif not _rango_2d_no_colineal(coords_2d_m):
            suficientes = False
            motivo_insuficiencia = "referencias_coplanares_colineales"
        else:
            suficientes = True
            motivo_insuficiencia = None

        planos_disponibles = sorted({float(v[eje_c]) for v in vertices_raw})
        catalogo_publico = [
            {
                "id": item["id"],
                "coordenadas": item["coordenadas"],
                "unidad_longitud": item["unidad_longitud"],
                "coordenadas_m": item["coordenadas_m"],
                "huella_resolucion": item["huella_resolucion"],
                "tiene_referencia_documental": item["tiene_referencia_documental"],
                "referencias_documentales": item["referencias_documentales"],
                "naturaleza_referencia": item["naturaleza_referencia"],
                "evidencia_fuente_pagina": item["evidencia_fuente_pagina"],
                "ubicacion_en_dibujo_acreditada": False,
                "utilizable_en_fuente": not item["contradice_fuente"],
            }
            for item in catalogo
        ]

        return {
            "geometria_origen": {
                "version_id": geo_id,
                "version_contrato": datos["version_contrato"],
                "huella_contenido": huella_esp,
                "sha256_geometria": sha_esp,
                "unidad_longitud": datos["unidad_longitud"],
                "estado_revision": datos["revision"]["estado"],
                "procedencia": copy.deepcopy(datos["procedencia"]),
            },
            "datos_sinteticos": bool(vg.datos_sinteticos),
            "plano": plano,
            "cotas_disponibles_eje": planos_disponibles,
            "todos_vertices": todos_vertices,
            "catalogo_interno": catalogo_map,
            "catalogo_publico": catalogo_publico,
            "huella_catalogo_referencias": _huella(catalogo_publico),
            "puntos_resueltos": puntos_resueltos,
            "suficientes_referencias": suficientes,
            "motivo_insuficiencia": motivo_insuficiencia,
        }

    @staticmethod
    def _normalizar_origen_propuesta(valor: Any) -> dict[str, Any]:
        if valor is None:
            return {"modo": "interfaz_revision_ingenieria", "referencia_origen": None, "editada_en_pantalla": False}
        obj = _campos_exactos(valor, {"modo"}, {"referencia_origen", "editada_en_pantalla"}, "origen_propuesta")
        modo = obj["modo"]
        _exigir(
            modo in ("interfaz_revision_ingenieria", "propuesta_estructurada_revisada", "propuesta_automatica_codex"),
            "origen_propuesta_invalido",
            "Modo de origen_propuesta no admitido.",
        )
        ref = obj.get("referencia_origen")
        if ref is not None:
            _id_texto(ref, "origen_propuesta.referencia_origen")
        editada = obj.get("editada_en_pantalla", False)
        _exigir(type(editada) is bool, "origen_propuesta_invalido", "editada_en_pantalla debe ser booleano.")
        return {"modo": modo, "referencia_origen": ref, "editada_en_pantalla": editada}

    def preparar(self, body: Any) -> dict[str, Any]:
        _rechazar_claves_metricas(body)
        solicitud = _campos_exactos(
            body,
            {"caso", "expediente_sha256", "geometria", "huella_geometria", "sha256_geometria", "fuente", "plano"},
            {"origen_propuesta"},
            "preparar",
        )
        with self.app.lock:
            codigos = _exigir_codigo_vigente()
            caso = solicitud["caso"]
            fp = solicitud["expediente_sha256"]
            folder, manifest = self._caso(caso, fp)
            fuente_vigente, fuente_solicitud, evidencia_fuente = self._fuente_comprobada(
                caso, fp, folder, manifest, solicitud["fuente"], exigir_sha=False
            )
            ctx_geo = self._geometria_y_referencias(
                caso,
                fp,
                folder,
                manifest,
                solicitud["geometria"],
                solicitud["huella_geometria"],
                solicitud["sha256_geometria"],
                solicitud["plano"],
                fuente_vigente,
            )
            origen_prop = self._normalizar_origen_propuesta(solicitud.get("origen_propuesta"))
            ident = uuid4().hex
            creado = _ahora()
            registro_base = _construir_registro_preparada(
                ident=ident,
                creado_utc=creado,
                caso=caso,
                fp=fp,
                origen_prop=origen_prop,
                ctx_geo=ctx_geo,
                fuente_solicitud=fuente_solicitud,
                fuente_vigente=fuente_vigente,
                evidencia_fuente=evidencia_fuente,
                codigos=codigos,
            )
            _validar_invariantes_borrador(registro_base)
            return self._guardar_atomico(caso, fp, folder, ident, registro_base)

    def calcular(self, body: Any) -> dict[str, Any]:
        _rechazar_claves_metricas(body)
        solicitud = _campos_exactos(
            body,
            {
                "caso",
                "expediente_sha256",
                "geometria",
                "huella_geometria",
                "sha256_geometria",
                "propuesta_id",
                "fuente",
                "plano",
                "limites",
                "anclas",
                "controles",
                "puntos",
            },
            {"preparacion_id", "huella_preparacion", "origen_propuesta"},
            "calcular",
        )
        _exigir(
            ("preparacion_id" in solicitud) == ("huella_preparacion" in solicitud),
            "preparacion_incompleta",
            "preparacion_id y huella_preparacion deben enviarse juntos.",
        )

        with self.app.lock:
            codigos = _exigir_codigo_vigente()
            caso = solicitud["caso"]
            fp = solicitud["expediente_sha256"]
            folder, manifest = self._caso(caso, fp)
            fuente_vigente, fuente_solicitud, evidencia_fuente = self._fuente_comprobada(
                caso, fp, folder, manifest, solicitud["fuente"], exigir_sha=True
            )
            ctx_geo = self._geometria_y_referencias(
                caso,
                fp,
                folder,
                manifest,
                solicitud["geometria"],
                solicitud["huella_geometria"],
                solicitud["sha256_geometria"],
                solicitud["plano"],
                fuente_vigente,
            )

            prep_id = None
            huella_prep = None
            if "preparacion_id" in solicitud:
                prep_id = _uuid(solicitud["preparacion_id"], "preparacion_id")
                huella_prep = _hex64(solicitud["huella_preparacion"], "huella_preparacion")
                prep = self.consultar(caso, fp, prep_id)
                _exigir(
                    prep["etapa"] == "preparada"
                    and prep["huella_version"] == huella_prep
                    and prep["geometria_origen"]["version_id"] == ctx_geo["geometria_origen"]["version_id"]
                    and prep["geometria_origen"]["sha256_geometria"] == ctx_geo["geometria_origen"]["sha256_geometria"]
                    and prep["fuente_vigente"] == fuente_vigente
                    and prep["plano"] == ctx_geo["plano"],
                    "preparacion_desactualizada",
                    "La preparación vinculada no corresponde a la fuente, plano o geometría actuales.",
                )

            origen_prop = self._normalizar_origen_propuesta(solicitud.get("origen_propuesta"))
            plano = ctx_geo["plano"]
            fuente_item_base = {k: solicitud["fuente"][k] for k in dc.FUENTE}
            propuesta = self._construir_propuesta_normalizada(
                propuesta_id_raw=solicitud["propuesta_id"],
                fuente_base=fuente_item_base,
                plano=plano,
                limites_raw=solicitud["limites"],
                anclas_raw=solicitud["anclas"],
                controles_raw=solicitud["controles"],
                puntos_raw=solicitud["puntos"],
                ctx_geo=ctx_geo,
            )

            ident = uuid4().hex
            creado = _ahora()

            if not ctx_geo["suficientes_referencias"]:
                registro_insuf = _construir_registro_pendiente_referencias(
                    ident=ident,
                    creado_utc=creado,
                    caso=caso,
                    fp=fp,
                    origen_prop=origen_prop,
                    ctx_geo=ctx_geo,
                    fuente_solicitud=fuente_solicitud,
                    fuente_vigente=fuente_vigente,
                    evidencia_fuente=evidencia_fuente,
                    propuesta=propuesta,
                    prep_id=prep_id,
                    huella_prep=huella_prep,
                    codigos=codigos,
                )
                _validar_invariantes_borrador(registro_insuf)
                return self._guardar_atomico(caso, fp, folder, ident, registro_insuf)

            try:
                resultado = dc.calibrar_digitizacion(
                    propuesta,
                    fuente_vigente=fuente_vigente,
                    puntos_resueltos=ctx_geo["puntos_resueltos"],
                )
            except dc.ErrorDigitizacion as exc:
                raise ErrorRevisionDigitizacion(exc.codigo, str(exc), **exc.detalles) from exc

            registro_base = _construir_registro_calculada(
                ident=ident,
                creado_utc=creado,
                caso=caso,
                fp=fp,
                origen_prop=origen_prop,
                ctx_geo=ctx_geo,
                fuente_solicitud=fuente_solicitud,
                fuente_vigente=fuente_vigente,
                evidencia_fuente=evidencia_fuente,
                propuesta=propuesta,
                resultado=resultado,
                prep_id=prep_id,
                huella_prep=huella_prep,
                codigos=codigos,
            )
            _validar_invariantes_borrador(registro_base)
            return self._guardar_atomico(caso, fp, folder, ident, registro_base)

    def _construir_propuesta_normalizada(
        self,
        *,
        propuesta_id_raw: Any,
        fuente_base: dict[str, Any],
        plano: dict[str, Any],
        limites_raw: Any,
        anclas_raw: Any,
        controles_raw: Any,
        puntos_raw: Any,
        ctx_geo: dict[str, Any],
    ) -> dict[str, Any]:
        propuesta_id = _id_texto(propuesta_id_raw, "propuesta_id")
        anclas_norm = self._normalizar_referencias_solicitud(
            anclas_raw, "anclas", fuente_base, plano["id"], ctx_geo
        )
        controles_norm = self._normalizar_referencias_solicitud(
            controles_raw, "controles", fuente_base, plano["id"], ctx_geo
        )
        puntos_norm = self._normalizar_puntos_solicitud(
            puntos_raw, fuente_base, plano["id"]
        )
        _campos_exactos(limites_raw, set(dc.LIMITES), set(), "limites")
        limites_norm = {k: _numero(v, f"limites.{k}", positivo=True) for k, v in limites_raw.items()}
        return {
            "contrato": dc.CONTRATO,
            "version": dc.VERSION,
            "id": propuesta_id,
            "fuente": copy.deepcopy(fuente_base),
            "plano": copy.deepcopy(plano),
            "limites": limites_norm,
            "anclas": anclas_norm,
            "controles": controles_norm,
            "puntos": puntos_norm,
        }

    def _reconstruir_propuesta_guardada(
        self,
        prop_guardada: Any,
        fuente_vigente: dict[str, Any],
        ctx_geo: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            obj = _campos_exactos(
                prop_guardada,
                {"contrato", "version", "id", "fuente", "plano", "limites", "anclas", "controles", "puntos"},
                set(),
                "registro.propuesta",
            )
            fuente_base = {k: fuente_vigente[k] for k in dc.FUENTE}
            _exigir(
                obj["contrato"] == dc.CONTRATO
                and obj["version"] == dc.VERSION
                and obj["fuente"] == fuente_base
                and obj["plano"] == ctx_geo["plano"],
                "registro_alterado",
                "La propuesta almacenada en el registro fue alterada o no coincide con fuente/plano vigentes.",
            )
            propuesta_esp = self._construir_propuesta_normalizada(
                propuesta_id_raw=obj["id"],
                fuente_base=fuente_base,
                plano=ctx_geo["plano"],
                limites_raw=obj["limites"],
                anclas_raw=obj["anclas"],
                controles_raw=obj["controles"],
                puntos_raw=obj["puntos"],
                ctx_geo=ctx_geo,
            )
        except ErrorRevisionDigitizacion as exc:
            raise ErrorRevisionDigitizacion(
                "registro_alterado",
                "Propuesta almacenada alterada o inconsistente con el contexto vigente.",
            ) from exc
        _exigir(
            _bytes(propuesta_esp) == _bytes(prop_guardada),
            "registro_alterado",
            "La propuesta almacenada no es canónica o fue alterada en disco.",
        )
        return propuesta_esp

    @staticmethod
    def _normalizar_referencias_solicitud(
        items: Any,
        nombre: str,
        fuente_base: dict[str, Any],
        plano_id_base: str,
        ctx_geo: dict[str, Any],
    ) -> list[dict[str, Any]]:
        _exigir(isinstance(items, list) and len(items) <= 1000, "contrato_solicitud_invalido", f"{nombre}: se esperaba lista (<= 1000).")
        salida = []
        for idx, item in enumerate(items):
            obj = _campos_exactos(item, {"id", "punto_resuelto", "uv_local"}, {"fuente", "plano_id"}, f"{nombre}[{idx}]")
            ident = _id_texto(obj["id"], f"{nombre}[{idx}].id")
            punto_id = _id_texto(obj["punto_resuelto"], f"{nombre}[{idx}].punto_resuelto")
            if "plano_id" in obj and obj["plano_id"] != plano_id_base:
                raise ErrorRevisionDigitizacion(
                    "referencia_otro_plano",
                    f"{nombre}[{idx}] declara plano_id distinto al plano activo.",
                )
            if "fuente" in obj and obj["fuente"] != fuente_base:
                raise ErrorRevisionDigitizacion(
                    "fuente_mezclada",
                    f"{nombre}[{idx}] declara una fuente distinta a la fuente activa.",
                )
            if punto_id not in ctx_geo["catalogo_interno"]:
                if punto_id in ctx_geo["todos_vertices"]:
                    raise ErrorRevisionDigitizacion(
                        "referencia_otro_plano",
                        f"El vértice '{punto_id}' pertenece a otro plano o cota de la geometría.",
                    )
                raise ErrorRevisionDigitizacion(
                    "punto_no_resuelto",
                    f"El identificador '{punto_id}' no existe en la geometría 0.3.0 vigente.",
                )
            if ctx_geo["catalogo_interno"][punto_id]["contradice_fuente"]:
                raise ErrorRevisionDigitizacion(
                    "referencia_otra_fuente",
                    f"El vértice '{punto_id}' está vinculado documentalmente a otro original o página.",
                )
            salida.append({
                "id": ident,
                "punto_resuelto": punto_id,
                "uv_local": obj["uv_local"],
                "fuente": copy.deepcopy(obj.get("fuente", fuente_base)),
                "plano_id": obj.get("plano_id", plano_id_base),
            })
        return salida

    @staticmethod
    def _normalizar_puntos_solicitud(
        items: Any,
        fuente_base: dict[str, Any],
        plano_id_base: str,
    ) -> list[dict[str, Any]]:
        _exigir(isinstance(items, list) and 1 <= len(items) <= 10000, "contrato_solicitud_invalido", "puntos: lista entre 1 y 10000.")
        salida = []
        for idx, item in enumerate(items):
            obj = _campos_exactos(item, {"id", "uv_local", "relacionados"}, {"fuente", "plano_id"}, f"puntos[{idx}]")
            ident = _id_texto(obj["id"], f"puntos[{idx}].id")
            if "plano_id" in obj and obj["plano_id"] != plano_id_base:
                raise ErrorRevisionDigitizacion("referencia_otro_plano", f"puntos[{idx}] declara otro plano_id.")
            if "fuente" in obj and obj["fuente"] != fuente_base:
                raise ErrorRevisionDigitizacion("fuente_mezclada", f"puntos[{idx}] declara otra fuente.")
            salida.append({
                "id": ident,
                "uv_local": obj["uv_local"],
                "fuente": copy.deepcopy(obj.get("fuente", fuente_base)),
                "plano_id": obj.get("plano_id", plano_id_base),
                "relacionados": obj["relacionados"],
            })
        return salida

    def _guardar_atomico(
        self,
        caso: str,
        fp: str,
        folder: Path,
        ident: str,
        registro_sin_huella: dict[str, Any],
    ) -> dict[str, Any]:
        huella_ver = _huella(registro_sin_huella)
        registro = {**registro_sin_huella, "huella_version": huella_ver}
        raw_reg = _bytes(registro)
        _exigir(len(raw_reg) <= MAX_JSON_BYTES, "tamano_invalido", "El registro de digitización excede el tamaño máximo.")
        meta = {
            "contrato": CONTRATO,
            "version": VERSION,
            "id": ident,
            "caso": caso,
            "etapa": registro["etapa"],
            "sha256_registro": _sha(raw_reg),
            "huella_version": huella_ver,
            "creado_utc": registro["creado_utc"],
        }
        raw_meta = _bytes(meta)
        base = self._base(folder, crear=True)
        with tempfile.TemporaryDirectory(prefix=".dig-", dir=base) as temporal:
            etapa_dir = _sin_enlace(Path(temporal).resolve())
            _exigir(etapa_dir.parent == base, "temporal_fuera_caso", "Directorio temporal fuera del expediente.")
            paquete = etapa_dir / "paquete"
            paquete.mkdir()
            for nombre, contenido in (("registro.json", raw_reg), ("version.json", raw_meta)):
                with (paquete / nombre).open("xb") as stream:
                    stream.write(contenido)
            self._cargar_y_comprobar(caso, fp, ident, ruta=paquete)
            destino = base / ident
            _exigir(not os.path.lexists(destino), "colision_version", "El identificador de versión ya existe.")
            paquete.rename(destino)
        return self.consultar(caso, fp, ident)

    def _cargar_y_comprobar(
        self,
        caso: str,
        fp: str,
        ident: str,
        *,
        ruta: Path | None = None,
    ) -> dict[str, Any]:
        folder, manifest = self._caso(caso, fp)
        target = _sin_enlace(ruta if ruta is not None else self._base(folder) / _uuid(ident))
        _exigir(
            target.is_dir() and sorted(p.name for p in target.iterdir()) == ["registro.json", "version.json"],
            "registro_alterado",
            "Registro de digitización ausente o con archivos inesperados.",
        )
        raw_meta, meta = _leer_json_seguro(target / "version.json", "version.json")
        raw_reg, reg = _leer_json_seguro(target / "registro.json", "registro.json")
        _exigir(
            isinstance(meta, dict)
            and set(meta) == {"contrato", "version", "id", "caso", "etapa", "sha256_registro", "huella_version", "creado_utc"}
            and meta["contrato"] == CONTRATO
            and meta["version"] == VERSION
            and meta["id"] == ident
            and meta["caso"] == caso
            and meta["sha256_registro"] == _sha(raw_reg),
            "registro_alterado",
            "Metadatos de versión de digitización alterados o inconsistentes.",
        )
        _exigir(isinstance(reg, dict) and "huella_version" in reg, "registro_alterado", "Contenido de registro inválido.")
        sin_huella = {k: v for k, v in reg.items() if k != "huella_version"}
        _exigir(
            reg["huella_version"] == meta["huella_version"] == _huella(sin_huella)
            and reg.get("contrato") == CONTRATO
            and reg.get("version") == VERSION
            and reg.get("id") == ident
            and reg.get("caso") == caso
            and reg.get("expediente_sha256") == fp
            and reg.get("etapa") == meta["etapa"]
            and reg.get("creado_utc") == meta["creado_utc"]
            and reg.get("revision") == {"estado": "borrador", "aprobacion": None}
            and reg.get("aprueba_ingenieria") is False
            and reg.get("disponible_para_modelado") is False
            and reg.get("ejecuta_etabs") is False,
            "registro_alterado",
            "El registro de digitización fue alterado o pertenece a otro estado del expediente.",
        )
        creado_utc = _timestamp_utc_valido(reg["creado_utc"])
        codigos_actuales = _codigo_actual()
        _exigir(
            reg.get("hashes_codigo") == codigos_actuales,
            "codigo_cambiado",
            "El código del servicio o del núcleo calibrado cambió respecto del registro conservado.",
        )

        origen_raw = reg.get("origen_propuesta")
        _exigir(isinstance(origen_raw, dict), "registro_alterado", "origen_propuesta inválido en registro persistido.")
        try:
            origen_prop = self._normalizar_origen_propuesta(origen_raw)
        except ErrorRevisionDigitizacion as exc:
            raise ErrorRevisionDigitizacion("registro_alterado", "origen_propuesta alterado en registro persistido.") from exc
        _exigir(
            _bytes(origen_prop) == _bytes(origen_raw),
            "registro_alterado",
            "origen_propuesta no coincide con la representación canónica esperada.",
        )

        fuente_vigente, fuente_solicitud_esp, evidencia_fuente = self._fuente_comprobada(
            caso, fp, folder, manifest, reg.get("fuente_solicitud"), exigir_sha=True
        )
        hashes_ent = reg.get("hashes_entradas")
        _exigir(isinstance(hashes_ent, dict), "registro_alterado", "hashes_entradas inválido en registro persistido.")
        _exigir(
            fuente_vigente == reg.get("fuente_vigente")
            and hashes_ent.get("original_sha256") == fuente_vigente["sha256"]
            and hashes_ent.get("preview_sha256") == evidencia_fuente["preview_sha256"],
            "fuente_alterada",
            "El original o su vista previa cambiaron respecto del registro conservado.",
        )

        geo_orig = reg.get("geometria_origen") or {}
        ctx_geo = self._geometria_y_referencias(
            caso,
            fp,
            folder,
            manifest,
            geo_orig.get("version_id"),
            geo_orig.get("huella_contenido"),
            geo_orig.get("sha256_geometria"),
            reg.get("plano"),
            fuente_vigente,
        )
        _exigir(
            ctx_geo["datos_sinteticos"] == reg.get("datos_sinteticos")
            and ctx_geo["huella_catalogo_referencias"] == hashes_ent.get("huella_catalogo_referencias"),
            "geometria_alterada",
            "La geometría o su catálogo de referencias cambiaron respecto del registro conservado.",
        )

        etapa = reg["etapa"]
        prep_id_raw = hashes_ent.get("preparacion_id")
        huella_prep_raw = hashes_ent.get("huella_preparacion")
        _exigir(
            (prep_id_raw is None) == (huella_prep_raw is None),
            "registro_alterado",
            "Vínculo de preparación incompleto o alterado en hashes_entradas.",
        )
        prep_id: str | None = None
        huella_prep: str | None = None
        if prep_id_raw is not None:
            _exigir(etapa != "preparada", "registro_alterado", "Una etapa preparada no admite preparacion_id.")
            try:
                prep_id = _uuid(prep_id_raw, "hashes_entradas.preparacion_id")
                huella_prep = _hex64(huella_prep_raw, "hashes_entradas.huella_preparacion")
            except ErrorRevisionDigitizacion as exc:
                raise ErrorRevisionDigitizacion("registro_alterado", "Identificador o huella de preparación alterados.") from exc
            _exigir(prep_id != ident, "registro_alterado", "Autorreferencia inválida en preparacion_id.")
            prep = self._cargar_y_comprobar(caso, fp, prep_id)
            _exigir(
                prep["etapa"] == "preparada"
                and prep["huella_version"] == huella_prep
                and prep["geometria_origen"] == ctx_geo["geometria_origen"]
                and prep["fuente_vigente"] == fuente_vigente
                and prep["plano"] == ctx_geo["plano"],
                "registro_alterado",
                "La preparación vinculada perdió vigencia o no coincide con el registro.",
            )

        if etapa == "preparada":
            _exigir(
                reg.get("propuesta") is None and reg.get("resultado") is None,
                "registro_alterado",
                "Un registro preparado no puede contener propuesta ni resultado calculado.",
            )
            esperado = _construir_registro_preparada(
                ident=ident,
                creado_utc=creado_utc,
                caso=caso,
                fp=fp,
                origen_prop=origen_prop,
                ctx_geo=ctx_geo,
                fuente_solicitud=fuente_solicitud_esp,
                fuente_vigente=fuente_vigente,
                evidencia_fuente=evidencia_fuente,
                codigos=codigos_actuales,
            )
        elif etapa == "pendiente_referencias":
            _exigir(
                not ctx_geo["suficientes_referencias"] and reg.get("resultado") is None,
                "registro_alterado",
                "Etapa pendiente_referencias incoherente con la disponibilidad de referencias o resultado no nulo.",
            )
            propuesta_esp = self._reconstruir_propuesta_guardada(reg.get("propuesta"), fuente_vigente, ctx_geo)
            esperado = _construir_registro_pendiente_referencias(
                ident=ident,
                creado_utc=creado_utc,
                caso=caso,
                fp=fp,
                origen_prop=origen_prop,
                ctx_geo=ctx_geo,
                fuente_solicitud=fuente_solicitud_esp,
                fuente_vigente=fuente_vigente,
                evidencia_fuente=evidencia_fuente,
                propuesta=propuesta_esp,
                prep_id=prep_id,
                huella_prep=huella_prep,
                codigos=codigos_actuales,
            )
        elif etapa == "calculada":
            _exigir(
                ctx_geo["suficientes_referencias"],
                "registro_alterado",
                "Etapa calculada incoherente con plano sin referencias coplanares suficientes.",
            )
            resultado_guardado = reg.get("resultado")
            _exigir(
                isinstance(resultado_guardado, dict)
                and resultado_guardado.get("revision") == {"estado": "borrador", "aprobacion": None}
                and resultado_guardado.get("disponible_para_modelado") is False,
                "registro_alterado",
                "Resultado calibrado inválido o con banderas de aprobación prohibidas.",
            )
            propuesta_esp = self._reconstruir_propuesta_guardada(reg.get("propuesta"), fuente_vigente, ctx_geo)
            try:
                recalculado = dc.calibrar_digitizacion(
                    propuesta_esp,
                    fuente_vigente=fuente_vigente,
                    puntos_resueltos=ctx_geo["puntos_resueltos"],
                )
            except dc.ErrorDigitizacion as exc:
                raise ErrorRevisionDigitizacion("calculo_no_reproducible", str(exc), **exc.detalles) from exc
            _exigir(
                _bytes(recalculado) == _bytes(resultado_guardado)
                and reg.get("sha256_resultado") == _sha(_bytes(recalculado))
                and hashes_ent.get("huella_entrada_modulo") == recalculado["huella_entrada"],
                "calculo_alterado",
                "El resultado almacenado no reproduce el cálculo calibrado sobre las fuentes vigentes.",
            )
            esperado = _construir_registro_calculada(
                ident=ident,
                creado_utc=creado_utc,
                caso=caso,
                fp=fp,
                origen_prop=origen_prop,
                ctx_geo=ctx_geo,
                fuente_solicitud=fuente_solicitud_esp,
                fuente_vigente=fuente_vigente,
                evidencia_fuente=evidencia_fuente,
                propuesta=propuesta_esp,
                resultado=recalculado,
                prep_id=prep_id,
                huella_prep=huella_prep,
                codigos=codigos_actuales,
            )
        else:
            raise ErrorRevisionDigitizacion("etapa_invalida", "Etapa de registro desconocida.")

        _validar_invariantes_borrador(esperado)
        _exigir(
            _bytes(sin_huella) == _bytes(esperado),
            "registro_alterado",
            "El resumen, pendientes, catálogo o campos derivados del registro fueron alterados respecto de las fuentes y el cálculo vigentes.",
        )

        final_meta, _ = _leer_json_seguro(target / "version.json", "version.json")
        final_reg, _ = _leer_json_seguro(target / "registro.json", "registro.json")
        _exigir(
            final_meta == raw_meta and final_reg == raw_reg,
            "registro_alterado",
            "El registro cambió en disco durante la comprobación.",
        )
        return {
            **copy.deepcopy(esperado),
            "huella_version": reg["huella_version"],
            "sha256_registro": meta["sha256_registro"],
            "vigente": True,
        }

    def consultar(
        self,
        caso: str,
        fp: str | None = None,
        id: str | None = None,
        *,
        expediente_sha256: str | None = None,
        version: str | None = None,
        registro: str | None = None,
    ) -> dict[str, Any]:
        fp_eff = fp if fp is not None else expediente_sha256
        id_eff = id if id is not None else (version if version is not None else registro)
        with self.app.lock:
            return self._cargar_y_comprobar(caso, fp_eff, id_eff)

    def listar(
        self,
        caso: str,
        fp: str | None = None,
        *,
        expediente_sha256: str | None = None,
    ) -> dict[str, Any]:
        fp_eff = fp if fp is not None else expediente_sha256
        with self.app.lock:
            folder, _ = self._caso(caso, fp_eff)
            base = self._base(folder, crear=False)
            filas: list[dict[str, Any]] = []
            if os.path.lexists(base) and base.is_dir():
                for path in sorted(base.iterdir()):
                    if re.fullmatch(r"[0-9a-f]{32}", path.name) is None:
                        continue
                    try:
                        item = self._cargar_y_comprobar(caso, fp_eff, path.name)
                        res = item["resumen"]
                        filas.append({
                            "id": path.name,
                            "vigente": True,
                            "etapa": item["etapa"],
                            "creado_utc": item["creado_utc"],
                            "huella_version": item["huella_version"],
                            "geometria": item["geometria_origen"]["version_id"],
                            "original_id": item["fuente_vigente"]["original_id"],
                            "pagina": item["fuente_vigente"]["pagina"],
                            "dibujo_id": item["fuente_vigente"]["dibujo_id"],
                            "plano_id": item["plano"]["id"],
                            "datos_sinteticos": item["datos_sinteticos"],
                            "calculo_posible": res["calculo_posible"],
                            "contraste_en_controles": res.get("contraste_en_controles", False),
                            "exactitud_documental_acreditada": res["exactitud_documental_acreditada"],
                            "carencia_vinculo_documental": res["carencia_vinculo_documental"],
                            "pendientes": len(item["pendientes"]),
                        })
                    except (ErrorRevisionDigitizacion, ValueError) as exc:
                        codigo = getattr(exc, "codigo", "registro_no_vigente")
                        filas.append({"id": path.name, "vigente": False, "problemas": [codigo]})
            self._caso(caso, fp_eff)
            return {
                "caso": caso,
                "expediente_sha256": fp_eff,
                "registros": filas,
                "versiones": filas,
                "seleccion_automatica": False,
            }
