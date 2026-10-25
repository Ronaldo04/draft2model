"""Tablas CSI -> indicadores mediante correspondencias explícitas y evidencia exacta."""
from __future__ import annotations
import copy
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
from uuid import uuid4
from datetime import datetime
from .gestion_extraccion import json_desde_bytes, carpeta_caso, _publicar
from .modelo_estructural import comprobar_configuracion, huella_configuracion
from .resultados_estructurales import aprobacion_vigente, exigir_resultados, huella_resultados


def _texto(value):return isinstance(value,str) and bool(value.strip())


def campo_caso_csi(tabla, variable, tipo_caso):
    """Campo de caso del esquema observado; no admite aliases inferidos."""
    if (tabla in ('Modal Periods And Frequencies','Modal Participating Mass Ratios')
            and variable=='periodo' and tipo_caso=='modal_eigen'):return 'Case'
    return 'OutputCase'


def _fecha_utc(value):
    # .NET usa siete decimales; Python 3.10 admite como máximo seis.
    # Se conserva la respuesta exacta y se normaliza solo el timestamp derivado.
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,7})?(?:Z|\+00:00)',value):
        raise ValueError('Fecha de respuesta debe ser ISO UTC explícita.')
    normalized=re.sub(r'\.(\d{1,7})(?=Z|\+00:00)',lambda m:'.'+m[1][:6].ljust(6,'0'),value)
    return datetime.fromisoformat(normalized.replace('Z','+00:00')).isoformat()


def _numero(text):
    if not isinstance(text,str) or not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?',text.strip()):
        raise ValueError('Valor CSI no es un decimal explícito con punto; no se infiere formato local.')
    value=float(text)
    if not math.isfinite(value):raise ValueError('Valor CSI no finito.')
    if value==0 and any(c in '123456789' for c in text.split('e')[0].split('E')[0]):
        raise ValueError('Subdesbordamiento al leer valor CSI.')
    return value


def _procesar_resultados(raiz, configuracion, respuesta, mapeo, *, publicar):
    snapshots={name:Path(path).read_bytes() for name,path in
               (('configuracion',configuracion),('respuesta',respuesta),('mapeo',mapeo))}
    config,raw,mapping=(json_desde_bytes(snapshots[name],name+'.json') for name in ('configuracion','respuesta','mapeo'))
    comp=comprobar_configuracion(raiz,config)
    if not comp.apto_para_adaptador:raise ValueError('Configuración o geometría sin aprobación/evidencia vigentes.')
    required={'contrato','version','caso','datos_sinteticos','huella_configuracion','sha256_respuesta','modelo',
              'unidades_api_esperadas','version_etabs_esperada','selectores','revision'}
    if (not isinstance(mapping,dict) or set(mapping)!=required or mapping['contrato']!='draft2model.mapeo_resultados_etabs'
            or mapping['version']!='0.1.0' or mapping['caso']!=config['caso']
            or type(mapping['datos_sinteticos']) is not bool or mapping['datos_sinteticos']!=config['datos_sinteticos']
            or mapping['huella_configuracion']!=huella_configuracion(config)):
        raise ValueError('Mapeo completo requerido para esta configuración.')
    if publicar:
        if not aprobacion_vigente(mapping):raise ValueError('Revisión explícita vigente del mapeo requerida para publicar.')
    elif mapping['revision']!={'estado':'borrador','aprobacion':None} and not aprobacion_vigente(mapping):
        raise ValueError('La previsualización admite borrador explícito o aprobación vigente.')
    if hashlib.sha256(snapshots['respuesta']).hexdigest()!=mapping['sha256_respuesta']:
        raise ValueError('La respuesta no coincide con la evidencia revisada.')
    if (not isinstance(raw,dict) or raw.get('contrato')!='draft2model.etabs_respuesta' or raw.get('version_contrato')!='0.1.0'
            or raw.get('estado')!='ok' or raw.get('operacion')!='leer_tablas'
            or raw.get('modo_ejecucion') not in ('real','doble') or not re.fullmatch(r'[0-9a-f]{32}',str(raw.get('id_solicitud','')))):
        raise ValueError('Se requiere una respuesta correcta de leer_tablas identificada.')
    if raw['modo_ejecucion']=='doble' and not config['datos_sinteticos']:
        raise ValueError('El doble no produce resultados reales.')
    case=carpeta_caso(raiz,config['caso'])
    model=mapping['modelo']
    if (not isinstance(model,dict) or not {'archivo','sha256'}.issubset(model)
            or set(model)-{'archivo','sha256','archivo_motor'} or not _texto(model['archivo'])):
        raise ValueError('Referencia de modelo inválida.')
    relative=Path(model['archivo']);model_path=case/relative
    if relative.is_absolute() or '..' in relative.parts or model_path.resolve()!=model_path or model_path.suffix.lower()!='.edb':
        raise ValueError('El modelo debe ser un EDB del caso, sin enlaces ni rutas externas.')
    model_sha=hashlib.sha256(model_path.read_bytes()).hexdigest()
    if model_sha!=model['sha256']:raise ValueError('Modelo EDB alterado desde la revisión.')
    motor_path=model_path
    if 'archivo_motor' in model:
        if not _texto(model['archivo_motor']):raise ValueError('Ruta de motor inválida.')
        motor_path=Path(model['archivo_motor'])
        if (not motor_path.is_absolute() or motor_path.resolve()!=motor_path
                or motor_path.suffix.lower()!='.edb' or not motor_path.is_file()
                or hashlib.sha256(motor_path.read_bytes()).hexdigest()!=model_sha):
            raise ValueError('El EDB del motor no coincide exactamente con la copia del expediente.')
    data=raw.get('datos')
    if not isinstance(data,dict) or Path(str(data.get('modelo','')))!=motor_path:
        raise ValueError('La respuesta corresponde a otro modelo.')
    if (not isinstance(data.get('casos'),list) or not all(_texto(v) for v in data['casos'])
            or not isinstance(data.get('estado_casos'),dict) or not isinstance(raw.get('avisos'),list)
            or not all(_texto(v) for v in raw['avisos'])):
        raise ValueError('Casos, estados o avisos de respuesta inválidos.')
    if not _texto(data.get('version_etabs')) or data['version_etabs']!=mapping['version_etabs_esperada']:
        raise ValueError('Versión ETABS de respuesta ausente o distinta de la revisada.')
    units=data.get('unidades')
    if not _texto(units) or units!=mapping['unidades_api_esperadas']:
        raise ValueError('Unidades de API distintas de las revisadas.')
    tables={}
    if not isinstance(data.get('tablas'),list):raise ValueError('Tablas CSI inválidas.')
    for table in data['tablas']:
        if not isinstance(table,dict) or not _texto(table.get('clave')) or table['clave'] in tables or not isinstance(table.get('campos'),list) or not isinstance(table.get('filas'),list):
            raise ValueError('Tabla duplicada o sin campos/filas explícitos.')
        if not all(_texto(v) for v in table['campos']) or len(set(table['campos']))!=len(table['campos']):
            raise ValueError('Campos CSI inválidos o duplicados.')
        if any(not isinstance(row,dict) or set(row)!=set(table['campos']) for row in table['filas']):
            raise ValueError('Fila CSI no corresponde a sus campos.')
        tables[table['clave']]=table
    selectors=mapping['selectores']
    if not isinstance(selectors,list) or not selectors:raise ValueError('Sin selectores de resultados.')
    config_cases={c['id']:c for c in config['casos']};rows=[];trace=[];selected=set()
    for selector in selectors:
        keys={'id','variable','caso','direccion','ubicacion','tabla','filtros','campo_valor','unidad_origen'}
        if not isinstance(selector,dict) or set(selector)!=keys or not all(_texto(selector[k]) for k in keys-{'filtros'}):
            raise ValueError('Selector inválido.')
        variable=selector['variable'];analysis_case=selector['caso'];table=tables.get(selector['tabla'])
        if variable not in ('periodo','deriva','cortante') or table is None or analysis_case not in config_cases:
            raise ValueError('Variable, tabla o caso no disponibles en la configuración.')
        if analysis_case not in data.get('casos',[]) or data.get('estado_casos',{}).get(analysis_case)!=4:
            raise ValueError('El caso no está confirmado como análisis terminado.')
        filters=selector['filtros']
        # Las tablas modales CSI observadas identifican el caso con Case.
        # No admitir un alias arbitrario ni inferirlo de filas sin identificador.
        case_field=campo_caso_csi(selector['tabla'],variable,config_cases[analysis_case]['tipo'])
        if (not isinstance(filters,dict) or not filters or filters.get(case_field)!=analysis_case
                or not all(k in table['campos'] and isinstance(v,str) for k,v in filters.items())
                or selector['campo_valor'] not in table['campos']):
            raise ValueError('Filtros/campo inválidos; '+case_field+' explícito es obligatorio.')
        source_unit=selector['unidad_origen'];factor=1.0
        if variable=='cortante':
            if source_unit not in ('N','kN') or not units.startswith(source_unit+'_'):
                raise ValueError('La unidad de fuerza no corresponde al sistema API soportado N/kN.')
            factor=0.001 if source_unit=='N' else 1.0
        elif source_unit!=('s' if variable=='periodo' else '1'):
            raise ValueError('Periodo en segundos y deriva adimensional requeridos.')
        candidates=[(i,row) for i,row in enumerate(table['filas']) if all(row[k]==v for k,v in filters.items())]
        if len(candidates)>1:raise ValueError('Selector ambiguo: no se elige paso/envolvente automáticamente.')
        row={k:selector[k] for k in ('id','variable','caso','direccion','ubicacion')}
        row['unidad']={'periodo':'s','deriva':'1','cortante':'kN'}[variable]
        if not candidates:row.update(valor=None,motivo_omision='No existe fila para el selector revisado.')
        else:
            number=_numero(candidates[0][1][selector['campo_valor']])
            row['valor']=number*factor
            if not math.isfinite(row['valor']) or (number!=0 and row['valor']==0):raise ValueError('Conversión no representable.')
        rows.append(row);selected.add(analysis_case)
        trace.append({'resultado_id':row['id'],'tabla':selector['tabla'],'fila_indice':candidates[0][0] if candidates else None,
                      'campo':selector['campo_valor'],'filtros':copy.deepcopy(filters),'unidad_origen':source_unit,'factor':factor})
    result={'contrato':'draft2model.resultados_estructurales','version_contrato':'0.1.0','corrida_id':raw['id_solicitud'],
            'caso_id':config['caso'],'creado_utc':_fecha_utc(raw.get('fin_utc')),
            'geometria':{'id':config['geometria_origen']['version_id'],'sha256':config['geometria_origen']['sha256_geometria']},
            'configuracion':{'id':config['id'],'sha256':huella_configuracion(config)},
            'motor':{'tipo':'real' if raw['modo_ejecucion']=='real' else 'simulacion','nombre':'ETABS' if raw['modo_ejecucion']=='real' else 'doble-ETABS','version':data['version_etabs']},
            'datos_sinteticos':config['datos_sinteticos'],
            'casos':[{'id':c,'tipo':config_cases[c]['tipo'],'descripcion':'Caso de configuración '+config['id']} for c in sorted(selected)],
            'unidades':{'periodo':'s','deriva':'1','cortante':'kN'},'resultados':rows,
            'advertencias':list(raw.get('avisos',[]))+['Motor y productor declarados; las huellas no autentican una ejecución externa.'],
            'omisiones':[r['id']+': '+r['motivo_omision'] for r in rows if r['valor'] is None]}
    exigir_resultados(result)
    # Revalidar fuentes justo antes de publicar; no mezclar versiones concurrentes.
    if (not comprobar_configuracion(raiz,config).apto_para_adaptador
            or hashlib.sha256(model_path.read_bytes()).hexdigest()!=model_sha
            or hashlib.sha256(motor_path.read_bytes()).hexdigest()!=model_sha):
        raise ValueError('El origen cambió durante la normalización.')
    for name,path in (('configuracion',configuracion),('respuesta',respuesta),('mapeo',mapeo)):
        if Path(path).read_bytes()!=snapshots[name]:raise ValueError('Entrada cambió durante la normalización.')
    if not publicar:
        return {'resultados':result,'correspondencias':trace,'huella_resultados':huella_resultados(result),
                'publicado':False,'aprueba_resultados':False,'revision_mapeo':'aprobado' if aprobacion_vigente(mapping) else 'borrador'}
    serial=lambda obj:(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    return _publicar(case,'resultados_estructurales',uuid4().hex,{
        'resultados.json':serial(result),'respuesta_puente.json':snapshots['respuesta'],'mapeo.json':snapshots['mapeo'],
        'configuracion.json':snapshots['configuracion'],
        'trazabilidad.json':serial({'sha256_respuesta':mapping['sha256_respuesta'],'modelo':model,
            'huella_resultados':huella_resultados(result),'correspondencias':trace})})


def registrar_resultados(raiz: Path, configuracion: Path, respuesta: Path, mapeo: Path) -> Path:
    """Publicar indicadores nuevos; exige mapeo aprobado, sin ejecutar ETABS."""
    return _procesar_resultados(raiz,configuracion,respuesta,mapeo,publicar=True)


def previsualizar_resultados(raiz: Path, configuracion: Path, respuesta: Path, mapeo: Path) -> dict:
    """Comprobar correspondencias y valores sin publicar ni aprobar el borrador."""
    return _procesar_resultados(raiz,configuracion,respuesta,mapeo,publicar=False)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('raiz','configuracion','respuesta','mapeo'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args(argv)
    try:print(registrar_resultados(args.raiz,args.configuracion,args.respuesta,args.mapeo));return 0
    except (ValueError,OSError,TypeError) as exc:
        import sys
        print('Resultados no registrados: '+str(exc),file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
