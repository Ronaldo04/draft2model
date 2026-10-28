"""Evaluación de lecturas propuestas con referencia y correspondencias declaradas.

No llama a modelos, no genera referencia humana y no aprueba ingeniería.
"""
from __future__ import annotations

import argparse
import copy
from datetime import date
import json
from pathlib import Path
import sys

from .extraccion_preliminar import cargar_extraccion, huella, validar_extraccion

VERSION = '0.1.0'


class ErrorEvaluacion(ValueError):
    """Entradas de evaluación inválidas o desactualizadas."""


def objeto(value, required, where):
    if not isinstance(value, dict) or set(value) != set(required):
        raise ErrorEvaluacion(f'{where}: campos requeridos exactamente: {", ".join(required)}.')


def revision(value, where):
    objeto(value, ('revisor_declarado', 'fecha', 'estado'), where)
    if value['estado'] != 'revisado' or not isinstance(value['revisor_declarado'], str) or not value['revisor_declarado'].strip():
        raise ErrorEvaluacion(f'{where}: se requiere estado revisado y revisor declarado.')
    try:
        if not isinstance(value['fecha'], str) or date.fromisoformat(value['fecha']).isoformat() != value['fecha']:
            raise ValueError()
    except (TypeError, ValueError):
        raise ErrorEvaluacion(f'{where}: fecha inválida; usar AAAA-MM-DD.') from None


def consistente(data, where):
    result = validar_extraccion(data)
    if not result.consistente:
        raise ErrorEvaluacion(where + ': ' + '; '.join(str(e) for e in result.errores))


def validar_referencia(ref):
    objeto(ref, ('contrato', 'version_contrato', 'caso', 'procedencia', 'alcance',
                 'sistema_coordenadas', 'revision', 'observaciones'), 'referencia')
    if ref['contrato'] != 'draft2model.referencia_vision' or ref['version_contrato'] != VERSION:
        raise ErrorEvaluacion('Contrato o versión de referencia no admitidos.')
    revision(ref['revision'], 'referencia.revision')
    if not isinstance(ref['observaciones'], list) or not ref['observaciones']:
        raise ErrorEvaluacion('La referencia necesita observaciones, no solo una plantilla vacía.')
    candidates = []
    for index, obs in enumerate(ref['observaciones']):
        where = f'observaciones[{index}]'
        objeto(obs, ('id', 'tipo', 'valor', 'unidad', 'legibilidad', 'evidencia'), where)
        if obs['legibilidad'] not in ('legible', 'ilegible', 'ambigua'):
            raise ErrorEvaluacion(where + ': legibilidad no admitida.')
        if obs['legibilidad'] == 'legible' and obs['valor'] is None:
            raise ErrorEvaluacion(where + ': una observación legible debe declarar valor.')
        if obs['legibilidad'] == 'ilegible' and obs['valor'] is not None:
            raise ErrorEvaluacion(where + ': una observación ilegible debe mantener valor null.')
        candidates.append({'id': obs['id'], 'tipo': obs['tipo'], 'valor_propuesto': obs['valor'],
                           'unidad': obs['unidad'], 'metodo': {'tipo': 'manual'}, 'evidencia': obs['evidencia']})
    # Reutilizar reglas de valores, unidades, IDs, hashes y coordenadas existentes.
    consistent_ref = {k: ref[k] for k in ('version_contrato', 'caso', 'procedencia', 'alcance', 'sistema_coordenadas')}
    consistent_ref.update(contrato='draft2model.extraccion_preliminar', candidatos=candidates)
    consistente(consistent_ref, 'referencia')


def proporcion(numerator, denominator):
    return {'numerador': numerator, 'denominador': denominator,
            'proporcion': numerator / denominator if denominator else None}


def validar_correspondencias(ref, extraction, mapping):
    objeto(mapping, ('contrato', 'version_contrato', 'caso', 'huella_referencia',
                     'huella_extraccion', 'revision', 'pares', 'sin_respaldo'), 'correspondencias')
    if mapping['contrato'] != 'draft2model.correspondencias_vision' or mapping['version_contrato'] != VERSION:
        raise ErrorEvaluacion('Contrato o versión de correspondencias no admitidos.')
    if mapping['caso'] != ref['caso'] or mapping['huella_referencia'] != huella(ref) or mapping['huella_extraccion'] != huella(extraction):
        raise ErrorEvaluacion('Correspondencias desactualizadas o de otro caso: no coinciden las huellas.')
    revision(mapping['revision'], 'correspondencias.revision')
    if not isinstance(mapping['pares'], list) or not isinstance(mapping['sin_respaldo'], list):
        raise ErrorEvaluacion('pares y sin_respaldo deben ser listas.')
    observations = {o['id']: o for o in ref['observaciones']}
    candidates = {c['id']: c for c in extraction['candidatos']}
    used, primaries, grouped = set(), {}, {}
    for index, pair in enumerate(mapping['pares']):
        where = f'pares[{index}]'
        objeto(pair, ('observacion_id', 'candidato_id', 'principal', 'evidencia_correcta',
                      'indice_evidencia_referencia', 'indice_evidencia_candidato'), where)
        oid, cid = pair['observacion_id'], pair['candidato_id']
        if not isinstance(oid, str) or not isinstance(cid, str) or oid not in observations or cid not in candidates:
            raise ErrorEvaluacion(where + ': referencia a observación/candidato inexistente.')
        if cid in used:
            raise ErrorEvaluacion(where + ': un candidato no puede emparejarse más de una vez.')
        if type(pair['principal']) is not bool or type(pair['evidencia_correcta']) is not bool:
            raise ErrorEvaluacion(where + ': principal y evidencia_correcta requieren booleanos explícitos.')
        obs, candidate = observations[oid], candidates[cid]
        if obs['tipo'] != candidate['tipo']:
            raise ErrorEvaluacion(where + ': los tipos no coinciden.')
        selected = []
        for key, source in (('indice_evidencia_referencia', obs), ('indice_evidencia_candidato', candidate)):
            n = pair[key]
            if type(n) is not int or not 0 <= n < len(source['evidencia']):
                raise ErrorEvaluacion(where + ': índice de evidencia inválido.')
            selected.append(source['evidencia'][n])
        if pair['evidencia_correcta']:
            a, b = selected
            if any(a[k] != b[k] for k in ('archivo_id', 'pagina', 'original_sha256')):
                raise ErrorEvaluacion(where + ': evidencia declarada correcta de otro documento, página o hash.')
            x, y = a['bbox_normalizada'], b['bbox_normalizada']
            if min(x[2], y[2]) <= max(x[0], y[0]) or min(x[3], y[3]) <= max(x[1], y[1]):
                raise ErrorEvaluacion(where + ': regiones sin solapamiento no pueden declararse evidencia correcta.')
        used.add(cid)
        grouped.setdefault(oid, []).append(pair)
        if pair['principal']:
            if oid in primaries:
                raise ErrorEvaluacion(where + ': dos candidatos principales para una misma observación.')
            primaries[oid] = pair
    if any(oid not in primaries for oid in grouped):
        raise ErrorEvaluacion('Cada observación emparejada necesita exactamente un candidato principal.')
    false_ids = mapping['sin_respaldo']
    if any(not isinstance(cid, str) or cid not in candidates for cid in false_ids):
        raise ErrorEvaluacion('sin_respaldo contiene candidatos inexistentes.')
    if len(set(false_ids)) != len(false_ids) or used.intersection(false_ids):
        raise ErrorEvaluacion('Candidatos repetidos o clasificados a la vez como emparejados y sin respaldo.')
    return observations, candidates, used, primaries


def metricas(observations, candidates, primaries):
    evaluable = [o for o in observations if o['legibilidad'] != 'ambigua']
    legible = [o for o in evaluable if o['legibilidad'] == 'legible']
    unreadable = [o for o in evaluable if o['legibilidad'] == 'ilegible']
    paired = [o for o in evaluable if o['id'] in primaries]
    paired_legible = [o for o in legible if o['id'] in primaries]
    def candidate(o):
        return candidates[primaries[o['id']]['candidato_id']]
    value_ok = sum(candidate(o)['valor_propuesto'] == o['valor'] for o in paired_legible)
    unit_ok = sum(candidate(o)['unidad'] == o['unidad'] for o in paired)
    full_ok = sum(candidate(o)['valor_propuesto'] == o['valor'] and candidate(o)['unidad'] == o['unidad']
                  and primaries[o['id']]['evidencia_correcta'] for o in paired_legible)
    return {
        'observaciones': len(observations), 'ambiguas_excluidas': len(observations) - len(evaluable),
        'cobertura': proporcion(len(paired), len(evaluable)),
        'exactitud_valor_legible_emparejado': proporcion(value_ok, len(paired_legible)),
        'exactitud_unidad_emparejada': proporcion(unit_ok, len(paired)),
        'lecturas_completas_sobre_legibles': proporcion(full_ok, len(legible)),
        'abstenciones_correctas_sobre_ilegibles': proporcion(sum(o['id'] in primaries and candidate(o)['valor_propuesto'] is None for o in unreadable), len(unreadable)),
        'abstenciones_incorrectas_sobre_legibles': sum(candidate(o)['valor_propuesto'] is None for o in paired_legible),
        'unidades_referencia_desconocidas': sum(o['unidad'] == 'desconocida' for o in evaluable),
        'unidades_propuestas_desconocidas': sum(candidate(o)['unidad'] == 'desconocida' for o in paired),
        'omisiones': [o['id'] for o in evaluable if o['id'] not in primaries],
    }


def evaluar_lecturas(referencia, extraccion, correspondencias):
    """Puntúa propuestas originales; no usa valores corregidos ni oculta rechazados."""
    validar_referencia(referencia)
    consistente(extraccion, 'extraccion')
    for key in ('caso', 'alcance', 'sistema_coordenadas'):
        if referencia[key] != extraccion[key]:
            raise ErrorEvaluacion(f'{key}: referencia y extracción incompatibles.')
    if referencia['procedencia']['tipo'] != extraccion['procedencia']['tipo']:
        raise ErrorEvaluacion('No mezclar referencia sintética con extracción de expediente, o viceversa.')
    observations, candidates, used, primaries = validar_correspondencias(referencia, extraccion, correspondencias)
    values = list(observations.values())
    pages = sorted({(o['evidencia'][0]['archivo_id'], o['evidencia'][0]['pagina']) for o in values})
    return {
        'contrato': 'draft2model.evaluacion_lecturas', 'version_contrato': VERSION,
        'caso': referencia['caso'], 'alcance': copy.deepcopy(referencia['alcance']),
        'procedencia': copy.deepcopy(referencia['procedencia']),
        'datos_sinteticos': referencia['procedencia']['tipo'] == 'sintetico',
        'modo': 'propuestas_originales', 'aprobacion_ingenieria': None,
        'aviso': 'Evalúa lecturas y evidencia declarada; no valida estructura ni comprueba archivos físicos o identidad del revisor.',
        'huellas': {'referencia': huella(referencia), 'extraccion': huella(extraccion), 'correspondencias': huella(correspondencias)},
        'revisiones_declaradas': {'referencia': copy.deepcopy(referencia['revision']), 'correspondencias': copy.deepcopy(correspondencias['revision'])},
        'metricas': metricas(values, candidates, primaries),
        'por_tipo': {kind: metricas([o for o in values if o['tipo'] == kind], candidates, primaries) for kind in ('cota', 'etiqueta', 'elemento')},
        'por_lamina': [{'archivo_id': fid, 'pagina': page, 'metricas': metricas([o for o in values if (o['evidencia'][0]['archivo_id'], o['evidencia'][0]['pagina']) == (fid, page)], candidates, primaries)} for fid, page in pages],
        'candidatos_emitidos': len(candidates),
        'evidencia_confirmada_sobre_emitidos': proporcion(sum(p['evidencia_correcta'] for p in correspondencias['pares']), len(candidates)),
        'duplicados_declarados': [p['candidato_id'] for p in correspondencias['pares'] if not p['principal']],
        'sin_respaldo_declarados': list(correspondencias['sin_respaldo']),
        'sin_clasificar': sorted(candidates.keys() - used - set(correspondencias['sin_respaldo'])),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description='Evaluar propuestas de lectura con referencia revisada y correspondencias explícitas.')
    for field in ('referencia', 'extraccion', 'correspondencias', 'salida'):
        parser.add_argument('--' + field, type=Path, required=True)
    args = parser.parse_args(argv)
    created = False
    try:
        result = evaluar_lecturas(cargar_extraccion(args.referencia), cargar_extraccion(args.extraccion), cargar_extraccion(args.correspondencias))
        text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        with args.salida.open('x', encoding='utf-8') as output:
            created = True
            output.write(text)
    except (ValueError, OSError) as error:
        if created:
            args.salida.unlink(missing_ok=True)
        print('Evaluación no completada: ' + str(error), file=sys.stderr)
        return 1
    print('Evaluación de lecturas: ' + str(args.salida))
    print('Datos sintéticos.' if result['datos_sinteticos'] else 'Referencia y correspondencias declaradas; aprobación técnica pendiente.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
