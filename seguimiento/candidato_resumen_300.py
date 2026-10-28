"""Alternativa aislada al resumen; no modifica el producto ni sus validaciones."""
import copy


def resumen_validacion(resultado):
    return {
        'consistente': resultado.consistente,
        'disponible_para_modelado': resultado.disponible_para_modelado,
        'datos_sinteticos': resultado.datos_sinteticos,
        'errores': [vars(h) for h in resultado.errores],
        'advertencias': [vars(h) for h in resultado.advertencias],
        'faltantes': copy.deepcopy(resultado.faltantes),
        'bloqueos': list(resultado.bloqueos),
        'huella_contenido': resultado.huella_contenido,
    }
