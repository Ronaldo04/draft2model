import json
from types import SimpleNamespace
import unittest
from urllib.parse import urlencode
from unittest.mock import patch
from tests import test_revision_mapeos as fixtures
from tests import test_revision_visual as httpfixtures


class MapeosHTTPTests(unittest.TestCase):
    def test_recuperacion_http_no_recalcula_ni_publica_duplicado(self):
        approved=self.fixture.approve(self.fixture.imported())
        with patch('draft2model.revision_mapeos.verificar_evidencia',side_effect=OSError('Interrupción')):
            with self.assertRaises(OSError):self.fixture.normalize(approved)
        body={**self.fixture.base(approved),'clave_solicitud':'c'*32,'confirmacion_explicita':True}
        status,raw,_=self.request('POST','/api/mapeo/normalizar',body)
        self.assertEqual(status,409,raw);self.assertEqual(json.loads(raw)['codigo'],'normalizacion_pendiente')
        status,raw,_=self.request('GET','/api/normalizacion/estado?'+urlencode({'caso':fixtures.CASO,'expediente_sha256':self.fixture.fp}))
        self.assertEqual(status,200,raw);pending=json.loads(raw)['pendientes'][0]
        recovery={'caso':fixtures.CASO,'expediente_sha256':self.fixture.fp,'clave_solicitud':pending['clave_solicitud'],
            'resultado':pending['resultados_candidatos'][0],'confirmacion_explicita':False}
        self.assertEqual(self.request('POST','/api/normalizacion/recuperar',recovery)[0],409)
        with patch('draft2model.revision_mapeos.registrar_resultados',side_effect=AssertionError('No recalcular')):
            status,raw,_=self.request('POST','/api/normalizacion/recuperar',{**recovery,'confirmacion_explicita':True})
        self.assertEqual(status,201,raw);self.assertEqual(json.loads(raw)['resultado'],recovery['resultado'])
        self.assertEqual(self.request('GET','/recuperacion.js')[0],200)

    def setUp(self):
        self.fixture=fixtures.MapeosTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.app=self.fixture.app
        self.server=SimpleNamespace(revision=self.app,token='prueba',origen='http://127.0.0.1:8766')

    def request(self,*args,**kwargs):return httpfixtures.HTTPRevisionTests.request(self,*args,**kwargs)

    def test_importar_previsualizar_aprobar_y_normalizar_con_huellas(self):
        self.assertEqual(self.request('POST','/api/mapeo/importar',self.fixture.body,headers={'X-Revision-Session':'otro'})[0],403)
        status,raw,_=self.request('POST','/api/mapeo/importar',self.fixture.body);self.assertEqual(status,201,raw)
        draft=json.loads(raw);self.assertFalse(draft['previsualizacion']['publicado'])
        url='/api/mapeo?'+urlencode({'caso':fixtures.CASO,'version':draft['id'],'expediente_sha256':self.fixture.fp})
        self.assertEqual(self.request('GET',url)[0],200)
        approval={**self.fixture.base(draft),'revisor':'Fixture sintética','fecha':'2026-10-17',
            'motivo':'Prueba de software','alcance':'Sin revisión física','confirmacion_explicita':True}
        self.assertEqual(self.request('POST','/api/mapeo/aprobar',{**approval,'confirmacion_explicita':False})[0],409)
        status,raw,_=self.request('POST','/api/mapeo/aprobar',approval);self.assertEqual(status,201,raw)
        approved=json.loads(raw);self.assertNotEqual(approved['id'],draft['id'])
        body={**self.fixture.base(approved),'clave_solicitud':'c'*32,'confirmacion_explicita':True}
        status,raw,_=self.request('POST','/api/mapeo/normalizar',body);self.assertEqual(status,201,raw)
        result=json.loads(raw);self.assertFalse(result['aprueba_resultados'])
        self.assertEqual(result['evidencia_analisis']['estados']['calculo'],'completado_verificado')
        status,raw,_=self.request('POST','/api/mapeo/normalizar',body)
        self.assertEqual(status,201,raw);self.assertEqual(json.loads(raw)['resultado'],result['resultado'])
        status,raw,_=self.request('GET','/api/mapeos?'+urlencode({'caso':fixtures.CASO,'expediente_sha256':self.fixture.fp}))
        self.assertEqual(status,200,raw);self.assertEqual(len(json.loads(raw)['versiones']),2)
        self.assertNotIn(str(self.fixture.bundle),raw.decode())
        status,raw,headers=self.request('GET','/mapeos.js')
        self.assertEqual(status,200);self.assertIn('text/javascript',headers['Content-Type']);self.assertNotIn(b'innerHTML',raw)
        status,raw,_=self.request('GET','/');self.assertEqual(status,200);self.assertIn(b'/mapeos.js',raw)
