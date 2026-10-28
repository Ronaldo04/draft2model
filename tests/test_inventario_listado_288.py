"""Continuación288: listado en modo inventario (IDs sin comprobar) para no retener app.lock validando todas las versiones.

El inventario nunca marca una versión como vigente ni muestra metadatos sin verificar; abrir la versión ejecuta la comprobación
completa. El modo por omisión (comprobación completa) no cambia.
"""
import json
import unittest
from unittest.mock import patch

from draft2model.revision_resultados import ServicioResultados
from tests import test_revision_resultados_http as base
from tests.test_revision_resultados_http import CASO, MODELO, RESULTADO


class InventarioListadoTests(base.ResultadosHTTPTests):
    def test_inventario_solo_ids_pendientes_sin_comprobar(self):
        with patch.object(ServicioResultados, '_resultado', side_effect=AssertionError('no comprobar')), \
             patch.object(ServicioResultados, '_modelo', side_effect=AssertionError('no comprobar')):
            for kind, ident in (('resultados', RESULTADO), ('modelos', MODELO)):
                status, raw, _ = self.request('GET', '/api/' + kind + '?caso=' + CASO + '&modo=inventario')
                self.assertEqual(status, 200, raw)
                data = json.loads(raw)
                self.assertEqual(data['modo'], 'inventario')
                row = next(v for v in data['versiones'] if v['id'] == ident)
                self.assertEqual((row['vigente'], row['verificacion'], row['resumen']), (None, 'pendiente', None))

    def test_modo_por_omision_sigue_comprobando_y_parametros_exactos(self):
        status, raw, _ = self.request('GET', '/api/resultados?caso=' + CASO)
        self.assertEqual(status, 200)
        self.assertTrue(all(v['vigente'] is True for v in json.loads(raw)['versiones']))
        for url in ('/api/resultados?caso=' + CASO + '&modo=rapido', '/api/modelos?caso=' + CASO + '&modo=inventario&x=1',
                    '/api/modelos?caso=' + CASO + '&modo=inventario&modo=inventario'):
            self.assertEqual(self.request('GET', url)[0], 409, url)

    def test_abrir_tras_inventario_comprueba_y_rechaza_alteracion(self):
        self.assertEqual(self.request('GET', '/api/resultados?caso=' + CASO + '&modo=inventario')[0], 200)
        res = self.app.raiz / CASO / 'resultados_estructurales' / RESULTADO / 'resultados.json'
        datos = json.loads(res.read_text(encoding='utf-8')); datos['corrida_id'] = '0' * 32
        res.write_text(json.dumps(datos), encoding='utf-8')               # alteración de contenido
        self.assertEqual(self.request('GET', self.url())[0], 409)          # abrir comprueba y rechaza

    def test_original_alterado_inventario_queda_pendiente_y_abrir_rechaza(self):
        original = next((self.app.raiz / CASO / 'originales').iterdir())
        original.write_bytes(original.read_bytes() + b'ALTERADO')
        status, raw, _ = self.request('GET', '/api/resultados?caso=' + CASO + '&modo=inventario')
        self.assertEqual(status, 200, raw)
        self.assertTrue(all(v['vigente'] is None and v['verificacion'] == 'pendiente' for v in json.loads(raw)['versiones']))
        self.assertEqual(self.request('GET', self.url())[0], 409)          # nunca se usa sin la comprobación real


if __name__ == '__main__':
    unittest.main()
