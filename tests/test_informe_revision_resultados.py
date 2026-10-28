"""Enlace optativo real al servicio, sobre fixture sintética conservada; sin motor/red."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from draft2model.informe import crear_informe, exportar_informe, validar_informe
from draft2model.revision_entregables import ServicioEntregables
from tests import test_revision_aprobacion_resultados as rr
CASO, RESULTADO, ANALISIS, snapshot = rr.CASO, rr.RESULTADO, rr.ANALISIS, rr.snapshot


class InformeRevisionResultadosTests(unittest.TestCase):
    def setUp(self):
        rr.RevisionResultadosTests.setUp(self)
        self.revisiones=self.service
        self.revision=self.revisiones.registrar(self.body)
        self.service=ServicioEntregables(self.app)
        self.body={'caso':CASO,'resultado':RESULTADO,'analisis':ANALISIS,'expediente_sha256':self.fp,
            'contexto':{'titulo':'Informe sintético con declaración explícita','hipotesis':['Fixture conservada.'],
                        'faltantes':['Revisión profesional no acreditada.'],'sitio':None},
            'revision_resultados':{'id':self.revision['id'],'sha256_revision':self.revision['sha256_revision']}}

    def crear(self):return self.service.crear(self.body)
    def archivo(self,item,formato='json'):
        return self.service.archivo(CASO,item['id'],formato,expediente_sha256=self.fp)
    def aprobacion(self,item):
        return {'caso':CASO,'version':item['id'],'expediente_sha256':self.fp,
                'sha256_informe':item['archivos']['informe.json'],'revisor_declarado':'Revisión documental declarada',
                'fecha':'2026-10-18','motivo':'Solo integridad documental sintética.','confirmacion_explicita':True}
    def fuente(self):
        return {'app':self.app,'caso':CASO,'id':self.revision['id'],
                'sha256_revision':self.revision['sha256_revision'],'expediente_sha256':self.fp}

    def test_seleccion_snapshot_render_pdf_sin_mutacion_ni_autoseleccion(self):
        native=snapshot(self.result);declaration=snapshot(self.case/'revisiones_resultados')
        body=copy.deepcopy(self.body);body.pop('revision_resultados')
        old=self.service.crear(body);old_json=json.loads(self.archivo(old))
        self.assertEqual(old['revision_resultados'],'pendiente')
        self.assertNotIn('revision_resultados_seleccionada',old);self.assertNotIn('revision_resultados',old_json)
        item=self.crear();report=json.loads(self.archivo(item));validar_informe(report)
        self.assertEqual(item['revision_resultados'],'revisados_declarados')
        self.assertEqual(item['revision_resultados_seleccionada'],self.body['revision_resultados'])
        self.assertEqual(report['revision_resultados'],self.revision)
        self.assertEqual(report['evidencia_analisis']['estados']['revision_resultados'],'pendiente')
        self.assertEqual(report['siete_resultados']['estado_modelo_analisis']['revision_resultados'],'pendiente')
        html=self.archivo(item,'html').decode()
        for text in ('Revisión DECLARADA','revisados_declarados',self.revision['id'],
                     self.revision['declaracion']['revisor_declarado'],self.revision['declaracion']['alcance'],
                     self.revision['declaracion']['observaciones'][0],'Faltantes críticos declarados: []'):
            self.assertIn(text,html)
        import pymupdf
        with pymupdf.open(stream=self.archivo(item,'pdf'),filetype='pdf') as pdf:
            # NFKC: el PDF puede extraer «ff» como ligadura U+FB00 en IDs hexadecimales aleatorios.
            import unicodedata
            text=unicodedata.normalize('NFKC',' '.join(p.get_text() for p in pdf))
            self.assertIn('Revisión DECLARADA',text);self.assertIn(self.revision['id'],text)
        self.assertEqual(snapshot(self.result),native);self.assertEqual(snapshot(self.case/'revisiones_resultados'),declaration)

    def test_hash_campos_nulos_analisis_caso_y_fuente_inventada_rechazados(self):
        cases=[{'revision_resultados':None},{'revision_resultados':False},{'revision_resultados':{}},
               {'revision_resultados':{'id':self.revision['id'],'sha256_revision':'0'*64}},
               {'revision_resultados':{**self.body['revision_resultados'],'snapshot':self.revision}},
               {'analisis':None},{'analisis':'0'*32},{'caso':'otro-caso'},{'resultado':'0'*32},
               {'expediente_sha256':'0'*64}]
        before=snapshot(self.bundle)
        for changes in cases:
            with self.subTest(changes=list(changes)),self.assertRaises((ValueError,OSError)):
                self.service.crear({**self.body,**changes})
        self.assertEqual(snapshot(self.bundle),before)
        checked,geometry,source,_=self.service._fuente(CASO,RESULTADO,self.fp,ANALISIS)
        with self.assertRaises(ValueError):crear_informe(checked['datos'],None,self.body['contexto'],
            geometria_archivo=geometry,evidencia_analisis=source,fuente_revision_resultados=self.revision)

    def test_aprobacion_hija_conserva_referencia_sin_aprobar_resultados(self):
        item=self.crear();before=self.archivo(item)
        child=self.service.aprobar(self.aprobacion(item));report=json.loads(self.archivo(child))
        self.assertEqual(child['revision_resultados_seleccionada'],item['revision_resultados_seleccionada'])
        self.assertEqual(report['revision_resultados'],self.revision);self.assertFalse(child['aprueba_resultados'])
        self.assertEqual(report['revision']['estado'],'aprobado');self.assertEqual(self.archivo(item),before)
        parent_report=json.loads(before)
        self.assertEqual({k:v for k,v in report.items() if k!='revision'},
                         {k:v for k,v in parent_report.items() if k!='revision'})

    def test_revision_resultado_y_edb_alterados_bloquean_consulta_descarga_aprobacion(self):
        item=self.crear()
        for path in (self.case/'revisiones_resultados'/self.revision['id']/'revision.json',
                     self.result/'resultados.json',self.run/'analizado.EDB'):
            raw=path.read_bytes();path.write_bytes(raw+b'\n')
            try:
                with self.subTest(path=path.name):
                    with self.assertRaises((ValueError,OSError)):self.service.consultar(CASO,item['id'],expediente_sha256=self.fp)
                    with self.assertRaises((ValueError,OSError)):self.archivo(item,'pdf')
                    with self.assertRaises((ValueError,OSError)):self.service.aprobar(self.aprobacion(item))
                    with self.assertRaises((ValueError,OSError)):self.crear()
            finally:path.write_bytes(raw)

    def test_snapshot_adulterado_aun_rehashado_y_referencia_cambiada(self):
        item=self.crear();folder=self.case/'informes'/item['id'];path=folder/'informe.json';meta_path=folder/'paquete.json'
        raw=path.read_bytes();raw_meta=meta_path.read_bytes();report=json.loads(raw)
        # Even a fully coherent invented snapshot is not an authoritative service record.
        from draft2model.revision_aprobacion_resultados import _bytes, ServicioRevisionResultados
        native_record=json.loads((self.case/'revisiones_resultados'/self.revision['id']/'revision.json').read_bytes())
        native_record['declaracion']['alcance']='Inventado después'
        report['revision_resultados']=ServicioRevisionResultados._proyeccion(native_record,_bytes(native_record))
        from draft2model.resultados_estructurales import huella_resultados
        report['huellas']['revision_resultados']=huella_resultados(report['revision_resultados'])
        self.assertTrue(validar_informe(report))  # Coherence alone cannot authenticate a source.
        changed=json.dumps(report).encode();path.write_bytes(changed)
        meta=json.loads(raw_meta);meta['archivos']['informe.json']=hashlib.sha256(changed).hexdigest()
        meta_path.write_text(json.dumps(meta))
        with self.assertRaises(ValueError):self.archivo(item)
        path.write_bytes(raw);meta_path.write_bytes(raw_meta)
        meta=json.loads(raw_meta);meta['revision_resultados']['sha256_revision']='0'*64
        meta_path.write_text(json.dumps(meta))
        with self.assertRaises(ValueError):self.archivo(item)

    def test_exportacion_exige_fuente_actual_y_cambio_durante_render_no_publica(self):
        item=self.crear();report=json.loads(self.archivo(item))
        _,geometry,source,_=self.service._fuente(CASO,RESULTADO,self.fp,ANALISIS)
        with self.assertRaises(ValueError):exportar_informe(report,self.bundle/'rechazado',
            geometria_archivo=geometry,evidencia_analisis=source)
        from draft2model import informe
        native=informe._pdf;path=self.case/'revisiones_resultados'/self.revision['id']/'revision.json';raw=path.read_bytes()
        def change(html):
            pdf=native(html);path.write_bytes(raw+b'\n');return pdf
        try:
            with patch.object(informe,'_pdf',side_effect=change),self.assertRaises(ValueError):
                exportar_informe(report,self.bundle/'no_publicado',geometria_archivo=geometry,
                    evidencia_analisis=source,fuente_revision_resultados=self.fuente())
            self.assertFalse((self.bundle/'no_publicado').exists())
        finally:path.write_bytes(raw)


if __name__=='__main__':unittest.main()
