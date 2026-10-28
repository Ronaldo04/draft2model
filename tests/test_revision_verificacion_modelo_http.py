import json
from types import SimpleNamespace
import unittest
from urllib.parse import urlencode
from tests import test_revision_verificacion_modelo as fixtures
from tests import test_revision_visual as httpfixtures


class VerificacionHTTPTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.ServicioTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.app=self.f.app;self.app._verificacion_modelo=self.f.service
        self.server=SimpleNamespace(revision=self.app,token='prueba',origen='http://127.0.0.1:8766')

    def request(self,*a,**kw):return httpfixtures.HTTPRevisionTests.request(self,*a,**kw)

    def test_protocolo_sesion_ejecucion_y_evidencia_sin_rutas(self):
        route='/api/modelo/verificacion/'
        self.assertEqual(self.request('POST',route+'preparar',self.f.body,headers={'X-Revision-Session':'otro'})[0],403)
        self.assertEqual(self.request('POST',route+'preparar',{**self.f.body,'ruta_edb':'externa'})[0],409)
        status,raw,_=self.request('POST',route+'preparar',self.f.body)
        self.assertEqual(status,201,raw);prep=json.loads(raw)
        body={'caso':prep['caso'],'trabajo':prep['id'],'huella_preparacion':prep['huella_preparacion'],
              'expediente_sha256':prep['expediente_sha256'],'confirmacion_explicita':False}
        self.assertEqual(self.request('POST',route+'ejecutar',body)[0],409)
        status,raw,_=self.request('POST',route+'ejecutar',{**body,'confirmacion_explicita':True})
        self.assertEqual(status,201,raw);self.f.finish(prep)
        status,raw,_=self.request('GET',route+'estado?'+urlencode({'caso':prep['caso'],'trabajo':prep['id']}))
        self.assertEqual(status,200,raw);self.assertTrue(json.loads(raw)['lectura_comprobada'])
        # Valores del resultado son observaciones; no se expone solicitud ni ruta privada.
        self.assertNotIn(str(self.app.raiz),raw.decode());self.assertNotIn('id_proceso',raw.decode())
        status,raw,_=self.request('GET',route+'historial?'+urlencode({'caso':prep['caso']}))
        self.assertEqual(status,200,raw);self.assertEqual(len(json.loads(raw)['trabajos']),1)
