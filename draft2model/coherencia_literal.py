"""Alertas locales de cotas; no OCR, conversión ni aprobación de una lectura."""
from decimal import Decimal, InvalidOperation
import re


_NUMERO = re.compile(r'(?<![\w.,])[-+−]?(?:\d+(?:[.,]\d+)?|[.,]\d+)(?![\d.,])')
_UNIDAD = re.compile(r'(?<![A-Za-z])(?:mm|cm|m)(?![A-Za-z0-9²³/])', re.IGNORECASE)


def alertas_cota_literal(candidato):
    """Contrasta solo lo declarado, nunca verifica que el texto exista en la imagen.

    Una unidad puede estar en un encabezado fuera de texto_fuente: su ausencia
    aquí pide comprobar evidencia, no demuestra que la unidad sea incorrecta.
    No interpreta fracciones, escalas ni separadores de miles.
    """
    if candidato.get('tipo') != 'cota':
        return []
    texto = candidato.get('texto_fuente')
    if not isinstance(texto, str) or not texto.strip():
        metodo = candidato.get('metodo')
        if (isinstance(metodo, dict) and metodo.get('tipo') in ('vision', 'ocr')
                and candidato.get('unidad') in ('m', 'cm', 'mm')):
            return [('unidad_sin_texto_fuente',
                     'Lectura automática con unidad definida pero sin texto literal: '
                     'compruebe su respaldo en la evidencia antes de usarla como longitud.')]
        return []  # registros heredados siguen siendo válidos; no se completan
    valor = candidato.get('valor_propuesto')
    if type(valor) not in (int, float):
        return []
    try:
        numero = Decimal(str(valor))
    except InvalidOperation:
        return []
    if not numero.is_finite():
        return []
    alertas = []
    # Las fracciones y notaciones científicas requieren interpretación; no
    # reducirlas a sus dígitos ni declarar contradicción por ese atajo.
    interpretable = not re.search(r'\d\s*[/eE]\s*[-+]?\d|\d[.,]\d{3}(?:\D|$)', texto)
    numeros = []
    if interpretable:
        for item in _NUMERO.findall(texto):
            numeros.append(Decimal(item.replace('−', '-').replace(',', '.')))
        if numeros and numero not in numeros:
            alertas.append(('valor_sin_correspondencia_literal',
                            'La cota propuesta no coincide con ningún número del texto declarado; '
                            'revise la imagen, sin convertir ni corregir automáticamente.'))
    unidad = candidato.get('unidad')
    if unidad in ('m', 'cm', 'mm'):
        unidades = {match.group().lower() for match in _UNIDAD.finditer(texto)}
        if unidad not in unidades:
            alertas.append(('unidad_sin_respaldo_literal',
                            'La unidad propuesta no aparece en el texto declarado. Compruebe si está '
                            'impresa en la región o en un encabezado con evidencia; no inferirla.'))
    return alertas
