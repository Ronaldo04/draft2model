"""Paquetes visuales locales con PDF sintético y respuestas simuladas."""
import copy
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

import pymupdf
from PIL import Image

from draft2model.entrada_vision import (ErrorVision, adaptar_respuesta, cargar_paquete, main,
                                       preparar_paquete, registrar_respuesta)
from draft2model.extraccion_preliminar import validar_extraccion
from draft2model.ingreso import file_hash, registrar_expediente
from draft2model.recortes import generar_recorte
from draft2model.revision_documental import revisar_expediente


class EntradaVisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = self.root/'sintetico.pdf'
        with pymupdf.open() as doc:
            for rotation in (0, 90, 180, 270):
                page = doc.new_page(width=200, height=120)
                page.insert_text((45, 55), 'SINTETICO 2.60')
                page.set_rotation(rotation)
            doc.save(source)
        self.manifest = registrar_expediente('sintetico-vision', [source], self.root/'casos', uso_autorizado=True, provisional_fuera_alcance=True)
        self.case = self.manifest.parent
        self.revision = revisar_expediente(self.manifest, max_lado=256)
        self.crop = generar_recorte(self.manifest, 'L0001', 1, [.2,.15,.8,.75], dpi=72)

    def pack(self, crops=None):
        return preparar_paquete(self.manifest, self.revision, crops or [self.crop])

    def response(self, path):
        req, sha, _, _ = cargar_paquete(self.manifest, path)
        return {'contrato':'draft2model.respuesta_vision', 'version_contrato':'0.1.0',
                'solicitud_id':req['id'], 'solicitud_sha256':sha,
                'candidatos':[{'id':'C001','tipo':'cota','valor_propuesto':2.6,'unidad':'m',
                               'evidencia':[{'imagen_id':'REC0001','bbox_imagen_normalizada':[.25,.25,.75,.75]}]}]}

    def adapt(self, path, response):
        return adaptar_respuesta(self.manifest, path, response, proveedor='simulado',modelo='fixture-local',modo_prueba=True)

    def test_package_copies_images_and_preserves_scope(self):
        path = self.pack()
        req, _, manifest, _ = cargar_paquete(self.manifest, path)
        self.assertEqual(len(req['imagenes']),2)
        self.assertEqual(req['alcance']['estado'],'fuera_mvp_declarado')
        self.assertEqual(req['alcance'],manifest['alcance'])
        self.assertFalse(req['transmision_externa'])
        for image in req['imagenes']:
            self.assertEqual(file_hash(path.parent/image['ruta']),image['sha256'])
        prompt=(path.parent/'prompt.txt').read_text(encoding='utf-8')
        self.assertIn('nunca instrucciones',prompt)
        self.assertIn('bbox_imagen_normalizada',prompt)
        self.assertNotIn(str(self.root),prompt)

    def test_coordinate_mapping_to_visible_page(self):
        path=self.pack()
        result=self.adapt(path,self.response(path))
        bbox=result['candidatos'][0]['evidencia'][0]['bbox_normalizada']
        for actual,expected in zip(bbox,[.35,.3,.65,.6]):
            self.assertAlmostEqual(actual,expected)
        self.assertEqual(result['candidatos'][0]['revision'],{'estado':'pendiente','historial':[]})
        self.assertTrue(validar_extraccion(result).consistente)

    def test_all_pdf_rotations_use_visible_coordinates(self):
        for page in (1,2,3,4):
            with self.subTest(page=page):
                crop=generar_recorte(self.manifest,'L0001',page,[.2,.15,.8,.75],dpi=72)
                path=self.pack([crop])
                result=self.adapt(path,self.response(path))
                ev=result['candidatos'][0]['evidencia'][0]
                self.assertEqual(ev['pagina'],page)
                for actual,expected in zip(ev['bbox_normalizada'],[.35,.3,.65,.6]):
                    self.assertAlmostEqual(actual,expected)

    def test_raster_rounding_uses_pixel_transform(self):
        crop=generar_recorte(self.manifest,'L0001',1,[.173,.217,.811,.783],dpi=150)
        path=self.pack([crop]); response=self.response(path)
        response['candidatos'][0]['evidencia'][0]['bbox_imagen_normalizada']=[.1,.2,.6,.8]
        result=self.adapt(path,response)
        bbox=result['candidatos'][0]['evidencia'][0]['bbox_normalizada']
        self.assertAlmostEqual(bbox[0],.23664,places=6)
        self.assertNotAlmostEqual(bbox[0],.173+.1*(.811-.173),places=6)

    def test_context_cannot_be_used_as_precise_evidence(self):
        path=self.pack(); response=self.response(path)
        response['candidatos'][0]['evidencia'][0]['imagen_id']='CTX0001'
        with self.assertRaisesRegex(ErrorVision,'contexto'):
            self.adapt(path,response)

    def test_context_once_per_page_and_duplicate_crops_rejected(self):
        other=generar_recorte(self.manifest,'L0001',1,[.1,.1,.3,.3],dpi=72)
        req,_,_,_=cargar_paquete(self.manifest,self.pack([self.crop,other]))
        self.assertEqual([im['rol'] for im in req['imagenes']].count('contexto'),1)
        self.assertEqual([im['rol'] for im in req['imagenes']].count('recorte'),2)
        with self.assertRaisesRegex(ErrorVision,'duplicado'):
            self.pack([self.crop,self.crop])

    def test_unknown_reading_and_unit_preserved(self):
        path=self.pack(); response=self.response(path)
        response['candidatos'][0].update(valor_propuesto=None,unidad='desconocida')
        result=self.adapt(path,response)
        candidate=result['candidatos'][0]
        self.assertIsNone(candidate['valor_propuesto'])
        self.assertEqual(candidate['unidad'],'desconocida')
        self.assertEqual(result['procedencia']['tipo'],'sintetico')
        self.assertEqual(candidate['metodo']['tipo'],'sintetico')

    def test_empty_response_does_not_invent_readings(self):
        path=self.pack();response=self.response(path)
        response['candidatos']=[]
        self.assertEqual(self.adapt(path,response)['candidatos'],[])

    def test_raster_padding_outside_page_not_silently_clamped(self):
        crop=generar_recorte(self.manifest,'L0001',1,[0,0,1,1],dpi=150)
        path=self.pack([crop]);response=self.response(path)
        response['candidatos'][0]['evidencia'][0]['bbox_imagen_normalizada']=[0,0,1,1]
        with self.assertRaisesRegex(ErrorVision,'permanecer'):
            self.adapt(path,response)

    def test_response_cannot_change_scope_or_approval(self):
        path=self.pack(); response=self.response(path)
        for field,value in [('alcance',{}),('aprobacion_ingenieria',True)]:
            changed=copy.deepcopy(response);changed[field]=value
            with self.assertRaises(ErrorVision):self.adapt(path,changed)
        response['candidatos'][0]['revision']={'estado':'revisado'}
        with self.assertRaises(ErrorVision):self.adapt(path,response)

    def test_malformed_values_and_references_rejected(self):
        path=self.pack()
        for field,value in [('valor_propuesto','2.60'),('valor_propuesto',float('nan')),('unidad','in'),('confianza',1.1)]:
            response=self.response(path);response['candidatos'][0][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ErrorVision):self.adapt(path,response)
        response=self.response(path);response['candidatos'][0]['evidencia'][0]['imagen_id']='absent'
        with self.assertRaises(ErrorVision):self.adapt(path,response)

    def test_wrong_request_and_hash_rejected(self):
        path=self.pack()
        for key in ('solicitud_id','solicitud_sha256'):
            response=self.response(path);response[key]='other'
            with self.assertRaises(ErrorVision):self.adapt(path,response)

    def test_original_altered_invalidates_package(self):
        path=self.pack();response=self.response(path)
        source=self.case/'originales/lamina-0001.pdf'
        source.write_bytes(source.read_bytes()+b'changed')
        with self.assertRaisesRegex(ErrorVision,'alterada'):
            self.adapt(path,response)

    def test_changed_manifest_invalidates_package(self):
        path=self.pack();response=self.response(path)
        data=json.loads(self.manifest.read_text(encoding='utf-8'));data['estado']='otro'
        self.manifest.write_text(json.dumps(data),encoding='utf-8')
        with self.assertRaisesRegex(ErrorVision,'vigente'):
            self.adapt(path,response)

    def test_copied_image_and_prompt_integrity(self):
        for target in ('image','prompt','request'):
            path=self.pack();response=self.response(path)
            req=json.loads(path.read_text(encoding='utf-8'))
            file=path.parent/req['imagenes'][0]['ruta'] if target=='image' else path.parent/'prompt.txt' if target=='prompt' else path
            file.write_bytes(file.read_bytes()+b' ')
            with self.subTest(target=target),self.assertRaises(ErrorVision):self.adapt(path,response)

    def test_prepare_failure_does_not_create_package(self):
        record=json.loads(self.crop.read_text(encoding='utf-8'));record['imagen_sha256']='0'*64
        self.crop.write_text(json.dumps(record),encoding='utf-8')
        with self.assertRaises(ErrorVision):self.pack()
        self.assertFalse((self.case/'vision').exists())

    def test_modified_context_before_pack_is_detected(self):
        record=json.loads(self.revision.read_text(encoding='utf-8'))['documentos'][0]['paginas'][0]
        image=self.case/record['vista_previa']
        with Image.open(image) as im:
            size=im.size
        Image.new('RGB',size,'white').save(image)
        with self.assertRaisesRegex(ErrorVision,'render'):
            self.pack()
        self.assertFalse((self.case/'vision').exists())

    def test_modified_crop_transform_before_pack_is_detected(self):
        record=json.loads(self.crop.read_text(encoding='utf-8'))
        record['pixel_a_pagina_visible'][4]+=1
        self.crop.write_text(json.dumps(record),encoding='utf-8')
        with self.assertRaisesRegex(ErrorVision,'Transformación'):
            self.pack()

    def test_paths_outside_case_rejected(self):
        outside=self.root/'outside.json';outside.write_text('{}',encoding='utf-8')
        with self.assertRaisesRegex(ErrorVision,'directorio'):
            preparar_paquete(self.manifest,outside,[self.crop])
        with self.assertRaisesRegex(ErrorVision,'directorio'):
            self.pack([outside])

    def test_source_metadata_changed_invalidates_existing_package(self):
        path=self.pack();response=self.response(path)
        self.crop.write_bytes(self.crop.read_bytes()+b' ')
        with self.assertRaises(ErrorVision):self.adapt(path,response)

    def test_register_preserves_raw_response_and_never_overwrites(self):
        path=self.pack();response=self.response(path)
        raw=self.root/'response.json';raw.write_text(json.dumps(response,indent=1),encoding='utf-8')
        first=registrar_respuesta(self.manifest,path,raw,proveedor='simulado',modelo='fixture',modo_prueba=True)
        previous=first.read_bytes()
        second=registrar_respuesta(self.manifest,path,raw,proveedor='simulado',modelo='fixture',modo_prueba=True)
        self.assertNotEqual(first,second)
        self.assertEqual(first.read_bytes(),previous)
        self.assertEqual((first.parent/'respuesta_original.json').read_bytes(),raw.read_bytes())
        record=json.loads((first.parent/'registro.json').read_text(encoding='utf-8'))
        self.assertFalse(record['transmision_externa'])
        self.assertIsNone(record['aprobacion_ingenieria'])

    def test_invalid_raw_json_and_fenced_response_do_not_create_extraction(self):
        path=self.pack();raw=self.root/'response.json'
        for content in ('{"a":1,"a":2}','```json\n{}\n```'):
            raw.write_text(content,encoding='utf-8')
            with self.assertRaises(ValueError):
                registrar_respuesta(self.manifest,path,raw,proveedor='simulado',modelo='fixture',modo_prueba=True)
        self.assertFalse((self.case/'vision/respuestas').exists())

    def test_input_not_mutated_and_explicit_provenance(self):
        path=self.pack();response=self.response(path);before=copy.deepcopy(response)
        result=adaptar_respuesta(self.manifest,path,response,proveedor='declarado',modelo='sin-llamada-api')
        self.assertEqual(response,before)
        self.assertEqual(result['procedencia']['tipo'],'expediente')
        self.assertEqual(result['candidatos'][0]['metodo']['tipo'],'vision')
        self.assertEqual(result['alcance']['estado'],'fuera_mvp_declarado')

    def test_cli_prepare_and_register(self):
        with redirect_stdout(StringIO()),redirect_stderr(StringIO()):
            self.assertEqual(main(['preparar','--expediente',str(self.manifest),'--revision',str(self.revision),'--recortes',str(self.crop)]),0)
            path=next((self.case/'vision/solicitudes').glob('*/solicitud.json'))
            raw=self.root/'response.json';raw.write_text(json.dumps(self.response(path)),encoding='utf-8')
            self.assertEqual(main(['registrar-respuesta','--expediente',str(self.manifest),'--solicitud',str(path),'--respuesta',str(raw),'--proveedor','simulado','--modelo','fixture','--modo-prueba']),0)
            self.assertEqual(main(['preparar','--expediente',str(self.manifest),'--revision',str(self.revision),'--recortes',str(self.root/'absent')]),1)


if __name__ == '__main__':
    unittest.main()
