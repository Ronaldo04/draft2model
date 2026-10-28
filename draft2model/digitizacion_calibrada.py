"""Propuestas afines locales desde anclas métricas resueltas, siempre en borrador.

Sin E/S, lectura de imágenes, inferencia de unidades ni aprobaciones. La fuente
vigente y el registro de puntos resueltos son entradas de confianza del servicio.
Ver docs/DIGITIZACION_CALIBRADA.md para contrato y alcance de los controles.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re

from .revision_superposicion import aplicar, transformacion, ErrorSuperposicion

CONTRATO = 'draft2model.digitizacion_calibrada'
VERSION = '0.1.0'
DIVISORES = {'m': 1, 'cm': 100, 'mm': 1000}
FUENTE = {'original_id', 'sha256', 'pagina', 'dibujo_id', 'bbox_pagina'}
LIMITES = {'residuo_ajuste_max_m', 'error_control_max_m', 'incertidumbre_max_m',
           'localizacion_uv', 'referencia_m', 'condicion_max',
           'escala_min_m_por_uv', 'escala_max_m_por_uv', 'coordenada_abs_max_m'}


class ErrorDigitizacion(ValueError):
    """Rechazo trazable de contrato o cálculo; detalles son serializables."""
    def __init__(self, codigo, mensaje, **detalles):
        super().__init__(mensaje)
        self.codigo = codigo
        self.detalles = detalles


def _exigir(condicion, codigo, mensaje, **detalles):
    if not condicion:
        raise ErrorDigitizacion(codigo, mensaje, **detalles)


def _campos(obj, campos, ruta):
    _exigir(isinstance(obj, dict) and set(obj) == set(campos), 'contrato',
            f'{ruta}: campos obligatorios exactos; no se admiten campos adicionales.')


def _numero(valor, ruta, positivo=False):
    try:
        valido = type(valor) in (int, float) and math.isfinite(valor)
        convertido = float(valor) if valido else None
    except (OverflowError, ValueError):
        valido, convertido = False, None
    _exigir(valido and (not positivo or convertido > 0), 'numero',
            f'{ruta}: número finito representable' + (' positivo.' if positivo else '.'))
    return convertido


def _id(valor, ruta):
    _exigir(isinstance(valor, str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', valor) is not None,
            'identificador', f'{ruta}: identificador inválido.')
    return valor


def _sha(valor, ruta):
    _exigir(isinstance(valor, str) and re.fullmatch('[0-9a-f]{64}', valor) is not None,
            'huella', f'{ruta}: SHA256 inválido.')


def _vector(valor, n, ruta):
    _exigir(isinstance(valor, list) and len(valor) == n, 'contrato', f'{ruta}: lista de {n} números.')
    return [_numero(v, ruta) for v in valor]


def _fuente(fuente):
    _campos(fuente, FUENTE, 'fuente')
    _id(fuente['original_id'], 'original_id'); _id(fuente['dibujo_id'], 'dibujo_id')
    _sha(fuente['sha256'], 'fuente.sha256')
    _exigir(type(fuente['pagina']) is int and fuente['pagina'] >= 1, 'pagina', 'Página desde 1.')
    x0, y0, x1, y1 = _vector(fuente['bbox_pagina'], 4, 'bbox_pagina')
    _exigir(0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1, 'bbox', 'BBox normalizado de página inválido.')


def _uv(valor):
    u, v = _vector(valor, 2, 'uv_local')
    _exigir(0 <= u <= 1 and 0 <= v <= 1, 'fuera_dibujo', 'Punto fuera del dibujo local [0,1]².')
    return [u, v]


def _espectro(a, b, c):
    """Autovalores de matriz simétrica 2x2 sin cancelación en el menor."""
    mayor = (a + c + math.hypot(a - c, 2 * b)) / 2
    menor = (a * c - b * b) / mayor if mayor > 0 else 0
    return mayor, menor


def _diseno(uv, limite):
    n = len(uv)
    centro = [math.fsum(p[k] for p in uv) / n for k in (0, 1)]
    delta = [[p[k] - centro[k] for k in (0, 1)] for p in uv]
    a = math.fsum(p[0] ** 2 for p in delta)
    b = math.fsum(p[0] * p[1] for p in delta)
    c = math.fsum(p[1] ** 2 for p in delta)
    mayor, menor = _espectro(a, b, c)
    _exigir(menor > 0 and math.sqrt(mayor / menor) <= limite,
            'anclas_degeneradas', 'Anclas colineales o mal condicionadas.')
    det = a * c - b * b
    return centro, delta, (c / det, -b / det, a / det), math.sqrt(mayor / menor)


def _ajuste(uv, xy, limite):
    centro, delta, inv, condicion = _diseno(uv, limite)
    if len(uv) == 3:
        # Reutiliza el afín existente, que exige además MIN_FORMA=1e-3.
        try:
            matriz = transformacion(uv, xy)
        except ErrorSuperposicion as exc:
            raise ErrorDigitizacion('anclas_degeneradas', str(exc)) from exc
    else:
        matriz = []
        for k in (0, 1):
            media = math.fsum(p[k] for p in xy) / len(xy)
            du = math.fsum(p[0] * (q[k] - media) for p, q in zip(delta, xy))
            dv = math.fsum(p[1] * (q[k] - media) for p, q in zip(delta, xy))
            a, b = inv[0] * du + inv[1] * dv, inv[1] * du + inv[2] * dv
            matriz.append([a, b, media - a * centro[0] - b * centro[1]])
    return matriz, centro, delta, inv, condicion


def _huella(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False, separators=(',', ':')).encode('utf-8')).hexdigest()


def _en_casco(p, uv):
    """Casco convexo: informa extrapolación sin inferir continuidad estructural."""
    puntos = sorted(set(tuple(v) for v in uv))
    def cruz(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    inferior, superior = [], []
    for q in puntos:
        while len(inferior) >= 2 and cruz(inferior[-2], inferior[-1], q) <= 0:
            inferior.pop()
        inferior.append(q)
    for q in reversed(puntos):
        while len(superior) >= 2 and cruz(superior[-2], superior[-1], q) <= 0:
            superior.pop()
        superior.append(q)
    casco = inferior[:-1] + superior[:-1]
    return all(cruz(a, b, p) >= -1e-14 for a, b in zip(casco, casco[1:] + casco[:1]))


def calibrar_digitizacion(propuesta, *, fuente_vigente, puntos_resueltos):
    """Interfaz pura; los rechazos de contrato/cálculo usan ErrorDigitizacion."""
    try:
        return _calibrar(propuesta, fuente_vigente=fuente_vigente, puntos_resueltos=puntos_resueltos)
    except ErrorDigitizacion:
        raise
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise ErrorDigitizacion('entrada_o_calculo_no_representable',
                                'Contrato inválido o cálculo no representable en binary64.') from exc


def _calibrar(propuesta, *, fuente_vigente, puntos_resueltos):
    """Calibrar un único dibujo/plano; entradas intactas, salida JSON en metros.

    `puntos_resueltos` es un registro externo confiable, no coordenadas propuestas
    por IA. Los controles quedan excluidos del ajuste. No emite geometría aprobada.
    """
    _campos(propuesta, {'contrato', 'version', 'id', 'fuente', 'plano', 'limites',
                        'anclas', 'controles', 'puntos'}, 'propuesta')
    _exigir(propuesta['contrato'] == CONTRATO and propuesta['version'] == VERSION,
            'version', 'Contrato o versión no soportado.')
    _id(propuesta['id'], 'id')
    _fuente(fuente_vigente); _fuente(propuesta['fuente'])
    fuente = propuesta['fuente']
    _exigir(fuente == fuente_vigente, 'fuente_no_vigente', 'Original/SHA/página/dibujo/bbox cambiados.')
    plano = propuesta['plano']
    _campos(plano, {'id', 'ejes', 'eje_constante', 'valor_constante', 'unidad_longitud'}, 'plano')
    _id(plano['id'], 'plano.id')
    _exigir(plano['ejes'] in (['x', 'y'], ['x', 'z'], ['y', 'z']) and
            plano['eje_constante'] in {'x', 'y', 'z'} - set(plano['ejes']),
            'plano', 'Declarar dos ejes cartesianos y el tercer eje constante.')
    _exigir(plano['unidad_longitud'] in DIVISORES, 'unidad', 'Unidad explícita m, cm o mm.')
    cota_original = _numero(plano['valor_constante'], 'valor_constante')
    cota = cota_original / DIVISORES[plano['unidad_longitud']]
    _exigir(cota_original == 0 or cota != 0, 'normalizacion', 'La cota se pierde al normalizar.')
    lim = propuesta['limites']
    _campos(lim, LIMITES, 'limites')
    lim = {k: _numero(v, k, positivo=True) for k, v in lim.items()}
    _exigir(lim['condicion_max'] >= 1 and lim['escala_min_m_por_uv'] < lim['escala_max_m_por_uv']
            and lim['localizacion_uv'] <= 1, 'limites', 'Rangos de condición/escala/localización inválidos.')
    _exigir(abs(cota) <= lim['coordenada_abs_max_m'], 'limite_fisico', 'Cota fuera del límite declarado.')
    _exigir(isinstance(puntos_resueltos, dict), 'contrato', 'Registro de puntos resueltos requerido.')
    usados, coordenadas, ubicaciones, referencias = set(), set(), set(), set()
    ids = set()

    def referencias_metricas(items, controles=False):
        _exigir(isinstance(items, list) and len(items) <= 1000, 'contrato', 'Lista de referencias hasta 1000.')
        salida = []
        for item in items:
            _campos(item, {'id', 'punto_resuelto', 'uv_local', 'fuente', 'plano_id'}, 'referencia')
            ident = _id(item['id'], 'referencia.id')
            punto_id = _id(item['punto_resuelto'], 'punto_resuelto')
            _exigir(ident not in ids and punto_id not in usados, 'referencia_repetida', 'Referencia repetida entre ajuste/controles.')
            ids.add(ident); usados.add(punto_id)
            _fuente(item['fuente'])
            _exigir(item['fuente'] == fuente and item['plano_id'] == plano['id'],
                    'fuente_mezclada', 'Referencia de otro original, dibujo, página o plano.')
            uv = _uv(item['uv_local'])
            _exigir(punto_id in puntos_resueltos, 'punto_no_resuelto', 'No existe la referencia métrica resuelta.')
            punto = puntos_resueltos[punto_id]
            _campos(punto, {'coordenadas', 'unidad_longitud', 'plano', 'fuente',
                            'huella_resolucion', 'referencias'}, 'punto_resuelto')
            _fuente(punto['fuente'])
            _campos(punto['plano'], set(plano), 'punto_resuelto.plano')
            _numero(punto['plano']['valor_constante'], 'punto_resuelto.plano.valor_constante')
            _exigir(punto['fuente'] == fuente and punto['plano'] == plano,
                    'fuente_mezclada', 'Punto resuelto de otra fuente o plano.')
            _sha(punto['huella_resolucion'], 'huella_resolucion')
            unidad = punto['unidad_longitud']
            _exigir(isinstance(unidad, str) and unidad in DIVISORES, 'unidad', 'Unidad métrica resuelta no soportada.')
            bruto = _vector(punto['coordenadas'], 2, 'coordenadas')
            xy = [v / DIVISORES[unidad] for v in bruto]
            _exigir(all(v == 0 or m != 0 for v, m in zip(bruto, xy)), 'normalizacion', 'Coordenada perdida al normalizar.')
            _exigir(max(map(abs, xy)) <= lim['coordenada_abs_max_m'], 'limite_fisico', 'Referencia fuera del límite declarado.')
            refs = punto['referencias']
            _exigir(isinstance(refs, list) and refs and all(isinstance(r, str) for r in refs),
                    'evidencia', 'Referencias documentales de resolución obligatorias.')
            for r in refs:
                _id(r, 'referencia_documental')
            _exigir(len(set(refs)) == len(refs), 'evidencia', 'Referencias documentales duplicadas.')
            _exigir(tuple(uv) not in ubicaciones and tuple(xy) not in coordenadas,
                    'referencia_repetida', 'Anclas/controles deben ser puntos físicos distintos.')
            if controles:
                _exigir(not (set(refs) & referencias), 'control_dependiente',
                        'Control comparte referencias de resolución con el ajuste.')
            else:
                referencias.update(refs)
            ubicaciones.add(tuple(uv)); coordenadas.add(tuple(xy))
            salida.append({'id': ident, 'punto_resuelto': punto_id, 'uv_local': uv, 'xy_m': xy,
                           'huella_resolucion': punto['huella_resolucion'], 'referencias': copy.deepcopy(refs)})
        return salida

    anclas = referencias_metricas(propuesta['anclas'])
    _exigir(len(anclas) >= 3, 'anclas_insuficientes', 'Al menos tres anclas métricas no colineales.')
    controles = referencias_metricas(propuesta['controles'], controles=True)
    uv, xy = [a['uv_local'] for a in anclas], [a['xy_m'] for a in anclas]
    matriz, centro, delta, inv, condicion = _ajuste(uv, xy, lim['condicion_max'])
    _exigir(all(math.isfinite(v) for f in matriz for v in f), 'no_finito', 'Ajuste no representable.')
    a, b = matriz[0][:2]; c, d = matriz[1][:2]
    # Normalización evita overflow al formar A^T A.
    escala = max(abs(a), abs(b), abs(c), abs(d))
    _exigir(escala > 0, 'transformacion_degenerada', 'Transformación sin escala.')
    aa, bb, cc, dd = a / escala, b / escala, c / escala, d / escala
    mayor, menor = _espectro(aa*aa+cc*cc, aa*bb+cc*dd, bb*bb+dd*dd)
    smax, smin = escala * math.sqrt(mayor), escala * math.sqrt(max(0, menor))
    _exigir(smin >= lim['escala_min_m_por_uv'] and smax <= lim['escala_max_m_por_uv']
            and smin > 0 and smax / smin <= lim['condicion_max'], 'transformacion_degenerada',
            'Escalas singulares/condición fuera de los límites declarados.')

    def residuos(items):
        for item in items:
            predicho = list(aplicar(matriz, *item['uv_local']))
            item['predicho_m'] = predicho
            item['residuo_m'] = math.dist(predicho, item['xy_m'])
            _exigir(all(math.isfinite(v) for v in predicho) and math.isfinite(item['residuo_m']),
                    'no_finito', 'Residuo no representable.')
        return max((i['residuo_m'] for i in items), default=0.0)

    residuo = residuos(anclas)
    error_control = residuos(controles)
    _exigir(residuo <= lim['residuo_ajuste_max_m'], 'residuo_excesivo',
            'Ajuste excede la tolerancia declarada.', residuo_max_m=residuo, anclas=anclas)
    controles_distribuidos = False
    if len(controles) >= 3:
        try:
            _diseno([p['uv_local'] for p in controles], lim['condicion_max'])
            controles_distribuidos = True
        except ErrorDigitizacion:
            pass
    exactitud = controles_distribuidos and error_control <= lim['error_control_max_m']
    puntos = propuesta['puntos']
    _exigir(isinstance(puntos, list) and 0 < len(puntos) <= 10000, 'contrato', 'Entre 1 y 10000 puntos propuestos.')
    nuevos = []
    for punto in puntos:
        _campos(punto, {'id', 'uv_local', 'fuente', 'plano_id', 'relacionados'}, 'punto')
        ident = _id(punto['id'], 'punto.id')
        _exigir(ident not in ids, 'identificador_repetido', 'ID de punto repetido.')
        ids.add(ident)
        _fuente(punto['fuente'])
        _exigir(punto['fuente'] == fuente and punto['plano_id'] == plano['id'],
                'fuente_mezclada', 'Punto propuesto de otra fuente o plano.')
        relacionados = punto['relacionados']
        _exigir(isinstance(relacionados, list) and relacionados and
                all(isinstance(r, str) and r in usados for r in relacionados) and len(set(relacionados)) == len(relacionados),
                'relaciones', 'Relacionar el punto con IDs métricos resueltos del ajuste/controles.')
        p = _uv(punto['uv_local'])
        metricas = list(aplicar(matriz, *p))
        _exigir(all(math.isfinite(v) and abs(v) <= lim['coordenada_abs_max_m'] for v in metricas),
                'limite_fisico', 'Punto transformado fuera del límite declarado.')
        du, dv = p[0] - centro[0], p[1] - centro[1]
        pesos = [1/len(anclas) + (du*inv[0]+dv*inv[1])*q[0] +
                 (du*inv[1]+dv*inv[2])*q[1] for q in delta]
        amplificacion = math.fsum(abs(w) for w in pesos)
        propagacion = smax * lim['localizacion_uv'] * (1 + amplificacion)
        referencia_ajuste = amplificacion * (lim['referencia_m'] + residuo)
        indicador = propagacion + referencia_ajuste + error_control
        _exigir(math.isfinite(indicador), 'no_finito', 'Incertidumbre no representable.')
        xyz = dict(zip(plano['ejes'], metricas)); xyz[plano['eje_constante']] = cota
        x0, y0, x1, y1 = fuente['bbox_pagina']
        nuevos.append({'id': ident, 'uv_local': p,
                       'uv_pagina': [x0+p[0]*(x1-x0), y0+p[1]*(y1-y0)], 'coordenadas_m': xyz,
                       'relacionados': copy.deepcopy(relacionados),
                       'extrapolacion': not _en_casco(p, uv),
                       'incertidumbre': {'tipo': 'indicador_conservador_no_estadistico',
                                        'alcance': 'dos_ejes_del_plano; cota_constante_declarada_sin_validar',
                                        'localizacion_m': propagacion, 'referencia_y_ajuste_m': referencia_ajuste,
                                        'control_max_m': error_control, 'amplificacion': amplificacion,
                                        'indicador_m': indicador,
                                        'dentro_limite': indicador <= lim['incertidumbre_max_m']}})
    entrada = {'propuesta': propuesta, 'fuente_vigente': fuente_vigente,
               'puntos_resueltos_usados': {k: puntos_resueltos[k] for k in sorted(usados)}}
    return {'contrato': CONTRATO + '.resultado', 'version': VERSION, 'id': propuesta['id'],
            'huella_entrada': _huella(entrada), 'fuente': copy.deepcopy(fuente),
            'plano_declarado': copy.deepcopy(plano), 'unidad_longitud': 'm',
            'limites_declarados': copy.deepcopy(lim), 'calculo_posible': True,
            'exactitud_verificada_en_controles': exactitud,
            'alcance_exactitud': 'Solo controles separados del ajuste y sus correspondencias declaradas; no certifica el resto del dibujo.',
            'controles_distribuidos': controles_distribuidos,
            'transformacion': {'tipo': 'afin_2d_minimos_cuadrados', 'matriz_local_a_m': matriz,
                              'condicion_diseno': condicion, 'escalas_singulares_m_por_uv': [smin, smax]},
            'residuo_ajuste_max_m': residuo, 'error_control_max_m': error_control if controles else None,
            'anclas': anclas, 'controles': controles, 'puntos': nuevos,
            'revision': {'estado': 'borrador', 'aprobacion': None}, 'disponible_para_modelado': False,
            'advertencias': ['La vigencia y las coordenadas resueltas deben comprobarse por el servicio llamante.',
                            'Tres anclas ajustadas exactamente no prueban exactitud.',
                            'La incertidumbre es indicativa; no incluye errores sistemáticos, correspondencias falsas ni deformación no afín.',
                            'No se infieren niveles, propiedades, suelo, continuidad ni geometría entre puntos.']}
