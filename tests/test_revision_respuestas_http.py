"""HTTP en memoria con paquete y respuesta sintéticos; sin servidor ni proveedor."""
import json
from types import SimpleNamespace
from urllib.parse import urlencode
import unittest
from unittest.mock import patch
from tests import test_revision_respuestas as fixtures
from tests import test_revision_visual as http


class RespuestasHTTPTests(unittest.TestCase):
    request=http.HTTPRevisionTests.request

    def setUp(self):
        self.fixture=fixtures.RespuestasWebTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.app=self.fixture.app;self.body=self.fixture.body
        self.server=SimpleNamespace(revision=self.app,token='prueba',origen='http://127.0.0.1:8766')

    def register(self,**changes):
        status,raw,_=self.request('POST','/api/respuesta/registrar',{**self.body,**changes})
        self.assertEqual(status,201,raw);return json.loads(raw)

    def query(self,**extra):return urlencode({'caso':self.body['caso'],'expediente_sha256':self.body['expediente_sha256'],**extra})

    def test_flujo_local_separado_pendiente_y_assets(self):
        with patch('subprocess.Popen',side_effect=AssertionError('Sin procesos')):
            item=self.register(modo_prueba=False)
            self.assertEqual(self.app.documentos(self.body['caso'])['versiones'],[])
            status,raw,headers=self.request('GET','/api/respuesta?'+self.query(version=item['id']))
            self.assertEqual(status,200);self.assertEqual(json.loads(raw),item);self.assertEqual(headers['Cache-Control'],'no-store')
            self.assertFalse(item['aprueba_ingenieria'] or item['transmision_externa'])
            body={'caso':item['caso'],'expediente_sha256':item['expediente_sha256'],'respuesta':item['id'],
                'sha256_extraccion':item['sha256_extraccion'],'confirmacion_explicita':True}
            for changes in ({'confirmacion_explicita':False},{'sha256_extraccion':'0'*64}):
                self.assertEqual(self.request('POST','/api/respuesta/importar',{**body,**changes})[0],409)
            status,raw,_=self.request('POST','/api/respuesta/importar',body);self.assertEqual(status,201,raw)
            result=json.loads(raw);self.assertEqual(result['estado'],'pendiente_revision');self.assertFalse(result['aprueba_ingenieria'])
            self.assertIn(result['extraccion'],self.app.documentos(item['caso'])['versiones'])
        for route in ('/respuestas.js','/'):
            status,raw,_=self.request('GET',route);self.assertEqual(status,200);self.assertIn(b'respuestaRegistrar',raw)

    def test_prueba_no_trasladable_y_listado_invalido(self):
        item=self.register();self.assertTrue(item['modo_prueba']);self.assertFalse(item['traslado_permitido'])
        body={'caso':item['caso'],'expediente_sha256':item['expediente_sha256'],'respuesta':item['id'],
            'sha256_extraccion':item['sha256_extraccion'],'confirmacion_explicita':True}
        self.assertEqual(self.request('POST','/api/respuesta/importar',body)[0],409)
        target=self.fixture.fixture.case/'vision/respuestas'/item['id']/'respuesta_original.json';target.write_text('[]')
        self.assertEqual(self.request('GET','/api/respuesta?'+self.query(version=item['id']))[0],409)
        status,raw,_=self.request('GET','/api/respuestas?'+self.query());self.assertEqual(status,200)
        self.assertEqual(json.loads(raw)['versiones'],[{'id':item['id'],'vigente':False}])

    def test_seguridad_origen_ids_limites_y_fuentes(self):
        for headers in ({'X-Revision-Session':'ajeno'},{'Origin':'https://ajeno.invalid'}):
            self.assertEqual(self.request('POST','/api/respuesta/registrar',self.body,headers)[0],403)
        for changes in ({'paquete':'../x'},{'expediente_sha256':'0'*64},{'modo_prueba':1},{'ruta':'C:/privado'},
                        {'respuesta_json':'x'*(1536*1024+1)}):
            status,raw,_=self.request('POST','/api/respuesta/registrar',{**self.body,**changes});self.assertEqual(status,409,raw)
            self.assertNotIn(str(self.app.raiz).encode(),raw)
        item=self.register();(self.fixture.path.parent/'prompt.txt').write_text('alterado')
        self.assertEqual(self.request('GET','/api/respuesta?'+self.query(version=item['id']))[0],409)
        self.assertEqual(self.request('GET','/api/respuestas?caso='+self.body['caso'])[0],409)

if __name__=='__main__':unittest.main()
