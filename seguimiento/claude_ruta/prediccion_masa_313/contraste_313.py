"""313: contraste POSTERIOR y separado. Compara PREDICCION_313.json (sellada antes) con los offsets nativos archivados de la lectura
6da62ea3… (tabla Frame Assignments - End Length Offsets) y el peso por sección. No modifica la predicción ni la tolerancia.
Uso: python contraste_313.py PREDICCION.json SALIDA.json
"""
import hashlib, json, sys
from decimal import Decimal as D
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
LECT = RAIZ / "data/private/pueblo-libre-002/lecturas_analisis/6da62ea363484498a3e13315c99b328a/respuesta.json"
TOL = 0.0005   # redondeo de tabla, declarado en la regla pre-registrada
GAMMA_AREA = D("0.3") * D("0.15") * D("24")   # kN/m: sección VS 0.15x0.30 y W=24 kN/m3 de CONCRETO-FC210 (REVISION_EXTREMOS_278)


def main(pred_path, salida):
    pred = json.load(open(pred_path, encoding="utf-8"))
    res = json.loads(LECT.read_text(encoding="utf-8"))
    rows = {r["UniqueName"]: r for t in res["datos"]["tablas"] if t["clave"] == "Frame Assignments - End Length Offsets" for r in t["filas"]}
    filas, cuenta = [], {"acuerdo": 0, "desacuerdo": 0, "abstencion": 0}
    for v in pred["vigas"]:
        r = rows[v["viga"]]; ni, nj = float(r["OffsetI"]), float(r["OffsetJ"])
        f = {"viga": v["viga"], "L_m": round(v["L_m"], 4), "nativo": {"I": ni, "J": nj, "opt": r["OffsetOpt"], "selfwt": r["SelfWtOpt"]},
             "prediccion_cara": {k: round(v["cara"][k], 4) for k in ("I", "J")}, "prediccion_rmax": {k: round(v["rmax"][k], 4) for k in ("I", "J")},
             "tope_1pct": v["cara"]["tope_1pct"], "abstencion": v["abstencion"]}
        if v["abstencion"]:
            f["estado"] = "abstencion"
        else:
            ok = abs(v["cara"]["I"] - ni) <= TOL and abs(v["cara"]["J"] - nj) <= TOL
            f["estado"] = "acuerdo" if ok else "desacuerdo"
        f["rmax_acuerdo"] = abs(v["rmax"]["I"] - ni) <= TOL and abs(v["rmax"]["J"] - nj) <= TOL
        cuenta[f["estado"]] += 1; filas.append(f)
    suma_nat = sum(D(str(f["nativo"]["I"])) + D(str(f["nativo"]["J"])) for f in filas)
    pred_ok = [f for f in filas if f["estado"] != "abstencion"]
    abst = [f for f in filas if f["estado"] == "abstencion"]
    out = {"tarea": "masa_313_contraste", "prediccion_sha256": hashlib.sha256(Path(pred_path).read_bytes()).hexdigest(),
           "lectura_nativa_sha256": hashlib.sha256(LECT.read_bytes()).hexdigest(), "tolerancia_m": TOL, "conteo": cuenta,
           "rmax_acuerdos": sum(f["rmax_acuerdo"] for f in filas),
           "extremos_nativos_total_m": str(suma_nat),
           "extremos_predichos_no_abstenidos_m": round(sum(f["prediccion_cara"]["I"] + f["prediccion_cara"]["J"] for f in pred_ok), 4),
           "extremos_nativos_en_no_abstenidos_m": round(sum(f["nativo"]["I"] + f["nativo"]["J"] for f in pred_ok), 4),
           "extremos_nativos_en_abstenidos_m": round(sum(f["nativo"]["I"] + f["nativo"]["J"] for f in abst), 4),
           "peso_kn_por_m": str(GAMMA_AREA),
           "desacuerdos": [f for f in filas if f["estado"] == "desacuerdo"], "abstenciones": abst, "filas": filas}
    json.dump(out, open(salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(cuenta, "rmax", out["rmax_acuerdos"], "| nativo total", suma_nat, "| pred(no abst)", out["extremos_predichos_no_abstenidos_m"],
          "vs nat", out["extremos_nativos_en_no_abstenidos_m"], "| nat en abst", out["extremos_nativos_en_abstenidos_m"])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
