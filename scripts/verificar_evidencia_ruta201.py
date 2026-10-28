"""Comprobación de EVIDENCIA LOCAL de la ruta 201 (no es prueba de código: depende de tmp/, que no se distribuye).

Solo lectura: no abre ETABS, no llama a red, no modifica registros. Una copia limpia sin tmp/ no tiene esta evidencia;
por eso estas comprobaciones no forman parte de `unittest discover`.

  .venv/Scripts/python.exe scripts/verificar_evidencia_ruta201.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from draft2model import revision_modelo as rm  # noqa: E402
from draft2model import verificacion_modelo_guardado as v  # noqa: E402


def comprobar_198():
    n198 = ROOT / "tmp" / "n198"
    registro = json.loads((n198 / "registro.json").read_bytes())
    assert registro["guardado"]["sha256"] == "a597406d9dee11d82a30eee10eb7054c3a5f0f75cf79d3a8a319c0779a40b571"
    assert registro["analisis_ejecutado"] is False
    estado = rm.consultar(n198 / "fuentes" / "private", "sintetico-001", "81af6b76b72c4ce5a25db549136b5e98")
    assert estado["estado"] == "pendiente"
    comp = json.loads((ROOT / "tmp/r199/315191e6ed2c426ca095774b129d3c26/comparacion_unidades_200.json").read_bytes())
    assert (comp["estado"], len(comp["discrepancias"]), len(comp["incompletos"]), comp["cobertura"]["malla"]) == ("verificado", 0, 0, "completa")
    return "registro 198 pendiente; recomparación 200 verificada 0/0"


def comprobar_plan_194():
    plan = json.loads((ROOT / "tmp" / "n194" / "plan.json").read_bytes())
    exp = v.expectativa_desde_plan(plan)
    assert len(exp["inventario"]) == 294
    assert not [x for x in exp["inventario"] if x["cobertura"] == "sin_lector"]
    assert {h: len(x["triangulos"]) for h, x in exp["malla"]["hosts"].items()} == {"S1": 14, "S2": 22}
    return "plan real 194: 294 operaciones, 0 sin lector"


def comprobar_ensayos_l2_r3():
    out = []
    for nombre in ("l2", "r3"):
        reg = json.loads((ROOT / "tmp" / nombre / "registro.json").read_bytes())
        assert reg["resultado_global"]["aceptado"] is True, nombre
        assert any(f.get("estado") == "equilibrio_estricto" for k, f in reg["fases"].items() if k.startswith("equilibrio_api")), nombre
        out.append(f"{nombre}: aceptado, equilibrio estricto API")
    return "; ".join(out)


def main():
    resultados, codigo = {}, 0
    for nombre, f in (("198", comprobar_198), ("194", comprobar_plan_194), ("l2_r3", comprobar_ensayos_l2_r3)):
        try:
            resultados[nombre] = {"estado": "ok", "detalle": f()}
        except FileNotFoundError as exc:
            resultados[nombre] = {"estado": "evidencia_ausente", "detalle": str(exc)}
            codigo = 2
        except AssertionError as exc:
            resultados[nombre] = {"estado": "contradicha", "detalle": repr(exc)}
            codigo = 1
    print(json.dumps(resultados, ensure_ascii=True, indent=2))
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
