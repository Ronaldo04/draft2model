"""Reutilización LRU por proceso de validar_geometria (función pura del JSON de geometría), medida en 279.

Una verificación de análisis aceptado llamaba 56 veces a validar_geometria (≈ 43 s en caliente) porque cada consultar_version
revalida la cadena completa de versiones padre. La validación sigue ejecutándose ante cualquier cambio: la clave es TODO el JSON
de la geometría (revisión incluida), comprobado antes y después; el resultado se sella como JSON canónico con SHA256 y cada
consumidor recibe un ResultadoValidacion reconstruido e independiente. Resultados con valores no JSON estrictos (NaN, tuplas,
tipos propios) no se guardan y pasan al original. Sin estado persistido, TTL ni confianza por mtime; no guarda lecturas de
archivos, aprobaciones, vigencia ni evidencias (esas comprobaciones siguen fuera, en gestion_geometria y sus llamadores).
"""
from collections import OrderedDict
from functools import wraps
import hashlib
import json
from threading import RLock

from .cache_malla_pura import _canonico_o_none, _exacto_o_none

MAX_ENTRADAS = 32
MAX_BYTES = 64 * 1024 * 1024
CAMPOS = ("errores", "advertencias", "faltantes", "bloqueos", "datos_sinteticos", "huella_contenido", "geometria_m", "derivados_m",
          "version_contrato")


def _sellar(resultado, hallazgo_cls):
    try:
        datos = {}
        for campo in CAMPOS:
            valor = getattr(resultado, campo)
            if campo in ("errores", "advertencias"):
                if not all(type(h) is hallazgo_cls for h in valor):
                    return None
                valor = [[h.ruta, h.codigo, h.mensaje] for h in valor]
            datos[campo] = valor
    except AttributeError:
        return None
    if _canonico_o_none(datos) is None:   # solo JSON estricto (sin NaN, tuplas ni tipos propios)
        return None
    # Se sella conservando el ORDEN de inserción de los dicts (huellas aguas abajo pueden serializar sin sort_keys).
    return json.dumps(datos, ensure_ascii=False, allow_nan=False).encode("utf-8")


def reutilizar_validacion(function=None, *, max_entradas=MAX_ENTRADAS, max_bytes=MAX_BYTES):
    if type(max_entradas) is not int or not 1 <= max_entradas <= MAX_ENTRADAS:
        raise ValueError("max_entradas debe estar entre 1 y " + str(MAX_ENTRADAS))
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_BYTES:
        raise ValueError("max_bytes debe estar entre 1 y 64 MiB")

    def decorate(original):
        cache = OrderedDict()
        lock = RLock()
        estado = {"usado": 0, "aciertos": 0, "fallos": 0}

        def reconstruir(sellado, tipo_resultado, hallazgo_cls):
            datos = json.loads(sellado)
            for campo in ("errores", "advertencias"):
                datos[campo] = [hallazgo_cls(*h) for h in datos[campo]]
            return tipo_resultado(**datos)

        @wraps(original)
        def wrapped(data, *args, **kwargs):
            if args or kwargs:
                return original(data, *args, **kwargs)
            key = _exacto_o_none(data)
            if key is None or len(key) + 32 > max_bytes:
                return original(data)
            with lock:
                entry = cache.get(key)
                if entry is not None:
                    cache.move_to_end(key)
                else:
                    estado["fallos"] += 1
            if entry is not None:
                sellado, digest, peso, tipo_resultado, hallazgo_cls = entry
                if hashlib.sha256(sellado).digest() == digest and _exacto_o_none(data) == key:
                    copia = reconstruir(sellado, tipo_resultado, hallazgo_cls)
                    with lock:
                        estado["aciertos"] += 1
                    return copia
                with lock:
                    if cache.get(key) is entry:
                        estado["usado"] -= peso
                        del cache[key]
            resultado = original(data)   # excepciones originales intactas
            from .validacion_geometria import Hallazgo
            sellado = _sellar(resultado, Hallazgo)
            if sellado is None or _exacto_o_none(data) != key:
                return resultado
            peso = len(key) + len(sellado) + 32
            if peso > max_bytes:
                return resultado
            # El resultado devuelto también debe ser idéntico al que se reconstruirá desde el sello.
            entry = (sellado, hashlib.sha256(sellado).digest(), peso, type(resultado), Hallazgo)
            with lock:
                previo = cache.pop(key, None)
                if previo is not None:
                    estado["usado"] -= previo[2]
                while cache and (len(cache) >= max_entradas or estado["usado"] + peso > max_bytes):
                    _, descartado = cache.popitem(last=False)
                    estado["usado"] -= descartado[2]
                cache[key] = entry
                estado["usado"] += peso
            return reconstruir(sellado, type(resultado), Hallazgo)

        def cache_info():
            with lock:
                return {"entradas": len(cache), "bytes": estado["usado"], "hits": estado["aciertos"], "misses": estado["fallos"],
                        "max_entradas": max_entradas, "max_bytes": max_bytes}

        def cache_clear():
            with lock:
                cache.clear()
                estado.update(usado=0, aciertos=0, fallos=0)

        wrapped.cache_info = cache_info
        wrapped.cache_clear = cache_clear
        return wrapped

    return decorate if function is None else decorate(function)
