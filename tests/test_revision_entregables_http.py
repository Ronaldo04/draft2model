import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from urllib.parse import urlencode
from draft2model.revision_visual import RevisionLocal
from tests.fixture_etabs import extraer_evidencia
from tests import test_revision_visual as httpfixtures

CASO='demo-integrada-sintetica'
RESULTADO='72c06efb3bfe477bb1fe565809aeddec'
ANALISIS='adf97fbc232141e8ae687872c0d71232'


class EntregablesHTTPTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.bundle=extraer_evidencia(Path(temp.name).resolve()/'fixture')
        self.app=RevisionLocal(self.bundle/'private')
        self.server=SimpleNamespace(revision=self.app,token='prueba',origen='http://127.0.0.1:8766')
        self.fp=self.app.expediente(CASO)[2]
        self.body={'caso':CASO,'resultado':RESULTADO,'expediente_sha256':self.fp,'analisis':None,
            'contexto':{'titulo':'Prueba HTTP','hipotesis':['Datos sintéticos.'],'faltantes':['Revisión pendiente.'],'sitio':None}}

    def request(self,*args,**kwargs):return httpfixtures.HTTPRevisionTests.request(self,*args,**kwargs)

    def url(self,kind,**kwargs):
        return '/api/'+kind+'?'+urlencode({'caso':CASO,'resultado':RESULTADO,'expediente_sha256':self.fp,**kwargs})

    def create(self):
        status,raw,_=self.request('POST','/api/informe/crear',self.body)
        self.assertEqual(status,201,raw)
        return json.loads(raw)

    def test_crear_consultar_historial_y_descargar_borrador(self):
        first=self.create();second=self.create();self.assertNotEqual(first['id'],second['id'])
        status,raw,_=self.request('GET',self.url('informes'))
        self.assertEqual(status,200,raw)
        self.assertEqual({r['id'] for r in json.loads(raw)['versiones']},{first['id'],second['id']})
        status,raw,_=self.request('GET',self.url('informe',version=first['id']))
        self.assertEqual(status,200,raw);self.assertFalse(json.loads(raw)['aprueba_resultados'])
        status,raw,headers=self.request('GET',self.url('informe/archivo',version=first['id'],formato='pdf'))
        self.assertEqual(status,200,raw);self.assertTrue(raw.startswith(b'%PDF'))
        self.assertEqual(headers['Content-Type'],'application/pdf')
        self.assertEqual(headers['Content-Disposition'],'attachment; filename="informe-'+first['id']+'.pdf"')
        status,raw,_=self.request('GET',self.url('informe/archivo',version=first['id'],formato='json'))
        self.assertEqual(status,200,raw);self.assertIsNone(json.loads(raw)['reglas'])
        self.assertEqual(json.loads(raw)['revision']['estado'],'borrador')

    def test_autorizacion_vigencia_y_alteracion_impiden_descarga(self):
        self.assertEqual(self.request('POST','/api/informe/crear',self.body,headers={'X-Revision-Session':'otro'})[0],403)
        self.assertEqual(self.request('POST','/api/informe/crear',{**self.body,'expediente_sha256':'0'*64})[0],409)
        report=self.create();url=self.url('informe/archivo',version=report['id'],formato='pdf')
        self.assertEqual(self.request('GET',url,headers={'X-Revision-Session':'otro'})[0],403)
        self.assertEqual(self.request('GET',self.url('informe/archivo',version=report['id'],formato='../fuera'))[0],409)
        path=self.app.raiz/CASO/'informes'/report['id']/'informe.pdf';path.write_bytes(b'ALTERADO')
        status,raw,_=self.request('GET',url);self.assertEqual(status,409,raw)
        self.assertNotIn(str(self.bundle),raw.decode())
        status,raw,_=self.request('GET',self.url('informes'))
        self.assertEqual(status,200,raw);self.assertFalse(json.loads(raw)['versiones'][0]['vigente'])
        other=self.create();original=next((self.app.raiz/CASO/'originales').iterdir());original.write_bytes(b'ALTERADO')
        self.assertEqual(self.request('GET',self.url('informe',version=other['id']))[0],409)

    def test_analisis_optativo_verificado_y_asset_servido(self):
        target=self.app.raiz/CASO/'analisis_etabs'/ANALISIS
        shutil.copytree(self.bundle/'analisis'/ANALISIS,target)
        status,raw,_=self.request('GET',self.url('analisis'))
        self.assertEqual(status,200,raw);self.assertTrue(json.loads(raw)['versiones'][0]['vigente'])
        self.body['analisis']=ANALISIS;report=self.create()
        self.assertEqual(report['evidencia_analisis']['estados']['calculo'],'completado_verificado')
        (target/'analizado.edb').write_bytes(b'ALTERADO')
        self.assertEqual(self.request('GET',self.url('informe',version=report['id']))[0],409)
        status,raw,headers=self.request('GET','/informes.js')
        self.assertEqual(status,200);self.assertIn('text/javascript',headers['Content-Type'])
        self.assertNotIn(b'innerHTML',raw)
        status,raw,_=self.request('GET','/')
        self.assertEqual(status,200);self.assertIn(b'/informes.js',raw)

    def test_manifest_malformado_devuelve_error_y_historial_sin_vigencia(self):
        report=self.create();path=self.app.raiz/CASO/'informes'/report['id']/'paquete.json'
        meta=json.loads(path.read_bytes());meta['archivos']=list(meta['archivos']);path.write_text(json.dumps(meta))
        self.assertEqual(self.request('GET',self.url('informe',version=report['id']))[0],409)
        status,raw,_=self.request('GET',self.url('informes'))
        self.assertEqual(status,200,raw);self.assertFalse(json.loads(raw)['versiones'][0]['vigente'])
