import copy
import json
import unittest
from unittest.mock import patch
from draft2model.preparacion_configuracion import ServicioPreparacionConfiguracion, conexiones_exactas, lecturas_tecnicas
from draft2model.revision_visual import RevisionLocal
from tests import test_integracion_malla as fixtures
from tests import test_gestion_geometria as disco


class PreparacionConfiguracionTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.CasoMalla();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.base=self.f.montar('vertical');self.app=RevisionLocal(self.f.raiz)
        self.fp=self.app.expediente(disco.CASO)[2];self.service=ServicioPreparacionConfiguracion(self.app)

    def crear(self):
        return self.service.crear({'caso':disco.CASO,'expediente_sha256':self.fp,'geometria':self.f.version.identificador})

    def guardar(self,current,data):
        return self.service.guardar({'caso':disco.CASO,'expediente_sha256':self.fp,'version':current['id'],
               'sha256_configuracion':current['sha256_configuracion'],'configuracion_json':json.dumps(data)})

    def test_preparacion_vinculada_sin_inventar_datos_ni_aprobar(self):
        result=self.crear();data=result['datos']
        self.assertEqual(len(data['puntos']),len(self.f.geo['vertices']))
        self.assertTrue(data['datos_sinteticos'])
        self.assertEqual((data['materiales'],data['cargas'],data['apoyos']),([],[],[]))
        self.assertIsNone(data['masa']);self.assertFalse(result['puede_registrar'])
        self.assertEqual(data['revision'],{'estado':'borrador','aprobacion':None})
        self.assertFalse(result['ejecuta_etabs'])

    def test_edicion_incompleta_se_conserva_como_nueva_version(self):
        first=self.crear();data=copy.deepcopy(first['datos']);data['sitio']={'descripcion':'Revisión pendiente'}
        second=self.guardar(first,data)
        self.assertNotEqual(first['id'],second['id'])
        self.assertIsNone(self.service.consultar(disco.CASO,self.fp,first['id'])['datos']['sitio'])
        self.assertEqual(second['datos']['sitio'],data['sitio']);self.assertFalse(second['puede_registrar'])

    def test_no_cambia_geometria_origen_ni_fabrica_aprobacion(self):
        first=self.crear()
        for change in ('geometry','approval','identity'):
            data=copy.deepcopy(first['datos'])
            if change=='geometry':data['geometria_origen']['version_id']='0'*32
            elif change=='approval':data['revision']={'estado':'aprobado','aprobacion':{}}
            else:data['caso']='otro'
            with self.assertRaises(ValueError):self.guardar(first,data)

    def test_alteracion_de_padre_invalida_revision(self):
        first=self.crear();second=self.guardar(first,first['datos'])
        folder=self.f.raiz/disco.CASO/'configuraciones_en_preparacion'/first['id']
        p=folder/'configuracion.json';p.write_bytes(p.read_bytes()+b' ')
        with self.assertRaises(ValueError):self.service.consultar(disco.CASO,self.fp,second['id'])

    def test_configuracion_incompleta_no_entra_en_registro_formal(self):
        first=self.crear();result=self.service.registrar({'caso':disco.CASO,'expediente_sha256':self.fp,
                 'version':first['id'],'sha256_configuracion':first['sha256_configuracion']})
        self.assertFalse(result['registrada']);self.assertTrue(result['validacion']['errores'])

    def test_borrador_completo_se_registra_una_sola_vez(self):
        first=self.crear();data=copy.deepcopy(self.base);data['id']=first['datos']['id']
        data['version_contrato']='0.5.0'
        data['liquidos']={'aplicabilidad':'ausente_confirmado','fuente':data['fuentes'][0]['id'],
                         'motivo':'Fixture sintética sin depósitos de líquido.','declaraciones':[]}
        # Configuración sintética completa del fixture de malla; no representa el piloto.
        data=self.f.completar(data);data['revision']={'estado':'borrador','aprobacion':None}
        second=self.guardar(first,data)
        body={'caso':disco.CASO,'expediente_sha256':self.fp,'version':second['id'],
              'sha256_configuracion':second['sha256_configuracion']}
        one=self.service.registrar(body);two=self.service.registrar(body)
        self.assertTrue(one['registrada']);self.assertEqual(one['configuracion'],two['configuracion'])

    def test_rutas_web_no_admiten_otro_origen_y_no_exigen_archivos_externos(self):
        from types import SimpleNamespace
        from urllib.parse import urlencode
        from tests import test_revision_visual as http
        client=http.HTTPRevisionTests();client.server=SimpleNamespace(revision=self.app,token='token-test',origen='http://127.0.0.1:8766')
        body={'caso':disco.CASO,'expediente_sha256':self.fp,'geometria':self.f.version.identificador}
        status,_,_=client.request('POST','/api/configuracion/preparacion/crear',body,headers={'Origin':'https://otro.test'})
        self.assertEqual(status,403)
        status,raw,_=client.request('POST','/api/configuracion/preparacion/crear',body)
        self.assertEqual(status,201,raw);created=json.loads(raw)
        query=urlencode({'caso':disco.CASO,'expediente_sha256':self.fp,'version':created['id']})
        status,raw,_=client.request('GET','/api/configuracion/preparacion?'+query)
        self.assertEqual(status,200);self.assertEqual(json.loads(raw)['datos']['geometria_origen']['version_id'],body['geometria'])
        select={k:created[k] for k in ('caso','expediente_sha256','sha256_configuracion')};select['version']=created['id']
        status,raw,_=client.request('POST','/api/configuracion/preparacion/conexiones/proponer',select)
        self.assertEqual(status,201,raw);proposal=json.loads(raw)
        declaration={**select,'sha256_propuesta':proposal['sha256_propuesta'],'conexiones_seleccionadas':[],
                     'confirmacion_explicita':True,'declaracion':{'declarado_por':'Revisor SINTÉTICO','fecha':'2026-10-24','alcance':'Sin conexiones en el ejemplo aislado.'}}
        status,raw,_=client.request('POST','/api/configuracion/preparacion/conexiones/declarar',declaration)
        self.assertEqual(status,201,raw);self.assertNotEqual(json.loads(raw)['id'],created['id'])

    def test_continuidad_seleccionada_se_calcula_y_versiona_sin_aprobar(self):
        self.f.montar('conectados');first=self.crear()
        body={'caso':disco.CASO,'expediente_sha256':self.fp,'version':first['id'],'sha256_configuracion':first['sha256_configuracion']}
        proposal=self.service.proponer_conexiones(body)
        self.assertEqual(proposal['cantidad'],1);self.assertFalse(proposal['modifica_configuracion'])
        declaration={'declarado_por':'Revisor SINTÉTICO','fecha':'2026-10-24','alcance':'Unión sintética explícita del muro y la losa.'}
        request={**body,'sha256_propuesta':proposal['sha256_propuesta'],'conexiones_seleccionadas':[proposal['conexiones'][0]['id']],
                 'declaracion':declaration,'confirmacion_explicita':True}
        second=self.service.declarar_conexiones(request)
        self.assertNotEqual(first['id'],second['id'])
        self.assertEqual(len(second['datos']['conexiones_borde']['conexiones']),1)
        self.assertIsNone(self.service.consultar(disco.CASO,self.fp,first['id'])['datos']['conexiones_borde'])
        self.assertEqual(second['datos']['revision'],{'estado':'borrador','aprobacion':None})
        self.assertFalse(second['ejecuta_etabs'])
        request['conexiones_seleccionadas']=[]
        empty=self.service.declarar_conexiones(request)
        self.assertEqual(empty['datos']['conexiones_borde']['conexiones'],[])

    def test_continuidad_rechaza_propuesta_cambiada_seleccion_ajena_y_declaracion_vacia(self):
        first=self.crear();body={'caso':disco.CASO,'expediente_sha256':self.fp,'version':first['id'],'sha256_configuracion':first['sha256_configuracion']}
        proposal=self.service.proponer_conexiones(body)
        valid={**body,'sha256_propuesta':proposal['sha256_propuesta'],'conexiones_seleccionadas':[],
               'declaracion':{'declarado_por':'Revisor sintético','fecha':'2026-10-24','alcance':'Sin uniones en este ejemplo.'},'confirmacion_explicita':True}
        for key,value in [('sha256_propuesta','0'*64),('conexiones_seleccionadas',['NOEXISTE']),('confirmacion_explicita',False)]:
            with self.subTest(key=key),self.assertRaises(ValueError):self.service.declarar_conexiones({**valid,key:value})
        for field,value in [('declarado_por',' '),('alcance',''),('fecha','2026-02-30')]:
            invalid=copy.deepcopy(valid);invalid['declaracion'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):self.service.declarar_conexiones(invalid)

    def test_material_desde_lectura_calcula_y_conserva_sin_aprobar(self):
        first=self.crear();reading={'id':'R1','tipo':'propiedad','valor_propuesto':210,'unidad':'kgf/cm2',
            'texto_fuente':"f'c=210 kgf/cm2",'simbolo':"f'c",'evidencia':[], 'revision':{'estado':'pendiente','historial':[]}}
        response={'expediente_sha256':self.fp,'huella':'a'*64,'datos':{'candidatos':[reading]}}
        body={'caso':disco.CASO,'expediente_sha256':self.fp,'version':first['id'],'sha256_configuracion':first['sha256_configuracion'],
              'extraccion':'e'*32,'huella_lectura':'a'*64,'lectura':'R1','material_id':'CONCRETO1','peso_kN_m3':24,
              'concreto_normal_sin_ensayos':True,'confirmacion_explicita':True,
              'declaracion':{'declarado_por':'Revisor SINTÉTICO','fecha':'2026-10-25','alcance':'Condiciones sintéticas de material, no piloto.'}}
        with patch.object(self.app,'version',return_value=response):
            result=self.service.material_desde_lectura(body)
            import math
            expected=4700*math.sqrt(210*.0980665)*1000
            self.assertAlmostEqual(result['datos']['materiales'][0]['E_kN_m2'],expected)
            self.assertAlmostEqual(result['datos']['materiales'][0]['poisson'],.15)
            self.assertIsNone(result['datos']['revision']['aprobacion']);self.assertNotEqual(first['id'],result['id'])
            self.assertEqual(reading['revision']['estado'],'pendiente');self.assertFalse(result['ejecuta_etabs'])
            self.assertEqual(self.service.consultar(disco.CASO,self.fp,first['id'])['datos']['materiales'],[])
            for key,value in [('huella_lectura','b'*64),('lectura','OTRA'),('peso_kN_m3',True),('concreto_normal_sin_ensayos',False),('confirmacion_explicita',False)]:
                with self.subTest(key=key),self.assertRaises(ValueError):self.service.material_desde_lectura({**body,key:value})

    def test_lecturas_no_exportan_rechazados_resultados_y_respetan_correcciones(self):
        base={'id':'R1','tipo':'propiedad','valor_propuesto':210,'unidad':'kgf/cm2','texto_fuente':"f'c=210",'evidencia':[],
              'revision':{'estado':'pendiente','historial':[]}}
        rejected=copy.deepcopy(base);rejected['revision']['estado']='rechazado'
        result=copy.deepcopy(base);result['tipo']='resultado_impreso'
        corrected=copy.deepcopy(base);corrected['revision']={'estado':'aceptado','historial':[{'valor_revisado':28,'unidad_revisada':'MPa'}]}
        values=lecturas_tecnicas({'candidatos':[base,rejected,result,corrected]})
        self.assertEqual(len(values),2);self.assertTrue(values[0]['resistencia_concreto'])
        self.assertEqual((values[1]['valor'],values[1]['unidad']),(28,'MPa'))
        steel=copy.deepcopy(base);steel['texto_fuente']='fy=4200'
        self.assertFalse(lecturas_tecnicas({'candidatos':[steel]})[0]['resistencia_concreto'])


class PropuestaGeometricaTests(unittest.TestCase):
    def geometria(self,offset=0):
        return fixtures.datos.geometria_superficies(vertices={'A':(0,0,0),'B':(0,4,0),'C':(0,4,3),'D':(0,0,3),
            'E':(offset,1,3),'F':(offset,3,3),'G':(2,3,3),'H':(2,1,3)},
            superficies=[('MURO',['A','B','C','D'],'Sintético'),('LOSA',['E','F','G','H'],'Sintético')],aprobar=False)

    def test_solape_parcial_se_detecta_y_no_un_contacto_puntual_o_proximo(self):
        geo=self.geometria();geo.update(version_contrato='0.3.0',aberturas=[])
        self.assertEqual(len(conexiones_exactas(geo)),1)
        close=self.geometria(1e-6);close.update(version_contrato='0.3.0',aberturas=[])
        self.assertEqual(conexiones_exactas(close),[])
        for v in geo['vertices']:
            if v['id'] in ('E','F','G','H'):v['y']+=3
        self.assertEqual(conexiones_exactas(geo),[])

    def test_superficie_duplicada_exige_revision(self):
        geo=self.geometria();geo.update(version_contrato='0.3.0',aberturas=[])
        repeated=copy.deepcopy(geo['superficies'][0]);repeated['id']='DUP';geo['superficies'].append(repeated)
        with self.assertRaisesRegex(ValueError,'coincidentes'):conexiones_exactas(geo)


if __name__=='__main__':unittest.main()
