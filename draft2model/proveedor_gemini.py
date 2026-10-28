"""Adaptador generateContent sin SDK ni reintentos.

La petición local es {model, body}: su hash incluye el modelo y el cuerpo.
Solo body se transmite al endpoint fijo derivado del modelo. No atribuye a
Gemini la opción store=false de OpenAI ni supone equivalencia de resolución.
"""
from __future__ import annotations

import base64
import copy
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from . import proveedor_openai as base

ENDPOINT = 'https://generativelanguage.googleapis.com/v1beta/models/'
ErrorProveedor = base.ErrorProveedor
MAX_BYTES = base.MAX_BYTES


def endpoint(modelo):
    if not isinstance(modelo, str) or re.fullmatch(r'(?:models/)?[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', modelo) is None:
        raise ErrorProveedor('Identificador de modelo Gemini inválido.')
    return ENDPOINT + modelo.removeprefix('models/') + ':generateContent'


def convertir_peticion(payload):
    """Traduce la solicitud local común, nunca una respuesta ni una aprobación."""
    if not isinstance(payload, dict):
        raise ErrorProveedor('Petición Gemini inválida.')
    endpoint(payload.get('model'))
    tokens = payload.get('max_output_tokens')
    if type(tokens) is not int or not 256 <= tokens <= 16384:
        raise ErrorProveedor('Límite de salida Gemini inválido.')
    messages = payload.get('input')
    if not isinstance(messages, list) or not messages:
        raise ErrorProveedor('Falta contenido para Gemini.')
    system, contents = [], []
    for message in messages:
        if not isinstance(message, dict) or message.get('role') not in ('developer', 'user'):
            raise ErrorProveedor('Rol no admitido para Gemini.')
        parts = []
        if not isinstance(message.get('content'), list) or not message['content']:
            raise ErrorProveedor('Contenido vacío para Gemini.')
        for item in message['content']:
            if not isinstance(item, dict):
                raise ErrorProveedor('Parte de entrada inválida.')
            if item.get('type') == 'input_text' and isinstance(item.get('text'), str):
                parts.append({'text': item['text']})
            elif item.get('type') == 'input_image' and message['role'] == 'user':
                if item.get('detail') != 'auto':
                    raise ErrorProveedor('Gemini requiere detalle auto; low/high no tienen equivalencia declarada.')
                url = item.get('image_url')
                prefix = 'data:image/png;base64,'
                if not isinstance(url, str) or not url.startswith(prefix):
                    raise ErrorProveedor('Gemini solo admite las imágenes PNG locales comprobadas.')
                data = url[len(prefix):]
                try:
                    if not base64.b64decode(data, validate=True):
                        raise ValueError('vacía')
                except (ValueError, base64.binascii.Error):
                    raise ErrorProveedor('Imagen PNG codificada inválida.') from None
                parts.append({'inlineData': {'mimeType': 'image/png', 'data': data}})
            else:
                raise ErrorProveedor('Parte no admitida; no se ejecutan herramientas.')
        if message['role'] == 'developer':
            system.extend(parts)
        else:
            contents.append({'role': 'user', 'parts': parts})
    fmt = payload.get('text', {}).get('format', {})
    if fmt.get('type') != 'json_schema' or not isinstance(fmt.get('schema'), dict):
        raise ErrorProveedor('Gemini requiere el esquema JSON explícito del proyecto.')
    body = {'contents': contents, 'generationConfig': {
        'candidateCount': 1, 'maxOutputTokens': tokens,
        'responseMimeType': 'application/json', 'responseJsonSchema': copy.deepcopy(fmt['schema'])}}
    if system:
        body['systemInstruction'] = {'parts': system}
    result = {'model': payload['model'], 'body': body}
    if not contents or len(base._json(result)) > MAX_BYTES:
        raise ErrorProveedor('Petición Gemini vacía o demasiado grande.')
    return result


def _http(payload, key, timeout):
    if not isinstance(payload, dict) or set(payload) != {'model', 'body'} or not isinstance(payload['body'], dict):
        raise ErrorProveedor('Envoltorio Gemini inválido.')
    url = endpoint(payload['model'])
    if type(timeout) is not int or not 1 <= timeout <= 180:
        raise ErrorProveedor('Timeout Gemini inválido.')
    if not isinstance(key, str) or not key.strip() or any(c in key for c in '\r\n'):
        raise ErrorProveedor('Credencial Gemini ausente o de formato inválido.')
    data = base._json(payload['body'])
    if len(data) > MAX_BYTES:
        raise ErrorProveedor('Petición Gemini demasiado grande.')
    request = Request(url, data=data, method='POST',
                      headers={'x-goog-api-key': key, 'Content-Type': 'application/json'})
    try:
        with build_opener(base._SinRedireccion()).open(request, timeout=timeout) as response:
            raw = response.read(MAX_BYTES + 1)
    except HTTPError as exc:
        error = ErrorProveedor(f'Gemini devolvió HTTP {exc.code}; no se reintentó.')
        error.http_status = exc.code
        raise error from None
    except (URLError, TimeoutError, OSError):
        raise ErrorProveedor('No se confirmó la respuesta de Gemini; el consumo puede ser incierto. No se reintentó.') from None
    if len(raw) > MAX_BYTES:
        raise ErrorProveedor('Respuesta Gemini demasiado grande.')
    try:
        result = base._loads(raw.decode('utf-8'))
    except UnicodeDecodeError:
        raise ErrorProveedor('Respuesta Gemini no UTF-8.') from None
    if not isinstance(result, dict):
        raise ErrorProveedor('Respuesta Gemini inválida.')
    return result


def leer_respuesta_api(response):
    if not isinstance(response, dict) or response.get('error'):
        raise ErrorProveedor('Gemini rechazó la petición o no produjo una respuesta utilizable.')
    feedback = response.get('promptFeedback', {})
    if not isinstance(feedback, dict) or feedback.get('blockReason'):
        raise ErrorProveedor('Gemini bloqueó el prompt o devolvió información de bloqueo inválida.')
    candidates = response.get('candidates')
    if not isinstance(candidates, list) or len(candidates) != 1:
        raise ErrorProveedor('Se requiere un único candidato Gemini.')
    candidate = candidates[0]
    if not isinstance(candidate, dict) or candidate.get('finishReason') != 'STOP':
        raise ErrorProveedor('Gemini no terminó la salida; no se importa texto parcial.')
    ratings = candidate.get('safetyRatings', [])
    if not isinstance(ratings, list) or any(not isinstance(r, dict) or r.get('blocked') for r in ratings):
        raise ErrorProveedor('Candidato Gemini bloqueado.')
    content = candidate.get('content')
    if not isinstance(content, dict) or content.get('role') != 'model' or not isinstance(content.get('parts'), list):
        raise ErrorProveedor('Contenido Gemini inválido.')
    texts = []
    for part in content['parts']:
        if (not isinstance(part, dict) or set(part) - {'text', 'thought', 'thoughtSignature'}
                or not isinstance(part.get('text'), str)
                or ('thought' in part and type(part['thought']) is not bool)
                or ('thoughtSignature' in part and not isinstance(part['thoughtSignature'], str))):
            raise ErrorProveedor('Parte Gemini inesperada; no se ejecutan herramientas.')
        if part.get('thought') is not True:
            texts.append(part['text'])
    if len(texts) != 1:
        raise ErrorProveedor('Se requiere un único texto JSON final de Gemini.')
    parsed = base._loads(texts[0])
    if not isinstance(parsed, dict):
        raise ErrorProveedor('La respuesta final Gemini no es un objeto JSON.')
    return parsed
