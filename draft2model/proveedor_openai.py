"""Cliente Responses API de OpenAI: preparación local y un envío explícito.

Modelo configurable, sin SDK, sin reintentos automáticos ni claves en archivos.
Las pruebas inyectan un transporte simulado y no consumen servicios externos.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

from .entrada_vision import (_inside, _json, _publish, cargar_paquete, registrar_respuesta)
from .extraccion_preliminar import cargar_extraccion
from .gestion_extraccion import importar_extraccion
from .ingreso import file_hash

ENDPOINT = 'https://api.openai.com/v1/responses'
VERSION = '0.1.0'
MAX_IMAGENES = 16
MAX_BYTES = 40*1024*1024  # Límite de este proyecto, no una tarifa o límite universal de API.


class ErrorProveedor(ValueError):
    """Configuración o ejecución no completada; no autoriza un reintento."""


def _now():
    return datetime.now(timezone.utc).isoformat()


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _loads(text):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ErrorProveedor('Respuesta JSON con claves repetidas.')
            out[key] = value
        return out
    def constant(_):
        raise ErrorProveedor('Respuesta JSON con valores no finitos.')
    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, TypeError) as exc:
        raise ErrorProveedor('Respuesta JSON ilegible o no estricta.') from exc


def esquema_respuesta(request, request_sha):
    """Subconjunto JSON Schema para Structured Outputs; validación local adicional."""
    crop_ids = [im['id'] for im in request['imagenes'] if im['admite_evidencia']]
    evidence = {'type': 'object', 'additionalProperties': False,
                'properties': {'imagen_id': {'type': 'string', 'enum': crop_ids},
                               'bbox_imagen_normalizada': {'type': 'array', 'minItems': 4, 'maxItems': 4,
                                                           'items': {'type': 'number', 'minimum': 0, 'maximum': 1}}},
                'required': ['imagen_id', 'bbox_imagen_normalizada']}
    candidate = {'type': 'object', 'additionalProperties': False,
                 'properties': {'id': {'type': 'string'}, 'tipo': {'type': 'string', 'enum': ['cota','etiqueta','elemento']},
                                'valor_propuesto': {'anyOf': [{'type':'number'},{'type':'string'},{'type':'null'}]},
                                'unidad': {'type': 'string', 'enum': ['m','cm','mm','desconocida','no_aplica']},
                                'evidencia': {'type': 'array', 'items': evidence, 'minItems': 1}},
                 'required': ['id', 'tipo', 'valor_propuesto', 'unidad', 'evidencia']}
    properties = {'contrato': {'type':'string','enum':['draft2model.respuesta_vision']},
                  'version_contrato': {'type':'string','enum':[VERSION]},
                  'solicitud_id': {'type':'string','enum':[request['id']]},
                  'solicitud_sha256': {'type':'string','enum':[request_sha]},
                  'candidatos': {'type':'array','items':candidate}}
    return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}


def preparar_peticion(expediente, solicitud, *, modelo, max_tokens=4096, detalle='high'):
    if not isinstance(modelo, str) or not re.fullmatch(r'[A-Za-z0-9_.:/-]{1,128}', modelo):
        raise ErrorProveedor('Indica el identificador exacto del modelo; no hay uno predeterminado.')
    if type(max_tokens) is not int or not 256 <= max_tokens <= 16384:
        raise ErrorProveedor('max_tokens debe estar entre 256 y 16384 (límite local de salida).')
    if detalle not in ('low', 'high', 'auto'):
        raise ErrorProveedor('Detalle no admitido.')
    request, sha, _, _ = cargar_paquete(expediente, solicitud)
    if not 1 <= len(request['imagenes']) <= MAX_IMAGENES:
        raise ErrorProveedor('Selecciona como máximo 16 imágenes por ejecución local.')
    base = Path(solicitud).resolve().parent
    prompt = _inside(base, 'prompt.txt').read_text(encoding='utf-8')
    prompt += '\nPara esta llamada utiliza únicamente los campos del esquema de salida; omite los campos opcionales texto_fuente y confianza.'
    content = []
    encoded_bytes = 0
    for image in request['imagenes']:
        raw = _inside(base, image['ruta']).read_bytes()
        if _hash(raw) != image['sha256']:
            raise ErrorProveedor('La imagen cambió al preparar la petición.')
        encoded_bytes += 4*((len(raw)+2)//3)
        if encoded_bytes > MAX_BYTES:
            raise ErrorProveedor('Las imágenes superan el límite local de 40 MiB codificadas.')
        content.append({'type':'input_text','text':f"Imagen {image['id']} · {image['rol']} · archivo {image['archivo_id']} · página {image['pagina']}"})
        content.append({'type':'input_image','detail':detalle,'image_url':'data:image/png;base64,'+base64.b64encode(raw).decode('ascii')})
    payload = {'model':modelo,'store':False,'max_output_tokens':max_tokens,
               'input':[{'role':'developer','content':[{'type':'input_text','text':prompt}]},
                        {'role':'user','content':content}],
               'text':{'format':{'type':'json_schema','name':'draft2model_lecturas','strict':True,
                                 'schema':esquema_respuesta(request,sha)}}}
    data = _json(payload)
    if len(data) > MAX_BYTES:
        raise ErrorProveedor('La petición supera 40 MiB (límite local). Divide la selección de imágenes.')
    # No se guarda el cuerpo base64 en el plan ni se imprime en consola.
    summary = {'proveedor':'openai','endpoint':ENDPOINT,'modelo':modelo,'solicitud_id':request['id'],
               'solicitud_sha256':sha,'peticion_sha256':_hash(data),'bytes_peticion':len(data),
               'imagenes':[{'id':im['id'],'sha256':im['sha256'],'rol':im['rol']} for im in request['imagenes']],
               'max_output_tokens':max_tokens,'detalle':detalle,'store':False,
               'costo_estimado':None,'nota_costo':'Sin tarifa configurada; el límite de salida no limita el costo total de entrada e imágenes.'}
    return payload, summary


def preparar_plan(expediente, solicitud, *, modelo, max_tokens=4096, detalle='high'):
    _, summary = preparar_peticion(expediente, solicitud, modelo=modelo,max_tokens=max_tokens,detalle=detalle)
    root = Path(expediente).resolve().parent
    request_path = _inside(root, solicitud)
    plan = {'contrato':'draft2model.plan_vision_openai','version_contrato':VERSION,
            'creado_utc':_now(),'estado':'preparado_sin_envio','caso':cargar_extraccion(expediente)['id'],
            'solicitud':request_path.relative_to(root).as_posix(),'configuracion':summary}
    return _publish(_inside(root,'vision/planes_openai'),{'plan.json':_json(plan)})/'plan.json'


class _SinRedireccion(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ErrorProveedor('Redirección inesperada; no se reenvía la credencial.')


def _http(payload, key, timeout):
    request = Request(ENDPOINT, data=_json(payload), method='POST',
                      headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    try:
        with build_opener(_SinRedireccion()).open(request,timeout=timeout) as response:
            raw = response.read(MAX_BYTES+1)
    except HTTPError as exc:
        # No persistir cuerpo de error ni encabezados que puedan incluir secretos.
        raise ErrorProveedor(f'OpenAI devolvió HTTP {exc.code}; no se reintentó.') from None
    except (URLError, TimeoutError, OSError):
        raise ErrorProveedor('No se confirmó la respuesta de OpenAI; el consumo puede ser incierto. No se reintentó.') from None
    if len(raw) > MAX_BYTES:
        raise ErrorProveedor('Respuesta demasiado grande; no se adapta ni importa.')
    try:
        result = _loads(raw.decode('utf-8'))
    except UnicodeDecodeError:
        raise ErrorProveedor('Respuesta no UTF-8.') from None
    if not isinstance(result,dict):
        raise ErrorProveedor('Respuesta de API inválida.')
    return result


def leer_respuesta_api(response):
    if not isinstance(response,dict) or response.get('status') != 'completed' or response.get('error'):
        raise ErrorProveedor('La API no devolvió una respuesta completada; no se importa una salida parcial.')
    if not isinstance(response.get('output'),list):
        raise ErrorProveedor('La salida de API debe ser una lista de mensajes.')
    texts=[]
    for item in response.get('output',[]):
        if not isinstance(item,dict):
            raise ErrorProveedor('Formato de salida inesperado.')
        if item.get('type') == 'reasoning':
            continue
        if item.get('type') != 'message' or item.get('role','assistant') != 'assistant':
            raise ErrorProveedor('Salida ajena a una lectura textual; no se ejecutan herramientas.')
        if item.get('status','completed') != 'completed' or not isinstance(item.get('content'),list):
            raise ErrorProveedor('Mensaje incompleto o sin contenido estructurado.')
        for content in item['content']:
            if not isinstance(content,dict) or content.get('type') == 'refusal':
                raise ErrorProveedor('El proveedor rechazó la petición; no hay extracción importable.')
            if content.get('type') != 'output_text' or not isinstance(content.get('text'),str):
                raise ErrorProveedor('Contenido de salida inesperado.')
            texts.append(content['text'])
    if len(texts) != 1:
        raise ErrorProveedor('Se requiere una única respuesta JSON inequívoca.')
    return _loads(texts[0])


def ejecutar_plan(expediente, plan_path, *, autorizar_envio=False, timeout=120, transporte=None):
    """Un intento por plan. Un transporte inyectado se marca siempre como simulación."""
    if autorizar_envio is not True:
        raise ErrorProveedor('Revisa el plan y autoriza explícitamente el envío de sus imágenes antes de ejecutar.')
    if type(timeout) is not int or not 1 <= timeout <= 180:
        raise ErrorProveedor('Timeout debe ser entero entre 1 y 180 segundos.')
    root = Path(expediente).resolve().parent
    plan_path = _inside(root,plan_path)
    plan = cargar_extraccion(plan_path)
    if (not isinstance(plan,dict) or plan.get('contrato') != 'draft2model.plan_vision_openai' or
        plan.get('version_contrato') != VERSION or plan.get('caso') != cargar_extraccion(expediente)['id']):
        raise ErrorProveedor('Plan incompatible con el expediente.')
    config = plan['configuracion']
    solicitud = _inside(root,plan['solicitud'])
    payload, current = preparar_peticion(expediente,solicitud,modelo=config['modelo'],
                                        max_tokens=config['max_output_tokens'],detalle=config['detalle'])
    if config != current:
        raise ErrorProveedor('El plan ya no coincide con la petición vigente. Prepara uno nuevo.')
    key = os.environ.get('OPENAI_API_KEY','').strip()
    simulated = transporte is not None
    if not simulated and not key:
        raise ErrorProveedor('Falta OPENAI_API_KEY en el entorno local. No se envió nada.')
    if not simulated and ('\n' in key or '\r' in key):
        raise ErrorProveedor('Credencial de formato inválido.')
    # Apertura exclusiva: evita dos envíos del mismo plan aun desde procesos distintos.
    marker = plan_path.parent/'intento.json'
    identifier=uuid4().hex
    attempt = {'id':identifier,'plan_sha256':file_hash(plan_path),'inicio_utc':_now(),
               'estado':'reservado_no_reintentar','simulada':simulated,'transmision_externa_intentada':None,
               'configuracion':config,'aprobacion_ingenieria':None}
    try:
        with marker.open('xb') as output:
            output.write(_json(attempt))
    except FileExistsError:
        raise ErrorProveedor('Este plan ya tiene un intento. Revísalo; no se reenvía automáticamente.') from None
    folder = _inside(root,'vision/intentos_openai')/identifier
    folder.mkdir(parents=True,exist_ok=False)
    start=time.monotonic()
    report={**attempt,'duracion_segundos':None,'duracion_api_segundos':None,
            'usage':None,'extraccion':None,'version_importada':None}
    try:
        report['transmision_externa_intentada']=not simulated
        api_start=time.monotonic()
        try:
            response=(transporte or _http)(payload,key,timeout)
        finally:
            report['duracion_api_segundos']=round(time.monotonic()-api_start,6)
        if key and key in json.dumps(response,ensure_ascii=False):
            raise ErrorProveedor('La respuesta contiene una credencial; no se guarda ni procesa.')
        (folder/'respuesta_api.json').write_bytes(_json(response))
        usage=response.get('usage') if isinstance(response,dict) else None
        report['usage']=usage if isinstance(usage,dict) else None
        report['respuesta_api_sha256']=file_hash(folder/'respuesta_api.json')
        report['respuesta_id_declarado']=response.get('id') if isinstance(response,dict) else None
        report['modelo_devuelto']=response.get('model') if isinstance(response,dict) else None
        parsed=leer_respuesta_api(response)
        adapted_path=folder/'respuesta_visual.json'
        adapted_path.write_bytes(_json(parsed))
        extraction=registrar_respuesta(expediente,solicitud,adapted_path,proveedor='openai' if not simulated else 'simulado',
                                       modelo=config['modelo'],modo_prueba=simulated)
        report['extraccion']=extraction.relative_to(root).as_posix()
        if not simulated:
            imported=importar_extraccion(root.parent,plan['caso'],extraction)
            report['version_importada']=imported.identificador
        report['estado']='simulacion_completada' if simulated else 'importada_pendiente_revision'
    except (ValueError, OSError, TypeError, KeyError) as exc:
        # La respuesta original se conserva, pero nunca una extracción aprobada.
        report['estado']='fallido'
        report['error_tipo']=type(exc).__name__
        report['mensaje']=str(exc) if isinstance(exc,ErrorProveedor) else 'La ejecución no completó la importación; revisa sus archivos privados. No se reintentó.'
    finally:
        report['duracion_segundos']=round(time.monotonic()-start,6)
        report['fin_utc']=_now()
        (folder/'resultado.json').write_bytes(_json(report))
    return folder/'resultado.json'


def main(argv=None):
    parser=argparse.ArgumentParser(description='OpenAI: preparar un plan sin red o ejecutar un envío explícito.')
    commands=parser.add_subparsers(dest='command',required=True)
    prepare=commands.add_parser('preparar')
    for field in ('expediente','solicitud'):
        prepare.add_argument('--'+field,type=Path,required=True)
    prepare.add_argument('--modelo',required=True)
    prepare.add_argument('--max-tokens',type=int,default=4096)
    prepare.add_argument('--detalle',choices=('low','high','auto'),default='high')
    execute=commands.add_parser('ejecutar')
    for field in ('expediente','plan'):
        execute.add_argument('--'+field,type=Path,required=True)
    execute.add_argument('--autorizar-envio',action='store_true')
    args=parser.parse_args(argv)
    try:
        if args.command=='preparar':
            path=preparar_plan(args.expediente,args.solicitud,modelo=args.modelo,max_tokens=args.max_tokens,detalle=args.detalle)
            print('Plan local sin envío: '+str(path))
            return 0
        path=ejecutar_plan(args.expediente,args.plan,autorizar_envio=args.autorizar_envio)
        state=cargar_extraccion(path)['estado']
        print('Resultado: '+str(path)+' · '+state)
        return 0 if state=='importada_pendiente_revision' else 2
    except (ValueError,OSError,KeyError,TypeError) as error:
        print('Conexión no completada: '+str(error),file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
