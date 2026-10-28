import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest import mock
import unittest
from tests import test_ejecutor_etabs as fixture
from draft2model import ejecutor_etabs as ej
from draft2model import adaptador_etabs as ad
from draft2model.ejecucion_modelo import EjecutorVerificado

TRANSPORTE=r'''
import sys,json,hashlib,os
from pathlib import Path
a=sys.argv[1:];s=json.loads(Path(a[a.index('-Solicitud')+1]).read_bytes());r=Path(a[a.index('-Respuesta')+1]);ops=s['operaciones']
if os.environ.get('INTERRUMPIR'):sys.exit(1)
names={v['registra']:v['debe_ser'] for op in ops for v in op.get('salidas',[])}
with (r.parent/'traza.jsonl').open('w',encoding='utf-8') as f:
 for op in ops:
  for event in ('inicio','fin'):f.write(json.dumps({'orden':op['orden'],'metodo':op['metodo'],'evento':event,'lectura':op['fase']=='verificacion'})+'\n')
target=Path(s['destino']);target.write_bytes(b'MODELO SINTETICO, NO ES ETABS')
if os.environ.get('ALTERAR_ORIGINAL'):Path(os.environ['ALTERAR_ORIGINAL']).write_bytes(b'original cambiado')
digest='0'*64 if os.environ.get('FALSO_EXITO') else hashlib.sha256(target.read_bytes()).hexdigest()
out={'contrato':'draft2model.etabs_respuesta','version_contrato':'0.1.0','id_solicitud':s['id'],'operacion':'ejecutar_plan','modo_ejecucion':'doble','estado':'ok','avisos':[],
 'datos':{'guardado':{'ruta':str(target),'sha256':digest},'huella_plan':s['huella_plan'],'analisis_ejecutado':False,'aprueba_modelo':False},
 'progreso':{'operaciones_ejecutadas':len(ops),'mapeo_nombres':names,'mutaciones_realizadas':True}}
r.write_text(json.dumps(out),encoding='utf-8')
'''


class EjecucionIntegradaTests(unittest.TestCase):
    def test_salida_abrupta_sin_traza_conserva_bloqueo_persistente(self):
        self.config.entorno={'INTERRUMPIR':'1'};executor=EjecutorVerificado(self.config)
        with self.assertRaises(ad.ErrorPuente) as ctx:executor.ejecutar(self.preparar(executor))
        self.assertTrue(ctx.exception.incierto);self.assertTrue(executor.estado_incierto.exists())
        self.assertFalse((ctx.exception.corrida/'aceptacion_integracion.json').exists())
    def setUp(self):
        self.base=fixture.EjecutorBase();self.base.setUp();self.addCleanup(self.base.doCleanups)
        script=self.base.trabajo/'transporte.py';script.write_text(TRANSPORTE,encoding='utf-8')
        self.config=ej.configuracion_doble(self.base.corridas,(sys.executable,str(script)))

    def preparar(self,executor):return self.base.preparar(executor)

    def test_original_cambiado_entre_preparar_y_ejecutar_no_lanza(self):
        executor=EjecutorVerificado(self.config);prepared=self.preparar(executor)
        self.base.original.write_bytes(b'cambio')
        with mock.patch('subprocess.Popen',side_effect=AssertionError('No debe lanzar')):
            with self.assertRaises(ad.ErrorEvidenciaEtabs):executor.ejecutar(prepared)
        self.assertFalse(Path(self.base.destino).exists())

    def test_exito_falso_registra_incertidumbre(self):
        self.config.entorno={'FALSO_EXITO':'1'};executor=EjecutorVerificado(self.config)
        with self.assertRaises(ad.ErrorEvidenciaEtabs) as ctx:executor.ejecutar(self.preparar(executor))
        self.assertTrue(ctx.exception.incierto);self.assertTrue(executor.estado_incierto.exists())
        self.assertTrue((ctx.exception.corrida/'revision_integracion_fallida.json').exists())

    def test_evidencia_cambiada_durante_proceso_no_se_acepta(self):
        self.config.entorno={'ALTERAR_ORIGINAL':str(self.base.original)};executor=EjecutorVerificado(self.config)
        with self.assertRaises(ad.ErrorEvidenciaEtabs) as ctx:executor.ejecutar(self.preparar(executor))
        self.assertTrue(ctx.exception.incierto);self.assertTrue(executor.estado_incierto.exists())

    def test_validacion_final_conserva_bloqueo(self):
        executor=EjecutorVerificado(self.config);prepared=self.preparar(executor)
        entered,release=threading.Event(),threading.Event();original=executor._verificar
        def verify(*args):
            entered.set();self.assertTrue(release.wait(10));return original(*args)
        with mock.patch.object(executor,'_verificar',side_effect=verify),ThreadPoolExecutor(1) as pool:
            future=pool.submit(executor.ejecutar,prepared)
            self.assertTrue(entered.wait(10))
            code="import sys;from pathlib import Path;from draft2model.adaptador_etabs import BloqueoExclusivo,ErrorBloqueo\ntry: BloqueoExclusivo(Path(sys.argv[1])).adquirir()\nexcept ErrorBloqueo: sys.exit(5)"
            try:
                probe=subprocess.run([sys.executable,'-c',code,str(executor.config.bloqueo)],capture_output=True,timeout=10)
                self.assertEqual(probe.returncode,5,probe.stderr)
            finally:release.set()
            result=future.result(timeout=10)
        self.assertEqual(result.modo_ejecucion,'doble');self.assertFalse(executor.estado_incierto.exists())
        self.assertTrue(Path(result.extra['aceptacion_integracion']).is_file())
