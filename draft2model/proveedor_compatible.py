"""Protocolo Chat Completions para servidores configurados por el operador local.

No convierte una clave en prueba de capacidades. Exige imágenes y JSON Schema
compatibles; un rechazo no relaja el contrato ni cambia de proveedor.
"""
import copy
import ipaddress
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from . import proveedor_openai as base


def _validar_endpoint(url):
    if not isinstance(url, str) or len(url) > 2048 or any(c.isspace() for c in url):
        raise base.ErrorProveedor('Configura D2M_COMPATIBLE_ENDPOINT como URL HTTPS de Chat Completions.')
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ''
        port = parsed.port
    except ValueError:
        raise base.ErrorProveedor('Endpoint compatible inválido.') from None
    if (parsed.scheme != 'https' or not host or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or port not in (None, 443)
            or not parsed.path.endswith('/chat/completions') or '..' in parsed.path or '%' in parsed.path
            or host == 'localhost' or host.endswith(('.localhost', '.local'))):
        raise base.ErrorProveedor('Endpoint compatible requiere HTTPS público, sin credenciales, query ni redirecciones.')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if '.' not in host or not re.fullmatch(r'[A-Za-z0-9.-]+', host):
            raise base.ErrorProveedor('Host compatible inválido.') from None
    else:
        if not address.is_global:
            raise base.ErrorProveedor('No se admiten direcciones privadas o locales para el proveedor compatible.')
    return url


def endpoint(modelo=None):
    return _validar_endpoint(os.environ.get('D2M_COMPATIBLE_ENDPOINT', '').strip())


def convertir_peticion(payload):
    url = endpoint()
    messages = []
    for message in payload['input']:
        role = {'developer': 'system', 'user': 'user'}.get(message.get('role'))
        if role is None:
            raise base.ErrorProveedor('Rol no admitido por Chat Completions.')
        parts = []
        for part in message['content']:
            if part.get('type') == 'input_text' and isinstance(part.get('text'), str):
                parts.append({'type': 'text', 'text': part['text']})
            elif (part.get('type') == 'input_image' and role == 'user'
                  and isinstance(part.get('image_url'), str) and part['image_url'].startswith('data:image/png;base64,')
                  and part.get('detail') in ('low', 'high', 'auto')):
                parts.append({'type': 'image_url', 'image_url': {'url': part['image_url'], 'detail': part['detail']}})
            else:
                raise base.ErrorProveedor('Contenido no admitido por Chat Completions.')
        messages.append({'role': role, 'content': parts})
    fmt = payload['text']['format']
    if fmt.get('type') != 'json_schema' or not isinstance(fmt.get('schema'), dict):
        raise base.ErrorProveedor('Se requiere JSON Schema en el proveedor compatible.')
    field = os.environ.get('D2M_COMPATIBLE_TOKEN_FIELD', 'max_tokens')
    if field not in ('max_tokens', 'max_completion_tokens'):
        raise base.ErrorProveedor('D2M_COMPATIBLE_TOKEN_FIELD no admitido.')
    body = {'model': payload['model'], 'messages': messages, field: payload['max_output_tokens'],
            'n': 1, 'stream': False, 'response_format': {'type': 'json_schema', 'json_schema': {
                'name': fmt['name'], 'strict': True, 'schema': copy.deepcopy(fmt['schema'])}}}
    return {'model': payload['model'], 'endpoint': url, 'body': body}


def _http(payload, key, timeout):
    if not isinstance(payload, dict) or set(payload) != {'model', 'endpoint', 'body'}:
        raise base.ErrorProveedor('Envoltorio compatible inválido.')
    url = _validar_endpoint(payload['endpoint'])
    if url != endpoint() or not isinstance(payload['body'], dict) or payload['body'].get('model') != payload['model']:
        raise base.ErrorProveedor('El destino o el modelo configurados cambiaron; prepara otro plan.')
    if type(timeout) is not int or not 1 <= timeout <= 180:
        raise base.ErrorProveedor('Timeout no admitido.')
    if not isinstance(key, str) or not key.strip() or any(c in key for c in '\r\n'):
        raise base.ErrorProveedor('Credencial compatible ausente o inválida.')
    data = base._json(payload['body'])
    if len(data) > base.MAX_BYTES:
        raise base.ErrorProveedor('Petición compatible demasiado grande.')
    request = Request(url, data=data, method='POST', headers={
        'Authorization': 'Bearer '+key, 'Content-Type': 'application/json'})
    try:
        with build_opener(base._SinRedireccion()).open(request, timeout=timeout) as response:
            raw = response.read(base.MAX_BYTES + 1)
    except HTTPError as exc:
        error = base.ErrorProveedor(f'Proveedor compatible devolvió HTTP {exc.code}; no se reintentó.')
        error.http_status = exc.code
        raise error from None
    except (URLError, TimeoutError, OSError):
        raise base.ErrorProveedor('Envío compatible no confirmado; consumo incierto, sin reintento.') from None
    if len(raw) > base.MAX_BYTES:
        raise base.ErrorProveedor('Respuesta compatible demasiado grande.')
    try:
        result = base._loads(raw.decode('utf-8'))
    except UnicodeDecodeError:
        raise base.ErrorProveedor('Respuesta compatible no UTF-8.') from None
    if not isinstance(result, dict):
        raise base.ErrorProveedor('Respuesta compatible inválida.')
    return result


def leer_respuesta_api(response):
    if not isinstance(response, dict) or response.get('error'):
        raise base.ErrorProveedor('Error del proveedor compatible.')
    choices = response.get('choices')
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        raise base.ErrorProveedor('Se requiere una única respuesta compatible.')
    choice = choices[0]
    message = choice.get('message')
    if (choice.get('finish_reason') != 'stop' or not isinstance(message, dict)
            or message.get('role') != 'assistant' or message.get('refusal')
            or message.get('tool_calls') or message.get('function_call')
            or not isinstance(message.get('content'), str)):
        raise base.ErrorProveedor('Respuesta compatible incompleta, rechazada o con herramientas.')
    result = base._loads(message['content'])
    if not isinstance(result, dict):
        raise base.ErrorProveedor('Salida compatible no es objeto JSON.')
    return result
