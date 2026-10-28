import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from draft2model.revision_visual import RevisionLocal
from draft2model.revision_entregables import ServicioEntregables
from tests.fixture_etabs import extraer_evidencia

CASO='demo-integrada-sintetica';RESULTADO='72c06efb3bfe477bb1fe565809aeddec';ANALISIS='adf97fbc232141e8ae687872c0d71232'


class EntregablesTests(unittest.TestCase):
    def test_listado_no_incluye_informe_roto_de_otro_resultado(self):
        report=self.service.crear(self.body);ident='e'*32;group=self.app.raiz/CASO/'informes'
        target=group/ident;shutil.copytree(group/report['id'],target)
        path=target/'paquete.json';meta=json.loads(path.read_bytes());meta.update(id=ident,resultado='f'*32)
        path.write_text(json.dumps(meta))
        rows=self.service.listar(CASO,RESULTADO,expediente_sha256=self.fp)['versiones']
        self.assertEqual([v['id'] for v in rows],[report['id']])

    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.bundle=extraer_evidencia(Path(temp.name).resolve()/'fixture')
        self.app=RevisionLocal(self.bundle/'private');self.service=ServicioEntregables(self.app)
        self.fp=self.app.expediente(CASO)[2]
        self.body={'caso':CASO,'resultado':RESULTADO,'expediente_sha256':self.fp,'analisis':None,
            'contexto':{'titulo':'Fixture documental','hipotesis':['Datos sintéticos de prueba.'],
                        'faltantes':['Normativa y revisión de ingeniería pendientes.'],'sitio':None}}

    def archivo(self,ident,formato='pdf'):return self.service.archivo(CASO,ident,formato,expediente_sha256=self.fp)

    def test_version_nueva_descarga_sin_aprobacion_ni_evidencia_inventada(self):
        first=self.service.crear(self.body);second=self.service.crear(self.body)
        self.assertNotEqual(first['id'],second['id']);self.assertEqual(first['estado'],'borrador')
        self.assertFalse(first['aprueba_resultados']);self.assertIsNone(first['evidencia_analisis'])
        self.assertTrue(self.archivo(first['id']).startswith(b'%PDF'))
        report=json.loads(self.archivo(first['id'],'json'))
        self.assertEqual(report['revision']['estado'],'borrador');self.assertIsNone(report['reglas'])
        self.assertEqual(report['resultados']['caso_id'],CASO)
        self.assertNotIn(str(self.bundle),json.dumps(first))

    def test_analisis_seleccionado_se_verifica_y_alteracion_bloquea_descarga(self):
        self.assertEqual(self.service.listar_analisis(CASO,RESULTADO,expediente_sha256=self.fp)['versiones'],[])
        target=self.app.raiz/CASO/'analisis_etabs'/ANALISIS
        shutil.copytree(self.bundle/'analisis'/ANALISIS,target)
        rows=self.service.listar_analisis(CASO,RESULTADO,expediente_sha256=self.fp)['versiones']
        self.assertTrue(rows[0]['vigente'])
        body=copy.deepcopy(self.body);body['analisis']=ANALISIS
        report=self.service.crear(body)
        self.assertEqual(report['evidencia_analisis']['estados']['calculo'],'completado_verificado')
        (target/'analizado.edb').write_bytes(b'ALTERADO')
        with self.assertRaises(ValueError):self.archivo(report['id'])

    def test_paquete_y_original_alterados_y_rutas_rechazadas(self):
        for extra in ({'resultado':'../fuera'},{'caso':'otro'},{'expediente_sha256':'0'*64},{'analisis':'../otra'}):
            with self.subTest(extra=extra),self.assertRaises((ValueError,OSError)):self.service.crear({**self.body,**extra})
        report=self.service.crear(self.body)
        with self.assertRaises(ValueError):self.archivo(report['id'],'../expediente')
        path=self.app.raiz/CASO/'informes'/report['id']/'informe.pdf';path.write_bytes(b'ALTERADO')
        with self.assertRaises(ValueError):self.archivo(report['id'])
        another=self.service.crear(self.body)
        original=next((self.app.raiz/CASO/'originales').iterdir());original.write_bytes(b'ALTERADO')
        with self.assertRaises(ValueError):self.archivo(another['id'])

    def test_snapshot_geometrico_discrepante_y_cambio_durante_consulta_rechazados(self):
        import hashlib
        from draft2model.informe import validar_informe
        report=self.service.crear(self.body);folder=self.app.raiz/CASO/'informes'/report['id']
        path=folder/'informe.json';data=json.loads(path.read_bytes())
        data['geometria']['datos']['muros'][0]['espesor']=0.30
        raw=json.dumps(data).encode();path.write_bytes(raw)
        meta_path=folder/'paquete.json';meta=json.loads(meta_path.read_bytes())
        meta['archivos']['informe.json']=hashlib.sha256(raw).hexdigest();meta_path.write_text(json.dumps(meta))
        with self.assertRaises(ValueError):self.archivo(report['id'],'json')
        another=self.service.crear(self.body)
        original=next((self.app.raiz/CASO/'originales').iterdir())
        def cambiar_fuente(data):
            validar_informe(data);original.write_bytes(b'ALTERADO DURANTE CONSULTA')
        with patch('draft2model.revision_entregables.validar_informe',side_effect=cambiar_fuente):
            with self.assertRaises(ValueError):self.archivo(another['id'])
