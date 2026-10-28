"""Políticas automáticas explícitas de nodos derivados y subdivisión de barras (puro, sin I/O ni ETABS).

Reutiliza `draft2model.malla_preparacion.preparar_malla` sobre una geometría 0.3.0 consistente y una
configuración 0.4.0/0.5.0 compatible para:
1. Enumerar todos los registros `nodos_derivados` y `subdivision_frames` exigidos por la malla conforme.
2. Evaluar un contrato cerrado de reglas explícitas declaradas por el ingeniero (`plano_z`, `borde_entre_puntos`,
   `entidades`, `nodos`, políticas explícitas de resto y autorización de subdivisión de barras).
3. Exponer vista previa estructurada (`previsualizar_politicas_malla`) con pendientes concretos, conflictos y errores,
   sin inventar apoyos en `z=0`, sin asumir diafragmas por nivel ni heredar condiciones de extremo sin regla.
4. Aplicar decisiones explícitas y completas sobre una copia en borrador (`aplicar_politicas_malla`), sin mutar las
   entradas, sin maquillar otros campos incompletos y sin conservar ni fabricar aprobaciones.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from fractions import Fraction
from typing import Any

from . import malla_preparacion as mp
from .validacion_geometria import validar_geometria

CONTRATO_REGLAS = "draft2model.reglas_politica_malla"
CONTRATO_PROPUESTA = "draft2model.propuesta_politicas_malla"
VERSION_CONTRATO = "0.1.0"

CONTRATO_CONFIGURACION = "draft2model.modelo_estructural"
VERSIONES_CONFIGURACION = ("0.4.0", "0.5.0")
VERSION_GEOMETRIA = "0.3.0"
UNIDADES_CONFIGURACION = {"longitud": "m", "fuerza": "kN", "tiempo": "s", "temperatura": "C"}

_RE_HEX32 = re.compile(r"^[0-9a-f]{32}$")
_RE_HEX64 = re.compile(r"^[0-9a-f]{64}$")

_CLAVES_REGLAS_RAIZ = frozenset({
    "contrato",
    "version_contrato",
    "unidad_longitud",
    "reglas_restricciones",
    "resto_restricciones",
    "reglas_diafragma",
    "resto_diafragma",
    "subdivision_frames",
})
_CLAVES_REGLA_RESTRICCION = frozenset({"id", "selector", "restricciones", "fuente", "motivo"})
_CLAVES_RESTO_RESTRICCION = frozenset({"restricciones", "fuente", "motivo"})
_CLAVES_REGLA_DIAFRAGMA = frozenset({"id", "selector", "accion", "diafragma", "motivo_sin_diafragma", "fuente"})
_CLAVES_RESTO_DIAFRAGMA = frozenset({"accion", "diafragma", "motivo_sin_diafragma", "fuente"})
_CLAVES_SUBDIV_TODAS = frozenset({"modo", "fuente", "motivo"})
_CLAVES_SUBDIV_POR_FRAME = frozenset({"modo", "reglas_frames"})
_CLAVES_REGLA_FRAME = frozenset({"id", "frames", "accion", "fuente", "motivo"})


class ErrorPoliticaMalla(ValueError):
    """Política de malla incompleta, contradictoria o incompatible; no se aplica parcialmente."""

    def __init__(self, mensaje: str, *, propuesta: dict[str, Any] | None = None) -> None:
        super().__init__(mensaje)
        self.propuesta = copy.deepcopy(propuesta) if propuesta is not None else None


def _canon(valor: Any) -> bytes:
    return json.dumps(valor, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(valor: Any) -> str:
    return hashlib.sha256(_canon(valor)).hexdigest()


def _es_texto_no_vacio(valor: Any) -> bool:
    return isinstance(valor, str) and bool(valor.strip())


def _es_numero_finito(valor: Any) -> bool:
    return type(valor) in (int, float) and math.isfinite(valor)


def _es_restriccion_6(valor: Any) -> bool:
    return isinstance(valor, list) and len(valor) == 6 and all(type(x) is bool for x in valor)


def _norm_float(valor: int | float) -> float:
    f = float(valor)
    return 0.0 if f == 0.0 else f


def plantilla_reglas_vacia() -> dict[str, Any]:
    """Devuelve un documento de reglas explícitas vacío en contrato cerrado 0.1.0."""
    return {
        "contrato": CONTRATO_REGLAS,
        "version_contrato": VERSION_CONTRATO,
        "unidad_longitud": "m",
        "reglas_restricciones": [],
        "resto_restricciones": None,
        "reglas_diafragma": [],
        "resto_diafragma": None,
        "subdivision_frames": None,
    }


def _err(errores: list[dict[str, str]], ruta: str, mensaje: str) -> None:
    errores.append({"ruta": ruta, "mensaje": mensaje})


def _validar_lista_ids(valor: Any, ruta: str, errores: list[dict[str, str]], *, vacia_permitida: bool = False) -> bool:
    if not isinstance(valor, list):
        _err(errores, ruta, "se requiere una lista de identificadores")
        return False
    if not valor and not vacia_permitida:
        _err(errores, ruta, "la lista de identificadores no puede estar vacía")
        return False
    vistos: set[str] = set()
    ok = True
    for idx, item in enumerate(valor):
        if not _es_texto_no_vacio(item):
            _err(errores, f"{ruta}[{idx}]", "se requiere un identificador de texto no vacío")
            ok = False
        elif item in vistos:
            _err(errores, f"{ruta}[{idx}]", f"identificador repetido '{item}'")
            ok = False
        else:
            vistos.add(item)
    return ok


def _validar_claves_exactas(obj: Any, esperadas: frozenset[str], ruta: str, errores: list[dict[str, str]]) -> bool:
    if not isinstance(obj, dict):
        _err(errores, ruta, "se requiere un objeto JSON")
        return False
    actuales = set(obj.keys())
    faltan = sorted(esperadas - actuales)
    sobran = sorted(actuales - esperadas)
    if faltan:
        _err(errores, ruta, "faltan campos obligatorios: " + ", ".join(faltan))
    if sobran:
        _err(errores, ruta, "campos no admitidos en contrato cerrado: " + ", ".join(sobran))
    return not faltan and not sobran


def _validar_selector(selector: Any, ruta: str, errores: list[dict[str, str]]) -> None:
    if not isinstance(selector, dict):
        _err(errores, ruta, "selector debe ser un objeto JSON")
        return
    tipo = selector.get("tipo")
    if tipo not in ("plano_z", "borde_entre_puntos", "entidades", "nodos"):
        _err(errores, f"{ruta}.tipo", "selector.tipo debe ser 'plano_z', 'borde_entre_puntos', 'entidades' o 'nodos'")
        return

    claves = set(selector.keys())
    if tipo == "plano_z":
        permitidas = {"tipo", "z_m", "hosts", "solo_corte"}
        sobran = sorted(claves - permitidas)
        if "z_m" not in claves:
            _err(errores, ruta, "selector 'plano_z' requiere 'z_m'")
        if sobran:
            _err(errores, ruta, "campos no admitidos en selector 'plano_z': " + ", ".join(sobran))
        if "z_m" in claves and not _es_numero_finito(selector["z_m"]):
            _err(errores, f"{ruta}.z_m", "z_m debe ser un número finito en metros")
        if selector.get("hosts") is not None:
            _validar_lista_ids(selector["hosts"], f"{ruta}.hosts", errores)
        if selector.get("solo_corte") is not None and type(selector["solo_corte"]) is not bool:
            _err(errores, f"{ruta}.solo_corte", "solo_corte debe ser booleano explícito")
        return

    if tipo == "borde_entre_puntos":
        permitidas = {"tipo", "inicio", "fin", "hosts"}
        faltan = sorted({"tipo", "inicio", "fin"} - claves)
        sobran = sorted(claves - permitidas)
        if faltan:
            _err(errores, ruta, "selector 'borde_entre_puntos' requiere: " + ", ".join(faltan))
        if sobran:
            _err(errores, ruta, "campos no admitidos en selector 'borde_entre_puntos': " + ", ".join(sobran))
        if "inicio" in claves and not _es_texto_no_vacio(selector["inicio"]):
            _err(errores, f"{ruta}.inicio", "inicio debe ser un identificador de punto no vacío")
        if "fin" in claves and not _es_texto_no_vacio(selector["fin"]):
            _err(errores, f"{ruta}.fin", "fin debe ser un identificador de punto no vacío")
        if (
            _es_texto_no_vacio(selector.get("inicio"))
            and _es_texto_no_vacio(selector.get("fin"))
            and selector["inicio"] == selector["fin"]
        ):
            _err(errores, ruta, "inicio y fin deben ser puntos distintos")
        if selector.get("hosts") is not None:
            _validar_lista_ids(selector["hosts"], f"{ruta}.hosts", errores)
        return

    if tipo == "entidades":
        permitidas = {"tipo", "hosts", "aberturas", "conexiones_borde", "nodos_corte"}
        sobran = sorted(claves - permitidas)
        if sobran:
            _err(errores, ruta, "campos no admitidos en selector 'entidades': " + ", ".join(sobran))
        filtros_activos = [
            k for k in ("hosts", "aberturas", "conexiones_borde", "nodos_corte") if selector.get(k) is not None
        ]
        if not filtros_activos:
            _err(
                errores,
                ruta,
                "selector 'entidades' requiere al menos un filtro explícito (hosts, aberturas, conexiones_borde o nodos_corte)",
            )
        for campo in ("hosts", "aberturas", "conexiones_borde"):
            if selector.get(campo) is not None:
                _validar_lista_ids(selector[campo], f"{ruta}.{campo}", errores)
        if selector.get("nodos_corte") is not None and type(selector["nodos_corte"]) is not bool:
            _err(errores, f"{ruta}.nodos_corte", "nodos_corte debe ser booleano explícito")
        return

    # tipo == "nodos"
    if _validar_claves_exactas(selector, frozenset({"tipo", "nodos"}), ruta, errores):
        _validar_lista_ids(selector["nodos"], f"{ruta}.nodos", errores)


def _validar_accion_diafragma(item: dict[str, Any], ruta: str, errores: list[dict[str, str]]) -> None:
    accion = item.get("accion")
    if accion not in ("asignar", "excluir"):
        _err(errores, f"{ruta}.accion", "accion debe ser 'asignar' o 'excluir'")
        return
    if accion == "asignar":
        if not _es_texto_no_vacio(item.get("diafragma")):
            _err(errores, f"{ruta}.diafragma", "accion 'asignar' requiere un identificador de diafragma no vacío")
        if item.get("motivo_sin_diafragma") is not None:
            _err(errores, f"{ruta}.motivo_sin_diafragma", "accion 'asignar' requiere motivo_sin_diafragma null")
    else:
        if item.get("diafragma") is not None:
            _err(errores, f"{ruta}.diafragma", "accion 'excluir' requiere diafragma null")
        if not _es_texto_no_vacio(item.get("motivo_sin_diafragma")):
            _err(errores, f"{ruta}.motivo_sin_diafragma", "accion 'excluir' requiere motivo_sin_diafragma explícito")


def validar_reglas_politica(reglas: Any) -> list[dict[str, str]]:
    """Valida el contrato cerrado `draft2model.reglas_politica_malla` 0.1.0 sin mutar la entrada."""
    errores: list[dict[str, str]] = []
    try:
        _canon(reglas)
    except (TypeError, ValueError):
        _err(errores, "$.reglas", "las reglas contienen valores no serializables como JSON estricto (p. ej. NaN o infinito)")
        return errores

    if not _validar_claves_exactas(reglas, _CLAVES_REGLAS_RAIZ, "$.reglas", errores):
        return errores

    if reglas["contrato"] != CONTRATO_REGLAS:
        _err(errores, "$.reglas.contrato", f"se requiere contrato '{CONTRATO_REGLAS}'")
    if reglas["version_contrato"] != VERSION_CONTRATO:
        _err(errores, "$.reglas.version_contrato", f"se requiere version_contrato '{VERSION_CONTRATO}'")
    if reglas["unidad_longitud"] != "m":
        _err(errores, "$.reglas.unidad_longitud", "se requiere unidad_longitud explícita igual a 'm'")

    # reglas_restricciones
    if not isinstance(reglas["reglas_restricciones"], list):
        _err(errores, "$.reglas.reglas_restricciones", "debe ser una lista de reglas")
    else:
        ids_r: set[str] = set()
        for i, item in enumerate(reglas["reglas_restricciones"]):
            ruta = f"$.reglas.reglas_restricciones[{i}]"
            if not _validar_claves_exactas(item, _CLAVES_REGLA_RESTRICCION, ruta, errores):
                continue
            if not _es_texto_no_vacio(item["id"]):
                _err(errores, f"{ruta}.id", "id debe ser texto no vacío")
            elif item["id"] in ids_r:
                _err(errores, f"{ruta}.id", f"id de regla de restricción repetido '{item['id']}'")
            else:
                ids_r.add(item["id"])
            _validar_selector(item["selector"], f"{ruta}.selector", errores)
            if not _es_restriccion_6(item["restricciones"]):
                _err(errores, f"{ruta}.restricciones", "restricciones requiere seis booleanos explícitos [Ux,Uy,Uz,Rx,Ry,Rz]")
            if not _es_texto_no_vacio(item["fuente"]):
                _err(errores, f"{ruta}.fuente", "fuente debe ser un identificador no vacío")
            if not _es_texto_no_vacio(item["motivo"]):
                _err(errores, f"{ruta}.motivo", "motivo debe ser texto explícito no vacío")

    # resto_restricciones
    resto_r = reglas["resto_restricciones"]
    if resto_r is not None:
        ruta = "$.reglas.resto_restricciones"
        if _validar_claves_exactas(resto_r, _CLAVES_RESTO_RESTRICCION, ruta, errores):
            if not _es_restriccion_6(resto_r["restricciones"]):
                _err(errores, f"{ruta}.restricciones", "restricciones requiere seis booleanos explícitos [Ux,Uy,Uz,Rx,Ry,Rz]")
            if not _es_texto_no_vacio(resto_r["fuente"]):
                _err(errores, f"{ruta}.fuente", "fuente debe ser un identificador no vacío")
            if not _es_texto_no_vacio(resto_r["motivo"]):
                _err(errores, f"{ruta}.motivo", "motivo debe ser texto explícito no vacío")

    # reglas_diafragma
    if not isinstance(reglas["reglas_diafragma"], list):
        _err(errores, "$.reglas.reglas_diafragma", "debe ser una lista de reglas")
    else:
        ids_d: set[str] = set()
        for i, item in enumerate(reglas["reglas_diafragma"]):
            ruta = f"$.reglas.reglas_diafragma[{i}]"
            if not _validar_claves_exactas(item, _CLAVES_REGLA_DIAFRAGMA, ruta, errores):
                continue
            if not _es_texto_no_vacio(item["id"]):
                _err(errores, f"{ruta}.id", "id debe ser texto no vacío")
            elif item["id"] in ids_d:
                _err(errores, f"{ruta}.id", f"id de regla de diafragma repetido '{item['id']}'")
            else:
                ids_d.add(item["id"])
            _validar_selector(item["selector"], f"{ruta}.selector", errores)
            _validar_accion_diafragma(item, ruta, errores)
            if not _es_texto_no_vacio(item["fuente"]):
                _err(errores, f"{ruta}.fuente", "fuente debe ser un identificador no vacío")

    # resto_diafragma
    resto_d = reglas["resto_diafragma"]
    if resto_d is not None:
        ruta = "$.reglas.resto_diafragma"
        if _validar_claves_exactas(resto_d, _CLAVES_RESTO_DIAFRAGMA, ruta, errores):
            _validar_accion_diafragma(resto_d, ruta, errores)
            if not _es_texto_no_vacio(resto_d["fuente"]):
                _err(errores, f"{ruta}.fuente", "fuente debe ser un identificador no vacío")

    # subdivision_frames
    sub = reglas["subdivision_frames"]
    if sub is not None:
        ruta = "$.reglas.subdivision_frames"
        if not isinstance(sub, dict):
            _err(errores, ruta, "subdivision_frames debe ser null o un objeto JSON")
        else:
            modo = sub.get("modo")
            if modo == "autorizar_calculadas":
                if _validar_claves_exactas(sub, _CLAVES_SUBDIV_TODAS, ruta, errores):
                    if not _es_texto_no_vacio(sub["fuente"]):
                        _err(errores, f"{ruta}.fuente", "fuente debe ser un identificador no vacío")
                    if not _es_texto_no_vacio(sub["motivo"]):
                        _err(errores, f"{ruta}.motivo", "motivo debe ser texto explícito no vacío")
            elif modo == "por_frame":
                if _validar_claves_exactas(sub, _CLAVES_SUBDIV_POR_FRAME, ruta, errores):
                    if not isinstance(sub["reglas_frames"], list):
                        _err(errores, f"{ruta}.reglas_frames", "reglas_frames debe ser una lista")
                    else:
                        ids_f: set[str] = set()
                        for i, rf in enumerate(sub["reglas_frames"]):
                            ruta_f = f"{ruta}.reglas_frames[{i}]"
                            if not _validar_claves_exactas(rf, _CLAVES_REGLA_FRAME, ruta_f, errores):
                                continue
                            if not _es_texto_no_vacio(rf["id"]):
                                _err(errores, f"{ruta_f}.id", "id debe ser texto no vacío")
                            elif rf["id"] in ids_f:
                                _err(errores, f"{ruta_f}.id", f"id de regla de frame repetido '{rf['id']}'")
                            else:
                                ids_f.add(rf["id"])
                            _validar_lista_ids(rf["frames"], f"{ruta_f}.frames", errores)
                            if rf["accion"] not in ("autorizar", "bloquear"):
                                _err(errores, f"{ruta_f}.accion", "accion debe ser 'autorizar' o 'bloquear'")
                            if not _es_texto_no_vacio(rf["fuente"]):
                                _err(errores, f"{ruta_f}.fuente", "fuente debe ser un identificador no vacío")
                            if not _es_texto_no_vacio(rf["motivo"]):
                                _err(errores, f"{ruta_f}.motivo", "motivo debe ser texto explícito no vacío")
            else:
                _err(errores, f"{ruta}.modo", "modo debe ser 'autorizar_calculadas' o 'por_frame'")

    return errores


def _nodos_en_segmento_abierto(
    a: list[float],
    b: list[float],
    xyz_derivados: dict[str, list[float]],
) -> set[str]:
    """Reutiliza el criterio exacto de colinealidad interior de `malla_preparacion` (sin fusión por proximidad)."""
    largo = math.dist(a, b)
    if largo == 0.0:
        return set()
    fa = [Fraction(x) for x in a]
    fb = [Fraction(x) for x in b]
    d = [y - x for x, y in zip(fa, fb)]
    dd = sum(x * x for x in d)
    eps = max(1e-12, 64 * math.ulp(max(abs(x) for x in a + b)) / largo)
    umbral2 = (Fraction(eps) * Fraction(largo)) ** 2
    seleccionados: set[str] = set()
    for nombre, p in xyz_derivados.items():
        fp = [Fraction(x) for x in p]
        v = [x - y for x, y in zip(fp, fa)]
        t = sum(x * y for x, y in zip(v, d)) / dd
        if not 0 < t < 1:
            continue
        cr = [
            v[1] * d[2] - v[2] * d[1],
            v[2] * d[0] - v[0] * d[2],
            v[0] * d[1] - v[1] * d[0],
        ]
        if sum(x * x for x in cr) / dd <= umbral2:
            seleccionados.add(nombre)
    return seleccionados


def _construir_inventario(
    prep: dict[str, Any],
    configuracion: dict[str, Any],
    vg: Any,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Construye el inventario determinista de nodos derivados y subdivisiones de frames."""
    nodos_corte = set(prep["cortes_nivel"]["nodos_corte"]) if prep["cortes_nivel"] else set()

    hosts_por_nodo: dict[str, set[str]] = {n: set() for n in prep["nodos_derivados"]}
    for tri in prep["triangulos"]:
        for n in tri["nodos"]:
            if n in hosts_por_nodo:
                hosts_por_nodo[n].add(tri["host"])

    # Mapeo de identificadores internos de malla a nombres CSI y aristas de contorno (superficies y huecos).
    malla_a_csi: dict[str, str] = {}
    raw_por_csi: dict[str, dict[str, Any]] = {}
    aristas_contorno: dict[tuple[str, int], set[str]] = {}
    g_m = vg.geometria_m
    for sup in g_m.get("superficies", []):
        if sup["id"] in prep["hosts"]:
            vs = sup["vertices"]
            for idx_ar in range(len(vs)):
                aristas_contorno[(f"superficie:{sup['id']}", idx_ar)] = {vs[idx_ar], vs[(idx_ar + 1) % len(vs)]}
    for ab in g_m.get("aberturas", []):
        if ab["superficie"] in prep["hosts"]:
            vs = ab["vertices"]
            for idx_ar in range(len(vs)):
                aristas_contorno[(f"hueco:{ab['id']}", idx_ar)] = {vs[idx_ar], vs[(idx_ar + 1) % len(vs)]}

    for item in prep["nodos"]:
        csi = item["csi"]
        raw_por_csi[csi] = item
        if item["tipo"] == "derivado":
            interno = item["nodo_malla"]
            malla_a_csi[interno] = csi
            todos_internos = {interno, *item.get("alias", [])}
            for alias_id in item.get("alias", []):
                malla_a_csi[alias_id] = csi
            for traza in item.get("trazas", []):
                contorno = traza.get("contorno")
                idx_ar = traza.get("arista")
                if isinstance(contorno, str) and isinstance(idx_ar, int) and (contorno, idx_ar) in aristas_contorno:
                    aristas_contorno[(contorno, idx_ar)] |= todos_internos
        else:
            for vid in item.get("vertices_geometria", []):
                malla_a_csi[vid] = csi

    conexiones_por_nodo: dict[str, set[str]] = {n: set() for n in prep["nodos_derivados"]}
    for cx in prep.get("conexiones", []):
        cid = cx["id"]
        internos = set(cx.get("nodos_compartidos", []))
        for interno in internos:
            csi = malla_a_csi.get(interno)
            if csi in conexiones_por_nodo:
                conexiones_por_nodo[csi].add(cid)
        for n_corte in nodos_corte:
            for traza in raw_por_csi[n_corte].get("trazas", []):
                arista = traza.get("arista")
                if isinstance(arista, list) and len(arista) == 2 and set(arista) <= internos:
                    conexiones_por_nodo[n_corte].add(cid)

    inventario_nodos: list[dict[str, Any]] = []
    mapa_nodos: dict[str, dict[str, Any]] = {}
    for csi in prep["nodos_derivados"]:
        raw = raw_por_csi[csi]
        xyz = [_norm_float(c) for c in raw["xyz_m"]]
        aberturas_nodo: set[str] = set()
        bordes_superficie: set[str] = set()
        for traza in raw.get("trazas", []):
            contorno = traza.get("contorno")
            if isinstance(contorno, str):
                if contorno.startswith("hueco:"):
                    aberturas_nodo.add(contorno.split(":", 1)[1])
                elif contorno.startswith("superficie:"):
                    bordes_superficie.add(contorno.split(":", 1)[1])
            elif traza.get("tipo") == "interseccion_nivel_calculada":
                arista = traza.get("arista")
                if isinstance(arista, list) and len(arista) == 2:
                    par = set(arista)
                    for (contorno_k, _), conj_nodos in aristas_contorno.items():
                        if par <= conj_nodos:
                            if contorno_k.startswith("hueco:"):
                                aberturas_nodo.add(contorno_k.split(":", 1)[1])
                            elif contorno_k.startswith("superficie:"):
                                bordes_superficie.add(contorno_k.split(":", 1)[1])
        ficha = {
            "nodo": csi,
            "xyz_m": xyz,
            "z_m": xyz[2],
            "es_nodo_corte": csi in nodos_corte,
            "hosts": sorted(hosts_por_nodo[csi]),
            "aberturas": sorted(aberturas_nodo),
            "bordes_superficie": sorted(bordes_superficie),
            "conexiones_borde": sorted(conexiones_por_nodo[csi]),
        }
        inventario_nodos.append(ficha)
        mapa_nodos[csi] = ficha

    frames_cfg = {f["id"]: f for f in configuracion.get("frames", []) if isinstance(f, dict) and isinstance(f.get("id"), str)}
    inventario_frames: list[dict[str, Any]] = []
    for req in prep["frames_subdivision_requerida"]:
        fid = req["frame"]
        f_orig = frames_cfg.get(fid, {})
        nodos_seq = list(req["nodos"])
        inventario_frames.append({
            "frame": fid,
            "inicio": f_orig.get("inicio", nodos_seq[0]),
            "fin": f_orig.get("fin", nodos_seq[-1]),
            "nodos": nodos_seq,
            "nodos_interiores": nodos_seq[1:-1],
            "subframes": list(req["subframes"]),
        })

    return inventario_nodos, mapa_nodos, inventario_frames


def _evaluar_selector(
    selector: dict[str, Any],
    ruta: str,
    *,
    mapa_nodos: dict[str, dict[str, Any]],
    xyz_derivados: dict[str, list[float]],
    coords_puntos: dict[str, list[float]],
    hosts_disponibles: set[str],
    aberturas_disponibles: set[str],
    conexiones_disponibles: set[str],
    errores: list[dict[str, str]],
) -> set[str] | None:
    """Evalúa un selector validado frente al inventario reproducido; devuelve None si hay referencias inválidas."""
    tipo = selector["tipo"]
    antes = len(errores)

    if tipo == "plano_z":
        hosts_sel = selector.get("hosts")
        if hosts_sel is not None:
            for h in hosts_sel:
                if h not in hosts_disponibles:
                    _err(errores, f"{ruta}.hosts", f"superficie host inexistente o no mallada: '{h}'")
        if len(errores) > antes:
            return None
        z_obj = _norm_float(selector["z_m"])
        solo_corte = selector.get("solo_corte")
        hosts_set = set(hosts_sel) if hosts_sel is not None else None
        out: set[str] = set()
        for csi, info in mapa_nodos.items():
            if info["z_m"] != z_obj:
                continue
            if hosts_set is not None and not ( set(info["hosts"]) & hosts_set ):
                continue
            if solo_corte is not None and info["es_nodo_corte"] is not solo_corte:
                continue
            out.add(csi)
        return out

    if tipo == "borde_entre_puntos":
        ini, fin = selector["inicio"], selector["fin"]
        if ini not in coords_puntos:
            _err(errores, f"{ruta}.inicio", f"punto '{ini}' inexistente en configuracion.puntos")
        if fin not in coords_puntos:
            _err(errores, f"{ruta}.fin", f"punto '{fin}' inexistente en configuracion.puntos")
        hosts_sel = selector.get("hosts")
        if hosts_sel is not None:
            for h in hosts_sel:
                if h not in hosts_disponibles:
                    _err(errores, f"{ruta}.hosts", f"superficie host inexistente o no mallada: '{h}'")
        if len(errores) > antes:
            return None
        pa, pb = coords_puntos[ini], coords_puntos[fin]
        if pa == pb:
            _err(errores, ruta, f"puntos '{ini}' y '{fin}' tienen coordenadas idénticas; segmento degenerado")
            return None
        candidatos = _nodos_en_segmento_abierto(pa, pb, xyz_derivados)
        if hosts_sel is not None:
            hosts_set = set(hosts_sel)
            candidatos = {n for n in candidatos if set(mapa_nodos[n]["hosts"]) & hosts_set}
        return candidatos

    if tipo == "entidades":
        hosts_sel = selector.get("hosts")
        ab_sel = selector.get("aberturas")
        cx_sel = selector.get("conexiones_borde")
        corte_sel = selector.get("nodos_corte")
        if hosts_sel is not None:
            for h in hosts_sel:
                if h not in hosts_disponibles:
                    _err(errores, f"{ruta}.hosts", f"superficie host inexistente o no mallada: '{h}'")
        if ab_sel is not None:
            for ab in ab_sel:
                if ab not in aberturas_disponibles:
                    _err(errores, f"{ruta}.aberturas", f"abertura inexistente en hosts mallados: '{ab}'")
        if cx_sel is not None:
            for cid in cx_sel:
                if cid not in conexiones_disponibles:
                    _err(errores, f"{ruta}.conexiones_borde", f"conexión de borde inexistente: '{cid}'")
        if len(errores) > antes:
            return None
        out = set(mapa_nodos.keys())
        if hosts_sel is not None:
            hs = set(hosts_sel)
            out = {n for n in out if set(mapa_nodos[n]["hosts"]) & hs}
        if ab_sel is not None:
            abs_set = set(ab_sel)
            out = {n for n in out if set(mapa_nodos[n]["aberturas"]) & abs_set}
        if cx_sel is not None:
            cxs = set(cx_sel)
            out = {n for n in out if set(mapa_nodos[n]["conexiones_borde"]) & cxs}
        if corte_sel is not None:
            out = {n for n in out if mapa_nodos[n]["es_nodo_corte"] is corte_sel}
        return out

    # tipo == "nodos"
    nodos_sel = selector["nodos"]
    for n in nodos_sel:
        if n not in mapa_nodos:
            _err(errores, f"{ruta}.nodos", f"'{n}' no es un nodo derivado de la malla reproducida")
    if len(errores) > antes:
        return None
    return set(nodos_sel)


def _extraer_fuentes_configuracion(configuracion: dict[str, Any], errores: list[dict[str, str]]) -> set[str]:
    raw = configuracion.get("fuentes")
    if not isinstance(raw, list):
        _err(errores, "$.configuracion.fuentes", "configuracion.fuentes debe ser una lista")
        return set()
    fuentes: set[str] = set()
    for i, item in enumerate(raw):
        ruta = f"$.configuracion.fuentes[{i}]"
        if not isinstance(item, dict) or set(item.keys()) != {"id", "descripcion", "referencia", "sha256"}:
            _err(errores, ruta, "cada fuente requiere exactamente id, descripcion, referencia y sha256")
            continue
        fid = item["id"]
        if not _es_texto_no_vacio(fid):
            _err(errores, f"{ruta}.id", "id de fuente inválido")
            continue
        if fid in fuentes:
            _err(errores, f"{ruta}.id", f"id de fuente repetido '{fid}'")
            continue
        if not _es_texto_no_vacio(item["descripcion"]) or not _es_texto_no_vacio(item["referencia"]):
            _err(errores, ruta, "descripcion y referencia de fuente deben ser textos no vacíos")
        if not isinstance(item["sha256"], str) or not _RE_HEX64.match(item["sha256"]):
            _err(errores, f"{ruta}.sha256", "sha256 de fuente debe ser hexadecimal en minúsculas de 64 caracteres")
        fuentes.add(fid)
    return fuentes


def _extraer_cotas_diafragmas(
    configuracion: dict[str, Any],
    coords_puntos: dict[str, list[float]],
    errores: list[dict[str, str]],
) -> dict[str, float]:
    raw = configuracion.get("diafragmas")
    if not isinstance(raw, list):
        _err(errores, "$.configuracion.diafragmas", "configuracion.diafragmas debe ser una lista")
        return {}
    cotas_por_id: dict[str, float] = {}
    for i, item in enumerate(raw):
        ruta = f"$.configuracion.diafragmas[{i}]"
        if not isinstance(item, dict) or not _es_texto_no_vacio(item.get("id")):
            _err(errores, ruta, "diafragma inválido en configuracion.diafragmas")
            continue
        did = item["id"]
        if did in cotas_por_id:
            _err(errores, f"{ruta}.id", f"diafragma repetido '{did}'")
            continue
        pts = item.get("puntos")
        if not isinstance(pts, list) or len(pts) < 2:
            _err(errores, f"{ruta}.puntos", f"diafragma '{did}' requiere al menos dos puntos coplanares")
            continue
        zs: set[float] = set()
        ok = True
        for p in pts:
            if not isinstance(p, str) or p not in coords_puntos:
                _err(errores, f"{ruta}.puntos", f"diafragma '{did}' referencia punto inexistente '{p}'")
                ok = False
            else:
                zs.add(_norm_float(coords_puntos[p][2]))
        if not ok:
            continue
        if len(zs) != 1:
            _err(errores, f"{ruta}.puntos", f"puntos del diafragma '{did}' no son coplanares en Z")
            continue
        cotas_por_id[did] = next(iter(zs))
    return cotas_por_id


def _propuesta_base(
    *,
    caso: str | None,
    datos_sinteticos: bool | None,
    huella_preparacion: str | None,
    inventario_nodos: list[dict[str, Any]],
    inventario_frames: list[dict[str, Any]],
    propuestos_nodos: list[dict[str, Any]],
    propuestos_frames: list[dict[str, Any]],
    trazabilidad_nodos: list[dict[str, Any]],
    reglas_sin_coincidencia: list[str],
    pendientes: list[dict[str, Any]],
    conflictos: list[dict[str, Any]],
    errores: list[dict[str, str]],
    reglas_declaradas: bool,
) -> dict[str, Any]:
    listo = reglas_declaradas and not errores and not conflictos and not pendientes
    salida = {
        "contrato": CONTRATO_PROPUESTA,
        "version_contrato": VERSION_CONTRATO,
        "ejecutable": False,
        "aprueba_ingenieria": False,
        "caso": caso,
        "datos_sinteticos": datos_sinteticos,
        "reglas_declaradas": reglas_declaradas,
        "listo_para_aplicar": listo,
        "huella_preparacion": huella_preparacion,
        "resumen": {
            "total_nodos_derivados": len(inventario_nodos),
            "nodos_derivados_resueltos": len(propuestos_nodos),
            "total_frames_subdivididos": len(inventario_frames),
            "frames_subdivididos_resueltos": len(propuestos_frames),
            "pendientes": len(pendientes),
            "conflictos": len(conflictos),
            "errores": len(errores),
        },
        "inventario_nodos_derivados": inventario_nodos,
        "inventario_subdivision_frames": inventario_frames,
        "nodos_derivados_propuestos": propuestos_nodos,
        "subdivision_frames_propuesta": propuestos_frames,
        "trazabilidad_nodos": trazabilidad_nodos,
        "reglas_sin_coincidencia": sorted(reglas_sin_coincidencia),
        "pendientes": pendientes,
        "conflictos": conflictos,
        "errores": errores,
    }
    salida["huella_propuesta"] = _sha(salida)
    return salida


def previsualizar_politicas_malla(
    geometria: Any,
    configuracion: Any,
    reglas: Any = None,
) -> dict[str, Any]:
    """Evalúa de forma pura la malla reproducida y las reglas explícitas sin modificar entradas ni disco."""
    errores: list[dict[str, str]] = []
    conflictos: list[dict[str, Any]] = []
    pendientes: list[dict[str, Any]] = []

    if not isinstance(geometria, dict):
        _err(errores, "$.geometria", "geometria debe ser un objeto JSON")
    if not isinstance(configuracion, dict):
        _err(errores, "$.configuracion", "configuracion debe ser un objeto JSON")
    if errores:
        return _propuesta_base(
            caso=None,
            datos_sinteticos=None,
            huella_preparacion=None,
            inventario_nodos=[],
            inventario_frames=[],
            propuestos_nodos=[],
            propuestos_frames=[],
            trazabilidad_nodos=[],
            reglas_sin_coincidencia=[],
            pendientes=[],
            conflictos=[],
            errores=errores,
            reglas_declaradas=reglas is not None,
        )

    try:
        sha_geo_in = _sha(geometria)
    except (TypeError, ValueError):
        _err(errores, "$.geometria", "geometria contiene valores no serializables como JSON estricto (p. ej. NaN o infinito)")
        sha_geo_in = ""
    try:
        sha_cfg_in = _sha(configuracion)
    except (TypeError, ValueError):
        _err(errores, "$.configuracion", "configuracion contiene valores no serializables como JSON estricto (p. ej. NaN o infinito)")
        sha_cfg_in = ""
    sha_reglas_in: str | None = None
    if reglas is not None:
        errores.extend(validar_reglas_politica(reglas))
        if not any(e["ruta"] == "$.reglas" and "serializables" in e["mensaje"] for e in errores):
            try:
                sha_reglas_in = _sha(reglas)
            except (TypeError, ValueError):
                sha_reglas_in = None

    caso_cfg = configuracion.get("caso") if isinstance(configuracion.get("caso"), str) else None
    sintetico_cfg = configuracion.get("datos_sinteticos") if type(configuracion.get("datos_sinteticos")) is bool else None

    if sha_geo_in == "" or sha_cfg_in == "":
        return _propuesta_base(
            caso=caso_cfg,
            datos_sinteticos=sintetico_cfg,
            huella_preparacion=None,
            inventario_nodos=[],
            inventario_frames=[],
            propuestos_nodos=[],
            propuestos_frames=[],
            trazabilidad_nodos=[],
            reglas_sin_coincidencia=[],
            pendientes=[],
            conflictos=[],
            errores=errores,
            reglas_declaradas=reglas is not None,
        )

    # 1. Validar geometría 0.3.0 y unidades/coordenadas.
    if geometria.get("version_contrato") != VERSION_GEOMETRIA:
        _err(
            errores,
            "$.geometria.version_contrato",
            f"se exige geometría {VERSION_GEOMETRIA} explícita; recibido {geometria.get('version_contrato')!r}",
        )
        vg = None
    else:
        vg = validar_geometria(copy.deepcopy(geometria))
        if not vg.consistente:
            detalle = "; ".join(str(e) for e in vg.errores)[:600]
            _err(errores, "$.geometria", f"geometría inconsistente: {detalle}")
            vg = None

    # 2. Validar contrato, unidades e identidad/origen de la configuración respecto de la geometría.
    if configuracion.get("contrato") != CONTRATO_CONFIGURACION:
        _err(errores, "$.configuracion.contrato", f"se requiere contrato '{CONTRATO_CONFIGURACION}'")
    if configuracion.get("version_contrato") not in VERSIONES_CONFIGURACION:
        _err(
            errores,
            "$.configuracion.version_contrato",
            f"se requiere version_contrato en {VERSIONES_CONFIGURACION}; recibido {configuracion.get('version_contrato')!r}",
        )
    if configuracion.get("unidades") != UNIDADES_CONFIGURACION:
        _err(errores, "$.configuracion.unidades", "se requieren unidades explícitas m, kN, s, C")
    if type(configuracion.get("datos_sinteticos")) is not bool:
        _err(errores, "$.configuracion.datos_sinteticos", "datos_sinteticos debe ser booleano explícito")

    if vg is not None:
        if configuracion.get("caso") != geometria.get("id"):
            _err(
                errores,
                "$.configuracion.caso",
                f"caso '{configuracion.get('caso')}' no corresponde a geometria.id '{geometria.get('id')}'",
            )
        if type(configuracion.get("datos_sinteticos")) is bool and configuracion["datos_sinteticos"] is not vg.datos_sinteticos:
            _err(
                errores,
                "$.configuracion.datos_sinteticos",
                "la marca datos_sinteticos de la configuración no coincide con la geometría origen",
            )
        origen = configuracion.get("geometria_origen")
        if not isinstance(origen, dict) or set(origen.keys()) != {"version_id", "sha256_geometria", "huella_contenido"}:
            _err(
                errores,
                "$.configuracion.geometria_origen",
                "geometria_origen requiere exactamente version_id, sha256_geometria y huella_contenido",
            )
        else:
            if not isinstance(origen["version_id"], str) or not _RE_HEX32.match(origen["version_id"]):
                _err(errores, "$.configuracion.geometria_origen.version_id", "version_id inválido")
            if not isinstance(origen["sha256_geometria"], str) or not _RE_HEX64.match(origen["sha256_geometria"]):
                _err(errores, "$.configuracion.geometria_origen.sha256_geometria", "sha256_geometria inválido")
            if origen.get("huella_contenido") != vg.huella_contenido:
                _err(
                    errores,
                    "$.configuracion.geometria_origen.huella_contenido",
                    "huella_contenido de geometria_origen no corresponde a la geometría suministrada",
                )

    fuentes_cfg = _extraer_fuentes_configuracion(configuracion, errores)

    malla_decl = configuracion.get("malla")
    if not isinstance(malla_decl, dict) or set(malla_decl.keys()) != {"estrategia", "fuente"}:
        _err(errores, "$.configuracion.malla", "configuracion.malla requiere estrategia y fuente")
    else:
        if malla_decl.get("estrategia") != mp.ESTRATEGIA:
            _err(errores, "$.configuracion.malla.estrategia", f"se requiere estrategia '{mp.ESTRATEGIA}'")
        if malla_decl.get("fuente") is not None and malla_decl.get("fuente") not in fuentes_cfg:
            _err(errores, "$.configuracion.malla.fuente", f"fuente de malla inexistente: {malla_decl.get('fuente')!r}")

    cortes_decl = configuracion.get("cortes_nivel")
    if not isinstance(cortes_decl, list):
        _err(errores, "$.configuracion.cortes_nivel", "cortes_nivel debe ser una lista")
    else:
        vistos_z_corte: set[float] = set()
        for idx, c in enumerate(cortes_decl):
            ruta_c = f"$.configuracion.cortes_nivel[{idx}]"
            if not isinstance(c, dict) or set(c.keys()) != {"z_m", "fuente", "motivo"}:
                _err(errores, ruta_c, "cada corte_nivel requiere z_m, fuente y motivo")
                continue
            if not _es_numero_finito(c["z_m"]):
                _err(errores, f"{ruta_c}.z_m", "z_m de corte debe ser número finito en metros")
            else:
                zf = _norm_float(c["z_m"])
                if zf in vistos_z_corte:
                    _err(errores, f"{ruta_c}.z_m", "nivel de corte Z repetido")
                vistos_z_corte.add(zf)
            if not _es_texto_no_vacio(c["fuente"]) or c["fuente"] not in fuentes_cfg:
                _err(errores, f"{ruta_c}.fuente", f"fuente de corte inexistente: {c.get('fuente')!r}")
            if not _es_texto_no_vacio(c["motivo"]):
                _err(errores, f"{ruta_c}.motivo", "motivo de corte debe ser texto no vacío")

    if not isinstance(configuracion.get("conexiones_borde"), dict):
        _err(
            errores,
            "$.configuracion.conexiones_borde",
            "se requiere el documento draft2model.conexiones_borde para reproducir la malla compatible",
        )

    # Si no se puede preparar la malla por incompatibilidad estructural, retornar diagnóstico limpio.
    prep: dict[str, Any] | None = None
    coords_puntos: dict[str, list[float]] = {}
    if vg is not None and isinstance(configuracion.get("conexiones_borde"), dict):
        try:
            coords_puntos = mp.coordenadas_puntos(configuracion, vg)
            prep = mp.preparar_malla(geometria, configuracion)
        except (KeyError, TypeError, ValueError, mp.ErrorMalla) as exc:
            _err(errores, "$.malla", str(exc))
            prep = None

    datos_sinteticos_res = vg.datos_sinteticos if vg is not None else sintetico_cfg

    if prep is None:
        assert _sha(geometria) == sha_geo_in
        assert _sha(configuracion) == sha_cfg_in
        if sha_reglas_in is not None:
            assert _sha(reglas) == sha_reglas_in
        return _propuesta_base(
            caso=caso_cfg,
            datos_sinteticos=datos_sinteticos_res,
            huella_preparacion=None,
            inventario_nodos=[],
            inventario_frames=[],
            propuestos_nodos=[],
            propuestos_frames=[],
            trazabilidad_nodos=[],
            reglas_sin_coincidencia=[],
            pendientes=[],
            conflictos=[],
            errores=errores,
            reglas_declaradas=reglas is not None,
        )

    inventario_nodos, mapa_nodos, inventario_frames = _construir_inventario(prep, configuracion, vg)
    xyz_derivados = {n: info["xyz_m"] for n, info in mapa_nodos.items()}
    hosts_disponibles = set(prep["hosts"].keys())
    aberturas_disponibles = {ab for hinfo in prep["hosts"].values() for ab in hinfo["aberturas"]}
    conexiones_disponibles = {cx["id"] for cx in prep.get("conexiones", [])}
    cotas_diafragmas = _extraer_cotas_diafragmas(configuracion, coords_puntos, errores)

    reglas_efectivas = plantilla_reglas_vacia() if reglas is None else reglas
    reglas_validas_sintaxis = not any(e["ruta"].startswith("$.reglas") for e in errores)

    if not reglas_validas_sintaxis:
        assert _sha(geometria) == sha_geo_in
        assert _sha(configuracion) == sha_cfg_in
        if sha_reglas_in is not None:
            assert _sha(reglas) == sha_reglas_in
        return _propuesta_base(
            caso=caso_cfg,
            datos_sinteticos=datos_sinteticos_res,
            huella_preparacion=prep["huella_preparacion"],
            inventario_nodos=inventario_nodos,
            inventario_frames=inventario_frames,
            propuestos_nodos=[],
            propuestos_frames=[],
            trazabilidad_nodos=[],
            reglas_sin_coincidencia=[],
            pendientes=[],
            conflictos=[],
            errores=errores,
            reglas_declaradas=reglas is not None,
        )

    # 3. Validar referencias de fuentes, diafragmas y selectores de las reglas contra la configuración/malla.
    reglas_sin_coincidencia: list[str] = []
    coincidencias_restr: dict[str, list[dict[str, Any]]] = {n: [] for n in prep["nodos_derivados"]}
    coincidencias_dia: dict[str, list[dict[str, Any]]] = {n: [] for n in prep["nodos_derivados"]}
    nodos_error_restr: set[str] = set()
    nodos_error_dia: set[str] = set()

    for idx, rr in enumerate(reglas_efectivas["reglas_restricciones"]):
        ruta = f"$.reglas.reglas_restricciones[{idx}]"
        fuente_ok = rr["fuente"] in fuentes_cfg
        if not fuente_ok:
            _err(errores, f"{ruta}.fuente", f"fuente '{rr['fuente']}' inexistente en configuracion.fuentes")
        seleccion = _evaluar_selector(
            rr["selector"],
            f"{ruta}.selector",
            mapa_nodos=mapa_nodos,
            xyz_derivados=xyz_derivados,
            coords_puntos=coords_puntos,
            hosts_disponibles=hosts_disponibles,
            aberturas_disponibles=aberturas_disponibles,
            conexiones_disponibles=conexiones_disponibles,
            errores=errores,
        )
        if seleccion is None:
            continue
        if not seleccion:
            reglas_sin_coincidencia.append(f"restricciones:{rr['id']}")
        if not fuente_ok:
            nodos_error_restr |= seleccion
            continue
        for n in seleccion:
            coincidencias_restr[n].append(rr)

    resto_r = reglas_efectivas["resto_restricciones"]
    resto_r_valido = resto_r is not None
    if resto_r is not None and resto_r["fuente"] not in fuentes_cfg:
        _err(errores, "$.reglas.resto_restricciones.fuente", f"fuente '{resto_r['fuente']}' inexistente en configuracion.fuentes")
        resto_r_valido = False

    for idx, rd in enumerate(reglas_efectivas["reglas_diafragma"]):
        ruta = f"$.reglas.reglas_diafragma[{idx}]"
        fuente_ok = rd["fuente"] in fuentes_cfg
        if not fuente_ok:
            _err(errores, f"{ruta}.fuente", f"fuente '{rd['fuente']}' inexistente en configuracion.fuentes")
        did = rd["diafragma"]
        dia_ok = True
        if rd["accion"] == "asignar" and did not in cotas_diafragmas:
            _err(errores, f"{ruta}.diafragma", f"diafragma '{did}' inexistente o inválido en configuracion.diafragmas")
            dia_ok = False
        seleccion = _evaluar_selector(
            rd["selector"],
            f"{ruta}.selector",
            mapa_nodos=mapa_nodos,
            xyz_derivados=xyz_derivados,
            coords_puntos=coords_puntos,
            hosts_disponibles=hosts_disponibles,
            aberturas_disponibles=aberturas_disponibles,
            conexiones_disponibles=conexiones_disponibles,
            errores=errores,
        )
        if seleccion is None:
            continue
        if not seleccion:
            reglas_sin_coincidencia.append(f"diafragma:{rd['id']}")
        cota_fuera: set[str] = set()
        if rd["accion"] == "asignar" and did in cotas_diafragmas:
            cota_d = cotas_diafragmas[did]
            for n in sorted(seleccion):
                if mapa_nodos[n]["z_m"] != cota_d:
                    _err(
                        errores,
                        ruta,
                        f"nodo derivado '{n}' en z={mapa_nodos[n]['z_m']} m fuera de la cota z={cota_d} m del diafragma '{did}'",
                    )
                    cota_fuera.add(n)
        nodos_error_dia |= cota_fuera
        if not fuente_ok or not dia_ok:
            nodos_error_dia |= seleccion
            continue
        for n in seleccion - cota_fuera:
            coincidencias_dia[n].append(rd)

    resto_d = reglas_efectivas["resto_diafragma"]
    resto_d_valido = resto_d is not None
    if resto_d is not None:
        if resto_d["fuente"] not in fuentes_cfg:
            _err(errores, "$.reglas.resto_diafragma.fuente", f"fuente '{resto_d['fuente']}' inexistente en configuracion.fuentes")
            resto_d_valido = False
        if resto_d["accion"] == "asignar" and resto_d["diafragma"] not in cotas_diafragmas:
            _err(
                errores,
                "$.reglas.resto_diafragma.diafragma",
                f"diafragma '{resto_d['diafragma']}' inexistente o inválido en configuracion.diafragmas",
            )
            resto_d_valido = False

    # 4. Resolver nodo por nodo sin inventar apoyos ni diafragmas y señalando contradicciones.
    propuestos_nodos: list[dict[str, Any]] = []
    trazabilidad_nodos: list[dict[str, Any]] = []

    for n in prep["nodos_derivados"]:
        info = mapa_nodos[n]
        cand_r = coincidencias_restr[n]
        cand_d = coincidencias_dia[n]

        res_r: dict[str, Any] | None = None
        es_especifica_r = False
        origen_r: str | None = None

        if n in nodos_error_restr:
            res_r = None
        elif len(cand_r) == 1:
            res_r = cand_r[0]
            es_especifica_r = True
            origen_r = f"regla:{cand_r[0]['id']}"
        elif len(cand_r) > 1:
            firmas_r = {(tuple(r["restricciones"]), r["fuente"]) for r in cand_r}
            if len(firmas_r) > 1:
                conflictos.append({
                    "tipo": "contradiccion_restricciones",
                    "ruta": f"$.nodos_derivados.{n}.restricciones",
                    "nodo": n,
                    "xyz_m": list(info["xyz_m"]),
                    "reglas": [r["id"] for r in cand_r],
                    "candidatos": [
                        {"id": r["id"], "restricciones": list(r["restricciones"]), "fuente": r["fuente"]}
                        for r in cand_r
                    ],
                    "mensaje": f"Nodo derivado '{n}': reglas de restricciones contradictorias ({', '.join(r['id'] for r in cand_r)}); no se elige la primera.",
                })
            else:
                res_r = cand_r[0]
                es_especifica_r = True
                origen_r = "reglas_coincidentes:" + ",".join(r["id"] for r in cand_r)
        elif resto_r is not None:
            if resto_r_valido:
                res_r = resto_r
                es_especifica_r = False
                origen_r = "resto_restricciones"
        else:
            pendientes.append({
                "tipo": "restricciones_nodo_derivado",
                "ruta": f"$.nodos_derivados.{n}.restricciones",
                "nodo": n,
                "xyz_m": list(info["xyz_m"]),
                "hosts": list(info["hosts"]),
                "es_nodo_corte": info["es_nodo_corte"],
                "motivo": "Sin regla explícita de restricciones ni política resto_restricciones para el nodo derivado.",
            })

        res_d: dict[str, Any] | None = None
        es_especifica_d = False
        origen_d: str | None = None

        if n in nodos_error_dia:
            res_d = None
        elif len(cand_d) == 1:
            res_d = cand_d[0]
            es_especifica_d = True
            origen_d = f"regla:{cand_d[0]['id']}"
        elif len(cand_d) > 1:
            firmas_d = {(r["accion"], r["diafragma"], r["motivo_sin_diafragma"], r["fuente"]) for r in cand_d}
            if len(firmas_d) > 1:
                conflictos.append({
                    "tipo": "contradiccion_diafragma",
                    "ruta": f"$.nodos_derivados.{n}.diafragma",
                    "nodo": n,
                    "xyz_m": list(info["xyz_m"]),
                    "reglas": [r["id"] for r in cand_d],
                    "candidatos": [
                        {
                            "id": r["id"],
                            "accion": r["accion"],
                            "diafragma": r["diafragma"],
                            "motivo_sin_diafragma": r["motivo_sin_diafragma"],
                            "fuente": r["fuente"],
                        }
                        for r in cand_d
                    ],
                    "mensaje": f"Nodo derivado '{n}': reglas de diafragma contradictorias ({', '.join(r['id'] for r in cand_d)}); no se elige la primera.",
                })
            else:
                res_d = cand_d[0]
                es_especifica_d = True
                origen_d = "reglas_coincidentes:" + ",".join(r["id"] for r in cand_d)
        elif resto_d is not None:
            if resto_d_valido:
                cota_ok = True
                if resto_d["accion"] == "asignar" and resto_d["diafragma"] in cotas_diafragmas:
                    cota_d = cotas_diafragmas[resto_d["diafragma"]]
                    if info["z_m"] != cota_d:
                        _err(
                            errores,
                            "$.reglas.resto_diafragma",
                            f"resto_diafragma intenta asignar '{resto_d['diafragma']}' (z={cota_d} m) al nodo '{n}' en z={info['z_m']} m",
                        )
                        cota_ok = False
                if cota_ok:
                    res_d = resto_d
                    es_especifica_d = False
                    origen_d = "resto_diafragma"
        else:
            pendientes.append({
                "tipo": "diafragma_nodo_derivado",
                "ruta": f"$.nodos_derivados.{n}.diafragma",
                "nodo": n,
                "xyz_m": list(info["xyz_m"]),
                "hosts": list(info["hosts"]),
                "es_nodo_corte": info["es_nodo_corte"],
                "motivo": "Sin regla explícita de diafragma ni política resto_diafragma para el nodo derivado.",
            })

        if res_r is not None and res_d is not None:
            fuente_r = res_r["fuente"]
            fuente_d = res_d["fuente"]
            fuente_final: str | None = None
            if fuente_r == fuente_d:
                fuente_final = fuente_r
            elif es_especifica_r and not es_especifica_d:
                fuente_final = fuente_r
            elif es_especifica_d and not es_especifica_r:
                fuente_final = fuente_d
            else:
                conflictos.append({
                    "tipo": "conflicto_fuentes_nodo_derivado",
                    "ruta": f"$.nodos_derivados.{n}.fuente",
                    "nodo": n,
                    "xyz_m": list(info["xyz_m"]),
                    "fuentes": [fuente_r, fuente_d],
                    "mensaje": (
                        f"Nodo derivado '{n}': restricciones ('{fuente_r}') y diafragma ('{fuente_d}') declaran "
                        "fuentes del mismo nivel de especificidad y el registro CSI exige una única fuente explícita."
                    ),
                })
            if fuente_final is not None:
                propuestos_nodos.append({
                    "nodo": n,
                    "xyz_m": list(info["xyz_m"]),
                    "restricciones": list(res_r["restricciones"]),
                    "diafragma": res_d["diafragma"] if res_d["accion"] == "asignar" else None,
                    "motivo_sin_diafragma": res_d["motivo_sin_diafragma"] if res_d["accion"] == "excluir" else None,
                    "fuente": fuente_final,
                })
                trazabilidad_nodos.append({
                    "nodo": n,
                    "origen_restricciones": origen_r,
                    "fuente_restricciones": fuente_r,
                    "motivo_restricciones": res_r["motivo"],
                    "origen_diafragma": origen_d,
                    "fuente_diafragma": fuente_d,
                    "fuente_registro": fuente_final,
                })

    # 5. Evaluar subdivisiones de frames requeridas.
    propuestos_frames: list[dict[str, Any]] = []
    req_por_frame = {item["frame"]: item for item in inventario_frames}
    frames_cfg_ids = {
        f["id"] for f in configuracion.get("frames", []) if isinstance(f, dict) and isinstance(f.get("id"), str)
    }
    pol_sub = reglas_efectivas["subdivision_frames"]

    if pol_sub is None:
        for fid, req in sorted(req_por_frame.items()):
            pendientes.append({
                "tipo": "subdivision_frame",
                "ruta": f"$.subdivision_frames.{fid}",
                "frame": fid,
                "nodos": list(req["nodos"]),
                "subframes": list(req["subframes"]),
                "motivo": "El frame atraviesa nodos interiores de malla; requiere política explícita de subdivisión.",
            })
    elif pol_sub["modo"] == "autorizar_calculadas":
        if pol_sub["fuente"] not in fuentes_cfg:
            _err(
                errores,
                "$.reglas.subdivision_frames.fuente",
                f"fuente '{pol_sub['fuente']}' inexistente en configuracion.fuentes",
            )
        else:
            for fid, req in sorted(req_por_frame.items()):
                propuestos_frames.append({
                    "frame": fid,
                    "nodos": list(req["nodos"]),
                    "fuente": pol_sub["fuente"],
                })
    else:  # modo == "por_frame"
        por_fid: dict[str, list[dict[str, Any]]] = {fid: [] for fid in req_por_frame}
        for idx, rf in enumerate(pol_sub["reglas_frames"]):
            ruta_rf = f"$.reglas.subdivision_frames.reglas_frames[{idx}]"
            if rf["fuente"] not in fuentes_cfg:
                _err(errores, f"{ruta_rf}.fuente", f"fuente '{rf['fuente']}' inexistente en configuracion.fuentes")
            for fid in rf["frames"]:
                if fid not in frames_cfg_ids:
                    _err(errores, f"{ruta_rf}.frames", f"frame '{fid}' inexistente en configuracion.frames")
                elif fid not in req_por_frame:
                    _err(
                        errores,
                        f"{ruta_rf}.frames",
                        f"frame '{fid}' no atraviesa nodos interiores de malla; subdivisión no admitida",
                    )
                else:
                    por_fid[fid].append(rf)

        for fid, req in sorted(req_por_frame.items()):
            cands = por_fid[fid]
            if not cands:
                pendientes.append({
                    "tipo": "subdivision_frame",
                    "ruta": f"$.subdivision_frames.{fid}",
                    "frame": fid,
                    "nodos": list(req["nodos"]),
                    "subframes": list(req["subframes"]),
                    "motivo": "Sin regla explícita para este frame en subdivision_frames.reglas_frames.",
                })
                continue
            firmas_f = {(c["accion"], c["fuente"]) for c in cands}
            if len(firmas_f) > 1:
                conflictos.append({
                    "tipo": "contradiccion_subdivision_frame",
                    "ruta": f"$.subdivision_frames.{fid}",
                    "frame": fid,
                    "reglas": [c["id"] for c in cands],
                    "candidatos": [{"id": c["id"], "accion": c["accion"], "fuente": c["fuente"]} for c in cands],
                    "mensaje": f"Frame '{fid}': reglas de subdivisión contradictorias ({', '.join(c['id'] for c in cands)}); no se elige la primera.",
                })
                continue
            elegida = cands[0]
            if elegida["accion"] == "bloquear":
                pendientes.append({
                    "tipo": "subdivision_frame_bloqueada",
                    "ruta": f"$.subdivision_frames.{fid}",
                    "frame": fid,
                    "nodos": list(req["nodos"]),
                    "subframes": list(req["subframes"]),
                    "motivo": f"Subdivisión bloqueada explícitamente por regla '{elegida['id']}': {elegida['motivo']}",
                })
            elif elegida["fuente"] in fuentes_cfg:
                propuestos_frames.append({
                    "frame": fid,
                    "nodos": list(req["nodos"]),
                    "fuente": elegida["fuente"],
                })

    # Comprobación estricta de no mutación de entradas.
    assert _sha(geometria) == sha_geo_in
    assert _sha(configuracion) == sha_cfg_in
    if sha_reglas_in is not None:
        assert _sha(reglas) == sha_reglas_in

    return _propuesta_base(
        caso=caso_cfg,
        datos_sinteticos=datos_sinteticos_res,
        huella_preparacion=prep["huella_preparacion"],
        inventario_nodos=inventario_nodos,
        inventario_frames=inventario_frames,
        propuestos_nodos=propuestos_nodos,
        propuestos_frames=propuestos_frames,
        trazabilidad_nodos=trazabilidad_nodos,
        reglas_sin_coincidencia=reglas_sin_coincidencia,
        pendientes=pendientes,
        conflictos=conflictos,
        errores=errores,
        reglas_declaradas=reglas is not None,
    )


def aplicar_politicas_malla(
    geometria: Any,
    configuracion: Any,
    reglas: Any,
) -> dict[str, Any]:
    """Aplica reglas explícitas completas sobre una COPIA en borrador de `configuracion`.

    Nunca modifica `geometria`, `configuracion` ni `reglas`. Nunca conserva ni genera aprobaciones
    (`revision = {"estado": "borrador", "aprobacion": None}`) ni maquilla otros campos incompletos.
    Lanza `ErrorPoliticaMalla` si existen errores, conflictos o pendientes.
    """
    if reglas is None:
        propuesta = previsualizar_politicas_malla(geometria, configuracion, reglas=None)
        raise ErrorPoliticaMalla(
            "Se requiere un documento explícito de reglas para aplicar políticas de malla.",
            propuesta=propuesta,
        )

    propuesta = previsualizar_politicas_malla(geometria, configuracion, reglas)
    if not propuesta["listo_para_aplicar"]:
        resumen = propuesta["resumen"]
        partes: list[str] = []
        if resumen["errores"]:
            partes.append(f"{resumen['errores']} error(es): " + "; ".join(e["mensaje"] for e in propuesta["errores"][:3]))
        if resumen["conflictos"]:
            partes.append(
                f"{resumen['conflictos']} conflicto(s): " + "; ".join(c["mensaje"] for c in propuesta["conflictos"][:3])
            )
        if resumen["pendientes"]:
            partes.append(f"{resumen['pendientes']} pendiente(s) sin regla explícita")
        detalle = " | ".join(partes) if partes else "propuesta no apta para aplicar"
        raise ErrorPoliticaMalla(f"No se aplican políticas incompletas o en conflicto ({detalle}).", propuesta=propuesta)

    sha_geo_in = _sha(geometria)
    sha_cfg_in = _sha(configuracion)
    sha_reglas_in = _sha(reglas)

    copia = copy.deepcopy(configuracion)
    copia["nodos_derivados"] = copy.deepcopy(propuesta["nodos_derivados_propuestos"])
    copia["subdivision_frames"] = copy.deepcopy(propuesta["subdivision_frames_propuesta"])
    # Toda modificación devuelve copia en borrador; jamás hereda ni registra aprobaciones.
    copia["revision"] = {"estado": "borrador", "aprobacion": None}

    assert _sha(geometria) == sha_geo_in
    assert _sha(configuracion) == sha_cfg_in
    assert _sha(reglas) == sha_reglas_in
    return copia
