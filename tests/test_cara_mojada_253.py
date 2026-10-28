"""R253: presión evaluada en la cara mojada física (desplazamiento declarado respecto de la superficie media)."""
import copy
import math
import unittest

from draft2model import acciones_liquidos as a
from draft2model import cargas_liquidos_etabs as cl
from tests import test_acciones_liquidos as tal

GAMMA = 10.0


def calcular(geo, nivel, sentido, delta=None):
    g, d, f = tal.entradas(geo=copy.deepcopy(geo), nivel=nivel, sentido=sentido)
    if delta is not None:
        d["superficies"][0]["desplazamiento_cara_m"] = delta
    declarada = a.declarar_acciones_liquidos(g, d, f)
    return g, declarada, f, a.calcular_acciones_liquidos(g, declarada, f)["superficies"][0]


FONDO = tal.superficie([(0, 0, 0), (4, 0, 0), (4, 3, 0), (0, 3, 0)])    # normal +Z
MURO = tal.superficie([(0, 0, 0), (4, 0, 0), (4, 0, 3), (0, 0, 3)])


class CaraMojadaTests(unittest.TestCase):
    def test_fondo_en_cara_fisica(self):
        # Superficie media del fondo en z = 0; cara mojada 0,10 m más arriba; carga hacia −Z (sentido −1).
        _, _, _, sin = calcular(FONDO, 2.0, -1)
        _, _, _, con = calcular(FONDO, 2.0, -1, 0.10)
        self.assertTrue(math.isclose(sin["fuerza_kn"][2], -GAMMA * 12 * 2.0, rel_tol=1e-12))
        self.assertTrue(math.isclose(con["fuerza_kn"][2], -GAMMA * 12 * 1.9, rel_tol=1e-12))   # γ·A·(h − δ)
        self.assertEqual((con["desplazamiento_cara_m"], con["nivel_efectivo_z_m"]), (0.10, 1.9))
        self.assertNotIn("nivel_efectivo_z_m", sin)   # sin la clave, el resultado no cambia

    def test_muro_vertical_sin_cambio_de_presion(self):
        _, _, _, sin = calcular(MURO, 2.0, 1)
        _, _, _, con = calcular(MURO, 2.0, 1, 0.10)
        self.assertEqual(sin["fuerza_kn"], con["fuerza_kn"])
        self.assertEqual(sin["momento_kn_m"], con["momento_kn_m"])

    def test_coeficientes_de_tabla_en_cara_fisica(self):
        g, declarada, f, _ = calcular(FONDO, 2.0, -1, 0.10)
        host = cl.preparar_cargas_no_uniformes(g, declarada, f)["superficies"][0]
        comp = next(c for c in host["componentes"] if c["Dir"] == "Gravity")
        self.assertTrue(math.isclose(cl.evaluar_componente(comp, [1.0, 1.0, 0.0]), GAMMA * 1.9, rel_tol=1e-12))
        self.assertEqual(host["nivel_efectivo_z_m"], 1.9)

    def test_rechazos(self):
        for valor in (-0.1, float("nan"), True, "0.1"):
            with self.subTest(valor=valor), self.assertRaises(a.ErrorAccionesLiquidos):
                calcular(FONDO, 2.0, -1, valor)


if __name__ == "__main__":
    unittest.main()
