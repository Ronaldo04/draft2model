"""E.030 vigente (RM 183-2026): valores de tabla y fórmulas con cita. Cálculos de referencia hechos a mano."""
import math
import unittest

from draft2model import normativa_e030 as n


class NormativaE030Tests(unittest.TestCase):
    def test_zona_uso_y_sitio(self):
        self.assertEqual(n.factor_zona(4)["Z"], 0.45)
        self.assertEqual(n.factor_zona(4)["cita"]["tabla"], "Tabla N° 1")
        self.assertEqual(n.factor_uso("C")["U"], 1.0)
        s1 = n.parametros_sitio(4, "S1")
        self.assertEqual((s1["S"], s1["TP"], s1["TL"], s1["metodo"]), (1.0, 0.4, 2.5, "valor_tabulado"))
        s2 = n.parametros_sitio(4, "S2")  # sin Vs30: mayor S del intervalo y TP/TL de la nota
        self.assertEqual((s2["S"], s2["TP"], s2["TL"], s2["metodo"]), (1.10, 0.6, 2.0, "sin_vs30_nota_tablas_4_5"))
        for args in ((4, "S4"), (5, "S1"), (4, "S9")):
            with self.subTest(args), self.assertRaises(ValueError):
                n.parametros_sitio(*args)
        # Interpolación por Vs30 (Tabla 3 y nota de Tablas 4/5); referencias aritméticas independientes de Codex (09).
        for perfil, vs, esperado in (("S2", 450, (1.05, 0.5, 2.25)), ("S3", 275, (1.15, 0.75, 1.8)),
                                     ("S2", 549.999, (1.0, 0.4, 2.5)), ("S2", 350, (1.10, 0.6, 2.0)), ("S3", 200, (1.20, 0.9, 1.6))):
            r = n.parametros_sitio(4, perfil, vs30=vs)
            with self.subTest(perfil=perfil, vs=vs):
                for calc, ref in zip((r["S"], r["TP"], r["TL"]), esperado):
                    self.assertTrue(math.isclose(calc, ref, rel_tol=1e-4))
                self.assertEqual(r["metodo"], "interpolacion_vs30")
        for perfil, vs in (("S2", 550), ("S2", 349.9), ("S3", 350), ("S3", 199), ("S2", -1), ("S2", float("nan"))):
            with self.subTest(fuera=(perfil, vs)), self.assertRaises(ValueError):  # sin extrapolación ni cambio de perfil
                n.parametros_sitio(4, perfil, vs30=vs)
        self.assertEqual(n.parametros_sitio(4, "S1", vs30=600)["metodo"], "valor_tabulado")  # perfil no interpolable

    def test_factor_c_cuatro_tramos(self):
        TP, TL = 0.4, 2.5
        casos = [(0.05, 1 + 7.5 * 0.05 / 0.4, "T < 0,2TP"), (0.1, 2.5, "0,2TP ≤ T ≤ TP"), (0.4, 2.5, "0,2TP ≤ T ≤ TP"),
                 (1.0, 1.0, "TP < T < TL"), (3.0, 2.5 * 0.4 * 2.5 / 9, "T ≥ TL")]
        for T, esperado, tramo in casos:
            r = n.factor_c(T, TP, TL)
            with self.subTest(T=T):
                self.assertTrue(math.isclose(r["C"], esperado, rel_tol=1e-12))
                self.assertEqual(r["tramo"], tramo)
        self.assertEqual(n.factor_c(0, TP, TL)["C"], 1.0)  # 2005 daba 2,5 en T = 0: la norma vigente no
        for malo in ((-0.1, TP, TL), (1, 0, TL), (1, 2.5, 2.5), (float("nan"), TP, TL)):
            with self.subTest(malo=malo), self.assertRaises(ValueError):
                n.factor_c(*malo)

    def test_espectro_y_r(self):
        r = n.coeficiente_r("albanileria_armada_o_confinada", 1.0, 1.0)
        self.assertEqual((r["R0"], r["R"]), (3, 3.0))
        self.assertEqual(n.coeficiente_r("albanileria_armada_o_confinada", 0.75, 0.9)["R"], 3 * 0.75 * 0.9)
        with self.assertRaises(ValueError):
            n.coeficiente_r("albanileria_armada_o_confinada", 1.2, 1.0)
        e = n.espectro(Z=0.45, U=1.0, S=1.0, R=3.0, TP=0.4, TL=2.5, periodos=[0.0, 0.4, 1.0])
        sa = [f["Sa_m_s2"] for f in e["filas"]]
        g = 9.80665
        for calc, esperado in zip(sa, [0.45 * 1.0 / 3 * g, 0.45 * 2.5 / 3 * g, 0.45 * 1.0 / 3 * g]):
            self.assertTrue(math.isclose(calc, esperado, rel_tol=1e-12))
        self.assertEqual(e["cita"][0]["articulo"], "41.1")
        with self.assertRaises(ValueError):
            n.espectro(Z=0.45, U=1, S=1, R=3, TP=0.4, TL=2.5, periodos=[1.0, 0.5])

    def test_deriva_cortante_y_excentricidad(self):
        d = n.deriva_admisible("albanileria", regular=True, R=3.0)
        self.assertEqual((d["limite"], d["factor_desplazamiento"]), (0.005, 2.25))
        self.assertEqual(n.deriva_admisible("albanileria", regular=False, R=3.0)["factor_desplazamiento"], 0.85 * 3.0)
        self.assertEqual(n.cortante_minimo(regular=True)["fraccion_del_estatico"], 0.80)
        self.assertEqual(n.cortante_minimo(regular=False)["fraccion_del_estatico"], 0.90)
        self.assertAlmostEqual(n.excentricidad_accidental(20.0)["e_m"], 1.0)
        self.assertEqual(n.NORMA["dispositivo"], "RM 183-2026-VIVIENDA")



    def test_anexo_ii_zonificacion(self):
        deps = n.listar_departamentos()
        self.assertIn("LIMA", deps)
        self.assertIn("ÁNCASH", deps)
        self.assertIn("LORETO", deps)
        self.assertEqual(len(deps), 25)

        provs_lima = n.listar_provincias("LIMA")
        self.assertIn("LIMA", provs_lima)
        self.assertIn("BARRANCA", provs_lima)

        dists_lima = n.listar_distritos("LIMA", "LIMA")
        nombres_dists = [d["distrito"] for d in dists_lima]
        self.assertIn("PUEBLO LIBRE", nombres_dists)
        self.assertIn("MIRAFLORES", nombres_dists)

        # Consultas de distritos específicas de E.030-2026
        pl = n.consultar_zona_distrito("LIMA", "LIMA", "PUEBLO LIBRE")
        self.assertEqual((pl["zona"], pl["Z"]), (4, 0.45))

        chavin = n.consultar_zona_distrito("ÁNCASH", "HUARI", "CHAVÍN DE HUÁNTAR")
        self.assertEqual((chavin["zona"], chavin["Z"]), (3, 0.35))

        sr = n.consultar_zona_distrito("LORETO", "MARISCAL RAMÓN CASTILLA", "SANTA ROSA")
        self.assertEqual((sr["zona"], sr["Z"]), (1, 0.10))

    def test_generar_y_exportar_espectro_etabs(self):
        puntos_c = n.generar_curva_espectro(Z=0.45, U=1.0, S=1.0, R=8.0, TP=0.4, TL=2.5, T_max=1.0, dT=0.1, tipo="C")
        self.assertEqual(len(puntos_c), 11)  # 0.0, 0.1, ..., 1.0
        self.assertEqual(puntos_c[0]["T"], 0.0)
        self.assertEqual(puntos_c[0]["valor"], 1.0)
        # En la meseta (0.2TP=0.08 a TP=0.4): C = 2.5
        self.assertEqual(puntos_c[2]["valor"], 2.5)  # T = 0.2

        txt = n.exportar_archivo_espectro_etabs(None, Z=0.45, U=1.0, S=1.0, R=8.0, TP=0.4, TL=2.5, T_max=0.5, dT=0.1, tipo="C")
        self.assertIn("; Espectro de Respuesta segun Norma E.030-2026", txt)
        self.assertIn("0.0000", txt)

    def test_escala_cortante_dinamico(self):
        # Regular: V_min = 80% V_est
        res_ok = n.verificar_escala_cortante_dinamico(V_estatico=100.0, V_dinamico=85.0, regular=True)
        self.assertTrue(res_ok["cumple"])
        self.assertEqual(res_ok["factor_escala"], 1.0)

        res_bajo = n.verificar_escala_cortante_dinamico(V_estatico=100.0, V_dinamico=70.0, regular=True)
        self.assertFalse(res_bajo["cumple"])
        self.assertAlmostEqual(res_bajo["factor_escala"], 80.0 / 70.0)

        # Irregular: V_min = 90% V_est
        res_irreg = n.verificar_escala_cortante_dinamico(V_estatico=100.0, V_dinamico=85.0, regular=False)
        self.assertFalse(res_irreg["cumple"])
        self.assertAlmostEqual(res_irreg["factor_escala"], 90.0 / 85.0)


if __name__ == "__main__":
    unittest.main()
