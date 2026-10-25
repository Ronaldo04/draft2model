"""Publicación y reproducción de derivados raster con identidad del original.

IDs direccionados por contenido: SHA256 de registro.json. Reescribir config,
render o matrices coherentemente no valida una versión ya publicada.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import stat
import tempfile

from . import preprocesamiento as core
from .gestion_extraccion import json_desde_bytes, _publicar
from .ingreso import file_hash

CARPETA = 'preprocesamientos'
ARCHIVOS = ('imagen.png', 'config.json', 'transformacion.json', 'registro.json')


def _json(data):
    return (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _ruta(root, valor, *, directorio=False):
    if not isinstance(valor, (str, Path)):
        raise ValueError('Ruta no admitida.')
    path = root / valor
    info = path.lstat()
    if (path.resolve() != path or not path.is_relative_to(root)
            or stat.S_ISLNK(info.st_mode)
            or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)
            or not (stat.S_ISDIR(info.st_mode) if directorio else stat.S_ISREG(info.st_mode))):
        raise ValueError('Ruta enlazada, fuera del caso o de tipo no admitido.')
    return path


def _original(expediente, archivo_id):
    manifest_path = Path(expediente).absolute()
    root = manifest_path.parent
    _ruta(root, manifest_path)
    raw = manifest_path.read_bytes()
    manifest = json_desde_bytes(raw, 'expediente.json')
    if (not isinstance(manifest, dict) or not isinstance(manifest.get('archivos'), list)
            or not isinstance(manifest.get('id'), str) or not isinstance(manifest.get('alcance'), dict)
            or manifest.get('uso_autorizado_declarado') is not True):
        raise ValueError('Expediente inválido o uso no declarado.')
    if not isinstance(archivo_id, str):
        raise ValueError('Identificador de archivo inválido.')
    entries = [e for e in manifest['archivos'] if isinstance(e, dict) and e.get('id') == archivo_id]
    if len(entries) != 1:
        raise ValueError('Original ausente o ambiguo.')
    entry = entries[0]
    source = _ruta(root, entry.get('archivo'))
    if source.suffix.lower() not in {'.png', '.jpg', '.jpeg'} or file_hash(source) != entry.get('sha256'):
        raise ValueError('Se requiere original PNG/JPEG registrado con SHA256 vigente.')
    # Reusar los límites y la orientación del recorrido raster registrado.
    from .recortes import cargar_raster_orientado
    image, exif = cargar_raster_orientado(source)
    image.close()
    return root, manifest_path, raw, manifest, entry, source, exif


def _render(source, config, parent):
    with tempfile.TemporaryDirectory(prefix='.preprocesamiento-', dir=parent) as temp:
        output = Path(temp) / 'render'
        registro = core.procesar_imagen(source, config, output)
        return {'imagen.png': (output / 'imagen.png').read_bytes(),
                'config.json': (output / 'config.json').read_bytes(),
                'transformacion.json': registro.read_bytes()}


def _estable(path, raw, source, digest):
    if path.read_bytes() != raw or file_hash(source) != digest:
        raise ValueError('El expediente u original cambió durante el preprocesamiento.')


def informacion_original(expediente, archivo_id):
    """Metadatos JSON para configurar esquinas sobre píxeles almacenados, no el visor EXIF."""
    _, path, raw, manifest, entry, source, exif = _original(expediente, archivo_id)
    _estable(path, raw, source, entry['sha256'])
    return {'caso':manifest['id'], 'archivo_id':archivo_id, 'original_sha256':entry['sha256'],
            'expediente_sha256':_sha(raw), 'alcance':copy.deepcopy(manifest['alcance']),
            'exif_original':copy.deepcopy(exif), 'config_sobre':'pixeles_original_almacenado_sin_auto_EXIF'}


def registrar_preprocesamiento(expediente, archivo_id, config, *, revisor_declarado, motivo):
    """Publica versión nueva; retorna ruta de registro.json. Sin EXIF automático."""
    for valor in (revisor_declarado, motivo):
        if not isinstance(valor, str) or not valor.strip():
            raise ValueError('Revisor declarado y motivo no vacíos son obligatorios.')
    config_bytes = _json(config)
    if len(config_bytes) > 65536:
        raise ValueError('Configuración supera 64 KiB.')
    config = json_desde_bytes(config_bytes, 'config.json')
    root, path, raw, manifest, entry, source, exif = _original(expediente, archivo_id)
    payload = _render(source, config, root)
    transformacion = json_desde_bytes(payload['transformacion.json'], 'transformacion.json')
    if transformacion.get('original_sha256') != entry['sha256']:
        raise ValueError('El render no procede de los bytes originales registrados.')
    registro = {
        'contrato': 'draft2model.revision_preprocesamiento', 'version': '0.1.0',
        'caso': manifest['id'], 'archivo_id': archivo_id, 'pagina': 1,
        'expediente_sha256': _sha(raw), 'original_sha256': entry['sha256'],
        'alcance': copy.deepcopy(manifest['alcance']),
        'creado_utc': datetime.now(timezone.utc).isoformat(),
        'revisor_declarado': revisor_declarado, 'motivo': motivo,
        'identidad_revisor': 'declarada_no_verificada', 'aprobacion_ingenieria': None,
        'imagen_sha256': _sha(payload['imagen.png']),
        'config_sha256': _sha(payload['config.json']),
        'transformacion_sha256': _sha(payload['transformacion.json']),
        'exif_original': exif,
        'politica_orientacion': 'original_almacenado_sin_auto_EXIF; perspectiva_rotacion_contraste_explicitos; PNG_sin_EXIF',
        'escala_metrica': None, 'mejora_precision_vision': 'no_evaluada',
    }
    payload['registro.json'] = _json(registro)
    identificador = _sha(payload['registro.json'])
    _estable(path, raw, source, entry['sha256'])
    destino = _publicar(root, CARPETA, identificador, payload)
    _estable(path, raw, source, entry['sha256'])
    consultar_preprocesamiento(path, identificador)
    return destino / 'registro.json'


def consultar_preprocesamiento(expediente, identificador):
    """Reproduce bytes/config/matrices y devuelve copias del registro y la transformación."""
    if not isinstance(identificador, str) or not re.fullmatch(r'[0-9a-f]{64}', identificador):
        raise ValueError('ID de preprocesamiento debe ser SHA256 del registro publicado.')
    root = Path(expediente).absolute().parent
    carpeta = _ruta(root, CARPETA, directorio=True)
    carpeta = _ruta(carpeta, identificador, directorio=True)
    snapshots = {nombre: _ruta(carpeta, nombre).read_bytes() for nombre in ARCHIVOS}
    if _sha(snapshots['registro.json']) != identificador:
        raise ValueError('Registro de preprocesamiento alterado: ID de contenido incompatible.')
    registro = json_desde_bytes(snapshots['registro.json'], 'registro.json')
    if not isinstance(registro, dict):
        raise ValueError('Registro de preprocesamiento inválido.')
    root, path, raw, manifest, entry, source, exif = _original(expediente, registro.get('archivo_id'))
    if (registro.get('contrato') != 'draft2model.revision_preprocesamiento' or registro.get('version') != '0.1.0'
            or registro.get('caso') != manifest['id'] or type(registro.get('pagina')) is not int or registro['pagina'] != 1
            or registro.get('expediente_sha256') != _sha(raw) or registro.get('original_sha256') != entry['sha256']
            or _json(registro.get('alcance')) != _json(manifest['alcance'])
            or _json(registro.get('exif_original')) != _json(exif)):
        raise ValueError('Preprocesamiento de otro original, expediente o alcance.')
    config = json_desde_bytes(snapshots['config.json'], 'config.json')
    reproducido = _render(source, config, root)
    for nombre, campo in (('imagen.png', 'imagen_sha256'), ('config.json', 'config_sha256'),
                           ('transformacion.json', 'transformacion_sha256')):
        if snapshots[nombre] != reproducido[nombre] or _sha(snapshots[nombre]) != registro.get(campo):
            raise ValueError('Bytes, configuración o transformación no reproducibles desde el original.')
    for nombre in ARCHIVOS:
        if _ruta(carpeta, nombre).read_bytes() != snapshots[nombre]:
            raise ValueError('Derivado modificado durante su comprobación.')
    _estable(path, raw, source, entry['sha256'])
    return {'id': identificador, 'ruta': carpeta, 'registro': copy.deepcopy(registro),
            'config': copy.deepcopy(config),
            'transformacion': json_desde_bytes(snapshots['transformacion.json'], 'transformacion.json'),
            'imagen_bytes': snapshots['imagen.png']}


def historial_preprocesamientos(expediente, archivo_id=None):
    """Lista versiones verificadas; un registro corrupto se informa, no se oculta."""
    root = Path(expediente).absolute().parent
    grupo = root / CARPETA
    if not grupo.exists() and not grupo.is_symlink():
        return []
    _ruta(root, CARPETA, directorio=True)
    resultado = []
    for carpeta in sorted(grupo.iterdir()):
        if carpeta.name.startswith('.tmp-'):
            continue
        consulta = consultar_preprocesamiento(expediente, carpeta.name)
        if archivo_id is None or consulta['registro']['archivo_id'] == archivo_id:
            resultado.append({'id': consulta['id'], 'registro': consulta['registro'],
                              'config': consulta['config'], 'transformacion': consulta['transformacion']})
    return sorted(resultado, key=lambda item: item['registro']['creado_utc'])
