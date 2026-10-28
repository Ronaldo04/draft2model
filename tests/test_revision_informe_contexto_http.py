"""Informe HTTP con referencias verificadas y contingencia portable; sin red ni procesos."""
import json
from types import SimpleNamespace
from urllib.parse import urlencode
import unittest
from tests import test_revision_informe_contexto as fixtures
from tests import test_revision_visual as http


class InformeContextoHTTPTests(unittest.TestCase):
    request=http.HTTPRevisionTests.request

    def setUp(self):
        self.fixture=fixtures.InformeContextoTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.app=self.fixture.app;self.fp=self.fixture.fp
        self.server=SimpleNamespace(revision=self.app,token='prueba',origen='http://127.0.0.1:8766')

    def url(self,route,**extra):return '/api/'+route+'?'+urlencode({'caso':fixtures.CASO,'resultado':fixtures.RESULTADO,'expediente_sha256':self.fp,**extra})

    def create(self,body):
        status,raw,_=self.request('POST','/api/informe/crear',body);self.assertEqual(status,201,raw);return json.loads(raw)

    def test_referencias_contexto_contingencia_descarga_y_aprobacion(self):
        job=self.fixture.explicacion();self.assertEqual(job['estado'],'contingencia')
        refs=self.fixture.refs(job['id']);item=self.create(self.fixture.body(refs))
        self.assertEqual(item['referencias'],refs);self.assertEqual(item['explicacion']['modo'],'contingencia_deterministica')
        self.assertFalse(item['explicacion']['generacion_llm_real'] or item['aprueba_resultados']);self.assertEqual(item['revision_resultados'],'pendiente')
        status,raw,_=self.request('GET',self.url('informe/archivo',version=item['id'],formato='json'));self.assertEqual(status,200)
        data=json.loads(raw);self.assertEqual(data['explicacion']['estado_revision'],'propuesta_pendiente_revision_humana');self.assertEqual(data['contexto']['sitio'],self.fixture.site['salida'])
        self.assertEqual(data['evaluacion'],self.fixture.ev['salida']);self.assertEqual(data['fuentes']['citas'][0]['texto'],fixtures.FRAGMENTO)
        status,raw,_=self.request('GET',self.url('informe/archivo',version=item['id'],formato='pdf'));self.assertEqual(status,200);self.assertTrue(raw.startswith(b'%PDF'))
        approve={'caso':fixtures.CASO,'version':item['id'],'expediente_sha256':self.fp,'sha256_informe':item['archivos']['informe.json'],
            'revisor_declarado':'Documental SINTÉTICO','fecha':'2026-10-18','motivo':'Revisión documental sin aprobar ingeniería.','confirmacion_explicita':True}
        status,raw,_=self.request('POST','/api/informe/aprobar',approve);self.assertEqual(status,201,raw);child=json.loads(raw)
        self.assertEqual(child['referencias'],refs);self.assertEqual(child['padre']['id'],item['id']);self.assertFalse(child['aprueba_resultados'])

    def test_compatibilidad_sin_referencias_y_rechazos_exactos(self):
        item=self.create(self.fixture.body());self.assertNotIn('referencias',item)
        job=self.fixture.explicacion();body=self.fixture.body(self.fixture.refs(job['id']))
        for change in ({'referencias':self.fixture.refs(job['id'],evaluacion=None)},
                       {'referencias':self.fixture.refs(job['id'],recuperacion='../otro')},
                       {'referencias':{**self.fixture.refs(),'extra':None}},
                       {'referencias':self.fixture.refs(job['id'],sitio=self.fixture.ev['id'])},
                       {'contexto':{**body['contexto'],'sitio':{'fuente':'pegada'}}},
                       {'explicacion':{'texto':'No admitido'}}):
            with self.subTest(change=change):
                status,raw,_=self.request('POST','/api/informe/crear',{**body,**change});self.assertEqual(status,409,raw);self.fixture.assertSinRutas(json.loads(raw))

    def test_fuente_cambiada_invalida_historial_descarga_y_aprobacion(self):
        item=self.create(self.fixture.body(self.fixture.refs()))
        rules=self.fixture.case/'contexto/reglas'/self.fixture.rules['id']/'reglas.json';rules.write_bytes(rules.read_bytes()+b' ')
        self.assertEqual(self.request('GET',self.url('informe',version=item['id']))[0],409)
        self.assertEqual(self.request('GET',self.url('informe/archivo',version=item['id'],formato='pdf'))[0],409)
        status,raw,_=self.request('GET',self.url('informes'));self.assertEqual(status,200);self.assertFalse(json.loads(raw)['versiones'][0]['vigente'])
        body={'caso':fixtures.CASO,'version':item['id'],'expediente_sha256':self.fp,'sha256_informe':item['archivos']['informe.json'],
            'revisor_declarado':'R','fecha':'2026-10-18','motivo':'M','confirmacion_explicita':True}
        self.assertEqual(self.request('POST','/api/informe/aprobar',body)[0],409)

if __name__=='__main__':unittest.main()
