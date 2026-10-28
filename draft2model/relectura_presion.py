"""Lectura dimensional de la tabla CSI no uniforme, sin modificar el modelo.

Las unidades presentes son parte obligatoria de la observación. La comparación
solo acredita asignaciones del patrón solicitado; no equilibrio ni ingeniería.
"""
from decimal import Decimal, InvalidOperation
import math

from .cargas_liquidos_etabs import CAMPOS, ErrorCargaLiquido


def _decimal(valor):
    if type(valor) not in (str, int, float) or isinstance(valor, str) and not valor.strip():
        raise ErrorCargaLiquido('Coeficiente numérico finito requerido.')
    try:
        d = Decimal(str(valor))
    except InvalidOperation as exc:
        raise ErrorCargaLiquido('Coeficiente decimal no válido.') from exc
    if not d.is_finite():
        raise ErrorCargaLiquido('Coeficiente no finito.')
    return d


def normalizar_tabla_no_uniforme(tabla):
    """GetTableForDisplayArray v1, datos planos, a coeficientes kN/m³ y kN/m²."""
    try:
        if type(tabla['version']) is not int or tabla['version'] != 1:
            raise ErrorCargaLiquido('Versión de tabla no admitida.')
        fuerza, longitud, temperatura = tabla['unidades'].split('_')
        if temperatura != 'C':
            raise ValueError('Unidad no admitida')
        f = {'N': Decimal('.001'), 'kN': Decimal(1)}[fuerza]
        l = {'mm': Decimal('.001'), 'cm': Decimal('.01'), 'm': Decimal(1)}[longitud]
        campos, datos, cantidad = tabla['campos'], tabla['datos'], tabla['registros']
        if (not isinstance(campos, list) or any(type(k) is not str for k in campos)
                or len(set(campos)) != len(campos) or not set(CAMPOS) <= set(campos)
                or not isinstance(datos, list) or type(cantidad) is not int or cantidad < 0
                or len(datos) != cantidad * len(campos)):
            raise ErrorCargaLiquido('Tabla incompleta o columnas ambiguas.')
        filas, claves = [], set()
        for i in range(cantidad):
            cruda = dict(zip(campos, datos[i*len(campos):(i+1)*len(campos)]))
            fila = {k: cruda[k] for k in CAMPOS}
            for k in ('UniqueName', 'LoadPattern', 'Dir', 'Restriction'):
                if type(fila[k]) is not str or not fila[k].strip():
                    raise ErrorCargaLiquido('Identificador o dirección ausente.')
            if fila['Dir'] not in ('Global-X', 'Global-Y', 'Gravity'):
                raise ErrorCargaLiquido('Dirección fuera de las componentes hidrostáticas admitidas.')
            if fila['Restriction'] not in ('Zero Negative Values', 'Zero Positive Values'):
                raise ErrorCargaLiquido('Restricción de signo no admitida.')
            clave = tuple(fila[k] for k in ('UniqueName', 'LoadPattern', 'Dir'))
            if clave in claves:
                raise ErrorCargaLiquido('Asignación duplicada; no se suman ni ocultan registros.')
            claves.add(clave)
            for k in ('A', 'B', 'C', 'D'):
                convertido = float(_decimal(fila[k]) * f / l ** (2 if k == 'D' else 3))
                if not math.isfinite(convertido):
                    raise ErrorCargaLiquido('Coeficiente normalizado no representable.')
                fila[k] = convertido
            filas.append(fila)
        return {'unidades_origen': tabla['unidades'], 'unidades': 'kN_m_C',
                'filas': filas, 'aprueba_ingenieria': False}
    except ErrorCargaLiquido:
        raise
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        raise ErrorCargaLiquido('Observación de tabla no uniforme inválida.') from exc


def comparar_tabla_no_uniforme(esperada, observada, *, patrones, tolerancia_absoluta):
    """Compara cobertura completa de patrones explícitos, incluidos registros extras.

    Ambas tablas se normalizan desde sus unidades. La tolerancia es computacional,
    explícita y absoluta, en kN/m³ para ABC y kN/m² para D; no se infiere del dato.
    """
    if (not isinstance(patrones, list) or not patrones
            or any(type(p) is not str or not p.strip() for p in patrones)
            or len(set(patrones)) != len(patrones)
            or type(tolerancia_absoluta) not in (float, int)
            or not math.isfinite(tolerancia_absoluta) or tolerancia_absoluta < 0):
        raise ErrorCargaLiquido('Patrones distintos y tolerancia computacional explícita requeridos.')
    e, o = normalizar_tabla_no_uniforme(esperada), normalizar_tabla_no_uniforme(observada)
    if any(r['LoadPattern'] not in patrones for r in e['filas']):
        raise ErrorCargaLiquido('Expectativa contiene patrones fuera del alcance declarado.')
    if any(not any(r['LoadPattern'] == p for r in e['filas']) for p in patrones):
        raise ErrorCargaLiquido('Cada patrón requiere asignaciones esperadas explícitas.')
    def indice(filas):
        return {tuple(r[k] for k in ('UniqueName', 'LoadPattern', 'Dir')): r
                for r in filas if r['LoadPattern'] in patrones}
    ei, oi = indice(e['filas']), indice(o['filas'])
    diferencias = []
    for clave in sorted(ei.keys() | oi.keys()):
        if clave not in oi:
            diferencias.append({'clave': list(clave), 'tipo': 'faltante'})
        elif clave not in ei:
            diferencias.append({'clave': list(clave), 'tipo': 'extra'})
        else:
            for campo in ('Restriction', 'A', 'B', 'C', 'D'):
                a, b = ei[clave][campo], oi[clave][campo]
                distinto = a != b if campo == 'Restriction' else abs(a-b) > tolerancia_absoluta
                if distinto:
                    diferencias.append({'clave': list(clave), 'campo': campo,
                                        'esperado': a, 'observado': b, 'tipo': 'distinto'})
    return {'asignaciones_coinciden': not diferencias, 'discrepancias': diferencias,
            'patrones': list(patrones), 'registros_esperados': len(ei), 'registros_observados': len(oi),
            'registros_ajenos': len(o['filas'])-len(oi), 'tolerancia_absoluta': tolerancia_absoluta,
            'unidades': 'kN_m_C', 'aprueba_ingenieria': False, 'equilibrio_verificado': False}
