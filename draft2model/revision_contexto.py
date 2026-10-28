"""Contexto técnico versionado: corpus, capa de sitio y reglas declaradas, con consultas derivadas.

Reutiliza los validadores y cálculos nativos de fuentes.py, sitio.py y
evaluacion_estructural.py. No crea umbrales, normativa, cartografía ni aprobaciones:
solo conserva contratos que ya traen su revisión declarada y pasan esos validadores.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import tempfile
from uuid import uuid4

from . import evaluacion_estructural as evaluacion
from . import fuentes
from . import sitio
from .gestion_extraccion import json_desde_bytes

CONTRATO = 'draft2model.contexto_versionado'
CONTRATO_DERIVADO = 'draft2model.contexto_derivado'
VERSION = '0.1.0'
GRUPO = 'contexto'
TIPOS = {'corpus': 'corpus.json', 'sitio': 'capa.json', 'reglas': 'reglas.json'}
DERIVADOS = ('recuperacion', 'sitio', 'evaluacion')
MAX_JSON = 1024*1024              # contrato JSON declarado
MAX_ARCHIVO = 4*1024*1024         # documento de corpus decodificado
MAX_TOTAL = 16*1024*1024          # suma de documentos de corpus
MAX_ARCHIVOS = 20
MAX_CONSULTA = 500
NOMBRE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}')
RESERVADOS = {'version.json', *TIPOS.values(), 'salida.json'}
AVISO = ('Contexto declarado por quien lo registra: identidad del revisor declarada y no verificada. '
         'No constituye verificación profesional ni aprueba resultados o informes.')
ERRORES = (ValueError, OSError, TypeError, KeyError, RuntimeError, UnicodeError, OverflowError, RecursionError)


class ErrorContexto(ValueError):
    """Mensaje público, sin rutas ni contenido privado."""


def _canonico(data):
    return (json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))+'\n').encode('utf-8')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _uuid(value):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{32}', value) is None:
        raise ErrorContexto('Identificador inválido; se esperan 32 hexadecimales en minúsculas.')
    return value


def _hex64(value):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ErrorContexto('Huella inválida; se esperan 64 hexadecimales en minúsculas.')
    return value


def _sin_enlace(path):
    info = os.lstat(path)
    if (Path(path).resolve() != Path(path) or stat.S_ISLNK(info.st_mode)
            or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)):
        raise ErrorContexto('Directorio o archivo enlazado no permitido.')
    return Path(path)


def _texto_json(value, etiqueta):
    if not isinstance(value, str) or not value.strip():
        raise ErrorContexto(etiqueta+': se requiere el JSON completo como texto.')
    raw = value.encode('utf-8')
    if len(raw) > MAX_JSON:
        raise ErrorContexto(etiqueta+': supera 1 MiB.')
    json_desde_bytes(raw, etiqueta)  # estricto: sin claves repetidas ni NaN
    return raw


def _campos(body, campos):
    if not isinstance(body, dict) or set(body) != set(campos):
        raise ErrorContexto('Campos de la solicitud inválidos: se exigen exactamente '+', '.join(sorted(campos))+'.')


def _aprobacion(data):
    """Declaración tal como viene en el contrato; nunca se genera aquí."""
    if 'aprobacion' in data:
        ap = data['aprobacion']
        return {k: ap[k] for k in ('revisor_declarado', 'fecha', 'alcance')}
    ap = data['revision']['aprobacion']
    return {k: ap[k] for k in ('revisor_declarado', 'fecha', 'motivo', 'alcance')}


class ServicioContexto:
    def __init__(self, app):
        self.app = app

    # -- rutas del caso -----------------------------------------------------------
    def _caso(self, caso, fingerprint):
        _hex64(fingerprint)
        folder, _, actual = self.app.expediente(caso)
        folder = Path(folder)
        if actual != fingerprint:
            raise ErrorContexto('El expediente cambió; vuelve a consultarlo.')
        _sin_enlace(Path(self.app.raiz)); _sin_enlace(folder)
        if folder.parent != Path(self.app.raiz) or not folder.is_dir():
            raise ErrorContexto('Expediente inválido o ausente.')
        return folder

    @staticmethod
    def _grupo(folder, nombre, crear=False):
        base = folder/GRUPO
        for path in (base, base/nombre):
            if os.path.lexists(path):
                _sin_enlace(path)
                if not path.is_dir():
                    raise ErrorContexto('Directorio de contexto inválido.')
            elif crear:
                path.mkdir()
        return base/nombre

    # -- validación nativa ---------------------------------------------------------
    @staticmethod
    def _nativo(tipo, carpeta):
        path = carpeta/TIPOS[tipo]
        if tipo == 'corpus':
            data = fuentes.cargar_corpus(path)  # rutas, hashes y aprobación declarada vigente
            return data, fuentes.huella_corpus(data), data['datos_sinteticos']
        raw = path.read_bytes()
        data = json_desde_bytes(raw, TIPOS[tipo])
        if tipo == 'sitio':
            # El núcleo solo valida al consultar: el punto (0, 0) se usa únicamente
            # para ejercitar su validador completo; su resultado se descarta.
            sitio.consultar_sitio(path, 0.0, 0.0)
            return data, sitio.huella_capa(data), data['datos_sinteticos']
        check = evaluacion.validar_reglas(data)
        if not check['correcta'] or not check['aprobacion_vigente']:
            raise ErrorContexto('Reglas sin validar o sin aprobación declarada vigente: '+' '.join(check['errores']))
        return data, check['huella'], data['datos_sinteticos']

    # -- registro ------------------------------------------------------------------
    def _registrar(self, tipo, caso, fingerprint, archivos):
        folder = self._caso(caso, fingerprint)
        base = self._grupo(folder, tipo, crear=True)
        ident = uuid4().hex
        with tempfile.TemporaryDirectory(prefix='.ctx-', dir=base) as temporal:
            etapa = Path(temporal).resolve()
            if etapa.parent != base:
                raise ErrorContexto('Temporal fuera del caso.')
            paquete = etapa/'paquete'
            paquete.mkdir()
            for name, raw in archivos.items():
                with (paquete/name).open('xb') as stream:
                    stream.write(raw)
            data, huella, sintetico = self._nativo(tipo, paquete)  # validador nativo sobre la etapa
            meta = {'contrato': CONTRATO, 'version': VERSION, 'tipo': tipo, 'id': ident, 'caso': caso,
                    'creado_utc': datetime.now(timezone.utc).isoformat(), 'huella': huella,
                    'datos_sinteticos': sintetico, 'archivos': {name: _sha(raw) for name, raw in archivos.items()}}
            with (paquete/'version.json').open('xb') as stream:
                stream.write(_canonico(meta))
            if any((paquete/name).read_bytes() != raw for name, raw in archivos.items()):
                raise ErrorContexto('El contrato cambió durante el registro.')
            self._caso(caso, fingerprint)
            destino = base/ident
            if os.path.lexists(destino):
                raise ErrorContexto('Destino existente; no se sobrescribe.')
            paquete.rename(destino)  # publicación atómica dentro de contexto/<tipo>/
        return self.consultar(caso, tipo, ident, expediente_sha256=fingerprint)

    def _publico(self, operacion, mensaje):
        try:
            with self.app.lock:
                return operacion()
        except ErrorContexto:
            raise
        except ERRORES:
            raise ErrorContexto(mensaje) from None

    def registrar_corpus(self, body):
        def operacion():
            _campos(body, {'caso', 'expediente_sha256', 'manifiesto_json', 'archivos'})
            manifest = _texto_json(body['manifiesto_json'], 'manifiesto')
            items = body['archivos']
            if not isinstance(items, list) or not 1 <= len(items) <= MAX_ARCHIVOS:
                raise ErrorContexto('Adjunta de 1 a 20 documentos del corpus.')
            files, total = {}, 0
            for item in items:
                if not isinstance(item, dict) or set(item) != {'nombre', 'contenido_base64'}:
                    raise ErrorContexto('Cada documento requiere exactamente nombre y contenido_base64.')
                name, encoded = item['nombre'], item['contenido_base64']
                if (not isinstance(name, str) or NOMBRE.fullmatch(name) is None or '..' in name
                        or name.lower() in RESERVADOS or name in files):
                    raise ErrorContexto('Nombre de documento inválido, reservado o repetido (solo nombre simple).')
                if not isinstance(encoded, str) or len(encoded) > 4*((MAX_ARCHIVO+2)//3):
                    raise ErrorContexto('Documento ausente o mayor de 4 MiB.')
                try:
                    raw = base64.b64decode(encoded, validate=True)
                except (binascii.Error, ValueError):
                    raise ErrorContexto('Contenido base64 inválido.') from None
                if not raw or len(raw) > MAX_ARCHIVO:
                    raise ErrorContexto('Documento vacío o mayor de 4 MiB.')
                total += len(raw)
                if total > MAX_TOTAL:
                    raise ErrorContexto('Los documentos superan 16 MiB en total.')
                files[name] = raw
            declared = json_desde_bytes(manifest, 'manifiesto')
            documents = declared.get('documentos') if isinstance(declared, dict) else None
            if (not isinstance(documents, list) or not all(isinstance(d, dict) for d in documents)
                    or sorted(d.get('archivo') for d in documents if isinstance(d.get('archivo'), str)) != sorted(files)
                    or len(documents) != len(files)):
                raise ErrorContexto('Los documentos adjuntos deben coincidir exactamente con los declarados en el manifiesto.')
            return self._registrar('corpus', body['caso'], body['expediente_sha256'], {'corpus.json': manifest, **files})
        return self._publico(operacion, 'Corpus inválido, sin aprobación declarada vigente o con documentos alterados.')

    def registrar_sitio(self, body):
        def operacion():
            _campos(body, {'caso', 'expediente_sha256', 'capa_json'})
            raw = _texto_json(body['capa_json'], 'capa de sitio')
            return self._registrar('sitio', body['caso'], body['expediente_sha256'], {'capa.json': raw})
        return self._publico(operacion, 'Capa de sitio inválida o sin aprobación declarada vigente.')

    def registrar_reglas(self, body):
        def operacion():
            _campos(body, {'caso', 'expediente_sha256', 'reglas_json'})
            raw = _texto_json(body['reglas_json'], 'reglas')
            return self._registrar('reglas', body['caso'], body['expediente_sha256'], {'reglas.json': raw})
        return self._publico(operacion, 'Reglas inválidas o sin aprobación declarada vigente.')

    # -- carga verificada ------------------------------------------------------------
    def _cargar(self, folder, tipo, ident):
        if tipo not in TIPOS:
            raise ErrorContexto('Tipo de contexto inválido.')
        target = self._grupo(folder, tipo)/_uuid(ident)
        _sin_enlace(target)
        if not target.is_dir():
            raise ErrorContexto('Versión de contexto ausente.')
        meta_raw = _sin_enlace(target/'version.json').read_bytes()
        meta = json_desde_bytes(meta_raw, 'version.json')
        campos = {'contrato', 'version', 'tipo', 'id', 'caso', 'creado_utc', 'huella', 'datos_sinteticos', 'archivos'}
        if (not isinstance(meta, dict) or set(meta) != campos or meta['contrato'] != CONTRATO or meta['version'] != VERSION
                or meta['tipo'] != tipo or meta['id'] != ident or type(meta['datos_sinteticos']) is not bool
                or not isinstance(meta['archivos'], dict) or TIPOS[tipo] not in meta['archivos']):
            raise ErrorContexto('Metadatos de contexto inválidos.')
        if sorted(p.name for p in target.iterdir()) != sorted([*meta['archivos'], 'version.json']):
            raise ErrorContexto('Contenido de la versión de contexto inválido.')
        raw = {}
        for name, digest in meta['archivos'].items():
            if not isinstance(name, str) or NOMBRE.fullmatch(name) is None:
                raise ErrorContexto('Metadatos de contexto inválidos.')
            raw[name] = _sin_enlace(target/name).read_bytes()
            if _sha(raw[name]) != digest:
                raise ErrorContexto('Archivo de contexto alterado.')
        data, huella, sintetico = self._nativo(tipo, target)
        if huella != meta['huella'] or sintetico != meta['datos_sinteticos']:
            raise ErrorContexto('El contrato no coincide con su registro.')
        return {'target': target, 'meta': meta, 'meta_raw': meta_raw, 'raw': raw, 'data': data}

    @staticmethod
    def _sin_cambios(item):
        target = item['target']
        if ((target/'version.json').read_bytes() != item['meta_raw']
                or any((target/name).read_bytes() != raw for name, raw in item['raw'].items())):
            raise ErrorContexto('El contexto cambió durante la consulta.')

    @staticmethod
    def _proyeccion(tipo, item, caso, fingerprint):
        meta, data = item['meta'], item['data']
        if tipo == 'corpus':
            resumen = {'documentos': [{k: d[k] for k in ('id', 'titulo', 'edicion', 'sha256')} for d in data['documentos']],
                       'fragmentos': len(data['fragmentos'])}
        elif tipo == 'sitio':
            resumen = {'fuente': data['fuente'], 'fecha': data['fecha'], 'precision_m': data['precision_m'],
                       'crs': data['crs'], 'zonas': [{'id': z['id'], 'etiqueta': z['etiqueta']} for z in data['zonas']]}
        else:
            resumen = {'reglas_id': data['id'], 'reglas': [{k: r[k] for k in ('id', 'variable', 'unidad', 'comparador', 'limite')}
                                                           | {'fuente': r['fuente']} for r in data['reglas']]}
        return {'id': meta['id'], 'tipo': tipo, 'caso': caso, 'expediente_sha256': fingerprint,
                'creado_utc': meta['creado_utc'], 'huella': meta['huella'], 'archivos': dict(meta['archivos']),
                'datos_sinteticos': meta['datos_sinteticos'], 'aprobacion_declarada': _aprobacion(data),
                'identidad_revisor': 'declarada_no_verificada', 'verificacion_profesional': False,
                'utilizable': True, 'resumen': resumen, 'aprueba_resultados': False, 'aprueba_informe': False,
                'aviso': AVISO}

    def consultar(self, caso, tipo, version, *, expediente_sha256):
        def operacion():
            folder = self._caso(caso, expediente_sha256)
            item = self._cargar(folder, tipo, version)
            self._sin_cambios(item)
            self._caso(caso, expediente_sha256)
            return self._proyeccion(tipo, item, caso, expediente_sha256)
        return self._publico(operacion, 'Contexto inválido, ausente o alterado; vuelve a consultar el expediente.')

    def listar(self, caso, *, expediente_sha256):
        def operacion():
            folder = self._caso(caso, expediente_sha256)
            out = {'caso': caso, 'expediente_sha256': expediente_sha256}
            for nombre, leer in [*((t, (lambda v, t=t: self.consultar(caso, t, v, expediente_sha256=expediente_sha256)))
                                   for t in TIPOS), ('derivados', lambda v: self.consultar_derivado(
                                       caso, v, expediente_sha256=expediente_sha256))]:
                base = self._grupo(folder, nombre)
                rows = []
                for path in sorted(base.iterdir()) if base.is_dir() else []:
                    if re.fullmatch('[0-9a-f]{32}', path.name) is None:
                        continue  # temporales .ctx-* no son versiones
                    try:
                        value = leer(path.name)
                        summary = ({'tipo': value['tipo'], 'fuentes': value['fuentes']} if nombre == 'derivados'
                                   else {'huella': value['huella'], 'datos_sinteticos': value['datos_sinteticos']})
                        rows.append({'id': path.name, 'vigente': True, **summary})
                    except ERRORES:
                        rows.append({'id': path.name, 'vigente': False, 'problemas': ['version_no_vigente']})
                out[nombre] = rows
            self._caso(caso, expediente_sha256)
            return out
        return self._publico(operacion, 'No se pudo listar el contexto del expediente.')

    # -- consultas derivadas -------------------------------------------------------
    def _resultado(self, caso, fingerprint, version):
        checked = self.app.resultados.consultar_resultado(caso, _uuid(version), expediente_sha256=fingerprint)
        return checked['datos'], checked['huella']

    @staticmethod
    def _mezcla(contexto_sintetico, datos):
        # Igual que informe.py: contexto sintético no se aplica a resultados reales.
        # Un contexto real sobre resultados sintéticos queda permitido y marcado.
        if datos is not None and contexto_sintetico and not datos['datos_sinteticos']:
            raise ErrorContexto('No se aplica contexto sintético a resultados reales.')

    def _calcular(self, folder, caso, fingerprint, tipo, solicitud):
        """Cálculo determinista desde fuentes revalidadas; usado al crear y al consultar."""
        datos = huella = None
        if solicitud.get('resultado') is not None:
            datos, huella = self._resultado(caso, fingerprint, solicitud['resultado'])
        if tipo == 'recuperacion':
            item = self._cargar(folder, 'corpus', solicitud['corpus'])
            self._mezcla(item['meta']['datos_sinteticos'], datos)
            salida = fuentes.recuperar(item['target']/'corpus.json', solicitud['consulta'], solicitud['limite'])
            fuentes_usadas = {'corpus': {'id': solicitud['corpus'], 'huella': item['meta']['huella']}}
        elif tipo == 'sitio':
            item = self._cargar(folder, 'sitio', solicitud['sitio'])
            self._mezcla(item['meta']['datos_sinteticos'], datos)
            salida = sitio.consultar_sitio(item['target']/'capa.json', solicitud['longitud'], solicitud['latitud'])
            fuentes_usadas = {'sitio': {'id': solicitud['sitio'], 'huella': item['meta']['huella']}}
        else:
            item = self._cargar(folder, 'reglas', solicitud['reglas'])
            if item['meta']['huella'] != solicitud['huella_reglas'] or huella != solicitud['huella_resultados']:
                raise ErrorContexto('Las huellas declaradas no corresponden a las reglas o al resultado vigentes.')
            salida = evaluacion.evaluar_resultados(datos, item['data'], huella_resultados_esperada=huella,
                                                   huella_reglas_esperada=solicitud['huella_reglas'])
            fuentes_usadas = {'reglas': {'id': solicitud['reglas'], 'huella': item['meta']['huella']}}
        self._sin_cambios(item)
        if solicitud.get('resultado') is not None and self._resultado(caso, fingerprint, solicitud['resultado'])[1] != huella:
            raise ErrorContexto('El resultado cambió durante la consulta.')
        fuentes_usadas['resultado'] = {'id': solicitud['resultado'], 'huella': huella} if huella else None
        return salida, fuentes_usadas

    def _derivar(self, tipo, caso, fingerprint, solicitud):
        folder = self._caso(caso, fingerprint)
        salida, fuentes_usadas = self._calcular(folder, caso, fingerprint, tipo, solicitud)
        raw = _canonico(salida)
        base = self._grupo(folder, 'derivados', crear=True)
        ident = uuid4().hex
        meta = {'contrato': CONTRATO_DERIVADO, 'version': VERSION, 'id': ident, 'caso': caso, 'tipo': tipo,
                'solicitud': solicitud, 'fuentes': fuentes_usadas, 'sha256_salida': _sha(raw),
                'creado_utc': datetime.now(timezone.utc).isoformat()}
        with tempfile.TemporaryDirectory(prefix='.ctx-', dir=base) as temporal:
            etapa = Path(temporal).resolve()
            if etapa.parent != base:
                raise ErrorContexto('Temporal fuera del caso.')
            paquete = etapa/'paquete'
            paquete.mkdir()
            (paquete/'salida.json').write_bytes(raw)
            (paquete/'version.json').write_bytes(_canonico(meta))
            if self._calcular(folder, caso, fingerprint, tipo, solicitud)[0] != salida:
                raise ErrorContexto('Las fuentes cambiaron durante la consulta.')
            self._caso(caso, fingerprint)
            destino = base/ident
            if os.path.lexists(destino):
                raise ErrorContexto('Destino existente; no se sobrescribe.')
            paquete.rename(destino)
        return self.consultar_derivado(caso, ident, expediente_sha256=fingerprint)

    @staticmethod
    def _resultado_opcional(value):
        return None if value is None else _uuid(value)

    def recuperar(self, body):
        def operacion():
            _campos(body, {'caso', 'expediente_sha256', 'corpus', 'consulta', 'limite', 'resultado'})
            consulta = body['consulta']
            if not isinstance(consulta, str) or not consulta.strip() or len(consulta) > MAX_CONSULTA:
                raise ErrorContexto('Consulta explícita de 1 a 500 caracteres.')
            if type(body['limite']) is not int or not 1 <= body['limite'] <= 20:
                raise ErrorContexto('Límite entre 1 y 20.')
            solicitud = {'corpus': _uuid(body['corpus']), 'consulta': consulta, 'limite': body['limite'],
                         'resultado': self._resultado_opcional(body['resultado'])}
            return self._derivar('recuperacion', body['caso'], body['expediente_sha256'], solicitud)
        return self._publico(operacion, 'No se pudo recuperar del corpus vigente.')

    def consultar_sitio(self, body):
        def operacion():
            _campos(body, {'caso', 'expediente_sha256', 'sitio', 'longitud', 'latitud', 'resultado'})
            for key in ('longitud', 'latitud'):
                value = body[key]
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise ErrorContexto('Declara longitud y latitud numéricas finitas (EPSG:4326).')
            solicitud = {'sitio': _uuid(body['sitio']), 'longitud': body['longitud'], 'latitud': body['latitud'],
                         'resultado': self._resultado_opcional(body['resultado'])}
            return self._derivar('sitio', body['caso'], body['expediente_sha256'], solicitud)
        return self._publico(operacion, 'No se pudo consultar la capa de sitio vigente con esa ubicación.')

    def evaluar(self, body):
        def operacion():
            _campos(body, {'caso', 'expediente_sha256', 'resultado', 'reglas', 'huella_resultados', 'huella_reglas'})
            solicitud = {'resultado': _uuid(body['resultado']), 'reglas': _uuid(body['reglas']),
                         'huella_resultados': _hex64(body['huella_resultados']), 'huella_reglas': _hex64(body['huella_reglas'])}
            return self._derivar('evaluacion', body['caso'], body['expediente_sha256'], solicitud)
        return self._publico(operacion, 'No se pudo evaluar: resultado, reglas o huellas sin vigencia.')

    def consultar_derivado(self, caso, version, *, expediente_sha256):
        def operacion():
            folder = self._caso(caso, expediente_sha256)
            target = self._grupo(folder, 'derivados')/_uuid(version)
            _sin_enlace(target)
            if not target.is_dir() or sorted(p.name for p in target.iterdir()) != ['salida.json', 'version.json']:
                raise ErrorContexto('Derivado ausente o con contenido inválido.')
            meta_raw = _sin_enlace(target/'version.json').read_bytes()
            raw = _sin_enlace(target/'salida.json').read_bytes()
            meta = json_desde_bytes(meta_raw, 'version.json')
            campos = {'contrato', 'version', 'id', 'caso', 'tipo', 'solicitud', 'fuentes', 'sha256_salida', 'creado_utc'}
            if (not isinstance(meta, dict) or set(meta) != campos or meta['contrato'] != CONTRATO_DERIVADO
                    or meta['version'] != VERSION or meta['id'] != version or meta['caso'] != caso
                    or meta['tipo'] not in DERIVADOS or not isinstance(meta['solicitud'], dict)
                    or _sha(raw) != meta['sha256_salida']):
                raise ErrorContexto('Derivado alterado.')
            salida = json_desde_bytes(raw, 'salida.json')
            # Reproducir desde las fuentes actuales: cualquier alteración invalida el derivado.
            actual, fuentes_usadas = self._calcular(folder, caso, expediente_sha256, meta['tipo'], meta['solicitud'])
            if actual != salida or fuentes_usadas != meta['fuentes']:
                raise ErrorContexto('Las fuentes del derivado cambiaron; no se reproduce.')
            if (target/'version.json').read_bytes() != meta_raw or (target/'salida.json').read_bytes() != raw:
                raise ErrorContexto('El derivado cambió durante la consulta.')
            self._caso(caso, expediente_sha256)
            return {'id': version, 'caso': caso, 'expediente_sha256': expediente_sha256, 'tipo': meta['tipo'],
                    'solicitud': meta['solicitud'], 'fuentes': meta['fuentes'], 'sha256_salida': meta['sha256_salida'],
                    'creado_utc': meta['creado_utc'], 'salida': salida, 'vigente': True, 'reproducido': True,
                    'datos_sinteticos': salida.get('datos_sinteticos'), 'aprueba_resultados': False,
                    'aprueba_informe': False, 'conformidad_normativa': 'no_evaluada', 'aviso': AVISO}
        return self._publico(operacion, 'Derivado inválido o sin vigencia; vuelve a generarlo.')
