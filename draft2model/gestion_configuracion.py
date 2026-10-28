"""Versiones de configuración estructural y aprobación propia ligada al contenido."""
from __future__ import annotations
import argparse
import copy
from datetime import date,datetime,timezone
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4
from .gestion_extraccion import carpeta_caso,_carpeta_propia,_publicar,json_desde_bytes
from .modelo_estructural import comprobar_configuracion,huella_configuracion


def _bytes(data):return (json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
def _sha(raw):return hashlib.sha256(raw).hexdigest()
def _record(revisor,fecha,motivo,alcance=None):
    if not all(isinstance(v,str) and v.strip() for v in (revisor,fecha,motivo)):
        raise ValueError('Revisor declarado, fecha y motivo requeridos.')
    if date.fromisoformat(fecha).isoformat()!=fecha:raise ValueError('Fecha debe ser AAAA-MM-DD.')
    if alcance is not None and (not isinstance(alcance,str) or not alcance.strip()):raise ValueError('Alcance requerido.')
    return {'revisor_declarado':revisor,'fecha':fecha,'motivo':motivo,'alcance':alcance}


def _carpeta(raiz,caso,version):
    if not isinstance(version,str) or not re.fullmatch(r'[0-9a-f]{32}',version):raise ValueError('Versión inválida.')
    case=carpeta_caso(raiz,caso);folder=_carpeta_propia(case,'configuraciones_estructurales')/version
    if folder.resolve()!=folder or not folder.is_dir():raise ValueError('Versión ausente o enlazada.')
    return folder


def _leer(folder,name):
    target=folder/name
    if target.resolve()!=target:raise ValueError('Archivo de versión enlazado.')
    return target.read_bytes()


def _exigir_config(raiz,caso,data):
    if not isinstance(data,dict) or data.get('caso')!=caso:raise ValueError('Configuración de otro caso.')
    check=comprobar_configuracion(raiz,data)
    if not check.consistente:raise ValueError('Configuración o geometría incoherentes: '+'; '.join(check.errores))
    return check


def _aprobacion_configuracion_admisible(data, check):
    # Una revisión registrada permite planes de desarrollo de superficies/huecos, no ejecutarlos.
    if isinstance(data, dict) and data.get('version_contrato') in ('0.2.0', '0.3.0'):
        return check.apto_para_plan_desarrollo
    # 0.1 y 0.4 (malla): habilitación operativa completa, sin faltantes de política de nodos ni subdivisión.
    return check.apto_para_adaptador


def consultar(raiz:Path,caso:str,version:str)->dict:
    """Comprueba toda la cadena y sus referencias actuales; rechaza alteraciones."""
    seen=set();chain=[];current=version;child=None;initial=None
    while current is not None:
        if current in seen:raise ValueError('Cadena de versiones circular.')
        seen.add(current);chain.append(current);folder=_carpeta(raiz,caso,current)
        config_raw=_leer(folder,'configuracion.json');meta_raw=_leer(folder,'version.json')
        data=json_desde_bytes(config_raw,'configuracion.json');envelope=json_desde_bytes(meta_raw,'version.json')
        if not isinstance(data,dict):raise ValueError('Configuración guardada no es un objeto.')
        if not isinstance(envelope,dict) or set(envelope)!={'contenido','sha256_contenido'} or _sha(_bytes(envelope['contenido']))!=envelope['sha256_contenido']:
            raise ValueError('Metadatos alterados o inválidos.')
        meta=envelope['contenido']
        keys={'tipo','version','id','caso','operacion','padre','sha256_configuracion','huella_configuracion','fuente_sha256','registro','creado_utc'}
        if (not isinstance(meta,dict) or set(meta)!=keys or meta['tipo']!='draft2model.version_configuracion'
                or meta['version']!='0.1.0' or meta['id']!=current or meta['caso']!=caso
                or meta['sha256_configuracion']!=_sha(config_raw) or meta['huella_configuracion']!=huella_configuracion(data)):
            raise ValueError('Configuración y metadatos no corresponden.')
        try:stamp=datetime.fromisoformat(meta['creado_utc'])
        except (TypeError,ValueError):raise ValueError('Fecha de versión inválida.')
        if stamp.utcoffset() is None:raise ValueError('Fecha de versión sin zona.')
        check=_exigir_config(raiz,caso,data)
        if child is not None:
            link=child['meta']['padre']
            if link!={'id':current,'sha256_configuracion':_sha(config_raw),'sha256_metadatos':_sha(meta_raw)}:
                raise ValueError('Vínculo padre alterado.')
            if data['id']!=child['data']['id'] or data['datos_sinteticos'] is not child['data']['datos_sinteticos']:
                raise ValueError('Revisión cambió identidad o naturaleza de configuración.')
            if child['meta']['operacion']=='aprobacion' and huella_configuracion(data)!=huella_configuracion(child['data']):
                raise ValueError('La aprobación cambió datos de configuración.')
        operation=meta['operacion'];record=meta['registro'];parent=meta['padre']
        if operation=='importacion':
            if parent is not None or record is not None or data['revision']!={'estado':'borrador','aprobacion':None}:
                raise ValueError('Importación no puede declarar aprobación ni padre.')
            source=_leer(folder,'fuente_importada.json')
            if _sha(source)!=meta['fuente_sha256'] or json_desde_bytes(source,'fuente')!=data:
                raise ValueError('Fuente importada alterada o distinta.')
        elif operation in ('revision','aprobacion'):
            if not isinstance(parent,dict) or set(parent)!={'id','sha256_configuracion','sha256_metadatos'} or meta['fuente_sha256'] is not None:
                raise ValueError('Padre o fuente de operación inválidos.')
            if not isinstance(record,dict) or set(record)!={'revisor_declarado','fecha','motivo','alcance'}:raise ValueError('Registro inválido.')
            _record(record['revisor_declarado'],record['fecha'],record['motivo'],record['alcance'])
            if operation=='revision':
                if data['revision']!={'estado':'borrador','aprobacion':None} or record['alcance'] is not None:
                    raise ValueError('Revisión debe ser borrador sin aprobación.')
            else:
                approval={'revisor_declarado':record['revisor_declarado'],'fecha':record['fecha'],
                          'alcance':record['alcance'],'huella_configuracion':huella_configuracion(data),
                          'identidad_revisor':'declarada_no_verificada'}
                if not _aprobacion_configuracion_admisible(data, check) or data['revision']!={'estado':'aprobado','aprobacion':approval} or not record['alcance']:
                    raise ValueError('Aprobación no vigente para esta configuración y geometría.')
        else:raise ValueError('Operación desconocida.')
        node={'data':data,'meta':meta,'folder':folder,'config_raw':config_raw,'meta_raw':meta_raw,'check':check}
        if initial is None:initial=node
        child=node;current=parent['id'] if parent is not None else None
    return {'id':version,'ruta':initial['folder'],'configuracion':copy.deepcopy(initial['data']),
            'metadatos':copy.deepcopy(initial['meta']),'comprobacion':initial['check'].a_dict(),'cadena':chain}


def _guardar(raiz,caso,data,operation,*,parent=None,source=None,record=None):
    _exigir_config(raiz,caso,data)
    ident=uuid4().hex;raw=_bytes(data)
    meta={'tipo':'draft2model.version_configuracion','version':'0.1.0','id':ident,'caso':caso,'operacion':operation,
          'padre':parent,'sha256_configuracion':_sha(raw),'huella_configuracion':huella_configuracion(data),
          'fuente_sha256':_sha(source) if source is not None else None,'registro':record,'creado_utc':datetime.now(timezone.utc).isoformat()}
    files={'configuracion.json':raw,'version.json':_bytes({'contenido':meta,'sha256_contenido':_sha(_bytes(meta))})}
    if source is not None:files['fuente_importada.json']=source
    _publicar(carpeta_caso(raiz,caso),'configuraciones_estructurales',ident,files)
    return consultar(raiz,caso,ident)


def importar(raiz,caso,entrada):
    raw=Path(entrada).read_bytes();data=json_desde_bytes(raw,'entrada')
    _exigir_config(raiz,caso,data)
    if data['revision']!={'estado':'borrador','aprobacion':None}:raise ValueError('Importar en borrador; aprobar mediante operación propia.')
    return _guardar(raiz,caso,data,'importacion',source=raw)


def _padre(raiz,caso,version):
    consult=consultar(raiz,caso,version);folder=consult['ruta']
    return consult,{'id':version,'sha256_configuracion':_sha(_leer(folder,'configuracion.json')),'sha256_metadatos':_sha(_leer(folder,'version.json'))}


def revisar(raiz,caso,version,propuesta,*,revisor,fecha,motivo):
    record=_record(revisor,fecha,motivo);source,link=_padre(raiz,caso,version)
    data=copy.deepcopy(propuesta);_exigir_config(raiz,caso,data)
    if data['revision']!={'estado':'borrador','aprobacion':None} or any(data[k]!=source['configuracion'][k] for k in ('id','datos_sinteticos')):
        raise ValueError('Revisar en borrador conservando identidad y naturaleza.')
    return _guardar(raiz,caso,data,'revision',parent=link,record=record)


def aprobar(raiz,caso,version,*,huella_esperada,revisor,fecha,motivo,alcance):
    record=_record(revisor,fecha,motivo,alcance);source,link=_padre(raiz,caso,version);data=source['configuracion']
    if huella_esperada!=huella_configuracion(data) or data['revision']['estado']=='aprobado':raise ValueError('Huella distinta o configuración ya aprobada.')
    data['revision']={'estado':'aprobado','aprobacion':{'revisor_declarado':revisor,'fecha':fecha,'alcance':alcance,
         'huella_configuracion':huella_configuracion(data),'identidad_revisor':'declarada_no_verificada'}}
    if not _aprobacion_configuracion_admisible(data, comprobar_configuracion(raiz,data)):raise ValueError('Configuración con faltantes o geometría sin aprobación vigente.')
    return _guardar(raiz,caso,data,'aprobacion',parent=link,record=record)


def preparar_malla_version(raiz:Path,caso:str,version:str)->dict:
    """Preparación reproducible de la malla de una configuración 0.4 registrada: nodos derivados, triángulos,
    subdivisiones requeridas, plantilla de política y faltantes. No escribe nada ni aprueba ingeniería."""
    from . import gestion_geometria as gg
    from . import malla_preparacion as mp
    result=consultar(raiz,caso,version);data=result['configuracion']
    if data.get('version_contrato') not in ('0.4.0','0.5.0'):raise ValueError('La preparación de malla solo aplica a configuraciones 0.4.0/0.5.0.')
    geometria=gg.consultar_version(raiz,caso,data['geometria_origen']['version_id']).geometria
    try:prep=mp.preparar_malla(geometria,data)
    except mp.ErrorMalla as exc:raise ValueError(f'Malla no reproducible: {exc}') from None
    return {'id':version,'preparacion':prep,'faltantes':[f for f in result['comprobacion']['faltantes'] if f['ruta'].startswith(('$.nodos_derivados.','$.subdivision_frames.'))],
            'apto_para_adaptador':result['comprobacion']['apto_para_adaptador'],'aprueba_ingenieria':False,
            'huella_configuracion':result['metadatos']['huella_configuracion']}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--raiz',type=Path,default=Path('data/private'));p.add_argument('--caso',required=True)
    sub=p.add_subparsers(dest='operacion',required=True)
    imp=sub.add_parser('importar');imp.add_argument('--entrada',type=Path,required=True)
    malla=sub.add_parser('malla',help='Preparación de malla 0.4 (solo lectura)');malla.add_argument('--version',required=True)
    for name in ('consultar','revisar','aprobar'):
        command=sub.add_parser(name);command.add_argument('--version',required=True)
        if name=='revisar':command.add_argument('--entrada',type=Path,required=True)
        if name!='consultar':
            for field in ('revisor','fecha','motivo'):command.add_argument('--'+field,required=True)
        if name=='aprobar':command.add_argument('--huella-esperada',required=True);command.add_argument('--alcance',required=True)
    args=p.parse_args(argv)
    try:
        if args.operacion=='importar':result=importar(args.raiz,args.caso,args.entrada)
        elif args.operacion=='consultar':result=consultar(args.raiz,args.caso,args.version)
        elif args.operacion=='malla':
            print(json.dumps(preparar_malla_version(args.raiz,args.caso,args.version),ensure_ascii=False,indent=2,allow_nan=False));return 0
        else:
            extra={k:getattr(args,k) for k in ('revisor','fecha','motivo')}
            if args.operacion=='revisar':result=revisar(args.raiz,args.caso,args.version,json_desde_bytes(args.entrada.read_bytes(),'propuesta'),**extra)
            else:result=aprobar(args.raiz,args.caso,args.version,huella_esperada=args.huella_esperada,alcance=args.alcance,**extra)
        result['ruta']=str(result['ruta']);print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False));return 0
    except (ValueError,OSError,TypeError) as exc:
        import sys
        print('Configuración no registrada: '+str(exc),file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
