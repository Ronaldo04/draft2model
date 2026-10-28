import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from draft2model.revision_visual import RevisionLocal
from draft2model.revision_mapeos import ServicioMapeos
from tests.fixture_etabs import extraer_evidencia

CASO='demo-integrada-sintetica'
ANALISIS='adf97fbc232141e8ae687872c0d71232'
RESULTADO='72c06efb3bfe477bb1fe565809aeddec'


class MapeosTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.bundle=extraer_evidencia(Path(temp.name).resolve()/'fixture')
        self.app=RevisionLocal(self.bundle/'private');self.service=ServicioMapeos(self.app)
        self.case=self.app.raiz/CASO;self.fp=self.app.expediente(CASO)[2]
        self.run=self.case/'analisis_etabs'/ANALISIS;shutil.copytree(self.bundle/'analisis'/ANALISIS,self.run)
        source=self.case/'resultados_estructurales'/RESULTADO
        self.raw=json.loads((source/'respuesta_puente.json').read_bytes())
        self.raw['datos']['modelo']=str(self.run/'analizado.edb')
        raw=json.dumps(self.raw)
        self.mapping=json.loads((source/'mapeo.json').read_bytes())
        self.mapping['modelo']={'archivo':'analisis_etabs/'+ANALISIS+'/analizado.edb',
            'sha256':hashlib.sha256((self.run/'analizado.edb').read_bytes()).hexdigest()}
        self.mapping['sha256_respuesta']=hashlib.sha256(raw.encode()).hexdigest()
        self.mapping['revision']={'estado':'borrador','aprobacion':None}
        self.body={'caso':CASO,'analisis':ANALISIS,'expediente_sha256':self.fp,'respuesta_json':raw,'mapeo_json':json.dumps(self.mapping)}

    def imported(self):return self.service.importar(self.body)

    def base(self,item):return {'caso':CASO,'version':item['id'],'expediente_sha256':self.fp,'huella_mapeo':item['huella_mapeo']}

    def approve(self,item,**changes):
        return self.service.aprobar({**self.base(item),'revisor':'Prueba sintética de software','fecha':'2026-10-17',
            'motivo':'Correspondencias de fixture','alcance':'No aprobación de ingeniería física',
            'confirmacion_explicita':True,**changes})

    def normalize(self,item,**changes):
        return self.service.normalizar({**self.base(item),'clave_solicitud':'b'*32,'confirmacion_explicita':True,**changes})

    def test_versiones_previsualizacion_aprobacion_y_normalizacion_idempotente(self):
        before={p.name for p in (self.case/'resultados_estructurales').iterdir()}
        draft=self.imported();self.assertFalse(draft['previsualizacion']['publicado'] or draft['aprueba_resultados'])
        self.assertEqual(before,{p.name for p in (self.case/'resultados_estructurales').iterdir()})
        with self.assertRaises(ValueError):self.normalize(draft)
        with self.assertRaises(ValueError):self.approve(draft,confirmacion_explicita=False)
        approved=self.approve(draft)
        self.assertNotEqual(draft['id'],approved['id']);self.assertEqual(draft['huella_mapeo'],approved['huella_mapeo'])
        self.assertEqual(self.service.consultar(CASO,draft['id'],expediente_sha256=self.fp)['mapeo']['revision']['estado'],'borrador')
        result=self.normalize(approved);again=self.normalize(approved);self.assertEqual(result,again)
        self.assertEqual(result['evidencia_analisis']['estados']['calculo'],'completado_verificado')
        self.assertFalse(result['aprueba_resultados']);self.assertEqual(result['conformidad_normativa'],'no_evaluada')
        self.assertEqual(len(list((self.case/'resultados_estructurales').iterdir())),len(before)+1)
        self.assertEqual(len(self.service.listar(CASO,expediente_sha256=self.fp)['versiones']),2)
        receipt_path=self.case/'normalizaciones_resultados'/('b'*32)/'aceptacion.json'
        receipt=json.loads(receipt_path.read_bytes());receipt['mapeo_version']='d'*32
        receipt_path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError,'otra normalización'):self.normalize(approved)

    def test_revision_nueva_y_origenes_ajenos_rechazados(self):
        draft=self.imported();mapping=copy.deepcopy(draft['mapeo'])
        mapping['selectores'][0]['ubicacion']='base-revisada'
        revised=self.service.revisar({**self.base(draft),'mapeo_json':json.dumps(mapping)})
        self.assertEqual(revised['padre'],draft['id']);self.assertNotEqual(revised['huella_mapeo'],draft['huella_mapeo'])
        for changes in ({'analisis':'../otra'},{'expediente_sha256':'0'*64},{'caso':'otro'}):
            with self.subTest(changes=changes),self.assertRaises((ValueError,OSError)):
                self.service.importar({**self.body,**changes})
        bad=copy.deepcopy(self.mapping);bad['modelo']['archivo']='../otra.edb'
        with self.assertRaises(ValueError):self.service.importar({**self.body,'mapeo_json':json.dumps(bad)})
        with self.assertRaises(ValueError):self.approve(draft,huella_mapeo='0'*64)

    def test_fuente_edb_snapshot_y_padre_alterados_invalidados(self):
        draft=self.imported();approved=self.approve(draft)
        target=self.case/'mapeos_resultados'/draft['id']/'respuesta.json'
        raw=target.read_bytes();target.write_bytes(raw+b'ALTERADO')
        with self.assertRaises(ValueError):self.service.consultar(CASO,approved['id'],expediente_sha256=self.fp)
        self.assertFalse(self.service.listar(CASO,expediente_sha256=self.fp)['versiones'][0]['vigente'])
        target.write_bytes(raw);(self.run/'analizado.edb').write_bytes(b'ALTERADO')
        with self.assertRaises(ValueError):self.normalize(approved)

    def test_normalizacion_interrumpida_no_se_repite_automaticamente(self):
        approved=self.approve(self.imported())
        with patch('draft2model.revision_mapeos.registrar_resultados',side_effect=RuntimeError('Interrupción simulada')):
            with self.assertRaises(RuntimeError):self.normalize(approved)
        with patch('draft2model.revision_mapeos.registrar_resultados',side_effect=AssertionError('No repetir')):
            with self.assertRaises(ValueError):self.normalize(approved)

    def test_resultado_huerfano_bloquea_clave_nueva_y_se_recupera_sin_recalcular(self):
        approved=self.approve(self.imported());before={p.name for p in (self.case/'resultados_estructurales').iterdir()}
        with patch('draft2model.revision_mapeos.verificar_evidencia',side_effect=OSError('Interrupción tras publicar')):
            with self.assertRaises(OSError):self.normalize(approved)
        new={p.name for p in (self.case/'resultados_estructurales').iterdir()}-before
        self.assertEqual(len(new),1);orphan=new.pop()
        with self.assertRaises(ValueError):self.app.resultados.consultar_resultado(CASO,orphan,expediente_sha256=self.fp)
        rows=self.app.resultados.listar_resultados(CASO)['versiones']
        self.assertFalse(next(r for r in rows if r['id']==orphan)['vigente'])
        with patch('draft2model.revision_mapeos.registrar_resultados',side_effect=AssertionError('No duplicar')):
            with self.assertRaisesRegex(ValueError,'pendiente'):self.normalize(approved,clave_solicitud='c'*32)
            status=self.service.estado_normalizacion(CASO,expediente_sha256=self.fp)
            self.assertEqual(status['pendientes'][0]['resultados_candidatos'],[orphan])
            recovered=self.service.recuperar({'caso':CASO,'expediente_sha256':self.fp,'clave_solicitud':'b'*32,
                'resultado':orphan,'confirmacion_explicita':True})
            self.assertEqual(self.normalize(approved),recovered)
        self.assertEqual(recovered['resultado'],orphan);self.assertTrue(self.app.resultados.consultar_resultado(CASO,orphan,expediente_sha256=self.fp)['vigente'])
        self.assertEqual(self.service.estado_normalizacion(CASO,expediente_sha256=self.fp)['pendientes'],[])

    def test_cancelar_sin_resultado_exige_confirmacion_y_no_publica(self):
        approved=self.approve(self.imported())
        with patch('draft2model.revision_mapeos.registrar_resultados',side_effect=RuntimeError('Antes de publicar')):
            with self.assertRaises(RuntimeError):self.normalize(approved)
        body={'caso':CASO,'expediente_sha256':self.fp,'clave_solicitud':'b'*32,'resultado':None,'confirmacion_explicita':False}
        with self.assertRaises(ValueError):self.service.recuperar(body)
        self.assertTrue(self.service.recuperar({**body,'confirmacion_explicita':True})['cancelada_sin_resultado'])
        self.assertEqual(self.service.estado_normalizacion(CASO,expediente_sha256=self.fp)['pendientes'],[])
        self.normalize(approved,clave_solicitud='c'*32)

    def test_recibo_con_evidencia_alterada_no_desbloquea_publicaciones(self):
        approved=self.approve(self.imported());result=self.normalize(approved)
        path=self.case/'normalizaciones_resultados'/('b'*32)/'aceptacion.json'
        receipt=json.loads(path.read_bytes());receipt['evidencia_analisis']=[];path.write_text(json.dumps(receipt))
        self.assertEqual(len(self.service.estado_normalizacion(CASO,expediente_sha256=self.fp)['pendientes']),1)
        with self.assertRaisesRegex(ValueError,'pendiente'):self.normalize(approved,clave_solicitud='c'*32)
        with self.assertRaises(ValueError):self.app.resultados.consultar_resultado(CASO,result['resultado'],expediente_sha256=self.fp)
        recovered=self.service.recuperar({'caso':CASO,'expediente_sha256':self.fp,'clave_solicitud':'b'*32,
            'resultado':result['resultado'],'confirmacion_explicita':True})
        self.assertEqual(recovered,result);self.assertEqual(len(list(path.parent.glob('aceptacion_no_vigente_*.json'))),1)

    def test_cambio_de_snapshot_durante_previsualizacion_no_devuelve_valores_ajenos(self):
        from draft2model.normalizacion_etabs import previsualizar_resultados
        draft=self.imported();path=self.case/'mapeos_resultados'/draft['id']/'mapeo.json'
        def cambiar(*args,**kwargs):
            data=json.loads(path.read_bytes());data['selectores'][0]['ubicacion']='ubicacion-cambiada'
            path.write_text(json.dumps(data))
            return previsualizar_resultados(*args,**kwargs)
        with patch('draft2model.revision_mapeos.previsualizar_resultados',side_effect=cambiar):
            with self.assertRaisesRegex(ValueError,'durante la previsualización'):
                self.service.consultar(CASO,draft['id'],expediente_sha256=self.fp)
