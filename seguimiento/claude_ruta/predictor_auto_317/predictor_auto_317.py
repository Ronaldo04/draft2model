"""317: candidato PURO y aislado de offsets Auto de vigas (ETABS 21.1.0) y descuento de peso propio en esos extremos.

Entradas: plan de operaciones (dict) + configuración EXPLÍCITA. Nunca lee archivos, tablas, pesos ni offsets del solver.

Configuración requerida:
  {"etabs_version": "21.1.0", "unidades": "kN_m_C", "tolerancia_union_m": <float>,
   "procedencia_tolerancia": "configuracion_verificada" | "escenario_declarado", "vigas": [nombres] | None}

Regla (procedencias distintas por parte):
  - DOCUMENTAL (ayuda ETABS «End Length Offsets»): en vigas solo cuentan columnas inferiores; la superior, otras vigas y las
    diagonales no.
  - EXPERIMENTAL 315/316 (sintético, 21.1.0, kN-m):
      - offset = distancia del joint a la cara de la columna a lo largo del eje de la viga, según ejes locales (0/90°);
      - extremo sin columna junto a muro: 0;
      - suma ≥ L con contribución en ambos extremos: 0/0;
      - suma ≥ L con contribución en un solo extremo: L − 2·tol (tol ensayada 0,001 y 0,005 m).
  - EXPERIMENTAL 278: con SelfWtOpt Auto, el peso propio en los offsets de viga se excluye; descuento = (oi + oj)·A·γ.
Se abstiene (con motivo) fuera de lo cubierto. Totales solo con cobertura completa de las vigas pedidas.
"""
from __future__ import annotations

import math
from collections import defaultdict

VERSION_CUBIERTA = "21.1.0"
UNIDADES_CUBIERTAS = ("kN_m_C",)
TOL_ENSAYADAS = (0.001, 0.005)          # 315 (A, por defecto) y 316 (B, SetMergeTol)
EPS = 1e-9


def _args(op):
    return {a["nombre"]: a["valor"] for a in op.get("argumentos", [])}


def _ref(v):
    return v["ref"].split(":", 1)[1] if isinstance(v, dict) and "ref" in v else v


def _finito(*xs):
    return all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in xs)


def leer_plan(plan):
    """Extrae del plan solo lo necesario. Duplicados y valores no finitos quedan registrados como problemas."""
    pts, frames, rect, mat_peso, sec_mat, ins, ang, avanzados, area_pts, otras_secciones = {}, {}, {}, {}, {}, set(), {}, set(), set(), set()
    problemas = []
    for op in plan.get("operaciones", []):
        m = op.get("metodo"); a = _args(op)
        if m == "cPointObj.AddCartesian":
            n = a.get("UserName")
            if n in pts:
                problemas.append(f"punto duplicado {n}")
            pts[n] = (a.get("X"), a.get("Y"), a.get("Z"))
        elif m == "cFrameObj.AddByPoint":
            n = a.get("UserName")
            if n in frames:
                problemas.append(f"frame duplicado {n}"); frames[n]["duplicado"] = True; continue
            frames[n] = {"p": (_ref(a.get("Point1")), _ref(a.get("Point2"))), "seccion": a.get("PropName"), "duplicado": False}
        elif m == "cPropFrame.SetRectangle":
            rect[a["Name"]] = (a.get("T3"), a.get("T2")); sec_mat[a["Name"]] = a.get("MatProp")
        elif m and m.startswith("cPropFrame.Set") and m not in ("cPropFrame.SetRectangle", "cPropFrame.SetModifiers"):
            if "Name" in a:
                otras_secciones.add(a["Name"])
        elif m == "cPropMaterial.SetWeightAndMass":
            mat_peso[a["Name"]] = (a.get("MyOption"), a.get("Value"))
        elif m == "cFrameObj.SetInsertionPoint":
            ins.add(_ref(a.get("Name")))
        elif m == "cFrameObj.SetLocalAxes":
            ang[_ref(a.get("Name"))] = a.get("Ang")
        elif m == "cFrameObj.SetLocalAxesAdvanced":
            avanzados.add(_ref(a.get("Name")))
        elif m == "cAreaObj.AddByPoint":
            for v in a.get("Point") or []:
                area_pts.add(_ref(v))
    return {"puntos": pts, "frames": frames, "rect": rect, "sec_mat": sec_mat, "mat_peso": mat_peso, "insercion": ins,
            "angulo": ang, "ejes_avanzados": avanzados, "puntos_area": area_pts, "otras_secciones": otras_secciones,
            "problemas": problemas}


def _validar_config(cfg):
    motivos = []
    if not isinstance(cfg, dict):
        return ["configuración ausente"]
    if cfg.get("etabs_version") != VERSION_CUBIERTA:
        motivos.append(f"versión ETABS {cfg.get('etabs_version')!r} no cubierta (solo {VERSION_CUBIERTA})")
    if cfg.get("unidades") not in UNIDADES_CUBIERTAS:
        motivos.append(f"unidades {cfg.get('unidades')!r} no cubiertas")
    t = cfg.get("tolerancia_union_m")
    if not _finito(t) or t <= 0:
        motivos.append("tolerancia de unión ausente, no finita o no positiva")
    if cfg.get("procedencia_tolerancia") not in ("configuracion_verificada", "escenario_declarado"):
        motivos.append("procedencia de la tolerancia no declarada")
    return motivos


def _vec(M, f):
    a, b = (M["puntos"].get(p) for p in M["frames"][f]["p"])
    if a is None or b is None or not _finito(*a, *b):
        return None
    return tuple(y - x for x, y in zip(a, b))


def _vertical(v):
    return abs(v[2]) > EPS and math.hypot(v[0], v[1]) <= EPS


def _horizontal(v):
    return abs(v[2]) <= EPS and math.hypot(v[0], v[1]) > EPS


def _cara(M, col, u):
    """Distancia a la cara de una columna vertical a lo largo de u (horizontal unitario). Devuelve (valor, motivo_abstencion)."""
    if col in M["insercion"]:
        return None, f"columna {col} con punto de inserción (no ensayado)"
    if col in M["ejes_avanzados"]:
        return None, f"columna {col} con ejes locales avanzados"
    sec = M["frames"][col]["seccion"]
    if sec not in M["rect"]:
        return None, f"columna {col}: sección {sec!r} ausente o no rectangular"
    t3, t2 = M["rect"][sec]
    if not _finito(t3, t2) or t3 <= 0 or t2 <= 0:
        return None, f"columna {col}: dimensiones no válidas"
    th = M["angulo"].get(col, 0.0)
    if not _finito(th) or abs((th / 90.0) - round(th / 90.0)) > 1e-9:
        return None, f"columna {col}: ángulo local {th} no ensayado (solo múltiplos de 90°)"
    v = _vec(M, col)
    if v[2] < 0:                                   # ejes por defecto definidos para columna con I abajo
        return None, f"columna {col} definida de arriba hacia abajo (no ensayado)"
    r = math.radians(th); e2 = (math.cos(r), math.sin(r)); e3 = (-math.sin(r), math.cos(r))
    c2, c3 = abs(u[0] * e2[0] + u[1] * e2[1]), abs(u[0] * e3[0] + u[1] * e3[1])
    if min(c2, c3) > 1e-9:
        return None, f"viga oblicua respecto de los ejes de {col} (no ensayado)"
    return min((t3 / 2) / c2 if c2 > 1e-9 else math.inf, (t2 / 2) / c3 if c3 > 1e-9 else math.inf), None


def predecir(plan, config):
    M = leer_plan(plan)
    motivos_cfg = _validar_config(config)
    base = {"contrato": "draft2model.prediccion_offsets_auto_candidato", "version_candidato": "0.1.0-317",
            "configuracion": dict(config) if isinstance(config, dict) else None, "lee_solver": False}
    if motivos_cfg:
        return {**base, "estado": "abstencion_global", "motivos": motivos_cfg, "vigas": [], "totales": None}
    tol = float(config["tolerancia_union_m"])
    tol_ensayada = any(abs(tol - t) <= 1e-12 for t in TOL_ENSAYADAS)
    junta = defaultdict(list)
    for f, d in M["frames"].items():
        for p in d["p"]:
            junta[p].append(f)
    pedidas = config.get("vigas")
    candidatas = []
    for f in sorted(M["frames"]):
        v = _vec(M, f)
        if pedidas is not None:
            if f in pedidas:
                candidatas.append(f)
        elif v is not None and _horizontal(v):
            candidatas.append(f)
    filas = []
    for f in candidatas:
        d = M["frames"][f]; abst, salv = [], []
        fila = {"viga": f, "seccion": d["seccion"], "puntos": list(d["p"])}
        if d.get("duplicado"):
            abst.append("frame duplicado en el plan")
        v = _vec(M, f)
        if v is None:
            filas.append({**fila, "abstencion": abst + ["coordenadas ausentes o no finitas"], "offsets": None}); continue
        L = math.sqrt(sum(c * c for c in v))
        if L <= EPS:
            filas.append({**fila, "abstencion": abst + ["longitud nula (geometría degenerada)"], "offsets": None}); continue
        if not _horizontal(v):
            filas.append({**fila, "L_m": L, "abstencion": abst + ["viga no horizontal (no cubierta)"], "offsets": None}); continue
        h = math.hypot(v[0], v[1]); u = (v[0] / h, v[1] / h)
        extremos = []
        for lado, p in zip(("I", "J"), d["p"]):
            z = M["puntos"][p][2]; contrib, procedencia = [], []
            for o in junta[p]:
                if o == f:
                    continue
                vo = _vec(M, o)
                if vo is None:
                    abst.append(f"{lado}: frame conectado {o} con coordenadas no válidas"); continue
                if _vertical(vo):
                    zs = [M["puntos"][q][2] for q in M["frames"][o]["p"]]
                    if max(zs) > z + EPS:
                        continue                                   # documental: columna superior no cuenta
                    val, mot = _cara(M, o, u)
                    if mot:
                        abst.append(f"{lado}: {mot}"); continue
                    contrib.append({"columna": o, "seccion": M["frames"][o]["seccion"], "angulo": M["angulo"].get(o, 0.0), "cara_m": val})
                elif _horizontal(vo):
                    continue                                       # documental: otras vigas no cuentan
                else:
                    abst.append(f"{lado}: frame inclinado {o} conectado (no cubierto)")
            off = max((c["cara_m"] for c in contrib), default=0.0)
            if contrib:
                procedencia.append("documental: columnas inferiores; experimental_315: proyección a la cara")
            elif p in M["puntos_area"]:
                procedencia.append("experimental_315: sin columna junto a muro -> 0 (un caso sintético K04)")
                salv.append(f"{lado}: muro sin columna, evidencia experimental limitada")
            else:
                procedencia.append("documental: sin columnas inferiores -> 0")
            extremos.append({"lado": lado, "punto": p, "columnas_inferiores": contrib, "offset_bruto_m": off, "procedencia": procedencia})
        oi, oj = extremos[0]["offset_bruto_m"], extremos[1]["offset_bruto_m"]
        regla_exceso = None
        if not abst and oi + oj >= L - EPS:
            if oi > 0 and oj > 0:
                oi = oj = 0.0; regla_exceso = "experimental_315/316: suma >= L con ambos extremos -> 0/0"
            elif not tol_ensayada:
                abst.append(f"suma >= L con tolerancia {tol} no ensayada (solo {TOL_ENSAYADAS})")
            elif L - 2 * tol <= 0:
                abst.append("L − 2·tol no positivo")
            else:
                if oi > 0:
                    oi = L - 2 * tol
                else:
                    oj = L - 2 * tol
                regla_exceso = "experimental_315/316: suma >= L con un solo extremo -> L − 2·tol"
        elif not abst and L - 2 * tol < oi + oj < L:
            abst.append("longitud libre entre 0 y 2·tol: zona límite no ensayada")
        fila.update({"L_m": L, "direccion_xy": list(u), "extremos": extremos, "abstencion": abst, "salvedades": salv,
                     "regla_exceso": regla_exceso})
        if abst:
            fila["offsets"] = None; filas.append(fila); continue
        fila["offsets"] = {"I": oi, "J": oj, "suma": oi + oj, "Lc": L - oi - oj}
        sec = d["seccion"]; mat = M["sec_mat"].get(sec); peso = M["mat_peso"].get(mat)
        if sec in M["rect"] and peso and peso[0] == 1 and _finito(peso[1], *M["rect"][sec]):
            area = M["rect"][sec][0] * M["rect"][sec][1]
            fila["descuento_peso"] = {"kN": (oi + oj) * area * peso[1], "area_m2": area, "gamma_kN_m3": peso[1], "material": mat,
                                      "procedencia": "experimental_278: SelfWtOpt Auto excluye peso en offsets de viga"}
        else:
            fila["descuento_peso"] = None; fila["salvedades"].append("descuento no determinable (sección/material/peso por volumen)")
        filas.append(fila)
    completas = [x for x in filas if x.get("offsets") is not None and x.get("descuento_peso")]
    totales = None
    if filas and len(completas) == len(filas):
        totales = {"vigas": len(filas), "offsets_m": sum(x["offsets"]["suma"] for x in filas), "descuento_kN": sum(x["descuento_peso"]["kN"] for x in filas)}
    return {**base, "estado": "prediccion", "tolerancia_ensayada": tol_ensayada, "problemas_plan": M["problemas"], "vigas": filas,
            "cobertura": {"pedidas": len(filas), "con_offsets": sum(x.get("offsets") is not None for x in filas), "con_descuento": len(completas),
                          "abstenidas": sum(bool(x.get("abstencion")) for x in filas)},
            "totales": totales, "aviso": "Totales solo con cobertura completa; candidato no integrado; no aprueba masa ni ingeniería."}
