"""313: predictor independiente de end length offsets Auto para vigas VS (regla pre-registrada en REGLA_PREREGISTRADA_313.md).

Entradas: SOLO el plan del modelo (puntos, frames, secciones rectangulares, inserciones, áreas). No lee pesos, offsets,
tablas ni recibos del solver. Uso: python predictor_313.py PLAN.json SALIDA.json
"""
import json, math, sys
from collections import defaultdict

TOL_COLINEAL = 1e-6


def _args(op):
    return {a["nombre"]: a["valor"] for a in op["argumentos"]}


def cargar_modelo(plan):
    ops = plan["operaciones"]
    pts, frames, secc, insercion, area_pts, metodos = {}, {}, {}, set(), set(), defaultdict(int)
    for op in ops:
        m = op.get("metodo"); metodos[m] += 1; a = _args(op) if "argumentos" in op else {}
        if m == "cPointObj.AddCartesian":
            pts[a["UserName"]] = (float(a["X"]), float(a["Y"]), float(a["Z"]))
        elif m == "cFrameObj.AddByPoint":
            p1, p2 = a["Point1"]["ref"].split(":", 1)[1], a["Point2"]["ref"].split(":", 1)[1]
            frames[a["UserName"]] = {"p": (p1, p2), "seccion": a["PropName"]}
        elif m == "cPropFrame.SetRectangle":
            secc[a["Name"]] = {"T3": float(a["T3"]), "T2": float(a["T2"])}
        elif m == "cFrameObj.SetInsertionPoint":
            insercion.add(a["Name"]["ref"].split(":", 1)[1])
        elif m == "cAreaObj.AddByPoint":
            for v in a.get("Point", a.get("PointName", [])) or []:
                area_pts.add(v["ref"].split(":", 1)[1] if isinstance(v, dict) else v)
    return {"puntos": pts, "frames": frames, "secciones": secc, "insercion": insercion, "puntos_area": area_pts,
            "metodos": {k: metodos[k] for k in ("cFrameObj.SetLocalAxes", "cFrameObj.SetEndLengthOffset", "cPropFrame.SetSDSection",
                                                 "cPropFrame.SetTee", "cPropFrame.SetAngle", "cFrameObj.SetInsertionPoint")}}


def _vec(m, f):
    a, b = (m["puntos"][p] for p in m["frames"][f]["p"])
    return tuple(bb - aa for aa, bb in zip(a, b))


def es_columna(m, f):
    dx, dy, dz = _vec(m, f)
    return abs(dz) > 1e-9 and math.hypot(dx, dy) < 1e-9


def predecir(m, prefijo="VS"):
    junta = defaultdict(list)
    for f, d in m["frames"].items():
        for p in d["p"]:
            junta[p].append(f)
    filas = []
    for f, d in sorted(m["frames"].items()):
        if not f.startswith(prefijo):
            continue
        dx, dy, dz = _vec(m, f); L = math.sqrt(dx * dx + dy * dy + dz * dz)
        h = math.hypot(dx, dy); ux, uy = (dx / h, dy / h) if h else (0.0, 0.0)
        extremos, abst = [], []
        for lado, p in zip(("I", "J"), d["p"]):
            contrib, otros = [], [o for o in junta[p] if o != f]
            for o in otros:
                s = m["secciones"].get(m["frames"][o]["seccion"])
                if s is None:
                    abst.append(f"A3:{lado}:{o}: sección no rectangular"); continue
                if es_columna(m, o):
                    if o in m["insercion"]:
                        abst.append(f"A1:{lado}:{o}: columna con punto de inserción desplazado"); continue
                    cand = min((s["T3"] / 2) / abs(ux) if abs(ux) > 1e-12 else math.inf,
                               (s["T2"] / 2) / abs(uy) if abs(uy) > 1e-12 else math.inf)
                    contrib.append({"otro": o, "tipo": "columna", "T3": s["T3"], "T2": s["T2"], "cara_m": cand,
                                    "rmax_m": max(s["T3"], s["T2"]) / 2})
                else:
                    ox, oy, oz = _vec(m, o)
                    if abs(oz) > 1e-9 and math.hypot(ox, oy) > 1e-9:
                        abst.append(f"A3:{lado}:{o}: frame inclinado"); continue
                    oh = math.hypot(ox, oy); sen = abs(ux * oy / oh - uy * ox / oh) if oh else 0.0
                    cand = (s["T2"] / 2) / sen if sen > TOL_COLINEAL else 0.0
                    contrib.append({"otro": o, "tipo": "viga", "T2": s["T2"], "sen_alfa": sen, "cara_m": cand,
                                    "rmax_m": max(s["T3"], s["T2"]) / 2 if sen > TOL_COLINEAL else 0.0})
            if not otros and p in m["puntos_area"]:
                abst.append(f"A2:{lado}: sin frames; el punto pertenece a áreas (muro/losa)")
            extremos.append({"lado": lado, "punto": p, "contribuciones": contrib,
                             "cara_m": max((c["cara_m"] for c in contrib), default=0.0),
                             "rmax_m": max((c["rmax_m"] for c in contrib), default=0.0)})
        fila = {"viga": f, "seccion": d["seccion"], "puntos": list(d["p"]), "L_m": L, "direccion_xy": [ux, uy],
                "abstencion": abst, "regla": "R-cara (M1+M2) + M3; variante R-max informada"}
        for var in ("cara_m", "rmax_m"):
            oi, oj = (e[var] for e in extremos)
            k = 1.0
            if oi + oj > 0.99 * L:                      # M3: Lc >= 1 % L, reducción proporcional
                k = 0.99 * L / (oi + oj)
            fila[var.replace("_m", "")] = {"I": oi * k, "J": oj * k, "suma": (oi + oj) * k, "tope_1pct": k < 1.0}
        fila["extremos"] = extremos
        filas.append(fila)
    return filas


if __name__ == "__main__":
    plan = json.load(open(sys.argv[1], encoding="utf-8"))
    mod = cargar_modelo(plan); filas = predecir(mod)
    out = {"tarea": "masa_313_prediccion", "entradas": {"plan": sys.argv[1]}, "metodos_relevantes": mod["metodos"],
           "secciones": mod["secciones"], "columnas_con_insercion": sorted(mod["insercion"]),
           "vigas": filas, "n_vigas": len(filas), "n_abstenidas": sum(bool(f["abstencion"]) for f in filas)}
    json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(filas), "vigas;", out["n_abstenidas"], "con abstención;", mod["metodos"])
