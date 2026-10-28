"""Inventario no acreditativo y conservación de guardas al abrir/descargar."""
import json
import unittest
from unittest.mock import patch
from draft2model.revision_entregables import ServicioEntregables
from tests import test_revision_entregables_http as base
from tests.test_revision_entregables_http import CASO, RESULTADO


class InventarioInformes(unittest.TestCase):
    setUp = base.EntregablesHTTPTests.setUp
    request = base.EntregablesHTTPTests.request
    url = base.EntregablesHTTPTests.url
    create = base.EntregablesHTTPTests.create

    def test_listado_no_revalida_ni_acredita_estado(self):
        report = self.create()
        with patch.object(ServicioEntregables, '_fuente', side_effect=AssertionError('No validar listado')), \
             patch.object(ServicioEntregables, 'consultar', side_effect=AssertionError('No abrir listado')):
            status, raw, _ = self.request('GET', self.url('informes', modo='inventario'))
        self.assertEqual(status, 200, raw)
        self.assertEqual(json.loads(raw), {'modo':'inventario', 'versiones':[
            {'id':report['id'],'vigente':None,'verificacion':'pendiente','estado':None,'analisis':None}]})

    def test_alteracion_no_se_acepta_al_abrir_ni_descargar(self):
        report = self.create()
        target = self.app.raiz / CASO / 'informes' / report['id'] / 'informe.json'
        target.write_bytes(target.read_bytes() + b' ')
        status, raw, _ = self.request('GET', self.url('informes', modo='inventario'))
        self.assertEqual(status, 200, raw)
        self.assertIsNone(json.loads(raw)['versiones'][0]['vigente'])
        for route in ('informe', 'informe/archivo'):
            self.assertEqual(self.request('GET', self.url(route, version=report['id'], formato='pdf'))[0], 409)

    def test_fuente_alterada_invalida_informe_intacto(self):
        report = self.create()
        source = self.app.raiz / CASO / 'resultados_estructurales' / RESULTADO / 'resultados.json'
        data = json.loads(source.read_bytes()); data['corrida_id'] = '0' * 32
        source.write_text(json.dumps(data), encoding='utf-8')
        self.assertEqual(self.request('GET', self.url('informes', modo='inventario'))[0], 200)
        self.assertEqual(self.request('GET', self.url('informe', version=report['id']))[0], 409)
        self.assertEqual(self.request('GET', self.url('informe/archivo', version=report['id'], formato='json'))[0], 409)

    def test_parametros_invalidos_y_pertenencia(self):
        for url in (self.url('informes', modo='rapido'), self.url('informes', modo='inventario')+'&modo=inventario',
                    self.url('informes', modo='inventario', extra='1'),
                    self.url('informes', modo='inventario', resultado='f'*32),
                    self.url('informes', modo='inventario', expediente_sha256='f'*64)):
            self.assertEqual(self.request('GET', url)[0], 409, url)

    def test_modo_predeterminado_sigue_comprobando(self):
        report = self.create()
        status, raw, _ = self.request('GET', self.url('informes'))
        self.assertEqual(status, 200, raw)
        self.assertEqual(json.loads(raw)['versiones'][0]['id'], report['id'])
        self.assertTrue(json.loads(raw)['versiones'][0]['vigente'])


if __name__ == '__main__':
    unittest.main()
