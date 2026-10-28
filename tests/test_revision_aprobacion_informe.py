"""Aprobación exclusivamente documental sobre evidencia sintética conservada."""
import copy
import hashlib
import json
import unittest
from unittest.mock import patch

from tests import test_revision_entregables as fixtures
from draft2model.revision_entregables import exportar_informe
from draft2model.informe import aprobar_informe,validar_informe

CASO,RESULTADO=fixtures.CASO,fixtures.RESULTADO


class AprobacionInformeTests(unittest.TestCase):
    setUp=fixtures.EntregablesTests.setUp
    archivo=fixtures.EntregablesTests.archivo

    def draft(self):
        return self.service.crear(self.body)

    def approval(self,draft):
        return {'caso':CASO,'version':draft['id'],'expediente_sha256':self.fp,
            'sha256_informe':draft['archivos']['informe.json'],
            'revisor_declarado':'Revisor documental declarado SINTÉTICO',
            'fecha':'2026-10-18','motivo':'Prueba documental; no aprueba ingeniería.',
            'confirmacion_explicita':True}

    def folder(self,ident):
        return self.app.raiz/CASO/'informes'/ident

    def test_aprobacion_inmutable_descargas_y_no_aprobacion_heredada(self):
        draft=self.draft();folder=self.folder(draft['id'])
        original={p.name:p.read_bytes() for p in folder.iterdir()}
        parent=json.loads(original['informe.json'])
        approved=self.service.aprobar(self.approval(draft))
        self.assertNotEqual(approved['id'],draft['id'])
        self.assertEqual(approved['estado'],'aprobado')
        self.assertEqual(approved['padre'],{'id':draft['id'],
            'sha256_informe':hashlib.sha256(original['informe.json']).hexdigest(),
            'sha256_paquete':hashlib.sha256(original['paquete.json']).hexdigest()})
        report=json.loads(self.archivo(approved['id'],'json'))
        self.assertEqual(report['revision']['estado'],'aprobado')
        self.assertIn('no autenticada',report['revision']['aprobacion']['alcance'])
        self.assertEqual(report['resultados'],parent['resultados'])
        self.assertEqual(report['siete_resultados'],parent['siete_resultados'])
        self.assertFalse(approved['aprueba_resultados'])
        self.assertEqual(approved['revision_resultados'],'pendiente')
        self.assertEqual(approved['conformidad_normativa'],'no_evaluada')
        self.assertTrue(self.archivo(approved['id']).startswith(b'%PDF'))
        self.assertIn(b'APROBADO',self.archivo(approved['id'],'html'))
        self.assertEqual(original,{p.name:p.read_bytes() for p in folder.iterdir()})
        rows=self.service.listar(CASO,RESULTADO,expediente_sha256=self.fp)['versiones']
        self.assertEqual({x['estado'] for x in rows},{'borrador','aprobado'})
        self.assertTrue(all(x['vigente'] for x in rows))
        self.assertEqual(self.draft()['estado'],'borrador')

    def test_confirmacion_campos_huellas_y_revision_incompletas_no_publican(self):
        draft=self.draft();body=self.approval(draft)
        before=set(self.folder(draft['id']).parent.iterdir())
        variants=[{**body,'confirmacion_explicita':x} for x in (False,1,'true',None)]
        variants += [{**body,'sha256_informe':'0'*64},{**body,'expediente_sha256':'0'*64},
                     {**body,'motivo':''},{**body,'fecha':'ayer'},{**body,'ruta':'../fuera'}]
        variants.append({k:v for k,v in body.items() if k!='revisor_declarado'})
        for invalid in variants:
            with self.subTest(invalid=invalid),self.assertRaises((ValueError,OSError)):
                self.service.aprobar(invalid)
        self.assertEqual(before,set(self.folder(draft['id']).parent.iterdir()))

    def test_alteracion_padre_invalida_hija_y_no_se_aprueba_una_aprobacion(self):
        draft=self.draft();approved=self.service.aprobar(self.approval(draft))
        with self.assertRaises(ValueError):self.service.aprobar(self.approval(approved))
        parent_meta=self.folder(draft['id'])/'paquete.json'
        parent_meta.write_bytes(parent_meta.read_bytes()+b'\n')
        with self.assertRaises(ValueError):self.archivo(approved['id'])
        rows=self.service.listar(CASO,RESULTADO,expediente_sha256=self.fp)['versiones']
        self.assertFalse(next(x for x in rows if x['id']==approved['id'])['vigente'])

    def test_fuente_alterada_bloquea_aprobacion_y_descarga(self):
        draft=self.draft();approved=self.service.aprobar(self.approval(draft))
        original=next((self.app.raiz/CASO/'originales').iterdir())
        original.write_bytes(b'ALTERADO SINTETICO')
        with self.assertRaises(ValueError):self.service.aprobar(self.approval(draft))
        with self.assertRaises(ValueError):self.archivo(approved['id'],'json')

    def test_cambio_de_padre_durante_exportacion_no_publica_ni_deja_staging(self):
        draft=self.draft();parent=self.folder(draft['id'])/'informe.html'
        before=set(parent.parent.parent.iterdir())
        def change(*args,**kwargs):
            result=exportar_informe(*args,**kwargs)
            parent.write_bytes(parent.read_bytes()+b'<!-- cambiado -->')
            return result
        with patch('draft2model.revision_entregables.exportar_informe',side_effect=change):
            with self.assertRaises(ValueError):self.service.aprobar(self.approval(draft))
        self.assertEqual(before,set(parent.parent.parent.iterdir()))

    def test_ciclos_cadenas_y_contenido_distinto_al_padre_rechazados(self):
        draft=self.draft();approved=self.service.aprobar(self.approval(draft))
        meta_path=self.folder(approved['id'])/'paquete.json'
        original=json.loads(meta_path.read_bytes())
        report_path=self.folder(approved['id'])/'informe.json'
        original_report=report_path.read_bytes()
        changed=json.loads(original_report);changed['contexto']['titulo']='Otro contenido documental'
        changed['revision']={'estado':'borrador','aprobacion':None}
        changed=aprobar_informe(changed,revisor_declarado='Fixture declarada',fecha='2026-10-18',motivo='Prueba de cambio')
        validar_informe(changed)
        raw=json.dumps(changed).encode();report_path.write_bytes(raw)
        altered=copy.deepcopy(original);altered['archivos']['informe.json']=hashlib.sha256(raw).hexdigest()
        meta_path.write_text(json.dumps(altered),encoding='utf-8')
        with self.assertRaises(ValueError):self.archivo(approved['id'])
        report_path.write_bytes(original_report)
        for patch_parent in ({'id':approved['id']},{'sha256_informe':'0'*64},
                             {'sha256_paquete':'0'*64},{'id':'../otro'}):
            meta=copy.deepcopy(original);meta['padre'].update(patch_parent)
            meta_path.write_text(json.dumps(meta),encoding='utf-8')
            with self.assertRaises(ValueError):self.archivo(approved['id'])
        meta_path.write_text(json.dumps(original),encoding='utf-8')
        # Un padre aprobado no puede crear recursión ni cadena ilimitada.
        parent_meta=self.folder(draft['id'])/'paquete.json'
        pm=json.loads(parent_meta.read_bytes());pm['estado']='aprobado';pm['padre']=original['padre']
        parent_meta.write_text(json.dumps(pm),encoding='utf-8')
        with self.assertRaises(ValueError):self.archivo(approved['id'])


if __name__=='__main__':unittest.main()
