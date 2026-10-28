import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
from tests import test_revision_analisis as fixtures
from tests import test_revision_visual as httpfixtures


class AnalisisHTTPTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.AnalisisWebTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.app=self.fixture.app;self.app._analisis=self.fixture.service
        self.server=SimpleNamespace(revision=self.app,token='prueba',origen='http://127.0.0.1:8766')

    def request(self,*args,**kwargs):return httpfixtures.HTTPRevisionTests.request(self,*args,**kwargs)

    def test_preparar_sin_motor_confirmar_calcular_y_reconsultar(self):
        with patch('subprocess.Popen',side_effect=AssertionError('No motor en preparación')):
            status,raw,_=self.request('POST','/api/analisis/preparar',self.fixture.body)
        self.assertEqual(status,201,raw);prepared=json.loads(raw)
        body={'caso':self.fixture.caso,'trabajo':prepared['id'],'huella_preparacion':prepared['huella_preparacion'],
              'expediente_sha256':prepared['expediente_sha256'],'confirmacion_explicita':False}
        self.assertEqual(self.request('POST','/api/analisis/ejecutar',body)[0],409)
        body['confirmacion_explicita']=True
        status,raw,_=self.request('POST','/api/analisis/ejecutar',body);self.assertEqual(status,201,raw)
        self.fixture.finish(prepared)
        url='/api/analisis/trabajo?'+urlencode({'caso':body['caso'],'trabajo':prepared['id']})
        status,raw,_=self.request('GET',url);self.assertEqual(status,200,raw)
        final=json.loads(raw);self.assertEqual(final['estado'],'aceptado');self.assertTrue(final['calculo_verificado'])
        self.assertEqual(final['estados_casos'],{'EST':4});self.assertFalse(final['resultado_normalizado'] or final['aprueba_resultados'])
        status,raw,_=self.request('GET','/api/analisis/trabajos?caso='+body['caso'])
        self.assertEqual(status,200,raw);self.assertEqual(json.loads(raw)['trabajos'][0]['id'],prepared['id'])

    def test_sesion_campos_y_script(self):
        self.assertEqual(self.request('POST','/api/analisis/preparar',self.fixture.body,headers={'X-Revision-Session':'otro'})[0],403)
        self.assertEqual(self.request('POST','/api/analisis/preparar',{**self.fixture.body,'id_proceso':1})[0],409)
        status,raw,headers=self.request('GET','/analisis.js');self.assertEqual(status,200,raw)
        self.assertIn('text/javascript',headers['Content-Type']);self.assertNotIn(b'innerHTML',raw)
        status,raw,_=self.request('GET','/');self.assertEqual(status,200);self.assertIn(b'id="analisisConfirmar"',raw)
        self.assertNotIn(str(self.app.raiz),raw.decode())
