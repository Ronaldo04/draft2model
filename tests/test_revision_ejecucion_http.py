import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
from tests import test_revision_ejecucion as fixtures
from tests import test_revision_visual as httpfixtures


class ConstruccionHTTPTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ConstruccionWebTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.app=self.fixture.app;self.app._ejecucion=self.fixture.service
        self.server=SimpleNamespace(revision=self.app,token='prueba',origen='http://127.0.0.1:8766')

    def request(self,*args,**kwargs):return httpfixtures.HTTPRevisionTests.request(self,*args,**kwargs)

    def test_preparacion_sin_motor_confirmacion_y_trabajo_aceptado(self):
        with patch('subprocess.Popen',side_effect=AssertionError('Preparar no inicia procesos')):
            status,raw,_=self.request('POST','/api/construccion/preparar',self.fixture.body)
        self.assertEqual(status,201,raw);prepared=json.loads(raw)
        body={'caso':self.fixture.caso,'trabajo':prepared['id'],'huella_preparacion':prepared['huella_preparacion'],
              'expediente_sha256':prepared['expediente_sha256'],'confirmacion_explicita':False}
        status,raw,_=self.request('POST','/api/construccion/ejecutar',body)
        self.assertEqual(status,409,raw);self.assertEqual(json.loads(raw)['codigo'],'confirmacion_requerida')
        body['confirmacion_explicita']=True
        status,raw,_=self.request('POST','/api/construccion/ejecutar',body)
        self.assertEqual(status,201,raw);self.fixture.finish(prepared)
        url='/api/construccion/trabajo?'+urlencode({'caso':body['caso'],'trabajo':prepared['id']})
        status,raw,_=self.request('GET',url);self.assertEqual(status,200,raw)
        final=json.loads(raw);self.assertEqual(final['estado'],'aceptado')
        self.assertFalse(final['analisis_ejecutado'] or final['aprueba_resultados'] or final['aprueba_modelo'])
        status,raw,_=self.request('GET','/api/construccion/trabajos?caso='+body['caso'])
        self.assertEqual(status,200,raw);self.assertEqual(json.loads(raw)['trabajos'][0]['id'],prepared['id'])

    def test_sesion_y_campos_prohibidos_impiden_operacion(self):
        for headers in ({'X-Revision-Session':'otro'},{'Origin':'http://ajeno.test'}):
            self.assertEqual(self.request('POST','/api/construccion/preparar',self.fixture.body,headers=headers)[0],403)
        status,raw,_=self.request('POST','/api/construccion/preparar',{**self.fixture.body,'id_proceso':123})
        self.assertEqual(status,409);self.assertEqual(json.loads(raw)['codigo'],'campos_invalidos')
        status,raw,_=self.request('GET','/api/construccion/trabajo?'+urlencode({'caso':self.fixture.caso,'trabajo':'../otro'}))
        self.assertEqual(status,409,raw);self.assertNotIn(str(self.app.raiz),raw.decode())
        status,raw,headers=self.request('GET','/construccion.js')
        self.assertEqual(status,200,raw);self.assertIn('text/javascript',headers['Content-Type'])
        self.assertNotIn(b'innerHTML',raw)
        status,raw,_=self.request('GET','/')
        self.assertEqual(status,200);self.assertIn(b'/construccion.js',raw)
        self.assertIn(b'id="construccionConfirmar"',raw)
