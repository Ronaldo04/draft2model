"""Controles postsolver reproducibles desde fuentes crudas y criterios declarados; sin motor."""
from __future__ import annotations

import base64
import copy
from datetime import date
import hashlib
import json
import math
import re

from .gestion_extraccion import json_desde_bytes
from .normalizacion_etabs import _numero

CONTRATO = 'draft2model.controles_analisis'
VERSION = '0.1.0'
TIPOS = {'participacion_modal', 'equilibrio', 'advertencias_solver'}
AVISO = ('Criterios, aplicabilidad e identidad del revisor declarados, sin verificación profesional. '
         'Estos controles no certifican completitud física, conformidad normativa ni seguridad. '
         'Estado CSI 4 no equivale a controles satisfactorios.')


def _bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode('utf-8')


def _sha(raw): return hashlib.sha256(raw).hexdigest()


def _campos(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError('Campos exactos requeridos: '+', '.join(sorted(expected)))


def _texto(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 4000:
        raise ValueError('Texto explícito no vacío requerido.')


def _hex(value, n=64):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{'+str(n)+'}', value) is None:
        raise ValueError('Identificador o SHA inválido.')


def _finito(value, minimo=None):
    if type(value) not in (int, float) or not math.isfinite(value) or (minimo is not None and value < minimo):
        raise ValueError('Número finito fuera del dominio declarado.')


def _lista_textos(values, vacia=False):
    if not isinstance(values, list) or (not vacia and not values):
        raise ValueError('Lista explícita requerida.')
    for value in values: _texto(value)
    if len(values) != len(set(values)): raise ValueError('Valores repetidos.')


def _fuente(raw):
    if not isinstance(raw, bytes) or not raw or len(raw) > 40*1024*1024:
        raise ValueError('Fuente requiere bytes originales no vacíos, hasta 40 MiB.')
    return {'sha256': _sha(raw), 'bytes_base64': base64.b64encode(raw).decode('ascii')}


def adaptar_lectura(respuesta_bytes, declaracion):
    """Adaptar esquema actual de LectorAnalisis; no acredita su aceptación ni consulta archivos."""
    raw = json_desde_bytes(respuesta_bytes, 'respuesta de lectura')
    if (not isinstance(raw, dict) or raw.get('contrato') != 'draft2model.etabs_respuesta'
            or raw.get('version_contrato') != '0.1.0' or raw.get('operacion') != 'leer_tablas'
            or raw.get('estado') != 'ok' or raw.get('modo_ejecucion') not in ('real', 'doble')
            or raw.get('id_solicitud') != declaracion['lectura']):
        raise ValueError('Respuesta de lectura identificada requerida.')
    if raw['modo_ejecucion'] == 'doble' and declaracion['datos_sinteticos'] is not True:
        raise ValueError('Transporte doble no aporta datos reales.')
    data = raw.get('datos')
    if (not isinstance(data, dict) or data.get('corrida_analisis_id') != declaracion['corrida_analisis']
            or data.get('sha256_modelo_verificado') != declaracion['modelo']['sha256_edb']
            or data.get('unidades') != 'kN_m_C' or data.get('casos') != declaracion['casos']
            or data.get('combinaciones') != []):
        raise ValueError('Corrida, EDB, casos o unidades no coinciden; no se completan vínculos ausentes.')
    states = data.get('estado_casos')
    if (not isinstance(states, dict) or set(states) != set(declaracion['casos'])
            or any(type(v) is not int or v != 4 for v in states.values())):
        raise ValueError('Lectura debe declarar casos completos; esto no los declara controlados.')
    if not isinstance(raw.get('avisos'),list): raise ValueError('Avisos del lector explícitos requeridos.')
    for aviso in raw['avisos']: _texto(aviso)
    if not isinstance(data.get('tablas'), list): raise ValueError('Tablas explícitas requeridas.')
    tables = {}
    for table in data['tablas']:
        if not isinstance(table, dict) or not {'clave','campos','filas'} <= set(table):
            raise ValueError('Tabla cruda incompleta.')
        _texto(table['clave']); _lista_textos(table['campos'])
        if table['clave'] in tables or not isinstance(table['filas'], list): raise ValueError('Tabla duplicada o filas inválidas.')
        case_field = 'OutputCase' if 'OutputCase' in table['campos'] else (
            'Case' if table['clave'] in ('Modal Periods And Frequencies', 'Modal Participating Mass Ratios') and 'Case' in table['campos'] else None)
        if case_field is None: raise ValueError('Tabla no admitida por el lector actual; falta campo de caso.')
        for row in table['filas']:
            if (not isinstance(row, dict) or set(row) != set(table['campos'])
                    or any(v is not None and not isinstance(v, str) for v in row.values())
                    or row[case_field] not in declaracion['casos']):
                raise ValueError('Fila de otro caso o esquema no textual.')
        tables[table['clave']] = copy.deepcopy(table)
    return {'tablas': tables, 'avisos_lector': copy.deepcopy(raw['avisos']),
            'estado_casos': copy.deepcopy(states), 'modo': raw['modo_ejecucion']}


def _declaracion(d):
    _campos(d, {'caso','expediente_sha256','corrida_analisis','lectura','modelo','datos_sinteticos','casos',
                'sha256_respuesta','sha256_avisos_solver','revisor_declarado','fecha','alcance','controles'})
    _texto(d['caso'])
    if re.fullmatch('[a-z0-9][a-z0-9_-]{0,79}', d['caso']) is None: raise ValueError('Caso inválido.')
    for key in ('corrida_analisis','lectura'): _hex(d[key], 32)
    for key in ('expediente_sha256','sha256_respuesta'): _hex(d[key])
    if d['sha256_avisos_solver'] is not None: _hex(d['sha256_avisos_solver'])
    _campos(d['modelo'], {'id','sha256_edb'}); _hex(d['modelo']['id'], 32); _hex(d['modelo']['sha256_edb'])
    if type(d['datos_sinteticos']) is not bool: raise ValueError('Naturaleza explícita requerida.')
    _lista_textos(d['casos'])
    for key in ('revisor_declarado','fecha','alcance'): _texto(d[key])
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}',d['fecha']) is None: raise ValueError('Fecha ISO requerida.')
    date.fromisoformat(d['fecha'])
    if not isinstance(d['controles'],list) or len(d['controles']) < 3: raise ValueError('Declare las tres familias de control.')
    ids = set(); tipos = set()
    for c in d['controles']:
        _campos(c, {'id','tipo','caso','aplica','critico','motivo','fuente_criterio','parametros'})
        _texto(c['id']); _texto(c['motivo']); _texto(c['fuente_criterio'])
        if c['id'] in ids or not isinstance(c['tipo'],str) or c['tipo'] not in TIPOS: raise ValueError('ID repetido o control no soportado.')
        ids.add(c['id']); tipos.add(c['tipo'])
        if type(c['aplica']) is not bool or type(c['critico']) is not bool: raise ValueError('Aplicabilidad y criticidad explícitas requeridas.')
        if c['caso'] not in d['casos'] and not (c['tipo']=='advertencias_solver' and c['caso'] is None):
            raise ValueError('Caso de control no declarado.')
        if c['tipo']=='advertencias_solver' and c['caso'] is not None:
            raise ValueError('Las advertencias cubren toda la corrida; caso debe ser null.')
        if not c['aplica'] and c['parametros'] != {}: raise ValueError('No aplicable requiere parámetros vacíos, con motivo explícito.')
    if tipos != TIPOS: raise ValueError('No omitir familias: declarar aplicabilidad de las tres.')


def _seleccionar(selector, caso, unidad, tablas):
    _campos(selector, {'tabla','campo_caso','filtros','campo','unidad'})
    for key in ('tabla','campo_caso','campo','unidad'): _texto(selector[key])
    if selector['unidad'] != unidad: raise ValueError('Unidad explícita incompatible con la fórmula.')
    if selector['tabla']=='Base Reactions':
        known={'FX':'kN','FY':'kN','FZ':'kN','MX':'kN_m','MY':'kN_m','MZ':'kN_m'}
        if selector['campo'] in known and known[selector['campo']]!=unidad:
            raise ValueError('Campo de fuerza/momento incompatible con la unidad declarada.')
    filters = selector['filtros']
    if (not isinstance(filters,dict) or filters.get(selector['campo_caso']) != caso
            or not all(isinstance(k,str) and k and isinstance(v,str) for k,v in filters.items())):
        raise ValueError('Filtro exacto del caso obligatorio.')
    expected = 'Case' if selector['tabla'] in ('Modal Periods And Frequencies','Modal Participating Mass Ratios') else 'OutputCase'
    if selector['campo_caso'] != expected: raise ValueError('Campo de caso no corresponde al esquema admitido.')
    table = tablas.get(selector['tabla'])
    trace = {'selector':copy.deepcopy(selector),'sha256_tabla':_sha(_bytes(table)) if table is not None else None,
             'fila_indice':None,'valor_crudo':None}
    if table is None: return None, trace, 'Tabla requerida ausente: '+selector['tabla']
    if not set(filters)|{selector['campo']} <= set(table['campos']):
        return None, trace, 'Campos requeridos ausentes en tabla.'
    rows = [(i,r) for i,r in enumerate(table['filas']) if all(r[k]==v for k,v in filters.items())]
    if len(rows)>1: raise ValueError('Selector ambiguo: declarar modo/paso/ubicación, sin elegir máximo ni última fila.')
    if not rows: return None, trace, 'No existe fila para filtros explícitos.'
    i,row = rows[0]; trace.update(fila_indice=i, valor_crudo=row[selector['campo']])
    if row[selector['campo']] is None or row[selector['campo']]=='': return None, trace, 'Valor crudo vacío.'
    return _numero(row[selector['campo']]), trace, None


def _solver(raw, d):
    if raw is None: return None
    source = json_desde_bytes(raw,'avisos solver declarados')
    _campos(source, {'contrato','version','corrida_analisis','modelo_id','sha256_edb','casos','origen_declarado','advertencias'})
    if (source['contrato']!='draft2model.avisos_solver_declarados' or source['version']!=VERSION
            or source['corrida_analisis']!=d['corrida_analisis'] or source['modelo_id']!=d['modelo']['id']
            or source['sha256_edb']!=d['modelo']['sha256_edb'] or source['casos']!=d['casos']):
        raise ValueError('Avisos de otro modelo, EDB, corrida o casos.')
    _texto(source['origen_declarado'])
    if not isinstance(source['advertencias'],list): raise ValueError('Advertencias explícitas requeridas.')
    for warning in source['advertencias']:
        _campos(warning, {'caso','codigo','texto'})
        if warning['caso'] is not None and warning['caso'] not in d['casos']: raise ValueError('Advertencia de caso ajeno.')
        _texto(warning['codigo']); _texto(warning['texto'])
    return source


def _calcular(c, tables, solver):
    # base_datos distingue cálculo sobre tablas de la lectura de una fuente solver solo declarada.
    base = 'fuente_solver_declarada' if c['tipo']=='advertencias_solver' else 'tablas_lectura'
    result = {'id':c['id'],'tipo':c['tipo'],'caso':c['caso'],'estado':'no_aplicable',
              'motivos':[c['motivo']],'formula':None,'valores':None,'trazas':[],'base_datos':base,
              'verificacion':'declarada_no_verificada' if base=='fuente_solver_declarada' else 'recalculada_desde_bytes_de_lectura'}
    if not c['aplica']: return result
    p = c['parametros']; missing=[]; traces=[]
    if c['tipo']=='participacion_modal':
        _campos(p, {'selector','minimo_acumulado','direccion'})
        _campos(p['selector'], {'tabla','campo_caso','filtros','campo','unidad'})
        _texto(p['direccion']); _finito(p['minimo_acumulado'],0)
        if p['minimo_acumulado']>1: raise ValueError('Participación mínima debe declararse como fracción 0..1.')
        if p['selector'].get('tabla')!='Modal Participating Mass Ratios' or p['selector'].get('campo') not in ('SumUX','SumUY','SumUZ','SumRX','SumRY','SumRZ'):
            raise ValueError('Solo campos acumulados observados, sin sumar UX ni deducir modo final.')
        expected = {'SumUX':'UX','SumUY':'UY','SumUZ':'UZ','SumRX':'RX','SumRY':'RY','SumRZ':'RZ'}
        if p['direccion']!=expected[p['selector']['campo']]: raise ValueError('Dirección distinta del campo acumulado.')
        value, trace, error = _seleccionar(p['selector'],c['caso'],'1',tables); traces.append(trace)
        if error: missing.append(error)
        if value is not None and not 0<=value<=1: raise ValueError('Participación cruda fuera de 0..1; no se infiere porcentaje.')
        satisfied = value is not None and value>=p['minimo_acumulado']
        result.update(formula='acumulado_seleccionado >= minimo_acumulado',
                      valores={'acumulado':value,'minimo':p['minimo_acumulado'],'unidad':'1','direccion':p['direccion']})
    elif c['tipo']=='equilibrio':
        _campos(p, {'cargas','reacciones','unidad','tolerancia_absoluta','tolerancia_relativa','escala_referencia'})
        if p['unidad'] not in ('kN','kN_m'): raise ValueError('Solo fuerza kN o momento kN_m en API kN_m_C.')
        for key in ('tolerancia_absoluta','tolerancia_relativa','escala_referencia'): _finito(p[key],0)
        if p['escala_referencia']==0: raise ValueError('Escala de referencia positiva requerida; no dividir por cero.')
        values=[]; seen=set()
        for side in ('cargas','reacciones'):
            if not isinstance(p[side],list) or not p[side]: raise ValueError('Cargas y reacciones requieren términos explícitos.')
            for term in p[side]:
                _campos(term, {'selector','factor'})
                if type(term['factor']) not in (int,float) or term['factor'] not in (-1,1): raise ValueError('Signo explícito +1/-1 requerido.')
                key=_bytes(term['selector'])
                if key in seen: raise ValueError('No reutilizar un mismo componente para cancelar cargas/reacciones.')
                seen.add(key)
                value,trace,error=_seleccionar(term['selector'],c['caso'],p['unidad'],tables)
                trace.update(lado=side,factor=term['factor']);traces.append(trace)
                if error: missing.append(error)
                if value is not None: values.append(value*term['factor'])
        residual = None if missing else math.fsum(values)
        limit = max(p['tolerancia_absoluta'],p['tolerancia_relativa']*p['escala_referencia'])
        _finito(limit)
        if residual is not None: _finito(residual)
        satisfied = residual is not None and abs(residual)<=limit
        relative=None if residual is None else abs(residual)/p['escala_referencia']
        if relative is not None: _finito(relative)
        result.update(formula='abs(sum(factor * cargas) + sum(factor * reacciones)) <= max(tol_abs, tol_rel * escala)',
                      valores={'residuo_firmado':residual,'limite':limit,'unidad':p['unidad'],
                               'error_relativo':relative})
    else:
        _campos(p, {'codigos_admitidos'});_lista_textos(p['codigos_admitidos'],vacia=True)
        if solver is None: missing.append('No se aportó fuente explícita de advertencias del solver; avisos del lector no la sustituyen.')
        warnings=[] if solver is None else solver['advertencias']
        unexpected=[w for w in warnings if w['codigo'] not in p['codigos_admitidos']]
        satisfied=solver is not None and not unexpected
        result.update(formula='todos los codigos de advertencia pertenecen a codigos_admitidos declarados',
                      valores={'advertencias':copy.deepcopy(warnings),'no_admitidas':copy.deepcopy(unexpected)})
    result.update(estado='sin_datos' if missing else ('satisfactorio' if satisfied else 'discrepante'),
                  motivos=missing or [c['motivo']],trazas=traces)
    return result


def crear_controles(declaracion, respuesta_bytes, *, avisos_solver_bytes=None):
    """Devolver contrato JSON nuevo y determinista; no escribir ni alterar sus entradas."""
    _declaracion(declaracion);d=copy.deepcopy(declaracion)
    response_source=_fuente(respuesta_bytes)
    solver_source=None if avisos_solver_bytes is None else _fuente(avisos_solver_bytes)
    if response_source['sha256']!=d['sha256_respuesta'] or (solver_source['sha256'] if solver_source else None)!=d['sha256_avisos_solver']:
        raise ValueError('SHA de bytes originales distinto del declarado.')
    data=adaptar_lectura(respuesta_bytes,d);solver=_solver(avisos_solver_bytes,d)
    controls=[_calcular(c,data['tablas'],solver) for c in d['controles']]
    applicable=[r for c,r in zip(d['controles'],controls) if c['aplica']]
    critical=[r['id'] for c,r in zip(d['controles'],controls) if c['critico'] and r['estado']=='sin_datos']
    # Una declaración externa (p. ej. lista vacía de avisos) no basta: al menos un control aplicable
    # debe calcularse desde las tablas crudas de la lectura para proyectar "controlado".
    calculated=[r for r in applicable if r['base_datos']=='tablas_lectura']
    controlled=bool(calculated) and all(r['estado']=='satisfactorio' for r in applicable)
    global_state=('satisfactorio' if controlled else 'discrepante' if any(r['estado']=='discrepante' for r in applicable)
                  else 'sin_datos' if applicable else 'no_aplicable')
    doc={'contrato':CONTRATO,'version':VERSION,'declaracion':d,
         'fuentes':{'respuesta':response_source,'avisos_solver':solver_source},
         'huellas_tablas':{name:_sha(_bytes(t)) for name,t in data['tablas'].items()},
         'controles':controls,'estado_global':global_state,'apto_proyeccion_controlado':controlled,
         'controles_solo_declarados':[r['id'] for r in applicable if r['base_datos']!='tablas_lectura'],
         'criticos_no_aplicables':[c['id'] for c in d['controles'] if c['critico'] and not c['aplica']],
         'faltantes_criticos':critical,'avisos_lector':data['avisos_lector'],
         'advertencias_solver':None if solver is None else copy.deepcopy(solver['advertencias']),
         'estado_casos_declarado':data['estado_casos'],'estado_analisis':'no_evaluado_por_este_nucleo',
         'revision_profesional_verificada':False,'aprueba_resultados':False,'conformidad_normativa':'no_evaluada','aviso':AVISO}
    doc['huella_contenido']=_sha(_bytes(doc))
    return doc


def recalcular_controles(documento, *, respuesta_bytes=None, avisos_solver_bytes=None):
    """Recalcular con originales embebidos; si se aportan bytes actuales, exigir identidad exacta."""
    if not isinstance(documento,dict) or not isinstance(documento.get('fuentes'),dict): raise ValueError('Contrato de controles inválido.')
    sources=documento['fuentes'];_campos(sources,{'respuesta','avisos_solver'})
    def decode(source):
        _campos(source,{'sha256','bytes_base64'})
        try:raw=base64.b64decode(source['bytes_base64'],validate=True)
        except (ValueError,TypeError):raise ValueError('Fuente base64 inválida.') from None
        if _fuente(raw)!=source:raise ValueError('Bytes o SHA de fuente alterados.')
        return raw
    raw=decode(sources['respuesta']);solver=None if sources['avisos_solver'] is None else decode(sources['avisos_solver'])
    if respuesta_bytes is not None and respuesta_bytes!=raw:raise ValueError('La respuesta actual cambió.')
    if avisos_solver_bytes is not None and avisos_solver_bytes!=solver:raise ValueError('La fuente solver actual cambió.')
    return crear_controles(documento['declaracion'],raw,avisos_solver_bytes=solver)


def validar_controles(documento, **fuentes_actuales):
    """Exigir contenido/criterios/fórmulas/huellas reproducibles; no autenticar motor ni revisor."""
    if recalcular_controles(documento,**fuentes_actuales)!=documento:
        raise ValueError('Controles, estados, criterios o huellas alterados.')
    return True
