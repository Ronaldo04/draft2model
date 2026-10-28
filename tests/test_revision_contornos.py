"""Flujo de software en disco sintético; proveedor doble, calibración real, sin red."""
import copy
import json
import unittest
from unittest.mock import patch

from draft2model.revision_contornos import ServicioContornos
from draft2model import gestion_geometria as gg
from tests import test_revision_digitizacion as fixtures


class RevisionContornosTests(unittest.TestCase):
    def setUp(self):
        fixtures.TMP_BASE.mkdir(parents=True,exist_ok=True)
        self.f=fixtures.RevisionDigitizacionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.geom,self.geo=self.f._importar_geo(fixtures._geometria_v03_base())
        self.prep=self.f.app.preparacion_configuracion.crear({'caso':fixtures.CASO,'expediente_sha256':self.f.fp,'geometria':self.geom})
        self.sent=[];self.answer=None
        def transport(payload,timeout):
            self.sent.append(payload)
            return {'id':'RESPUESTA-SINTETICA-SIN-RED','model':'fixture','status':'completed','output':[{'type':'message','role':'assistant',
                'content':[{'type':'output_text','text':json.dumps(self.answer)}]}]}
        self.service=ServicioContornos(self.f.app,transporte=transport,registro_cuota=self.f.root/'cuota_sintetica.json')

    def body(self):
        return {'caso':fixtures.CASO,'expediente_sha256':self.f.fp,'proveedor':'openai','modelo':'fixture',
                'max_tokens':8192,'clave_solicitud':'a'*32,'configuracion_preparacion':self.prep['id'],
                'sha256_configuracion':self.prep['sha256_configuracion'],'limites_digitizacion':fixtures._limites_validos()}

    def raw(self):
        _,_,_,_,ctx=self.service._contexto(self.body())
        plane=next(p['id'] for p in ctx['planos'] if p['eje_constante']=='z' and p['valor_constante']==0)
        refs=['E1'];anchor=lambda id,p,uv:{'id':id,'punto_resuelto':p,'uv_local':uv,'evidencias':refs}
        point=lambda id,uv:{'id':id,'uv_local':uv,'relacionados':['VA','VB','VC'],'evidencias':refs}
        return {'contrato':'draft2model.contornos_planos','version_contrato':'0.1.0','caso':fixtures.CASO,
                'evidencias':[{'id':'E1','archivo_id':self.f.id_pdf,'pagina':1,'bbox_normalizada':[0,0,1,1],'texto':'CONTORNO SINTETICO DE PRUEBA'}],
                'dibujos':[{'id':'D1','archivo_id':self.f.id_pdf,'pagina':1,'bbox_pagina':[0,0,1,1],'plano_id':plane,
                            'anclas':[anchor('A1','VA',[.1,.875]),anchor('A2','VB',[.9,.875]),anchor('A3','VC',[.9,.125])],
                            'controles':[],'puntos':[point('PN1',[.93,.6]),point('PN2',[.98,.6]),point('PN3',[.93,.55])]}],
                'elementos':[{'id':'NUEVA_LOSA','tipo':'losa','accion':'nuevo','vertices':['PN1','PN2','PN3'],'dibujos':['D1'],'evidencias':refs}],
                'aberturas':[],'faltantes':['Proyecto sintético incompleto; sin revisión técnica humana.']}

    def execute(self):
        job=self.service.preparar_originales(self.body());self.assertFalse(self.sent)
        self.service.ejecutar({'caso':fixtures.CASO,'expediente_sha256':self.f.fp,'trabajo':job['id'],'confirmacion_explicita':True})
        self.service._threads[job['id']].join(30);self.assertFalse(self.service._threads[job['id']].is_alive())
        return self.service.consultar(fixtures.CASO,self.f.fp,job['id'])

    def test_preparar_no_envia_y_flujo_calibra_y_publica_borradores_con_fuentes(self):
        self.answer=self.raw();result=self.execute()
        self.assertEqual(result['estado'],'contornos_borrador',result['paso'])
        data=result['resultado'];self.assertEqual(len(self.sent),1)
        self.assertTrue(data['incorporacion']['aplicado'],data['incorporacion'].get('conflictos'))
        self.assertIsNotNone(data['geometria_version']);self.assertIsNotNone(data['configuracion_preparacion'])
        child=gg.consultar_version(self.f.app.raiz,fixtures.CASO,data['geometria_version'])
        self.assertTrue(child.comprobacion.correcta);self.assertIsNone(child.geometria['revision']['aprobacion'])
        self.assertTrue(child.comprobacion.validacion['datos_sinteticos'])
        self.assertTrue(any(s['id']=='NUEVA_LOSA' for s in child.geometria['superficies']))
        self.assertEqual(gg.consultar_version(self.f.app.raiz,fixtures.CASO,self.geom).geometria,self.geo['datos'])
        config=self.f.app.preparacion_configuracion.consultar(fixtures.CASO,self.f.fp,data['configuracion_preparacion'])
        self.assertEqual(config['registro']['padre']['id'],self.prep['id'])
        self.assertTrue(any(p['id']=='PN1' for p in config['datos']['puntos']))
        again=self.service.recuperar({'caso':fixtures.CASO,'expediente_sha256':self.f.fp,'trabajo':result['id']})
        self.assertEqual(again['resultado']['geometria_version'],data['geometria_version']);self.assertEqual(len(self.sent),1)

    def test_respuesta_ajena_se_conserva_sin_publicar_y_sin_reintento(self):
        self.answer=self.raw();self.answer['dibujos'][0]['plano_id']='PLANO_NO_EXISTE'
        before=self.f.app.geometrias(fixtures.CASO);result=self.execute()
        self.assertEqual(result['estado'],'fallido_no_reintentar');self.assertEqual(len(self.sent),1)
        self.assertEqual(self.f.app.geometrias(fixtures.CASO),before)

    def test_criterios_invalidos_no_se_envian(self):
        body=self.body();body['limites_digitizacion']['localizacion_uv']=0
        with self.assertRaises(ValueError):self.service.preparar_originales(body)
        self.assertFalse(self.sent)

    def test_rutas_http_preparacion_consulta_y_confirmacion_sin_envio(self):
        from types import SimpleNamespace
        from urllib.parse import urlencode
        from tests.test_revision_visual import HTTPRevisionTests
        self.f.app._contornos=self.service
        client=HTTPRevisionTests();client.server=SimpleNamespace(revision=self.f.app,token='TOKEN-SOLO-PRUEBA',origen='http://127.0.0.1:8766')
        status,raw,_=client.request('POST','/api/contornos/preparar',self.body())
        self.assertEqual(status,201,raw);job=json.loads(raw)
        identity={'caso':fixtures.CASO,'expediente_sha256':self.f.fp}
        status,raw,_=client.request('GET','/api/contornos/historial?'+urlencode(identity))
        self.assertEqual(status,200,raw);self.assertIn(job['id'],json.loads(raw)['trabajos'])
        status,raw,_=client.request('GET','/api/contornos/estado?'+urlencode({**identity,'trabajo':job['id']}))
        self.assertEqual(status,200,raw);self.assertEqual(json.loads(raw)['estado'],'preparado')
        status,_,_=client.request('POST','/api/contornos/ejecutar',{**identity,'trabajo':job['id'],'confirmacion_explicita':False})
        self.assertEqual(status,409)
        status,_,_=client.request('POST','/api/contornos/recuperar',{**identity,'trabajo':job['id']})
        self.assertEqual(status,409);self.assertFalse(self.sent)


if __name__=='__main__':unittest.main()
