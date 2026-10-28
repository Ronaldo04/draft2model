"""Revisión propia declarada con fixture portable: sin motor, red ni valores inventados."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from draft2model import evidencia_analisis as evidencia
from draft2model.revision_aprobacion_resultados import CONTROLES, ErrorRevisionResultados, ServicioRevisionResultados
from draft2model.revision_visual import RevisionLocal
from tests.fixture_etabs import extraer_evidencia

CASO='demo-integrada-sintetica';RESULTADO='72c06efb3bfe477bb1fe565809aeddec';ANALISIS='adf97fbc232141e8ae687872c0d71232'


def snapshot(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}


class RevisionResultadosTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.bundle=extraer_evidencia(Path(temp.name).resolve()/'f');self.app=RevisionLocal(self.bundle/'private')
        self.case=self.app.raiz/CASO;self.run=self.case/'analisis_etabs'/ANALISIS
        shutil.copytree(self.bundle/'analisis'/ANALISIS,self.run)
        self.result=self.case/'resultados_estructurales'/RESULTADO
        self.fp=self.app.expediente(CASO)[2];self.service=ServicioRevisionResultados(self.app)
        for target in ('subprocess.Popen','urllib.request.urlopen','socket.create_connection','draft2model.proveedor_openai._http'):
            guard=patch(target,side_effect=AssertionError('Sin red ni procesos'));guard.start();self.addCleanup(guard.stop)
        data=self.app.resultados.consultar_resultado(CASO,RESULTADO,expediente_sha256=self.fp)
        proof=evidencia.verificar_evidencia(self.app.raiz,CASO,RESULTADO,self.run)
        self.body={'caso':CASO,'resultado':RESULTADO,'analisis':ANALISIS,'expediente_sha256':self.fp,
            'huella_resultados':data['huella'],'huella_evidencia':evidencia.huella_evidencia(proof),
            'revisor_declarado':'Revisor declarado de prueba SINTÉTICA','fecha':'2026-10-18',
            'alcance':'Solo revisión de evidencia sintética de software y del resultado EST seleccionado.',
            'motivo':'Prueba del registro declarativo; no certificación ni revisión de ingeniería física.',
            'controles':{k:True for k in CONTROLES},'faltantes_criticos':[],
            'observaciones':['La omisión DY y las advertencias permanecen visibles; no se califican por IA.'],
            'confirmacion_explicita':True}

    def read(self,revision):return self.service.consultar(CASO,revision,expediente_sha256=self.fp)
    def listing(self):return self.service.listar(CASO,RESULTADO,expediente_sha256=self.fp)

    def assert_safe(self,value):
        text=json.dumps(value,ensure_ascii=False)
        for forbidden in (str(self.bundle),json.dumps(str(self.bundle))[1:-1],'archivo_motor','destino_guardado','id_proceso','"ruta"'):
            self.assertNotIn(forbidden,text)

    def test_fuentes_sin_escrituras_y_revision_propia_sin_mutar_paquete(self):
        before=snapshot(self.bundle)
        source=self.service.consultar_fuentes(CASO,RESULTADO,ANALISIS,expediente_sha256=self.fp)
        self.assertEqual(snapshot(self.bundle),before);self.assertEqual(source['huella_evidencia'],self.body['huella_evidencia'])
        self.assertEqual(source['controles_requeridos'],list(CONTROLES));self.assertEqual(source['revision_resultados'],'pendiente')
        native=snapshot(self.result);item=self.service.registrar(self.body)
        self.assertEqual(snapshot(self.result),native);self.assertEqual(item['revision_resultados'],'revisados_declarados')
        self.assertEqual(item['fuentes']['omisiones'],source['omisiones']);self.assertEqual(item['fuentes']['advertencias'],source['advertencias'])
        self.assertEqual(item['fuentes']['filas_omitidas'][0]['id'],'DY');self.assertIsNone(item['fuentes']['filas_omitidas'][0]['valor'])
        self.assertTrue(item['fuentes']['datos_sinteticos']);self.assertEqual(item['declaracion']['observaciones'],self.body['observaciones'])
        self.assertFalse(item['aprueba_resultados'] or item['aprueba_informe'] or item['aprueba_ingenieria'] or item['verificacion_profesional'])
        self.assertEqual(item['conformidad_normativa'],'no_evaluada');self.assertEqual(item['identidad_revisor'],'declarada_no_verificada')
        self.assertEqual(self.read(item['id']),item);self.assert_safe(item)
        projected=self.app.resultados.consultar_resultado(CASO,RESULTADO,expediente_sha256=self.fp)
        self.assertEqual(projected['revision_resultados'],'pendiente');self.assertFalse(projected['aprueba_resultados'])

    def test_varias_declaraciones_inmutables_y_reinicio_no_selecciona_ultima(self):
        first=self.service.registrar(self.body);folder=self.case/'revisiones_resultados'/first['id'];before=snapshot(folder)
        second=self.service.registrar({**self.body,'motivo':'Otra declaración propia de software sintético.'})
        self.assertNotEqual(first['id'],second['id']);self.assertEqual(snapshot(folder),before)
        service=ServicioRevisionResultados(self.app);before=snapshot(self.bundle)
        rows=service.listar(CASO,RESULTADO,expediente_sha256=self.fp)
        self.assertEqual(snapshot(self.bundle),before);self.assertFalse(rows['seleccion_automatica'])
        self.assertEqual({r['id'] for r in rows['versiones']},{first['id'],second['id']});self.assertTrue(all(r['vigente'] for r in rows['versiones']))
        self.assert_safe(rows)

    def test_confirmacion_controles_criticos_fecha_y_observaciones_exactos(self):
        missing=dict(self.body['controles']);missing.pop(CONTROLES[0])
        cases=[{'confirmacion_explicita':False},{'confirmacion_explicita':1},{'controles':missing},
            {'controles':{**self.body['controles'],CONTROLES[0]:False}},
            {'controles':{**self.body['controles'],CONTROLES[0]:1}},
            {'controles':{**self.body['controles'],'inferido_ia':True}},
            {'faltantes_criticos':['Falta crítica declarada por el revisor']},{'faltantes_criticos':None},
            {'observaciones':'No lista'},{'observaciones':['']},{'fecha':'2026-02-30'},
            {'revisor_declarado':''},{'alcance':' '},{'motivo':''},{'ruta':'C:/ajena'}]
        before=snapshot(self.bundle)
        for changes in cases:
            with self.subTest(changes=changes),self.assertRaises(ErrorRevisionResultados) as ctx:self.service.registrar({**self.body,**changes})
            self.assertNotIn(str(self.bundle),str(ctx.exception))
        body=dict(self.body);body.pop('faltantes_criticos')
        with self.assertRaises(ErrorRevisionResultados):self.service.registrar(body)
        self.assertEqual(snapshot(self.bundle),before)

    def test_ids_huellas_analisis_y_aislamiento_entre_casos(self):
        before=snapshot(self.bundle)
        for changes in ({'resultado':'../otro'},{'analisis':ANALISIS.upper()},{'analisis':[]},{'resultado':123},
                        {'analisis':'0'*32},{'huella_resultados':'0'*64},{'huella_evidencia':'0'*64},
                        {'expediente_sha256':'0'*64},{'caso':'../fuera'},{'caso':'otro-caso'}):
            with self.subTest(changes=changes),self.assertRaises(ErrorRevisionResultados):self.service.registrar({**self.body,**changes})
        self.assertEqual(snapshot(self.bundle),before)
        item=self.service.registrar(self.body)
        with self.assertRaises(ErrorRevisionResultados):self.service.consultar('otro-caso',item['id'],expediente_sha256=self.fp)
        for version in ('../fuera',{},None):
            with self.assertRaises(ErrorRevisionResultados):self.read(version)

    def test_fuentes_edb_modelo_respuesta_y_original_alterados_no_vigentes(self):
        item=self.service.registrar(self.body);original=next((self.case/'originales').iterdir())
        for path in (self.run/'analizado.EDB',self.run/'entrada.edb',self.run/'respuesta.json',
                     self.run/'aceptacion_analisis.json',self.result/'configuracion.json',
                     self.case/'modelos_construidos'/'225f8c4a9a0744fbb702a9f0b9affdc0'/'modelo.edb',original):
            with self.subTest(path=path.name):
                raw=path.read_bytes();path.write_bytes(raw+b'alterado')
                with self.assertRaises(ErrorRevisionResultados):self.read(item['id'])
                with self.assertRaises(ErrorRevisionResultados):self.service.registrar(self.body)
                rows=self.listing()['versiones'];self.assertFalse(rows[0]['vigente']);self.assertIsNone(rows[0]['resumen'])
                path.write_bytes(raw)
        self.assertTrue(self.read(item['id'])['vigente'])

    def test_edicion_bytes_paquete_y_registro_malformado_no_se_ocultan(self):
        item=self.service.registrar(self.body);path=self.result/'resultados.json';raw=path.read_bytes();path.write_bytes(raw+b'\n')
        with self.assertRaises(ErrorRevisionResultados):self.read(item['id'])
        path.write_bytes(raw);target=self.case/'revisiones_resultados'/item['id'];record_path=target/'revision.json';meta_path=target/'version.json'
        raw_record=record_path.read_bytes();raw_meta=meta_path.read_bytes()
        for change in ('lista','control','fuentes','fecha','otro_resultado'):
            record=json.loads(raw_record)
            if change=='lista':record['declaracion']=[]
            elif change=='control':record['declaracion']['controles'][CONTROLES[0]]=False
            elif change=='fuentes':record['fuentes']={'inventadas':True}
            elif change=='fecha':record['creado_utc']=None
            else:record['declaracion']['resultado']='f'*32
            bad=json.dumps(record).encode();record_path.write_bytes(bad);meta=json.loads(raw_meta);meta['sha256_revision']=hashlib.sha256(bad).hexdigest();meta_path.write_text(json.dumps(meta))
            with self.subTest(change=change),self.assertRaises(ErrorRevisionResultados):self.read(item['id'])
            self.assertFalse(self.listing()['versiones'][0]['vigente'])
            record_path.write_bytes(raw_record);meta_path.write_bytes(raw_meta)

    def test_cambio_durante_verificacion_no_publica_y_cambio_registro_se_detecta(self):
        original=next((self.case/'originales').iterdir());raw=original.read_bytes();native=evidencia.verificar_evidencia;changed=False
        def modify(*args,**kwargs):
            nonlocal changed
            value=native(*args,**kwargs)
            if not changed:changed=True;original.write_bytes(raw+b'alterado durante verificacion')
            return value
        with patch('draft2model.revision_aprobacion_resultados.evidencia.verificar_evidencia',side_effect=modify):
            with self.assertRaises(ErrorRevisionResultados):self.service.registrar(self.body)
        base=self.case/'revisiones_resultados'
        self.assertFalse(list(base.iterdir()) if base.exists() else [])
        original.write_bytes(raw);item=self.service.registrar(self.body);meta=base/item['id']/'version.json';native_sources=self.service._fuentes;changed=False
        def modify_record(*args,**kwargs):
            nonlocal changed
            value=native_sources(*args,**kwargs)
            if not changed:changed=True;meta.write_bytes(meta.read_bytes()+b'\n')
            return value
        with patch.object(self.service,'_fuentes',side_effect=modify_record):
            with self.assertRaises(ErrorRevisionResultados):self.read(item['id'])

    def test_otro_analisis_sin_vinculo_exacto_no_se_acepta(self):
        other='28f6d928fac949acadd19f294e6bf644';shutil.copytree(self.bundle/'otro_analisis'/other,self.case/'analisis_etabs'/other)
        with self.assertRaises(ErrorRevisionResultados):self.service.registrar({**self.body,'analisis':other})

    def test_enlace_de_grupo_se_rechaza(self):
        other=self.bundle/'ajeno';other.mkdir();group=self.case/'revisiones_resultados'
        try:os.symlink(other,group,target_is_directory=True)
        except OSError as error:self.skipTest('Sandbox Windows no permite crear enlace: '+str(error.winerror if hasattr(error,'winerror') else type(error).__name__))
        self.addCleanup(lambda:group.unlink() if group.is_symlink() else None)
        with self.assertRaises(ErrorRevisionResultados):self.service.registrar(self.body)
        self.assertEqual(list(other.iterdir()),[])

if __name__=='__main__':unittest.main()
