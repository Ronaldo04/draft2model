"""Resultados declarados y comparación pura; no ejecuta un motor estructural.

La integridad de un JSON no autentica al productor ni acredita un análisis real.
Las unidades se comparan exactamente, sin conversión implícita.
"""
from __future__ import annotations

import argparse
import copy
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

CONTRATO = 'draft2model.resultados_estructurales'
VERSION = '0.1.0'
VARIABLES = ('periodo', 'deriva', 'cortante')
UNIDADES = {'periodo': {'s'}, 'deriva': {'1'}, 'cortante': {'N', 'kN'}}
AVISO = ('Datos y motor declarados, sin autenticación del productor. '
         'La comparación numérica no certifica seguridad estructural ni valida un modelo ETABS.')


class ErrorResultados(ValueError):
    pass


def huella_resultados(data: Any) -> str:
    """Huella canónica de todos los campos del resultado, incluida su procedencia."""
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def _numero(value):
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


def _texto(value):
    return isinstance(value, str) and bool(value.strip())


def _id(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', value) is not None


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def _campos(data, required, optional=()):
    return isinstance(data, dict) and set(required).issubset(data) and not set(data) - set(required) - set(optional)


def clave_resultado(row):
    """Identidad física declarada; el ID de fila no sustituye esta clave."""
    return row['variable'], row['caso'], row['direccion'], row['ubicacion']


def validar_resultados(data: Any, *, referencias_esperadas=None) -> dict:
    """Valida estructura y referencias opcionales, sin modificar ni escribir la entrada.

    `referencias_esperadas` debe contener geometria/configuracion {id, sha256};
    permite al llamador vincular los resultados a sus artefactos verificados.
    """
    errors = []
    root = {'contrato', 'version_contrato', 'corrida_id', 'caso_id', 'creado_utc',
            'geometria', 'configuracion', 'motor', 'datos_sinteticos', 'casos', 'unidades',
            'resultados', 'advertencias', 'omisiones'}
    if not _campos(data, root):
        return {'correcta': False, 'errores': ['Campos raíz inválidos.'], 'huella': None}
    if data['contrato'] != CONTRATO or data['version_contrato'] != VERSION:
        errors.append('Contrato o versión no admitidos.')
    for key in ('corrida_id', 'caso_id'):
        if not _id(data[key]):
            errors.append(f'{key}: identificador inválido.')
    try:
        stamp = datetime.fromisoformat(data['creado_utc'].replace('Z', '+00:00'))
        if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0:
            raise ValueError()
    except (TypeError, ValueError, AttributeError):
        errors.append('creado_utc debe ser fecha y hora ISO con zona UTC.')
    for key in ('geometria', 'configuracion'):
        ref = data[key]
        if not _campos(ref, {'id', 'sha256'}) or not _id(ref.get('id')) or not _sha(ref.get('sha256')):
            errors.append(f'{key}: referencia id/SHA256 inválida.')
    if referencias_esperadas is not None:
        if not _campos(referencias_esperadas, {'geometria', 'configuracion'}):
            errors.append('Referencias esperadas inválidas.')
        elif any(data[key] != referencias_esperadas[key] for key in ('geometria', 'configuracion')):
            errors.append('Los resultados no corresponden a geometría/configuración esperadas.')
    motor = data['motor']
    if (not _campos(motor, {'tipo', 'nombre', 'version'}) or motor.get('tipo') not in ('real', 'simulacion')
            or not all(_texto(motor.get(k)) for k in ('nombre', 'version'))):
        errors.append('Motor inválido: declarar tipo real/simulacion, nombre y versión.')
    if type(data['datos_sinteticos']) is not bool:
        errors.append('datos_sinteticos debe ser booleano.')
    elif isinstance(motor, dict) and motor.get('tipo') == 'simulacion' and not data['datos_sinteticos']:
        errors.append('Una simulación debe conservar datos_sinteticos true.')
    cases = data['casos']
    case_ids = set()
    if not isinstance(cases, list) or not cases:
        errors.append('Se requiere al menos un caso de análisis explícito.')
    else:
        for case in cases:
            if not _campos(case, {'id', 'tipo', 'descripcion'}) or not _id(case.get('id')) or not all(_texto(case.get(k)) for k in ('tipo', 'descripcion')):
                errors.append('Caso de análisis inválido.')
            elif case['id'] in case_ids:
                errors.append('Identificador de caso de análisis repetido.')
            else:
                case_ids.add(case['id'])
    units = data['unidades']
    if not _campos(units, VARIABLES) or any(not isinstance(units.get(v), str) or units[v] not in UNIDADES[v] for v in VARIABLES):
        errors.append('Unidades inválidas; periodo s, deriva 1 y cortante N o kN explícitos.')
    for key in ('advertencias', 'omisiones'):
        if not isinstance(data[key], list) or not all(_texto(x) for x in data[key]):
            errors.append(f'{key} debe ser una lista de textos no vacíos.')
    rows = data['resultados']
    ids, keys = set(), set()
    if not isinstance(rows, list):
        errors.append('resultados debe ser una lista.')
    else:
        for row in rows:
            if not _campos(row, {'id', 'variable', 'caso', 'direccion', 'ubicacion', 'valor', 'unidad'}, {'motivo_omision'}):
                errors.append('Campos de resultado inválidos.')
                continue
            if not _id(row['id']) or row['id'] in ids:
                errors.append('ID de resultado inválido o repetido.')
            else:
                ids.add(row['id'])
            if row['variable'] not in VARIABLES or not isinstance(row['caso'], str) or row['caso'] not in case_ids or not all(_texto(row[k]) for k in ('direccion', 'ubicacion')):
                errors.append('Variable, caso, dirección o ubicación de resultado inválidos.')
                continue
            key = clave_resultado(row)
            if key in keys:
                errors.append('Resultado físico repetido para variable/caso/dirección/ubicación.')
            keys.add(key)
            if not isinstance(units, dict) or row['unidad'] != units.get(row['variable']):
                errors.append('La unidad de la fila no corresponde a la unidad declarada.')
            if row['valor'] is None:
                if not _texto(row.get('motivo_omision')):
                    errors.append('Un valor null exige motivo_omision explícito.')
            elif not _numero(row['valor']):
                errors.append('Los valores deben ser números finitos, nunca booleanos.')
            elif 'motivo_omision' in row:
                errors.append('Un valor presente no puede declarar motivo_omision.')
            elif row['variable'] == 'periodo' and row['valor'] <= 0:
                errors.append('El periodo presente debe ser positivo.')
    fingerprint = None
    try:
        fingerprint = huella_resultados(data)
    except (ValueError, TypeError, OverflowError):
        errors.append('El resultado no es JSON estricto serializable.')
    return {'correcta': not errors, 'errores': errors, 'huella': fingerprint}


def exigir_resultados(data, **kwargs):
    check = validar_resultados(data, **kwargs)
    if not check['correcta']:
        raise ErrorResultados(' '.join(check['errores']))
    return check


def huella_declaracion(data):
    return huella_resultados({k: v for k, v in data.items() if k != 'revision'})


def aprobacion_vigente(data):
    """Identidad y competencia declaradas; ninguna firma/autenticación implícita."""
    revision = data.get('revision') if isinstance(data, dict) else None
    if not _campos(revision, {'estado', 'aprobacion'}) or revision['estado'] != 'aprobado':
        return False
    ap = revision['aprobacion']
    if not _campos(ap, {'revisor_declarado', 'fecha', 'motivo', 'alcance', 'huella_contenido'}):
        return False
    if not all(_texto(ap[k]) for k in ('revisor_declarado', 'motivo', 'alcance')):
        return False
    try:
        if not isinstance(ap['fecha'], str) or len(ap['fecha']) != 10:
            return False
        date.fromisoformat(ap['fecha'])
        return ap['huella_contenido'] == huella_declaracion(data)
    except (ValueError, TypeError):
        return False


def _equivalencia(actual, referencia, declaration, a, r, tolerancias):
    if not _campos(declaration, {'contrato', 'version_contrato', 'id', 'actual', 'referencia',
                                 'unidades', 'casos', 'hipotesis', 'tolerancias', 'justificacion', 'revision'}):
        raise ErrorResultados('Declaración de equivalencia incompleta.')
    if (declaration['contrato'] != 'draft2model.equivalencia_resultados' or declaration['version_contrato'] != VERSION
            or not _id(declaration['id']) or not _texto(declaration['justificacion'])
            or not aprobacion_vigente(declaration)):
        raise ErrorResultados('Equivalencia sin revisión/aprobación declarada vigente para su huella.')
    for key, data, check in (('actual', actual, a), ('referencia', referencia, r)):
        expected = {'corrida_id': data['corrida_id'], 'huella': check['huella'],
                    'geometria': data['geometria'], 'configuracion': data['configuracion']}
        if declaration[key] != expected:
            raise ErrorResultados('La equivalencia no corresponde a la corrida/referencias exactas: '+key)
    if declaration['unidades'] != actual['unidades'] or actual['unidades'] != referencia['unidades']:
        raise ErrorResultados('Unidades incompatibles; se exige equivalencia exacta sin conversiones implícitas.')
    if declaration['tolerancias'] != tolerancias:
        raise ErrorResultados('Las tolerancias no coinciden con la equivalencia revisada.')
    hypothesis = declaration['hipotesis']
    if (not _campos(hypothesis, {'actual', 'referencia', 'justificacion'})
            or not _texto(hypothesis['justificacion'])
            or any(not isinstance(hypothesis[k], list) or not hypothesis[k] or not all(_texto(x) for x in hypothesis[k])
                   for k in ('actual', 'referencia'))):
        raise ErrorResultados('Declarar hipótesis de ambos análisis y justificación de su equivalencia.')
    mapping = declaration['casos']
    if not isinstance(mapping, list):
        raise ErrorResultados('Correspondencia de casos inválida.')
    aa, rr = {x['id'] for x in actual['casos']}, {x['id'] for x in referencia['casos']}
    lookup, targets = {}, set()
    for row in mapping:
        if (not _campos(row, {'actual', 'referencia', 'justificacion'})
                or not _id(row.get('actual')) or not _id(row.get('referencia')) or not _texto(row.get('justificacion'))):
            raise ErrorResultados('Correspondencia de caso incompleta.')
        if row['referencia'] in lookup or row['actual'] in targets:
            raise ErrorResultados('La correspondencia de casos debe ser uno a uno.')
        lookup[row['referencia']] = row['actual']
        targets.add(row['actual'])
    if set(lookup) != rr or targets != aa:
        raise ErrorResultados('La equivalencia debe cubrir exactamente todos los casos de ambas corridas.')
    return lookup


def comparar_resultados(actual: Any, referencia: Any, tolerancias: Any, equivalencia: Any, *,
                        huella_actual_esperada: str, huella_referencia_esperada: str) -> dict:
    """Compara resultados equivalentes con tolerancias explícitas por variable.

    Acepta si |actual-ref| <= max(absoluta, relativa*|ref|). Cerca de cero
    (|ref| <= umbral_cero) usa exclusivamente absoluta. Nunca divide por cero.
    La tolerancia absoluta tiene la unidad declarada de la variable.
    """
    a, r = exigir_resultados(actual), exigir_resultados(referencia)
    if a['huella'] != huella_actual_esperada or r['huella'] != huella_referencia_esperada:
        raise ErrorResultados('La huella esperada no coincide con los resultados actuales.')
    for key in ('caso_id', 'datos_sinteticos'):
        if actual[key] != referencia[key]:
            raise ErrorResultados(f'Referencia no equivalente: {key}.')
    if actual['motor']['tipo'] != referencia['motor']['tipo']:
        raise ErrorResultados('No se comparan motores reales con simulaciones.')
    case_mapping = _equivalencia(actual, referencia, equivalencia, a, r, tolerancias)
    if not _campos(tolerancias, VARIABLES):
        raise ErrorResultados('Se requiere tolerancia explícita para cada variable.')
    for variable, tol in tolerancias.items():
        if (not _campos(tol, {'absoluta', 'relativa', 'umbral_cero', 'unidad'})
                or tol['unidad'] != actual['unidades'][variable]
                or any(not _numero(tol[k]) or tol[k] < 0 for k in ('absoluta', 'relativa', 'umbral_cero'))):
            raise ErrorResultados('Tolerancia inválida o unidad no equivalente: '+variable)
    aa = {clave_resultado(x): x for x in actual['resultados']}
    rr = {(x['variable'], case_mapping[x['caso']], x['direccion'], x['ubicacion']): x for x in referencia['resultados']}
    comparisons = []
    for key in sorted(aa.keys() | rr.keys()):
        left, right = aa.get(key), rr.get(key)
        row = dict(zip(('variable', 'caso', 'direccion', 'ubicacion'), key))
        row.update(valor_actual=left['valor'] if left else None, valor_referencia=right['valor'] if right else None)
        if left is None or right is None or left['valor'] is None or right['valor'] is None:
            row.update(estado='faltante', diferencia_absoluta=None, tolerancia_aplicada=None)
        else:
            tol = tolerancias[key[0]]
            absolute = abs(left['valor'] - right['valor'])
            near_zero = abs(right['valor']) <= tol['umbral_cero']
            threshold = tol['absoluta'] if near_zero else max(tol['absoluta'], tol['relativa'] * abs(right['valor']))
            if not _numero(absolute) or not _numero(threshold):
                raise ErrorResultados('Desbordamiento numérico en comparación.')
            row.update(estado='dentro_tolerancia' if absolute <= threshold else 'fuera_tolerancia',
                diferencia_absoluta=absolute, tolerancia_aplicada=threshold, cerca_de_cero=near_zero)
        comparisons.append(row)
    complete = bool(comparisons) and all(x['estado'] != 'faltante' for x in comparisons)
    return {'contrato': 'draft2model.comparacion_resultados', 'version_contrato': VERSION,
            'huella_actual': a['huella'], 'huella_referencia': r['huella'],
            'corrida_actual': actual['corrida_id'], 'corrida_referencia': referencia['corrida_id'],
            'geometria': copy.deepcopy(actual['geometria']), 'configuracion': copy.deepcopy(actual['configuracion']),
            'motor_actual': copy.deepcopy(actual['motor']), 'motor_referencia': copy.deepcopy(referencia['motor']),
            'equivalencia': copy.deepcopy(equivalencia), 'huella_equivalencia': huella_declaracion(equivalencia),
            'datos_sinteticos': actual['datos_sinteticos'], 'tolerancias': copy.deepcopy(tolerancias),
            'formula': 'abs(actual-referencia) <= max(absoluta, relativa*abs(referencia)); cerca de cero: absoluta',
            'comparacion_completa': complete, 'dentro_tolerancias': complete and all(x['estado'] == 'dentro_tolerancia' for x in comparisons),
            'comparaciones': comparisons, 'advertencias_actuales': copy.deepcopy(actual['advertencias']),
            'omisiones_actuales': copy.deepcopy(actual['omisiones']),
            'advertencias_referencia': copy.deepcopy(referencia['advertencias']),
            'omisiones_referencia': copy.deepcopy(referencia['omisiones']), 'aviso': AVISO}


def cargar_json(path):
    """Reutiliza el parser estricto local: rechaza claves duplicadas y NaN."""
    from .gestion_extraccion import json_desde_bytes
    return json_desde_bytes(Path(path).read_bytes(), Path(path).name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('resultados', type=Path)
    args = parser.parse_args()
    check = validar_resultados(cargar_json(args.resultados))
    print(json.dumps(check, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if check['correcta'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
