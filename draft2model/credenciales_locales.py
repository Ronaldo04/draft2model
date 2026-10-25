"""Carga explícita de credenciales locales Markdown, sin evaluar código ni imprimir valores."""
from pathlib import Path
import re

PERMITIDAS = frozenset(('OPENAI_API_KEY','GEMINI_API_KEY','ANTHROPIC_API_KEY',
                       'COMPATIBLE_API_KEY','D2M_COMPATIBLE_ENDPOINT','D2M_COMPATIBLE_TOKEN_FIELD'))


def cargar(ruta):
    path = Path(ruta).absolute()
    if path.resolve() != path or not path.is_file() or path.stat().st_size > 32768:
        raise ValueError('Archivo de credenciales ausente, enlazado o demasiado grande.')
    raw = path.read_text(encoding='utf-8-sig')
    blocks = re.findall(r'^```env\s*\n(.*?)^```\s*$',raw,re.M|re.S)
    if len(blocks) != 1:
        raise ValueError('Se requiere exactamente un bloque env en el Markdown privado.')
    values = {}; seen = set()
    for line in blocks[0].splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        name, sep, value = line.partition('=')
        name = name.strip(); value = value.strip()
        if not sep or name not in PERMITIDAS or name in seen:
            raise ValueError('Variable desconocida, duplicada o formato inválido en credenciales.')
        seen.add(name)
        if value[:1] in ('"', "'"):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError('Comillas incompletas en credenciales.')
            value = value[1:-1]
        if any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError('Caracteres de control no admitidos en credenciales.')
        if value:
            values[name] = value
    if 'D2M_COMPATIBLE_ENDPOINT' in values:
        from .proveedor_compatible import _validar_endpoint
        _validar_endpoint(values['D2M_COMPATIBLE_ENDPOINT'])
    if values.get('D2M_COMPATIBLE_TOKEN_FIELD','max_tokens') not in ('max_tokens','max_completion_tokens'):
        raise ValueError('Campo de tokens compatible no admitido.')
    return values


def estado(values):
    """Solo presencia: no autentica ni comprueba saldo/modelos/conectividad."""
    return {name: bool(values.get(name)) for name in sorted(PERMITIDAS)}
