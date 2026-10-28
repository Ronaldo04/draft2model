"""314: contraste posterior, por extremo y por viga, de R-cara (313), R-ETABS (314) y la variante de sensibilidad R-ETABS-B3cero
(muros no intervienen: 0 en extremos sin columna; declarada tras clasificar la geometría, antes de este contraste, solo informativa).
Misma población (45 vigas, 90 extremos) y tolerancia ±0,0005 m. Uso: python contraste_314.py PRED313 PRED314 SALIDA
"""
import hashlib, json, sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
LECT = RAIZ / "data/private/pueblo-libre-002/lecturas_analisis/6da62ea363484498a3e13315c99b328a/respuesta.json"
TOL = 0.0005


def main(p313, p314, salida):
    a = {v["viga"]: v for v in json.load(open(p313, encoding="utf-8"))["vigas"]}
    b = {v["viga"]: v for v in json.load(open(p314, encoding="utf-8"))["vigas"]}
    res = json.loads(LECT.read_text(encoding="utf-8"))
    nat = {r["UniqueName"]: r for t in res["datos"]["tablas"] if t["clave"] == "Frame Assignments - End Length Offsets" for r in t["filas"]}
    ext = {"R-cara_313": Counter(), "R-ETABS_314": Counter(), "R-ETABS-B3cero": Counter()}
    vig = {k: Counter() for k in ext}; filas = []
    for name in sorted(b):
        va, vb, n = a[name], b[name], nat[name]
        nv = {"I": float(n["OffsetI"]), "J": float(n["OffsetJ"])}
        beam_abst_b = any(x.startswith("B2") or x.startswith("B4: viga") for x in vb["abstencion"])
        fila = {"viga": name, "L_m": round(vb["L_m"], 4), "nativo": nv, "extremos": {}}
        estados_v = {k: [] for k in ext}
        for e313, e314 in zip(va["extremos"], vb["extremos"]):
            lado = e314["lado"]
            ab314 = beam_abst_b or any(x.startswith(("B1:" + lado, "B3:" + lado, "B4:" + lado)) for x in vb["abstencion"])
            ab313 = bool(va["abstencion"]) and any((":" + lado + ":") in x or x.startswith("A") and (":" + lado) in x for x in va["abstencion"])
            pr = {"R-cara_313": None if va["abstencion"] and ab313 else va["cara"][lado],
                  "R-ETABS_314": None if ab314 else e314["offset_m"],
                  "R-ETABS-B3cero": None if (beam_abst_b or any(x.startswith(("B1:" + lado, "B4:" + lado)) for x in vb["abstencion"])) else e314["offset_m"]}
            d = {}
            for k, v in pr.items():
                st = "abstencion" if v is None else ("acuerdo" if abs(v - nv[lado]) <= TOL else "desacuerdo")
                ext[k][st] += 1; estados_v[k].append(st); d[k] = {"pred": None if v is None else round(v, 4), "estado": st}
            d["salvedad_muro"] = e314["salvedad_muro"]; d["columnas_inferiores"] = [c["columna"] for c in e314["columnas_inferiores"]]
            fila["extremos"][lado] = d
        for k, sts in estados_v.items():
            vig[k]["abstencion" if "abstencion" in sts else ("acuerdo" if all(s == "acuerdo" for s in sts) else "desacuerdo")] += 1
        fila["abstencion_314"] = vb["abstencion"]; filas.append(fila)
    out = {"tarea": "extremos_314_contraste", "ensayo_ciego": False, "tolerancia_m": TOL,
           "lectura_nativa_sha256": hashlib.sha256(LECT.read_bytes()).hexdigest(),
           "poblacion": {"vigas": len(filas), "extremos": 2 * len(filas)},
           "por_extremo": {k: dict(v) for k, v in ext.items()}, "por_viga": {k: dict(v) for k, v in vig.items()}, "filas": filas}
    json.dump(out, open(salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"por_extremo": out["por_extremo"], "por_viga": out["por_viga"]}, ensure_ascii=False))


if __name__ == "__main__":
    main(*sys.argv[1:4])
