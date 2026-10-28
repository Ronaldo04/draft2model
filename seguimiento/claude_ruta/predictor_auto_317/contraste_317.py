"""317: contraste SEPARADO y posterior de PREDICCION_PILOTO_317.json con la lectura nativa archivada 6da62ea3 (tabla End Length Offsets)
y la tabla de materiales 461c7510 (peso VS). No modifica la predicción. Uso: python contraste_317.py PRED SALIDA"""
import hashlib, json, sys
from decimal import Decimal as D
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[3]
LECT = RAIZ / "data/private/pueblo-libre-002/lecturas_analisis/6da62ea363484498a3e13315c99b328a/respuesta.json"
MAT = RAIZ / "data/private/pueblo-libre-002/lecturas_analisis/461c751056c74acaa6d738b29f4df633/respuesta.json"
TOL = 0.0005
pred = json.load(open(sys.argv[1], encoding="utf-8"))
nat = {r["UniqueName"]: r for t in json.loads(LECT.read_text(encoding="utf-8"))["datos"]["tablas"] if t["clave"] == "Frame Assignments - End Length Offsets" for r in t["filas"]}
cnt = {"acuerdo": 0, "desacuerdo": 0, "abstencion": 0}; errores = []; filas = []
for v in pred["vigas"]:
    n = nat[v["viga"]]
    for lado, k in (("I", "OffsetI"), ("J", "OffsetJ")):
        ob = float(n[k])
        if v["offsets"] is None:
            st, e = "abstencion", None
        else:
            e = v["offsets"][lado] - ob; st = "acuerdo" if abs(e) <= TOL else "desacuerdo"; errores.append(abs(e))
        cnt[st] += 1; filas.append({"viga": v["viga"], "lado": lado, "pred": None if v["offsets"] is None else round(v["offsets"][lado], 6), "nativo": ob, "error_m": None if e is None else round(e, 6), "estado": st,
                                    "regla_exceso": v.get("regla_exceso")})
nat_vs = sum((D(r["Weight"]) for t in json.loads(MAT.read_text(encoding="utf-8"))["datos"]["tablas"] if t["clave"] == "Material List by Section Property" for r in t["filas"] if r["Section"] == "VS-15X30"), D(0))
bruto = sum(D(str(v["L_m"])) * D(str(v["descuento_peso"]["area_m2"])) * D(str(v["descuento_peso"]["gamma_kN_m3"])) for v in pred["vigas"] if v.get("descuento_peso"))
neto_pred = bruto - D(str(pred["totales"]["descuento_kN"])) if pred.get("totales") else None
out = {"tarea": "predictor_317_contraste", "ensayo_ciego": False, "exposicion_previa": "313/314/315/316 conocidos; tolerancia = escenario declarado",
       "prediccion_sha256": hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest(), "lectura_sha256": hashlib.sha256(LECT.read_bytes()).hexdigest(),
       "poblacion_extremos": len(filas), "conteo": cnt, "error_max_m": max(errores) if errores else None,
       "peso_VS": {"bruto_kN": str(bruto), "neto_predicho_kN": str(neto_pred), "tabla_nativa_kN": str(nat_vs), "diferencia_kN": str(neto_pred - nat_vs) if neto_pred is not None else None,
                   "nota": "tabla nativa con 4 decimales"},
       "desacuerdos": [f for f in filas if f["estado"] == "desacuerdo"], "filas": filas}
Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(cnt, "error_max", out["error_max_m"], out["peso_VS"])
