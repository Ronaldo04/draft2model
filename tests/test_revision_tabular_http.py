"""Rutas HTTP de contingencia tabular sobre ServicioTabular real; transporte en memoria, sin red."""
import base64
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from tests import test_revision_visual as httpfixtures
from tests import test_revision_tabular as servicio
from tests.test_revision_tabular import CASO, libro


class TabularHTTPTests(unittest.TestCase):
    # Composición: se reutilizan fixture y ayudantes del servicio sin heredar (ni repetir) sus pruebas.
    body_csv = servicio.TabularWebTests.body_csv
    body_xlsx = servicio.TabularWebTests.body_xlsx
    versiones_geometria = servicio.TabularWebTests.versiones_geometria

    def setUp(self):
        servicio.TabularWebTests.setUp(self)
        self.server = SimpleNamespace(revision=self.app, token='prueba', origen='http://127.0.0.1:8766')

    def request(self, *args, **kwargs):
        return httpfixtures.HTTPRevisionTests.request(self, *args, **kwargs)

    def url(self, kind, **kwargs):
        return '/api/tabular/'+kind+'?'+urlencode({'caso': CASO, 'expediente_sha256': self.fp, **kwargs})

    def post(self, path, body, **kw):
        status, raw, _ = self.request('POST', path, body, **kw)
        return status, json.loads(raw) if raw else None

    def assertPrivado(self, raw):
        text = raw.decode('utf-8') if isinstance(raw, bytes) else json.dumps(raw)
        self.assertNotIn(str(self.app.raiz), text); self.assertNotIn(json.dumps(str(self.app.raiz))[1:-1], text)

    def test_flujo_csv_xlsx_historial_version_importacion_y_replay(self):
        status, item = self.post('/api/tabular/crear', self.body_csv()); self.assertEqual(status, 201, item)
        self.assertEqual((item['estado'], item['aprobacion'], item['importacion']), ('borrador', None, None))
        status, xlsx = self.post('/api/tabular/crear', self.body_xlsx()); self.assertEqual(status, 201, xlsx)
        status, raw, _ = self.request('GET', self.url('historial')); self.assertEqual(status, 200, raw)
        self.assertEqual({r['id'] for r in json.loads(raw)['versiones']}, {item['id'], xlsx['id']})
        status, raw, _ = self.request('GET', self.url('version', version=item['id'])); self.assertEqual(status, 200, raw)
        version = json.loads(raw)
        self.assertEqual(version['geometria']['revision'], {'estado': 'borrador', 'aprobacion': None})
        self.assertEqual(len(version['geometria']['muros']), version['resumen']['muros'])
        self.assertPrivado(raw); self.assertNotIn(base64.b64encode(self.csv['nodos.csv']).decode(), raw.decode())
        self.assertEqual(self.versiones_geometria(), [])  # crear no importa
        body = {'caso': CASO, 'expediente_sha256': self.fp, 'version': item['id'], 'huella_tabular': item['huella_tabular'],
                'confirmacion_explicita': True}
        status, out = self.post('/api/tabular/importar', {**body, 'confirmacion_explicita': False})
        self.assertEqual(status, 409); self.assertIn('Confirma', out['error'])
        self.assertEqual(self.post('/api/tabular/importar', {**body, 'huella_tabular': '0'*64})[0], 409)
        status, first = self.post('/api/tabular/importar', body); self.assertEqual(status, 201, first)
        status, again = self.post('/api/tabular/importar', body); self.assertEqual(status, 201, again)
        self.assertEqual(first, again); self.assertEqual(self.versiones_geometria(), [first['geometria']])
        self.assertEqual((first['estado'], first['aprobacion'], first['aprueba_geometria']), ('borrador', None, False))

    def test_sesion_origen_huella_y_fuente_alterada(self):
        self.assertEqual(self.post('/api/tabular/crear', self.body_csv(), headers={'X-Revision-Session': 'otra'})[0], 403)
        self.assertEqual(self.post('/api/tabular/crear', self.body_csv(), headers={'Origin': 'http://evil.test'})[0], 403)
        self.assertEqual(self.request('GET', self.url('historial'), headers={'X-Revision-Session': 'otra'})[0], 403)
        status, out = self.post('/api/tabular/crear', {**self.body_csv(), 'expediente_sha256': '0'*64})
        self.assertEqual(status, 409); self.assertPrivado(out)
        status, item = self.post('/api/tabular/crear', self.body_csv()); self.assertEqual(status, 201)
        (self.case/'tabulares'/item['id']/'muros.csv').write_bytes(b'id,nivel,nodo_i,nodo_j\n')
        status, raw, _ = self.request('GET', self.url('version', version=item['id'])); self.assertEqual(status, 409); self.assertPrivado(raw)
        status, out = self.post('/api/tabular/importar', {'caso': CASO, 'expediente_sha256': self.fp, 'version': item['id'],
                                                         'huella_tabular': item['huella_tabular'], 'confirmacion_explicita': True})
        self.assertEqual(status, 409); self.assertEqual(self.versiones_geometria(), [])
        self.assertEqual(self.request('GET', self.url('version', version='../x'))[0], 409)

    def test_cuerpo_grande_solo_para_crear(self):
        grande = base64.b64encode(b'X'*(3*1024*1024)).decode()  # > 2 MiB, < 24 MiB
        body = {**self.body_xlsx(), 'archivos': [{'nombre': 'grande.xlsx', 'contenido_base64': grande}]}
        status, out = self.post('/api/tabular/crear', body)
        self.assertEqual(status, 409, out)  # admitido por tamaño; rechazado por el lector XLSX del servicio
        status, out = self.post('/api/tabular/importar', {'caso': CASO, 'expediente_sha256': self.fp, 'version': '1'*32,
                                                         'huella_tabular': '0'*64, 'confirmacion_explicita': True, 'relleno': grande})
        self.assertEqual(status, 413)
        enorme = {**body, 'archivos': [{'nombre': 'x.xlsx', 'contenido_base64': 'A'*(25*1024*1024)}]}
        self.assertEqual(self.post('/api/tabular/crear', enorme)[0], 413)
        status, item = self.post('/api/tabular/crear', self.body_xlsx(raw=libro())); self.assertEqual(status, 201)

    def test_interfaz_servida(self):
        status, raw, headers = self.request('GET', '/tabular.js')
        self.assertEqual(status, 200); self.assertIn(b'/api/tabular/importar', raw)
        self.assertTrue(headers['Content-Type'].startswith('text/javascript'))
        status, raw, _ = self.request('GET', '/')
        self.assertIn(b'<script src="/tabular.js"></script>', raw); self.assertIn(b'id="tabularImportar"', raw)


if __name__ == '__main__':
    unittest.main()
