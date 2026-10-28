"""Listado sin comprobación y apertura comprobada de un análisis concreto."""
import json
import shutil
import unittest
from unittest.mock import patch

from draft2model.revision_entregables import ServicioEntregables
from tests import test_revision_entregables_http as base
from tests.test_revision_entregables_http import CASO, RESULTADO, ANALISIS


class InventarioAnalisis(unittest.TestCase):
    setUp = base.EntregablesHTTPTests.setUp
    request = base.EntregablesHTTPTests.request
    url = base.EntregablesHTTPTests.url

    def agregar_analisis(self):
        target = self.app.raiz / CASO / 'analisis_etabs' / ANALISIS
        shutil.copytree(self.bundle / 'analisis' / ANALISIS, target)
        return target

    def test_inventario_no_verifica_fuentes_ni_afirma_vigencia(self):
        self.agregar_analisis()
        with patch.object(ServicioEntregables, '_fuente', side_effect=AssertionError('No validar en listado')):
            status, raw, _ = self.request('GET', self.url('analisis', modo='inventario'))
        self.assertEqual(status, 200, raw)
        self.assertEqual(json.loads(raw), {'modo': 'inventario', 'versiones': [
            {'id': ANALISIS, 'vigente': None, 'verificacion': 'pendiente', 'estados': None, 'casos': None}]})

    def test_seleccion_completa_y_edb_alterado_rechazado(self):
        target = self.agregar_analisis()
        url = self.url('analisis/comprobar', analisis=ANALISIS)
        status, raw, _ = self.request('GET', url)
        self.assertEqual(status, 200, raw)
        row = json.loads(raw)
        self.assertEqual((row['id'], row['vigente'], row['verificacion']), (ANALISIS, True, 'completa'))
        (target / 'analizado.edb').write_bytes(b'ALTERADO')
        status, raw, _ = self.request('GET', self.url('analisis', modo='inventario'))
        self.assertEqual(status, 200, raw)
        self.assertIsNone(json.loads(raw)['versiones'][0]['vigente'])
        self.assertEqual(self.request('GET', url)[0], 409)

    def test_resultado_alterado_no_se_acepta_al_comprobar(self):
        self.agregar_analisis()
        p = self.app.raiz / CASO / 'resultados_estructurales' / RESULTADO / 'resultados.json'
        value = json.loads(p.read_bytes())
        value['corrida_id'] = '0' * 32
        p.write_text(json.dumps(value), encoding='utf-8')
        self.assertEqual(self.request('GET', self.url('analisis', modo='inventario'))[0], 200)
        self.assertEqual(self.request('GET', self.url('analisis/comprobar', analisis=ANALISIS))[0], 409)

    def test_omision_conserva_listado_verificado(self):
        self.agregar_analisis()
        status, raw, _ = self.request('GET', self.url('analisis'))
        self.assertEqual(status, 200, raw)
        self.assertTrue(json.loads(raw)['versiones'][0]['vigente'])

    def test_modo_parametros_y_fingerprint_invalidos(self):
        for url in (self.url('analisis', modo='rapido'), self.url('analisis', modo='inventario')+'&modo=inventario',
                    self.url('analisis', modo='inventario', x='1'),
                    self.url('analisis', modo='inventario', resultado='f'*32),
                    self.url('analisis', modo='inventario', expediente_sha256='f'*64),
                    self.url('analisis/comprobar'),
                    self.url('analisis/comprobar', analisis='../fuera')):
            self.assertEqual(self.request('GET', url)[0], 409, url)


if __name__ == '__main__':
    unittest.main()
