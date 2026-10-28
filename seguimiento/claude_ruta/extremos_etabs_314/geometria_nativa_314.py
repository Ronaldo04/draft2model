"""314: diagnóstico POSTERIOR de geometría. Compara longitudes y coordenadas de las vigas VS del plan con la geometría nativa
archivada (relectura 09d1, N_mm) y muestra, para las vigas B2 (suma ≥ L), offsets brutos R-ETABS frente a nativos.
No es entrada de ninguna regla. Uso: python geometria_nativa_314.py PRED314 CONTRASTE314 SALIDA
"""
import hashlib, json, math, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
GEO = RAIZ / "tmp/recorrido_09d1/lectura/2eca39b2592c4c1d8a0cdb800eb06ddf/respuesta.json"
PLAN = RAIZ / "data/private/pueblo-libre-002/modelos_construidos/0f37271307b6449c89c458c60a1640c7/plan.json"
sys.path.insert(0, str(RAIZ / "seguimiento/claude_ruta/prediccion_masa_313"))
from predictor_313 import cargar_modelo  # noqa: E402


def main(p314, c314, salida):
    g = json.loads(GEO.read_text(encoding="utf-8")); lec = g["datos"]["lecturas"]
    assert lec["unidades"] == "N_mm_C"
    m = cargar_modelo(json.loads(PLAN.read_text(encoding="utf-8")))
    pred = {v["viga"]: v for v in json.load(open(p314, encoding="utf-8"))["vigas"]}
    con = {f["viga"]: f for f in json.load(open(c314, encoding="utf-8"))["filas"]}
    filas, max_dl, max_dp = [], 0.0, 0.0
    for name, v in sorted(pred.items()):
        pa, pb = (m["puntos"][p] for p in m["frames"][name]["p"])
        na, nb = ([c / 1000 for c in lec["puntos"]["coordenadas"][p]] for p in lec["frames"]["puntos"][name])
        Lp, Ln = math.dist(pa, pb), math.dist(na, nb)
        dp = max(max(abs(x - y) for x, y in zip(pa, na)), max(abs(x - y) for x, y in zip(pb, nb)))
        max_dl, max_dp = max(max_dl, abs(Lp - Ln)), max(max_dp, dp)
        f = {"viga": name, "L_plan_m": round(Lp, 6), "L_nativa_m": round(Ln, 6), "dL_m": round(Lp - Ln, 9), "max_dcoord_m": round(dp, 9),
             "seccion_nativa": lec["frames"]["secciones"][name], "insercion_nativa": lec["frames"].get("insercion", {}).get(name)}
        if any(a.startswith("B2") for a in v["abstencion"]):
            f["B2"] = {"bruto_ETABS": {"I": v["etabs"]["I"], "J": v["etabs"]["J"]}, "nativo": con[name]["nativo"],
                       "relacion_nativo_suma_sobre_L": round((con[name]["nativo"]["I"] + con[name]["nativo"]["J"]) / Lp, 4)}
        filas.append(f)
    out = {"tarea": "extremos_314_geometria_nativa", "fuente_geometria": str(GEO.relative_to(RAIZ)), "sha256_fuente": hashlib.sha256(GEO.read_bytes()).hexdigest(),
           "sha256_edb_relectura_antes": g["datos"].get("sha256_antes"), "max_abs_dL_m": max_dl, "max_abs_dcoord_m": max_dp,
           "vigas_B2": [f for f in filas if "B2" in f], "filas": filas}
    json.dump(out, open(salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("max|dL|", max_dl, "max|dcoord|", max_dp)
    for f in out["vigas_B2"]:
        print(f["viga"], f["L_plan_m"], f["L_nativa_m"], f["B2"]["bruto_ETABS"], f["B2"]["nativo"], f["B2"]["relacion_nativo_suma_sobre_L"])


if __name__ == "__main__":
    main(*sys.argv[1:4])
