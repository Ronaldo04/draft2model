"""Trabajos de análisis con datos y transporte fabricados, sin ETABS ni red."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

from draft2model import adaptador_etabs as ad
from draft2model import gestion_configuracion as configs
from draft2model import modelo_estructural as me
from draft2model.analisis_etabs import AnalizadorEtabs
from draft2model.revision_analisis import ServicioAnalisis, ErrorAnalisis
from draft2model.revision_visual import RevisionLocal
from tests import test_revision_modelo as fixture_modelo


TRANSPORTE=r'''
import hashlib,json,os,sys
from pathlib import Path
a=sys.argv[1:];s=json.loads(Path(a[a.index('-Solicitud')+1]).read_bytes());r=Path(a[a.index('-Respuesta')+1])
if os.environ.get('ABRUPTO'):sys.exit(1)
p=Path(s['destino']);p.write_bytes(b'ANALIZADO SINTETICO NO ETABS')
if os.environ.get('ALTERAR'):Path(os.environ['ALTERAR']).write_bytes(b'alterado')
out={'contrato':'draft2model.etabs_respuesta','version_contrato':'0.1.0','id_solicitud':s['id'],'operacion':'analizar_modelo','modo_ejecucion':'doble','estado':'ok','avisos':[],
 'datos':{'guardado':{'ruta':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()},'casos_ejecutados':s['casos'],
 'estados_casos':{name:(3 if os.environ.get('INCOMPLETO') else 4) for name in s['casos']},
 'sha256_entrada':s['sha256_entrada'],'analisis_ejecutado':True,'aprueba_resultados':False,'version_etabs':'DOBLE-SINTETICO'}}
r.write_text(json.dumps(out),encoding='utf-8')
'''


class AnalisisWebTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture_modelo.RevisionModeloTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.model=self.fixture.register();self.approval=self.fixture.approve(self.model)
        self.app=RevisionLocal(self.fixture.root);self.caso=self.fixture.case;self.case=self.app.raiz/self.caso
        script=self.fixture.base.trabajo/'analisis_web_doble.py';script.write_text(TRANSPORTE,encoding='utf-8')
        self.command=(sys.executable,str(script));self.env={}
        self.factory=lambda work,lock:AnalizadorEtabs(ad.ConfiguracionPuente.doble(work,self.command,lock,entorno=self.env))
        self.service=ServicioAnalisis(self.app,self.factory)
        self.body={'caso':self.caso,'modelo':self.model.name,'aprobacion':self.approval.name,
                   'expediente_sha256':self.app.expediente(self.caso)[2],'clave_solicitud':'a'*32}

    def prepare(self,**changes):return self.service.preparar({**self.body,**changes})

    def execute(self,prepared,service=None,**changes):
        return (service or self.service).ejecutar({'caso':self.caso,'trabajo':prepared['id'],
            'huella_preparacion':prepared['huella_preparacion'],'expediente_sha256':prepared['expediente_sha256'],
            'confirmacion_explicita':True,**changes})

    def finish(self,prepared,service=None):
        service=service or self.service
        service._threads[prepared['id']].join(20)
        self.assertFalse(service._threads[prepared['id']].is_alive())
        return service.consultar(self.caso,prepared['id'])

    def test_preparar_sin_procesos_replay_y_conflicto(self):
        with patch('subprocess.Popen',side_effect=AssertionError('No lanzar en preparar')):
            first=self.prepare();again=self.prepare()
        self.assertEqual(first,again);self.assertEqual(first['estado'],'preparado')
        self.assertIsNone(first['corrida_id']);self.assertEqual(first['casos'],['EST'])
        with self.assertRaisesRegex(ErrorAnalisis,'clave_reutilizada'):
            self.prepare(modelo='b'*32)
        self.assertEqual(len(self.service.listar(self.caso)['trabajos']),1)

    def test_confirmacion_reinicio_preparado_y_aceptacion_sin_normalizar(self):
        prepared=self.prepare()
        for changes in ({'confirmacion_explicita':False},{'confirmacion_explicita':1},{'huella_preparacion':'0'*64}):
            with self.subTest(changes=changes),self.assertRaises(ErrorAnalisis):self.execute(prepared,**changes)
        restarted=ServicioAnalisis(RevisionLocal(self.app.raiz),self.factory)
        self.assertEqual(self.execute(prepared,restarted)['estado'],'en_ejecucion')
        result=self.finish(prepared,restarted)
        self.assertEqual(result['estado'],'aceptado',result)
        self.assertTrue(result['vigente'] and result['calculo_verificado'] and result['analisis_ejecutado'])
        self.assertFalse(result['resultado_normalizado'] or result['aprueba_resultados'])
        self.assertEqual(result['estados_casos'],{'EST':4})
        self.assertTrue((self.case/'analisis_etabs'/result['corrida_id']/'aceptacion_analisis.json').exists())
        self.assertFalse((self.case/'resultados_estructurales').exists())
        self.assertEqual(self.execute(prepared,restarted)['estado'],'aceptado')
        final=ServicioAnalisis(RevisionLocal(self.app.raiz),self.factory).consultar(self.caso,prepared['id'])
        self.assertEqual(final,result)
        text=json.dumps(result)
        for item in (str(self.app.raiz),':\\','id_proceso','"ruta"'):self.assertNotIn(item,text)

    def test_mezcla_modelo_aprobacion_y_ids_rechazados(self):
        another_model=self.fixture.register();another_approval=self.fixture.approve(another_model)
        for changes in ({'aprobacion':another_approval.name},{'aprobacion':'b'*32},{'modelo':'../fuera'},
                        {'expediente_sha256':'0'*64},{'caso':'otro'},{'clave_solicitud':1},{'extra':True}):
            with self.subTest(changes=changes),self.assertRaises(ErrorAnalisis):self.prepare(**changes)

    def test_entradas_alteradas_impiden_proceso(self):
        for index,target in enumerate((self.fixture.base.original,self.model/'modelo.edb',self.approval/'aprobacion.json')):
            with self.subTest(target=target.name):
                prepared=self.prepare(clave_solicitud=f'{index+1:032x}');raw=target.read_bytes();target.write_bytes(raw+b'alterado')
                with patch('subprocess.Popen',side_effect=AssertionError('No debe lanzar')):
                    with self.assertRaises(ErrorAnalisis):self.execute(prepared)
                self.assertEqual(self.service.consultar(self.caso,prepared['id'])['estado'],'fallido_sin_lanzar')
                self.assertFalse(self.service.pendiente.exists())
                target.write_bytes(raw)

    def test_casos_incompletos_no_se_aceptan_y_reinicio_no_reintenta(self):
        self.env['INCOMPLETO']='1';prepared=self.prepare();self.execute(prepared);result=self.finish(prepared)
        self.assertEqual(result['estado'],'incierto');self.assertFalse(result['analisis_ejecutado'])
        self.assertTrue(self.service.pendiente.exists())
        self.assertTrue(Path(str(self.service.motor_lock)+'.incierto.json').exists())
        with patch('subprocess.Popen',side_effect=AssertionError('Reinicio no reintenta')):
            restarted=ServicioAnalisis(RevisionLocal(self.app.raiz),self.factory)
            self.assertEqual(self.execute(prepared,restarted)['estado'],'incierto')

    def test_salida_abrupta_y_fuente_cambiada_durante_motor(self):
        self.env['ABRUPTO']='1';prepared=self.prepare();self.execute(prepared);result=self.finish(prepared)
        self.assertEqual(result['estado'],'incierto')
        run=self.case/'analisis_etabs'/result['corrida_id']
        self.assertFalse((run/'aceptacion_analisis.json').exists())

    def test_original_cambiado_durante_transporte_no_se_acepta(self):
        self.env['ALTERAR']=str(self.fixture.base.original)
        prepared=self.prepare();self.execute(prepared);result=self.finish(prepared)
        self.assertEqual(result['estado'],'incierto');self.assertFalse(result['vigente'])

    def test_aceptacion_solicitud_y_edb_alterados_invalidan_consulta(self):
        prepared=self.prepare();self.execute(prepared);result=self.finish(prepared)
        self.assertEqual(result['estado'],'aceptado')
        run=self.case/'analisis_etabs'/result['corrida_id']
        for name in ('aceptacion_analisis.json','solicitud.json','respuesta.json','entrada.edb','analizado.edb'):
            with self.subTest(name=name):
                path=run/name;raw=path.read_bytes();path.write_bytes(raw+b'alterado')
                current=self.service.consultar(self.caso,prepared['id'])
                self.assertFalse(current['vigente'] or current['calculo_verificado'])
                path.write_bytes(raw)

    def test_tipos_malformados_de_recibo_y_salida_no_rompen_consulta(self):
        prepared=self.prepare();self.execute(prepared);result=self.finish(prepared)
        self.assertEqual(result['estado'],'aceptado')
        record,_=self.service._leer(self.caso,prepared['id'])
        work=self.case/'trabajos_analisis'/prepared['id'];receipt_path=work/'aceptacion_web.json'
        original_receipt=receipt_path.read_bytes();receipt=json.loads(original_receipt)
        run=self.case/'analisis_etabs'/result['corrida_id']
        malformed=copy.deepcopy(receipt);malformed['archivos']=list(malformed['archivos'])
        raw=json.dumps(malformed).encode();receipt_path.write_bytes(raw)
        self.service._estado(record,'aceptado',huella_aceptacion=hashlib.sha256(raw).hexdigest())
        self.assertFalse(self.service.consultar(self.caso,prepared['id'])['vigente'])
        for name,value in (('solicitud.json',[]),('respuesta.json',[]),('aceptacion_analisis.json',[]),
                           ('respuesta.json',{'datos':list(receipt['archivos'])})):
            with self.subTest(name=name,value=value):
                path=run/name;before=path.read_bytes();path.write_text(json.dumps(value),encoding='utf-8')
                changed=copy.deepcopy(receipt);changed['archivos'][name]=hashlib.sha256(path.read_bytes()).hexdigest()
                raw=json.dumps(changed).encode();receipt_path.write_bytes(raw)
                self.service._estado(record,'aceptado',huella_aceptacion=hashlib.sha256(raw).hexdigest())
                self.assertFalse(self.service.consultar(self.caso,prepared['id'])['vigente'])
                path.write_bytes(before)
        receipt_path.write_bytes(original_receipt);self.service._estado(record,'aceptado')
        self.assertTrue(self.service.consultar(self.caso,prepared['id'])['vigente'])

    def test_aprobacion_controles_lista_se_rechaza_sin_attributeerror(self):
        prepared=self.prepare();path=self.approval/'aprobacion.json';approval=json.loads(path.read_bytes())
        approval['controles']=list(approval['controles']);path.write_text(json.dumps(approval),encoding='utf-8')
        with patch('subprocess.Popen',side_effect=AssertionError('No lanzar con aprobación inválida')):
            with self.assertRaises(ErrorAnalisis):self.execute(prepared)
        self.assertEqual(self.service.consultar(self.caso,prepared['id'])['estado'],'fallido_sin_lanzar')

    def test_huerfano_conserva_reserva_global(self):
        prepared=self.prepare();record,_=self.service._leer(self.caso,prepared['id'])
        self.service._estado(record,'en_ejecucion')
        with patch('subprocess.Popen',side_effect=AssertionError('No reanudar')):
            current=ServicioAnalisis(self.app,self.factory).consultar(self.caso,prepared['id'])
        self.assertEqual(current['estado'],'incierto');self.assertTrue(self.app.ejecucion.pendiente.exists())

    def test_exclusion_con_construccion_en_otro_proceso(self):
        # Preparar construcción en el mismo caso sin abrir motor.
        config=copy.deepcopy(self.fixture.config);config['revision']={'estado':'borrador','aprobacion':None}
        source=self.fixture.base.escribir(config,'config-web.json')
        imported=configs.importar(self.app.raiz,self.caso,source)
        approved=configs.aprobar(self.app.raiz,self.caso,imported['id'],huella_esperada=me.huella_configuracion(config),
            revisor='Prueba sintética',fecha='2026-10-17',motivo='Exclusión',alcance='Solo software')
        (self.case/'plantilla.edb').write_bytes(self.fixture.base.copia.read_bytes())
        opts={k:v for k,v in self.fixture.plan['opciones'].items() if k!='destino_guardado'}
        build=self.app.ejecucion.preparar({'caso':self.caso,'configuracion_version':approved['id'],
            'plantilla_relativa':'plantilla.edb','expediente_sha256':self.body['expediente_sha256'],
            'clave_solicitud':'b'*32,'opciones':opts})
        execute={'caso':self.caso,'trabajo':build['id'],'huella_preparacion':build['huella_preparacion'],
                 'expediente_sha256':build['expediente_sha256'],'confirmacion_explicita':True}
        prepared=self.prepare();entered,release=threading.Event(),threading.Event();original=self.service._worker
        def stop(*args):entered.set();release.wait(10);original(*args)
        self.assertEqual(self.service.lease,self.app.ejecucion.lease)
        self.assertEqual(self.service.motor_lock,self.app.ejecucion.motor_lock)
        self.assertEqual(self.service.pendiente,self.app.ejecucion.pendiente)
        program="import json,sys;from pathlib import Path;from draft2model.revision_visual import RevisionLocal;from draft2model.revision_ejecucion import ErrorEjecucion\ntry: RevisionLocal(Path(sys.argv[1])).ejecucion.ejecutar(json.loads(sys.argv[2]))\nexcept ErrorEjecucion as e:\n print(e.codigo);sys.exit(5 if e.codigo=='otra_ejecucion_activa' else 6)"
        with patch.object(self.service,'_worker',side_effect=stop):
            self.execute(prepared);self.assertTrue(entered.wait(5))
            try:
                result=subprocess.run([sys.executable,'-c',program,str(self.app.raiz),json.dumps(execute)],capture_output=True,timeout=10)
                self.assertEqual(result.returncode,5,result.stdout+result.stderr)
                self.assertEqual(self.app.ejecucion.consultar(self.caso,build['id'])['estado'],'preparado')
            finally:release.set()
            self.assertEqual(self.finish(prepared)['estado'],'aceptado')

    @unittest.skipUnless(sys.platform=='win32','Preflight Windows')
    def test_preflight_largo_antes_de_motor(self):
        with patch('subprocess.Popen',side_effect=AssertionError('No lanzar')):
            with self.assertRaises(ErrorAnalisis):
                ServicioAnalisis._rutas_analisis(Path('D:/')/('a'*230))


if __name__=='__main__':unittest.main()
