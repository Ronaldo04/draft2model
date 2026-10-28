"""Adaptador Anthropic Messages sin SDK ni reintentos.

La petición local es {model, body}: su hash incluye el modelo y el cuerpo y
solo body se transmite al endpoint fijo. La salida usa output_config.format
(json_schema). Las restricciones que la API no aplica se trasladan a la
descripción de una COPIA del esquema; el contrato original no se modifica y la
validación local del proyecto sigue siendo la que decide. No atribuye a
Anthropic la opción store=false de OpenAI ni equivalencias de resolución.
"""
from __future__ import annotations

import base64
import copy
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from . import proveedor_openai as base

ENDPOINT = 'https://api.anthropic.com/v1/messages'
VERSION_API = '2023-06-01'
ErrorProveedor = base.ErrorProveedor
MAX_BYTES = base.MAX_BYTES
# Límites locales conservadores alineados con la documentación pública de
# Messages/visión; no se verificaron con una cuenta ni con la API real.
MAX_CUERPO = 32_000_000
MAX_IMAGEN = 5*1024*1024
MAX_LADO_PX = 8000
MAX_IMAGENES = 100

_CLAVES_PETICION = {'model', 'store', 'max_output_tokens', 'input', 'text'}
_CLAVES_CUERPO = {'model', 'max_tokens', 'system', 'messages', 'output_config'}
_PNG = b'\x89PNG\r\n\x1a\n'
# Palabras clave que se envían sin cambios.
_ESQUEMA_ADMITIDO = {'type', 'properties', 'required', 'additionalProperties', 'items',
                     'enum', 'const', 'anyOf', 'allOf', 'description', 'title', 'format'}
_FORMATOS = {'date-time', 'time', 'date', 'duration', 'email', 'hostname', 'uri', 'ipv4', 'ipv6', 'uuid'}
# Restricciones no aplicadas por la API: se describen en la copia y se validan localmente.
_ESQUEMA_TRASLADADO = ('minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum', 'multipleOf',
                       'minLength', 'maxLength', 'maxItems', 'minItems')


def endpoint(modelo):
    if not isinstance(modelo, str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', modelo) is None:
        raise ErrorProveedor('Identificador de modelo Anthropic inválido.')
    return ENDPOINT


def _trasladable(clave, valor):
    # minItems 0 y 1 están admitidos; otros valores se describen y validan localmente.
    return clave in _ESQUEMA_TRASLADADO and not (clave == 'minItems' and valor in (0, 1))


def restricciones_trasladadas(esquema):
    """Lista [ruta, palabra, valor] de lo que no viaja como restricción; no modifica el esquema."""
    salida = []

    def visitar(nodo, ruta):
        if isinstance(nodo, dict):
            for clave in sorted(nodo):
                valor = nodo[clave]
                if _trasladable(clave, valor):
                    salida.append([ruta or '/', clave, valor])
                elif clave == 'properties' and isinstance(valor, dict):
                    for nombre in sorted(valor):
                        visitar(valor[nombre], ruta+'/properties/'+nombre)
                elif clave == 'items':
                    visitar(valor, ruta+'/items')
                elif clave in ('anyOf', 'allOf') and isinstance(valor, list):
                    for i, sub in enumerate(valor):
                        visitar(sub, ruta+'/'+clave+'/'+str(i))
    visitar(esquema, '')
    return salida


def _esquema_anthropic(esquema):
    """Copia profunda transformada; rechaza palabras clave desconocidas en vez de relajarlas."""
    copia = copy.deepcopy(esquema)

    def visitar(nodo, ruta):
        if not isinstance(nodo, dict):
            raise ErrorProveedor('Nodo JSON Schema inválido en '+(ruta or '/')+'.')
        movidas = []
        for clave in list(nodo):
            valor = nodo[clave]
            if _trasladable(clave, valor):
                movidas.append(clave+'='+json.dumps(valor, ensure_ascii=False))
                del nodo[clave]
            elif clave not in _ESQUEMA_ADMITIDO and not (clave == 'minItems' and valor in (0, 1)):
                raise ErrorProveedor('Palabra JSON Schema no admitida por el adaptador Anthropic: '+str(clave)+'.')
        if 'format' in nodo and nodo['format'] not in _FORMATOS:
            raise ErrorProveedor('Formato JSON Schema no admitido por Anthropic.')
        tipo = nodo.get('type')
        if tipo == 'object' or 'properties' in nodo:
            if nodo.get('additionalProperties') is not False:
                raise ErrorProveedor('Anthropic exige additionalProperties false; no se añade en silencio.')
            props = nodo.get('properties', {})
            if not isinstance(props, dict):
                raise ErrorProveedor('properties inválido.')
            for nombre, sub in props.items():
                visitar(sub, ruta+'/properties/'+nombre)
        elif 'additionalProperties' in nodo:
            raise ErrorProveedor('additionalProperties fuera de un objeto.')
        if 'items' in nodo:
            visitar(nodo['items'], ruta+'/items')
        for clave in ('anyOf', 'allOf'):
            if clave in nodo:
                if not isinstance(nodo[clave], list) or not nodo[clave]:
                    raise ErrorProveedor(clave+' inválido.')
                for i, sub in enumerate(nodo[clave]):
                    visitar(sub, ruta+'/'+clave+'/'+str(i))
        if movidas:
            nota = 'Restricciones validadas localmente (no aplicadas por la API): '+'; '.join(movidas)+'.'
            previa = nodo.get('description')
            if previa is not None and not isinstance(previa, str):
                raise ErrorProveedor('description inválida.')
            nodo['description'] = (previa+' ' if previa else '')+nota
    visitar(copia, '')
    return copia


def _imagen(item):
    if item.get('detail') != 'auto':
        raise ErrorProveedor('Anthropic requiere detalle auto; low/high no tienen equivalencia declarada.')
    url = item.get('image_url')
    prefix = 'data:image/png;base64,'
    if not isinstance(url, str) or not url.startswith(prefix):
        raise ErrorProveedor('Anthropic solo admite las imágenes PNG locales comprobadas; no URL remotas.')
    data = url[len(prefix):]
    try:
        raw = base64.b64decode(data, validate=True)
    except (ValueError, base64.binascii.Error):
        raise ErrorProveedor('Imagen PNG codificada inválida.') from None
    if len(raw) < 24 or not raw.startswith(_PNG) or raw[12:16] != b'IHDR':
        raise ErrorProveedor('La imagen declarada PNG no tiene cabecera PNG.')
    if len(raw) > MAX_IMAGEN:
        raise ErrorProveedor('Imagen por encima del límite local de 5 MiB para Anthropic.')
    ancho, alto = int.from_bytes(raw[16:20], 'big'), int.from_bytes(raw[20:24], 'big')
    if not (0 < ancho <= MAX_LADO_PX and 0 < alto <= MAX_LADO_PX):
        raise ErrorProveedor('Dimensiones de imagen fuera del límite local para Anthropic.')
    return {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': data}}, (ancho, alto)


def convertir_peticion(payload):
    """Traduce la solicitud local común, nunca una respuesta ni una aprobación."""
    if not isinstance(payload, dict) or set(payload) - _CLAVES_PETICION:
        raise ErrorProveedor('Petición Anthropic inválida; no se admiten herramientas ni campos ajenos.')
    endpoint(payload.get('model'))
    tokens = payload.get('max_output_tokens')
    if type(tokens) is not int or not 256 <= tokens <= 16384:
        raise ErrorProveedor('Límite de salida Anthropic inválido.')
    messages = payload.get('input')
    if not isinstance(messages, list) or not messages:
        raise ErrorProveedor('Falta contenido para Anthropic.')
    system, content, dims = [], [], []
    for message in messages:
        if not isinstance(message, dict) or set(message) != {'role', 'content'} or message['role'] not in ('developer', 'user'):
            raise ErrorProveedor('Rol no admitido para Anthropic.')
        if message['role'] == 'developer' and content:
            raise ErrorProveedor('Las instrucciones deben preceder al contenido; no se reordenan.')
        if not isinstance(message['content'], list) or not message['content']:
            raise ErrorProveedor('Contenido vacío para Anthropic.')
        for item in message['content']:
            if not isinstance(item, dict):
                raise ErrorProveedor('Parte de entrada inválida.')
            if item.get('type') == 'input_text' and set(item) == {'type', 'text'} and isinstance(item['text'], str):
                if not item['text']:
                    raise ErrorProveedor('Texto vacío para Anthropic.')
                (system if message['role'] == 'developer' else content).append({'type': 'text', 'text': item['text']})
            elif item.get('type') == 'input_image' and message['role'] == 'user' and set(item) == {'type', 'detail', 'image_url'}:
                block, size = _imagen(item)
                content.append(block); dims.append(size)
            else:
                raise ErrorProveedor('Parte no admitida; no se ejecutan herramientas.')
    if not content or not system:
        raise ErrorProveedor('Anthropic requiere instrucciones y contenido de usuario.')
    if len(dims) > MAX_IMAGENES or (len(dims) > 20 and any(max(d) > 2000 for d in dims)):
        raise ErrorProveedor('Demasiadas imágenes o dimensiones no admitidas para Anthropic.')
    text = payload.get('text')
    fmt = text.get('format') if isinstance(text, dict) and set(text) == {'format'} else None
    if (not isinstance(fmt, dict) or fmt.get('type') != 'json_schema' or not isinstance(fmt.get('schema'), dict)
            or fmt.get('strict', True) is not True or set(fmt) - {'type', 'name', 'strict', 'schema'}):
        raise ErrorProveedor('Anthropic requiere el esquema JSON explícito del proyecto.')
    body = {'model': payload['model'], 'max_tokens': tokens,
            'system': '\n\n'.join(b['text'] for b in system),
            'messages': [{'role': 'user', 'content': content}],
            'output_config': {'format': {'type': 'json_schema', 'schema': _esquema_anthropic(fmt['schema'])}}}
    result = {'model': payload['model'], 'body': body}
    if len(base._json(body)) > MAX_CUERPO:
        raise ErrorProveedor('Petición Anthropic demasiado grande para el límite local.')
    return result


def _validar_cuerpo(body, modelo):
    if (not isinstance(body, dict) or set(body) != _CLAVES_CUERPO or body['model'] != modelo
            or not isinstance(body['system'], str) or type(body['max_tokens']) is not int):
        raise ErrorProveedor('Cuerpo Anthropic inválido; no se envían herramientas ni campos ajenos.')
    msgs = body['messages']
    if not isinstance(msgs, list) or len(msgs) != 1 or not isinstance(msgs[0], dict) or msgs[0].get('role') != 'user':
        raise ErrorProveedor('Mensajes Anthropic inválidos.')
    for block in msgs[0].get('content') or [None]:
        ok = isinstance(block, dict) and (
            (block.get('type') == 'text' and set(block) == {'type', 'text'}) or
            (block.get('type') == 'image' and isinstance(block.get('source'), dict)
             and block['source'].get('type') == 'base64' and block['source'].get('media_type') == 'image/png'))
        if not ok:
            raise ErrorProveedor('Bloque Anthropic no admitido; sin URL remotas ni herramientas.')
    fmt = body['output_config']
    if not isinstance(fmt, dict) or set(fmt) != {'format'} or fmt['format'].get('type') != 'json_schema':
        raise ErrorProveedor('Formato de salida Anthropic inválido.')


def _http(payload, key, timeout):
    if not isinstance(payload, dict) or set(payload) != {'model', 'body'}:
        raise ErrorProveedor('Envoltorio Anthropic inválido.')
    url = endpoint(payload['model'])
    _validar_cuerpo(payload['body'], payload['model'])
    if type(timeout) is not int or not 1 <= timeout <= 180:
        raise ErrorProveedor('Timeout Anthropic inválido.')
    if not isinstance(key, str) or not key.strip() or any(c in key for c in '\r\n'):
        raise ErrorProveedor('Credencial Anthropic ausente o de formato inválido.')
    data = base._json(payload['body'])
    if len(data) > MAX_CUERPO:
        raise ErrorProveedor('Petición Anthropic demasiado grande.')
    request = Request(url, data=data, method='POST', headers={
        'x-api-key': key, 'anthropic-version': VERSION_API, 'Content-Type': 'application/json'})
    try:
        with build_opener(base._SinRedireccion()).open(request, timeout=timeout) as response:
            raw = response.read(MAX_BYTES + 1)
    except HTTPError as exc:
        # Solo el código y un tipo de error con forma de identificador; nunca cuerpo, cabeceras ni clave.
        tipo = None
        try:
            detalle = json.loads(exc.read(65536).decode('utf-8'))
            candidato = detalle.get('error', {}).get('type')
            if candidato in ('invalid_request_error', 'authentication_error', 'permission_error', 'not_found_error',
                             'request_too_large', 'rate_limit_error', 'api_error', 'overloaded_error'):
                tipo = candidato
        except Exception:
            pass
        error = ErrorProveedor(f'Anthropic devolvió HTTP {exc.code}'+(f' ({tipo})' if tipo else '')+'; no se reintentó.')
        error.http_status = exc.code
        error.tipo_error = tipo
        raise error from None
    except (URLError, TimeoutError, OSError):
        raise ErrorProveedor('No se confirmó la respuesta de Anthropic; el consumo puede ser incierto. No se reintentó.') from None
    if len(raw) > MAX_BYTES:
        raise ErrorProveedor('Respuesta Anthropic demasiado grande.')
    try:
        result = base._loads(raw.decode('utf-8'))
    except UnicodeDecodeError:
        raise ErrorProveedor('Respuesta Anthropic no UTF-8.') from None
    if not isinstance(result, dict):
        raise ErrorProveedor('Respuesta Anthropic inválida.')
    return result


def leer_respuesta_api(response):
    if not isinstance(response, dict) or response.get('type') != 'message' or response.get('error'):
        raise ErrorProveedor('Anthropic rechazó la petición o no produjo un mensaje utilizable.')
    if response.get('role') != 'assistant':
        raise ErrorProveedor('Mensaje Anthropic sin rol assistant.')
    if response.get('stop_reason') != 'end_turn':
        # refusal, max_tokens, tool_use, pause_turn, stop_sequence u otro: no se importa salida parcial.
        raise ErrorProveedor('Anthropic no terminó la salida (stop_reason distinto de end_turn); no se importa.')
    blocks = response.get('content')
    if not isinstance(blocks, list):
        raise ErrorProveedor('Contenido Anthropic inválido.')
    texts = []
    for block in blocks:
        kind = block.get('type') if isinstance(block, dict) else None
        if kind == 'text' and set(block) <= {'type', 'text', 'citations'} and isinstance(block.get('text'), str) \
                and block.get('citations') is None:
            texts.append(block['text'])
        elif kind == 'thinking' and set(block) <= {'type', 'thinking', 'signature'} \
                and isinstance(block.get('thinking'), str) and isinstance(block.get('signature', ''), str):
            continue  # Razonamiento separado: no es salida ni se ejecuta.
        elif kind == 'redacted_thinking' and set(block) == {'type', 'data'} and isinstance(block['data'], str):
            continue
        else:
            raise ErrorProveedor('Bloque Anthropic inesperado; no se ejecutan herramientas.')
    if len(texts) != 1:
        raise ErrorProveedor('Se requiere un único texto JSON final de Anthropic.')
    parsed = base._loads(texts[0])
    if not isinstance(parsed, dict):
        raise ErrorProveedor('La respuesta final Anthropic no es un objeto JSON.')
    return parsed
