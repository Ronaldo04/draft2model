import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from draft2model.revision_visual import RevisionLocal
from draft2model.revision_reconstruccion import ServicioReconstruccion,peticion
from tests import test_entrada_vision as vision_fixtures
from tests.test_reconstruccion_automatica import fixture


def wire(data):
    data=copy.deepcopy(data);table=[];index={}
    def refs(items):
        result=[]
        for e in items:
            item={k:v for k,v in e.items() if k!='original_sha256'}
            signature=json.dumps(item,sort_keys=True)
            if signature not in index:
                ident='E'+str(len(table)+1);index[signature]=ident;table.append({'id':ident,**item})
            result.append(index[signature])
        return result
    data['evidencia_unidad']=refs(data['evidencia_unidad'])
    for k in ('niveles','puntos','medidas','alineaciones','elementos'):
        for item in data[k]:item['evidencias']=refs(item['evidencias'])
    data['version_contrato']='0.2.0';data['evidencias']=table
    return data


class ReconstruccionWebTests(unittest.TestCase):
    def setUp(self):
        self.f=vision_fixtures.EntradaVisionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.packet=self.f.pack();self.app=RevisionLocal(self.f.case.parent)
        self.caso=self.f.case.name;self.fp=self.app.expediente(self.caso)[2]
        self.quota=self.f.root/'consumo.json';self.quota.write_text('{"openai":[],"gemini":[]}',encoding='utf-8')
        data,_=fixture();data['caso']=self.caso
        original=json.loads(self.f.manifest.read_text(encoding='utf-8'))['archivos'][0]
        for key in ('evidencia_unidad',):
            for e in data[key]:e.update(archivo_id=original['id'],original_sha256=original['sha256'])
        self.answer=data;self.calls=[]
        self.guard=patch('draft2model.proveedor_openai._http',side_effect=AssertionError('No red real'))
        self.guard.start();self.addCleanup(self.guard.stop)

    def service(self,answer=None):
        def transport(payload,timeout):
            self.calls.append(payload)
            return {'id':'sintetico','status':'completed','model':'fixture','output':[{'type':'message','role':'assistant',
                    'content':[{'type':'output_text','text':json.dumps(wire(answer or self.answer))}]}]}
        return ServicioReconstruccion(self.app,transport,self.quota)

    def body(self,**changes):
        return {'caso':self.caso,'expediente_sha256':self.fp,'paquete':self.packet.parent.name,
                'proveedor':'openai','modelo':'fixture','max_tokens':4096,'clave_solicitud':'a'*32,**changes}

    def run_job(self,service,job):
        service.ejecutar({'caso':self.caso,'expediente_sha256':self.fp,'trabajo':job['id'],'confirmacion_explicita':True})
        thread=service._threads[job['id']];thread.join(15);self.assertFalse(thread.is_alive())
        return service.consultar(self.caso,self.fp,job['id'])

    def test_preparacion_local_idempotente_sin_base64_guardado(self):
        s=self.service();a=s.preparar(self.body());b=s.preparar(self.body())
        self.assertEqual(a['id'],b['id']);self.assertEqual(self.calls,[])
        p=self.f.case/'reconstrucciones'/a['id']/'entrada.json'
        self.assertNotIn('data:image',p.read_text(encoding='utf-8'))
        with self.assertRaises(ValueError):s.preparar(self.body(modelo='otro'))

    def test_cadena_programada_de_respuesta_a_geometria_sintetica(self):
        s=self.service();job=s.preparar(self.body());result=self.run_job(s,job)
        self.assertEqual(result['estado'],'geometria_borrador')
        self.assertTrue(result['resultado']['simulado']);self.assertIsNone(result['resultado']['geometria_version'])
        self.assertEqual(result['resultado']['geometria']['procedencia']['tipo'],'sintetico')
        self.assertFalse(result['aprueba_ingenieria']);self.assertEqual(len(self.calls),1)
        with self.assertRaises(ValueError):self.run_job(s,job)
        self.assertEqual(len(self.calls),1)

    def test_unidad_no_se_respalda_en_pagina_no_enviada(self):
        data=copy.deepcopy(self.answer);data['evidencia_unidad']=copy.deepcopy(data['evidencia_unidad'])
        data['evidencia_unidad'][0]['pagina']=999
        service=self.service(data);result=self.run_job(service,service.preparar(self.body()))
        self.assertEqual(result['estado'],'fallido_no_reintentar')
        self.assertIn('unidad cita una página que no se envió',result['paso'])
        self.assertIsNone(result['resultado']);self.assertEqual(len(self.calls),1)

    def test_faltantes_se_informan_sin_geometria_falsa(self):
        data=copy.deepcopy(self.answer);data['alineaciones'].pop()
        s=self.service(data);result=self.run_job(s,s.preparar(self.body()))
        self.assertEqual(result['estado'],'terminado_con_faltantes');self.assertIsNone(result['resultado']['geometria'])
        self.assertTrue(result['resultado']['faltantes'])

    def test_pagina_no_enviada_rechazada(self):
        data=copy.deepcopy(self.answer);data['puntos'][0]['evidencias'][0]['pagina']=2
        s=self.service(data);result=self.run_job(s,s.preparar(self.body()))
        self.assertEqual(result['estado'],'fallido_no_reintentar');self.assertIsNone(result['resultado'])

    def test_cuota_preserva_y_cuenta_reservas_fallidas(self):
        s=ServicioReconstruccion(self.app,registro_cuota=self.quota)
        for i in range(5):s._reservar('openai',str(i)*32,'fixture')
        with self.assertRaises(ValueError):s._reservar('openai','f'*32,'fixture')
        self.assertEqual(len(json.loads(self.quota.read_text())['openai']),5)

    def test_payload_google_mismo_contrato_no_lecturas_aisladas(self):
        payload,proof=peticion(self.f.manifest,self.packet,proveedor='gemini',modelo='fixture',max_tokens=4096)
        schema=payload['body']['generationConfig']['responseJsonSchema']
        self.assertIn('alineaciones',schema['properties']);self.assertIn('elementos',schema['properties'])
        self.assertNotIn('candidatos',schema['properties']);self.assertEqual(proof['imagenes'],2)

    def test_originales_preparados_sin_intervencion_ni_red(self):
        s=self.service();body=self.body();body.pop('paquete')
        job=s.preparar_originales(body)
        self.assertEqual(job['estado'],'preparado');self.assertEqual(job['preparacion']['imagenes'],8)
        self.assertEqual(self.calls,[])
        again=s.preparar_originales(body);self.assertEqual(again['id'],job['id'])

    def test_original_alterado_invalida_consulta(self):
        s=self.service();job=s.preparar(self.body())
        source=next((self.f.case/'originales').iterdir());source.write_bytes(source.read_bytes()+b'alterado')
        with self.assertRaises(ValueError):s.consultar(self.caso,self.fp,job['id'])

    def test_rutas_http_y_confirmacion_local(self):
        from types import SimpleNamespace
        from urllib.parse import urlencode
        from tests import test_revision_visual as http_fixtures
        server=http_fixtures.HTTPRevisionTests()
        self.app._reconstruccion=self.service()
        server.server=SimpleNamespace(revision=self.app,token='token-test',origen='http://127.0.0.1:8766')
        status,raw,_=server.request('GET','/api/reconstruccion/cuota')
        self.assertEqual(status,200);self.assertEqual(json.loads(raw)['openai']['restantes'],5)
        body=self.body();body.pop('paquete')
        status,raw,_=server.request('POST','/api/reconstruccion/preparar',body)
        self.assertEqual(status,201,raw);job=json.loads(raw)['id']
        query=urlencode({'caso':self.caso,'expediente_sha256':self.fp,'trabajo':job})
        status,raw,_=server.request('GET','/api/reconstruccion/estado?'+query)
        self.assertEqual(status,200);self.assertEqual(json.loads(raw)['estado'],'preparado')
        status,_,_=server.request('POST','/api/reconstruccion/ejecutar',{},headers={'Origin':'https://otro.test'})
        self.assertEqual(status,403);self.assertEqual(self.calls,[])

    def test_simulacion_no_pierde_marca_al_reabrir_con_servicio_real(self):
        s=self.service();job=s.preparar(self.body());self.run_job(s,job)
        reopened=ServicioReconstruccion(self.app,registro_cuota=self.quota)
        self.assertTrue(reopened.consultar(self.caso,self.fp,job['id'])['simulado'])

    def test_ampliacion_autorizada_respeta_nuevo_tope(self):
        self.quota.write_text('{"openai":[],"gemini":[],"limites_autorizados":{"openai":10,"gemini":5}}',encoding='utf-8')
        s=ServicioReconstruccion(self.app,registro_cuota=self.quota)
        for i in range(10):s._reservar('openai',format(i,'032x'),'fixture')
        with self.assertRaises(ValueError):s._reservar('openai','f'*32,'fixture')
        self.assertEqual(s.estado_cuota()['openai']['restantes'],0)

    def test_evidencia_compartida_conserva_trazabilidad_sin_repetir_hashes(self):
        from draft2model.reconstruccion_automatica import expandir_respuesta
        manifest=json.loads(self.f.manifest.read_text(encoding='utf-8'))
        compact=wire(self.answer);expanded=expandir_respuesta(compact,manifest)
        self.assertEqual(expanded,self.answer)
        self.assertLess(len(json.dumps(compact)),len(json.dumps(self.answer)))
        compact['puntos'][0]['evidencias']=['E-no-existe']
        with self.assertRaises(ValueError):expandir_respuesta(compact,manifest)

    def test_recuperar_reevalua_respuesta_conservada_sin_nueva_llamada_api(self):
        data=copy.deepcopy(self.answer);data['unidad']='desconocida';data['evidencia_unidad']=[]
        s=self.service(data);job=s.preparar(self.body());first=self.run_job(s,job)
        self.assertEqual(first['estado'],'terminado_con_faltantes')
        self.assertTrue(first['tiene_respuesta_conservada'])
        self.assertEqual(len(self.calls),1)
        recovered=s.recuperar({'caso':self.caso,'expediente_sha256':self.fp,'trabajo':job['id'],
            'unidad_revisada':{'unidad':'m','revisor':'Ing. Revisión','motivo':'Niveles NPT en metros.'}})
        self.assertEqual(recovered['estado'],'geometria_borrador')
        self.assertEqual(len(self.calls),1)
        self.assertEqual(recovered['resultado']['unidad_declarada_ingenieria']['unidad'],'m')
        self.assertTrue(recovered['simulado'])


if __name__=='__main__':unittest.main()
