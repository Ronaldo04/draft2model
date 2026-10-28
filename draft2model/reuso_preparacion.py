"""Instantánea privada por resultado de validación; no caché global ni persistida."""
from dataclasses import dataclass
import hashlib
import json


def _canon(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',', ':'),allow_nan=False).encode('utf-8')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def huellas(geometria, configuracion):
    # Incluye TODO, incluso revisión y metadatos. No se omiten partes para mejorar aciertos.
    return (_sha(_canon(geometria)), _sha(_canon(configuracion)))


@dataclass(frozen=True)
class _Instantanea:
    entradas: tuple
    contenido: bytes
    sha256: str


def sellar(geometria, configuracion, preparacion, entradas_antes):
    if huellas(geometria,configuracion) != entradas_antes:
        raise ValueError('Las entradas cambiaron durante la preparación de la malla.')
    body={k:v for k,v in preparacion.items() if k!='huella_preparacion'}
    if preparacion.get('huella_preparacion') != _sha(_canon(body)):
        raise ValueError('Huella de preparación incoherente.')
    raw=_canon(preparacion)
    return _Instantanea(entradas_antes,raw,_sha(raw))


def obtener(instantanea, geometria, configuracion):
    if not isinstance(instantanea,_Instantanea):
        return None
    try:
        entradas=huellas(geometria,configuracion)
    except (TypeError,ValueError):
        return None   # se conserva el recorrido original de cálculo/rechazo, no una excepción nueva del reuso
    if entradas!=instantanea.entradas or _sha(instantanea.contenido)!=instantanea.sha256:
        return None
    # Cada consumidor recibe un objeto nuevo: no comparte mutaciones con la validación ni otros planes.
    return json.loads(instantanea.contenido)
