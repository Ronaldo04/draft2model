"""Lectura dirigida y reaplicación local con transportes exclusivamente sintéticos."""
import copy
import json
import unittest
from unittest.mock import patch
from pathlib import Path

from draft2model.revision_visual import RevisionLocal
from draft2model.revision_parametros import ServicioParametros
from draft2model.lectura_parametros import validar_respuesta
from tests import test_integracion_malla as fixtures
from tests import test_gestion_geometria as disk


def respuesta(caso,original,*,completo=True):
    refs=['E1'];q=lambda name,value,unit:{'nombre':name,'valor':value,'unidad':unit,'evidencias':refs}
    return {'contrato':'draft2model.parametros_planos','version_contrato':'0.1.0','caso':caso,
        'evidencias':[{'id':'E1','archivo_id':original,'pagina':1,'bbox_normalizada':[.1,.1,.8,.8],
                       'texto':"Especificaciones SINTÉTICAS: f'c=210 kgf/cm2; E=25000 MPa; nu=0.2; peso=24 kN/m3; e=0.20m"}],
        'materiales':[{'id':'MAT','nombre':'Concreto SINTÉTICO','clase':'concreto','evidencias':refs,
             'propiedades':[q('E',25000,'MPa'),q('poisson',.2,'adimensional'),q('peso_especifico',24,'kN/m3')] if completo else [q('fc',210,'kgf/cm2')]}],
        'secciones':[{'id':'LOSA','nombre':'Losa maciza SINTÉTICA','tipo':'losa_maciza','material':'MAT',
                       'parametros':[q('espesor',.2,'m')],'evidencias':refs}],
        'asignaciones':[{'elemento':'S1','seccion':'LOSA','evidencias':refs}],
        'cargas':[],'faltantes':['Hipótesis sintéticas de prueba; no proyecto real.']}


class LecturaParametrosTests(unittest.TestCase):
    def setUp(self):
        # El fixture geométrico original usa bytes PDF mínimos sin render; aquí
        # se necesita un original sintético real para preparar imágenes.
        import pymupdf
        registrar=disk.registrar_expediente
        def registrar_renderizable(caso,archivos,raiz,**kwargs):
            doc=pymupdf.open();page=doc.new_page(width=600,height=500)
            page.insert_text((30,40),'PLANO SINTETICO PARA PRUEBA DE SOFTWARE')
            raw=doc.tobytes();doc.close()
            for path in archivos:Path(path).write_bytes(raw)
            return registrar(caso,archivos,raiz,**kwargs)
        self.f=fixtures.CasoMalla()
        with patch.object(disk,'registrar_expediente',side_effect=registrar_renderizable):self.f.setUp()
        self.addCleanup(self.f.doCleanups);self.f.montar('horizontal')
        self.app=RevisionLocal(self.f.raiz);self.caso=disk.CASO;self.fp=self.app.expediente(self.caso)[2]
        self.initial=self.app.preparacion_configuracion.crear({'caso':self.caso,'expediente_sha256':self.fp,'geometria':self.f.version.identificador})
        self.original=self.app.expediente(self.caso)[1]['archivos'][0]['id'];self.calls=[]
        self.quota=self.f.raiz/'cuota_test.json';self.quota.write_text('{"openai":[],"gemini":[]}',encoding='utf-8')
        self.guard=patch('draft2model.proveedor_openai._http',side_effect=AssertionError('No red real en prueba'))
        self.guard.start();self.addCleanup(self.guard.stop)

    def service(self,answer=None):
        def transport(payload,timeout):
            self.calls.append(payload)
            return {'id':'respuesta-SINTETICA','status':'completed','model':'fixture','output':[{'type':'message','role':'assistant',
                     'content':[{'type':'output_text','text':json.dumps(answer or respuesta(self.caso,self.original))}]}]}
        return ServicioParametros(self.app,transporte=transport,registro_cuota=self.quota)

    def prepare(self,service):
        return service.preparar_originales({'caso':self.caso,'expediente_sha256':self.fp,'proveedor':'openai','modelo':'fixture',
            'max_tokens':8192,'clave_solicitud':'a'*32,'configuracion_preparacion':self.initial['id'],
            'sha256_configuracion':self.initial['sha256_configuracion']})

    def execute(self,service,job):
        service.ejecutar({'caso':self.caso,'expediente_sha256':self.fp,'trabajo':job['id'],'confirmacion_explicita':True})
        service._threads[job['id']].join(20);self.assertFalse(service._threads[job['id']].is_alive())
        return service.consultar(self.caso,self.fp,job['id'])

    def test_preparacion_sin_envio_y_cadena_a_configuracion_y_lecturas(self):
        service=self.service();job=self.prepare(service);self.assertEqual(self.calls,[])
        result=self.execute(service,job);self.assertEqual(result['estado'],'parametros_borrador',result['paso'])
        record=result['resultado'];self.assertTrue(record['simulado']);self.assertIsNone(record['geometria_version'])
        self.assertEqual(len(self.calls),1);self.assertIn('lecturas_ingenieria',str(self.f.raiz/self.caso/'lecturas_ingenieria'/job['id']))
        child=self.app.preparacion_configuracion.consultar(self.caso,self.fp,record['configuracion_preparacion'])
        self.assertEqual(child['datos']['secciones'][0]['id'],'LOSA');self.assertEqual(child['datos']['materiales'][0]['E_kN_m2'],25000000)
        self.assertEqual(child['datos']['revision'],{'estado':'borrador','aprobacion':None});self.assertTrue(child['datos']['datos_sinteticos'])
        self.assertIsNone(record['extraccion']);extraction=record['lecturas_propuestas']
        self.assertTrue(extraction['candidatos']);self.assertTrue(all(c['revision']['estado']=='pendiente' for c in extraction['candidatos']))
        self.assertEqual(extraction['procedencia']['tipo'],'sintetico')
        repeat=service.recuperar({'caso':self.caso,'expediente_sha256':self.fp,'trabajo':job['id']})
        self.assertEqual(repeat['resultado']['configuracion_preparacion'],record['configuracion_preparacion'])
        self.assertIsNone(repeat['resultado']['extraccion']);self.assertEqual(len(self.calls),1)
        with self.assertRaises(ValueError):self.execute(service,job)
        self.assertEqual(len(self.calls),1)

    def test_datos_incompletos_y_reaplicacion_sin_api_despues_de_completar_material(self):
        service=self.service(respuesta(self.caso,self.original,completo=False));result=self.execute(service,self.prepare(service))
        self.assertEqual(result['estado'],'parametros_borrador',result['paso']);record=result['resultado']
        self.assertEqual(record['materiales_para_revision'][0]['material_id'],'MAT')
        self.assertIn(record['materiales_para_revision'][0]['lectura'],
                      {row['id'] for row in record['lecturas_propuestas']['candidatos']})
        old=self.app.preparacion_configuracion.consultar(self.caso,self.fp,record['configuracion_preparacion'])
        self.assertEqual(old['datos']['materiales'],[]);self.assertTrue(record['aplicacion']['faltantes'])
        data=copy.deepcopy(old['datos']);data['materiales']=[{'id':'MAT','tipo':'isotropo_lineal','E_kN_m2':25000000,
                'poisson':.2,'peso_kN_m3':24,'fuente':data['fuentes'][0]['id']}]
        manual=self.app.preparacion_configuracion.guardar({'caso':self.caso,'expediente_sha256':self.fp,
            'version':old['id'],'sha256_configuracion':old['sha256_configuracion'],'configuracion_json':json.dumps(data)})
        body={'caso':self.caso,'expediente_sha256':self.fp,'trabajo':result['id'],'configuracion_preparacion':manual['id'],
              'sha256_configuracion':manual['sha256_configuracion'],'clave_aplicacion':'b'*32}
        applied=service.aplicar(body);again=service.aplicar(body)
        self.assertEqual(applied['configuracion_preparacion'],again['configuracion_preparacion']);self.assertEqual(applied['envios_api'],0)
        child=self.app.preparacion_configuracion.consultar(self.caso,self.fp,applied['configuracion_preparacion'])
        self.assertEqual(child['datos']['secciones'][0]['id'],'LOSA');self.assertIsNone(child['datos']['revision']['aprobacion']);self.assertEqual(len(self.calls),1)
        with self.assertRaises(ValueError):service.aplicar({**body,'sha256_configuracion':'f'*64})

    def test_fuente_no_enviada_se_conserva_como_fallo_sin_configuracion_falsa(self):
        answer=respuesta(self.caso,self.original);answer['evidencias'][0]['pagina']=999
        service=self.service(answer);result=self.execute(service,self.prepare(service))
        self.assertEqual(result['estado'],'fallido_no_reintentar');self.assertIsNone(result['resultado']);self.assertEqual(len(self.calls),1)

    def test_cliente_http_doble_importa_lecturas_y_reserva_una_cuota_local(self):
        service=ServicioParametros(self.app,registro_cuota=self.quota)
        def http(payload,key,timeout):
            self.calls.append(payload)
            return {'id':'HTTP-DOBLE-SINTETICO','status':'completed','model':'fixture','output':[{'type':'message','role':'assistant',
                'content':[{'type':'output_text','text':json.dumps(respuesta(self.caso,self.original))}]}]}
        with patch.object(service,'_key',return_value='CLAVE-FICTICIA-DE-PRUEBA'),patch('draft2model.proveedor_openai._http',side_effect=http):
            result=self.execute(service,self.prepare(service));self.assertEqual(result['estado'],'parametros_borrador',result['paso'])
            record=result['resultado'];self.assertIsNotNone(record['extraccion'])
            extracted=self.app.version(self.caso,record['extraccion'])['datos']
            self.assertTrue(all(c['revision']['estado']=='pendiente' for c in extracted['candidatos']))
            service.recuperar({'caso':self.caso,'expediente_sha256':self.fp,'trabajo':result['id']})
            self.assertEqual(len(self.calls),1);self.assertEqual(len(json.loads(self.quota.read_text())['openai']),1)


class ContratoParametrosTests(unittest.TestCase):
    def test_material_desconocido_puede_conservarse_y_asignacion_ajena_es_advertencia(self):
        data=respuesta('caso','L1');data['secciones'][0]['material']='desconocido';data['asignaciones'][0]['elemento']='NO-DECLARADO'
        result=validar_respuesta(data,{'id':'caso','archivos':[{'id':'L1','sha256':'a'*64}]},{('L1',1)},{'S1'})
        self.assertEqual(len(result['advertencias']),1);self.assertIsNone(result['revision']['aprobacion'])
        self.assertEqual(result['datos']['evidencias'][0]['original_sha256'],'a'*64)


if __name__=='__main__':unittest.main()
