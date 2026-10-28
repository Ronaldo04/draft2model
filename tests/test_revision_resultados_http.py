import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from urllib.parse import urlencode
from draft2model.revision_visual import RevisionLocal
from tests.fixture_etabs import extraer_evidencia
from tests import test_revision_visual as httpfixtures

CASO='demo-integrada-sintetica'
RESULTADO='72c06efb3bfe477bb1fe565809aeddec'
MODELO='225f8c4a9a0744fbb702a9f0b9affdc0'


class ResultadosHTTPTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.bundle=extraer_evidencia(Path(temp.name).resolve()/'fixture')
        self.app=RevisionLocal(self.bundle/'private')
        self.server=SimpleNamespace(revision=self.app,token='prueba',origen='http://127.0.0.1:8766')
        self.fingerprint=self.app.expediente(CASO)[2]

    def request(self,*args,**kwargs):return httpfixtures.HTTPRevisionTests.request(self,*args,**kwargs)

    def url(self,kind='resultado',**kwargs):
        return '/api/'+kind+'?'+urlencode({'caso':CASO,'version':MODELO if kind=='modelo' else RESULTADO,
            'expediente_sha256':self.fingerprint,**kwargs})

    def test_consulta_http_de_modelo_y_cifras_con_estados_separados(self):
        for kind,ident in [('resultados',RESULTADO),('modelos',MODELO)]:
            status,raw,_=self.request('GET','/api/'+kind+'?caso='+CASO)
            self.assertEqual(status,200,raw)
            self.assertIn(ident,[v['id'] for v in json.loads(raw)['versiones']])
        status,raw,headers=self.request('GET',self.url())
        self.assertEqual(status,200,raw);data=json.loads(raw)
        self.assertFalse(data['analisis_vinculado'] or data['aprueba_resultados'])
        self.assertTrue(any(row['valor'] is None for row in data['datos']['resultados']))
        self.assertNotIn(str(self.bundle),raw.decode());self.assertEqual(headers['Cache-Control'],'no-store')
        status,raw,_=self.request('GET',self.url('modelo'))
        self.assertEqual(status,200,raw);data=json.loads(raw)
        self.assertEqual(data['revision'],'pendiente');self.assertIsNone(data['aprobacion'])

    def test_token_hash_y_parametros_no_permiten_lecturas_ajenas(self):
        self.assertEqual(self.request('GET',self.url(),headers={'X-Revision-Session':'otro'})[0],403)
        for url in (self.url(expediente_sha256='0'*64),self.url(version='../otro'),
                    self.url(caso='otro-caso'),self.url()+'&version='+RESULTADO,
                    '/api/resultado?caso='+CASO+'&version='+RESULTADO):
            status,raw,_=self.request('GET',url)
            self.assertEqual(status,409,(url,raw));self.assertNotIn(str(self.bundle),raw.decode())

    def test_original_alterado_invalida_consulta_y_listado(self):
        original=next((self.app.raiz/CASO/'originales').iterdir())
        original.write_bytes(original.read_bytes()+b'ALTERADO')
        self.assertEqual(self.request('GET',self.url())[0],409)
        status,raw,_=self.request('GET','/api/resultados?caso='+CASO)
        self.assertEqual(status,200);rows=json.loads(raw)['versiones']
        self.assertFalse(rows[0]['vigente']);self.assertIsNone(rows[0]['resumen'])

    def test_interfaz_local_y_script_no_ejecutan_ni_aprueban(self):
        status,raw,_=self.request('GET','/')
        self.assertEqual(status,200);self.assertIn(b'/resultados.js',raw)
        self.assertIn(b'id="resultadoFilas"',raw)
        status,raw,headers=self.request('GET','/resultados.js')
        self.assertEqual(status,200);self.assertIn('text/javascript',headers['Content-Type'])
        self.assertNotIn(b'innerHTML',raw);self.assertNotIn(b'RunAnalysis',raw)
        self.assertEqual(self.request('POST','/api/resultado',{})[0],404)
