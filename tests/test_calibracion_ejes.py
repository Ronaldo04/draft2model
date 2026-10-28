"""Calibración por cadenas de cotas impresas y registro entre láminas sobre PDF vectorial sintético."""
import tempfile
import unittest
from pathlib import Path

import pymupdf

from draft2model import calibracion_ejes as ce

K = 0.0125  # m/pt de la lámina sintética


def lamina(path, ejes_m, cotas, *, extra=(), fila=60.0, homonimo=None):
    """Globos de eje arriba (y=20) y abajo (y=300), cotas en una fila y textos ajenos."""
    with pymupdf.open() as doc:
        page = doc.new_page(width=1800, height=320)
        for rot, x_m in ejes_m.items():
            x = 40 + x_m / K
            for y in (20, 300):
                page.insert_text((x - 3, y), rot, fontsize=8)
        for (a, b), texto in cotas.items():
            x = 40 + (ejes_m[a] + ejes_m[b]) / 2 / K
            page.insert_text((x - 8, fila), texto, fontsize=6)
        for x, y, texto in extra:
            page.insert_text((x, y), texto, fontsize=6)
        if homonimo:
            for y in (20, 300):
                page.insert_text((homonimo - 3, y), "B", fontsize=8)
        doc.save(path)


class CalibracionEjesTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.dir = Path(t.name)

    def test_cadena_k_residuos_y_tramo_sin_cota(self):
        pdf = self.dir / "a.pdf"
        ejes = {"1": 0.0, "2": 2.55, "3": 3.45, "4": 6.0}
        lamina(pdf, ejes, {("1", "2"): "2.55", ("2", "3"): ".90"}, extra=[(200, 150, "1"), (300, 160, "2.40")])
        e = ce.ejes_desde_texto(pdf, 1, list("1234"), "x")  # el «1» suelto no desplaza el eje
        c = ce.calibrar_cadena(pdf, 1, e)
        self.assertEqual(c["referencias"], 2)
        self.assertAlmostEqual(c["k_m_por_pt"], K, delta=K * 0.01)
        self.assertEqual([t.get("estado") for t in c["tramos"]], [None, None, "sin_referencia"])  # no se rellena
        self.assertLess(c["residuo_max_m"], 0.01)

    def test_rotulo_ambiguo_exige_declaracion(self):
        pdf = self.dir / "b.pdf"
        lamina(pdf, {"A": 0.0, "B": 3.15, "C": 5.0}, {("A", "B"): "3.15", ("B", "C"): "1.85"}, homonimo=40 + 2.0 / K)
        with self.assertRaisesRegex(ValueError, "ambigua"):
            ce.ejes_desde_texto(pdf, 1, list("ABC"), "x")
        e = ce.ejes_desde_texto(pdf, 1, list("ABC"), "x", fijar={"B": 40 + 3.15 / K})
        self.assertEqual(list(e["fijados"]), ["B"])
        self.assertEqual(ce.calibrar_cadena(pdf, 1, e)["referencias"], 2)

    def test_registro_entre_laminas_con_sentido_y_residuos(self):
        a, b = self.dir / "arq.pdf", self.dir / "est.pdf"
        arq = {"8": 0.0, "7": 2.55, "6": 3.45, "2": 15.0, "1": 20.0}
        lamina(a, arq, {("8", "7"): "2.55", ("7", "6"): ".90", ("6", "2"): "11.55", ("2", "1"): "5.00"})
        lamina(b, {"A": 0.0, "B": 2.55, "C": 3.45, "D": 5.5, "H": 15.0, "I": 20.0}, {})
        ea = ce.ejes_desde_texto(a, 1, ["8", "7", "6", "2", "1"], "x")
        ka = ce.calibrar_cadena(a, 1, ea)["k_m_por_pt"]
        eb = ce.ejes_desde_texto(b, 1, list("ABCDHI"), "x")
        r = ce.registrar(ea, ka, eb, {"A": "8", "B": "7", "H": "2", "I": "1"}, origen_a="8")
        self.assertEqual(r["sentido"], "igual")
        self.assertLess(r["residuo_max_m"], 0.02)
        self.assertAlmostEqual(r["posiciones_b_m"]["D"], 5.5, delta=0.03)  # eje sin correspondencia: derivado
        with self.assertRaises(ValueError):
            ce.registrar(ea, ka, eb, {"A": "8"}, origen_a="8")


if __name__ == "__main__":
    unittest.main()
