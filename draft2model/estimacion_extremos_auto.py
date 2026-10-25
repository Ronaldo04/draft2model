"""Estimación experimental de end length offsets Auto de vigas y del peso propio excluido (propuesta 321; destino draft2model/).

Estimación opcional: preserva el libro bruto y distingue reglas documentadas de observaciones experimentales.
- Entrada pública `estimar_desde_plan(plan, config)`: exige primero un plan real válido con
  `operaciones_etabs.validar_plan_por_version` (lista blanca, firmas, referencias y huella) y después aplica el núcleo.
- `nucleo(plan, config)`: análisis puro, usable en pruebas con mini-planes sintéticos.
- CLI: `python -m draft2model.estimacion_extremos_auto --plan P.json --configuracion C.json --salida NUEVA.json`.
Cero solver, cero llamadas remotas. No resta pesos a ningún libro: solo emite la estimación con su procedencia.

Perfil cubierto (empírico): ETABS 21.1.0; kN_m_C; secciones rectangulares; columnas verticales; ejes 0/90°; vigas alineadas;
tolerancia de unión 0,001 o 0,005 m. Procedencias:
  - documental: columnas inferiores, ayuda ETABS «End Length Offsets»;
  - experimental: proyección a la cara, muro, reglas de exceso y peso excluido (ensayos sintéticos 315/316 y conciliación 278).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

VERSION_NUCLEO = "0.3.1"
VERSION_CUBIERTA = "21.1.0"
UNIDADES_CUBIERTAS = ("kN_m_C",)
TOL_ENSAYADAS = (0.001, 0.005)
EPS = 1e-9

# Clasificación explícita de TODAS las escrituras admitidas por la lista blanca real (operaciones_etabs.FIRMAS) y de las
# ediciones de tabla. Toda escritura no clasificada es un problema del plan (no se acepta en silencio).
INTERPRETADAS = {"cPointObj.AddCartesian", "cFrameObj.AddByPoint", "cPropFrame.SetRectangle", "cPropMaterial.SetWeightAndMass",
                 "cFrameObj.SetInsertionPoint", "cAreaObj.AddByPoint", "cAreaObj.SetOpening", "cLoadPatterns.Add",
                 "cSapModel.SetPresentUnits", "cPropMaterial.SetMassSource_1", "cPropFrame.SetConcreteL"}
NEUTRAS = {   # no alteran geometría de frames, sección, material ni opciones de peso propio
    "cAnalyze.SetRunCaseFlag", "cAreaObj.SetLoadUniform", "cAreaObj.SetLocalAxes", "cCaseModalEigen.SetCase", "cCaseModalEigen.SetNumberModes",
    "cCaseModalEigen.SetParameters", "cCaseResponseSpectrum.SetCase", "cCaseResponseSpectrum.SetEccentricity", "cCaseResponseSpectrum.SetLoads",
    "cCaseResponseSpectrum.SetModalCase", "cCaseStaticLinear.SetCase", "cCaseStaticLinear.SetLoads", "cCombo.Add", "cCombo.SetCaseList",
    "cDiaphragm.SetDiaphragm", "cFile.Save", "cFrameObj.SetLoadDistributed", "cPointObj.SetDiaphragm", "cPointObj.SetLoadForce",
    "cPointObj.SetRestraint", "cPropArea.SetSlab", "cPropArea.SetSlabRibbed", "cPropArea.SetSlabWaffle", "cPropArea.SetWall",
    "cPropMaterial.SetMPIsotropic", "cPropMaterial.SetMaterial", "cStory.SetStories_2",
    "cDatabaseTables.SetTableForEditingArray", "cDatabaseTables.ApplyEditedTables"}
# Fuera de la lista blanca real, pero interpretadas como bloqueo si aparecen en un mini-plan del núcleo
BLOQUEO_SI_AFECTA = {"cFrameObj.SetEndLengthOffset", "cFrameObj.SetModifiers", "cFrameObj.SetSection", "cFrameObj.SetMass",
                     "cFrameObj.SetLocalAxes", "cFrameObj.SetLocalAxesAdvanced", "cPropFrame.SetModifiers"}
TABLAS_NEUTRAS = {"Functions - Response Spectrum - User Defined", "Load Case Definitions - Response Spectrum",
                  "Load Case Definitions - Damping - Modal", "Area Load Assignments - Non-uniform"}
ITEM_OBJETOS = {"enum": "eItemType", "nombre": "Objects", "valor": 0}


class ErrorDominio(ValueError):
    """Objeto que no es un plan o configuración analizable."""


def _finito(*xs):
    return all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in xs)


def _lectura(m):
    return isinstance(m, str) and "." in m and (m.split(".", 1)[1] == "Count" or m.split(".", 1)[1].startswith("Get"))


def validar_config(cfg):
    if not isinstance(cfg, dict):
        return ["configuración ausente o no es un objeto"]
    m = []
    if cfg.get("etabs_version") != VERSION_CUBIERTA:
        m.append(f"versión ETABS {cfg.get('etabs_version')!r} no cubierta (solo {VERSION_CUBIERTA})")
    if cfg.get("unidades") not in UNIDADES_CUBIERTAS:
        m.append(f"unidades {cfg.get('unidades')!r} no cubiertas")
    t = cfg.get("tolerancia_union_m")
    if not _finito(t) or t <= 0:
        m.append("tolerancia de unión ausente, no finita o no positiva")
    if cfg.get("procedencia_tolerancia") not in ("configuracion_verificada", "escenario_declarado"):
        m.append("procedencia de la tolerancia no válida")
    if "vigas" not in cfg:
        m.append("falta 'vigas' (None = todas las horizontales; lista = selección explícita)")
    elif cfg["vigas"] is not None and not isinstance(cfg["vigas"], list):
        m.append("'vigas' debe ser None o una lista")
    extra = set(cfg) - {"etabs_version", "unidades", "tolerancia_union_m", "procedencia_tolerancia", "vigas", "referencia_configuracion"}
    if extra:
        m.append(f"campos de configuración no admitidos: {sorted(extra)}")
    return m


def _ref(v, pref):
    if isinstance(v, dict) and set(v) == {"ref"} and isinstance(v["ref"], str) and v["ref"].startswith(pref + ":"):
        return v["ref"].split(":", 1)[1]
    if isinstance(v, str) and v:
        return v
    return None


def leer_plan(plan, unidades_cfg):
    if not isinstance(plan, dict) or not isinstance(plan.get("operaciones"), list):
        raise ErrorDominio("El plan debe ser un objeto con lista 'operaciones'.")
    P = {"puntos": {}, "frames": {}, "rect": {}, "sec_mat": {}, "mat_peso": {}, "insercion": set(), "angulo": {}, "avanzados": set(),
         "puntos_area": set(), "areas_abertura": set(), "no_cubierto_frame": defaultdict(list), "no_cubierto_seccion": defaultdict(list),
         "patrones_peso_propio": [], "fuente_masa": None, "problemas": [], "salvedades_globales": [], "areas": {}}
    prob = P["problemas"]; refs_frame = []
    for i, op in enumerate(plan["operaciones"]):
        if not isinstance(op, dict) or not isinstance(op.get("metodo"), str):
            prob.append(f"op[{i}]: operación sin método"); continue
        m = op["metodo"]
        if m == "edicion_tabla":
            if op.get("tabla") not in TABLAS_NEUTRAS:
                prob.append(f"op[{i}]: edición de tabla no clasificada {op.get('tabla')!r}")
            continue
        args = op.get("argumentos", [])
        if not isinstance(args, list) or any(not isinstance(a, dict) or not isinstance(a.get("nombre"), str) or "valor" not in a for a in args):
            prob.append(f"op[{i}] {m}: argumentos mal formados"); continue
        nombres = [a["nombre"] for a in args]
        if len(nombres) != len(set(nombres)):
            prob.append(f"op[{i}] {m}: argumento duplicado"); continue
        a = {x["nombre"]: x["valor"] for x in args}
        if _lectura(m) or m in NEUTRAS:
            continue
        if m not in INTERPRETADAS and m not in BLOQUEO_SI_AFECTA:
            if m.startswith("cPropFrame.Set"):
                P["no_cubierto_seccion"][a.get("Name")].append(f"{m} (sección no interpretada)")
            elif m.startswith("cFrameObj.Set"):
                P["no_cubierto_frame"][_ref(a.get("Name"), "frame")].append(f"{m} no clasificado")
            prob.append(f"op[{i}]: escritura no clasificada {m}"); continue
        if "ItemType" in a and a["ItemType"] != ITEM_OBJETOS:
            prob.append(f"op[{i}] {m}: ItemType distinto de Objects (grupo/selección no resuelto)"); continue
        if m == "cPointObj.AddCartesian":
            n = a.get("UserName")
            if not isinstance(n, str) or not n:
                prob.append(f"op[{i}]: punto sin nombre"); continue
            if n in P["puntos"]:
                prob.append(f"punto duplicado {n}"); P["puntos"][n] = None; continue
            xyz = (a.get("X"), a.get("Y"), a.get("Z"))
            P["puntos"][n] = xyz if _finito(*xyz) else None
            if P["puntos"][n] is None:
                prob.append(f"punto {n} con coordenadas no finitas")
        elif m == "cFrameObj.AddByPoint":
            n = a.get("UserName"); p1, p2 = _ref(a.get("Point1"), "punto"), _ref(a.get("Point2"), "punto")
            if not isinstance(n, str) or not n:
                prob.append(f"op[{i}]: frame sin nombre"); continue
            if n in P["frames"]:
                prob.append(f"frame duplicado {n}"); P["frames"][n]["invalido"] = "frame duplicado en el plan"; continue
            P["frames"][n] = {"p": (p1, p2), "seccion": a.get("PropName"), "invalido": None if p1 and p2 and p1 != p2 else "referencias de punto inválidas"}
            if P["frames"][n]["invalido"]:
                prob.append(f"frame {n}: {P['frames'][n]['invalido']}")
        elif m == "cPropFrame.SetRectangle":
            n = a.get("Name")
            if n in P["rect"] or n in P["no_cubierto_seccion"]:
                prob.append(f"sección duplicada {n}"); P["rect"][n] = None; continue
            t3, t2 = a.get("T3"), a.get("T2")
            P["rect"][n] = (t3, t2) if _finito(t3, t2) and t3 > 0 and t2 > 0 else None; P["sec_mat"][n] = a.get("MatProp")
            if P["rect"][n] is None:
                prob.append(f"sección {n}: dimensiones no positivas o no finitas")
        elif m == "cPropFrame.SetConcreteL":
            n = a.get("Name")
            if n in P["rect"]:
                prob.append(f"sección duplicada {n}"); P["rect"][n] = None
            P["no_cubierto_seccion"][n].append("sección L (no rectangular)")
        elif m == "cPropMaterial.SetWeightAndMass":
            n = a.get("Name")
            if n in P["mat_peso"]:
                prob.append(f"peso de material duplicado {n}"); P["mat_peso"][n] = None; continue
            opt, val = a.get("MyOption"), a.get("Value")
            if opt == 1 and _finito(val) and val >= 0:
                P["mat_peso"][n] = ("peso_volumetrico", val)
            elif opt == 1:
                P["mat_peso"][n] = None; prob.append(f"material {n}: peso volumétrico negativo o no finito")
            else:
                P["mat_peso"][n] = ("masa_no_cubierta", val)
        elif m == "cFrameObj.SetInsertionPoint":
            f = _ref(a.get("Name"), "frame"); P["insercion"].add(f); refs_frame.append((i, m, f))
        elif m == "cAreaObj.AddByPoint":
            pts, n = a.get("Point"), a.get("UserName")
            if not isinstance(pts, list):
                prob.append(f"op[{i}]: área con puntos mal formados"); continue
            rs = [_ref(v, "punto") for v in pts]
            if any(r is None for r in rs):
                prob.append(f"op[{i}]: referencia de punto de área inválida"); continue
            claves = [x.get("registra") for x in op.get("salidas", []) if isinstance(x, dict) and isinstance(x.get("registra"), str)]
            for k in claves or [f"area:{n}"]:          # el generador registra 'superficie:ID', 'abertura:ID', 'muro:ID'
                P["areas"][k] = rs
        elif m == "cAreaObj.SetOpening":
            v = a.get("Name"); n = v["ref"] if isinstance(v, dict) and set(v) == {"ref"} and isinstance(v["ref"], str) else None
            if n not in P["areas"]:
                prob.append(f"op[{i}]: abertura sobre área inexistente {n!r}")
            elif a.get("IsOpening") is True:
                P["areas_abertura"].add(n)
        elif m == "cLoadPatterns.Add":
            mult = a.get("SelfWTMultiplier")
            if not _finito(mult):
                prob.append(f"op[{i}]: multiplicador de peso propio no finito")
            elif mult != 0:
                P["patrones_peso_propio"].append({"patron": a.get("Name"), "multiplicador": mult})
        elif m == "cSapModel.SetPresentUnits":
            u = a.get("Units")
            if not isinstance(u, dict) or u.get("nombre") != unidades_cfg:
                prob.append(f"op[{i}]: SetPresentUnits a {u!r} distinto de la configuración {unidades_cfg}")
        elif m == "cPropMaterial.SetMassSource_1":
            P["fuente_masa"] = {k: a.get(k) for k in ("IncludeElements", "IncludeAddedMass", "IncludeLoads", "LoadPat", "sf")}
        elif m in BLOQUEO_SI_AFECTA:
            if m == "cPropFrame.SetModifiers":
                P["no_cubierto_seccion"][a.get("Name")].append("cPropFrame.SetModifiers no cubierto"); continue
            f = _ref(a.get("Name"), "frame"); refs_frame.append((i, m, f))
            if m == "cFrameObj.SetEndLengthOffset":
                if a.get("AutoOffset") is not True:
                    P["no_cubierto_frame"][f].append("SetEndLengthOffset con AutoOffset distinto de True (offsets explícitos no interpretados)")
                elif any(not _finito(a.get(k)) or a.get(k) != 0 for k in ("Length1", "Length2", "RZ")):
                    P["no_cubierto_frame"][f].append("SetEndLengthOffset Auto con longitudes/RZ no nulos o mal formados")
            elif m == "cFrameObj.SetLocalAxes":
                if f in P["angulo"]:
                    prob.append(f"ejes locales duplicados para {f}")
                P["angulo"][f] = a.get("Ang") if _finito(a.get("Ang")) else float("nan")
            elif m == "cFrameObj.SetLocalAxesAdvanced":
                P["avanzados"].add(f)
            else:
                P["no_cubierto_frame"][f].append(f"{m} no cubierto")
    for f in P["frames"].values():
        if not f["invalido"] and any(P["puntos"].get(p) is None for p in f["p"]):
            f["invalido"] = "punto inexistente, duplicado o no finito"
    for f, d in P["frames"].items():
        if d["invalido"] == "punto inexistente, duplicado o no finito":
            prob.append(f"frame {f}: {d['invalido']}")
    for i, m, f in refs_frame:
        if f not in P["frames"]:
            prob.append(f"op[{i}] {m}: referencia a frame inexistente {f!r}")
    for n, rs in P["areas"].items():
        if n not in P["areas_abertura"]:
            P["puntos_area"].update(rs)
    unos = [x for x in P["patrones_peso_propio"]]
    if any(x["multiplicador"] != 1 for x in unos) or len(unos) > 1:
        P["salvedades_globales"].append("multiplicadores de peso propio distintos de un único patrón con 1: el consumidor debe escalar")
    return P


def _vec(P, f):
    a, b = (P["puntos"][p] for p in P["frames"][f]["p"])
    return tuple(y - x for x, y in zip(a, b))


def _vertical(v):
    return abs(v[2]) > EPS and math.hypot(v[0], v[1]) <= EPS


def _horizontal(v):
    return abs(v[2]) <= EPS and math.hypot(v[0], v[1]) > EPS


def _bloqueos(P, f, papel):
    d = P["frames"][f]; s = d["seccion"]; out = [f"{papel} {f}: {x}" for x in P["no_cubierto_frame"].get(f, [])]
    out += [f"{papel} {f}: sección {s}: {x}" for x in P["no_cubierto_seccion"].get(s, [])]
    if P["rect"].get(s) is None:
        out.append(f"{papel} {f}: sección {s!r} ausente, no rectangular, duplicada o inválida")
    if f in P["insercion"]:
        out.append(f"{papel} {f}: punto de inserción no cubierto")
    if f in P["avanzados"]:
        out.append(f"{papel} {f}: ejes locales avanzados")
    return out


def _cara(P, col, u):
    th = P["angulo"].get(col, 0.0)
    if not _finito(th) or abs(th / 90.0 - round(th / 90.0)) > 1e-9:
        return None, f"columna {col}: ángulo local {th} no ensayado"
    if _vec(P, col)[2] < 0:
        return None, f"columna {col} definida de arriba hacia abajo"
    t3, t2 = P["rect"][P["frames"][col]["seccion"]]
    r = math.radians(th); e2 = (math.cos(r), math.sin(r)); e3 = (-math.sin(r), math.cos(r))
    c2, c3 = abs(u[0] * e2[0] + u[1] * e2[1]), abs(u[0] * e3[0] + u[1] * e3[1])
    if min(c2, c3) > 1e-9:
        return None, f"viga oblicua respecto de los ejes de {col}"
    return min((t3 / 2) / c2 if c2 > 1e-9 else math.inf, (t2 / 2) / c3 if c3 > 1e-9 else math.inf), None


def _abst(fila, motivos):
    return {**fila, "abstencion": motivos, "offsets": None, "descuento_peso": None}


def _fila_viga(P, f, tol, tol_ok, junta):
    d = P["frames"][f]; fila = {"viga": f, "seccion": d["seccion"], "puntos": list(d["p"])}
    if d["invalido"]:
        return _abst(fila, [d["invalido"]])
    v = _vec(P, f); L = math.sqrt(sum(c * c for c in v))
    if L <= EPS:
        return _abst(fila, ["longitud nula"])
    if not _horizontal(v):
        return _abst({**fila, "L_m": L}, ["miembro no horizontal (no cubierto)"])
    abst = _bloqueos(P, f, "viga"); salv = []
    ang_v = P["angulo"].get(f, 0.0)
    if not _finito(ang_v) or ang_v != 0:
        abst.append(f"viga {f}: ejes locales girados ({ang_v}) no cubiertos")
    h = math.hypot(v[0], v[1]); u = (v[0] / h, v[1] / h); extremos = []
    for lado, p in zip(("I", "J"), d["p"]):
        z = P["puntos"][p][2]; contrib = []
        for o in junta[p]:
            if o == f:
                continue
            if P["frames"][o]["invalido"]:
                abst.append(f"{lado}: frame conectado {o} inválido"); continue
            vo = _vec(P, o)
            if _vertical(vo):
                if max(P["puntos"][q][2] for q in P["frames"][o]["p"]) > z + EPS:
                    continue
                b = _bloqueos(P, o, "columna")
                if b:
                    abst += [f"{lado}: {x}" for x in b]; continue
                val, mot = _cara(P, o, u)
                if mot:
                    abst.append(f"{lado}: {mot}"); continue
                contrib.append({"columna": o, "seccion": P["frames"][o]["seccion"], "angulo": P["angulo"].get(o, 0.0), "cara_m": val})
            elif not _horizontal(vo):
                abst.append(f"{lado}: frame inclinado {o} conectado (no cubierto)")
        off = max((c["cara_m"] for c in contrib), default=0.0)
        if contrib:
            proc = "documental: columnas inferiores; experimental_315: proyección a la cara"
        elif p in P["puntos_area"]:
            proc = "experimental_315: sin columna junto a muro -> 0 (un caso)"; salv.append(f"{lado}: muro sin columna (evidencia limitada)")
        else:
            proc = "documental: sin columnas inferiores -> 0"
        extremos.append({"lado": lado, "punto": p, "columnas_inferiores": contrib, "offset_bruto_m": off, "procedencia": [proc]})
    fila.update({"L_m": L, "direccion_xy": list(u), "extremos": extremos, "salvedades": salv, "regla_exceso": None})
    if abst:
        return _abst(fila, abst)
    oi, oj = extremos[0]["offset_bruto_m"], extremos[1]["offset_bruto_m"]
    if oi + oj >= L - EPS:
        if oi > 0 and oj > 0:
            oi = oj = 0.0; fila["regla_exceso"] = "experimental_315/316: ambos extremos -> 0/0"
        elif not tol_ok:
            return _abst(fila, [f"suma >= L con tolerancia {tol} no ensayada"])
        elif L - 2 * tol <= 0:
            return _abst(fila, ["L − 2·tol no positivo"])
        else:
            oi, oj = (L - 2 * tol, 0.0) if oi > 0 else (0.0, L - 2 * tol)
            fila["regla_exceso"] = "experimental_315/316: un extremo -> L − 2·tol"
    elif L - 2 * tol < oi + oj:
        return _abst(fila, ["longitud libre entre 0 y 2·tol (zona límite no ensayada)"])
    fila["offsets"] = {"I": oi, "J": oj, "suma": oi + oj, "Lc": L - oi - oj}
    sec = d["seccion"]; mat = P["sec_mat"].get(sec); peso = P["mat_peso"].get(mat)
    if not (peso and peso[0] == "peso_volumetrico"):
        return _abst(fila, [f"descuento no determinable: material {mat!r} sin peso volumétrico válido"])
    area = P["rect"][sec][0] * P["rect"][sec][1]; kn = (oi + oj) * area * peso[1]
    if not _finito(kn) or kn < 0:
        return _abst(fila, ["descuento no finito o negativo"])
    fila["descuento_peso"] = {"kN": kn, "area_m2": area, "gamma_kN_m3": peso[1], "material": mat, "peso_cero_declarado": peso[1] == 0,
                              "procedencia": "experimental_278: SelfWtOpt Auto excluye peso en offsets de viga"}
    fila["abstencion"] = []
    return fila


def nucleo(plan, config):
    """Análisis puro (sin validar el contrato real del plan): usar `estimar_desde_plan` para planes de producción."""
    base = {"contrato": "draft2model.estimacion_extremos_auto", "version_nucleo": VERSION_NUCLEO, "lee_solver": False, "llamadas_remotas": 0,
            "configuracion": dict(config) if isinstance(config, dict) else None,
            "procedencia_tolerancia_declarada": config.get("procedencia_tolerancia") if isinstance(config, dict) else None,
            "aviso_procedencia": "La procedencia de la tolerancia es una DECLARACIÓN; el consumidor debe vincular recibo/modelo para verificarla."}
    mc = validar_config(config)
    if mc:
        return {**base, "estado": "abstencion_global", "motivos": mc, "vigas": [], "cobertura": None, "totales": None}
    try:
        P = leer_plan(plan, config["unidades"])
    except ErrorDominio as e:
        return {**base, "estado": "abstencion_global", "motivos": [str(e)], "vigas": [], "cobertura": None, "totales": None}
    if "unidades_etabs" in plan and plan["unidades_etabs"] != config["unidades"]:
        return {**base, "estado": "abstencion_global", "motivos": ["unidades del plan distintas de la configuración"], "vigas": [], "cobertura": None, "totales": None}
    tol = float(config["tolerancia_union_m"]); tol_ok = any(abs(tol - t) <= 1e-12 for t in TOL_ENSAYADAS)
    junta = defaultdict(list)
    for f, d in P["frames"].items():
        for p in d["p"]:
            if p:
                junta[p].append(f)
    filas = []
    if config["vigas"] is None:
        for f in sorted(P["frames"]):
            d = P["frames"][f]
            if d["invalido"]:
                filas.append(_abst({"viga": f}, [d["invalido"]]))
            elif _horizontal(_vec(P, f)):
                filas.append(_fila_viga(P, f, tol, tol_ok, junta))
    else:
        vistos = Counter()
        for n in config["vigas"]:
            if not isinstance(n, str) or not n:
                filas.append(_abst({"viga": n}, ["nombre solicitado inválido"])); continue
            vistos[n] += 1
            if vistos[n] > 1:
                filas.append(_abst({"viga": n}, ["solicitud duplicada"]))
            elif n not in P["frames"]:
                filas.append(_abst({"viga": n}, ["no existe en el plan"]))
            else:
                filas.append(_fila_viga(P, n, tol, tol_ok, junta))
    completas = [x for x in filas if not x["abstencion"]]
    bloqueo = (["plan con problemas"] if P["problemas"] else []) + (["selección vacía o sin vigas horizontales"] if not filas else []) + \
              (["cobertura incompleta"] if len(completas) != len(filas) else [])
    totales = None
    if not bloqueo:
        t_off = math.fsum(x["offsets"]["suma"] for x in filas); t_kn = math.fsum(x["descuento_peso"]["kN"] for x in filas)
        if _finito(t_off, t_kn):
            totales = {"vigas": len(filas), "offsets_m": t_off, "descuento_kN": t_kn}
        else:
            bloqueo.append("totales no finitos")
    return {**base, "estado": "estimacion", "tolerancia_ensayada": tol_ok, "problemas_plan": P["problemas"],
            "perfil_peso": {"patrones_peso_propio": P["patrones_peso_propio"], "fuente_masa": P["fuente_masa"], "salvedades": P["salvedades_globales"]},
            "vigas": filas, "cobertura": {"pedidas": len(filas), "completas": len(completas), "abstenidas": len(filas) - len(completas)},
            "totales": totales, "bloqueo_totales": bloqueo,
            "aviso": "Estimación experimental: no sustituye al libro bruto, al contraste nativo ni a la revisión de ingeniería."}


def estimar_desde_plan(plan, config, validador=None):
    """Entrada pública: configuración válida y plan real validado (lista blanca/firmas/referencias/huella) antes del núcleo."""
    mc = validar_config(config)
    if mc:
        return {"contrato": "draft2model.estimacion_extremos_auto", "version_nucleo": VERSION_NUCLEO, "estado": "abstencion_global",
                "motivos": mc, "vigas": [], "totales": None}
    from draft2model.operaciones_etabs import validar_plan_por_version
    if validador is not None and validador is not validar_plan_por_version:
        return {"estado": "plan_rechazado", "motivos": ["Se requiere el validador oficial del plan."], "vigas": [], "totales": None}
    try:
        problemas = validar_plan_por_version(plan)
    except (ValueError, TypeError, KeyError, IndexError, OverflowError):
        problemas = ["Plan mal formado: no se pudo validar su contrato."]
    if problemas:
        return {"contrato": "draft2model.estimacion_extremos_auto", "version_nucleo": VERSION_NUCLEO, "estado": "plan_rechazado",
                "motivos": list(problemas)[:20], "n_problemas_validador": len(problemas), "vigas": [], "totales": None}
    out = nucleo(plan, config)
    out["plan_validado"] = {"validador": "operaciones_etabs.validar_plan_por_version", "contrato": plan.get("contrato"),
                            "version_contrato": plan.get("version_contrato"), "huella_plan": plan.get("huella_plan")}
    return out


def _json_estricto(path):
    def pares(ps):
        ks = [k for k, _ in ps]
        if len(ks) != len(set(ks)):
            raise ErrorDominio(f"{path}: claves JSON duplicadas")
        return dict(ps)

    def constante(c):
        raise ErrorDominio(f"{path}: valor JSON no estándar {c}")
    b = Path(path).read_bytes()
    return json.loads(b.decode("utf-8"), object_pairs_hook=pares, parse_constant=constante), hashlib.sha256(b).hexdigest()


def validar_captura_configuracion(captura, unidades, version):
    """Configuración leída en la misma instancia/EDB que la captura de masa; no autentica por sí sola un recibo."""
    import re
    if (not isinstance(captura, dict) or set(captura) != {'unidades','version_etabs','retorno','tolerancia_union_m'}
            or captura['unidades'] != unidades or captura['version_etabs'] != version
            or type(captura['retorno']) is not int or captura['retorno'] != 0
            or not isinstance(captura['tolerancia_union_m'], str)
            or re.fullmatch(r'[+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?', captura['tolerancia_union_m']) is None):
        raise ValueError('Captura de configuración Auto inválida.')
    tol = float(captura['tolerancia_union_m'])
    if not math.isfinite(tol) or tol <= 0:
        raise ValueError('Tolerancia de unión no positiva o no finita.')
    return {'etabs_version':version,'unidades':unidades,'tolerancia_union_m':tol,
            'procedencia_tolerancia':'configuracion_verificada','vigas':None}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Estimación experimental de offsets Auto (sin solver ni llamadas remotas).")
    ap.add_argument("--plan", required=True); ap.add_argument("--configuracion", required=True); ap.add_argument("--salida", required=True)
    a = ap.parse_args(argv)
    try:
        plan, h_plan = _json_estricto(a.plan); cfg, h_cfg = _json_estricto(a.configuracion)
        out = estimar_desde_plan(plan, cfg)
        out["entradas"] = {"plan_sha256": h_plan, "configuracion_sha256": h_cfg}
        texto = json.dumps(out, ensure_ascii=False, indent=1, allow_nan=False) + "\n"
        Path(a.salida).parent.mkdir(parents=True, exist_ok=True)
        with open(a.salida, "x", encoding="utf-8") as fh:
            fh.write(texto)
    except FileExistsError:
        print("Salida existente: no se sobrescribe.", file=sys.stderr); return 2
    except (ErrorDominio, ValueError, OSError) as e:
        print("Estimación no realizada: " + str(e), file=sys.stderr); return 2
    print(f"{out['estado']}: {a.salida}")
    return 0 if out["estado"] == "estimacion" else 3


if __name__ == "__main__":
    raise SystemExit(main())
