"""Memoización LRU por proceso SOLO de funciones puras JSON (preparar_malla). Candidato Codex 267/268 integrado por Claude.

Sin estado persistido, TTL ni confianza por mtime; la clave es TODO el JSON de geometría y configuración (revisión incluida),
comprobado antes y después; salida sellada con SHA256 y copia independiente por consumidor. Errores y valores no JSON pasan al
original. No se decoran aprobaciones, lecturas de archivos, evidencias, EDB ni planes."""
from collections import OrderedDict
from functools import wraps
import hashlib
import json
import math
from threading import Event, RLock

MAX_ENTRADAS = 4   # el caso conserva 3 modelos históricos: con 2, un listado expulsaba el primero (Continuación268)
MAX_BYTES = 64 * 1024 * 1024
ESPERA_MAX_S = 1800.0   # espera acotada de un miss concurrente de la MISMA clave; al vencer calcula por su cuenta (Continuación279)


def _json_canonico(value):
    """No convierte tuplas, claves no textuales, subtipos o valores no finitos."""
    active = set()

    def check(item):
        kind = type(item)
        if kind in (str, int, bool, type(None)):
            return
        if kind is float:
            if not math.isfinite(item):
                raise ValueError('Número no JSON')
            return
        if kind not in (list, dict):
            raise TypeError('Tipo no JSON')
        ident = id(item)
        if ident in active:
            raise ValueError('JSON cíclico')
        active.add(ident)
        try:
            if kind is dict:
                for key, child in item.items():
                    if type(key) is not str:
                        raise TypeError('Clave no textual')
                    check(child)
            else:
                for child in item:
                    check(child)
        finally:
            active.remove(ident)

    check(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def _canonico_o_none(value):
    try:
        return _json_canonico(value)
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError, RuntimeError):
        return None


def _exacto_o_none(value):
    """JSON estricto (mismas reglas de tipos que _json_canonico) serializado en el ORDEN EXACTO de inserción.

    Revisión Codex 284: con sort_keys, entradas equivalentes con otro orden compartían entrada y un acierto devolvía el orden de
    la primera llamada (o el orden ordenado de la salida). Clave y sello en orden exacto: la salida no depende del historial.
    """
    if _canonico_o_none(value) is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError):
        return None


def reutilizar_malla_pura(function=None, *, max_entradas=MAX_ENTRADAS, max_bytes=MAX_BYTES, espera_max_s=ESPERA_MAX_S):
    """Decora preparar_malla(geometria, configuracion), sin cache de evidencias.

    El límite contabiliza bytes de claves JSON completas, salidas JSON y SHA256.
    Single-flight acotado (279): misses simultáneos de la MISMA clave esperan al primer cálculo (hasta espera_max_s) y reciben
    copias independientes; si el primero falla o vence la espera, cada llamador calcula y recibe su propia excepción. Claves
    distintas calculan en paralelo; ningún lock se mantiene durante el cálculo.
    """
    if type(max_entradas) is not int or not 1 <= max_entradas <= MAX_ENTRADAS:
        raise ValueError('max_entradas debe estar entre 1 y ' + str(MAX_ENTRADAS))
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_BYTES:
        raise ValueError('max_bytes debe estar entre 1 y 64 MiB')

    def decorate(original):
        cache = OrderedDict()
        en_curso = {}   # clave → Event: agrupa misses concurrentes de la MISMA clave (single-flight acotado)
        lock = RLock()
        used = 0
        hits = 0
        misses = 0

        @wraps(original)
        def wrapped(geometria, configuracion, *args, **kwargs):
            nonlocal used, hits, misses
            # Extensiones de firma no forman parte del contrato de dos entradas.
            if args or kwargs:
                return original(geometria, configuracion, *args, **kwargs)
            key = _exacto_o_none([geometria, configuracion])
            if key is None or len(key) + 32 > max_bytes:
                return original(geometria, configuracion)
            hash(key)  # Bytes memoiza su hash; evita recorrer claves grandes dentro del lock.
            with lock:
                entry = cache.get(key)
                if entry is not None:
                    cache.move_to_end(key)
                else:
                    misses += 1
            if entry is not None:
                sealed, digest, weight = entry
                # SHA y copia fuera del lock. No se comparte la estructura mutable.
                if hashlib.sha256(sealed).digest() == digest:
                    copied = json.loads(sealed)
                    if _exacto_o_none([geometria, configuracion]) == key:
                        with lock:
                            hits += 1
                        return copied
                else:
                    with lock:
                        if cache.get(key) is entry:
                            used -= weight
                            del cache[key]
            # Single-flight: si otro hilo ya calcula esta clave, esperar (acotado) y reutilizar su resultado sellado. Si falla o
            # vence la espera, este hilo calcula por su cuenta: cada llamador recibe su propia excepción original.
            with lock:
                evento = en_curso.get(key)
                lider = evento is None
                if lider:
                    evento = en_curso[key] = Event()
            if not lider:
                evento.wait(espera_max_s)
                with lock:
                    entry = cache.get(key)
                if entry is not None and hashlib.sha256(entry[0]).digest() == entry[1]:
                    copied = json.loads(entry[0])
                    if _exacto_o_none([geometria, configuracion]) == key:
                        with lock:
                            hits += 1
                        return copied
                return original(geometria, configuracion)
            try:
                result = original(geometria, configuracion)  # Excepciones originales intactas.
            except BaseException:
                with lock:
                    en_curso.pop(key, None)
                evento.set()   # los que esperan calculan por su cuenta y reciben su propia excepción
                raise
            try:
                return _guardar(key, result, geometria, configuracion)
            finally:
                with lock:
                    en_curso.pop(key, None)
                evento.set()

        def _guardar(key, result, geometria, configuracion):
            nonlocal used
            sealed = _exacto_o_none(result)
            if sealed is None or _exacto_o_none([geometria, configuracion]) != key:
                return result
            weight = len(key) + len(sealed) + 32
            if weight > max_bytes:
                return result
            entry = (sealed, hashlib.sha256(sealed).digest(), weight)
            with lock:
                previous = cache.pop(key, None)
                if previous is not None:
                    used -= previous[2]
                while cache and (len(cache) >= max_entradas or used + weight > max_bytes):
                    _, discarded = cache.popitem(last=False)
                    used -= discarded[2]
                cache[key] = entry
                used += weight
            return result

        def cache_info():
            with lock:
                return {'entradas':len(cache), 'bytes':used, 'hits':hits, 'misses':misses,
                        'max_entradas':max_entradas, 'max_bytes':max_bytes}

        def cache_clear():
            nonlocal used, hits, misses
            with lock:
                cache.clear()
                used = hits = misses = 0

        wrapped.cache_info = cache_info
        wrapped.cache_clear = cache_clear
        return wrapped

    return decorate if function is None else decorate(function)
