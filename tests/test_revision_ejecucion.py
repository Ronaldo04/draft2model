"""Construcción web con transporte Python sintético; ningún motor ETABS."""
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
from draft2model import ejecutor_etabs as ej
from draft2model import gestion_configuracion as configs
from draft2model import modelo_estructural as me
from draft2model.ejecucion_modelo import EjecutorVerificado
from draft2model.revision_ejecucion import ErrorEjecucion, ServicioEjecucion
from draft2model.revision_visual import RevisionLocal
from tests.test_operaciones_etabs import PlanBase


TRANSPORTE = r'''
import hashlib,json,os,sys
from pathlib import Path
a=sys.argv[1:];s=json.loads(Path(a[a.index('-Solicitud')+1]).read_bytes());r=Path(a[a.index('-Respuesta')+1])
out={'contrato':'draft2model.etabs_respuesta','version_contrato':'0.1.0','id_solicitud':s['id'],'operacion':s['operacion'],'modo_ejecucion':'doble','estado':'ok','avisos':[]}
if s['operacion']=='abrir_copia_plantilla':
 p=s['parametros'];assert p['instancia']=='nueva' and not p.get('id_proceso')
 out['datos']={'id_proceso':None if os.environ.get('SIN_PID') else 1234,'instancia':'nueva','modelo_abierto':p['copia']}
else:
 ops=s['operaciones'];assert s['id_proceso']==1234
 names={v['registra']:v['debe_ser'] for op in ops for v in op.get('salidas',[])}
 with (r.parent/'traza.jsonl').open('w',encoding='utf-8') as f:
  for op in ops:
   for event in ('inicio','fin'):
    row={'orden':op['orden'],'metodo':op['metodo'],'evento':event,'lectura':op['fase']=='verificacion'}
    if event=='fin':row.update(retorno=0,salidas={v['registra']:v['debe_ser'] for v in op.get('salidas',[])})
    f.write(json.dumps(row)+'\n')
 if os.environ.get('FALLO_PARCIAL'):sys.exit(1)
 target=Path(s['destino']);target.write_bytes(b'MODELO SINTETICO NO ETABS')
 digest='0'*64 if os.environ.get('FALSO_EXITO') else hashlib.sha256(target.read_bytes()).hexdigest()
 out['datos']={'guardado':{'ruta':str(target),'sha256':digest},'huella_plan':s['huella_plan'],'analisis_ejecutado':False,'aprueba_modelo':False}
 out['progreso']={'operaciones_ejecutadas':len(ops),'mapeo_nombres':names,'mutaciones_realizadas':True}
r.write_text(json.dumps(out),encoding='utf-8')
'''


class ConstruccionWebTests(unittest.TestCase):
    def setUp(self):
        self.fixture = PlanBase(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.app = RevisionLocal(self.fixture.raiz)
        self.caso = self.fixture.data['caso']
        self.case = self.app.raiz/self.caso
        self.template = self.case/'plantilla.edb'; self.template.write_bytes(b'PLANTILLA SINTETICA')
        data = copy.deepcopy(self.fixture.data)
        data['plantilla']['sha256'] = hashlib.sha256(self.template.read_bytes()).hexdigest()
        source = self.fixture.escribir(data, 'config-importar.json')
        imported = configs.importar(self.app.raiz,self.caso,source)
        approved = configs.aprobar(self.app.raiz,self.caso,imported['id'],
            huella_esperada=me.huella_configuracion(data), revisor='Ensayo sintético',fecha='2026-10-17',
            motivo='Prueba de software',alcance='Fixture inventada; no ingeniería')
        self.config = approved
        script = self.fixture.trabajo/'transporte_web.py'; script.write_text(TRANSPORTE,encoding='utf-8')
        self.command = (sys.executable,str(script))
        self.env = {}
        self.factories = {
            'fabrica_adaptador': lambda work,lock:ad.AdaptadorEtabs(ad.ConfiguracionPuente.doble(work,self.command,lock,entorno=self.env)),
            'fabrica_ejecutor': lambda work,lock:EjecutorVerificado(ej.configuracion_doble(work,self.command,lock,entorno=self.env)),
        }
        self.service = ServicioEjecucion(self.app, **self.factories)
        self.body = {'caso':self.caso,'configuracion_version':approved['id'],
                     'plantilla_relativa':'plantilla.edb','expediente_sha256':self.app.expediente(self.caso)[2],
                     'clave_solicitud':'a'*32,'opciones':{'tipo_shell_muro':'ShellThin','gravedad_programa_m_s2':9.80665}}

    def prepare(self, **changes):
        return self.service.preparar({**self.body,**changes})

    def execute(self, prepared, **changes):
        return self.service.ejecutar({'caso':self.caso,'trabajo':prepared['id'],
            'huella_preparacion':prepared['huella_preparacion'],'expediente_sha256':prepared['expediente_sha256'],
            'confirmacion_explicita':True,**changes})

    def finish(self, prepared):
        self.service._threads[prepared['id']].join(20)
        self.assertFalse(self.service._threads[prepared['id']].is_alive())
        return self.service.consultar(self.caso,prepared['id'])

    def test_preparar_sin_procesos_replay_y_clave_con_otro_payload(self):
        with patch('subprocess.Popen',side_effect=AssertionError('No se lanza en preparación')):
            first=self.prepare(); again=self.prepare()
        self.assertEqual(first,again)
        self.assertEqual(first['estado'],'preparado')
        self.assertEqual(first['configuracion_version'],self.config['id'])
        with self.assertRaisesRegex(ErrorEjecucion,'clave_reutilizada'):
            self.prepare(opciones={**self.body['opciones'],'tipo_shell_muro':'ShellThick'})
        self.assertEqual(len(self.service.listar(self.caso)['trabajos']),1)

    def test_construir_aceptacion_fuerte_modelo_pendiente_y_reinicio(self):
        prepared=self.prepare()
        with self.assertRaisesRegex(ErrorEjecucion,'confirmacion_requerida'):
            self.execute(prepared,confirmacion_explicita=False)
        self.assertEqual(self.execute(prepared)['estado'],'en_ejecucion')
        final=self.finish(prepared)
        self.assertEqual(final['estado'],'aceptado',final)
        self.assertTrue(final['vigente']);self.assertIsNotNone(final['modelo_id'])
        self.assertFalse(final['analisis_ejecutado'] or final['aprueba_modelo'] or final['aprueba_resultados'])
        self.assertEqual(final['modo_ejecucion'],'doble')
        self.assertFalse(self.service.pendiente.exists())
        from draft2model import revision_modelo
        model=revision_modelo.consultar(self.app.raiz,self.caso,final['modelo_id'])
        self.assertEqual(model['estado'],'pendiente');self.assertIsNone(model['aprobacion'])
        restarted=ServicioEjecucion(RevisionLocal(self.app.raiz),**self.factories)
        self.assertEqual(restarted.consultar(self.caso,prepared['id']),final)
        self.assertEqual(self.execute(prepared)['estado'],'aceptado')
        public=json.dumps(final)
        self.assertNotIn(str(self.app.raiz),public);self.assertNotIn('id_proceso',public)

    def test_inputs_alterados_no_lanzan(self):
        for target in (self.fixture.original,self.template,self.config['ruta']/'configuracion.json'):
            with self.subTest(target=target.name):
                original=target.read_bytes()
                prepared=self.prepare(clave_solicitud=hashlib.md5(str(target).encode()).hexdigest())
                target.write_bytes(original+b'alterado')
                with patch('subprocess.Popen',side_effect=AssertionError('No debe lanzar')):
                    with self.assertRaises(ErrorEjecucion):self.execute(prepared)
                self.assertEqual(self.service.consultar(self.caso,prepared['id'])['estado'],'fallido_sin_lanzar')
                self.assertFalse(self.service.pendiente.exists())
                target.write_bytes(original)

    def test_falso_exito_y_fallo_parcial_no_aceptados(self):
        prepared=self.prepare();self.env['FALSO_EXITO']='1'
        self.execute(prepared);final=self.finish(prepared)
        self.assertEqual(final['estado'],'incierto');self.assertIsNone(final['modelo_id'])
        self.assertTrue(self.service.pendiente.exists())
        with self.assertRaisesRegex(ErrorEjecucion,'motor_incierto'):
            self.execute(self.prepare(clave_solicitud='b'*32))
        self.assertEqual(ServicioEjecucion(self.app,**self.factories).consultar(self.caso,prepared['id'])['estado'],'incierto')

    def test_fallo_parcial_persiste_traza(self):
        self.env['FALLO_PARCIAL']='1';prepared=self.prepare()
        self.execute(prepared);final=self.finish(prepared)
        self.assertEqual(final['estado'],'incierto')
        work=self.case/'trabajos_construccion'/prepared['id']
        ref=json.loads((work/'construccion_ref.json').read_bytes())
        corrida=self.case/ref['grupo']/ref['corrida_id']
        self.assertTrue((corrida/'traza.jsonl').exists())
        self.assertFalse((corrida/'aceptacion_integracion.json').exists())

    def test_dos_servicios_y_exclusion_entre_procesos(self):
        prepared=self.prepare(); entered,release=threading.Event(),threading.Event()
        original=self.service._worker
        def stopped(*args):
            entered.set();release.wait(10);original(*args)
        other=ServicioEjecucion(RevisionLocal(self.app.raiz),**self.factories)
        with patch.object(self.service,'_worker',side_effect=stopped):
            self.execute(prepared)
            self.assertTrue(entered.wait(5))
            self.assertEqual(other.ejecutar({'caso':self.caso,'trabajo':prepared['id'],
                'huella_preparacion':prepared['huella_preparacion'],'expediente_sha256':prepared['expediente_sha256'],
                'confirmacion_explicita':True})['estado'],'en_ejecucion')
            second=self.prepare(clave_solicitud='b'*32)
            with self.assertRaisesRegex(ErrorEjecucion,'otra_ejecucion_activa'):
                self.execute(second)
            probe="import sys;from pathlib import Path;from draft2model.adaptador_etabs import BloqueoExclusivo,ErrorBloqueo\ntry: BloqueoExclusivo(Path(sys.argv[1])).adquirir()\nexcept ErrorBloqueo: sys.exit(5)"
            try:
                out=subprocess.run([sys.executable,'-c',probe,str(self.service.lease)],capture_output=True,timeout=10)
                self.assertEqual(out.returncode,5,out.stderr)
            finally:release.set()
            self.assertEqual(self.finish(prepared)['estado'],'aceptado')

    def test_reinicio_huerfano_no_reintenta_y_pid_ausente(self):
        prepared=self.prepare()
        record,_=self.service._leer(self.caso,prepared['id'])
        self.service._estado(record,'en_ejecucion')
        other=ServicioEjecucion(self.app,**self.factories)
        with patch('subprocess.Popen',side_effect=AssertionError('Reinicio no lanza')):
            final=other.consultar(self.caso,prepared['id'])
        self.assertEqual(final['estado'],'incierto');self.assertTrue(other.pendiente.exists())
        self.assertTrue(final['requiere_recuperacion'])

    def test_apertura_sin_pid_no_construye(self):
        self.env['SIN_PID']='1';prepared=self.prepare()
        self.execute(prepared);final=self.finish(prepared)
        self.assertEqual(final['estado'],'incierto')
        self.assertFalse((self.case/'trabajos_construccion'/prepared['id']/'construccion_ref.json').exists())

    def test_rutas_y_opciones_arbitrarias_rechazadas_sin_lanzar(self):
        for changes in ({'plantilla_relativa':'../plantilla.edb'},
                        {'plantilla_relativa':str(self.template)},
                        {'configuracion_version':self.fixture.data['id']},
                        {'opciones':{**self.body['opciones'],'destino_guardado':'C:/otro.edb'}},
                        {'id_proceso':1234}):
            with self.subTest(changes=changes),self.assertRaises(ErrorEjecucion):
                self.prepare(**changes)

    @unittest.skipUnless(sys.platform == 'win32','Preflight nativo de Windows')
    def test_ruta_larga_se_rechaza_en_preparacion_sin_motor(self):
        name='p'*140+'.edb'
        (self.case/name).write_bytes(self.template.read_bytes())
        with patch('subprocess.Popen',side_effect=AssertionError('Preflight antes del motor')):
            with self.assertRaisesRegex(ErrorEjecucion,'ruta_motor_demasiado_larga'):
                self.prepare(plantilla_relativa=name)
        self.assertFalse(self.service.pendiente.exists())


if __name__=='__main__':unittest.main()
