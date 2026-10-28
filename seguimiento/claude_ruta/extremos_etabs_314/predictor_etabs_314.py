"""314: predictor R-ETABS (REGLA_314.md). Solo plan; reutiliza el lector de plan de 313 sin modificarlo.
Uso: python predictor_etabs_314.py PLAN.json SALIDA.json
"""
import json, math, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "prediccion_masa_313"))
from predictor_313 import cargar_modelo, es_columna, _vec  # noqa: E402  (lectura del plan, sin cambios)


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
        abst, extremos = [], []
        if abs(dz) > 1e-9:
            abst.append("B4: viga inclinada")
        for lado, p in zip(("I", "J"), d["p"]):
            z = m["puntos"][p][2]; inferiores, salvedad = [], False
            for o in junta[p]:
                if o == f or not es_columna(m, o):
                    continue                                    # E2: solo columnas; otras vigas no cuentan
                zs = [m["puntos"][q][2] for q in m["frames"][o]["p"]]
                if max(zs) - z > 1e-9:                          # E3: columna por encima del joint: se ignora
                    continue
                s = m["secciones"].get(m["frames"][o]["seccion"])
                if s is None:
                    abst.append(f"B4:{lado}:{o}: sección no rectangular"); continue
                if o in m["insercion"]:
                    abst.append(f"B1:{lado}:{o}: columna inferior con punto de inserción"); continue
                inferiores.append({"columna": o, "T3": s["T3"], "T2": s["T2"], "offset_m": max(s["T3"], s["T2"]) / 2})
            if p in m["puntos_area"]:
                if inferiores:
                    salvedad = True
                else:
                    abst.append(f"B3:{lado}: sin columna inferior y punto con áreas (muro/losa)")
            extremos.append({"lado": lado, "punto": p, "columnas_inferiores": inferiores, "salvedad_muro": salvedad,
                             "offset_m": max((c["offset_m"] for c in inferiores), default=0.0)})
        oi, oj = extremos[0]["offset_m"], extremos[1]["offset_m"]
        if oi + oj >= L - 1e-12 and (oi or oj):
            abst.append(f"B2: suma de offsets {oi + oj:.4f} >= L {L:.4f}; límite no documentado")
        filas.append({"viga": f, "L_m": L, "puntos": list(d["p"]), "abstencion": abst, "extremos": extremos,
                      "etabs": {"I": oi, "J": oj, "suma": oi + oj}, "regla": "R-ETABS (E2+E3, ½·dimensión máxima)"})
    return filas


if __name__ == "__main__":
    mod = cargar_modelo(json.load(open(sys.argv[1], encoding="utf-8")))
    filas = predecir(mod)
    out = {"tarea": "extremos_314_prediccion", "plan": sys.argv[1], "vigas": filas, "n_vigas": len(filas),
           "n_abstenidas": sum(bool(f["abstencion"]) for f in filas)}
    json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    from collections import Counter
    print(len(filas), "vigas;", out["n_abstenidas"], "abstenidas;", Counter(a.split(":")[0] for f in filas for a in f["abstencion"]))
