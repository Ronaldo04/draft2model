"""Evaluación pura contra reglas configuradas y aprobadas de forma declarada.

No incorpora normas, límites, coeficientes o juicios de seguridad predeterminados.
Solo admite la fórmula explícita `factor * x + desplazamiento`, sin ejecutar código.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from .resultados_estructurales import (
    AVISO, VARIABLES, UNIDADES, _campos, _id, _numero, _texto, aprobacion_vigente,
    cargar_json, clave_resultado, exigir_resultados, huella_declaracion,
)

CONTRATO = 'draft2model.reglas_estructurales'
VERSION = '0.1.0'
FORMULA = 'factor * x + desplazamiento'
COMPARADORES = ('<', '<=', '==', '>=', '>')


class ErrorEvaluacion(ValueError):
    pass


def validar_reglas(data: Any) -> dict:
    errors = []
    if not _campos(data, {'contrato', 'version_contrato', 'id', 'datos_sinteticos', 'reglas', 'revision'}):
        return {'correcta': False, 'errores': ['Campos de reglas inválidos.'], 'huella': None, 'aprobacion_vigente': False}
    if data['contrato'] != CONTRATO or data['version_contrato'] != VERSION or not _id(data['id']):
        errors.append('Contrato, versión o identificador de reglas inválidos.')
    if type(data['datos_sinteticos']) is not bool:
        errors.append('La marca datos_sinteticos debe ser booleana.')
    ids = set()
    if not isinstance(data['reglas'], list) or not data['reglas']:
        errors.append('Se requiere al menos una regla configurada.')
    else:
        for rule in data['reglas']:
            base = {'id', 'variable', 'unidad', 'formula', 'limite', 'comparador', 'aplicabilidad', 'fuente'}
            if not (_campos(rule, base) or _campos(rule, base | {'unidad_resultado'})):
                errors.append('Campos de regla inválidos.')
                continue
            # unidad_resultado (opcional, revisión Codex 290): unidad de factor·x + desplazamiento y del límite, distinta de la
            # unidad de ENTRADA. Explícita; nunca se infiere del factor. Sin la clave, el resultado conserva la unidad de entrada.
            if 'unidad_resultado' in rule and (not isinstance(rule['unidad_resultado'], str)
                                               or rule['unidad_resultado'] not in UNIDADES.get(rule['variable'], set()) | {'1'}):
                errors.append('unidad_resultado no admitida: unidad de la variable o «1» (adimensional).')
            if not _id(rule['id']) or rule['id'] in ids:
                errors.append('ID de regla inválido o repetido.')
            else:
                ids.add(rule['id'])
            if (rule['variable'] not in VARIABLES or not isinstance(rule['unidad'], str)
                    or rule['unidad'] not in UNIDADES.get(rule['variable'], set())):
                errors.append('Variable o unidad de regla no admitida.')
            formula = rule['formula']
            if (not _campos(formula, {'expresion', 'factor', 'desplazamiento'})
                    or formula['expresion'] != FORMULA
                    or any(not _numero(formula[k]) for k in ('factor', 'desplazamiento'))):
                errors.append('Fórmula inválida: se exige factor * x + desplazamiento con constantes finitas.')
            if not _numero(rule['limite']) or rule['comparador'] not in COMPARADORES:
                errors.append('Límite finito y comparador explícitos obligatorios.')
            applies = rule['aplicabilidad']
            if (not _campos(applies, {'aplica', 'casos', 'direcciones', 'ubicaciones', 'motivo'})
                    or type(applies['aplica']) is not bool or not _texto(applies['motivo'])):
                errors.append('Aplicabilidad booleana, selectores y motivo obligatorios.')
            else:
                for key in ('casos', 'direcciones', 'ubicaciones'):
                    values = applies[key]
                    if (not isinstance(values, list) or not values or not all(_texto(x) for x in values)
                            or len(set(values)) != len(values)):
                        errors.append('Selectores de aplicabilidad deben ser listas no vacías sin duplicados.')
            source = rule['fuente']
            if not _campos(source, {'titulo', 'edicion', 'apartado', 'referencia'}) or not all(_texto(source[k]) for k in source):
                errors.append('Fuente debe declarar título, edición, apartado y referencia.')
    revision = data['revision']
    if (not _campos(revision, {'estado', 'aprobacion'})
            or revision['estado'] not in ('borrador', 'aprobado')
            or (revision['estado'] == 'borrador' and revision['aprobacion'] is not None)):
        errors.append('Estado de revisión de reglas inválido.')
    approved = aprobacion_vigente(data)
    if isinstance(revision, dict) and revision.get('estado') == 'aprobado' and not approved:
        errors.append('Aprobación declarada de reglas ausente, inválida o con huella obsoleta.')
    fingerprint = None
    try:
        fingerprint = huella_declaracion(data)
    except (ValueError, TypeError, OverflowError):
        errors.append('Reglas no serializables como JSON estricto.')
    return {'correcta': not errors, 'errores': errors, 'huella': fingerprint, 'aprobacion_vigente': approved}


def evaluar_resultados(resultados: Any, reglas: Any, *, huella_resultados_esperada: str,
                       huella_reglas_esperada: str, referencias_esperadas=None) -> dict:
    """Evalúa cada selector explícito; diferencia faltante, no aplicable y relación.

    La igualdad se decide sobre los números representados, sin tolerancia tácita.
    La aprobación de reglas cubre su contenido completo salvo el registro revision.
    """
    check = exigir_resultados(resultados, referencias_esperadas=referencias_esperadas)
    rc = validar_reglas(reglas)
    if not rc['correcta'] or not rc['aprobacion_vigente']:
        raise ErrorEvaluacion('Reglas sin aprobación declarada vigente. '+' '.join(rc['errores']))
    if check['huella'] != huella_resultados_esperada or rc['huella'] != huella_reglas_esperada:
        raise ErrorEvaluacion('Las huellas esperadas no corresponden al contenido vigente.')
    if resultados['datos_sinteticos'] != reglas['datos_sinteticos']:
        raise ErrorEvaluacion('No se aplican reglas sintéticas a resultados reales ni viceversa.')
    rows = {clave_resultado(row): row for row in resultados['resultados']}
    evaluations = []
    for rule in reglas['reglas']:
        if rule['unidad'] != resultados['unidades'][rule['variable']]:
            raise ErrorEvaluacion('Unidad de regla incompatible; no hay conversión implícita: '+rule['id'])
        applies = rule['aplicabilidad']
        for case in applies['casos']:
            for direction in applies['direcciones']:
                for location in applies['ubicaciones']:
                    row = rows.get((rule['variable'], case, direction, location))
                    item = {'regla_id': rule['id'], 'variable': rule['variable'], 'unidad': rule['unidad'],
                            'caso': case, 'direccion': direction, 'ubicacion': location,
                            'formula': copy.deepcopy(rule['formula']), 'limite': rule['limite'],
                            'comparador': rule['comparador'], 'fuente': copy.deepcopy(rule['fuente']),
                            'aplicabilidad': copy.deepcopy(applies), 'resultado_id': row['id'] if row else None,
                            'valor_entrada': row['valor'] if row else None, 'valor_evaluado': None,
                            'relacion_limite': None, 'satisface_regla_configurada': None}
                    if 'unidad_resultado' in rule:   # solo si se declara: evaluaciones anteriores conservan su forma y huella
                        item['unidad_resultado'] = rule['unidad_resultado']
                    if not applies['aplica']:
                        item.update(estado='no_aplicable', motivo=applies['motivo'])
                    elif row is None or row['valor'] is None:
                        item.update(estado='faltante', motivo=row.get('motivo_omision') if row else 'No existe resultado para el selector configurado.')
                    else:
                        try:
                            value = rule['formula']['factor'] * row['valor'] + rule['formula']['desplazamiento']
                        except OverflowError as exc:
                            raise ErrorEvaluacion('Desbordamiento numérico al evaluar '+rule['id']) from exc
                        if not _numero(value):
                            raise ErrorEvaluacion('Desbordamiento numérico al evaluar '+rule['id'])
                        limit = rule['limite']
                        relation = 'debajo' if value < limit else 'sobre' if value > limit else 'en'
                        passed = {'<': value < limit, '<=': value <= limit, '==': value == limit,
                                  '>=': value >= limit, '>': value > limit}[rule['comparador']]
                        item.update(estado='evaluado', valor_evaluado=value, relacion_limite=relation,
                                    satisface_regla_configurada=passed)
                    evaluations.append(item)
    return {'contrato': 'draft2model.evaluacion_estructural', 'version_contrato': VERSION,
            'corrida_id': resultados['corrida_id'], 'caso_id': resultados['caso_id'],
            'huella_resultados': check['huella'], 'reglas_id': reglas['id'], 'huella_reglas': rc['huella'],
            'aprobacion_reglas_declarada': copy.deepcopy(reglas['revision']['aprobacion']),
            'geometria': copy.deepcopy(resultados['geometria']), 'configuracion': copy.deepcopy(resultados['configuracion']),
            'motor': copy.deepcopy(resultados['motor']), 'datos_sinteticos': resultados['datos_sinteticos'],
            'evaluaciones': evaluations, 'advertencias': copy.deepcopy(resultados['advertencias']),
            'omisiones': copy.deepcopy(resultados['omisiones']), 'aviso': AVISO,
            'criterio': 'Solo satisfacción de reglas configuradas; no es un juicio de seguridad estructural.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('resultados', type=Path)
    parser.add_argument('reglas', type=Path)
    parser.add_argument('--huella-resultados', required=True)
    parser.add_argument('--huella-reglas', required=True)
    args = parser.parse_args()
    output = evaluar_resultados(cargar_json(args.resultados), cargar_json(args.reglas),
        huella_resultados_esperada=args.huella_resultados, huella_reglas_esperada=args.huella_reglas)
    print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
