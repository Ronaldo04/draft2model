"""E.060/E.070/E.020 y E.030 estático: valores verificables a mano; unidades kgf/cm² frente a MPa."""
import math
import unittest

from draft2model import normativa_e030 as e030
from draft2model import normativa_rne as rne


class MaterialesCargasTests(unittest.TestCase):
    def test_concreto_e060_en_mpa(self):
        r = rne.modulo_concreto(210, "kgf/cm2")
        fc = 210 * 0.0980665
        self.assertTrue(math.isclose(r["Ec_MPa"], 4700 * math.sqrt(fc), rel_tol=1e-12))
        self.assertAlmostEqual(r["Ec_MPa"], 21328.6, places=0)
        self.assertAlmostEqual(r["nu_derivado_isotropia"], 0.15, places=12)
        self.assertNotAlmostEqual(r["Ec_MPa"], 4700 * math.sqrt(210), places=0)  # no mezclar kgf/cm² en la fórmula SI
        with self.assertRaises(ValueError):
            rne.modulo_concreto(210, "kg/cm2")

    def test_albanileria_e070(self):
        r = rne.modulo_albanileria(35, "kgf/cm2", "arcilla")
        self.assertAlmostEqual(r["Em_MPa"], 500 * 35 * 0.0980665)
        self.assertAlmostEqual(r["Gm_MPa"], 0.4 * r["Em_MPa"])
        with self.assertRaises(ValueError):
            rne.modulo_albanileria(35, "kgf/cm2", "king_kong")  # el tipo de unidad no se infiere del nombre comercial

    def test_pesos_y_cargas_e020(self):
        self.assertEqual(rne.peso_especifico("concreto_armado")["peso_kN_m3"], 24.0)
        self.assertEqual(rne.peso_especifico("agua_dulce")["peso_kN_m3"], 10.0)
        self.assertEqual(rne.carga_viva("vivienda")["kN_m2"], 2.0)
        self.assertEqual(rne.carga_viva("techo_pendiente_hasta_3")["kN_m2"], 1.0)
        with self.assertRaises(ValueError):
            rne.carga_viva("oficina")


class E030EstaticoTests(unittest.TestCase):
    def test_peso_periodo_cortante_y_distribucion(self):
        self.assertEqual(e030.fraccion_carga_viva("C")["fraccion"], 0.25)
        self.assertEqual(e030.fraccion_carga_viva("tanque")["fraccion"], 1.0)
        t = e030.periodo_aproximado(10.4, "albanileria_o_muros")
        self.assertAlmostEqual(t["T_s"], 10.4 / 60)
        v = e030.cortante_basal_estatico(Z=0.45, U=1.0, S=1.0, R=3.0, T=t["T_s"], TP=0.4, TL=2.5, P_kN=1000)
        self.assertEqual(v["C"], 2.5)  # art. 18.3: estático usa 2,5 aunque T < 0,2TP
        self.assertAlmostEqual(v["V_kN"], 0.45 * 2.5 / 3 * 1000)
        self.assertTrue(v["cumple_C_R_minimo"])
        largo = e030.cortante_basal_estatico(Z=0.45, U=1, S=1, R=8, T=10.0, TP=0.4, TL=2.5, P_kN=1000)
        # R236: caso independiente de Codex. C = 2,5·0,4·2,5/100 = 0,025; C/R = 0,003125 < 0,11.
        self.assertFalse(largo["cumple_C_R_minimo"])
        self.assertTrue(largo["minimo_aplicado"])
        self.assertAlmostEqual(largo["C_R"], 0.003125)
        self.assertAlmostEqual(largo["V_bruto_kN"], 1.40625)
        self.assertAlmostEqual(largo["V_kN"], 49.5)  # 0,45·1·1·0,11·1000: valor utilizable
        justo = e030.cortante_basal_estatico(Z=0.45, U=1, S=1, R=2.5 / 0.11, T=0.2, TP=0.4, TL=2.5, P_kN=1000)
        self.assertFalse(justo["minimo_aplicado"])  # frontera C/R = 0,11 exacta
        self.assertAlmostEqual(justo["V_kN"], justo["V_bruto_kN"])
        for malo in (dict(TP=0.4, TL=0.2, T=0.1), dict(TP=0.4, TL=0.4, T=0.1), dict(TP=0.0, TL=2.5, T=0.1),
                     dict(TP=0.4, TL=2.5, T=-1), dict(TP=0.4, TL=2.5, T=0.1, R=0), dict(TP=0.4, TL=2.5, T=0.1, P_kN=0),
                     dict(TP=0.4, TL=2.5, T=0.1, Z=float("inf"))):
            kw = {**dict(Z=0.45, U=1, S=1, R=3, P_kN=1000), **malo}
            with self.subTest(malo=malo), self.assertRaises(ValueError):  # TL < TP ya no se acepta en la rama estática
                e030.cortante_basal_estatico(**kw)
        with self.assertRaises(ValueError):
            e030.espectro(Z=0.45, U=1, S=1, R=3, TP=0.4, TL=0.2, periodos=[0.1])
        d = e030.distribucion_altura(100.0, [10, 10], [2.6, 5.2], T=0.3)
        self.assertEqual(d["k"], 1.0)
        self.assertTrue(math.isclose(sum(d["F_kN"]), 100.0) and math.isclose(d["F_kN"][1], 2 * d["F_kN"][0]))
        self.assertAlmostEqual(e030.distribucion_altura(1, [1], [1], T=1.0)["k"], 1.25)
        self.assertEqual(e030.distribucion_altura(1, [1], [1], T=5.0)["k"], 2.0)


if __name__ == "__main__":
    unittest.main()
