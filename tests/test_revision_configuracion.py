import copy
import json
from types import SimpleNamespace
import unittest
from tests import test_modelo_estructural as fixtures
from tests import test_revision_visual as httpfixtures
from draft2model.revision_visual import RevisionLocal


class ConfiguracionHTTPTests(unittest.TestCase):
    def test_editor_y_recurso_sirven_con_politica_local(self):
        status,raw,headers=self.request('GET','/')
        self.assertEqual(status,200);self.assertIn(b'/configuracion.js',raw)
        self.assertIn("script-src 'self'",headers['Content-Security-Policy'])
        status,raw,headers=self.request('GET','/configuracion.js')
        self.assertEqual(status,200);self.assertIn('text/javascript',headers['Content-Type'])
        self.assertNotIn(b'innerHTML',raw)

    def setUp(self):
        self.base=fixtures.ModeloTests();self.base.setUp();self.addCleanup(self.base.doCleanups)
        self.app=RevisionLocal(self.base.raiz)
        self.server=SimpleNamespace(revision=self.app,token='prueba',origen='http://127.0.0.1:8766')
        self.request=lambda *a,**kw:httpfixtures.HTTPRevisionTests.request(self,*a,**kw)
        self.caso=self.base.data['caso']
        self.body={'caso':self.caso,'expediente_sha256':self.app.expediente(self.caso)[2]}

    def importar(self):
        status,raw,_=self.request('POST','/api/configuracion/importar',{**self.body,'configuracion_json':json.dumps(self.base.data)})
        self.assertEqual(status,201,raw);return json.loads(raw)['id']

    def actor(self,version):
        data=self.app.configuraciones.consultar(self.caso,version)
        return {**self.body,'version':version,'huella':data['huella'],'sha256_configuracion':data['sha256_configuracion'],
                'revisor_declarado':'Prueba sintética','fecha':'2026-10-17','motivo':'Ensayo interfaz'}

    def test_http_importar_revisar_aprobar_consultar(self):
        version=self.importar()
        status,raw,_=self.request('GET','/api/configuraciones?caso='+self.caso)
        self.assertEqual(status,200);self.assertEqual(json.loads(raw)['versiones'],[version])
        proposal=copy.deepcopy(self.base.data);proposal['materiales'][0]['E_kN_m2']*=1.1
        status,raw,_=self.request('POST','/api/configuracion/revisar',{**self.actor(version),'configuracion_json':json.dumps(proposal)})
        self.assertEqual(status,201,raw);child=json.loads(raw)['id']
        status,raw,_=self.request('POST','/api/configuracion/aprobar',{**self.actor(child),'alcance':'Solo software','confirmacion_explicita':True})
        self.assertEqual(status,201,raw);approved=json.loads(raw)['id']
        status,raw,_=self.request('GET','/api/configuracion?caso='+self.caso+'&version='+approved)
        self.assertEqual(status,200);self.assertTrue(json.loads(raw)['comprobacion']['apto_para_adaptador'])
        self.assertEqual(self.app.configuraciones.consultar(self.caso,version)['datos']['revision']['estado'],'borrador')

    def test_rechaza_fingerprint_aprobacion_sin_confirmacion_y_rutas(self):
        version=self.importar();base={**self.actor(version),'alcance':'Prueba','confirmacion_explicita':True}
        for change in ({'huella':'0'*64},{'sha256_configuracion':'0'*64},{'confirmacion_explicita':False},{'ruta':'C:/privado'},{'expediente_sha256':'0'*64}):
            status,_,_=self.request('POST','/api/configuracion/aprobar',{**base,**change})
            self.assertEqual(status,409)
        self.assertEqual(self.app.configuraciones.listar(self.caso),[version])
        self.assertEqual(self.request('GET','/api/configuraciones?caso='+self.caso,headers={'X-Revision-Session':'incorrecto'})[0],403)

    def test_original_alterado_bloquea_consulta_y_revision(self):
        version=self.importar();body={**self.actor(version),'configuracion_json':json.dumps(self.base.data)}
        self.base.original.write_bytes(b'alterado')
        self.assertEqual(self.request('GET','/api/configuracion?caso='+self.caso+'&version='+version)[0],409)
        self.assertEqual(self.request('POST','/api/configuracion/revisar',body)[0],409)
