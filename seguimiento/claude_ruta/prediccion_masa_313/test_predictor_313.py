"""313: pruebas representativas del predictor con mini-planes SINTÉTICOS (no usan el expediente ni datos del solver).
Ejecutar: python -m unittest seguimiento/claude_ruta/prediccion_masa_313/test_predictor_313.py
"""
import math, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import predictor_313 as P  # noqa: E402


def plan(puntos, frames, secciones, insercion=(), areas=()):
    ops = [{"metodo": "cPointObj.AddCartesian", "argumentos": [{"nombre": "X", "valor": x}, {"nombre": "Y", "valor": y}, {"nombre": "Z", "valor": z},
            {"nombre": "UserName", "valor": n}]} for n, (x, y, z) in puntos.items()]
    ops += [{"metodo": "cPropFrame.SetRectangle", "argumentos": [{"nombre": "Name", "valor": n}, {"nombre": "T3", "valor": t3}, {"nombre": "T2", "valor": t2}]}
            for n, (t3, t2) in secciones.items()]
    ops += [{"metodo": "cFrameObj.AddByPoint", "argumentos": [{"nombre": "Point1", "valor": {"ref": "punto:" + a}}, {"nombre": "Point2", "valor": {"ref": "punto:" + b}},
             {"nombre": "PropName", "valor": s}, {"nombre": "UserName", "valor": n}]} for n, (a, b, s) in frames.items()]
    ops += [{"metodo": "cFrameObj.SetInsertionPoint", "argumentos": [{"nombre": "Name", "valor": {"ref": "frame:" + n}}]} for n in insercion]
    ops += [{"metodo": "cAreaObj.AddByPoint", "argumentos": [{"nombre": "Point", "valor": [{"ref": "punto:" + p} for p in pts]}]} for pts in areas]
    return {"operaciones": ops}


SEC = {"VS": (0.30, 0.15), "CX": (0.40, 0.15), "CY": (0.15, 0.40)}


def una(p):
    return {f["viga"]: f for f in P.predecir(P.cargar_modelo(p))}


class Predictor(unittest.TestCase):
    def test_orientacion_columna(self):
        # viga en X entre columna CX (0.40 en X) y CY (0.15 en X): caras 0.20 y 0.075
        pts = {"a": (0, 0, 0), "b": (3, 0, 0), "a0": (0, 0, -3), "b0": (3, 0, -3)}
        f = una(plan(pts, {"VS1": ("a", "b", "VS"), "C1": ("a0", "a", "CX"), "C2": ("b0", "b", "CY")}, SEC))["VS1"]
        self.assertAlmostEqual(f["cara"]["I"], 0.20); self.assertAlmostEqual(f["cara"]["J"], 0.075); self.assertFalse(f["abstencion"])
        # la misma viga girada a Y intercambia las dimensiones usadas
        pts = {"a": (0, 0, 0), "b": (0, 3, 0), "a0": (0, 0, -3), "b0": (0, 3, -3)}
        f = una(plan(pts, {"VS1": ("a", "b", "VS"), "C1": ("a0", "a", "CX"), "C2": ("b0", "b", "CY")}, SEC))["VS1"]
        self.assertAlmostEqual(f["cara"]["I"], 0.075); self.assertAlmostEqual(f["cara"]["J"], 0.20)

    def test_viga_colineal_sin_apoyo_y_perpendicular(self):
        pts = {"a": (0, 0, 0), "b": (2, 0, 0), "c": (4, 0, 0), "d": (2, 2, 0)}
        f = una(plan(pts, {"VS1": ("a", "b", "VS"), "VS2": ("b", "c", "VS"), "VS3": ("b", "d", "VS")}, SEC))
        self.assertAlmostEqual(f["VS1"]["cara"]["J"], 0.075)        # cara lateral de la perpendicular VS3 (T2/2)
        self.assertAlmostEqual(f["VS1"]["cara"]["I"], 0.0)          # extremo libre
        pts2 = {"a": (0, 0, 0), "b": (2, 0, 0), "c": (4, 0, 0)}
        g = una(plan(pts2, {"VS1": ("a", "b", "VS"), "VS2": ("b", "c", "VS")}, SEC))
        self.assertEqual(g["VS1"]["cara"]["J"], 0.0)                 # colineal: continuidad, no apoyo

    def test_oblicua(self):
        c = math.cos(math.radians(30)); s = math.sin(math.radians(30))
        pts = {"a": (0, 0, 0), "b": (3 * c, 3 * s, 0), "a0": (0, 0, -3)}
        f = una(plan(pts, {"VS1": ("a", "b", "VS"), "C1": ("a0", "a", "CX")}, SEC))["VS1"]
        self.assertAlmostEqual(f["cara"]["I"], min(0.20 / c, 0.075 / s))

    def test_tope_1pct(self):
        pts = {"a": (0, 0, 0), "b": (0.2, 0, 0), "a0": (0, 0, -3), "b0": (0.2, 0, -3)}
        f = una(plan(pts, {"VS1": ("a", "b", "VS"), "C1": ("a0", "a", "CX"), "C2": ("b0", "b", "CX")}, SEC))["VS1"]
        self.assertTrue(f["cara"]["tope_1pct"]); self.assertAlmostEqual(f["cara"]["suma"], 0.99 * 0.2)
        self.assertAlmostEqual(f["cara"]["I"], f["cara"]["J"])      # reducción proporcional

    def test_abstenciones_ambiguas(self):
        pts = {"a": (0, 0, 0), "b": (3, 0, 0), "a0": (0, 0, -3), "w1": (3, 1, 0), "w2": (3, 1, -3)}
        f = una(plan(pts, {"VS1": ("a", "b", "VS"), "C1": ("a0", "a", "CX")}, SEC, insercion=("C1",), areas=[("b", "w1", "w2")]))["VS1"]
        tipos = sorted(x.split(":")[0] for x in f["abstencion"])
        self.assertEqual(tipos, ["A1", "A2"])

    def test_seccion_distinta_en_columna(self):
        sec = dict(SEC, CBIG=(0.75, 0.20))
        pts = {"a": (0, 0, 0), "b": (3, 0, 0), "a0": (0, 0, -3)}
        f = una(plan(pts, {"VS1": ("a", "b", "VS"), "C1": ("a0", "a", "CBIG")}, sec))["VS1"]
        self.assertAlmostEqual(f["cara"]["I"], 0.375); self.assertAlmostEqual(f["rmax"]["I"], 0.375)

    def test_independencia_estatica(self):
        src = (Path(__file__).resolve().parent / "predictor_313.py").read_text(encoding="utf-8")
        for prohibido in ("lecturas_analisis", "respuesta.json", "OffsetI", "Weight", "libro_masa", "End Length Offsets"):
            self.assertNotIn(prohibido, src)


if __name__ == "__main__":
    unittest.main()
