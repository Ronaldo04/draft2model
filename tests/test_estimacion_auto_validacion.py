"""321 (núcleo; copia de 319): pruebas negativas. Reproducen los 4 fallos de REVISION_PREDICTOR_318 y casos afines; comprueban AUSENCIA de totales y de
cobertura falsa, no solo la presencia de un mensaje. Ejecutar: python -m unittest seguimiento/claude_ruta/nucleo_auto_321/pruebas/test_nucleo_validacion_321.py
"""
import copy, sys, unittest
from pathlib import Path
from draft2model import estimacion_extremos_auto as _E  # noqa: E402
class P:
    predecir = staticmethod(_E.nucleo)
from tests.test_estimacion_auto_nucleo import plan, base, CFG  # noqa: E402


def op(metodo, **args):
    return {"metodo": metodo, "argumentos": [{"nombre": k, "valor": v} for k, v in args.items()]}


def sin_totales(t, out, pedidas=None):
    t.assertIsNone(out["totales"])
    if pedidas is not None:
        t.assertEqual(out["cobertura"]["pedidas"], pedidas)
        t.assertLess(out["cobertura"]["completas"], pedidas)


class Fallos318(unittest.TestCase):
    def test_control_valido_tiene_totales(self):
        out = P.predecir(plan(*base()), dict(CFG, vigas=["VIGA"]))
        self.assertIsNotNone(out["totales"]); self.assertEqual(out["cobertura"], {"pedidas": 1, "completas": 1, "abstenidas": 0})

    def test_viga_fantasma_permanece_en_denominador(self):
        out = P.predecir(plan(*base()), dict(CFG, vigas=["VIGA", "FANTASMA"]))
        sin_totales(self, out, pedidas=2)
        self.assertEqual(next(v for v in out["vigas"] if v["viga"] == "FANTASMA")["abstencion"], ["no existe en el plan"])

    def test_punto_duplicado_bloquea(self):
        p = plan(*base()); p["operaciones"].insert(1, copy.deepcopy(p["operaciones"][0]))   # repite el punto 'a'
        out = P.predecir(p, dict(CFG, vigas=["VIGA"]))
        sin_totales(self, out, pedidas=1); self.assertTrue(any("duplicado" in x for x in out["problemas_plan"]))
        self.assertIsNone(out["vigas"][0]["offsets"])

    def test_offsets_explicitos_no_auto(self):
        p = plan(*base(), extra=[op("cFrameObj.SetEndLengthOffset", Name={"ref": "frame:VIGA"}, AutoOffset=False, Length1=0.3, Length2=0.2, RZ=0.0)])
        out = P.predecir(p, dict(CFG, vigas=["VIGA"]))
        sin_totales(self, out, pedidas=1); self.assertIn("AutoOffset", " ".join(out["vigas"][0]["abstencion"]))
        p = plan(*base(), extra=[op("cFrameObj.SetEndLengthOffset", Name={"ref": "frame:CI"}, AutoOffset=False, Length1=0.1, Length2=0.0, RZ=0.0)])
        sin_totales(self, P.predecir(p, dict(CFG, vigas=["VIGA"])), pedidas=1)          # también en la columna de apoyo
        p = plan(*base(), extra=[op("cFrameObj.SetEndLengthOffset", Name={"ref": "frame:VIGA"}, AutoOffset=True, Length1=0.0, Length2=0.0, RZ=0.0)])
        self.assertIsNotNone(P.predecir(p, dict(CFG, vigas=["VIGA"]))["totales"])       # Auto explícito y nulo: coherente

    def test_peso_negativo_y_no_finito(self):
        for val in (-25.0, float("nan"), float("inf")):
            p = plan(*base())
            for o in p["operaciones"]:
                if o["metodo"] == "cPropMaterial.SetWeightAndMass":
                    o["argumentos"][2]["valor"] = val
            out = P.predecir(p, dict(CFG, vigas=["VIGA"]))
            sin_totales(self, out, pedidas=1); self.assertIsNone(out["vigas"][0]["descuento_peso"])
        p = plan(*base())
        for o in p["operaciones"]:
            if o["metodo"] == "cPropMaterial.SetWeightAndMass":
                o["argumentos"][2]["valor"] = 0.0
        out = P.predecir(p, dict(CFG, vigas=["VIGA"]))
        self.assertEqual(out["vigas"][0]["descuento_peso"]["kN"], 0.0); self.assertTrue(out["vigas"][0]["descuento_peso"]["peso_cero_declarado"])


class Afines(unittest.TestCase):
    def test_seleccion_mal_formada(self):
        for vigas in ("VIGA", 3, {"VIGA": 1}):
            out = P.predecir(plan(*base()), dict(CFG, vigas=vigas))
            self.assertEqual(out["estado"], "abstencion_global"); self.assertIsNone(out["totales"])
        cfg = dict(CFG); cfg.pop("vigas")
        self.assertEqual(P.predecir(plan(*base()), cfg)["estado"], "abstencion_global")
        out = P.predecir(plan(*base()), dict(CFG, vigas=[]))
        self.assertIsNone(out["totales"]); self.assertEqual(out["cobertura"]["pedidas"], 0)
        out = P.predecir(plan(*base()), dict(CFG, vigas=["VIGA", "VIGA", None]))
        sin_totales(self, out, pedidas=3)

    def test_argumento_y_referencia_duplicados_o_invalidos(self):
        p = plan(*base()); p["operaciones"][0]["argumentos"].append({"nombre": "X", "valor": 9.0})
        sin_totales(self, P.predecir(p, dict(CFG, vigas=["VIGA"])))
        p = plan(*base())
        for o in p["operaciones"]:
            if o["metodo"] == "cFrameObj.AddByPoint" and o["argumentos"][3]["valor"] == "VIGA":
                o["argumentos"][1]["valor"] = {"ref": "punto:NO_EXISTE"}
        out = P.predecir(p, dict(CFG, vigas=["VIGA"])); sin_totales(self, out, pedidas=1)
        p = plan(*base(), extra=[copy.deepcopy(o) for o in plan(*base())["operaciones"] if o["metodo"] == "cPropFrame.SetRectangle"][:1])
        sin_totales(self, P.predecir(p, dict(CFG, vigas=["VIGA"])))                       # sección duplicada

    def test_dimension_negativa_en_miembro_objetivo(self):
        sec = {"V": (-0.40, 0.20), "C1": (0.50, 0.25)}
        out = P.predecir(plan(*base(), sec=sec), dict(CFG, vigas=["VIGA"]))
        sin_totales(self, out, pedidas=1); self.assertIn("viga VIGA", " ".join(out["vigas"][0]["abstencion"]))

    def test_modificadores_y_cambios_no_cubiertos(self):
        extras = [op("cFrameObj.SetModifiers", Name={"ref": "frame:VIGA"}, Value=[1, 1, 1, 1, 1, 1, 0.5, 0.5]),
                  op("cPropFrame.SetModifiers", Name="V", Value=[1, 1, 1, 1, 1, 1, 1, 2]),
                  op("cFrameObj.SetSection", Name={"ref": "frame:VIGA"}, PropName="C1"),
                  op("cFrameObj.SetMass", Name={"ref": "frame:VIGA"}, MassOverL=0.1),
                  op("cFrameObj.SetReleases", Name={"ref": "frame:VIGA"}),
                  op("cFrameObj.SetInsertionPoint", Name={"ref": "frame:VIGA"}),
                  op("cFrameObj.SetLocalAxes", Name={"ref": "frame:VIGA"}, Ang=30.0),
                  op("cFrameObj.SetLocalAxesAdvanced", Name={"ref": "frame:VIGA"})]
        for e in extras:
            out = P.predecir(plan(*base(), extra=[e]), dict(CFG, vigas=["VIGA"]))
            sin_totales(self, out, pedidas=1)
            self.assertTrue(out["vigas"][0]["abstencion"], e["metodo"])

    def test_unidades_del_plan_y_plan_mal_formado(self):
        p = plan(*base()); p["unidades_etabs"] = "N_mm_C"
        self.assertEqual(P.predecir(p, dict(CFG, vigas=None))["estado"], "abstencion_global")
        for malo in (None, [], {"operaciones": "x"}, {"sin": 1}):
            out = P.predecir(malo, dict(CFG, vigas=None))
            self.assertEqual(out["estado"], "abstencion_global"); self.assertIsNone(out["totales"])
        self.assertIn("versión", P.predecir(None, dict(CFG, etabs_version="20"))["motivos"][0])   # config antes que plan

    def test_nunca_descuentos_negativos(self):
        out = P.predecir(plan(*base()), dict(CFG, vigas=None))
        self.assertTrue(all(v["descuento_peso"]["kN"] >= 0 for v in out["vigas"] if v.get("descuento_peso")))


if __name__ == "__main__":
    unittest.main()
