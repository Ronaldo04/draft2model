"""Aprobación propia sobre copia portable sintética; sin motor ni red."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from draft2model import revision_modelo as rm
from draft2model.revision_aprobacion_modelo import ErrorRevisionModelo, ServicioRevisionModelo
from draft2model.revision_visual import RevisionLocal
from tests.fixture_etabs import extraer_evidencia

CASO='demo-integrada-sintetica'
MODELO='225f8c4a9a0744fbb702a9f0b9affdc0'


def snapshot(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


class RevisionModeloWebTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.bundle=extraer_evidencia(Path(temp.name).resolve()/'fixture')
        self.app=RevisionLocal(self.bundle/'private');self.case=self.app.raiz/CASO
        # Conservar antecedentes; el ensayo necesita un modelo sin aprobación activa.
        (self.case/'aprobaciones_modelo').rename(self.case/'aprobaciones_antecedentes')
        self.service=ServicioRevisionModelo(self.app)
        self.fp=self.app.expediente(CASO)[2]
        self.model=self.case/'modelos_construidos'/MODELO
        self.huella=self.app.resultados.consultar_modelo(CASO,MODELO,expediente_sha256=self.fp)['huella_modelo']
        self.body={'caso':CASO,'modelo':MODELO,'expediente_sha256':self.fp,'huella_modelo':self.huella,
                   'revisor':'Revisor de prueba sintética','fecha':'2026-10-17',
                   'alcance':'Solo evidencia sintética de software; no aprobación de ingeniería física.',
                   'controles':{key:True for key in rm.CONTROLES},'confirmacion_explicita':True}

    def consultar(self):
        return self.service.consultar(CASO,MODELO,expediente_sha256=self.fp)

    def test_pendiente_consulta_sin_escrituras_y_aprobacion_propia(self):
        before=snapshot(self.bundle);initial=self.consultar()
        self.assertEqual(snapshot(self.bundle),before)
        self.assertEqual(initial['estado'],'pendiente');self.assertEqual(initial['aprobaciones'],[])
        self.assertEqual(initial['controles_requeridos'],list(rm.CONTROLES))
        result=self.service.aprobar(self.body)
        self.assertEqual(result['estado'],'aprobado');self.assertEqual(len(result['aprobaciones']),1)
        approval=result['aprobaciones'][0]
        self.assertEqual(approval['id'],result['aprobacion_registrada'])
        self.assertEqual(approval['huella_modelo'],self.huella)
        self.assertEqual(approval['controles'],self.body['controles'])
        self.assertEqual(approval['identidad_revisor'],'declarada_no_verificada')
        self.assertTrue(approval['autoriza_analisis'])
        self.assertFalse(result['analisis_ejecutado'] or result['aprueba_resultados'])
        self.assertEqual(rm.consultar(self.app.raiz,CASO,MODELO)['estado'],'pendiente')
        self.assertEqual(self.consultar()['aprobaciones'],result['aprobaciones'])
        text=json.dumps(result)
        for private in (str(self.bundle),'archivo_motor','destino_guardado','"ruta"',':\\'):
            self.assertNotIn(private,text)

    def test_confirmacion_controles_exactos_y_declaracion_obligatorios(self):
        missing=dict(self.body['controles']);missing.pop(next(iter(missing)))
        false=dict(self.body['controles']);false[next(iter(false))]=False
        truthy=dict(self.body['controles']);truthy[next(iter(truthy))]=1
        cases=[{'confirmacion_explicita':False},{'confirmacion_explicita':1},
               {'controles':missing},{'controles':false},{'controles':truthy},
               {'controles':{**self.body['controles'],'inferido':True}},
               {'revisor':''},{'alcance':'  '},{'fecha':'2026-13-17'},{'extra':'no permitido'}]
        before=snapshot(self.bundle)
        for changes in cases:
            with self.subTest(changes=changes),self.assertRaises(ErrorRevisionModelo):
                self.service.aprobar({**self.body,**changes})
        incomplete=dict(self.body);incomplete.pop('fecha')
        with self.assertRaises(ErrorRevisionModelo):self.service.aprobar(incomplete)
        self.assertEqual(snapshot(self.bundle),before)

    def test_huellas_caso_e_identificadores_no_publican(self):
        before=snapshot(self.bundle)
        for changes in ({'huella_modelo':'0'*64},{'expediente_sha256':'0'*64},
                        {'modelo':'../'+MODELO},{'modelo':'a'*32},{'modelo':123},
                        {'caso':'otro-caso'},{'caso':'../fuera'}):
            with self.subTest(changes=changes),self.assertRaises(ErrorRevisionModelo):
                self.service.aprobar({**self.body,**changes})
        self.assertEqual(snapshot(self.bundle),before)

    def test_origen_o_edb_alterados_impiden_consultar_y_aprobar(self):
        manifest=json.loads((self.case/'expediente.json').read_bytes())
        original=self.case/manifest['archivos'][0]['archivo']
        for path in (original,self.model/'modelo.edb',self.model/'configuracion.json'):
            with self.subTest(path=path.name):
                raw=path.read_bytes();path.write_bytes(raw+b'alterado')
                with self.assertRaises(ErrorRevisionModelo):self.consultar()
                with self.assertRaises(ErrorRevisionModelo):self.service.aprobar(self.body)
                path.write_bytes(raw)
        self.assertEqual(self.consultar()['estado'],'pendiente')

    def test_aprobacion_alterada_no_se_hereda_y_varias_no_se_seleccionan(self):
        first=self.service.aprobar(self.body);second=self.service.aprobar(self.body)
        self.assertNotEqual(first['aprobacion_registrada'],second['aprobacion_registrada'])
        self.assertEqual(len(second['aprobaciones']),2)
        group=self.case/'aprobaciones_modelo'
        path=group/first['aprobacion_registrada']/'aprobacion.json'
        record=json.loads(path.read_bytes());record['controles'][rm.CONTROLES[0]]=False
        path.write_text(json.dumps(record),encoding='utf-8')
        current=self.consultar()
        self.assertEqual([a['id'] for a in current['aprobaciones']],[second['aprobacion_registrada']])
        self.assertIn('aprobaciones_no_verificables_en_caso',current['advertencias'])
        path=group/second['aprobacion_registrada']/'aprobacion.json'
        record=json.loads(path.read_bytes());record['modelo_id']='a'*32
        path.write_text(json.dumps(record),encoding='utf-8')
        self.assertEqual(self.consultar()['estado'],'pendiente')

    def test_reconsulta_final_rechaza_cambio_antes_de_publicar_respuesta(self):
        real=rm.aprobar
        def change(*args,**kwargs):
            result=real(*args,**kwargs)
            path=self.model/'modelo.edb';path.write_bytes(path.read_bytes()+b'cambio concurrente')
            return result
        with patch.object(rm,'aprobar',side_effect=change):
            with self.assertRaises(ErrorRevisionModelo):self.service.aprobar(self.body)

    def test_directorio_alterado_y_errores_sin_paths(self):
        (self.case/'aprobaciones_modelo').write_text('no directorio')
        with self.assertRaises(ErrorRevisionModelo):self.consultar()
        with patch.object(self.app.resultados,'consultar_modelo',side_effect=ValueError('C:/privado/secreto')):
            with self.assertRaises(ErrorRevisionModelo) as ctx:self.consultar()
        self.assertNotIn('privado',str(ctx.exception))


if __name__=='__main__':unittest.main()
