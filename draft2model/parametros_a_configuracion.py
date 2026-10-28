"""Aplicación pura y parcial de lecturas tipadas a configuración 0.5 en borrador.

No calcula propiedades normativas, crea geometría ni aprueba lecturas o modelos.
Las evidencias originales se conservan por dato; lo incompleto queda pendiente.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections import defaultdict

from . import lectura_parametros as lectura
from . import modelo_estructural as modelo
from .contratos import DIVISORES_A_METROS
from .normativa_rne import a_mpa, KGF_CM2_A_MPA
from .reconstruccion_automatica import _validar_esquema

MAPA_SECCIONES = {'rectangular': 'frame_rectangular', 'L': modelo.SECCION_L,
                  'muro': 'shell_muro', 'losa_maciza': 'shell_losa_homogenea',
                  'losa_aligerada_unidireccional': modelo.TIPOS_ALIGERADOS[0],
                  'losa_aligerada_bidireccional': modelo.TIPOS_ALIGERADOS[1]}
DIMENSIONES = {'frame_rectangular': 'ancho_m alto_m', 'shell_muro': 'espesor_m',
               'shell_losa_homogenea': 'espesor_m', modelo.SECCION_L: modelo.DIM_L,
               **modelo.DIM_ALIGERADOS}
TIPOS_ELEMENTO = {'frame', 'punto', 'muro', 'superficie'}


class ErrorParametros(ValueError):
    """Contrato de entrada inválido; los datos físicos incompletos son pendientes."""


def _canonico(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _sha(obj):
    return hashlib.sha256(_canonico(obj).encode('utf-8')).hexdigest()


def _numero(valor, *, positivo=True):
    try:
        if type(valor) not in (int, float) or not math.isfinite(valor) or (positivo and valor <= 0):
            raise ValueError('Valor numérico finito' + (' positivo' if positivo else '') + ' requerido.')
        return float(valor)
    except OverflowError as exc:
        raise ValueError('Valor no representable.') from exc


def _longitud(cantidad):
    valor = _numero(cantidad['valor'])
    if cantidad['unidad'] not in DIVISORES_A_METROS:
        raise ValueError('Longitud requiere m, cm o mm explícitos.')
    convertido = valor / DIVISORES_A_METROS[cantidad['unidad']]
    if not math.isfinite(convertido) or convertido <= 0:
        raise ValueError('Longitud no representable al convertir.')
    return convertido


def _cantidades(items):
    resultado = {}
    for item in items:
        if item['nombre'] in resultado:
            raise ValueError('Propiedad/parámetro repetido; no se elige la última fila.')
        resultado[item['nombre']] = item
    return resultado


def _material(row, parcial=False):
    q = _cantidades(row['propiedades'])
    if set(q) - {'fc', 'fm', 'fy', 'E', 'poisson', 'peso_especifico'}:
        raise ValueError('Propiedad sin aplicación tipada; conservar y resolver explícitamente.')
    if row['clase'] == 'otro':
        raise ValueError('Clase de material sin representación explícita.')
    faltan = sorted({'E', 'poisson', 'peso_especifico'} - set(q))
    if faltan and not parcial:
        raise ValueError('Faltan propiedades mecánicas literales: ' + ', '.join(faltan) +
                         '; resistencias fc/fm/fy no derivan E, Poisson ni peso automáticamente.')
    resultado = {'id': row['id'], 'tipo': 'isotropo_lineal'}
    if 'E' in q:
        e = q['E']; ev = _numero(e['valor'])
        if e['unidad'] in ('MPa', 'kgf/cm2'):
            ev = a_mpa(ev, e['unidad']) * 1000
        elif e['unidad'] != 'kN/m2':
            raise ValueError('E requiere MPa, kgf/cm2 o kN/m2 explícitos.')
        resultado['E_kN_m2'] = ev
    if 'poisson' in q:
        nu = q['poisson']; nv = _numero(nu['valor'], positivo=False)
        if nu['unidad'] != 'adimensional' or not -1 < nv < .5:
            raise ValueError('Poisson requiere unidad adimensional y -1 < nu < 0.5.')
        resultado['poisson'] = nv
    if 'peso_especifico' in q:
        peso = q['peso_especifico']; pv = _numero(peso['valor'])
        if peso['unidad'] == 'kgf/m3':
            pv *= KGF_CM2_A_MPA / 10  # kgf→kN, misma definición existente; no valor normativo.
        elif peso['unidad'] == 'tf/m3':
            pv *= KGF_CM2_A_MPA * 100
        elif peso['unidad'] != 'kN/m3':
            raise ValueError('Peso específico requiere kgf/m3, tf/m3 o kN/m3.')
        resultado['peso_kN_m3'] = pv
    if any(not math.isfinite(v) or v <= 0 for k, v in resultado.items() if k in ('E_kN_m2', 'peso_kN_m3')):
        raise ValueError('Propiedades no representables tras conversión.')
    return resultado


def _material_completo(row):
    try:
        return (row.get('tipo') == 'isotropo_lineal' and _numero(row['E_kN_m2']) > 0 and
                -1 < _numero(row['poisson'], positivo=False) < .5 and _numero(row['peso_kN_m3']) > 0)
    except (ValueError, KeyError, TypeError):
        return False


def _dimensiones(row):
    tipo = MAPA_SECCIONES.get(row['tipo'])
    if tipo is None:
        raise ValueError('Forma sin representación; no se sustituye por otra sección.')
    q = _cantidades(row['parametros'])
    dims = {}
    esperadas = DIMENSIONES[tipo].split()
    for key in esperadas:
        nombre = key[:-2] if key.endswith('_m') else key
        if nombre not in q:
            raise ValueError('Parámetro explícito faltante: ' + nombre)
        valor, unidad = q[nombre]['valor'], q[nombre]['unidad']
        if key.endswith('_m'):
            dims[key] = _longitud(q[nombre])
        elif key.startswith('espejo_eje_'):
            if unidad != 'adimensional' or type(valor) not in (int, float) or valor not in (0, 1):
                raise ValueError('Espejo requiere 0 o 1 adimensional explícito.')
            dims[key] = bool(valor)
        elif key == 'direccion_nervios':
            if unidad != 'adimensional' or type(valor) not in (int, float) or valor not in (1, 2):
                raise ValueError('Dirección de nervios requiere 1 o 2 adimensional explícito.')
            dims[key] = int(valor)
        else:
            angulo = _numero(valor, positivo=False)
            if unidad != 'grados' or not -180 <= angulo < 180:
                raise ValueError('Ángulo explícito en grados, -180 <= ángulo < 180 requerido.')
            dims[key] = angulo
    sobrantes = set(q) - {k[:-2] if k.endswith('_m') else k for k in esperadas}
    if sobrantes:
        raise ValueError('Parámetros adicionales sin aplicación inequívoca: ' + ', '.join(sorted(sobrantes)))
    if tipo == modelo.SECCION_L and (dims['espesor_ala_m'] >= dims['alto_m'] or dims['espesor_alma_m'] >= dims['ancho_m']):
        raise ValueError('Espesores de L deben ser menores que dimensiones exteriores.')
    if tipo in modelo.TIPOS_ALIGERADOS:
        if dims['capa_m'] >= dims['alto_total_m']:
            raise ValueError('Capa debe ser menor que alto total.')
        if any(max(dims['ancho_nervio_superior_m'], dims['ancho_nervio_inferior_m']) >= v
               for k, v in dims.items() if k.startswith('separacion')):
            raise ValueError('Nervios deben ser menores que cada separación.')
    return tipo, dims


def _registro(items, llave='id'):
    if not isinstance(items, list):
        raise ErrorParametros('Las colecciones de configuración deben ser listas.')
    salida = {}
    for row in items:
        if not isinstance(row, dict) or not isinstance(row.get(llave), str) or row[llave] in salida:
            raise ErrorParametros('Configuración con identificadores ausentes o repetidos.')
        salida[row[llave]] = row
    return salida


def _validar_lectura(valor):
    requeridas = {'datos', 'advertencias', 'faltantes', 'revision', 'ejecutable_etabs'}
    if (not isinstance(valor, dict) or not requeridas <= set(valor) or not isinstance(valor.get('datos'), dict)
            or not isinstance(valor.get('advertencias'), list) or not isinstance(valor.get('faltantes'), list)
            or not isinstance(valor.get('revision'), dict) or valor.get('ejecutable_etabs') is not False):
        raise ErrorParametros('Se requiere la salida de validar_respuesta, no la respuesta cruda.')
    datos = copy.deepcopy(valor['datos'])
    tabla = {}
    for e in datos.get('evidencias', []):
        sha = e.pop('original_sha256', None)
        if not isinstance(sha, str) or re.fullmatch(modelo.SHA, sha) is None:
            raise ErrorParametros('Evidencia sin SHA256 del original enriquecido.')
        if e.get('id') in tabla:
            raise ErrorParametros('Evidencias con identificador repetido.')
        tabla[e['id']] = {**e, 'original_sha256': sha}
    try:
        _validar_esquema(datos, lectura.esquema())
    except (ValueError, OverflowError) as exc:
        raise ErrorParametros('Lectura tipada inválida: ' + str(exc)) from exc
    for e in tabla.values():
        b = e['bbox_normalizada']
        if e['pagina'] < 1 or len(b) != 4 or not 0 <= b[0] < b[2] <= 1 or not 0 <= b[1] < b[3] <= 1:
            raise ErrorParametros('Evidencia con página/bbox inválidos.')
    for group in ('materiales', 'secciones', 'cargas'):
        _registro(datos[group])
    for group in ('materiales', 'secciones', 'asignaciones', 'cargas'):
        for row in datos[group]:
            for item in [row] + row.get('propiedades', row.get('parametros', [])):
                refs = item['evidencias']
                if not refs or any(ref not in tabla for ref in refs):
                    raise ErrorParametros('Dato sin evidencia resoluble.')
    return valor['datos'], tabla


def aplicar_parametros(configuracion, lectura_validada, *, elementos_permitidos):
    """Aplicar filas resolubles y conservar pendientes, sin mutar entradas.

    El catálogo permitido es ID→tipo o ID→{tipo, vertical}. También admite un
    conjunto de IDs; en ese caso solo infiere tipo de colecciones ya existentes.
    Las superficies requieren orientación explícita para asignar una sección.
    """
    datos, evidencias = _validar_lectura(lectura_validada)
    if not isinstance(configuracion, dict) or configuracion.get('contrato') != modelo.CONTRATO or configuracion.get('version_contrato') != modelo.VERSION_LIQUIDOS:
        raise ErrorParametros('Se requiere configuración estructural 0.5.0.')
    if configuracion.get('caso') != datos['caso']:
        raise ErrorParametros('Lectura de otro expediente.')
    if type(configuracion.get('datos_sinteticos')) is not bool:
        raise ErrorParametros('Naturaleza sintética/real explícita requerida en configuración.')
    for objeto in (lectura_validada, datos):
        if objeto.get('simulado') is True and not configuracion['datos_sinteticos']:
            raise ErrorParametros('Lectura simulada no se incorpora a un modelo real.')
        if 'datos_sinteticos' in objeto and objeto['datos_sinteticos'] != configuracion['datos_sinteticos']:
            raise ErrorParametros('Naturaleza de lectura y configuración incompatible.')
    if configuracion.get('unidades') != {'longitud': 'm', 'fuerza': 'kN', 'tiempo': 's', 'temperatura': 'C'}:
        raise ErrorParametros('Configuración debe declarar unidades m/kN/s/C.')
    out = copy.deepcopy(configuracion)
    colecciones = ('fuentes', 'materiales', 'secciones', 'patrones', 'cargas', 'asignaciones_frames',
                   'asignaciones_muros', 'asignaciones_superficies', 'faltantes', 'frames', 'puntos')
    tablas = {g: _registro(out.get(g), 'objetivo' if g.startswith('asignaciones_') else 'ruta' if g == 'faltantes' else 'id') for g in colecciones}
    if isinstance(elementos_permitidos, dict):
        catalogo = copy.deepcopy(elementos_permitidos)
    elif isinstance(elementos_permitidos, (set, frozenset, list, tuple)):
        catalogo = {ident: {} for ident in elementos_permitidos}
    else:
        raise ErrorParametros('Catálogo de elementos permitidos requerido.')
    for ident, value in list(catalogo.items()):
        if not isinstance(ident, str):
            raise ErrorParametros('ID permitido debe ser texto.')
        if isinstance(value, str):
            value = {'tipo': value}
        if not isinstance(value, dict) or set(value) - {'tipo', 'vertical'}:
            raise ErrorParametros('Descriptor permitido: tipo y vertical opcional.')
        if 'vertical' in value and type(value['vertical']) is not bool:
            raise ErrorParametros('Orientación vertical debe ser booleana explícita.')
        tipos_presentes = [tipo for group, tipo in [('frames', 'frame'), ('puntos', 'punto'),
                           ('asignaciones_superficies', 'superficie'), ('asignaciones_muros', 'muro')]
                           if ident in tablas[group]]
        if len(set(tipos_presentes)) > 1 or value.get('tipo') and tipos_presentes and value['tipo'] != tipos_presentes[0]:
            raise ErrorParametros('Catálogo contradice tipo de un elemento de configuración.')
        tipo = value.get('tipo') or (tipos_presentes[0] if tipos_presentes else None)
        if tipo is not None and tipo not in TIPOS_ELEMENTO:
            raise ErrorParametros('Tipo de elemento permitido desconocido.')
        catalogo[ident] = {**value, 'tipo': tipo}
    huella = _sha(datos)
    # Recalcular únicamente pendientes de ESTA lectura permite completar datos en
    # UI349 y reaplicar sin conservar bloqueos ya resueltos ni limpiar otros gaps.
    propias = {s['id'] for s in out['fuentes'] if isinstance(s.get('referencia'), str)
               and s['referencia'].startswith('lectura_parametros/' + huella + '#')}
    out['faltantes'] = [f for f in out['faltantes'] if not (f.get('fuente') in propias and
                         re.search(r'\.lectura_[0-9a-f]{12}$', f.get('ruta', '')))]
    tablas['faltantes'] = _registro(out['faltantes'], 'ruta')
    aplicados, pendientes, conflictos, trazabilidad = [], [], [], []
    bloqueados = {'materiales': set(), 'secciones': set()}

    def agregar_fuente(ruta, contenido, refs):
        refs = list(dict.fromkeys(refs))
        snapshot = {'ruta': ruta, 'dato': contenido, 'evidencias': [evidencias[r] for r in refs]}
        ident = 'LP-' + _sha({'lectura': huella, 'snapshot': snapshot})[:32]
        source = {'id': ident, 'descripcion': 'Lectura literal sin derivación normativa: ' + _canonico(snapshot),
                  'referencia': 'lectura_parametros/' + huella + '#' + ruta, 'sha256': huella}
        previo = tablas['fuentes'].get(ident)
        if previo is not None and previo != source:
            raise ErrorParametros('Colisión de ID de fuente; no se sobrescribe.')
        if previo is None:
            out['fuentes'].append(source); tablas['fuentes'][ident] = source
        trazabilidad.append({'ruta': ruta, 'fuente': ident, 'evidencias': copy.deepcopy(snapshot['evidencias'])})
        return ident

    def fuente_fila(grupo, indice, row):
        ruta = '$.' + grupo + '[' + str(indice) + ']'
        todas = list(row['evidencias'])
        for j, q in enumerate(row.get('propiedades', row.get('parametros', []))):
            subgrupo = 'propiedades' if 'propiedades' in row else 'parametros'
            agregar_fuente(ruta + '.' + subgrupo + '[' + str(j) + ']', q, q['evidencias'])
            todas += q['evidencias']
        return agregar_fuente(ruta, row, todas)

    def pendiente(grupo, row, motivo, fuente, *, conflicto=False):
        ident = row.get('id', row.get('elemento', 'dato'))
        entry = {'coleccion': grupo, 'id': ident, 'motivo': motivo, 'dato': copy.deepcopy(row), 'fuente': fuente}
        pendientes.append(entry)
        if conflicto:
            conflictos.append(copy.deepcopy(entry))
        # Ruta determinista para gaps completos: no se agrega un objeto físico incompleto.
        ruta = '$.' + grupo + '.' + ident + '.lectura_' + _sha({'fila': row, 'motivo': motivo})[:12]
        if ruta not in tablas['faltantes']:
            gap = {'ruta': ruta, 'motivo': motivo, 'fuente': fuente}
            out['faltantes'].append(gap); tablas['faltantes'][ruta] = gap

    def incorporar(grupo, row, candidate, fuente):
        candidate = {**candidate, 'fuente': fuente}
        previo = tablas[grupo].get(candidate['id'])
        if previo is not None:
            if {k: v for k, v in previo.items() if k != 'fuente'} != {k: v for k, v in candidate.items() if k != 'fuente'}:
                bloqueados.get(grupo, set()).add(candidate['id'])
                pendiente(grupo, row, 'ID existente con datos distintos; no se sobrescribe.', fuente, conflicto=True)
                return False
            estado = 'ya_existente'
        else:
            out[grupo].append(candidate); tablas[grupo][candidate['id']] = candidate
            estado = 'incorporado'
        aplicados.append({'coleccion': grupo, 'id': candidate['id'], 'estado': estado, 'fuente_lectura': fuente})
        return True

    for i, row in enumerate(datos['materiales']):
        fuente = fuente_fila('materiales', i, row)
        try:
            material = _material(row)
        except ValueError as exc:
            previo = tablas['materiales'].get(row['id'])
            if previo and _material_completo(previo):
                try:
                    parcial = _material(row, parcial=True)
                    if any(previo.get(k) != v for k, v in parcial.items()):
                        raise ValueError('Material existente contradice propiedades literales de la lectura.')
                    aplicados.append({'coleccion': 'materiales', 'id': row['id'],
                                      'estado': 'resuelto_en_configuracion', 'fuente_lectura': fuente})
                    continue
                except ValueError as conflicto:
                    exc = conflicto
            bloqueados['materiales'].add(row['id'])
            pendiente('materiales', row, str(exc), fuente)
            continue
        incorporar('materiales', row, material, fuente)
    clases = {row['id']: row['clase'] for row in datos['materiales']}
    for i, row in enumerate(datos['secciones']):
        fuente = fuente_fila('secciones', i, row)
        try:
            if row['material'] not in tablas['materiales'] or row['material'] in bloqueados['materiales']:
                raise ValueError('Material completo compatible pendiente de resolución.')
            material = tablas['materiales'][row['material']]
            if not _material_completo(material):
                raise ValueError('Material sin propiedades mecánicas completas.')
            if row['tipo'] == 'L' and clases.get(row['material']) != 'concreto':
                raise ValueError('Sección L requiere material de concreto identificado explícitamente.')
            tipo, dimensiones = _dimensiones(row)
            candidate = {'id': row['id'], 'tipo': tipo, 'material': row['material'], 'dimensiones': dimensiones}
        except ValueError as exc:
            bloqueados['secciones'].add(row['id'])
            pendiente('secciones', row, str(exc), fuente)
            continue
        incorporar('secciones', row, candidate, fuente)

    grupos = defaultdict(list)
    for i, row in enumerate(datos['asignaciones']):
        grupos[row['elemento']].append((row, fuente_fila('asignaciones', i, row)))
    for objetivo, rows in grupos.items():
        if len({row['seccion'] for row, _ in rows}) != 1:
            for row, fuente in rows:
                pendiente('asignaciones', row, 'Asignaciones contradictorias al mismo elemento; ninguna fila aplicada.', fuente, conflicto=True)
            continue
        row, fuente = rows[0]
        descriptor = catalogo.get(objetivo, {})
        tipo_obj = descriptor.get('tipo')
        seccion = tablas['secciones'].get(row['seccion'])
        if not seccion or row['seccion'] in bloqueados['secciones']:
            pendiente('asignaciones', row, 'Sección inexistente, incompleta o en conflicto.', fuente); continue
        if objetivo not in catalogo or tipo_obj is None:
            pendiente('asignaciones', row, 'Elemento ajeno o sin tipo comprobado.', fuente); continue
        if tipo_obj == 'frame' and objetivo not in tablas['frames']:
            pendiente('asignaciones', row, 'Frame permitido todavía no incorporado a la configuración.', fuente); continue
        tipo_sec = seccion['tipo']
        compatible = tipo_obj == 'frame' and tipo_sec in modelo.TIPOS_FRAME or tipo_obj == 'muro' and tipo_sec == 'shell_muro'
        if tipo_obj == 'superficie' and 'vertical' in descriptor:
            compatible = tipo_sec == 'shell_muro' if descriptor['vertical'] else tipo_sec in ('shell_losa_homogenea',) + modelo.TIPOS_ALIGERADOS
        if not compatible:
            pendiente('asignaciones', row, 'Tipo/orientación de elemento incompatible o no declarado.', fuente); continue
        group = {'frame': 'asignaciones_frames', 'muro': 'asignaciones_muros', 'superficie': 'asignaciones_superficies'}[tipo_obj]
        previo = tablas[group].get(objetivo)
        if previo is not None and previo.get('seccion') not in (None, row['seccion']):
            pendiente('asignaciones', row, 'Elemento ya asignado a otra sección; no se sobrescribe.', fuente, conflicto=True); continue
        if previo is not None and previo.get('seccion') == row['seccion']:
            estado = 'ya_existente'
        else:
            candidate = {'objetivo': objetivo, 'seccion': row['seccion'], 'fuente': fuente}
            if previo is not None:
                out[group][out[group].index(previo)] = candidate
            else:
                out[group].append(candidate)
            tablas[group][objetivo] = candidate
            estado = 'incorporado'
        aplicados.append({'coleccion': group, 'id': objetivo, 'estado': estado, 'fuente_lectura': fuente})

    # Patrones dedicados: multiplicador cero representa SOLO carga externa literal;
    # la política del peso propio/masa global queda explícitamente pendiente.
    for i, row in enumerate(datos['cargas']):
        fuente = fuente_fila('cargas', i, row)
        try:
            valor = _numero(row['valor'])
            if row['direccion'] != 'global_z_negativa' or not row['elementos'] or not row['alcance'].strip():
                raise ValueError('Carga sin dirección, alcance o elementos explícitos; no se aplica al edificio entero.')
            if re.search(r'\b(general|global|edificio|todos|todas|todo|toda|desconocido|desconocida)\b', row['alcance'].casefold()):
                raise ValueError('Alcance general o desconocido requiere delimitación explícita antes de cargar elementos.')
            if row['tipo'] not in ('muerta', 'viva'):
                raise ValueError('Agua/otro requieren su contrato físico específico; no se convierten a carga uniforme genérica.')
            tipos = {catalogo.get(ident, {}).get('tipo') for ident in row['elementos']}
            if any(ident not in catalogo for ident in row['elementos']) or len(tipos) != 1 or None in tipos:
                raise ValueError('Carga con elementos ajenos o de tipos distintos/no declarados.')
            if len(set(row['elementos'])) != len(row['elementos']):
                raise ValueError('Carga repite elementos; no se duplica su magnitud.')
            tipo_obj = next(iter(tipos))
            group_obj = {'frame': 'frames', 'punto': 'puntos'}.get(tipo_obj)
            if group_obj and any(ident not in tablas[group_obj] for ident in row['elementos']):
                raise ValueError('Puntos/frames permitidos todavía no incorporados a la configuración.')
            sufijo = {'punto': '', 'frame': '/m', 'muro': '/m2', 'superficie': '/m2'}[tipo_obj]
            factores = {'kN'+sufijo: 1, 'kgf'+sufijo: KGF_CM2_A_MPA/10,
                        'tf'+sufijo: KGF_CM2_A_MPA*100}
            if row['unidad'] not in factores:
                raise ValueError('Unidad de carga incompatible con tipo de elemento.')
            magnitud = valor * factores[row['unidad']]
            if not math.isfinite(magnitud) or magnitud <= 0:
                raise ValueError('Carga no representable al convertir.')
            patron_id = 'PL-' + row['id'][:28] + '-' + _sha({'caso': datos['caso'], 'carga': row['id']})[:12]
            patron = {'id': patron_id, 'tipo': row['tipo'], 'multiplicador_peso_propio': 0.0, 'fuente': fuente}
            candidates = []
            for ident in row['elementos']:
                carga_id = 'CL-' + _sha({'carga': row['id'], 'elemento': ident, 'caso': datos['caso']})[:32]
                candidates.append({'id': carga_id, 'patron': patron_id, 'objetivo_tipo': tipo_obj,
                                   'objetivo': ident, 'componentes': [0.0, 0.0, -magnitud],
                                   'unidad': 'kN'+sufijo, 'sistema': 'global', 'fuente': fuente})
            for group, candidate in [('patrones', patron)] + [('cargas', v) for v in candidates]:
                previo = tablas[group].get(candidate['id'])
                if previo and {k: v for k, v in previo.items() if k != 'fuente'} != {k: v for k, v in candidate.items() if k != 'fuente'}:
                    raise ValueError('ID de patrón/carga existente con datos distintos; ninguna carga de esta fila aplicada.')
            hip = {'id': 'H-' + patron_id,
                   'descripcion': 'Patrón dedicado a la carga externa literal ' + row['id'] +
                                  '; multiplicador de peso propio cero para aislamiento computacional. No determina política de peso propio, masa, gravedad ni casos del edificio.',
                   'fuente': fuente}
            hipotesis = _registro(out.get('hipotesis'))
            previo_hip = hipotesis.get(hip['id'])
            if previo_hip and {k: v for k, v in previo_hip.items() if k != 'fuente'} != {k: v for k, v in hip.items() if k != 'fuente'}:
                raise ValueError('Hipótesis de patrón existente diferente; requiere conciliación explícita.')
        except ValueError as exc:
            pendiente('cargas', row, str(exc), fuente, conflicto='existente' in str(exc)); continue
        incorporar('patrones', row, {k: v for k, v in patron.items() if k != 'fuente'}, fuente)
        for candidate in candidates:
            incorporar('cargas', row, {k: v for k, v in candidate.items() if k != 'fuente'}, fuente)
        if hip['id'] not in hipotesis:
            out['hipotesis'].append(hip)
        pendiente('politica_peso_masa', row,
                  'Definir/revisar política global de peso propio y masa: patrón dedicado solo contiene la carga externa leída; no se crean masas, gravedad ni casos.', fuente)
    for i, texto in enumerate(datos['faltantes']):
        fuente = agregar_fuente('$.faltantes[' + str(i) + ']', texto, [])
        pendiente('lectura', {'id': 'F' + str(i), 'texto': texto}, texto, fuente)

    revision_previa = copy.deepcopy(out.get('revision'))
    out['revision'] = {'estado': 'borrador', 'aprobacion': None}
    # Diagnóstico completo existente, sin geometría externa ni aceptación automática.
    validacion = modelo.validar_configuracion(out).a_dict()
    return {'configuracion': out, 'aplicados': aplicados, 'faltantes': pendientes, 'conflictos': conflictos,
            'trazabilidad': trazabilidad, 'huella_lectura': huella, 'lectura_conservada': copy.deepcopy(lectura_validada),
            'revision_configuracion_previa': revision_previa, 'validacion': validacion,
            'completa': False, 'ejecutable_etabs': False, 'aprueba_lecturas': False, 'aprueba_ingenieria': False,
            'advertencias': ['La validación sin geometría no acredita orientación, malla ni vigencia geométrica.',
                            'Lectura tipada no equivale a aprobación de sus valores ni de su aplicación.']}
