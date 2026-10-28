"""La cache caliente de malla no debe ocultar evidencia alterada en disco."""
import json
from pathlib import Path
import unittest
from draft2model import malla_preparacion as mp

class EvidenciaConCacheTests(unittest.TestCase):
    def prepare(self):
        from tests.test_liquidos_ruta201 import CasoLiquidos
        fixture=CasoLiquidos();fixture.setUp();self.addCleanup(fixture.doCleanups)
        config=fixture.aprobar_en_disco(fixture.montar_liquidos('horizontal','ausente_confirmado',patrones=()))
        mp.preparar_malla.cache_clear()
        fixture.plan(config);fixture.plan(config)
        self.assertGreater(mp.preparar_malla.cache_info()['hits'],0)
        return fixture,config

    def test_original_alterado_se_rechaza_con_malla_caliente(self):
        fixture,config=self.prepare()
        case=fixture.raiz/config['caso']
        index=json.loads((case/'expediente.json').read_text(encoding='utf-8'))
        original=case/index['archivos'][0]['archivo']
        original.write_bytes(original.read_bytes()+b'\nalterado por prueba adversarial')
        with self.assertRaises(ValueError):fixture.plan(config)

    def test_geometria_archivada_alterada_se_rechaza_con_malla_caliente(self):
        fixture,config=self.prepare()
        path=fixture.raiz/config['caso']/'geometrias'/config['geometria_origen']['version_id']/'geometria.json'
        path.write_bytes(path.read_bytes()+b'\n ')
        with self.assertRaises(ValueError):fixture.plan(config)

if __name__=='__main__':unittest.main()
