"""Inventario vectorial: primitivas re/qu, componentes por grosor, franjas paralelas y ajuste a sección conocida."""
import tempfile
import unittest
from pathlib import Path

import pymupdf

from draft2model import inventario_vectorial as iv

K = 0.0125  # m/pt


def plano(path):
    with pymupdf.open() as doc:
        page = doc.new_page(width=600, height=400)
        # Columna 0,15×0,40 como rectángulo primitivo (trazo fino), adosada a una franja de cimiento.
        page.draw_rect(pymupdf.Rect(100, 100, 100 + 0.40 / K, 100 + 0.15 / K), width=0.84)
        # Franja de cimiento de 0,50 m: dos líneas paralelas de 4 m.
        for y in (200, 200 + 0.50 / K):
            page.draw_line((50, y), (50 + 4.0 / K, y), width=0.84)
        # Placa en trazo grueso (polilínea cerrada 0,10×1,35) y una «letra» dibujada con trazos cortos.
        x, y = 400, 80
        pts = [(x, y), (x + 0.10 / K, y), (x + 0.10 / K, y + 1.35 / K), (x, y + 1.35 / K), (x, y)]
        for a, b in zip(pts, pts[1:]):
            page.draw_line(a, b, width=1.32)
        page.draw_line((450, 300), (452, 308), width=1.32)
        page.draw_line((452, 308), (454, 300), width=1.32)
        doc.save(path)


class InventarioVectorialTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.pdf = Path(t.name) / "p.pdf"
        plano(self.pdf)
        self.todos = iv.segmentos(self.pdf, 1, (0, 0, 600, 400))

    def test_primitivas_se_descomponen_en_lados(self):
        re = [s for s in self.todos if s["tipo"] == "re"]
        self.assertEqual(len(re), 4)

    def test_componentes_separan_elementos_de_trazos_de_rotulo(self):
        gruesos = iv.segmentos(self.pdf, 1, (0, 0, 600, 400), grosor=1.32)
        comps = iv.componentes(gruesos)
        tam = sorted(max(c["caja_pt"][2] - c["caja_pt"][0], c["caja_pt"][3] - c["caja_pt"][1]) * K for c in comps)
        self.assertEqual(len(comps), 2)
        self.assertLess(tam[0], 0.25)            # letra: no es elemento
        self.assertAlmostEqual(tam[1], 1.35, places=3)

    def test_franja_paralela_eje_y_ancho(self):
        finos = [s for s in self.todos if s["tipo"] == "l" and abs(s["grosor"] - 0.84) < 0.02]
        f = iv.franjas_paralelas(finos, ancho_pt=(0.35 / K, 0.55 / K), solape_min_pt=0.5 / K)
        self.assertEqual(len(f), 1)
        self.assertAlmostEqual(f[0]["ancho_pt"] * K, 0.50, places=6)
        self.assertAlmostEqual(f[0]["eje_pt"], 200 + 0.25 / K)

    def test_ajuste_a_seccion_y_rechazo_si_no_concuerda(self):
        r = iv.ajustar_rectangulo(self.todos, (110, 105), (0.15, 0.40), K)
        self.assertEqual((r["estado"], r["dim_m"], r["orientacion"]), ("ajustado", [0.4, 0.15], "x_largo"))
        self.assertEqual(iv.ajustar_rectangulo(self.todos, (110, 105), (0.15, 0.60), K)["estado"], "no_ajustado")
        self.assertEqual(iv.ajustar_rectangulo(self.todos, (590, 390), (0.15, 0.40), K)["estado"], "no_ajustado")



def _seg(p, q):
    return {"p": p, "q": q, "largo": ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5, "grosor": 1.0}


class AdversasR243Tests(unittest.TestCase):
    """R243-01/02: contraejemplos de Codex y variantes de frontera."""
    H = [_seg((0, 0), (32, 0)), _seg((0, 12), (32, 12))]  # dos horizontales 0,40 m separadas 0,15 m (k = 0,0125)

    def ajustar(self, extra):
        return iv.ajustar_rectangulo(self.H + extra, (16, 6), (0.15, 0.40), 0.0125)

    def test_cierres_laterales(self):
        izq, der = _seg((0, 0), (0, 12)), _seg((32, 0), (32, 12))
        casos = {
            "sin cierres": ([], "incompleto", 0),
            "un cierre": ([izq], "incompleto", 1),
            "un cierre duplicado no son dos lados": ([izq, izq, _seg((0, 12), (0, 0))], "incompleto", 1),
            "lado partido que no cubre": ([_seg((0, 0), (0, 5)), _seg((0, 7), (0, 12)), der], "incompleto", 1),
            "lado partido que cubre": ([_seg((0, 0), (0, 6)), _seg((0, 6), (0, 12)), der], "ajustado", 2),
            "dos cierres": ([izq, der], "ajustado", 2),
        }
        for nombre, (extra, estado, lados) in casos.items():
            r = self.ajustar(extra)
            with self.subTest(nombre):
                self.assertEqual(r["estado"], estado)
                self.assertEqual(r["lados_verticales_confirmados"], lados)
        self.assertNotIn("caja_pt", self.ajustar([]))  # un incompleto no entrega geometría confirmada

    def test_union_por_distancia_real(self):
        def n(sep, tol=0.6):
            return len(iv.componentes([_seg((0, 0), (0, 2)), _seg((sep, 0), (sep, -2))], tol_pt=tol))
        self.assertEqual(n(0.84), 2)    # contraejemplo: celdas vecinas, distancia > tol
        self.assertEqual(n(0.61), 2)    # justo fuera
        self.assertEqual(n(0.60), 1)    # frontera incluida
        self.assertEqual(n(0.30), 1)    # dentro
        cadena = [_seg((0, 0), (1, 0)), _seg((1.5, 0), (2.5, 0)), _seg((3.0, 0), (4.0, 0))]
        self.assertEqual(len(iv.componentes(cadena, tol_pt=0.6)), 1)   # conexión por cadena válida
        self.assertEqual(len(iv.componentes(cadena, tol_pt=0.4)), 3)


if __name__ == "__main__":
    unittest.main()
