"""Pruebas unitarias para la arquitectura modular de sistemas constructivos.

Verifica:
1. Catálogo de módulos sismorresistentes (Módulo 1: Aporticado, Módulo 2: Albañilería).
2. Parámetros normativos según E.030-2026 (R0=8, CT=35, Deriva <= 0.007 vs R0=3, CT=60, Deriva <= 0.005).
3. Reglas de verificación de secciones E.060 (b >= 25 cm, Ag >= 1000 cm2).
4. Verificación de distorsiones de entrepiso bajo espectro E.030-2026.
5. Especificación técnica de 7 etapas lista para ingesta del curso de modelado.
"""

import unittest
from draft2model.modulos_sistema import (
    MODULO_PORTICADO,
    MODULO_ALBANILERIA,
    listar_modulos,
    obtener_modulo
)
from draft2model.modulo_porticado import (
    calcular_parametros_porticado,
    verificar_secciones_porticado,
    validar_derivas_porticado,
    obtener_especificacion_modulo
)


class TestModulosSistema(unittest.TestCase):
    def test_catalogo_modulos_disponibles(self):
        mods = listar_modulos()
        self.assertEqual(len(mods), 2)
        ids = [m["id"] for m in mods]
        self.assertIn("porticado", ids)
        self.assertIn("albanileria", ids)

    def test_modulo_porticado_es_principal(self):
        mod1 = obtener_modulo("porticado")
        self.assertEqual(mod1["numero"], 1)
        self.assertEqual(mod1["estado"], "produccion_activo")
        self.assertIn("E.030-2026", mod1["normativa"]["sismo"]["codigo"])
        self.assertEqual(mod1["normativa"]["sismo"]["r0"], 8.0)
        self.assertEqual(mod1["normativa"]["sismo"]["ct_art36"], 35.0)
        self.assertEqual(mod1["normativa"]["sismo"]["deriva_max_tabla14"], 0.007)

    def test_modulo_albanileria_es_desarrollo(self):
        mod2 = obtener_modulo("albanileria")
        self.assertEqual(mod2["numero"], 2)
        self.assertEqual(mod2["estado"], "fase_desarrollo")
        self.assertEqual(mod2["caso_demostracion"], "pueblo-libre-v04")
        self.assertEqual(mod2["normativa"]["sismo"]["r0"], 3.0)
        self.assertEqual(mod2["normativa"]["sismo"]["ct_art36"], 60.0)
        self.assertEqual(mod2["normativa"]["sismo"]["deriva_max_tabla14"], 0.005)

    def test_calculo_parametros_sismicos_porticado(self):
        # Edificio de 3 pisos, altura total 9.0 m, Lima (Z4=0.45, S1=1.00, TP=0.4, TL=2.5, U=1.0)
        res = calcular_parametros_porticado(
            zona=4,
            categoria="C",
            perfil="S1",
            altura_total_hn=9.0
        )
        self.assertEqual(res["modulo"], "porticado")
        params = res["parametros"]
        self.assertEqual(params["R0"], 8.0)
        self.assertEqual(params["R"], 8.0)
        self.assertEqual(params["CT"], 35.0)
        # T = 9.0 / 35.0 = 0.2571 s
        self.assertAlmostEqual(params["T_aprox_s"], 9.0 / 35.0, places=3)
        # T < TP (0.257 < 0.40) -> C = 2.50
        self.assertEqual(params["C_aprox"], 2.50)
        self.assertEqual(params["deriva_limite"], 0.007)


    def test_verificacion_secciones_e060(self):
        # Secciones conformes
        secciones_ok = [
            {"id": "COL-1", "dimensiones": {"ancho_m": 0.30, "alto_m": 0.40}},  # 30x40 -> A=0.12 >= 0.10 m2, b=0.30 >= 0.25
            {"id": "VIG-101", "dimensiones": {"ancho_m": 0.25, "alto_m": 0.50}} # 25x50 -> b=0.25 >= 0.25, esbeltez 2.0 <= 4.0
        ]
        res = verificar_secciones_porticado(secciones_ok)
        self.assertEqual(len(res), 2)
        self.assertTrue(res[0]["valido"])
        self.assertTrue(res[1]["valido"])

        # Columna que no cumple sección mínima (ej: 20x20 cm)
        secciones_bad = [
            {"id": "COL-sub", "dimensiones": {"ancho_m": 0.20, "alto_m": 0.20}}
        ]
        res_bad = verificar_secciones_porticado(secciones_bad)
        self.assertFalse(res_bad[0]["valido"])
        self.assertFalse(res_bad[0]["cumple_dimension_minima_25cm"])
        self.assertFalse(res_bad[0]["cumple_area_minima_1000cm2"])

    def test_validacion_derivas_porticado(self):
        derivas_ok = [
            {"nivel": "Piso 1", "deriva_x": 0.0035, "deriva_y": 0.0042},
            {"nivel": "Piso 2", "deriva_x": 0.0048, "deriva_y": 0.0055},
            {"nivel": "Piso 3", "deriva_x": 0.0052, "deriva_y": 0.0061}
        ]
        res = validar_derivas_porticado(derivas_ok)
        self.assertTrue(res["cumple_todas_derivas"])
        self.assertEqual(res["limite_normativo"], 0.007)
        self.assertEqual(res["maxima_deriva"], 0.0061)

        derivas_exceso = [
            {"nivel": "Piso 1", "deriva_x": 0.0035, "deriva_y": 0.0042},
            {"nivel": "Piso 2", "deriva_x": 0.0082, "deriva_y": 0.0055}  # 0.0082 > 0.007
        ]
        res_exceso = validar_derivas_porticado(derivas_exceso)
        self.assertFalse(res_exceso["cumple_todas_derivas"])
        self.assertEqual(res_exceso["piso_critico"], "Piso 2")

    def test_especificacion_modulo_completa(self):
        spec = obtener_especificacion_modulo("porticado")
        self.assertTrue(spec["estado_preparacion"]["listo_para_ingesta_curso"])
        self.assertEqual(len(spec["etapas_requisitos"]), 7)
        self.assertEqual(spec["parametros_referencia"]["r0"], 8.0)
        self.assertEqual(spec["parametros_referencia"]["modificador_columna"], 0.70)
        self.assertEqual(spec["parametros_referencia"]["modificador_viga"], 0.35)
        self.assertEqual(spec["parametros_referencia"]["offset_zona_rigida"], 0.50)


if __name__ == "__main__":
    unittest.main()
