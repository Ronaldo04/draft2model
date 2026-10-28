"""Servicio web con LectorAnalisis real y transporte Python exclusivamente sintético."""
import json
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch
from uuid import uuid4

from draft2model import adaptador_etabs as ad
from draft2model.lectura_analisis import LectorAnalisis
from draft2model.revision_lecturas import ServicioLecturas, ErrorLecturas
from draft2model.revision_ejecucion import _bytes, _sha
from tests import test_lectura_analisis as fixtures


class LecturasWebTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.LecturaAnalisisTests(); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.app = self.fixture.app; self.caso = self.fixture.fixture.caso
        self.factory = lambda work, lock: LectorAnalisis(ad.ConfiguracionPuente.doble(
            work,self.fixture.command,lock,entorno=self.fixture.environment))
        self.service = ServicioLecturas(self.app,self.factory)
        self.body = {'caso':self.caso,'analisis':self.fixture.run.name,
            'expediente_sha256':self.app.expediente(self.caso)[2],
            'clave_solicitud':uuid4().hex,'tablas':['Story Drifts'],'casos':['EST']}

    def prepare(self, **changes):
        return self.service.preparar({**self.body,**changes})

    def execute(self, prepared, **changes):
        return self.service.ejecutar({'caso':self.caso,'trabajo':prepared['id'],
            'huella_preparacion':prepared['huella_preparacion'],
            'expediente_sha256':prepared['expediente_sha256'],'confirmacion_explicita':True,**changes})

    def finish(self, prepared):
        self.service._threads[prepared['id']].join(15)
        self.assertFalse(self.service._threads[prepared['id']].is_alive())
        return self.service.consultar(self.caso,prepared['id'])

    def accepted(self):
        prepared = self.prepare(); self.execute(prepared)
        result = self.finish(prepared)
        if result['estado'] != 'aceptado':
            error = self.service._carpeta(self.caso,prepared['id'])/'error_worker.json'
            self.fail(error.read_text() if error.exists() else str(result))
        return result

    def test_preparacion_sin_proceso_replay_conflicto_y_seleccion(self):
        with patch('subprocess.Popen',side_effect=AssertionError('Preparar no abre motor')):
            prepared = self.prepare(); replay = self.prepare()
            self.assertEqual(prepared,replay)
            for changes in ({'tablas':['Otra']},{'casos':['AJENO']},{'analisis':'../x'}, {'casos':[]}, {'extra':1}):
                with self.subTest(changes=changes),self.assertRaises(ErrorLecturas): self.prepare(**changes)
        self.assertEqual(prepared['estado'],'preparado')
        self.assertIsNone(prepared['lectura_id']); self.assertIsNone(prepared['datos_tablas'])

    def test_confirmacion_aceptacion_bytes_y_reinicio(self):
        prepared = self.prepare()
        with self.assertRaisesRegex(ErrorLecturas,'confirmacion_requerida'):
            self.execute(prepared,confirmacion_explicita=1)
        self.execute(prepared); result = self.finish(prepared)
        self.assertEqual(result['estado'],'aceptado'); self.assertTrue(result['lectura_verificada'])
        self.assertEqual(result['datos_tablas']['estado_casos'],{'EST':4})
        self.assertFalse(result['analisis_ejecutado']); self.assertFalse(result['aprueba_resultados'])
        self.assertEqual(set(result['datos_tablas']),{'unidades','version_etabs','casos','estado_casos','tablas'})
        self.assertNotIn('id_proceso',json.dumps(result)); self.assertNotIn(str(self.app.raiz),json.dumps(result))
        raw = self.service.respuesta_bytes(self.caso,result['id'],expediente_sha256=result['expediente_sha256'])
        self.assertEqual(_sha(raw),result['sha256_respuesta'])
        self.assertEqual(json.loads(raw)['datos']['tablas'],result['datos_tablas']['tablas'])
        restarted = ServicioLecturas(self.app,self.factory)
        self.assertEqual(restarted.consultar(self.caso,result['id']),result)
        self.assertEqual(self.execute(prepared),result)
        self.assertEqual(restarted.listar(self.caso)['trabajos'],[result])

    def test_fuentes_y_snapshots_alterados_no_lanzan(self):
        paths = [self.fixture.run/'analizado.edb',self.fixture.fixture.model/'modelo.edb',
            self.fixture.fixture.approval/'aprobacion.json',self.fixture.fixture.fixture.base.original]
        prepared = self.prepare()
        paths += [self.service._carpeta(self.caso,prepared['id'])/'evidencia_analisis.json']
        for index,path in enumerate(paths):
            with self.subTest(path=path.name):
                job = prepared if index == len(paths)-1 else self.prepare(clave_solicitud=uuid4().hex)
                raw = path.read_bytes(); path.write_bytes(raw+b'alterado')
                try:
                    with patch('subprocess.Popen',side_effect=AssertionError('No motor')):
                        with self.assertRaisesRegex(ErrorLecturas,'entradas_no_vigentes'): self.execute(job)
                    self.assertEqual(self.service.consultar(self.caso,job['id'])['estado'],'fallido_sin_lanzar')
                    self.assertFalse(self.app.ejecucion.pendiente.exists())
                finally:path.write_bytes(raw)

    def test_tampering_recibo_request_respuesta_snapshot_y_tipos(self):
        result = self.accepted(); folder = self.fixture.work/result['lectura_id']
        work = self.service._carpeta(self.caso,result['id'])
        for name,path in [('request',folder/'solicitud.json'),('response',folder/'respuesta.json'),
                ('native_receipt',folder/'aceptacion_lectura.json'),('proof',folder/'evidencia_analisis.json'),
                ('web_receipt',work/'aceptacion_web.json')]:
            original = path.read_bytes()
            for value in ([], {'datos':[]}, {'archivos':[]}):
                with self.subTest(name=name,value=value):
                    path.write_bytes(_bytes(value))
                    current = self.service.consultar(self.caso,result['id'])
                    self.assertFalse(current['vigente']); self.assertFalse(current['lectura_verificada'])
                    self.assertIsNone(current['datos_tablas'])
                    with self.assertRaises(ErrorLecturas):
                        self.service.respuesta_bytes(self.caso,result['id'],expediente_sha256=result['expediente_sha256'])
                    path.write_bytes(original)

    def test_semantica_cierre_casos_modo_falso_exito_no_aceptada(self):
        # Cada fallo conserva reserva global; el resto usa casos aislados de prueba.
        for flag in ('NO_CERRADA','ESTADO_INCOMPLETO','FALSO_EXITO','MODO_AJENO','FILA_MALFORMADA'):
            with self.subTest(flag=flag):
                self.fixture.environment.clear(); self.fixture.environment[flag]='1'
                prepared = self.prepare(clave_solicitud=uuid4().hex); self.execute(prepared)
                result = self.finish(prepared)
                self.assertEqual(result['estado'],'incierto'); self.assertFalse(result['lectura_verificada'])
                self.assertTrue(self.app.ejecucion.pendiente.exists())
                with self.assertRaises(ErrorLecturas):
                    self.service.respuesta_bytes(self.caso,result['id'],expediente_sha256=result['expediente_sha256'])
                # Recuperación externa simulada únicamente para el siguiente escenario sintético.
                self.app.ejecucion.pendiente.unlink()
                marker = self.fixture.reader.estado_incierto
                if marker.exists():marker.unlink()

    def test_consulta_reverifica_semantica_aun_con_recibos_rehashados(self):
        result = self.accepted(); folder = self.fixture.work/result['lectura_id']
        work = self.service._carpeta(self.caso,result['id'])
        response = json.loads((folder/'respuesta.json').read_bytes())
        response['datos']['instancia_cerrada'] = False
        (folder/'respuesta.json').write_bytes(_bytes(response))
        receipt = json.loads((folder/'aceptacion_lectura.json').read_bytes())
        receipt['sha256_respuesta'] = _sha((folder/'respuesta.json').read_bytes())
        (folder/'aceptacion_lectura.json').write_bytes(_bytes(receipt))
        web = json.loads((work/'aceptacion_web.json').read_bytes())
        web['archivos'] = {k:_sha((folder/k).read_bytes()) for k in web['archivos']}
        (work/'aceptacion_web.json').write_bytes(_bytes(web))
        record,state = self.service._leer(self.caso,result['id'])
        self.service._estado(record,state,huella_aceptacion=_sha(_bytes(web)),sha256_respuesta=receipt['sha256_respuesta'])
        self.assertFalse(self.service.consultar(self.caso,result['id'])['vigente'])

    def test_fuente_cambia_durante_lectura_no_se_acepta(self):
        self.fixture.environment['ALTERAR'] = str(self.fixture.run/'analizado.edb')
        prepared = self.prepare(); self.execute(prepared)
        result = self.finish(prepared)
        self.assertEqual(result['estado'],'incierto'); self.assertFalse(result['vigente'])

    def test_huerfano_reinicio_conserva_marcador_sin_reintento(self):
        prepared = self.prepare(); record,_ = self.service._leer(self.caso,prepared['id'])
        self.service._estado(record,'en_ejecucion')
        restarted = ServicioLecturas(self.app,self.factory)
        with patch('subprocess.Popen',side_effect=AssertionError('Sin reintento')):
            current = restarted.preparar(self.body)
        self.assertEqual(current['estado'],'incierto'); self.assertTrue(current['requiere_recuperacion'])
        self.assertTrue(self.app.ejecucion.pendiente.exists())

    def test_exclusion_entre_servicios_y_procesos_y_doble_ejecutar(self):
        analysis = self.fixture.fixture.prepare(clave_solicitud=uuid4().hex)
        execute = {'caso':self.caso,'trabajo':analysis['id'],'huella_preparacion':analysis['huella_preparacion'],
            'expediente_sha256':analysis['expediente_sha256'],'confirmacion_explicita':True}
        entered,release = threading.Event(),threading.Event(); original = self.service._worker
        def stop(*args):entered.set();release.wait(10);original(*args)
        program = "import json,sys;from pathlib import Path;from draft2model.revision_visual import RevisionLocal;from draft2model.revision_analisis import ServicioAnalisis;from draft2model.revision_ejecucion import ErrorEjecucion\ntry: ServicioAnalisis(RevisionLocal(Path(sys.argv[1]))).ejecutar(json.loads(sys.argv[2]))\nexcept ErrorEjecucion as e:\n print(e.codigo);sys.exit(5 if e.codigo=='otra_ejecucion_activa' else 6)"
        prepared = self.prepare()
        self.assertEqual(self.service.lease,self.app.ejecucion.lease)
        self.assertEqual(self.service.motor_lock,self.app.ejecucion.motor_lock)
        self.assertEqual(self.service.pendiente,self.app.ejecucion.pendiente)
        with patch.object(self.service,'_worker',side_effect=stop):
            self.execute(prepared); self.assertTrue(entered.wait(5))
            try:
                self.assertEqual(self.execute(prepared)['estado'],'en_ejecucion')
                result = subprocess.run([sys.executable,'-c',program,str(self.app.raiz),json.dumps(execute)],
                    capture_output=True,timeout=10)
                self.assertEqual(result.returncode,5,result.stdout+result.stderr)
            finally:release.set()
            self.assertEqual(self.finish(prepared)['estado'],'aceptado')

    def test_ids_caso_fingerprint_ajenos_y_respuesta_pendiente(self):
        prepared = self.prepare()
        for case,ident,fp in [(self.caso,'../x',prepared['expediente_sha256']),
                ('otro-caso',prepared['id'],prepared['expediente_sha256']),
                (self.caso,prepared['id'],'0'*64), (self.caso,prepared['id'],prepared['expediente_sha256'])]:
            with self.subTest(case=case,ident=ident,fp=fp),self.assertRaises(ErrorLecturas):
                self.service.respuesta_bytes(case,ident,expediente_sha256=fp)

    def test_bytes_relectura_final_y_consultas_aceptadas_sin_escritura(self):
        result = self.accepted()
        def files():
            return {str(p):p.read_bytes() for p in self.fixture.case.rglob('*') if p.is_file()}
        before = files()
        self.service.consultar(self.caso,result['id']); self.service.listar(self.caso)
        self.service.respuesta_bytes(self.caso,result['id'],expediente_sha256=result['expediente_sha256'])
        self.assertEqual(files(),before)
        original = self.service._revalidar; calls = []
        response = self.fixture.work/result['lectura_id']/'respuesta.json'
        def change(record):
            proof = original(record); calls.append(1)
            if len(calls) == 2:response.write_bytes(b'{}')
            return proof
        with patch.object(self.service,'_revalidar',side_effect=change):
            with self.assertRaises(ErrorLecturas):
                self.service.respuesta_bytes(self.caso,result['id'],expediente_sha256=result['expediente_sha256'])

    def test_timeout_mantiene_incertidumbre_sin_reintentar(self):
        self.fixture.environment['ESPERAR'] = '1'
        self.service = ServicioLecturas(self.app,lambda work,lock: LectorAnalisis(ad.ConfiguracionPuente.doble(
            work,self.fixture.command,lock,timeout_s=0.3,entorno=self.fixture.environment)))
        prepared = self.prepare(); self.execute(prepared)
        result = self.finish(prepared)
        self.assertEqual(result['estado'],'incierto'); self.assertTrue(self.app.ejecucion.pendiente.exists())
        with patch('subprocess.Popen',side_effect=AssertionError('No repetir timeout')):
            self.assertEqual(self.execute(prepared)['estado'],'incierto')


if __name__ == '__main__':unittest.main()
