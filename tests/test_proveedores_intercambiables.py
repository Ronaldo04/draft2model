"""Planes y servicios con protocolos distintos, respuestas dobles y cero red real."""
import json
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError

from draft2model import proveedores, proveedor_compatible as compatible
from draft2model import proveedor_openai as base
from draft2model.revision_proveedor import ServicioProveedor, ErrorProveedorWeb
from draft2model.revision_explicaciones import ServicioExplicaciones
from tests import test_revision_proveedor as vision
from tests import test_revision_explicaciones as explicaciones
from tests.test_proveedor_gemini import respuesta as respuesta_gemini
from tests.test_proveedor_anthropic import respuesta as respuesta_anthropic


ENDPOINT = 'https://ia.example.org/v1/chat/completions'


def respuesta_compatible(text):
    return {'id': 'doble-compatible', 'model': 'modelo-doble', 'usage': {'total_tokens': 12},
            'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': text}}]}


class ProtocolosTests(unittest.TestCase):
    def test_registro_no_carga_modulos_solicitados_por_usuario(self):
        for name in ('otro', '../../os', None, [], 'https://otro'):
            with self.subTest(name=name), self.assertRaises(ValueError): proveedores.obtener(name)
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'A', 'GEMINI_API_KEY': 'B', 'COMPATIBLE_API_KEY': 'C', 'ANTHROPIC_API_KEY': 'D'}):
            self.assertEqual([base.clave_api(p) for p in proveedores.CATALOGO], ['A', 'B', 'D', 'C'])

    def test_endpoint_configurado_sin_clave_query_o_destino_local(self):
        with patch.dict('os.environ', {'D2M_COMPATIBLE_ENDPOINT': ENDPOINT}):
            self.assertEqual(compatible.endpoint(), ENDPOINT)
        for url in ('http://ia.example.org/v1/chat/completions', 'https://user:secret@ia.example.org/chat/completions',
                    'https://127.0.0.1/chat/completions', 'https://10.1.2.3/chat/completions',
                    ENDPOINT+'?key=secret', ENDPOINT+'#secret', 'https://localhost/chat/completions',
                    'https://ia.example.org/a/../chat/completions'):
            with self.subTest(url=url), patch.dict('os.environ', {'D2M_COMPATIBLE_ENDPOINT': url}), self.assertRaises(base.ErrorProveedor):
                compatible.endpoint()

    def test_transporte_compatible_solo_body_cabecera_y_un_intento(self):
        envelope = {'model': 'modelo-doble', 'endpoint': ENDPOINT,
                    'body': {'model': 'modelo-doble', 'messages': []}}
        stream = MagicMock()
        stream.__enter__.return_value.read.return_value = json.dumps(respuesta_compatible('{}')).encode()
        opener = MagicMock(); opener.open.return_value = stream
        with patch.dict('os.environ', {'D2M_COMPATIBLE_ENDPOINT': ENDPOINT}), patch.object(compatible, 'build_opener', return_value=opener):
            compatible._http(envelope, 'SECRETO-DOBLE', 19)
            req = opener.open.call_args.args[0]
            self.assertEqual(json.loads(req.data), envelope['body'])
            self.assertEqual(req.full_url, ENDPOINT)
            self.assertEqual(req.get_header('Authorization'), 'Bearer SECRETO-DOBLE')
            self.assertEqual(opener.open.call_count, 1)
            self.assertEqual(opener.open.call_args.kwargs['timeout'], 19)
            for failure in (HTTPError(ENDPOINT, 429, 'SECRETO-DOBLE', {}, None), URLError('SECRETO-DOBLE')):
                opener.reset_mock(); opener.open.side_effect = failure
                with self.assertRaises(base.ErrorProveedor) as caught:
                    compatible._http(envelope, 'SECRETO-DOBLE', 19)
                self.assertNotIn('SECRETO-DOBLE', str(caught.exception))
                self.assertEqual(opener.open.call_count, 1)
                if isinstance(failure, HTTPError): self.assertEqual(caught.exception.http_status, 429)
            opener.reset_mock()
            with patch.dict('os.environ', {'D2M_COMPATIBLE_ENDPOINT': 'https://otro.example.org/v1/chat/completions'}):
                with self.assertRaises(base.ErrorProveedor): compatible._http(envelope, 'SECRETO-DOBLE', 19)
            opener.open.assert_not_called()

    def test_compatible_rechaza_herramientas_truncamiento_y_duplicados(self):
        self.assertEqual(compatible.leer_respuesta_api(respuesta_compatible('{"ok":true}')), {'ok': True})
        for changes in ({'finish_reason': 'length'}, {'message': {'role': 'assistant', 'content': '{}', 'tool_calls': [{}]}},
                        {'message': {'role': 'assistant', 'content': '{"x":1,"x":2}'}},
                        {'message': {'role': 'assistant', 'content': '{}', 'refusal': 'No'}}):
            r = respuesta_compatible('{}'); r['choices'][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(base.ErrorProveedor): compatible.leer_respuesta_api(r)


class VisionIntercambiableTests(unittest.TestCase):
    def setUp(self):
        self.fixture = vision.ProveedorWebTests('test_preparar_sin_clave_red_ni_proceso_idempotente_y_tras_reinicio')
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.env = patch.dict('os.environ', {'GEMINI_API_KEY': '', 'ANTHROPIC_API_KEY': '', 'COMPATIBLE_API_KEY': '', 'D2M_COMPATIBLE_ENDPOINT': ENDPOINT})
        self.env.start(); self.addCleanup(self.env.stop)

    def test_vision_gemini_y_compatible_no_importan_ni_acreditan_llamada_real(self):
        parsed = self.fixture.fixture.response(self.fixture.packet)
        for index, (provider, response) in enumerate((('gemini', respuesta_gemini(json.dumps(parsed))),
                                                     ('anthropic', respuesta_anthropic(json.dumps(parsed))),
                                                     ('openai_compatible', respuesta_compatible(json.dumps(parsed))))):
            with self.subTest(provider=provider):
                transport = vision.Transporte(response)
                service = ServicioProveedor(self.fixture.app, transport)
                body = self.fixture.body(clave=str(index+1)*32, proveedor=provider,
                    opciones={'max_tokens': 512, 'detalle': 'auto', 'timeout_s': 20})
                item = service.preparar(body)
                self.assertEqual(item['proveedor'], provider)
                _, done = self.fixture.run_job(service, item)
                self.assertEqual(done['estado'], 'completado_verificado')
                self.assertFalse(done['llamada_real_acreditada']); self.assertTrue(done['vigente'])
                self.assertIn('body', transport.llamadas[0][0])
                self.assertEqual(len(transport.llamadas), 1)
                self.fixture.run_job(service, item); self.assertEqual(len(transport.llamadas), 1)
                self.assertFalse(list(self.fixture.fixture.case.glob('extracciones/*')))

    def test_anthropic_esquema_simplificado_no_relaja_bbox_local(self):
        parsed = self.fixture.fixture.response(self.fixture.packet)
        parsed['candidatos'][0]['evidencia'][0]['bbox_imagen_normalizada'] = [-.1, .2, .8, .9]
        transport = vision.Transporte(respuesta_anthropic(json.dumps(parsed)))
        service = ServicioProveedor(self.fixture.app, transport)
        item = service.preparar(self.fixture.body(proveedor='anthropic',
            opciones={'max_tokens': 512, 'detalle': 'auto', 'timeout_s': 20}))
        _, done = self.fixture.run_job(service, item)
        self.assertEqual(done['estado'], 'respuesta_rechazada')
        self.assertFalse(done['llamada_real_acreditada'])
        self.assertEqual(len(transport.llamadas), 1)
        self.assertFalse(list(self.fixture.fixture.case.glob('extracciones/*')))

    def test_cambiar_proveedor_con_misma_clave_rechaza_y_destino_cambiado_invalida(self):
        # Recorrido real (sin transporte inyectado): solo Google/OpenAI para planos (ruta 201, R202-03).
        with self.assertRaises(ErrorProveedorWeb):
            ServicioProveedor(self.fixture.app).preparar(self.fixture.body(proveedor='openai_compatible'))
        # El adaptador compatible se sigue ejercitando únicamente con transporte de prueba.
        service = ServicioProveedor(self.fixture.app, vision.Transporte(respuesta_compatible('{}')))
        item = service.preparar(self.fixture.body(proveedor='openai_compatible'))
        with self.assertRaises(ErrorProveedorWeb): service.preparar(self.fixture.body(proveedor='gemini'))
        with patch.dict('os.environ', {'D2M_COMPATIBLE_ENDPOINT': 'https://otro.example.org/v1/chat/completions'}):
            self.assertFalse(service.consultar(self.fixture.caso, item['id'])['vigente'])


class ExplicacionesIntercambiablesTests(unittest.TestCase):
    def setUp(self):
        self.fixture = explicaciones.ExplicacionesTests('test_preparacion_sin_clave_red_idempotente_y_reinicio')
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        env = patch.dict('os.environ', {'GEMINI_API_KEY': '', 'ANTHROPIC_API_KEY': '', 'COMPATIBLE_API_KEY': '', 'D2M_COMPATIBLE_ENDPOINT': ENDPOINT})
        env.start(); self.addCleanup(env.stop)

    def test_explicaciones_conservan_validacion_local_y_proveedor(self):
        text = explicaciones.api()['output'][0]['content'][0]['text']
        for index, (provider, response) in enumerate((('gemini', respuesta_gemini(text)),
                                                     ('anthropic', respuesta_anthropic(text)),
                                                     ('openai_compatible', respuesta_compatible(text)))):
            with self.subTest(provider=provider):
                transport = explicaciones.Transporte(response)
                service = ServicioExplicaciones(self.fixture.app, transport)
                item = service.preparar(self.fixture.body(clave=str(index+2)*32, proveedor=provider))
                _, done = self.fixture.run_job(service, item)
                self.assertEqual(done['estado'], 'completado_llm_verificado')
                self.assertEqual(done['proveedor'], provider)
                self.assertEqual(done['modo_transporte'], 'transporte_prueba_python')
                self.assertFalse(done['aprueba_resultados'] or done['aprueba_informe'])
                self.assertIn('body', transport.llamadas[0][0])

    def test_sin_clave_del_proveedor_seleccionado_no_usa_clave_openai(self):
        service = ServicioExplicaciones(self.fixture.app)
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'CLAVE-OTRO-PROVEEDOR'}):
            item = service.preparar(self.fixture.body(proveedor='gemini'))
            _, done = self.fixture.run_job(service, item)
        self.assertEqual(done['estado'], 'contingencia')
        # Política vigente del usuario: APIs solo para revisión/extracción de planos; las explicaciones no las usan.
        self.assertEqual(done['salida']['causa'], 'api_restringida_a_revision_planos')
