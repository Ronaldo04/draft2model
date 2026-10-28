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


class PanelesHTTPTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.bundle=extraer_evidencia(Path(temp.name).resolve()/'fixture')
        self.app=RevisionLocal(self.bundle/'private')
        self.server=SimpleNamespace(revision=self.app,token='prueba',origen='http://127.0.0.1:8766')
        self.fp=self.app.expediente(CASO)[2]
        self.body={'caso':CASO,'resultado':RESULTADO,'expediente_sha256':self.fp,'analisis':None}

    def request(self,*args,**kwargs):return httpfixtures.HTTPRevisionTests.request(self,*args,**kwargs)

    def url(self,kind,**kwargs):
        return '/api/'+kind+'?'+urlencode({'caso':CASO,'resultado':RESULTADO,'expediente_sha256':self.fp,**kwargs})

    def crear(self):
        status,raw,_=self.request('POST','/api/panel/crear',self.body)
        self.assertEqual(status,201,raw)
        return json.loads(raw)

    def test_versiones_consulta_descarga_y_csp(self):
        first=self.crear();second=self.crear();self.assertNotEqual(first['id'],second['id'])
        status,raw,_=self.request('GET',self.url('paneles'))
        self.assertEqual(status,200,raw)
        self.assertEqual({v['id'] for v in json.loads(raw)['versiones']},{first['id'],second['id']})
        status,raw,_=self.request('GET',self.url('panel',version=first['id']))
        self.assertEqual(status,200,raw);self.assertFalse(json.loads(raw)['aprueba_resultados'])
        status,raw,headers=self.request('GET',self.url('panel/archivo',version=first['id']))
        self.assertEqual(status,200,raw);self.assertTrue(raw.startswith(b'<!doctype html>'))
        self.assertEqual(headers['Content-Type'],'text/html; charset=utf-8')
        self.assertEqual(headers['Content-Disposition'],'attachment; filename="panel-'+first['id']+'.html"')
        self.assertNotIn("'unsafe-inline'",headers['Content-Security-Policy'].split('script-src')[1].split(';')[0])
        for asset in ['/paneles.js','/']:
            status,raw,_=self.request('GET',asset);self.assertEqual(status,200)
            self.assertIn(b'paneles.js' if asset=='/' else b'd2m-result',raw)

    def test_autorizacion_y_archivo_alterado(self):
        self.assertEqual(self.request('POST','/api/panel/crear',self.body,headers={'X-Revision-Session':'otro'})[0],403)
        self.assertEqual(self.request('POST','/api/panel/crear',{**self.body,'expediente_sha256':'0'*64})[0],409)
        panel=self.crear();url=self.url('panel/archivo',version=panel['id'])
        self.assertEqual(self.request('GET',url,headers={'X-Revision-Session':'otro'})[0],403)
        path=self.app.raiz/CASO/'paneles'/panel['id']/'panel.html';path.write_bytes(b'ALTERADO')
        status,raw,_=self.request('GET',url);self.assertEqual(status,409,raw)
        self.assertNotIn(str(self.bundle),raw.decode())
        status,raw,_=self.request('GET',self.url('paneles'))
        self.assertEqual(status,200,raw);self.assertFalse(json.loads(raw)['versiones'][0]['vigente'])
