"""Preparación reproducible de la malla derivada para la configuración 0.4 (sin ETABS, pura).

geometría 0.3 + configuración → particiones de TODOS los hosts asignados (con todos sus huecos) → compatibilidad en
bordes DECLARADOS (`conexiones_borde`) → triángulos que conservan todos los nodos de borde → nombres CSI
deterministas, nodos derivados, triángulos por host y subdivisiones de frame requeridas.

No asigna apoyos, diafragmas ni cargas a nodos derivados: lista lo que la configuración debe declarar
(`nodos_derivados`, `subdivision_frames`). Ningún vínculo por proximidad: un frame solo se subdivide en nodos de
malla situados sobre su segmento bajo el criterio computacional existente, y el resultado exige declaración.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from fractions import Fraction
from typing import Any

from . import compatibilidad_particiones as cp
from . import cortes_superficies as cs
from . import particion_superficies as ps
from . import triangulacion_particiones as tp
from .cache_malla_pura import reutilizar_malla_pura

CONTRATO = "draft2model.preparacion_malla"
VERSION = "0.1.0"
ESTRATEGIA = "particion_franjas_triangulada_v1"


class ErrorMalla(ValueError):
    """Preparación no reproducible o no admitida; no se publica parcialmente."""


def _canon(x: Any) -> bytes:
    return json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(x: Any) -> str:
    return hashlib.sha256(_canon(x)).hexdigest()


def nombre_nodo(ident: str) -> str:
    m = re.fullmatch(r"(.+)#n(\d+)", ident)
    if not m:
        raise ErrorMalla(f"Nodo derivado con identificador no reconocido: {ident}")
    return f"MN_{m[1]}_{m[2]}"


def nombre_triangulo(ident: str) -> str:
    m = re.fullmatch(r"(.+)#c(\d+)#t(\d+)(?:#corte(\d+))?", ident)
    if not m:
        raise ErrorMalla(f"Triángulo con identificador no reconocido: {ident}")
    return f"MA_{m[1]}_{m[2]}_{m[3]}" + (f"_K{m[4]}" if m[4] else "")


def nombre_nodo_corte(ident: str) -> str:
    m = re.fullmatch(r"CORTE#(\d+)", ident)
    if not m:
        raise ErrorMalla(f"Nodo de corte con identificador no reconocido: {ident}")
    return f"MC_{m[1]}"


def nombre_subframe(frame: str, k: int) -> str:
    return f"{frame}_S{k}"


def coordenadas_puntos(configuracion: dict, vg: Any) -> dict:
    g = vg.geometria_m
    niveles = {n["id"]: n["cota"] for n in g["niveles"]}
    nodos = {n["id"]: n for n in g["nodos"]}
    vertices = {v["id"]: v for v in g["vertices"]}
    salida = {}
    for p in configuracion["puntos"]:
        if "vertice_geometria" in p:
            v = vertices[p["vertice_geometria"]]
            salida[p["id"]] = [v["x"], v["y"], v["z"]]
        else:
            n = nodos[p["nodo_geometria"]]
            salida[p["id"]] = [n["x"], n["y"], niveles[p["nivel_geometria"]]]
    return salida


def _ids_configuracion(c: dict) -> set:
    ids = set()
    for clave in ("puntos", "frames", "secciones", "materiales", "patrones", "casos", "combinaciones", "diafragmas", "espectros"):
        ids |= {x["id"] for x in c.get(clave, []) if isinstance(x, dict) and isinstance(x.get("id"), str)}
    return ids


@reutilizar_malla_pura   # función pura: misma salida para el mismo JSON completo (cache LRU acotada, cache_malla_pura)
def preparar_malla(geometria: Any, configuracion: Any) -> dict:
    """Preparación determinista; ErrorMalla si no se puede reproducir íntegramente."""
    if not isinstance(geometria, dict) or not isinstance(configuracion, dict):
        raise ErrorMalla("Geometría y configuración deben ser objetos.")
    try:
        contexto = ps._ContextoGeometria(geometria)
        _, vg = contexto.verificar(geometria)
    except ps.ErrorParticion as exc:
        raise ErrorMalla(f"Malla no reproducible: {exc}") from None
    if not vg.consistente or vg.version_contrato != "0.3.0":
        raise ErrorMalla("Se requiere geometría 0.3.0 consistente.")
    try:
        hosts = sorted(a["objetivo"] for a in configuracion["asignaciones_superficies"])
        seccion_host = {a["objetivo"]: a["seccion"] for a in configuracion["asignaciones_superficies"]}
        conexiones = configuracion["conexiones_borde"]
        niveles = [c["z_m"] for c in configuracion["cortes_nivel"]]
        punto_de_vertice = {p["vertice_geometria"]: p["id"] for p in configuracion["puntos"] if "vertice_geometria" in p}
        punto_de_vertice.update({x["vertice_geometria"]: x["punto"] for x in configuracion["vertices_compartidos"]})
        coords_config = coordenadas_puntos(configuracion, vg)
    except (KeyError, TypeError) as exc:
        raise ErrorMalla("Configuración sin los campos necesarios para preparar la malla.") from exc
    if not hosts:
        raise ErrorMalla("La configuración no asigna superficies que mallar.")
    try:
        partes = [ps.particionar_superficie(geometria, h, _contexto=contexto) for h in hosts]
        compat = cp.compatibilizar_particiones(geometria, partes, conexiones, _contexto=contexto)
        tri = tp.triangular_compatibilidad(geometria, partes, conexiones, compat, _contexto=contexto)
        contexto.verificar(geometria)
    except (ps.ErrorParticion, cp.ErrorCompatibilidad, tp.ErrorTriangulacion) as exc:
        raise ErrorMalla(f"Malla no reproducible: {exc}") from None
    # -- cortes por niveles Z explícitos (adenda 186): después de compatibilidad/triangulación y antes de
    # nombres CSI y políticas. Conserva ambos lados (nunca elimina material seco) y no crea pisos.
    nodos_m, tris_m, corte = tri["nodos"], tri["triangulos"], None
    if niveles:
        try:
            corte = cs.cortar_malla_por_niveles(nodos_m, tris_m, niveles)
        except cs.ErrorCorte as exc:
            raise ErrorMalla(f"Corte por niveles no reproducible: {exc}") from None
        nodos_m, tris_m = corte["nodos"], corte["triangulos"]
    # -- nombres CSI de nodos --
    csi, origen_nodo = {}, {}
    for n in nodos_m:
        if "fuentes" not in n:  # nodo calculado por el corte, compartido por aristas
            nombre = nombre_nodo_corte(n["id"])
            origen_nodo[nombre] = {"tipo": "derivado", "nodo_malla": n["id"], "alias": [], "trazas": [n["traza"]], "insertado_en": []}
            csi[n["id"]] = nombre
            continue
        vertices = sorted({f["traza"]["vertice"] for f in n["fuentes"] if f["traza"]["tipo"] == "original"})
        if vertices:
            puntos = {punto_de_vertice.get(v) for v in vertices}
            if None in puntos or len(puntos) != 1:
                raise ErrorMalla(f"Nodo {n['id']}: vértices {vertices} sin un único punto explícito en la configuración.")
            nombre = puntos.pop()
            if coords_config[nombre] != n["xyz_m"]:
                raise ErrorMalla(f"Nodo {n['id']}: coordenadas distintas del punto {nombre} de la configuración.")
            origen_nodo[nombre] = {"tipo": "punto_configuracion", "vertices_geometria": vertices}
        else:
            nombre = nombre_nodo(n["id"])
            origen_nodo[nombre] = {"tipo": "derivado", "nodo_malla": n["id"], "alias": n["alias"],
                                   "trazas": [f["traza"] for f in n["fuentes"]], "insertado_en": n["insertado_en"]}
        csi[n["id"]] = nombre
    if len(set(csi.values())) != len(csi):
        raise ErrorMalla("Dos nodos de malla reciben el mismo nombre CSI.")
    reservados = _ids_configuracion(configuracion)
    derivados = sorted(v for k, v in csi.items() if origen_nodo[v]["tipo"] == "derivado")
    if set(derivados) & reservados:
        raise ErrorMalla("Nombre de nodo derivado en colisión con un identificador de la configuración.")
    xyz = {csi[n["id"]]: n["xyz_m"] for n in nodos_m}
    ocupadas = {tuple(v): k for k, v in coords_config.items()}
    for nombre in derivados:
        if tuple(xyz[nombre]) in ocupadas:
            raise ErrorMalla(f"Nodo derivado {nombre} coincide con el punto {ocupadas[tuple(xyz[nombre])]}; "
                             "no se fusiona por proximidad: declare el vértice en la geometría.")
    # -- triángulos --
    normales = {h: vg.derivados_m["superficies"][h]["normal_unitaria"] for h in hosts}
    triangulos = []
    for t in tris_m:
        nombre = nombre_triangulo(t["id"])
        q = [xyz[csi[n]] for n in t["nodos"]]
        u = [q[1][k] - q[0][k] for k in range(3)]
        w = [q[2][k] - q[0][k] for k in range(3)]
        cruz = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
        area = math.fsum(c * nk for c, nk in zip(cruz, normales[t["superficie_origen"]])) / 2
        if not area > 0:
            raise ErrorMalla(f"Triángulo {t['id']} invertido o degenerado respecto de la normal del host.")
        triangulos.append({"csi": nombre, "id_malla": t["id"], "host": t["superficie_origen"], "celda": t["celda_origen"],
                           "seccion": seccion_host[t["superficie_origen"]], "nodos": [csi[n] for n in t["nodos"]],
                           "area_m2": area, "centroide_m": [math.fsum(p[k] for p in q) / 3 for k in range(3)],
                           **({"triangulo_fuente": t["triangulo_fuente"]} if "triangulo_fuente" in t else {})})
    nombres_tri = [t["csi"] for t in triangulos]
    if len(set(nombres_tri)) != len(nombres_tri) or set(nombres_tri) & (reservados | set(xyz)):
        raise ErrorMalla("Nombres CSI de triángulos repetidos o en colisión.")
    # -- frames sobre nodos de malla (criterio computacional existente, aritmética exacta) --
    requeridas = []
    for frame in sorted(configuracion["frames"], key=lambda f: f["id"]):
        a, b = coords_config[frame["inicio"]], coords_config[frame["fin"]]
        fa, fb = [Fraction(x) for x in a], [Fraction(x) for x in b]
        d = [y - x for x, y in zip(fa, fb)]
        dd = sum(x * x for x in d)
        largo = math.dist(a, b)
        eps = max(1e-12, 64 * math.ulp(max(abs(x) for x in a + b)) / largo)
        umbral2 = (Fraction(eps) * Fraction(largo)) ** 2
        interiores = []
        for nombre, p in xyz.items():
            fp = [Fraction(x) for x in p]
            v = [x - y for x, y in zip(fp, fa)]
            t = sum(x * y for x, y in zip(v, d)) / dd
            if not 0 < t < 1:
                continue
            cr = [v[1] * d[2] - v[2] * d[1], v[2] * d[0] - v[0] * d[2], v[0] * d[1] - v[1] * d[0]]
            if sum(x * x for x in cr) / dd <= umbral2:
                interiores.append((t, nombre))
        interiores.sort()
        minimo = Fraction(eps)
        ts = [Fraction(0)] + [t for t, _ in interiores] + [Fraction(1)]
        if any(t1 - t0 <= minimo for t0, t1 in zip(ts, ts[1:])):
            raise ErrorMalla(f"Frame {frame['id']}: nodos de malla más cercanos que el criterio a otro nodo; caso ambiguo.")
        if interiores:
            requeridas.append({"frame": frame["id"], "nodos": [frame["inicio"]] + [n for _, n in interiores] + [frame["fin"]],
                               "subframes": [nombre_subframe(frame["id"], k) for k in range(1, len(interiores) + 2)]})
    subnombres = [s for r in requeridas for s in r["subframes"]]
    if set(subnombres) & (reservados | set(xyz) | set(nombres_tri)):
        raise ErrorMalla("Nombre de subframe en colisión con otro identificador.")
    hosts_info = {h: {"seccion": seccion_host[h], "normal_unitaria": normales[h],
                      "area_neta_m2": vg.derivados_m["superficies"][h]["area_neta_m2"],
                      "aberturas": vg.derivados_m["superficies"][h]["aberturas_ids"],
                      "triangulos": [t["csi"] for t in triangulos if t["host"] == h]} for h in hosts}
    datos = {
        "contrato": CONTRATO, "version_contrato": VERSION, "estrategia": ESTRATEGIA, "ejecutable": False,
        "origen": {"sha256_geometria_canonica": cp._sha(geometria), "huella_contenido_geometria": vg.huella_contenido,
                   "huella_conexiones": conexiones["declaracion"]["huella_conexiones"],
                   "huella_compatibilidad": compat["huella_compatibilidad"], "huella_triangulacion": tri["huella_triangulacion"],
                   "particiones": {p["superficie"]["id"]: p["huella_particion"] for p in partes},
                   "huella_corte": corte["huella_corte"] if corte else None},
        "cortes_nivel": {"niveles_z_m": sorted(niveles), "declaraciones": copy.deepcopy(configuracion["cortes_nivel"]),
                         "nodos_corte": sorted(csi[n["id"]] for n in nodos_m if "fuentes" not in n),
                         "no_crea_pisos": True, "conserva_ambos_lados": True} if corte else None,
        "hosts": hosts_info,
        "nodos": [{"csi": k, "xyz_m": xyz[k], **origen_nodo[k]} for k in sorted(xyz)],
        "triangulos": triangulos,
        "nodos_derivados": derivados,
        "plantilla_nodos_derivados": [{"nodo": n, "xyz_m": list(xyz[n]), "restricciones": None, "diafragma": None, "motivo_sin_diafragma": None,
                                       "fuente": None} for n in derivados],
        "frames_subdivision_requerida": requeridas,
        "conexiones": copy.deepcopy(compat["conexiones"]),
        "bordes_no_conectados": copy.deepcopy(compat["bordes_no_conectados"]),
    }
    datos["huella_preparacion"] = _sha(datos)
    try:
        contexto.verificar(geometria)
    except ps.ErrorParticion as exc:
        raise ErrorMalla(f"Malla no reproducible: {exc}") from None
    return datos
