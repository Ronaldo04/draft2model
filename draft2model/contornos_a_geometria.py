"""Incorporación transaccional de contornos desde digitizaciones reproducibles.

Función pura: el servicio llamante verifica originales/archivos y suministra sus
registros consultados. Aquí se reproducen números y vínculos, no se autentican
documentos ni correspondencias visuales. Nunca se crea aprobación.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re

from . import contratos as c
from . import digitizacion_calibrada as dc
from . import lectura_contornos as lc
from .validacion_geometria import validar_geometria


def _exigir(ok, mensaje):
    if not ok:
        raise ValueError(mensaje)


def _validar_lectura(lectura):
    _exigir(isinstance(lectura, dict) and {'datos', 'contexto', 'huella_lectura', 'revision', 'ejecutable_etabs'} <= set(lectura), 'Se requiere lectura validada enriquecida.')
    datos, contexto = lectura['datos'], lc.validar_contexto(lectura['contexto'])
    _exigir(lectura['ejecutable_etabs'] is False and lectura['huella_lectura'] == lc.huella({'datos': datos, 'contexto': contexto}), 'Lectura alterada o con banderas incompatibles.')
    raw = copy.deepcopy(datos)
    sources = {}
    paginas = set()
    for e in raw['evidencias']:
        sha = e.pop('original_sha256')
        _exigir(e['archivo_id'] not in sources or sources[e['archivo_id']] == sha, 'Hashes de original contradictorios.')
        sources[e['archivo_id']] = sha; paginas.add((e['archivo_id'], e['pagina']))
    for d in raw['dibujos']:
        f = d.pop('fuente'); d.pop('plano')
        _exigir(d['archivo_id'] not in sources or sources[d['archivo_id']] == f['sha256'], 'Fuente de dibujo contradictoria.')
        sources[d['archivo_id']] = f['sha256']; paginas.add((d['archivo_id'], d['pagina']))
    checked = lc.validar_respuesta(raw, {'id': datos['caso'], 'archivos': [{'id': k, 'sha256': v} for k, v in sources.items()]}, paginas, contexto)
    _exigir(checked['datos'] == datos and checked['huella_lectura'] == lectura['huella_lectura'], 'Enriquecimiento de lectura alterado.')
    return datos, contexto


def _forma_refs(rows, puntos=False):
    result = []
    for row in rows:
        item = {'id': row['id'], 'uv_local': row['uv_local']}
        if puntos:
            item['relacionados'] = sorted(row['relacionados'])
        else:
            item['punto_resuelto'] = row['punto_resuelto']
        result.append(item)
    return sorted(result, key=lambda r: r['id'])


def _reproducir(dibujo, registro, geometria, contexto):
    _exigir(isinstance(registro, dict) and registro.get('vigente') is True, 'Falta registro consultado como vigente; la bandera sola no basta.')
    almacenado = {k: v for k, v in registro.items() if k not in {'vigente', 'sha256_registro'}}
    sin_huella = {k: v for k, v in almacenado.items() if k != 'huella_version'}
    _exigir(registro.get('huella_version') == lc.huella(sin_huella), 'Huella de versión de digitización incorrecta.')
    sha_bytes = hashlib.sha256(lc.canonico(almacenado)+b'\n').hexdigest()
    _exigir(registro.get('sha256_registro') == sha_bytes, 'SHA de registro de digitización incorrecto.')
    _exigir(registro.get('contrato') == 'draft2model.revision_digitizacion' and registro.get('version') == '0.1.0' and registro.get('etapa') == 'calculada', 'Registro de otro contrato/etapa.')
    _exigir(registro.get('caso') == geometria['id'] and registro.get('datos_sinteticos') is contexto['geometria']['datos_sinteticos'], 'Digitización de otro caso/naturaleza.')
    _exigir(registro.get('revision') == {'estado': 'borrador', 'aprobacion': None} and all(registro.get(k) is False for k in ('aprueba_ingenieria', 'disponible_para_modelado', 'ejecuta_etabs')), 'Digitización con aprobación o banderas no permitidas.')
    origen = registro['geometria_origen']; cg = contexto['geometria']
    _exigir(all(origen.get(k) == cg[k] for k in ('version_id', 'sha256_geometria', 'huella_contenido', 'unidad_longitud')), 'Digitización vinculada a otra geometría.')
    fuente, plano = dibujo['fuente'], dibujo['plano']
    _exigir(registro['fuente_vigente'] == fuente and registro['plano'] == plano, 'Original/página/ROI/dibujo/plano de digitización ajenos.')
    prop = registro['propuesta']
    _exigir(prop['id'] == dibujo['id'] and prop['fuente'] == fuente and prop['plano'] == plano, 'Propuesta de digitización diferente al dibujo leído.')
    for group in ('anclas', 'controles', 'puntos'):
        _exigir(_forma_refs(prop[group], group == 'puntos') == _forma_refs(dibujo[group], group == 'puntos'), 'Correspondencias/puntos de digitización distintos a la propuesta leída.')
        _exigir(all(row.get('fuente') == fuente and row.get('plano_id') == plano['id'] for row in prop[group]), 'Puntos con fuente/plano mezclados.')
    hashes = registro['hashes_entradas']
    _exigir(hashes.get('original_sha256') == fuente['sha256'] and hashes.get('sha256_geometria') == cg['sha256_geometria'] and
            hashes.get('geometria_id') == cg['version_id'] and hashes.get('huella_geometria') == cg['huella_contenido'] and
            hashes.get('expediente_sha256') == registro['expediente_sha256'], 'Huellas de entradas de digitización inconsistentes.')
    _exigir(all(isinstance(hashes.get(k), str) and re.fullmatch('[0-9a-f]{64}', hashes[k]) for k in
                ('preview_sha256', 'huella_catalogo_referencias')) and
            registro['evidencia_fuente']['preview_sha256'] == hashes['preview_sha256'] and
            lc.huella(registro['catalogo_referencias']) == hashes['huella_catalogo_referencias'] and
            {k: registro['fuente_solicitud'][k] for k in dc.FUENTE} == fuente,
            'Vista previa, catálogo o solicitud de fuente inconsistentes.')
    codigo = registro.get('hashes_codigo')
    _exigir(isinstance(codigo, dict) and {'revision_digitizacion.py', 'digitizacion_calibrada.py', 'revision_superposicion.py'} <= set(codigo) and
            all(isinstance(v, str) and re.fullmatch('[0-9a-f]{64}', v) for v in codigo.values()), 'Faltan huellas de código del registro consultado.')
    vertices = {v['id']: v for v in geometria['vertices']}
    catalogo = lc.registros(registro['catalogo_referencias'])
    resueltos = {}; advertencias = []
    usados = {r['punto_resuelto'] for g in ('anclas', 'controles') for r in prop[g]}
    for ident in sorted(usados):
        _exigir(ident in vertices and ident in catalogo and catalogo[ident].get('utilizable_en_fuente') is True, 'Referencia métrica ajena o no utilizable en el original.')
        v = vertices[ident]
        _exigir(float(v[plano['eje_constante']]) == plano['valor_constante'], 'Referencia de otra cota/plano.')
        coords = [float(v[e]) for e in plano['ejes']]
        proc = v['procedencia']; refs = proc.get('referencias')
        refs = list(refs) if isinstance(refs, list) and refs else ['descriptor_geometrico:'+cg['version_id']]
        if refs == ['descriptor_geometrico:'+cg['version_id']]:
            advertencias.append('Referencia '+ident+': solo descriptor geométrico, sin ubicación documental acreditada.')
        huella_res = lc.huella({'caso': geometria['id'], 'geometria_id': cg['version_id'], 'sha256_geometria': cg['sha256_geometria'],
                              'huella_geometria': cg['huella_contenido'], 'vertice_id': ident, 'coordenadas': coords,
                              'unidad_longitud': plano['unidad_longitud'], 'plano': plano, 'procedencia': proc})
        _exigir(catalogo[ident]['coordenadas'] == coords and catalogo[ident]['huella_resolucion'] == huella_res, 'Catálogo de referencias no corresponde a vértices originales.')
        resueltos[ident] = {'coordenadas': coords, 'unidad_longitud': plano['unidad_longitud'], 'plano': copy.deepcopy(plano),
                           'fuente': copy.deepcopy(fuente), 'huella_resolucion': huella_res, 'referencias': refs}
    resultado = dc.calibrar_digitizacion(prop, fuente_vigente=fuente, puntos_resueltos=resueltos)
    _exigir(lc.canonico(resultado) == lc.canonico(registro['resultado']) and registro.get('sha256_resultado') == hashlib.sha256(lc.canonico(resultado)+b'\n').hexdigest() and
            hashes.get('huella_entrada_modulo') == resultado['huella_entrada'], 'Resultado de digitización no reproducible desde geometría original.')
    resumen = registro.get('resumen', {})
    _exigir(resumen.get('exactitud_documental_acreditada') is False and all(resumen.get(k, False) is False for k in ('aprueba_ingenieria', 'disponible_para_modelado', 'ejecuta_etabs', 'integra_al_modelo')), 'Resumen contiene acreditación/aprobación no permitida.')
    _exigir(resultado['calculo_posible'] is True and resultado['residuo_ajuste_max_m'] <= prop['limites']['residuo_ajuste_max_m'], 'Ajuste fuera de los límites declarados.')
    _exigir(resultado['error_control_max_m'] is None or resultado['error_control_max_m'] <= prop['limites']['error_control_max_m'], 'Error de control fuera del límite declarado.')
    _exigir(all(p['incertidumbre']['dentro_limite'] and p['incertidumbre']['indicador_m'] <= prop['limites']['incertidumbre_max_m'] for p in resultado['puntos']), 'Puntos exceden incertidumbre máxima declarada.')
    if not resultado['exactitud_verificada_en_controles']:
        advertencias.append('Dibujo '+dibujo['id']+': sin exactitud contrastada en al menos tres controles independientes.')
    if any(p['extrapolacion'] for p in resultado['puntos']):
        advertencias.append('Dibujo '+dibujo['id']+': incluye extrapolación fuera de las anclas, conservada en borrador.')
    advertencias.append('Dibujo '+dibujo['id']+': correspondencias propuestas; exactitud documental no acreditada ni aprobación de ingeniería.')
    return resultado, advertencias


def incorporar_contornos(geometria, lectura_validada, digitizaciones_comprobadas):
    """Añadir una lectura completa o devolver base intacta salvo revisión/gaps.

    `digitizaciones_comprobadas` es dibujoID→respuesta íntegra de consultar real.
    No autentica sus bytes aquí: comprueba hash, vínculos y reproduce el cálculo.
    """
    base = copy.deepcopy(geometria)
    validacion_base = validar_geometria(base)
    _exigir(base.get('version_contrato') == c.VERSION_GEOMETRIA_ABERTURAS and validacion_base.consistente, 'Geometría base 0.3.0 inconsistente.')
    datos, contexto = _validar_lectura(lectura_validada)
    cg = contexto['geometria']
    _exigir(datos['caso'] == base['id'] and cg['huella_contenido'] == validacion_base.huella_contenido and
            cg['sha256_geometria_canonica'] == lc.huella(base) and cg['datos_sinteticos'] is validacion_base.datos_sinteticos and
            cg['unidad_longitud'] == base['unidad_longitud'], 'Lectura de otra geometría, revisión o naturaleza.')
    vertices = {v['id']: v for v in base['vertices']}
    _exigir(set(contexto['puntos_resueltos']) <= set(vertices) and set(contexto['superficies']) <= {s['id'] for s in base['superficies']}, 'Contexto refiere entidades geométricas inexistentes.')
    if 'catalogo_vertices' in contexto:
        _exigir(all(v == vertices[v['id']] for v in contexto['catalogo_vertices']), 'Catálogo espacial contextual alterado respecto de geometría base.')
    for plano in contexto['planos']:
        _exigir(all(float(vertices[i][plano['eje_constante']]) == float(plano['valor_constante']) for i in plano['puntos_resueltos']), 'Catálogo de plano contradice geometría original.')
    _exigir(isinstance(digitizaciones_comprobadas, dict), 'Registro de digitizaciones requerido.')
    dibujos = lc.registros(datos['dibujos']); resultados = {}; pendientes = []; conflictos = []; advertencias = list(lectura_validada.get('advertencias', []))
    for ident, dibujo in sorted(dibujos.items()):
        if ident not in digitizaciones_comprobadas:
            pendientes.append({'tipo': 'digitizacion_ausente', 'id': ident, 'motivo': 'Falta registro comprobado del dibujo.'}); continue
        try:
            resultado, avisos = _reproducir(dibujo, digitizaciones_comprobadas[ident], base, contexto)
            resultados[ident] = resultado; advertencias += avisos
        except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
            conflictos.append({'tipo': 'digitizacion_invalida', 'id': ident, 'motivo': str(exc)})
    usados = {item['id'] for group in ('niveles', 'nodos', 'muros', 'vertices', 'superficies', 'aberturas') for item in base[group]} | set(contexto['frames'])
    copia = copy.deepcopy(base); frames = []; agregados = {'vertices': [], 'superficies': [], 'aberturas': [], 'frames': []}
    tabla_evidencias = lc.registros(datos['evidencias']); traza = []

    def reservar(ident):
        if ident in usados:
            conflictos.append({'tipo': 'colision_id', 'id': ident, 'motivo': 'ID nuevo colisiona; no se sobrescribe ni mueve el existente.'})
            return False
        usados.add(ident); return True

    def procedencia(eids, dids, descripcion):
        proc = copy.deepcopy(base['procedencia'])
        proc['descripcion'] = descripcion+'; correspondencia/topología propuestas sin aprobación ni exactitud documental acreditada.'
        dependencias = sorted({ref for d in dids if d in resultados for group in ('anclas', 'controles')
                               for r in resultados[d][group] for ref in r['referencias']})
        proc['referencias'] = dependencias + ['contornos:'+lectura_validada['huella_lectura']+':'+i for i in sorted(eids)] + [
            'digitizacion:'+digitizaciones_comprobadas[d]['id']+':'+digitizaciones_comprobadas[d]['huella_version'] for d in sorted(dids) if d in resultados]
        fuentes = sorted({dibujos[d]['archivo_id'] for d in dids})
        proc['lamina'] = ','.join(fuentes)
        return proc

    divisor = c.DIVISORES_A_METROS[base['unidad_longitud']]
    for did, dibujo in sorted(dibujos.items()):
        if did not in resultados:
            continue
        calculados = {p['id']: p for p in resultados[did]['puntos']}
        for punto in sorted(dibujo['puntos'], key=lambda p: p['id']):
            ident = punto['id']
            if not reservar(ident):
                continue
            metrica = calculados[ident]['coordenadas_m']
            xyz = {k: metrica[k]*divisor for k in ('x', 'y', 'z')}
            if not all(math.isfinite(v) and v/divisor == metrica[k] for k, v in xyz.items()):
                conflictos.append({'tipo': 'conversion_unidad', 'id': ident, 'motivo': 'Coordenadas no representables exactamente en unidad de geometría.'}); continue
            copia['vertices'].append({'id': ident, **xyz, 'procedencia': procedencia(punto['evidencias'], [did], 'Punto calculado mediante calibración afín local')})
            agregados['vertices'].append(ident)
            traza.append({'coleccion': 'vertices', 'id': ident, 'dibujo': did,
                          'registro_digitizacion': digitizaciones_comprobadas[did]['id'], 'huella_entrada_calculo': resultados[did]['huella_entrada'],
                          'fuente': copy.deepcopy(dibujo['fuente']), 'plano': copy.deepcopy(dibujo['plano']),
                          'incertidumbre': copy.deepcopy(calculados[ident]['incertidumbre']), 'extrapolacion': calculados[ident]['extrapolacion'],
                          'evidencias': [copy.deepcopy(tabla_evidencias[i]) for i in sorted(punto['evidencias'])]})
    existentes = {v['id'] for v in copia['vertices']}
    for elem in sorted(datos['elementos'], key=lambda e: e['id']):
        if not reservar(elem['id']):
            continue
        if not set(elem['vertices']) <= existentes or not set(elem['dibujos']) <= set(resultados):
            pendientes.append({'tipo': 'topologia_sin_metricas', 'id': elem['id'], 'motivo': 'Entidad sin puntos/dibujos reproducibles.'}); continue
        proc = procedencia(elem['evidencias'], elem['dibujos'], 'Contorno nuevo propuesto de tipo '+elem['tipo'])
        if elem['tipo'] in ('columna', 'viga'):
            vmap = {v['id']: v for v in copia['vertices']}
            a, b = [tuple(vmap[i][k] for k in ('x', 'y', 'z')) for i in elem['vertices']]
            if a == b:
                conflictos.append({'tipo': 'frame_nulo', 'id': elem['id'], 'motivo': 'Extremos coincidentes físicamente.'}); continue
            frames.append({'id': elem['id'], 'tipo': elem['tipo'], 'puntos': list(elem['vertices']),
                           'evidencias': [copy.deepcopy(tabla_evidencias[i]) for i in sorted(elem['evidencias'])], 'procedencia': proc})
            agregados['frames'].append(elem['id'])
        else:
            copia['superficies'].append({'id': elem['id'], 'vertices': list(elem['vertices']), 'papel_geometrico': elem['tipo'], 'procedencia': proc})
            agregados['superficies'].append(elem['id'])
    for abertura in sorted(datos['aberturas'], key=lambda a: a['id']):
        if not reservar(abertura['id']):
            continue
        if not set(abertura['vertices']) <= existentes or not set(abertura['dibujos']) <= set(resultados):
            pendientes.append({'tipo': 'abertura_sin_metricas', 'id': abertura['id'], 'motivo': 'Abertura sin puntos/dibujos reproducibles.'}); continue
        copia['aberturas'].append({'id': abertura['id'], 'superficie': abertura['host'], 'vertices': list(abertura['vertices']),
                                  'procedencia': procedencia(abertura['evidencias'], abertura['dibujos'], 'Vano nuevo propuesto explícitamente')})
        agregados['aberturas'].append(abertura['id'])
    advertencias = sorted(set(advertencias))
    if not any(agregados.values()) and not pendientes and not conflictos:
        pendientes.append({'tipo': 'sin_nuevos_contornos', 'id': base['id'], 'motivo': 'La lectura no contiene puntos o entidades nuevos respaldados.'})
    copia['revision'] = {'estado': 'borrador', 'aprobacion': None}
    validacion = validar_geometria(copia)
    if not validacion.consistente:
        conflictos.append({'tipo': 'geometria_propuesta_invalida', 'motivo': 'La topología propuesta no supera validar_geometria.',
                           'errores': [vars(e) for e in validacion.errores]})
    aplicado = not pendientes and not conflictos
    if not aplicado:
        copia = copy.deepcopy(base); frames = []; agregados = {k: [] for k in agregados}; traza = []
        copia['revision'] = {'estado': 'borrador', 'aprobacion': None}
    gaps = list(datos['faltantes']) + advertencias + [p['motivo'] for p in pendientes+conflictos]
    for descripcion in dict.fromkeys(gaps):
        fila = {'descripcion': descripcion}
        if fila not in copia['faltantes']:
            copia['faltantes'].append(fila)
    return {'geometria': copia, 'aplicado': aplicado, 'transaccion_completa': aplicado,
            'agregados': agregados, 'frames_propuestos': frames, 'pendientes': pendientes,
            'conflictos': conflictos, 'advertencias': advertencias, 'faltantes': copy.deepcopy(copia['faltantes']),
            'trazabilidad': traza, 'lectura_conservada': copy.deepcopy(lectura_validada),
            'validacion': validar_geometria(copia).a_dict(), 'validacion_propuesta': validacion.a_dict(),
            'origen': copy.deepcopy(cg), 'revision_anterior': copy.deepcopy(base['revision']),
            'completo': False, 'aprueba_ingenieria': False, 'ejecutable_etabs': False}
