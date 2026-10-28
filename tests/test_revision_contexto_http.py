"""Contexto/explicaciones HTTP sin red, claves ni procesos externos."""
import base64
import json
from types import SimpleNamespace
from urllib.parse import urlencode
import unittest
from unittest.mock import patch
from tests import test_revision_contexto as fixture
from tests import test_revision_visual as http_fixture


class ContextoHTTPTests(unittest.TestCase):
    request=http_fixture.HTTPRevisionTests.request

    def setUp(self):
        self.fixture=fixture.ContextoTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.app=self.fixture.app;self.fp=self.fixture.fp
        self.base={'caso':fixture.CASO,'expediente_sha256':self.fp}
        self.server=SimpleNamespace(revision=self.app,token='prueba',origen='http://127.0.0.1:8766')
        guard=patch('draft2model.proveedor_openai._http',side_effect=AssertionError('Sin red'))
        guard.start();self.addCleanup(guard.stop)
        env=patch.dict('os.environ',{'OPENAI_API_KEY':''});env.start();self.addCleanup(env.stop)

    def post(self,route,body):
        status,raw,_=self.request('POST',route,body);self.assertEqual(status,201,raw)
        return json.loads(raw)

    def test_registro_corpus_mayor_2mib_recuperacion_abstencion_y_alteracion(self):
        text='x'*(2*1024*1024)+'\n'+fixture.TEXTO
        item=self.post('/api/contexto/corpus/registrar',{**self.base,'manifiesto_json':json.dumps(fixture.corpus(texto=text)),
            'archivos':[{'nombre':'fuente.txt','contenido_base64':base64.b64encode(text.encode()).decode()}]})
        query='/api/contexto/version?'+urlencode({**self.base,'tipo':'corpus','version':item['id']})
        self.assertEqual(self.request('GET',query)[0],200)
        found=self.post('/api/contexto/recuperar',{**self.base,'corpus':item['id'],'consulta':'deriva', 'limite':3,'resultado':None})
        absent=self.post('/api/contexto/recuperar',{**self.base,'corpus':item['id'],'consulta':'terminoinexistente', 'limite':3,'resultado':None})
        self.assertTrue(found['reproducido']);self.assertFalse(absent['aprueba_informe'])
        route='/api/contexto/derivado?'+urlencode({**self.base,'version':found['id']})
        self.assertEqual(self.request('GET',route)[0],200)
        (self.fixture.case/'contexto/corpus'/item['id']/'fuente.txt').write_bytes(b'alterado')
        self.assertEqual(self.request('GET',query)[0],409);self.assertEqual(self.request('GET',route)[0],409)

    def test_reglas_sitio_evaluacion_y_listado(self):
        rules=self.post('/api/contexto/reglas/registrar',{**self.base,'reglas_json':json.dumps(fixture.reglas(1.0))})
        site=self.post('/api/contexto/sitio/registrar',{**self.base,'capa_json':json.dumps(fixture.capa())})
        ev=self.post('/api/contexto/evaluar',{**self.base,'resultado':fixture.RESULTADO,'reglas':rules['id'],
            'huella_resultados':self.fixture.huella_resultado,'huella_reglas':rules['huella']})
        crossing=self.post('/api/contexto/consultar-sitio',{**self.base,'sitio':site['id'],'longitud':1,'latitud':1,'resultado':None})
        self.assertEqual(crossing['salida']['estado'],'dentro');self.assertFalse(ev['aprueba_resultados'])
        status,raw,_=self.request('GET','/api/contexto/historial?'+urlencode(self.base))
        self.assertEqual(status,200);self.fixture.assertSinRutas(json.loads(raw))

    def test_explicacion_sin_clave_conserva_contingencia_y_no_envia(self):
        self.assertIsNone(self.app._explicaciones)
        body={**self.base,'resultado':fixture.RESULTADO,'huella_resultados':self.fixture.huella_resultado,
            'derivados':{'recuperacion':None,'evaluacion':None,'sitio':None},'modelo':'declarado-sintetico',
            'opciones':{'max_tokens':512,'timeout_s':20},'clave_solicitud':'a'*32}
        job=self.post('/api/explicaciones/preparar',body)
        self.assertEqual(self.post('/api/explicaciones/preparar',body)['id'],job['id'])
        execution={**self.base,'trabajo':job['id'],'huella_preparacion':job['huella_preparacion'],'confirmacion_explicita':True}
        self.assertEqual(self.request('POST','/api/explicaciones/ejecutar',{**execution,'confirmacion_explicita':False})[0],409)
        done=self.post('/api/explicaciones/ejecutar',execution)
        self.assertEqual(done['estado'],'contingencia');self.assertFalse(done['salida']['generacion_llm_real'])
        query='/api/explicaciones/trabajo?'+urlencode({'caso':fixture.CASO,'trabajo':job['id']})
        self.assertEqual(self.request('GET',query)[0],200)
        for headers in ({'X-Revision-Session':'ajeno'},{'Origin':'https://ajeno.invalid'}):
            self.assertEqual(self.request('POST','/api/explicaciones/preparar',body,headers)[0],403)
        self.fixture.assertSinRutas(done)
