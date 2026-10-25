"""Registro de protocolos de IA admitidos; las claves nunca forman parte del catálogo.

Un modelo no se presume compatible por su nombre o por disponer de una clave.
Los adaptadores se incorporan como código revisado, no como plugins enviados por UI.
"""
from dataclasses import dataclass
from importlib import import_module
from types import MappingProxyType


@dataclass(frozen=True)
class Proveedor:
    id: str
    nombre: str
    modulo: str
    variable_clave: str
    campo_uso: str = 'usage'
    campo_modelo: str = 'model'
    campo_respuesta: str = 'id'
    detalle_auto: bool = False

    def api(self):
        return import_module('.' + self.modulo, package=__package__)

    def endpoint(self, modelo):
        api = self.api()
        return api.endpoint(modelo) if hasattr(api, 'endpoint') else api.ENDPOINT


CATALOGO = MappingProxyType({p.id: p for p in (
    Proveedor('openai', 'OpenAI Responses', 'proveedor_openai', 'OPENAI_API_KEY'),
    Proveedor('gemini', 'Google Gemini', 'proveedor_gemini', 'GEMINI_API_KEY',
              'usageMetadata', 'modelVersion', 'responseId', True),
    Proveedor('anthropic', 'Anthropic Messages', 'proveedor_anthropic', 'ANTHROPIC_API_KEY', detalle_auto=True),
    Proveedor('openai_compatible', 'API compatible con Chat Completions', 'proveedor_compatible', 'COMPATIBLE_API_KEY'),
)})


def obtener(identificador):
    if not isinstance(identificador, str) or identificador not in CATALOGO:
        raise ValueError('Proveedor no registrado. Selecciona un protocolo compatible; una clave no añade un adaptador.')
    return CATALOGO[identificador]


def metadatos(identificador, respuesta):
    spec = obtener(identificador)
    if not isinstance(respuesta, dict):
        return {'usage': None, 'modelo_devuelto': None, 'respuesta_id_declarado': None}
    usage = respuesta.get(spec.campo_uso)
    model, ident = respuesta.get(spec.campo_modelo), respuesta.get(spec.campo_respuesta)
    return {'usage': usage if isinstance(usage, dict) else None,
            'modelo_devuelto': model if isinstance(model, str) else None,
            'respuesta_id_declarado': ident if isinstance(ident, str) else None}
