"""Responses API con transporte simulado o HTTP sustituido; ninguna llamada real."""
import base64
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import pymupdf

from draft2model.entrada_vision import preparar_paquete, cargar_paquete
from draft2model.gestion_extraccion import validar_version, corregir_version, exportar_version
from draft2model.ingreso import registrar_expediente
from draft2model.recortes import generar_recorte
from draft2model.revision_documental import revisar_expediente
from draft2model.proveedor_openai import (ENDPOINT, ErrorProveedor, _http, ejecutar_plan,
                                          leer_respuesta_api, main, preparar_peticion, preparar_plan)


class ProveedorOpenAITests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        source=self.root/'sintetico.pdf'
        with pymupdf.open() as doc:
            doc.new_page(width=200,height=120).insert_text((40,50),'SINTETICO')
            doc.save(source)
        self.manifest=registrar_expediente('sintetico-api',[source],self.root/'casos',uso_autorizado=True,provisional_fuera_alcance=True)
        self.case=self.manifest.parent
        revision=revisar_expediente(self.manifest,256)
        crop=generar_recorte(self.manifest,'L0001',1,[.2,.15,.8,.75],dpi=72)
        self.packet=preparar_paquete(self.manifest,revision,[crop])

    def plan(self):
        return preparar_plan(self.manifest,self.packet,modelo='fixture-vision',max_tokens=512)

    def response(self):
        request,sha,_,_=cargar_paquete(self.manifest,self.packet)
        parsed={'contrato':'draft2model.respuesta_vision','version_contrato':'0.1.0',
                'solicitud_id':request['id'],'solicitud_sha256':sha,
                'candidatos':[{'id':'C001','tipo':'cota','valor_propuesto':2.6,'unidad':'m',
                               'evidencia':[{'imagen_id':'REC0001','bbox_imagen_normalizada':[.25,.25,.75,.75]}]}]}
        return {'id':'resp_fixture','model':'fixture-vision','status':'completed',
                'output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':json.dumps(parsed)}]}],
                'usage':{'input_tokens':100,'output_tokens':20,'total_tokens':120}}

    def test_prepare_no_key_no_network_and_explicit_model(self):
        with patch.dict('os.environ',{'OPENAI_API_KEY':''}),patch('draft2model.proveedor_openai._http') as http:
            path=self.plan()
        self.assertFalse(http.called)
        plan=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(plan['estado'],'preparado_sin_envio')
        self.assertIsNone(plan['configuracion']['costo_estimado'])
        self.assertNotIn('data:image',path.read_text(encoding='utf-8'))

    def test_payload_images_labels_json_schema_and_no_storage(self):
        payload,summary=preparar_peticion(self.manifest,self.packet,modelo='fixture-vision')
        self.assertEqual(payload['model'],'fixture-vision')
        self.assertIs(payload['store'],False)
        self.assertTrue(payload['text']['format']['strict'])
        items=payload['input'][1]['content']
        self.assertEqual([i['type'] for i in items],['input_text','input_image','input_text','input_image'])
        req,_,_,_=cargar_paquete(self.manifest,self.packet)
        for content,image in zip([i for i in items if i['type']=='input_image'],req['imagenes']):
            self.assertEqual(base64.b64decode(content['image_url'].split(',',1)[1]),(self.packet.parent/image['ruta']).read_bytes())
        self.assertEqual(payload['text']['format']['schema']['properties']['candidatos']['items']['properties']['evidencia']['items']['properties']['imagen_id']['enum'],['REC0001'])
        self.assertEqual(summary['endpoint'],ENDPOINT)

    def test_schema_all_object_fields_required_and_closed(self):
        payload,_=preparar_peticion(self.manifest,self.packet,modelo='fixture')
        def inspect(node):
            if isinstance(node,dict):
                if node.get('type')=='object':
                    self.assertEqual(set(node['required']),set(node['properties']))
                    self.assertIs(node['additionalProperties'],False)
                for value in node.values():inspect(value)
            elif isinstance(node,list):
                for value in node:inspect(value)
        inspect(payload['text']['format']['schema'])

    def test_local_limits_and_changed_packet_block_request(self):
        for kw in ({'modelo':''},{'modelo':'fixture','max_tokens':True},{'modelo':'fixture','max_tokens':20000},{'modelo':'fixture','detalle':'invalid'}):
            with self.subTest(kw=kw),self.assertRaises(ErrorProveedor):
                preparar_peticion(self.manifest,self.packet,**kw)
        (self.packet.parent/'prompt.txt').write_text('changed',encoding='utf-8')
        with self.assertRaises(ValueError):preparar_peticion(self.manifest,self.packet,modelo='fixture')

    def test_network_requires_explicit_action_and_key_before_attempt(self):
        plan=self.plan()
        with patch.dict('os.environ',{'OPENAI_API_KEY':''}),patch('draft2model.proveedor_openai._http') as http:
            with self.assertRaises(ErrorProveedor):ejecutar_plan(self.manifest,plan)
            with self.assertRaisesRegex(ErrorProveedor,'OPENAI_API_KEY'):
                ejecutar_plan(self.manifest,plan,autorizar_envio=True)
            self.assertFalse(http.called)
            self.assertFalse((plan.parent/'intento.json').exists())

    def test_plan_change_not_silently_accepted(self):
        plan=self.plan();data=json.loads(plan.read_text(encoding='utf-8'))
        data['configuracion']['endpoint']='https://other.invalid'
        plan.write_text(json.dumps(data),encoding='utf-8')
        with self.assertRaisesRegex(ErrorProveedor,'vigente'):
            ejecutar_plan(self.manifest,plan,autorizar_envio=True,transporte=lambda *a:self.response())

    def test_simulated_transport_cannot_be_imported_as_real(self):
        report=ejecutar_plan(self.manifest,self.plan(),autorizar_envio=True,transporte=lambda *a:self.response())
        data=json.loads(report.read_text(encoding='utf-8'))
        self.assertEqual(data['estado'],'simulacion_completada')
        self.assertFalse(data['transmision_externa_intentada'])
        self.assertIsNone(data['version_importada'])
        extracted=json.loads((self.case/data['extraccion']).read_text(encoding='utf-8'))
        self.assertEqual(extracted['procedencia']['tipo'],'sintetico')
        self.assertFalse((self.case/'extracciones').exists())

    def test_http_double_complete_pipeline_to_review_export(self):
        # Fixtures exclusivamente sintéticos; se sustituye HTTP, no se llama a OpenAI.
        with patch.dict('os.environ',{'OPENAI_API_KEY':'fake-for-unit-test'}),patch('draft2model.proveedor_openai._http',return_value=self.response()) as http:
            report=ejecutar_plan(self.manifest,self.plan(),autorizar_envio=True)
        self.assertEqual(http.call_count,1)
        data=json.loads(report.read_text(encoding='utf-8'))
        self.assertEqual(data['estado'],'importada_pendiente_revision')
        self.assertEqual(data['usage']['total_tokens'],120)
        self.assertTrue(validar_version(self.case.parent,'sintetico-api',data['version_importada']).correcta)
        corrected=corregir_version(self.case.parent,'sintetico-api',data['version_importada'],'C001',estado='revisado',
                                   motivo='Confirmacion en fixture sintetico',fecha='2026-10-15',revisor_declarado='Prueba sintetica',valor_revisado=2.65,unidad_revisada='m')
        exported=exportar_version(self.case.parent,'sintetico-api',corrected.identificador)
        self.assertEqual(exported.datos['candidatos'][0]['valor_revisado'],2.65)
        self.assertEqual(exported.datos['alcance']['estado'],'fuera_mvp_declarado')
        self.assertIsNone(exported.datos['aprobacion_ingenieria'])

    def test_one_attempt_per_plan_no_automatic_retry(self):
        plan=self.plan();called=[]
        def fake(*args):called.append(1);return self.response()
        ejecutar_plan(self.manifest,plan,autorizar_envio=True,transporte=fake)
        with self.assertRaisesRegex(ErrorProveedor,'intento'):
            ejecutar_plan(self.manifest,plan,autorizar_envio=True,transporte=fake)
        self.assertEqual(len(called),1)

    def test_timeout_is_retained_without_import_or_retry(self):
        plan=self.plan();calls=[]
        def fake(*args):calls.append(1);raise TimeoutError('test')
        path=ejecutar_plan(self.manifest,plan,autorizar_envio=True,transporte=fake)
        data=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(data['estado'],'fallido')
        self.assertIsNone(data['usage'])
        self.assertIsNone(data['version_importada'])
        self.assertEqual(len(calls),1)
        self.assertFalse((self.case/'extracciones').exists())

    def test_incomplete_refusal_and_invalid_json_not_imported(self):
        for kind in ('incomplete','refusal','duplicate','markdown','wrong_evidence'):
            response=self.response()
            if kind=='incomplete':response['status']='incomplete'
            if kind=='refusal':response['output'][0]['content']=[{'type':'refusal','refusal':'test'}]
            if kind=='duplicate':response['output'][0]['content'][0]['text']='{"x":1,"x":2}'
            if kind=='markdown':response['output'][0]['content'][0]['text']='```json\n{}\n```'
            if kind=='wrong_evidence':
                value=json.loads(response['output'][0]['content'][0]['text'])
                value['candidatos'][0]['evidencia'][0]['imagen_id']='CTX0001'
                response['output'][0]['content'][0]['text']=json.dumps(value)
            path=ejecutar_plan(self.manifest,self.plan(),autorizar_envio=True,transporte=lambda *a:response)
            with self.subTest(kind=kind):
                report=json.loads(path.read_text(encoding='utf-8'))
                self.assertEqual(report['estado'],'fallido')
                self.assertIsNone(report['version_importada'])
                self.assertTrue((path.parent/'respuesta_api.json').exists())
        self.assertFalse((self.case/'extracciones').exists())

    def test_missing_usage_is_unknown_not_zero(self):
        response=self.response();response.pop('usage')
        report=ejecutar_plan(self.manifest,self.plan(),autorizar_envio=True,transporte=lambda *a:response)
        self.assertIsNone(json.loads(report.read_text(encoding='utf-8'))['usage'])

    def test_secret_not_persisted_if_unexpected_response_echoes_it(self):
        response=self.response();response['unexpected']='fake-secret-only-for-test'
        with patch.dict('os.environ',{'OPENAI_API_KEY':'fake-secret-only-for-test'}):
            report=ejecutar_plan(self.manifest,self.plan(),autorizar_envio=True,transporte=lambda *a:response)
        self.assertFalse((report.parent/'respuesta_api.json').exists())
        self.assertNotIn('fake-secret-only-for-test',report.read_text(encoding='utf-8'))

    def test_parser_rejects_ambiguous_or_tool_outputs(self):
        response=self.response();response['output'].append(response['output'][0])
        with self.assertRaises(ErrorProveedor):leer_respuesta_api(response)
        response=self.response();response['output']=[{'type':'function_call','name':'execute'}]
        with self.assertRaises(ErrorProveedor):leer_respuesta_api(response)
        response=self.response();response['output'][0]['status']='incomplete'
        with self.assertRaises(ErrorProveedor):leer_respuesta_api(response)
        response=self.response();response['output']=None
        with self.assertRaises(ErrorProveedor):leer_respuesta_api(response)

    def test_http_endpoint_timeout_and_headers_not_written(self):
        class Reply:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return b'{"status":"completed","output":[]}'
        with patch('draft2model.proveedor_openai.build_opener') as opener:
            opener.return_value.open.return_value=Reply()
            self.assertEqual(_http({'model':'fixture'},'fake-key',5)['status'],'completed')
            args,kwargs=opener.return_value.open.call_args
            self.assertEqual(args[0].full_url,ENDPOINT)
            self.assertEqual(args[0].get_header('Authorization'),'Bearer fake-key')
            self.assertEqual(kwargs['timeout'],5)
        for error in (HTTPError(ENDPOINT,429,'rate limit',{},None),URLError('offline')):
            with patch('draft2model.proveedor_openai.build_opener') as opener:
                opener.return_value.open.side_effect=error
                with self.assertRaises(ErrorProveedor):_http({},'fake-key',5)

    def test_cli_preparation_works_without_key(self):
        with redirect_stdout(StringIO()),redirect_stderr(StringIO()),patch.dict('os.environ',{'OPENAI_API_KEY':''}):
            self.assertEqual(main(['preparar','--expediente',str(self.manifest),'--solicitud',str(self.packet),'--modelo','fixture-vision']),0)
            plan=next((self.case/'vision/planes_openai').glob('*/plan.json'))
            self.assertEqual(main(['ejecutar','--expediente',str(self.manifest),'--plan',str(plan),'--autorizar-envio']),1)


if __name__=='__main__':
    unittest.main()
