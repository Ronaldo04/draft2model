"""Conformidad entre particiones de superficies distintas unidas por conexiones de borde EXPLÍCITAS.

API pura: `compatibilizar_particiones(geometria, particiones, conexiones) -> dict`;
errores `ErrorCompatibilidad(ValueError)`. Sin ETABS, red ni archivos; no ejecutable; sin aprobación de ingeniería.

- `particiones`: resultados completos de `particion_superficies.particionar_superficie` (contrato 0.1.0) para
  hosts del MISMO JSON geométrico. Se reproducen contra la fuente: una copia alterada, omitida o duplicada se rechaza.
- `conexiones`: documento `draft2model.conexiones_borde` 0.1.0 (campos exactos en docs/COMPATIBILIDAD_PARTICIONES.md),
  ligado a la geometría por SHA canónico y huella, con fuentes y declaración (identidad declarada no verificada).
- Solo se unen nodos situados sobre segmentos DECLARADOS y geométricamente coincidentes (colineales con longitud
  positiva de solape) bajo el criterio computacional existente: epsilon = max(1e-12, 64·ulp(coordenada máxima)/escala),
  evaluado en aritmética racional exacta. No hay unión por proximidad ni por redondeo: dos puntos distintos de un
  mismo segmento compartido más cercanos que el criterio son ambiguos y se rechazan.
- Los cortes se propagan hasta un punto fijo a todas las cadenas y celdas implicadas (incluidas cadenas de varios
  hosts). Un vértice fuente común a dos superficies es el mismo nodo por identidad de fuente, no por proximidad.

Tras compatibilizar se revalidan incidencias, cadenas y áreas por superficie y la igualdad de las cadenas en cada
conexión; cualquier fallo rechaza el resultado completo. No acredita frames, apoyos, diafragmas, ejes, material,
cargas, masa, calidad de malla ni rigidez.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from datetime import date
from fractions import Fraction
from typing import Any

from . import particion_superficies as ps
from .validacion_geometria import validar_geometria

CONTRATO = "draft2model.compatibilidad_particiones"
VERSION = "0.1.0"
CONTRATO_CONEXIONES = "draft2model.conexiones_borde"
VERSION_CONEXIONES = "0.1.0"
PATRON_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
SHA = re.compile(r"[0-9a-f]{64}")
PENDIENTES = [
    "Barras/frames sobre bordes y nodos compartidos: conectar en el siguiente incremento con `nodos` y `conexiones`.",
    "Apoyos, diafragmas, ejes locales, material, cargas y masa de las piezas compatibilizadas.",
    "Calidad de malla (nodos colineales, franjas alargadas) con criterios declarados; no evaluada aquí.",
    "Transporte ETABS de piezas y nodos compartidos, guardado, reapertura y relectura independiente.",
]


class ErrorCompatibilidad(ValueError):
    """Entrada no admitida o compatibilidad no verificable; nunca se publica un resultado parcial."""


def _canonico(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(data: Any) -> str:
    return hashlib.sha256(_canonico(data)).hexdigest()


def huella_conexiones(documento: dict) -> str:
    """SHA del documento de conexiones completo excepto `declaracion`."""
    return _sha({k: v for k, v in documento.items() if k != "declaracion"})


def _exacto(objeto, claves, ruta):
    if not isinstance(objeto, dict) or set(objeto) != set(claves):
        raise ErrorCompatibilidad(f"{ruta}: se requieren exactamente los campos {', '.join(sorted(claves))}.")
    return objeto


def _texto(valor, ruta):
    if not isinstance(valor, str) or not valor.strip():
        raise ErrorCompatibilidad(f"{ruta}: se requiere texto no vacío.")
    return valor


def _ident(valor, ruta):
    if not isinstance(valor, str) or not PATRON_ID.fullmatch(valor):
        raise ErrorCompatibilidad(f"{ruta}: identificador inválido.")
    return valor


def _validar_documento(doc, sha_geo, huella_geo):
    _exacto(doc, ("contrato", "version_contrato", "id", "geometria", "conexiones", "fuentes", "declaracion"), "conexiones")
    if doc["contrato"] != CONTRATO_CONEXIONES or doc["version_contrato"] != VERSION_CONEXIONES:
        raise ErrorCompatibilidad("Documento de conexiones de contrato o versión no admitidos.")
    _ident(doc["id"], "conexiones.id")
    _exacto(doc["geometria"], ("sha256_geometria_canonica", "huella_contenido"), "conexiones.geometria")
    if doc["geometria"]["sha256_geometria_canonica"] != sha_geo or doc["geometria"]["huella_contenido"] != huella_geo:
        raise ErrorCompatibilidad("El documento de conexiones no está ligado a esta geometría.")
    if not isinstance(doc["fuentes"], list) or not doc["fuentes"]:
        raise ErrorCompatibilidad("conexiones.fuentes: se requiere al menos una fuente.")
    fuentes = {}
    for i, f in enumerate(doc["fuentes"]):
        _exacto(f, ("id", "descripcion", "referencia", "sha256"), f"conexiones.fuentes[{i}]")
        _ident(f["id"], f"conexiones.fuentes[{i}].id")
        _texto(f["descripcion"], f"conexiones.fuentes[{i}].descripcion")
        _texto(f["referencia"], f"conexiones.fuentes[{i}].referencia")
        if not isinstance(f["sha256"], str) or not SHA.fullmatch(f["sha256"]):
            raise ErrorCompatibilidad(f"conexiones.fuentes[{i}].sha256 inválido.")
        if f["id"] in fuentes:
            raise ErrorCompatibilidad("conexiones.fuentes: identificador repetido.")
        fuentes[f["id"]] = f
    if not isinstance(doc["conexiones"], list):
        raise ErrorCompatibilidad("conexiones.conexiones: se requiere lista explícita (puede estar vacía).")
    vistos, caras = set(), set()
    for i, c in enumerate(doc["conexiones"]):
        ruta = f"conexiones.conexiones[{i}]"
        _exacto(c, ("id", "a", "b", "fuente"), ruta)
        _ident(c["id"], ruta + ".id")
        if c["id"] in vistos:
            raise ErrorCompatibilidad(ruta + ": identificador repetido.")
        vistos.add(c["id"])
        if c["fuente"] not in fuentes:
            raise ErrorCompatibilidad(ruta + ".fuente: referencia inexistente.")
        for lado in ("a", "b"):
            _exacto(c[lado], ("superficie", "desde", "hasta"), f"{ruta}.{lado}")
            for k in ("superficie", "desde", "hasta"):
                _ident(c[lado][k], f"{ruta}.{lado}.{k}")
        if c["a"]["superficie"] == c["b"]["superficie"]:
            raise ErrorCompatibilidad(ruta + ": una conexión une dos superficies distintas.")
        cara = frozenset(((c["a"]["superficie"], frozenset((c["a"]["desde"], c["a"]["hasta"]))),
                          (c["b"]["superficie"], frozenset((c["b"]["desde"], c["b"]["hasta"])))))
        if cara in caras:
            raise ErrorCompatibilidad(ruta + ": par de aristas repetido.")
        caras.add(cara)
    decl = _exacto(doc["declaracion"], ("declarado_por", "fecha", "identidad", "alcance", "huella_conexiones"), "conexiones.declaracion")
    _texto(decl["declarado_por"], "declaracion.declarado_por")
    _texto(decl["alcance"], "declaracion.alcance")
    try:
        if not isinstance(decl["fecha"], str) or len(decl["fecha"]) != 10:
            raise ValueError
        date.fromisoformat(decl["fecha"])
    except ValueError:
        raise ErrorCompatibilidad("declaracion.fecha: fecha ISO inválida.") from None
    if decl["identidad"] != "declarada_no_verificada":
        raise ErrorCompatibilidad("declaracion.identidad debe ser declarada_no_verificada.")
    if decl["huella_conexiones"] != huella_conexiones(doc):
        raise ErrorCompatibilidad("La declaración no corresponde al contenido actual del documento de conexiones.")


def _f3(p):
    return tuple(Fraction(x) for x in p)


def _menos(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _cruz(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def compatibilizar_particiones(geometria: Any, particiones: Any, conexiones: Any, *, _contexto=None) -> dict:
    """Une particiones solo en bordes declarados y coincidentes; verifica y publica o rechaza todo."""
    if not isinstance(geometria, dict) or not isinstance(particiones, list) or not particiones:
        raise ErrorCompatibilidad("Se requieren geometría (objeto) y una lista no vacía de particiones.")
    if _contexto is None:
        try:
            sha_geo = _sha(geometria)
        except (TypeError, ValueError) as exc:
            raise ErrorCompatibilidad("Geometría no serializable como JSON estricto.") from exc
        vg = validar_geometria(copy.deepcopy(geometria))
    else:
        try:
            sha_geo, vg = _contexto.verificar(geometria)
        except ps.ErrorParticion as exc:
            raise ErrorCompatibilidad(str(exc)) from None
    if not vg.consistente:
        raise ErrorCompatibilidad("Geometría inconsistente.")
    try:
        _canonico(conexiones)
        _canonico(particiones)
    except (TypeError, ValueError) as exc:
        raise ErrorCompatibilidad("Particiones o conexiones no serializables como JSON estricto (p. ej. NaN).") from exc
    _validar_documento(conexiones, sha_geo, vg.huella_contenido)
    # -- particiones reproducidas contra la fuente --
    por_sup = {}
    for i, p in enumerate(particiones):
        if not isinstance(p, dict) or not isinstance(p.get("superficie"), dict) or not isinstance(p["superficie"].get("id"), str):
            raise ErrorCompatibilidad(f"particiones[{i}] no es un resultado de partición.")
        sid = p["superficie"]["id"]
        if sid in por_sup:
            raise ErrorCompatibilidad(f"Partición duplicada para {sid}.")
        try:
            reproducida = (ps.particionar_superficie(geometria, sid) if _contexto is None
                          else ps.particionar_superficie(geometria, sid, _contexto=_contexto))
        except ps.ErrorParticion as exc:
            raise ErrorCompatibilidad(f"La partición de {sid} no se reproduce: {exc}") from None
        if _canonico(reproducida) != _canonico(p):
            raise ErrorCompatibilidad(f"La partición de {sid} no coincide con su reproducción desde la fuente (alterada o de otra fuente).")
        por_sup[sid] = copy.deepcopy(p)
    g = vg.geometria_m
    contornos = {s["id"]: s["vertices"] for s in g["superficies"]}
    xyz = {v["id"]: (v["x"], v["y"], v["z"]) for v in g["vertices"]}
    for c in conexiones["conexiones"]:
        for lado in ("a", "b"):
            s = c[lado]["superficie"]
            if s not in contornos:
                raise ErrorCompatibilidad(f"Conexión {c['id']}: superficie {s} inexistente.")
            if s not in por_sup:
                raise ErrorCompatibilidad(f"Conexión {c['id']}: falta la partición de {s}.")

    # -- estado mutable por superficie --
    nodos = {}  # id global -> {"xyz": [...], "fuentes": [...], "insertado_en": [...]}
    alias = {}

    def raiz(n):
        while n in alias:
            n = alias[n]
        return n
    for sid, p in sorted(por_sup.items()):
        for n in p["nodos"]:
            previo = nodos.get(n["id"])
            if previo is None:
                nodos[n["id"]] = {"xyz": list(n["xyz_m"]), "fuentes": [{"particion": sid, "nodo": n["id"], "traza": n["traza"]}], "insertado_en": []}
            elif previo["xyz"] != list(n["xyz_m"]):
                raise ErrorCompatibilidad(f"Nodo {n['id']} con coordenadas distintas en dos particiones.")
            else:  # vértice fuente común: mismo nodo por identidad de fuente
                previo["fuentes"].append({"particion": sid, "nodo": n["id"], "traza": n["traza"]})
    celdas = {sid: [dict(cl, nodos=list(cl["nodos"])) for cl in p["celdas"]] for sid, p in por_sup.items()}
    cadenas = {sid: {(cd["contorno"], cd["arista"]): dict(cd, nodos=list(cd["nodos"])) for cd in p["cadenas_contorno"]}
               for sid, p in por_sup.items()}

    def arista_de(c, lado):
        s, a, b = c[lado]["superficie"], c[lado]["desde"], c[lado]["hasta"]
        ids = contornos[s]
        for i in range(len(ids)):
            u, w = ids[i], ids[(i + 1) % len(ids)]
            if (u, w) == (a, b):
                return s, i, "directa"
            if (u, w) == (b, a):
                return s, i, "inversa"
        raise ErrorCompatibilidad(f"Conexión {c['id']}: {a}-{b} no es una arista del contorno exterior de {s}.")

    # -- geometría de cada conexión (exacta) --
    geom = []
    for c in sorted(conexiones["conexiones"], key=lambda c: c["id"]):
        sa, ia, oa = arista_de(c, "a")
        sb, ib, ob = arista_de(c, "b")
        a0, a1 = _f3(xyz[c["a"]["desde"]]), _f3(xyz[c["a"]["hasta"]])
        b0, b1 = _f3(xyz[c["b"]["desde"]]), _f3(xyz[c["b"]["hasta"]])
        d = _menos(a1, a0)
        dd = _dot(d, d)
        puntos = [xyz[v] for v in (c["a"]["desde"], c["a"]["hasta"], c["b"]["desde"], c["b"]["hasta"])]
        escala = max(math.dist(p, q) for p in puntos for q in puntos)
        eps = max(1e-12, 64 * math.ulp(max(abs(x) for p in puntos for x in p)) / escala)
        if not math.isfinite(eps) or eps > 1e-6:
            raise ErrorCompatibilidad(f"Conexión {c['id']}: coordenadas numéricamente inestables respecto de su extensión.")
        umbral2 = (Fraction(eps) * Fraction(escala)) ** 2

        def dist2(p):
            v = _cruz(_menos(p, a0), d)
            return _dot(v, v) / dd

        if dist2(b0) > umbral2 or dist2(b1) > umbral2:
            raise ErrorCompatibilidad(f"Conexión {c['id']}: las aristas no son colineales bajo el criterio declarado.")
        tb0, tb1 = _dot(_menos(b0, a0), d) / dd, _dot(_menos(b1, a0), d) / dd
        lo, hi = max(Fraction(0), min(tb0, tb1)), min(Fraction(1), max(tb0, tb1))
        longitud = float(hi - lo) * math.sqrt(float(dd))
        if hi <= lo or longitud <= eps * escala:
            raise ErrorCompatibilidad(f"Conexión {c['id']}: sin solape de longitud positiva (contacto puntual o disjuntas).")
        geom.append({"c": c, "sa": sa, "ia": ia, "oa": oa, "sb": sb, "ib": ib, "ob": ob, "a0": a0, "d": d, "dd": dd,
                     "lo": lo, "hi": hi, "umbral2": umbral2, "eps": eps, "escala": escala, "longitud": longitud,
                     "minimo_t": Fraction(eps) * Fraction(escala) / Fraction(math.sqrt(float(dd)))})

    def t_de(gm, nid):
        return _dot(_menos(_f3(nodos[nid]["xyz"]), gm["a0"]), gm["d"]) / gm["dd"]

    def insertar(sid, clave, nuevo, gm):
        """Inserta `nuevo` en la cadena (sid, clave) y en la celda que contiene el segmento cortado."""
        cad = cadenas[sid][clave]["nodos"]
        ts = [t_de(gm, n) for n in cad]
        tn = t_de(gm, nuevo)
        creciente = ts[-1] > ts[0]
        for k in range(len(cad) - 1):
            lo_, hi_ = (ts[k], ts[k + 1]) if creciente else (ts[k + 1], ts[k])
            if lo_ < tn < hi_:
                u, w = cad[k], cad[k + 1]
                cad.insert(k + 1, nuevo)
                for cl in celdas[sid]:
                    ns = cl["nodos"]
                    for j in range(len(ns)):
                        if {ns[j], ns[(j + 1) % len(ns)]} == {u, w}:
                            ns.insert(j + 1, nuevo)
                            cl["tipo"] = "convexa"
                            nodos[nuevo]["insertado_en"].append({"particion": sid, "contorno": clave[0], "arista": clave[1],
                                                                 "conexion": gm["c"]["id"], "entre": [u, w]})
                            return True
                raise ErrorCompatibilidad(f"Segmento {u}-{w} de {sid} sin celda de frontera.")
        raise ErrorCompatibilidad(f"No se pudo situar {nuevo} en la cadena {clave} de {sid}.")

    def unir(rep, otro, gm):
        if rep == otro:
            return
        if math.dist(nodos[rep]["xyz"], nodos[otro]["xyz"]) > gm["eps"] * gm["escala"]:
            raise ErrorCompatibilidad(f"Conexión {gm['c']['id']}: nodos {rep} y {otro} en el mismo parámetro con XYZ distintos.")
        alias[otro] = rep
        nodos[rep]["fuentes"].extend(nodos[otro]["fuentes"])
        nodos[rep]["insertado_en"].extend(nodos[otro]["insertado_en"])
        nodos[rep].setdefault("alias", []).append(otro)
        del nodos[otro]
        for sid in celdas:
            for cl in celdas[sid]:
                cl["nodos"] = [rep if n == otro else n for n in cl["nodos"]]
            for cd in cadenas[sid].values():
                cd["nodos"] = [rep if n == otro else n for n in cd["nodos"]]

    # -- punto fijo: propagar todos los cortes en todos los solapes declarados --
    for _ in range(10000):
        cambio = False
        for gm in geom:
            lados = [(gm["sa"], ("superficie:" + gm["sa"], gm["ia"])), (gm["sb"], ("superficie:" + gm["sb"], gm["ib"]))]
            por_t = {}
            for sid, clave in lados:
                for n in cadenas[sid][clave]["nodos"]:
                    t = t_de(gm, n)
                    if gm["lo"] <= t <= gm["hi"]:
                        por_t.setdefault(t, set()).add(n)
            ts = sorted(por_t)
            for t0, t1 in zip(ts, ts[1:]):
                if t1 - t0 <= gm["minimo_t"]:
                    raise ErrorCompatibilidad(f"Conexión {gm['c']['id']}: puntos distintos más cercanos que el criterio; caso ambiguo.")
            for t in ts:
                grupo = sorted(por_t[t])
                rep = grupo[0]
                for otro in grupo[1:]:
                    if raiz(otro) != rep:
                        unir(rep, otro, gm)
                        cambio = True
                for sid, clave in lados:
                    if rep not in cadenas[sid][clave]["nodos"]:
                        insertar(sid, clave, rep, gm)
                        cambio = True
            if cambio:
                break
        if not cambio:
            break
    else:
        raise ErrorCompatibilidad("La propagación de cortes no converge.")
    return _verificar_y_publicar(geometria, sha_geo, vg, conexiones, por_sup, nodos, celdas, cadenas, geom, t_de, contornos, xyz)


def _verificar_y_publicar(geometria, sha_geo, vg, conexiones, por_sup, nodos, celdas, cadenas, geom, t_de, contornos, xyz):
    problemas = []
    for sid, cls in celdas.items():
        dirigidas = {}
        for cl in cls:
            ns = cl["nodos"]
            if len(set(ns)) != len(ns):
                problemas.append(f"{cl['id']}: nodo repetido.")
            for i in range(len(ns)):
                dirigidas[(ns[i], ns[(i + 1) % len(ns)])] = dirigidas.get((ns[i], ns[(i + 1) % len(ns)]), 0) + 1
        if any(v != 1 for v in dirigidas.values()):
            problemas.append(f"{sid}: arista dirigida repetida.")
        incid = {}
        for a, b in dirigidas:
            incid.setdefault(frozenset((a, b)), 0)
            incid[frozenset((a, b))] += 1
        frontera = {k for k, v in incid.items() if v == 1}
        if any(v > 2 for v in incid.values()):
            problemas.append(f"{sid}: arista con más de dos incidencias.")
        segmentos = set()
        for cd in cadenas[sid].values():
            segmentos |= {frozenset((u, w)) for u, w in zip(cd["nodos"], cd["nodos"][1:])}
        if segmentos != frontera:
            problemas.append(f"{sid}: la frontera no coincide con las cadenas de contorno.")
        # Áreas conservadas (inserciones colineales) y orientación según la normal del host.
        normal = por_sup[sid]["superficie"]["normal_unitaria"]
        for cl, orig in zip(cls, por_sup[sid]["celdas"]):
            q = [nodos[n]["xyz"] for n in cl["nodos"]]
            nw = [math.fsum((q[i][(k + 1) % 3] - q[(i + 1) % len(q)][(k + 1) % 3]) * (q[i][(k + 2) % 3] + q[(i + 1) % len(q)][(k + 2) % 3])
                            for i in range(len(q))) for k in range(3)]
            area = math.fsum(x * y for x, y in zip(nw, normal)) / 2
            if not area > 0 or abs(area - orig["area_m2"]) > 1e-9 * max(1.0, orig["area_m2"]):
                problemas.append(f"{cl['id']}: área u orientación alteradas por la compatibilización.")
    salida_conexiones = []
    for gm in geom:
        c = gm["c"]
        listas = []
        for sid, i in ((gm["sa"], gm["ia"]), (gm["sb"], gm["ib"])):
            cad = cadenas[sid][("superficie:" + sid, i)]["nodos"]
            dentro = [n for n in cad if gm["lo"] <= t_de(gm, n) <= gm["hi"]]
            listas.append(sorted(dentro, key=lambda n: t_de(gm, n)))
        if listas[0] != listas[1] or len(listas[0]) < 2:
            problemas.append(f"Conexión {c['id']}: las cadenas no comparten los mismos nodos en el solape.")
        salida_conexiones.append({"id": c["id"], "fuente": c["fuente"],
                                  "a": dict(c["a"], arista_indice=gm["ia"], orientacion=gm["oa"]),
                                  "b": dict(c["b"], arista_indice=gm["ib"], orientacion=gm["ob"]),
                                  "solape": {"inicio": listas[0][0] if listas[0] else None, "fin": listas[0][-1] if listas[0] else None,
                                             "t_a": [f"{gm['lo'].numerator}/{gm['lo'].denominator}", f"{gm['hi'].numerator}/{gm['hi'].denominator}"],
                                             "longitud_m": gm["longitud"]},
                                  "nodos_compartidos": listas[0],
                                  "criterio_coincidencia": {"epsilon_relativo": gm["eps"], "escala_m": gm["escala"]}})
    if problemas:
        raise ErrorCompatibilidad("Compatibilidad no verificable; no se publica: " + " | ".join(sorted(set(problemas)))[:2000])
    # Bordes no conectados: tramos de aristas exteriores sin conexión y todas las aristas de huecos.
    libres = []
    for sid in sorted(por_sup):
        ids = contornos[sid]
        for i in range(len(ids)):
            cubiertos = []
            for gm in geom:
                for lado_s, lado_i, lado in ((gm["sa"], gm["ia"], "a"), (gm["sb"], gm["ib"], "b")):
                    if (lado_s, lado_i) == (sid, i):
                        cubiertos.append(gm)
            cad = cadenas[sid][("superficie:" + sid, i)]["nodos"]
            tramos = []
            for u, w in zip(cad, cad[1:]):
                if not any(gm["lo"] <= t_de(gm, u) <= gm["hi"] and gm["lo"] <= t_de(gm, w) <= gm["hi"] for gm in cubiertos):
                    tramos.append([u, w])
            if tramos:
                libres.append({"superficie": sid, "contorno": "superficie:" + sid, "arista": i, "desde": ids[i],
                               "hasta": ids[(i + 1) % len(ids)], "segmentos_libres": tramos})
        for cd in sorted(cadenas[sid].values(), key=lambda x: (x["contorno"], x["arista"])):
            if cd["contorno"].startswith("hueco:"):
                libres.append({"superficie": sid, "contorno": cd["contorno"], "arista": cd["arista"], "desde": cd["desde"],
                               "hasta": cd["hasta"], "segmentos_libres": [[u, w] for u, w in zip(cd["nodos"], cd["nodos"][1:])]})
    datos = {
        "contrato": CONTRATO, "version_contrato": VERSION, "ejecutable": False, "aprueba_ingenieria": False,
        "aviso": "Conformidad geométrica entre particiones solo en bordes declarados; no es unión estructural verificada en ETABS.",
        "origen": {"sha256_geometria_canonica": sha_geo, "huella_contenido": vg.huella_contenido,
                   "conexiones": {"id": conexiones["id"], "sha256_documento": _sha(conexiones),
                                  "huella_conexiones": conexiones["declaracion"]["huella_conexiones"],
                                  "declaracion": copy.deepcopy(conexiones["declaracion"])},
                   "particiones": [{"superficie": s, "huella_particion": por_sup[s]["huella_particion"]} for s in sorted(por_sup)]},
        "nodos": [{"id": n, "xyz_m": nodos[n]["xyz"], "fuentes": nodos[n]["fuentes"], "alias": sorted(nodos[n].get("alias", [])),
                   "insertado_en": nodos[n]["insertado_en"]} for n in sorted(nodos)],
        "piezas": [{"superficie": s, "celdas": [{k: cl[k] for k in ("id", "nodos", "tipo", "franja", "area_m2", "pieza_de")} for cl in celdas[s]],
                    "cadenas_contorno": [{k: cd[k] for k in ("contorno", "arista", "desde", "hasta", "nodos")}
                                         for cd in sorted(cadenas[s].values(), key=lambda x: (x["contorno"] != "superficie:" + s, x["contorno"], x["arista"]))]}
                   for s in sorted(por_sup)],
        "conexiones": salida_conexiones,
        "bordes_no_conectados": libres,
        "comprobaciones": {"superficies": len(por_sup), "conexiones": len(geom), "nodos": len(nodos),
                           "nodos_insertados": sum(len(v["insertado_en"]) for v in nodos.values()),
                           "uniones_por_alias": sum(len(v.get("alias", [])) for v in nodos.values()),
                           "nodos_colgantes_en_conexiones": 0, "areas_conservadas": True},
        "limites": ["Sin declaración no hay unión: bordes coincidentes no declarados quedan en bordes_no_conectados.",
                    "Celdas con nodos colineales admitidas; la calidad de malla no se evalúa."],
        "pendientes": list(PENDIENTES),
    }
    datos["huella_compatibilidad"] = _sha(datos)
    return datos
