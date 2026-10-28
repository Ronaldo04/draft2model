import json
from types import SimpleNamespace
import unittest
from urllib.parse import urlencode
from tests import test_revision_aprobacion_modelo as fixtures
from tests import test_revision_visual as httpfixtures


class RevisionModeloHTTPTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.RevisionModeloWebTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.app=self.fixture.app
        self.server=SimpleNamespace(revision=self.app,token='prueba',origen='http://127.0.0.1:8766')

    def request(self,*args,**kwargs):return httpfixtures.HTTPRevisionTests.request(self,*args,**kwargs)

    def test_revision_propia_http_con_controles_y_fuentes(self):
        body=self.fixture.body
        url='/api/modelo/revision?'+urlencode({k:body[k] for k in ('caso','modelo','expediente_sha256')})
        status,raw,_=self.request('GET',url);self.assertEqual(status,200,raw);self.assertEqual(json.loads(raw)['estado'],'pendiente')
        for change in ({'confirmacion_explicita':False},{'controles':{}},{'huella_modelo':'0'*64}):
            status,raw,_=self.request('POST','/api/modelo/aprobar',{**body,**change});self.assertEqual(status,409,raw)
        self.assertEqual(self.request('POST','/api/modelo/aprobar',body,headers={'X-Revision-Session':'otro'})[0],403)
        status,raw,_=self.request('POST','/api/modelo/aprobar',body);self.assertEqual(status,201,raw)
        data=json.loads(raw);self.assertFalse(data['analisis_ejecutado'] or data['aprueba_resultados'])
        self.assertEqual(len(data['aprobaciones']),1);self.assertEqual(data['identidad_revisor'],'declarada_no_verificada')
        status,raw,_=self.request('GET',url);self.assertEqual(status,200,raw);self.assertEqual(json.loads(raw)['estado'],'aprobado')
        (self.fixture.model/'modelo.edb').write_bytes(b'ALTERADO')
        status,raw,_=self.request('GET',url);self.assertEqual(status,409,raw);self.assertNotIn(str(self.app.raiz),raw.decode())

    def test_asset_y_confirmaciones_visibles(self):
        status,raw,headers=self.request('GET','/revision_modelo.js')
        self.assertEqual(status,200,raw);self.assertIn('text/javascript',headers['Content-Type']);self.assertNotIn(b'innerHTML',raw)
        status,raw,_=self.request('GET','/');self.assertEqual(status,200)
        self.assertIn(b'id="modeloRevisionConfirmar"',raw);self.assertIn(b'/revision_modelo.js',raw)
