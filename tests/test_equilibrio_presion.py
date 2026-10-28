"""Regresión contra respuestas nativas conservadas; no ejecuta ETABS ni usa red."""
import copy
import json
from pathlib import Path
import unittest
from scripts.evaluar_ensayo_presion import evaluar


class EquilibrioPresionTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((Path(__file__).parent/'fixtures'/'equilibrio_presion_etabs21_186.json').read_bytes())

    def test_negativo_sin_corte_no_confunde_importacion_exitosa_con_equilibrio(self):
        r=evaluar(self.data['sin_corte']['registro'])
        self.assertFalse(r['equilibrio_ensayo_sintetico'])
        self.assertAlmostEqual(r['fuerza_reaccion_kn'][1],62.5)
        self.assertAlmostEqual(r['residuo_fuerza_kn'][1],18.75)

    def test_corte_equilibra_fuerza_y_momento(self):
        r=evaluar(self.data['con_corte']['registro'])
        self.assertTrue(r['equilibrio_ensayo_sintetico'])
        self.assertAlmostEqual(r['fuerza_reaccion_kn'][1],43.75)
        self.assertFalse(r['aprueba_ingenieria'])

    def test_misma_fuerza_con_momento_alterado_no_pasa(self):
        x=copy.deepcopy(self.data['con_corte']['registro']);x['reacciones'][0]['momento'][0]+=1
        self.assertFalse(evaluar(x)['equilibrio_ensayo_sintetico'])

    def test_ensayo_incompleto_o_fuente_alterada_se_rechaza(self):
        for key,value in [('error','fallo'),('cierre_confirmado',False),('solver_ejecutado',False),('sha256_original_posterior','0'*64)]:
            x=copy.deepcopy(self.data['con_corte']['registro']);x[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):evaluar(x)


if __name__=='__main__':unittest.main()
