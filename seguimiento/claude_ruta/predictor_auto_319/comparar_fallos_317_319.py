"""319: los 4 casos de REVISION_PREDICTOR_318 con 317 (intacto) y 319: 317 da totales, 319 no. Uso: python comparar_fallos_317_319.py"""
import copy, json, sys
from pathlib import Path
A = Path(__file__).resolve().parent
sys.path.insert(0, str(A)); sys.path.insert(0, str(A.parent / "predictor_auto_317"))
import predictor_auto_317 as P317, predictor_auto_319 as P319  # noqa: E402
from test_validacion_319 import plan, base, CFG, op  # noqa: E402
p_dup = plan(*base()); p_dup["operaciones"].insert(1, copy.deepcopy(p_dup["operaciones"][0]))
p_neg = plan(*base())
for o in p_neg["operaciones"]:
    if o["metodo"] == "cPropMaterial.SetWeightAndMass": o["argumentos"][2]["valor"] = -25.0
casos = {"viga_fantasma": (plan(*base()), ["VIGA", "FANTASMA"]), "punto_duplicado": (p_dup, ["VIGA"]),
         "extremos_no_auto": (plan(*base(), extra=[op("cFrameObj.SetEndLengthOffset", Name={"ref": "frame:VIGA"}, AutoOffset=False, Length1=0.3, Length2=0.2, RZ=0.0)]), ["VIGA"]),
         "peso_negativo": (p_neg, ["VIGA"])}
out = {k: {"317_totales": P317.predecir(p, dict(CFG, vigas=v))["totales"], "319_totales": P319.predecir(p, dict(CFG, vigas=v))["totales"]} for k, (p, v) in casos.items()}
print(json.dumps(out, ensure_ascii=False))
assert all(r["317_totales"] is not None and r["319_totales"] is None for r in out.values())
