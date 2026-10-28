"""Autorización vigente del usuario: APIs solo para revisión/extracción de planos."""

PROVEEDORES_AUTORIZADOS = frozenset(('openai','gemini'))
FINALIDAD_AUTORIZADA = 'revision_extraccion_planos'


def exigir_autorizacion(proveedor, finalidad):
    if proveedor not in PROVEEDORES_AUTORIZADOS or finalidad != FINALIDAD_AUTORIZADA:
        raise ValueError('Uso de API no autorizado: solo Google/OpenAI para revisión y extracción de planos.')
