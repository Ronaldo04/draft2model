"""Respuesta visual de prueba en la versión del paquete: 0.2.0 añade texto_fuente, simbolo y cobertura."""
import copy


def respuesta(req, sha, candidatos, *, cobertura=None):
    data = {'contrato': 'draft2model.respuesta_vision', 'version_contrato': req['version_contrato'],
            'solicitud_id': req['id'], 'solicitud_sha256': sha, 'candidatos': copy.deepcopy(candidatos)}
    if req['version_contrato'] == '0.2.0':
        for c in data['candidatos']:
            c.setdefault('texto_fuente', str(c['valor_propuesto']) if c['valor_propuesto'] is not None else 'ilegible')
            c.setdefault('simbolo', None)
        data['cobertura'] = cobertura if cobertura is not None else completar_cobertura(req, data['candidatos'])
    return data


def completar_cobertura(req, candidatos):
    usadas = {ev['imagen_id'] for c in candidatos for ev in c['evidencia']}
    return [{'imagen_id': im['id'], 'estado': 'completa' if im['id'] in usadas else 'sin_lecturas', 'observacion': ''}
            for im in req['imagenes'] if im['admite_evidencia']]
