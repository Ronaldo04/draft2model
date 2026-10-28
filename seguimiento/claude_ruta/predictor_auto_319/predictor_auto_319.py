"""319: candidato PURO y autónomo de offsets Auto de vigas (ETABS 21.1.0) con validación conservadora.

Corrige 317 (REVISION_PREDICTOR_318):
  - las solicitudes inexistentes, duplicadas o inválidas permanecen en el denominador;
  - los duplicados y referencias inválidas del plan bloquean los totales;
  - SetEndLengthOffset no Auto, los modificadores y demás operaciones no cubiertas producen abstención;
  - pesos negativos o no finitos se rechazan.
Reglas y procedencias iguales que en 317 (documental: columnas inferiores; experimental 315/316/278). No abre archivos ni lee el solver.

Configuración: {"etabs_version": "21.1.0", "unidades": "kN_m_C", "tolerancia_union_m": float > 0,
                "procedencia_tolerancia": "configuracion_verificada" | "escenario_declarado", "vigas": None | [str, ...]}
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict

VERSION_CUBIERTA = "21.1.0"
UNIDADES_CUBIERTAS = ("kN_m_C",)
TOL_ENSAYADAS = (0.001, 0.005)
EPS = 1e-9
# Operaciones sin efecto sobre offsets/peso propio de frames (lecturas, áreas, cargas, casos, etc.) no se enumeran:
# se consideran neutras salvo que sean cFrameObj.* / cPropFrame.* de escritura no interpretadas (abajo).
FRAME_SET_INTERPRETADAS = {"cFrameObj.AddByPoint", "cFrameObj.SetInsertionPoint", "cFrameObj.SetLocalAxes", "cFrameObj.SetLocalAxesAdvanced",
                           "cFrameObj.SetEndLengthOffset", "cFrameObj.SetModifiers", "cFrameObj.SetSection", "cFrameObj.SetMass"}
PROP_SET_INTERPRETADAS = {"cPropFrame.SetRectangle", "cPropFrame.SetModifiers"}


class ErrorDominio(ValueError):
    """Entrada estructuralmente inválida (no un plan con problemas, sino un objeto que no es plan)."""


def _finito(*xs):
    return all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in xs)


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
        m.append("'vigas' debe ser None o una lista (no texto ni otro tipo)")
    return m


def _ref(v, pref):
    if isinstance(v, dict) and set(v) == {"ref"} and isinstance(v["ref"], str) and v["ref"].startswith(pref + ":"):
        return v["ref"].split(":", 1)[1]
    if isinstance(v, str) and v:
        return v
    return None


def leer_plan(plan):
    if not isinstance(plan, dict) or not isinstance(plan.get("operaciones"), list):
        raise ErrorDominio("El plan debe ser un objeto con lista 'operaciones'.")
    P = {"puntos": {}, "frames": {}, "rect": {}, "sec_mat": {}, "mat_peso": {}, "insercion": set(), "angulo": {}, "avanzados": set(),
         "puntos_area": set(), "no_cubierto_frame": defaultdict(list), "no_cubierto_seccion": defaultdict(list), "problemas": []}
    prob = P["problemas"]
    for i, op in enumerate(plan["operaciones"]):
        if not isinstance(op, dict) or not isinstance(op.get("metodo", None), (str, type(None))):
            prob.append(f"op[{i}]: operación mal formada"); continue
        m = op.get("metodo")
        args = op.get("argumentos", [])
        if not isinstance(args, list) or any(not isinstance(a, dict) or not isinstance(a.get("nombre"), str) or "valor" not in a for a in args):
            prob.append(f"op[{i}] {m}: argumentos mal formados"); continue
        nombres = [a["nombre"] for a in args]
        if len(nombres) != len(set(nombres)):
            prob.append(f"op[{i}] {m}: argumento duplicado {sorted(k for k, n in Counter(nombres).items() if n > 1)}"); continue
        a = {x["nombre"]: x["valor"] for x in args}
        if m is None:
            continue
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
            if n in P["rect"]:
                prob.append(f"sección duplicada {n}"); P["rect"][n] = None; continue
            t3, t2 = a.get("T3"), a.get("T2")
            P["rect"][n] = (t3, t2) if _finito(t3, t2) and t3 > 0 and t2 > 0 else None
            P["sec_mat"][n] = a.get("MatProp")
            if P["rect"][n] is None:
                prob.append(f"sección {n}: dimensiones no positivas o no finitas")
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
            P["insercion"].add(_ref(a.get("Name"), "frame"))
        elif m == "cFrameObj.SetLocalAxes":
            f = _ref(a.get("Name"), "frame"); ang = a.get("Ang")
            if f in P["angulo"]:
                prob.append(f"ejes locales duplicados para {f}")
            P["angulo"][f] = ang if _finito(ang) else float("nan")
        elif m == "cFrameObj.SetLocalAxesAdvanced":
            P["avanzados"].add(_ref(a.get("Name"), "frame"))
        elif m == "cFrameObj.SetEndLengthOffset":
            f = _ref(a.get("Name"), "frame")
            if a.get("AutoOffset") is not True:
                P["no_cubierto_frame"][f].append("SetEndLengthOffset con AutoOffset distinto de True (offsets explícitos no interpretados)")
            elif any(_finito(a.get(k)) and a.get(k) != 0 for k in ("Length1", "Length2", "RZ")):
                P["no_cubierto_frame"][f].append("SetEndLengthOffset Auto con longitudes/RZ no nulos (no interpretado)")
        elif m in ("cFrameObj.SetModifiers", "cFrameObj.SetSection", "cFrameObj.SetMass"):
            P["no_cubierto_frame"][_ref(a.get("Name"), "frame")].append(f"{m} no cubierto")
        elif m == "cPropFrame.SetModifiers":
            P["no_cubierto_seccion"][a.get("Name")].append("cPropFrame.SetModifiers no cubierto")
        elif m.startswith("cFrameObj.Set") and m not in FRAME_SET_INTERPRETADAS:
            P["no_cubierto_frame"][_ref(a.get("Name"), "frame")].append(f"{m} no cubierto")
        elif m.startswith("cPropFrame.Set") and m not in PROP_SET_INTERPRETADAS:
            P["no_cubierto_seccion"][a.get("Name")].append(f"{m} (sección no rectangular o no interpretada)")
        elif m == "cAreaObj.AddByPoint":
            pts = a.get("Point")
            if not isinstance(pts, list):
                prob.append(f"op[{i}]: área con puntos mal formados"); continue
            for v in pts:
                r = _ref(v, "punto")
                if r is None:
                    prob.append(f"op[{i}]: referencia de punto de área inválida")
                else:
                    P["puntos_area"].add(r)
    for f, d in P["frames"].items():
        if not d["invalido"] and any(P["puntos"].get(p) is None for p in d["p"]):
            d["invalido"] = "punto inexistente, duplicado o no finito"
            prob.append(f"frame {f}: {d['invalido']}")
    return P


def _vec(P, f):
    a, b = (P["puntos"][p] for p in P["frames"][f]["p"])
    return tuple(y - x for x, y in zip(a, b))


def _vertical(v):
    return abs(v[2]) > EPS and math.hypot(v[0], v[1]) <= EPS


def _horizontal(v):
    return abs(v[2]) <= EPS and math.hypot(v[0], v[1]) > EPS


def _bloqueos_miembro(P, f, papel):
    d = P["frames"][f]; s = d["seccion"]; out = []
    out += [f"{papel} {f}: {x}" for x in P["no_cubierto_frame"].get(f, [])]
    out += [f"{papel} {f}: sección {s}: {x}" for x in P["no_cubierto_seccion"].get(s, [])]
    if s not in P["rect"] or P["rect"][s] is None:
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


def _fila_viga(P, f, tol, tol_ensayada, junta):
    d = P["frames"][f]; fila = {"viga": f, "seccion": d["seccion"], "puntos": list(d["p"])}; abst, salv = [], []
    if d["invalido"]:
        return {**fila, "abstencion": [d["invalido"]], "offsets": None, "descuento_peso": None}
    v = _vec(P, f); L = math.sqrt(sum(c * c for c in v))
    if L <= EPS:
        return {**fila, "abstencion": ["longitud nula"], "offsets": None, "descuento_peso": None}
    if not _horizontal(v):
        return {**fila, "L_m": L, "abstencion": ["miembro no horizontal (no cubierto)"], "offsets": None, "descuento_peso": None}
    abst += _bloqueos_miembro(P, f, "viga")
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
                abst.append(f"{lado}: frame conectado {o} inválido ({P['frames'][o]['invalido']})"); continue
            vo = _vec(P, o)
            if _vertical(vo):
                if max(P["puntos"][q][2] for q in P["frames"][o]["p"]) > z + EPS:
                    continue
                b = _bloqueos_miembro(P, o, "columna")
                if b:
                    abst += [f"{lado}: {x}" for x in b]; continue
                val, mot = _cara(P, o, u)
                if mot:
                    abst.append(f"{lado}: {mot}"); continue
                contrib.append({"columna": o, "seccion": P["frames"][o]["seccion"], "angulo": P["angulo"].get(o, 0.0), "cara_m": val})
            elif _horizontal(vo):
                continue
            else:
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
        return {**fila, "abstencion": abst, "offsets": None, "descuento_peso": None}
    oi, oj = extremos[0]["offset_bruto_m"], extremos[1]["offset_bruto_m"]
    if oi + oj >= L - EPS:
        if oi > 0 and oj > 0:
            oi = oj = 0.0; fila["regla_exceso"] = "experimental_315/316: ambos extremos -> 0/0"
        elif not tol_ensayada:
            return {**fila, "abstencion": [f"suma >= L con tolerancia {tol} no ensayada"], "offsets": None, "descuento_peso": None}
        elif L - 2 * tol <= 0:
            return {**fila, "abstencion": ["L − 2·tol no positivo"], "offsets": None, "descuento_peso": None}
        else:
            oi, oj = (L - 2 * tol, 0.0) if oi > 0 else (0.0, L - 2 * tol)
            fila["regla_exceso"] = "experimental_315/316: un extremo -> L − 2·tol"
    elif L - 2 * tol < oi + oj:
        return {**fila, "abstencion": ["longitud libre entre 0 y 2·tol (zona límite no ensayada)"], "offsets": None, "descuento_peso": None}
    fila["offsets"] = {"I": oi, "J": oj, "suma": oi + oj, "Lc": L - oi - oj}
    sec = d["seccion"]; mat = P["sec_mat"].get(sec); peso = P["mat_peso"].get(mat)
    if peso and peso[0] == "peso_volumetrico":
        area = P["rect"][sec][0] * P["rect"][sec][1]; kn = (oi + oj) * area * peso[1]
        if _finito(kn) and kn >= 0:
            fila["descuento_peso"] = {"kN": kn, "area_m2": area, "gamma_kN_m3": peso[1], "material": mat, "peso_cero_declarado": peso[1] == 0,
                                      "procedencia": "experimental_278: SelfWtOpt Auto excluye peso en offsets de viga"}
        else:
            fila["descuento_peso"] = None; fila["abstencion"] = ["descuento no finito o negativo"]; return fila
    else:
        fila["descuento_peso"] = None
        fila["abstencion"] = [f"descuento no determinable: material {mat!r} sin peso volumétrico válido (ausente, duplicado, inválido o por masa)"]
        return fila
    fila["abstencion"] = []
    return fila


def predecir(plan, config):
    base = {"contrato": "draft2model.prediccion_offsets_auto_candidato", "version_candidato": "0.2.0-319", "lee_solver": False,
            "configuracion": dict(config) if isinstance(config, dict) else None}
    mc = validar_config(config)
    if mc:
        return {**base, "estado": "abstencion_global", "motivos": mc, "vigas": [], "cobertura": None, "totales": None}
    try:
        P = leer_plan(plan)
    except ErrorDominio as e:
        return {**base, "estado": "abstencion_global", "motivos": [str(e)], "vigas": [], "cobertura": None, "totales": None}
    if "unidades_etabs" in plan and plan["unidades_etabs"] != config["unidades"]:
        return {**base, "estado": "abstencion_global", "motivos": [f"unidades del plan {plan['unidades_etabs']!r} distintas de la configuración"],
                "vigas": [], "cobertura": None, "totales": None}
    tol = float(config["tolerancia_union_m"]); tol_ensayada = any(abs(tol - t) <= 1e-12 for t in TOL_ENSAYADAS)
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
                filas.append({"viga": f, "abstencion": [d["invalido"]], "offsets": None, "descuento_peso": None})
            elif _horizontal(_vec(P, f)):
                filas.append(_fila_viga(P, f, tol, tol_ensayada, junta))
    else:
        vistos = Counter()
        for n in config["vigas"]:
            if not isinstance(n, str) or not n:
                filas.append({"viga": n, "abstencion": ["nombre solicitado inválido"], "offsets": None, "descuento_peso": None}); continue
            vistos[n] += 1
            if vistos[n] > 1:
                filas.append({"viga": n, "abstencion": ["solicitud duplicada"], "offsets": None, "descuento_peso": None})
            elif n not in P["frames"]:
                filas.append({"viga": n, "abstencion": ["no existe en el plan"], "offsets": None, "descuento_peso": None})
            else:
                filas.append(_fila_viga(P, n, tol, tol_ensayada, junta))
    completas = [x for x in filas if not x["abstencion"] and x.get("offsets") and x.get("descuento_peso")]
    bloqueo_totales = []
    if P["problemas"]:
        bloqueo_totales.append("plan con problemas estructurales")
    if not filas:
        bloqueo_totales.append("selección vacía o sin vigas horizontales")
    if len(completas) != len(filas):
        bloqueo_totales.append("cobertura incompleta")
    totales = None if bloqueo_totales else {"vigas": len(filas), "offsets_m": sum(x["offsets"]["suma"] for x in filas),
                                            "descuento_kN": sum(x["descuento_peso"]["kN"] for x in filas)}
    return {**base, "estado": "prediccion", "tolerancia_ensayada": tol_ensayada, "problemas_plan": P["problemas"], "vigas": filas,
            "cobertura": {"pedidas": len(filas), "completas": len(completas), "abstenidas": len(filas) - len(completas)},
            "totales": totales, "bloqueo_totales": bloqueo_totales,
            "aviso": "Candidato no integrado; totales solo sin problemas de plan y con cobertura completa; no aprueba masa ni ingeniería."}
