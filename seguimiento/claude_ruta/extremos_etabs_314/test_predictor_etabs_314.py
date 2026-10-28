"""314: pruebas sintéticas de R-ETABS (no usan expediente ni datos del solver).
Ejecutar: python -m unittest seguimiento/claude_ruta/extremos_etabs_314/test_predictor_etabs_314.py
"""
import sys, unittest
from pathlib import Path
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI)); sys.path.insert(0, str(AQUI.parent / "prediccion_masa_313"))
import predictor_etabs_314 as E  # noqa: E402
from predictor_313 import cargar_modelo  # noqa: E402
from test_predictor_313 import plan, SEC  # noqa: E402  (constructor de mini-planes sintéticos de 313, sin cambios)


def una(p):
    return {f["viga"]: f for f in E.predecir(cargar_modelo(p))}


class RETABS(unittest.TestCase):
    def test_columna_inferior_cuenta_superior_no(self):
        pts = {"a": (0, 0, 3), "b": (3, 0, 3), "a0": (0, 0, 0), "b6": (3, 0, 6)}
        f = una(plan(pts, {"VS1": ("a", "b", "VS"), "C1": ("a0", "a", "CY"), "C2": ("b", "b6", "CX")}, SEC))["VS1"]
        self.assertAlmostEqual(f["etabs"]["I"], 0.20)     # columna inferior CY: max(0.15,0.40)/2, sin proyección
        self.assertEqual(f["etabs"]["J"], 0.0)            # solo columna superior: se ignora
        self.assertFalse(f["abstencion"])

    def test_otras_vigas_no_cuentan(self):
        pts = {"a": (0, 0, 3), "b": (2, 0, 3), "d": (2, 2, 3)}
        f = una(plan(pts, {"VS1": ("a", "b", "VS"), "VS3": ("b", "d", "VS")}, SEC))["VS1"]
        self.assertEqual(f["etabs"]["J"], 0.0); self.assertFalse(f["abstencion"])

    def test_mayor_columna_inferior(self):
        sec = dict(SEC, CBIG=(0.75, 0.20))
        f = una(plan({"a": (0, 0, 3), "b": (3, 0, 3), "a0": (0, 0, 0)}, {"VS1": ("a", "b", "VS"), "C1": ("a0", "a", "CBIG")}, sec))["VS1"]
        self.assertAlmostEqual(f["etabs"]["I"], 0.375)

    def test_abstenciones(self):
        pts = {"a": (0, 0, 3), "b": (3, 0, 3), "a0": (0, 0, 0), "w1": (3, 1, 3), "w2": (3, 1, 0)}
        f = una(plan(pts, {"VS1": ("a", "b", "VS"), "C1": ("a0", "a", "CX")}, SEC, insercion=("C1",), areas=[("b", "w1", "w2")]))["VS1"]
        self.assertEqual(sorted(x.split(":")[0] for x in f["abstencion"]), ["B1", "B3"])
        pts = {"a": (0, 0, 3), "b": (0.3, 0, 3), "a0": (0, 0, 0), "b0": (0.3, 0, 0)}
        g = una(plan(pts, {"VS1": ("a", "b", "VS"), "C1": ("a0", "a", "CY"), "C2": ("b0", "b", "CY")}, SEC))["VS1"]
        self.assertTrue(any(x.startswith("B2") for x in g["abstencion"]))   # 0.2+0.2 >= 0.3: límite no documentado

    def test_columna_y_muro_salvedad(self):
        pts = {"a": (0, 0, 3), "b": (3, 0, 3), "a0": (0, 0, 0), "w1": (0, 1, 3), "w2": (0, 1, 0)}
        f = una(plan(pts, {"VS1": ("a", "b", "VS"), "C1": ("a0", "a", "CX")}, SEC, areas=[("a", "w1", "w2")]))["VS1"]
        self.assertFalse(f["abstencion"]); self.assertTrue(f["extremos"][0]["salvedad_muro"]); self.assertAlmostEqual(f["etabs"]["I"], 0.20)

    def test_independencia_estatica(self):
        src = (AQUI / "predictor_etabs_314.py").read_text(encoding="utf-8")
        for prohibido in ("lecturas_analisis", "respuesta.json", "OffsetI", "Weight", "libro_masa", "0.002", "End Length Offsets"):
            self.assertNotIn(prohibido, src)


if __name__ == "__main__":
    unittest.main()
