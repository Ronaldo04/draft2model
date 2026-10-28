"""Protocolo Gemini y ciclo de plan con transporte artificial; sin red real."""
import copy
import json
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError

from draft2model import proveedor_gemini as gemini
from draft2model import proveedor_openai as base
from tests import test_proveedor_openai as fixture_openai


def respuesta(text='{"ok":true}', **changes):
    return {'candidates': [{'finishReason': 'STOP', 'content': {'role': 'model', 'parts': [{'text': text}]}}],
            'usageMetadata': {'promptTokenCount': 5, 'candidatesTokenCount': 2},
            'modelVersion': 'fixture-gemini', 'responseId': 'fixture-response', **changes}


class GeminiProtocoloTests(unittest.TestCase):
    def test_parse_final_y_pensamiento_separados(self):
        source = respuesta()
        source['candidates'][0]['content']['parts'].insert(0, {'text': 'No es la salida JSON.', 'thought': True})
        self.assertEqual(gemini.leer_respuesta_api(source), {'ok': True})

    def test_rechaza_parcial_multiple_bloqueo_herramienta_y_json_ambiguo(self):
        values = [respuesta(candidates=[]), respuesta(candidates=respuesta()['candidates'] * 2),
                  respuesta(promptFeedback={'blockReason': 'SAFETY'}), respuesta('[]'),
                  respuesta('{"x":1,"x":2}'), respuesta('{"x":NaN}')]
        for reason in ('MAX_TOKENS', 'SAFETY', None):
            value = respuesta(); value['candidates'][0]['finishReason'] = reason; values.append(value)
        for part in ({'functionCall': {'name': 'tool'}}, {'text': '{}', 'inlineData': {}},
                     {'text': '{}', 'thought': 'false'}):
            value = respuesta(); value['candidates'][0]['content']['parts'] = [part]; values.append(value)
        for value in values:
            with self.subTest(value=value), self.assertRaises(base.ErrorProveedor):
                gemini.leer_respuesta_api(value)

    def test_endpoint_no_admite_destino_o_query_inyectados(self):
        self.assertEqual(gemini.endpoint('models/fixture-gemini'), gemini.endpoint('fixture-gemini'))
        for name in ('../secreto', 'x?key=secret', 'https://otro', 'models/x/y', '', None):
            with self.subTest(name=name), self.assertRaises(base.ErrorProveedor): gemini.endpoint(name)

    def test_http_clave_solo_cabecera_body_exacto_y_error_sin_secreto(self):
        envelope = {'model': 'fixture-gemini', 'body': {'contents': [{'parts': [{'text': 'QA'}]}]}}
        stream = MagicMock(); stream.__enter__.return_value.read.return_value = json.dumps(respuesta()).encode()
        opener = MagicMock(); opener.open.return_value = stream
        with patch.object(gemini, 'build_opener', return_value=opener):
            gemini._http(envelope, 'CLAVE-SOLO-MOCK', 12)
        req = opener.open.call_args.args[0]
        self.assertNotIn('CLAVE', req.full_url)
        self.assertEqual(json.loads(req.data), envelope['body'])
        self.assertEqual(req.get_header('X-goog-api-key'), 'CLAVE-SOLO-MOCK')
        self.assertEqual(opener.open.call_count, 1)
        opener.open.side_effect = HTTPError(req.full_url, 429, 'CLAVE-SOLO-MOCK', {}, None)
        with patch.object(gemini, 'build_opener', return_value=opener), self.assertRaises(base.ErrorProveedor) as caught:
            gemini._http(envelope, 'CLAVE-SOLO-MOCK', 12)
        self.assertNotIn('CLAVE', str(caught.exception)); self.assertEqual(caught.exception.http_status, 429)


class GeminiVisionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_openai.ProveedorOpenAITests('test_prepare_no_key_no_network_and_explicit_model')
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)

    def preparar(self):
        return base.preparar_plan(self.fixture.manifest, self.fixture.packet,
                                  modelo='fixture-gemini', detalle='auto', proveedor='gemini')

    def test_preparacion_local_modelo_cuerpo_esquema_y_proveedor_exacto(self):
        with patch.dict('os.environ', {'GEMINI_API_KEY': ''}), patch.object(gemini, '_http') as http:
            path = self.preparar()
            payload, summary = base.preparar_peticion(self.fixture.manifest, self.fixture.packet,
                modelo='fixture-gemini', proveedor='gemini', detalle='auto')
        self.assertFalse(http.called)
        self.assertIn('planes_gemini', path.parts)
        self.assertEqual(summary['proveedor'], 'gemini'); self.assertIsNone(summary['store'])
        self.assertEqual(payload['body']['generationConfig']['responseMimeType'], 'application/json')
        self.assertIn('responseJsonSchema', payload['body']['generationConfig'])
        self.assertNotIn('store', payload['body'])
        parts = payload['body']['contents'][0]['parts']
        self.assertEqual(sum('inlineData' in part for part in parts), 2)
        self.assertEqual(summary['peticion_sha256'], base._hash(base._json(payload)))
        with self.assertRaises(base.ErrorProveedor):
            base.preparar_peticion(self.fixture.manifest, self.fixture.packet,
                                  modelo='fixture-gemini', proveedor='gemini', detalle='high')

    def test_plan_sin_clave_no_reserva_y_transporte_doble_no_reenvia(self):
        plan = self.preparar()
        with patch.dict('os.environ', {'GEMINI_API_KEY': '', 'OPENAI_API_KEY': 'OTRA-CLAVE'}), self.assertRaises(base.ErrorProveedor):
            base.ejecutar_plan(self.fixture.manifest, plan, autorizar_envio=True)
        self.assertFalse((plan.parent/'intento.json').exists())
        text = self.fixture.response()['output'][0]['content'][0]['text']
        with patch.dict('os.environ', {'GEMINI_API_KEY': ''}):
            report_path = base.ejecutar_plan(self.fixture.manifest, plan, autorizar_envio=True,
                    transporte=lambda payload, key, timeout: respuesta(text), importar_automaticamente=False)
        report = json.loads(report_path.read_bytes())
        self.assertEqual(report['estado'], 'simulacion_completada'); self.assertTrue(report['simulada'])
        self.assertEqual(report['modelo_devuelto'], 'fixture-gemini')
        self.assertIn('intentos_gemini', report_path.parts); self.assertIsNone(report['version_importada'])
        with self.assertRaises(base.ErrorProveedor):
            base.ejecutar_plan(self.fixture.manifest, plan, autorizar_envio=True,
                              transporte=lambda *args: self.fail('No reenviar'))
