"""Contingencia tabular supervisada (CSV/XLSX) hacia geometría BORRADOR, con traslado separado.

Reutiliza importacion_tabular.convertir_tablas, lectura_xlsx.leer_tablas_xlsx (y sus
límites ZIP/XML/fórmulas/vínculos) y gestion_geometria. No infiere unidades, campos,
cargas ni aprobaciones; no es visión ni ETABS y nunca aprueba geometría o ingeniería.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from uuid import uuid4

from . import contratos
from . import gestion_geometria as g
from .adaptador_etabs import BloqueoExclusivo
from .gestion_extraccion import json_desde_bytes
from .importacion_tabular import convertir_tablas, colecciones_tabulares
from .lectura_xlsx import leer_tablas_xlsx

CONTRATO = 'draft2model.tabular_web'
VERSION = '0.1.0'
CARPETA = 'tabulares'
PROCEDENCIA = 'contingencia_tabular_supervisada'
CSV_NOMBRES = tuple(n+'.csv' for n in contratos.COLECCIONES)  # niveles.csv, nodos.csv, muros.csv
XLSX_NOMBRE = 'libro.xlsx'
MAX_METADATOS = 256*1024
MAX_CSV = 4*1024*1024
MAX_XLSX = 16*1024*1024
NOMBRE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}')
IMPORTACION = ('importacion_pendiente.json', 'importacion.json')
ERRORES = (ValueError, OSError, TypeError, KeyError, RuntimeError, UnicodeError, OverflowError, RecursionError, IndexError)


class ErrorTabular(ValueError):
    """Mensaje público, sin rutas ni contenido privado."""


def _bytes(data):
    return (json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2)+'\n').encode('utf-8')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _id(value):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{32}', value) is None:
        raise ErrorTabular('Identificador inválido; se esperan 32 hexadecimales en minúsculas.')
    return value


def _hex64(value):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ErrorTabular('Huella inválida; se esperan 64 hexadecimales en minúsculas.')
    return value


def _sin_enlace(path, *, falta=False):
    path = Path(path)
    if falta and not os.path.lexists(path):
        return path
    info = os.lstat(path)
    if (path.resolve() != path or stat.S_ISLNK(info.st_mode)
            or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)):
        raise ErrorTabular('Directorio o archivo enlazado no permitido.')
    return path


def _leer(path):
    path = _sin_enlace(path)
    if not path.is_file():
        raise ErrorTabular('Archivo ausente.')
    return path.read_bytes()


def _nuevo(path, raw):
    with Path(path).open('xb') as stream:
        stream.write(raw)


def _decodificar(encoded, maximo):
    if not isinstance(encoded, str) or len(encoded) > 4*((maximo+2)//3):
        raise ErrorTabular('Contenido ausente o mayor que el límite permitido.')
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise ErrorTabular('Contenido base64 inválido.') from None
    if not raw or len(raw) > maximo:
        raise ErrorTabular('Contenido vacío o mayor que el límite permitido.')
    return raw


def _tablas(formato, originales, colecciones):
    """Texto CSV por colección desde los bytes originales exactos; el lector XLSX aplica sus límites."""
    if formato == 'csv':
        return {n: originales[n+'.csv'].decode('utf-8') for n in colecciones}
    return leer_tablas_xlsx(io.BytesIO(originales[XLSX_NOMBRE]), colecciones=tuple(colecciones))


def _convertir(caso, metadatos_raw, formato, originales):
    metadatos = json_desde_bytes(metadatos_raw, 'metadatos')
    if not isinstance(metadatos, dict) or metadatos.get('id') != caso:
        raise ErrorTabular('Los metadatos deben declarar el mismo caso del expediente como id.')
    # convertir_tablas exige revision borrador/aprobación null y unidad declarada: no se eleva ni se infiere.
    geometria = convertir_tablas(metadatos, _tablas(formato, originales, colecciones_tabulares(metadatos)))
    if geometria['revision'] != {'estado': 'borrador', 'aprobacion': None}:
        raise ErrorTabular('La salida importable debe ser borrador sin aprobación.')
    return geometria


class ServicioTabular:
    def __init__(self, app):
        self.app = app

    # -- expediente y carpetas ---------------------------------------------------------
    def _caso(self, caso, fingerprint):
        _hex64(fingerprint)
        folder, manifest, actual = self.app.expediente(caso)
        folder = Path(folder)
        if actual != fingerprint:
            raise ErrorTabular('El expediente cambió; vuelve a consultarlo.')
        _sin_enlace(Path(self.app.raiz)); _sin_enlace(folder)
        if folder.parent != Path(self.app.raiz) or not folder.is_dir():
            raise ErrorTabular('Expediente inválido o ausente.')
        for entry in manifest['archivos']:
            self.app._original(caso, entry['id'])  # huella de cada original del expediente
        if self.app.expediente(caso)[2] != fingerprint:
            raise ErrorTabular('El expediente cambió durante la comprobación.')
        return folder

    @staticmethod
    def _base(folder, crear=False):
        base = _sin_enlace(folder/CARPETA, falta=True)
        if os.path.lexists(base):
            if not base.is_dir():
                raise ErrorTabular('Directorio de versiones tabulares inválido.')
        elif crear:
            base.mkdir()
        return base

    def _publico(self, operacion, mensaje):
        try:
            with self.app.lock:
                return operacion()
        except ErrorTabular:
            raise
        except ERRORES:
            raise ErrorTabular(mensaje) from None

    # -- registro ------------------------------------------------------------------------
    def crear(self, body):
        def operacion():
            if not isinstance(body, dict) or set(body) != {'caso', 'expediente_sha256', 'metadatos_json', 'formato', 'archivos'}:
                raise ErrorTabular('Campos exactos: caso, expediente_sha256, metadatos_json, formato y archivos.')
            caso, fp = body['caso'], body['expediente_sha256']
            meta_text = body['metadatos_json']
            if not isinstance(meta_text, str) or not meta_text.strip() or len(meta_text.encode('utf-8')) > MAX_METADATOS:
                raise ErrorTabular('metadatos_json debe ser texto JSON de hasta 256 KiB.')
            metadatos_raw = meta_text.encode('utf-8')
            colecciones = colecciones_tabulares(json_desde_bytes(metadatos_raw, 'metadatos'))
            csv_nombres = tuple(n+'.csv' for n in colecciones)
            formato, items = body['formato'], body['archivos']
            if formato not in ('csv', 'xlsx') or not isinstance(items, list):
                raise ErrorTabular('Formato csv o xlsx y lista de archivos obligatorios.')
            for item in items:
                if (not isinstance(item, dict) or set(item) != {'nombre', 'contenido_base64'} or not isinstance(item['nombre'], str)
                        or NOMBRE.fullmatch(item['nombre']) is None or '..' in item['nombre']):
                    raise ErrorTabular('Cada archivo requiere nombre simple y contenido_base64.')
            nombres = [i['nombre'] for i in items]
            if formato == 'csv':
                if sorted(nombres) != sorted(csv_nombres):
                    raise ErrorTabular('CSV requiere exactamente: ' + ', '.join(csv_nombres) + '.')
                originales = {i['nombre']: _decodificar(i['contenido_base64'], MAX_CSV) for i in items}
                nombre_original = None
            else:
                if len(items) != 1 or not nombres[0].lower().endswith('.xlsx'):
                    raise ErrorTabular('XLSX requiere exactamente un libro .xlsx.')
                originales = {XLSX_NOMBRE: _decodificar(items[0]['contenido_base64'], MAX_XLSX)}
                nombre_original = nombres[0]
            folder = self._caso(caso, fp)
            geometria = _convertir(caso, metadatos_raw, formato, originales)
            geometria_raw = _bytes(geometria)
            archivos = {'metadatos.json': metadatos_raw, **originales, 'geometria.json': geometria_raw}
            base = self._base(folder, crear=True)
            ident = uuid4().hex
            meta = {'contrato': CONTRATO, 'version': VERSION, 'id': ident, 'caso': caso, 'expediente_sha256': fp,
                    'formato': formato, 'nombre_original': nombre_original, 'procedencia': PROCEDENCIA,
                    'archivos': {name: _sha(raw) for name, raw in archivos.items()},
                    'creado_utc': datetime.now(timezone.utc).isoformat()}
            with tempfile.TemporaryDirectory(prefix='.tab-', dir=base) as temporal:
                etapa = Path(temporal).resolve()
                if etapa.parent != base:
                    raise ErrorTabular('Temporal fuera del caso.')
                paquete = etapa/'paquete'
                paquete.mkdir()
                for name, raw in {**archivos, 'version.json': _bytes(meta)}.items():
                    _nuevo(paquete/name, raw)
                self._cargar(caso, ident, fp, ruta=paquete)  # reconversión desde la etapa antes de publicar
                self._caso(caso, fp)
                destino = base/ident
                if os.path.lexists(destino):
                    raise ErrorTabular('Destino existente; no se sobrescribe.')
                paquete.rename(destino)
            return self.consultar(caso, ident, expediente_sha256=fp)
        return self._publico(operacion, 'Tablas o metadatos inválidos para el contrato geométrico; no se registró nada.')

    # -- carga verificada --------------------------------------------------------------
    def _cargar(self, caso, version, fp, *, ruta=None):
        folder = self._caso(caso, fp)
        target = _sin_enlace(ruta if ruta is not None else self._base(folder)/_id(version))
        if not target.is_dir():
            raise ErrorTabular('Versión tabular ausente.')
        meta_raw = _leer(target/'version.json')
        meta = json_desde_bytes(meta_raw, 'version.json')
        campos = {'contrato', 'version', 'id', 'caso', 'expediente_sha256', 'formato', 'nombre_original', 'procedencia',
                  'archivos', 'creado_utc'}
        if (not isinstance(meta, dict) or set(meta) != campos or meta['contrato'] != CONTRATO or meta['version'] != VERSION
                or meta['id'] != version or meta['caso'] != caso or meta['expediente_sha256'] != fp
                or meta['procedencia'] != PROCEDENCIA or meta['formato'] not in ('csv', 'xlsx')
                or not isinstance(meta['archivos'], dict)):
            raise ErrorTabular('Metadatos de versión tabular inválidos o de otro caso.')
        metadatos_raw = _leer(target/'metadatos.json')
        colecciones = colecciones_tabulares(json_desde_bytes(metadatos_raw, 'metadatos'))
        csv_nombres = tuple(n+'.csv' for n in colecciones)
        esperados = ['metadatos.json', 'geometria.json', *(csv_nombres if meta['formato'] == 'csv' else (XLSX_NOMBRE,))]
        if sorted(meta['archivos']) != sorted(esperados):
            raise ErrorTabular('Archivos de la versión tabular inválidos.')
        presentes = sorted(p.name for p in target.iterdir())
        extra = sorted(set(presentes) - set(esperados) - {'version.json'})
        if not set(esperados) | {'version.json'} <= set(presentes) or not set(extra) <= set(IMPORTACION):
            raise ErrorTabular('Contenido de la versión tabular inválido.')
        raw = {}
        for name in esperados:
            raw[name] = _leer(target/name)
            if _sha(raw[name]) != meta['archivos'][name]:
                raise ErrorTabular('Archivo de la versión tabular alterado.')
        originales = {k: v for k, v in raw.items() if k not in ('metadatos.json', 'geometria.json')}
        geometria = _convertir(caso, raw['metadatos.json'], meta['formato'], originales)
        # Reconvertir desde fuentes: una alteración coherente de geometria.json (con hash rehecho) no basta.
        if _bytes(geometria) != raw['geometria.json']:
            raise ErrorTabular('La geometría guardada no corresponde a sus tablas originales.')
        self._caso(caso, fp)
        if _leer(target/'version.json') != meta_raw or any(_leer(target/n) != v for n, v in raw.items()):
            raise ErrorTabular('La versión tabular cambió durante la consulta.')
        return target, meta, meta_raw, geometria

    def _importacion(self, target, version, huella):
        accepted, marker = target/'importacion.json', target/'importacion_pendiente.json'
        if os.path.lexists(accepted):
            saved = json_desde_bytes(_leer(accepted), 'importacion.json')
            if not isinstance(saved, dict) or set(saved) != {'tabular', 'huella_tabular', 'geometria'} or saved['tabular'] != version:
                raise ErrorTabular('Recibo de importación inválido.')
            return {'estado': 'importada', 'geometria': _id(saved['geometria']), 'huella_tabular': _hex64(saved['huella_tabular'])}
        if os.path.lexists(marker):
            return {'estado': 'interrumpida', 'geometria': None, 'huella_tabular': huella}
        return None

    def _proyeccion(self, caso, fp, target, meta, meta_raw, geometria):
        huella = _sha(meta_raw)
        return {'id': meta['id'], 'caso': caso, 'expediente_sha256': fp, 'formato': meta['formato'],
                'nombre_original': meta['nombre_original'], 'archivos': dict(meta['archivos']), 'huella_tabular': huella,
                'creado_utc': meta['creado_utc'], 'procedencia': PROCEDENCIA,
                'version_contrato': geometria['version_contrato'],
                'resumen': {**{n: len(geometria[n]) for n in ('vertices', 'superficies', 'aberturas') if n in geometria}, 'unidad_longitud': geometria['unidad_longitud'], 'niveles': len(geometria['niveles']),
                            'nodos': len(geometria['nodos']), 'muros': len(geometria['muros']),
                            'faltantes': len(geometria['faltantes']), 'procedencia_declarada': geometria['procedencia']['tipo']},
                'estado': 'borrador', 'aprobacion': None, 'importacion': self._importacion(target, meta['id'], huella),
                'disponible_para_modelado': False, 'aprueba_geometria': False, 'aprueba_ingenieria': False,
                'aviso': 'Ingreso tabular supervisado convertido a geometría en borrador; no es visión, ETABS ni aprobación.'}

    def consultar(self, caso, version, *, expediente_sha256):
        def operacion():
            target, meta, meta_raw, geometria = self._cargar(caso, _id(version), expediente_sha256)
            return self._proyeccion(caso, expediente_sha256, target, meta, meta_raw, geometria)
        return self._publico(operacion, 'Versión tabular inválida, alterada o de otro caso; vuelve a consultar el expediente.')

    def listar(self, caso, *, expediente_sha256):
        def operacion():
            base = self._base(self._caso(caso, expediente_sha256))
            rows = []
            for path in sorted(base.iterdir()) if base.is_dir() else []:
                if re.fullmatch('[0-9a-f]{32}', path.name) is None:
                    continue  # temporales .tab-* no son versiones
                try:
                    item = self.consultar(caso, path.name, expediente_sha256=expediente_sha256)
                    rows.append({'id': path.name, 'vigente': True, 'formato': item['formato'], 'estado': 'borrador',
                                 'importacion': item['importacion']})
                except ERRORES:
                    rows.append({'id': path.name, 'vigente': False, 'problemas': ['version_no_vigente']})
            self._caso(caso, expediente_sha256)
            return {'caso': caso, 'expediente_sha256': expediente_sha256, 'versiones': rows}
        return self._publico(operacion, 'No se pudieron listar las versiones tabulares.')

    # -- traslado separado al historial geométrico ----------------------------------------
    def importar(self, body):
        def operacion():
            if not isinstance(body, dict) or set(body) != {'caso', 'expediente_sha256', 'version', 'huella_tabular', 'confirmacion_explicita'}:
                raise ErrorTabular('Campos exactos: caso, expediente_sha256, version, huella_tabular y confirmacion_explicita.')
            if body['confirmacion_explicita'] is not True:
                raise ErrorTabular('Confirma explícitamente el traslado del borrador.')
            caso, fp, version = body['caso'], body['expediente_sha256'], _id(body['version'])
            huella = _hex64(body['huella_tabular'])
            folder = self._caso(caso, fp)
            with BloqueoExclusivo(_sin_enlace(folder/'tabular_web.lock', falta=True)):
                target, meta, meta_raw, geometria = self._cargar(caso, version, fp)
                if _sha(meta_raw) != huella:
                    raise ErrorTabular('La huella de la versión tabular no coincide.')
                estado = self._importacion(target, version, huella)
                if estado is not None and estado['estado'] == 'importada':
                    ident = estado['geometria']
                    if estado['huella_tabular'] != huella:
                        raise ErrorTabular('Recibo de importación de otra huella.')
                elif estado is not None:
                    raise ErrorTabular('Importación interrumpida: queda evidencia y requiere revisión; no se repite automáticamente.')
                else:
                    _nuevo(target/'importacion_pendiente.json', _bytes({'tabular': version, 'huella_tabular': huella}))
                    ident = g.importar_geometria(self.app.raiz, caso, target/'geometria.json').identificador
                    self._verificar_geometria(caso, ident, geometria)
                    self._cargar(caso, version, fp)
                    _nuevo(target/'importacion.json', _bytes({'tabular': version, 'huella_tabular': huella, 'geometria': ident}))
                self._verificar_geometria(caso, ident, geometria)  # replay: recibo revalidado contra el historial
                self._cargar(caso, version, fp)
            return {'caso': caso, 'expediente_sha256': fp, 'tabular': version, 'huella_tabular': huella, 'geometria': ident,
                    'estado': 'borrador', 'aprobacion': None, 'disponible_para_modelado': False,
                    'aprueba_geometria': False, 'aprueba_ingenieria': False}
        return self._publico(operacion, 'No se importó: versión, huella o expediente sin vigencia.')

    def _verificar_geometria(self, caso, ident, geometria):
        checked = g.consultar_version(self.app.raiz, caso, _id(ident))
        if (not checked.comprobacion.correcta or checked.geometria != geometria
                or checked.geometria['revision'] != {'estado': 'borrador', 'aprobacion': None}):
            raise ErrorTabular('La versión geométrica importada no es vigente o no coincide con la tabla.')
