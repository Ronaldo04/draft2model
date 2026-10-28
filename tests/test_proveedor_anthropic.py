"""Protocolo Anthropic Messages con transporte artificial y respuestas dobles; sin red ni API real."""
import base64
import copy
import json
import socket
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from draft2model import proveedor_anthropic as anthropic
from draft2model import proveedor_openai as base
from draft2model.revision_explicaciones import esquema_llm

CLAVE = 'CLAVE-SOLO-MOCK'


def png(ancho=4, alto=3):
    return (b'\x89PNG\r\n\x1a\n' + (13).to_bytes(4, 'big') + b'IHDR' + ancho.to_bytes(4, 'big')
            + alto.to_bytes(4, 'big') + b'\x08\x02\x00\x00\x00' + b'\x00' * 8)


def data_url(raw=None):
    return 'data:image/png;base64,' + base64.b64encode(raw or png()).decode('ascii')


def esquema_vision():
    request = {'id': 'sol-1', 'imagenes': [{'id': 'r1', 'admite_evidencia': True}]}
    return base.esquema_respuesta(request, 'a' * 64)


def peticion(**cambios):
    payload = {'model': 'fixture-claude', 'store': False, 'max_output_tokens': 4096,
               'input': [{'role': 'developer', 'content': [{'type': 'input_text', 'text': 'Instrucciones QA'}]},
                         {'role': 'user', 'content': [{'type': 'input_text', 'text': 'Imagen r1'},
                                                      {'type': 'input_image', 'detail': 'auto', 'image_url': data_url()}]}],
               'text': {'format': {'type': 'json_schema', 'name': 'draft2model_lecturas', 'strict': True,
                                   'schema': esquema_vision()}}}
    payload.update(cambios)
    return payload


def respuesta(text='{"ok":true}', **cambios):
    value = {'id': 'msg_fixture', 'type': 'message', 'role': 'assistant', 'model': 'fixture-claude',
             'content': [{'type': 'text', 'text': text}], 'stop_reason': 'end_turn', 'stop_sequence': None,
             'usage': {'input_tokens': 5, 'output_tokens': 2}}
    value.update(cambios)
    return value


class SinRed(unittest.TestCase):
    def setUp(self):
        bloqueo = MagicMock(side_effect=AssertionError('red bloqueada en pruebas'))
        for target in ('socket.create_connection', 'socket.socket.connect', 'subprocess.Popen'):
            p = patch(target, bloqueo); p.start(); self.addCleanup(p.stop)


class ConversionTests(SinRed):
    def test_cuerpo_messages_exacto_y_sin_store(self):
        original = peticion()
        intacto = copy.deepcopy(original)
        env = anthropic.convertir_peticion(original)
        self.assertEqual(original, intacto)
        self.assertEqual(set(env), {'model', 'body'})
        body = env['body']
        self.assertEqual(set(body), {'model', 'max_tokens', 'system', 'messages', 'output_config'})
        self.assertEqual(body['model'], 'fixture-claude'); self.assertEqual(body['max_tokens'], 4096)
        self.assertEqual(body['system'], 'Instrucciones QA')
        self.assertEqual(body['messages'], [{'role': 'user', 'content': [
            {'type': 'text', 'text': 'Imagen r1'},
            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png',
                                         'data': data_url().split(',', 1)[1]}}]}])
        self.assertEqual(body['output_config']['format']['type'], 'json_schema')
        self.assertNotIn('store', json.dumps(body)); self.assertNotIn('tools', body)
        self.assertEqual(anthropic.endpoint('fixture-claude'), 'https://api.anthropic.com/v1/messages')

    def test_esquema_copia_traslada_solo_lo_no_admitido(self):
        schema = esquema_vision()
        intacto = copy.deepcopy(schema)
        sent = anthropic.convertir_peticion(peticion())['body']['output_config']['format']['schema']
        self.assertEqual(schema, intacto)  # El contrato original no se modifica.
        self.assertEqual(peticion()['text']['format']['schema'], intacto)
        ev = sent['properties']['candidatos']['items']['properties']['evidencia']
        bbox = ev['items']['properties']['bbox_imagen_normalizada']
        self.assertNotIn('maxItems', bbox); self.assertNotIn('minItems', bbox)
        self.assertNotIn('minimum', bbox['items']); self.assertNotIn('maximum', bbox['items'])
        self.assertIn('minItems=4', bbox['description']); self.assertIn('maxItems=4', bbox['description'])
        self.assertIn('minimum=0', bbox['items']['description']); self.assertIn('maximum=1', bbox['items']['description'])
        self.assertEqual(ev['minItems'], 1)  # minItems 0/1 sí viaja.
        self.assertCountEqual(anthropic.restricciones_trasladadas(intacto), [
            ['/properties/candidatos/items/properties/evidencia/items/properties/bbox_imagen_normalizada', 'maxItems', 4],
            ['/properties/candidatos/items/properties/evidencia/items/properties/bbox_imagen_normalizada', 'minItems', 4],
            ['/properties/candidatos/items/properties/evidencia/items/properties/bbox_imagen_normalizada/items', 'maximum', 1],
            ['/properties/candidatos/items/properties/evidencia/items/properties/bbox_imagen_normalizada/items', 'minimum', 0]])

    def test_explicaciones_texto_sin_imagenes_y_esquema_sin_traslados(self):
        schema = esquema_llm(['ind-1'], ['frag-1'])
        payload = peticion(input=[{'role': 'developer', 'content': [{'type': 'input_text', 'text': 'Explica'}]},
                                  {'role': 'user', 'content': [{'type': 'input_text', 'text': '{"indicadores":[]}'}]}],
                           text={'format': {'type': 'json_schema', 'name': 'draft2model_explicacion', 'strict': True,
                                            'schema': schema}})
        body = anthropic.convertir_peticion(payload)['body']
        self.assertEqual(body['output_config']['format']['schema'], schema)
        self.assertEqual(anthropic.restricciones_trasladadas(schema), [])

    def test_rechaza_detalle_url_remota_herramientas_y_esquema_desconocido(self):
        def con_imagen(**item):
            p = peticion(); p['input'][1]['content'][1] = {'type': 'input_image', 'detail': 'auto', 'image_url': data_url(), **item}
            return p
        invalidos = [con_imagen(detail='low'), con_imagen(detail='high'),
                     con_imagen(image_url='https://ejemplo.invalid/a.png'),
                     con_imagen(image_url='data:image/jpeg;base64,' + base64.b64encode(png()).decode()),
                     con_imagen(image_url='data:image/png;base64,' + base64.b64encode(b'no-es-png' * 4).decode()),
                     con_imagen(image_url=data_url(png(9000, 10))),
                     con_imagen(image_url='data:image/png;base64,***'),
                     peticion(tools=[{'name': 'x'}]), peticion(tool_choice={'type': 'auto'}),
                     peticion(model='../x'), peticion(model=None), peticion(max_output_tokens=10),
                     peticion(text={'format': {'type': 'text'}})]
        p = peticion(); p['input'][1]['content'].append({'type': 'function_call', 'name': 'x'}); invalidos.append(p)
        p = peticion(); p['input'][0]['content'].append({'type': 'input_image', 'detail': 'auto', 'image_url': data_url()}); invalidos.append(p)
        p = peticion(); p['input'].append({'role': 'assistant', 'content': [{'type': 'input_text', 'text': 'x'}]}); invalidos.append(p)
        p = peticion(); p['input'].append(p['input'][0]); invalidos.append(p)  # instrucción tras contenido: no se reordena
        for clave, valor in (('pattern', '^x$'), ('oneOf', [{'type': 'string'}]), ('$ref', '#/x'), ('format', 'regex')):
            p = peticion(); p['text']['format']['schema']['properties']['candidatos']['items']['properties']['id'][clave] = valor
            invalidos.append(p)
        p = peticion(); p['text']['format']['schema']['additionalProperties'] = True; invalidos.append(p)
        for value in invalidos:
            with self.subTest(value=str(value)[:120]), self.assertRaises(base.ErrorProveedor):
                anthropic.convertir_peticion(value)

    def test_limite_de_cuerpo_local(self):
        with patch.object(anthropic, 'MAX_CUERPO', 200), self.assertRaises(base.ErrorProveedor):
            anthropic.convertir_peticion(peticion())


class TransporteTests(SinRed):
    def abrir(self, payload=None, **kw):
        stream = MagicMock(); stream.__enter__.return_value.read.return_value = payload if payload is not None else json.dumps(respuesta()).encode()
        opener = MagicMock(); opener.open.return_value = stream
        if 'side_effect' in kw:
            opener.open.side_effect = kw['side_effect']
        return opener

    def test_cabeceras_cuerpo_exacto_un_solo_intento_sin_redireccion(self):
        env = anthropic.convertir_peticion(peticion())
        opener = self.abrir()
        with patch.object(anthropic, 'build_opener', return_value=opener) as build:
            out = anthropic._http(env, CLAVE, 12)
        self.assertEqual(out['id'], 'msg_fixture')
        self.assertIsInstance(build.call_args.args[0], base._SinRedireccion)
        req = opener.open.call_args.args[0]
        self.assertEqual(req.full_url, anthropic.ENDPOINT); self.assertNotIn('CLAVE', req.full_url)
        self.assertEqual(json.loads(req.data), env['body'])
        self.assertEqual(req.get_header('X-api-key'), CLAVE)
        self.assertEqual(req.get_header('Anthropic-version'), '2023-06-01')
        self.assertIsNone(req.get_header('Authorization'))
        self.assertEqual(opener.open.call_count, 1); self.assertEqual(opener.open.call_args.kwargs['timeout'], 12)

    def test_error_http_saneado_con_estado_y_sin_secreto(self):
        env = anthropic.convertir_peticion(peticion())
        cuerpo = MagicMock(); cuerpo.read.return_value = json.dumps(
            {'type': 'error', 'error': {'type': 'rate_limit_error', 'message': 'eco ' + CLAVE}}).encode()
        exc = HTTPError(anthropic.ENDPOINT, 429, 'msg ' + CLAVE, {'x-api-key': CLAVE}, cuerpo)
        opener = self.abrir(side_effect=exc)
        with patch.object(anthropic, 'build_opener', return_value=opener), self.assertRaises(base.ErrorProveedor) as caught:
            anthropic._http(env, CLAVE, 12)
        self.assertNotIn('CLAVE', str(caught.exception)); self.assertNotIn('eco', str(caught.exception))
        self.assertEqual(caught.exception.http_status, 429); self.assertEqual(caught.exception.tipo_error, 'rate_limit_error')
        self.assertEqual(opener.open.call_count, 1)

    def test_incertidumbre_sin_http_status(self):
        env = anthropic.convertir_peticion(peticion())
        for exc in (URLError('x'), TimeoutError(), OSError()):
            opener = self.abrir(side_effect=exc)
            with self.subTest(exc=type(exc)), patch.object(anthropic, 'build_opener', return_value=opener), \
                    self.assertRaises(base.ErrorProveedor) as caught:
                anthropic._http(env, CLAVE, 12)
            self.assertFalse(hasattr(caught.exception, 'http_status')); self.assertEqual(opener.open.call_count, 1)

    def test_rechazos_previos_al_envio_y_respuestas_invalidas(self):
        env = anthropic.convertir_peticion(peticion())
        malos = []
        for timeout in (0, 181, 1.5, None):
            malos.append((env, CLAVE, timeout))
        for key in ('', '  ', 'a\nb', None):
            malos.append((env, key, 10))
        e = copy.deepcopy(env); e['body']['tools'] = []; malos.append((e, CLAVE, 10))
        e = copy.deepcopy(env); e['body']['model'] = 'otro'; malos.append((e, CLAVE, 10))
        e = copy.deepcopy(env); e['body']['messages'][0]['content'][1]['source'] = {'type': 'url', 'url': 'https://x'}; malos.append((e, CLAVE, 10))
        e = copy.deepcopy(env); e['endpoint'] = 'https://otro'; malos.append((e, CLAVE, 10))
        for args in malos:
            opener = self.abrir()
            with self.subTest(args=str(args[1:])), patch.object(anthropic, 'build_opener', return_value=opener), \
                    self.assertRaises(base.ErrorProveedor):
                anthropic._http(*args)
            self.assertFalse(opener.open.called)
        with patch.object(anthropic, 'MAX_CUERPO', 100), self.assertRaises(base.ErrorProveedor):
            anthropic._http(env, CLAVE, 10)
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'[]', b'\xff', b'x' * (anthropic.MAX_BYTES + 1)):
            opener = self.abrir(raw)
            with self.subTest(raw=raw[:12]), patch.object(anthropic, 'build_opener', return_value=opener), \
                    self.assertRaises(base.ErrorProveedor):
                anthropic._http(env, CLAVE, 10)


class RespuestaTests(SinRed):
    def test_json_final_unico_con_razonamiento_separado(self):
        value = respuesta(content=[{'type': 'thinking', 'thinking': 'no es salida', 'signature': 'sig'},
                                   {'type': 'redacted_thinking', 'data': 'opaco'},
                                   {'type': 'text', 'text': '{"ok":true}'}])
        self.assertEqual(anthropic.leer_respuesta_api(value), {'ok': True})

    def test_rechazos(self):
        values = [None, [], respuesta(type='error'), respuesta(error={'type': 'x'}), respuesta(role='user'),
                  respuesta(content='{"ok":true}'), respuesta(content=[]),
                  respuesta('[]'), respuesta('"x"'), respuesta('{"x":1,"x":2}'), respuesta('{"x":NaN}'), respuesta('no json'),
                  respuesta(content=[{'type': 'text', 'text': '{}'}, {'type': 'text', 'text': '{}'}]),
                  respuesta(content=[{'type': 'tool_use', 'id': 't', 'name': 'x', 'input': {}}], stop_reason='end_turn'),
                  respuesta(content=[{'type': 'text', 'text': '{}', 'citations': [{'x': 1}]}]),
                  respuesta(content=[{'type': 'thinking', 'thinking': '{"ok":true}'}]),
                  respuesta(content=[{'type': 'thinking', 'thinking': 1}, {'type': 'text', 'text': '{}'}]),
                  respuesta(content=[{'type': 'fallback'}, {'type': 'text', 'text': '{}'}]),
                  respuesta(content=[{'type': 'text', 'text': '{}', 'extra': 1}])]
        for reason in ('refusal', 'max_tokens', 'tool_use', 'pause_turn', 'stop_sequence',
                       'model_context_window_exceeded', None):
            values.append(respuesta(stop_reason=reason))
        for value in values:
            with self.subTest(value=str(value)[:100]), self.assertRaises(base.ErrorProveedor):
                anthropic.leer_respuesta_api(value)


if __name__ == '__main__':
    unittest.main()
