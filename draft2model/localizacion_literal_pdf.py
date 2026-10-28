"""Propuestas de región basadas en palabras del PDF; sin OCR ni correcciones."""
from itertools import groupby
import unicodedata

import pymupdf


def _literal(texto):
    return unicodedata.normalize('NFC', texto).casefold()


def localizar_literal_pdf(contenido, pagina, texto):
    """Busca palabras completas contiguas de una línea y devuelve TODAS las regiones.

    No elige por proximidad a una bbox propuesta, no convierte números/unidades,
    y no acredita que una capa de texto coincida visualmente con el dibujo.
    Las cajas devueltas corresponden a la página visible tras su rotación.
    """
    if type(pagina) is not int or pagina < 1:
        raise ValueError('Página inválida.')
    if not isinstance(texto, str) or not texto.strip() or len(texto) > 500:
        raise ValueError('Se requiere texto literal de entre 1 y 500 caracteres.')
    target = [_literal(t) for t in texto.split()]
    with pymupdf.open(stream=contenido, filetype='pdf') as document:
        if document.needs_pass or pagina > document.page_count:
            raise ValueError('Página no disponible o PDF protegido.')
        page = document[pagina - 1]
        words = page.get_text('words')
        if len(words) > 100000:
            raise ValueError('Página demasiado extensa para búsqueda local.')
        matches = []
        ordered = sorted(words, key=lambda w: (w[5], w[6], w[7]))
        for _, group in groupby(ordered, key=lambda w: (w[5], w[6])):
            line = list(group)
            for index in range(len(line) - len(target) + 1):
                section = line[index:index + len(target)]
                if [_literal(w[4]) for w in section] != target:
                    continue
                rect = pymupdf.Rect(section[0][:4])
                for word in section[1:]:
                    rect |= pymupdf.Rect(word[:4])
                rect = rect * page.rotation_matrix
                bounds = page.rect
                if (rect.is_empty or not bounds.contains(rect) or bounds.width <= 0 or bounds.height <= 0):
                    continue
                matches.append({'texto_pdf': ' '.join(w[4] for w in section),
                                'bbox_normalizada': [rect.x0 / bounds.width, rect.y0 / bounds.height,
                                                     rect.x1 / bounds.width, rect.y1 / bounds.height]})
        # No recortar resultados y aparentar una coincidencia única.
        if len(matches) > 50:
            return {'estado': 'demasiadas_coincidencias', 'total': len(matches), 'regiones': []}
        return {'estado': ('sin_texto_vectorial' if not words else 'sin_coincidencias' if not matches
                           else 'unica' if len(matches) == 1 else 'ambigua'),
                'total': len(matches), 'regiones': matches}
