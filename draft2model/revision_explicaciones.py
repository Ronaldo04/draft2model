"""Explicaciones sustentadas: composición determinística, proveedor configurable y contingencia.

La tabla de cifras se compone siempre desde contratos vigentes, con independencia del
LLM. Las declaraciones del LLM solo se aceptan si cada cifra, referencia y cita
coincide exactamente con los datos verificados; aun así quedan como propuesta
pendiente de revisión semántica humana. No aprueba resultados, informe ni normativa.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
from uuid import uuid4

from . import fuentes
from . import proveedor_openai as cliente
from .adaptador_etabs import BloqueoExclusivo, ErrorBloqueo
from .gestion_extraccion import json_desde_bytes

VERSION = '0.1.0'
CONTRATO_SALIDA = 'draft2model.explicacion_sustentada'
CONTRATO_LLM = 'draft2model.explicacion_llm'
CAMPOS_PREPARAR = {'caso', 'expediente_sha256', 'resultado', 'huella_resultados', 'derivados', 'modelo', 'opciones',
                   'clave_solicitud'}
CAMPOS_EJECUTAR = {'caso', 'trabajo', 'huella_preparacion', 'expediente_sha256', 'confirmacion_explicita'}
CAMPOS_RECUPERAR = {'caso', 'trabajo', 'huella_preparacion', 'confirmacion_explicita', 'resolucion'}
TIPOS_DERIVADO = ('recuperacion', 'evaluacion', 'sitio')
BLOQUEANTES = ('en_ejecucion', 'incierto')
MAX_DECLARACIONES = 30
MAX_TEXTO = 1200
# Heurística acotada: el software no decide conformidad ni certifica.
PROHIBIDO = re.compile(r'certific|cumple (con )?la norma|conforme a (la )?norma|aprobad[oa] por|es seguro|garantiza', re.I)
NUMERO = re.compile(r'(?<![\w.])[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?')
LIMITES_SOFTWARE = [
    'Se verifica que cifras, unidades e identificadores coincidan exactamente con el resultado y la evaluación vigentes.',
    'Se verifica que cada cita exista literalmente en un fragmento recuperado de un corpus con aprobación declarada vigente.',
    'No se verifica el sentido técnico del texto libre: queda como propuesta pendiente de revisión humana.',
    'No se evalúa conformidad normativa, seguridad estructural ni se emiten recomendaciones de ingeniería.',
    'La identidad de revisores declarada en corpus y reglas no está autenticada.']
ERRORES = (ValueError, OSError, RuntimeError, KeyError, TypeError, sqlite3.Error, UnicodeError, OverflowError)


class ErrorExplicaciones(ValueError):
    """Código público, sin rutas ni credenciales."""
    def __init__(self, codigo):
        self.codigo = codigo
        super().__init__(codigo)


def _bytes(data):
    return (json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))+'\n').encode('utf-8')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _uuid(value):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{32}', value) is None:
        raise ErrorExplicaciones('identificador_invalido')
    return value


def _hex64(value):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ErrorExplicaciones('huella_invalida')
    return value


def _directa(path):
    path = Path(path)
    if path.resolve() != path or path.is_symlink():
        raise ErrorExplicaciones('ruta_no_permitida')
    return path


def _nuevo(path, data):
    with Path(path).open('xb') as stream:
        stream.write(data)


def _proveedor(record):
    return cliente.validar_proveedor(record.get('proveedor', 'openai'))


def _clave(proveedor='openai'):
    return cliente.clave_api(proveedor)


def _mismo_numero(a, b):
    return type(a) in (int, float) and type(b) in (int, float) and float(a) == float(b)


def esquema_llm(refs, fragmentos):
    """Structured Outputs: referencias y fragmentos limitados a los verificados."""
    cita = {'type': 'object', 'additionalProperties': False,
            'properties': {'fragmento_id': {'type': 'string', 'enum': fragmentos or ['__sin_fragmentos__']},
                           'texto': {'type': 'string'}}, 'required': ['fragmento_id', 'texto']}
    cifra = {'type': 'object', 'additionalProperties': False,
             'properties': {'indicador': {'type': 'string', 'enum': refs or ['__sin_indicadores__']},
                            'valor': {'type': 'number'}, 'unidad': {'type': 'string'}},
             'required': ['indicador', 'valor', 'unidad']}
    declaracion = {'type': 'object', 'additionalProperties': False,
                   'properties': {'id': {'type': 'string'}, 'texto': {'type': 'string'},
                                  'indicadores': {'type': 'array', 'items': {'type': 'string', 'enum': refs or ['__sin_indicadores__']}},
                                  'cifras': {'type': 'array', 'items': cifra}, 'citas': {'type': 'array', 'items': cita}},
                   'required': ['id', 'texto', 'indicadores', 'cifras', 'citas']}
    abstencion = {'type': 'object', 'additionalProperties': False,
                  'properties': {'tema': {'type': 'string'}, 'motivo': {'type': 'string'}}, 'required': ['tema', 'motivo']}
    props = {'contrato': {'type': 'string', 'enum': [CONTRATO_LLM]}, 'version': {'type': 'string', 'enum': [VERSION]},
             'declaraciones': {'type': 'array', 'items': declaracion}, 'abstenciones': {'type': 'array', 'items': abstencion}}
    return {'type': 'object', 'properties': props, 'required': list(props), 'additionalProperties': False}


class ServicioExplicaciones:
    """`transporte(payload, timeout)` solo desde pruebas Python; nunca recibe la credencial."""

    def __init__(self, app, transporte=None):
        self.app = app
        if transporte is not None and not callable(transporte):
            raise TypeError('transporte inválido')
        self._transporte = transporte
        raiz = _directa(Path(app.raiz))
        self.base = raiz/'.explicaciones_web'
        if not self.base.exists():
            self.base.mkdir()
        _directa(self.base)
        (self.base/'trabajos').mkdir(exist_ok=True)
        _directa(self.base/'trabajos')
        self.db = self.base/'trabajos.sqlite3'
        self.control = self.base/'llm.lock'  # control propio del LLM; no es ETABS ni visión
        self._threads = {}
        with self._conexion() as db:
            db.execute('CREATE TABLE IF NOT EXISTS trabajos (id TEXT PRIMARY KEY, caso TEXT NOT NULL, clave TEXT NOT NULL, '
                       'payload TEXT NOT NULL, estado TEXT NOT NULL, registro TEXT NOT NULL, UNIQUE(caso,clave))')
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS llm_unico ON trabajos((1)) WHERE estado='en_ejecucion'")

    # -- persistencia ------------------------------------------------------------
    @contextmanager
    def _conexion(self):
        """Transacción con cierre garantizado: Windows no retiene el archivo SQLite."""
        if self.db.exists():
            _directa(self.db)
        db = sqlite3.connect(self.db, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def _carpeta(self, ident):
        folder = self.base/'trabajos'/_uuid(ident)
        if not folder.exists():
            folder.mkdir()
        return _directa(folder)

    def _leer(self, ident, nombre):
        return _directa(self._carpeta(ident)/nombre).read_bytes()

    def _trabajo(self, caso, ident):
        _uuid(ident)
        with self._conexion() as db:
            row = db.execute('SELECT * FROM trabajos WHERE id=? AND caso=?', (ident, caso)).fetchone()
        if row is None:
            raise ErrorExplicaciones('trabajo_ausente')
        return json.loads(row['registro']), row['estado']

    def _estado(self, record, state, **extra):
        record = {**record, **extra}
        with self._conexion() as db:
            db.execute('UPDATE trabajos SET estado=?,registro=? WHERE id=?', (state, _bytes(record).decode(), record['id']))
        _nuevo(self._carpeta(record['id'])/('evento_'+uuid4().hex+'.json'), _bytes({'estado': state, 'registro': record}))
        return record

    # -- fuentes verificadas -------------------------------------------------------
    def _contexto(self):
        servicio = getattr(self.app, 'contexto', None)
        if servicio is None:
            from .revision_contexto import ServicioContexto
            servicio = ServicioContexto(self.app)
        return servicio

    def _fuentes(self, caso, fingerprint, resultado, huella, derivados):
        """Lee resultado y derivados vigentes por API pública; devuelve contexto y huellas exactas."""
        checked = self.app.resultados.consultar_resultado(caso, resultado, expediente_sha256=fingerprint)
        if checked['huella'] != huella:
            raise ErrorExplicaciones('resultado_cambio')
        ctx = self._contexto()
        vistos, extra = {}, {}
        for tipo in TIPOS_DERIVADO:
            ident = derivados[tipo]
            if ident is None:
                continue
            item = ctx.consultar_derivado(caso, ident, expediente_sha256=fingerprint)
            if item['tipo'] != tipo or item.get('vigente') is not True:
                raise ErrorExplicaciones('derivado_no_corresponde')
            vinculado = item['fuentes'].get('resultado')
            if tipo == 'evaluacion' and vinculado != {'id': resultado, 'huella': huella}:
                raise ErrorExplicaciones('evaluacion_de_otro_resultado')
            if vinculado is not None and vinculado != {'id': resultado, 'huella': huella}:
                raise ErrorExplicaciones('derivado_de_otro_resultado')
            vistos[tipo] = {'id': ident, 'sha256_salida': item['sha256_salida'], 'fuentes': item['fuentes']}
            extra[tipo] = item
        corpus = None
        if 'recuperacion' in extra:
            corpus_id = extra['recuperacion']['fuentes']['corpus']['id']
            ctx.consultar(caso, 'corpus', _uuid(corpus_id), expediente_sha256=fingerprint)
            folder, _, _ = self.app.expediente(caso)
            corpus = _directa(Path(folder)/'contexto'/'corpus'/corpus_id/'corpus.json')
        return checked['datos'], extra, vistos, corpus

    @staticmethod
    def _deterministico(caso, resultado, huella, datos, extra):
        """Tabla y citas independientes del LLM, solo desde datos verificados."""
        indicadores = []
        for row in datos['resultados']:
            indicadores.append({'ref': 'R:'+row['id'], 'resultado_fila': row['id'], 'variable': row['variable'],
                                'caso': row['caso'], 'direccion': row['direccion'], 'ubicacion': row['ubicacion'],
                                'valor': row['valor'], 'unidad': row['unidad'],
                                'motivo_omision': row.get('motivo_omision')})
        evaluaciones = []
        if 'evaluacion' in extra:
            for ev in extra['evaluacion']['salida']['evaluaciones']:
                evaluaciones.append({'ref': 'E:'+':'.join((ev['regla_id'], ev['caso'], ev['direccion'], ev['ubicacion'])),
                                     **{k: ev[k] for k in ('regla_id', 'variable', 'unidad', 'caso', 'direccion', 'ubicacion',
                                                           'estado', 'valor_entrada', 'valor_evaluado', 'limite',
                                                           'comparador', 'relacion_limite', 'satisface_regla_configurada',
                                                           'fuente')},
                                     # 290: la unidad emparejada con valor_evaluado/límite es la de salida; la de entrada se conserva.
                                     'unidad': ev.get('unidad_resultado', ev['unidad']), 'unidad_entrada': ev['unidad']})
        fragmentos, abstencion = [], None
        if 'recuperacion' in extra:
            salida = extra['recuperacion']['salida']
            abstencion = salida['abstencion']
            fragmentos = [{'ref': 'F:'+f['id'], **{k: f[k] for k in ('id', 'documento', 'pagina', 'apartado', 'texto',
                                                                     'titulo', 'edicion', 'sha256_documento')}}
                          for f in salida['fragmentos']]
        sitio = None
        if 'sitio' in extra:
            s = extra['sitio']['salida']
            sitio = {k: s[k] for k in ('estado', 'zonas', 'fuente', 'fecha_fuente', 'precision_m', 'huella_capa',
                                       'datos_sinteticos', 'parametros_geotecnicos', 'capacidad_portante')}
        tabla = []
        for item in indicadores:
            valor = 'sin dato ('+str(item['motivo_omision'])+')' if item['valor'] is None else repr(item['valor'])+' '+item['unidad']
            tabla.append(item['ref']+' · '+item['variable']+' · '+item['caso']+' · '+item['direccion']+'/'+item['ubicacion']+' · '+valor)
        for ev in evaluaciones:
            if ev['estado'] == 'evaluado':
                tabla.append(ev['ref']+' · '+repr(ev['valor_evaluado'])+' '+ev['unidad']+' '+ev['relacion_limite']+' del límite configurado '
                             +repr(ev['limite'])+' ('+ev['comparador']+'); satisface la regla configurada: '
                             +('sí' if ev['satisface_regla_configurada'] else 'no'))
            else:
                tabla.append(ev['ref']+' · '+ev['estado'])
        abstenciones = []
        if 'recuperacion' not in extra:
            abstenciones.append({'tema': 'fuentes', 'motivo': 'Sin recuperación de corpus seleccionada; no se citan fuentes.'})
        elif abstencion:
            abstenciones.append({'tema': 'fuentes', 'motivo': 'La consulta al corpus no tuvo coincidencias; no hay citas.'})
        if 'evaluacion' not in extra:
            abstenciones.append({'tema': 'reglas', 'motivo': 'Sin evaluación de reglas registradas; no se comparan límites.'})
        if sitio is not None and sitio['estado'] != 'dentro':
            # Semántica conservadora de sitio: 'limite' es franja incierta; no se afirma pertenencia ni se infiere geotecnia.
            abstenciones.append({'tema': 'sitio', 'motivo': 'Estado de sitio '+sitio['estado']+': no se afirma pertenencia a una zona ni parámetros de suelo.'})
        if 'sitio' not in extra:
            abstenciones.append({'tema': 'sitio', 'motivo': 'Sin consulta de sitio; no se describe el emplazamiento.'})
        return {'caso': caso, 'resultado': resultado, 'huella_resultados': huella,
                'datos_sinteticos': datos['datos_sinteticos'], 'motor': datos['motor'],
                'indicadores': indicadores, 'evaluaciones': evaluaciones, 'fragmentos': fragmentos, 'sitio': sitio,
                'tabla': tabla, 'abstenciones': abstenciones, 'limites_verificables': LIMITES_SOFTWARE}

    @staticmethod
    def _peticion(det, modelo, opts, proveedor='openai'):
        refs = [i['ref'] for i in det['indicadores']] + [e['ref'] for e in det['evaluaciones']]
        prompt = ('Explica en español los datos verificados que se adjuntan. Usa solo esos datos. Cada declaración debe '
                  'citar indicadores por su ref y, si cita fuentes, copiar literalmente el texto del fragmento. Toda cifra '
                  'del texto debe figurar en cifras con el valor y la unidad exactos del indicador. No infieras normativa, '
                  'umbrales, recomendaciones ni conformidad; si falta información, decláralo en abstenciones.')
        contexto = {k: det[k] for k in ('indicadores', 'evaluaciones', 'fragmentos', 'sitio', 'abstenciones', 'datos_sinteticos')}
        payload = {'model': modelo, 'store': False, 'max_output_tokens': opts['max_tokens'],
                'input': [{'role': 'developer', 'content': [{'type': 'input_text', 'text': prompt}]},
                          {'role': 'user', 'content': [{'type': 'input_text', 'text': json.dumps(contexto, ensure_ascii=False, sort_keys=True)}]}],
                'text': {'format': {'type': 'json_schema', 'name': 'draft2model_explicacion', 'strict': True,
                                    'schema': esquema_llm(refs, [f['id'] for f in det['fragmentos']])}}}
        return cliente.cliente_api(proveedor).convertir_peticion(payload) if cliente.validar_proveedor(proveedor) != 'openai' else payload

    def _revalidar(self, record):
        """Fuentes, derivados y composición idénticos a la preparación; sin red ni clave."""
        datos, extra, vistos, corpus = self._fuentes(record['caso'], record['expediente_sha256'], record['resultado'],
                                                     record['huella_resultados'], record['derivados'])
        if vistos != record['fuentes']:
            raise ErrorExplicaciones('fuentes_cambio')
        det = self._deterministico(record['caso'], record['resultado'], record['huella_resultados'], datos, extra)
        if _sha(_bytes(det)) != record['sha256_deterministico'] or _sha(self._leer(record['id'], 'deterministico.json')) != record['sha256_deterministico']:
            raise ErrorExplicaciones('composicion_cambio')
        peticion = self._leer(record['id'], 'peticion.json')
        if _sha(peticion) != record['sha256_peticion'] or _bytes(self._peticion(det, record['modelo_declarado'], record['opciones'], _proveedor(record))) != peticion:
            raise ErrorExplicaciones('peticion_cambio')
        return det, json.loads(peticion), corpus

    # -- validación de la salida del LLM ------------------------------------------------
    @staticmethod
    def validar_llm(parsed, det, corpus, huella_corpus):
        """Errores como códigos; vacío significa sustentada. No juzga el sentido técnico."""
        errors = []
        if (not isinstance(parsed, dict) or set(parsed) != {'contrato', 'version', 'declaraciones', 'abstenciones'}
                or parsed['contrato'] != CONTRATO_LLM or parsed['version'] != VERSION
                or not isinstance(parsed['declaraciones'], list) or not isinstance(parsed['abstenciones'], list)
                or len(parsed['declaraciones']) > MAX_DECLARACIONES):
            return ['contrato_invalido']
        valores = {i['ref']: (i['valor'], i['unidad']) for i in det['indicadores']}
        valores |= {e['ref']: (e['valor_evaluado'], e['unidad']) for e in det['evaluaciones']}
        fragmentos = {f['id'] for f in det['fragmentos']}
        ids = set()
        for d in parsed['declaraciones']:
            if (not isinstance(d, dict) or set(d) != {'id', 'texto', 'indicadores', 'cifras', 'citas'}
                    or not isinstance(d['id'], str) or not d['id'] or d['id'] in ids
                    or not isinstance(d['texto'], str) or not d['texto'].strip() or len(d['texto']) > MAX_TEXTO
                    or not all(isinstance(d[k], list) for k in ('indicadores', 'cifras', 'citas'))):
                errors.append('declaracion_invalida'); continue
            ids.add(d['id'])
            if not d['indicadores'] and not d['citas']:
                errors.append('declaracion_sin_sustento:'+d['id'])
            if any(not isinstance(r,str) or r not in valores for r in d['indicadores']):
                errors.append('indicador_inexistente:'+d['id'])
            declared = []
            for c in d['cifras']:
                ok = (isinstance(c, dict) and set(c) == {'indicador', 'valor', 'unidad'}
                      and isinstance(c['indicador'],str) and c['indicador'] in valores
                      and c['indicador'] in d['indicadores'] and _mismo_numero(c['valor'], valores[c['indicador']][0])
                      and c['unidad'] == valores[c['indicador']][1])
                if not ok:
                    errors.append('cifra_no_coincide:'+d['id'])
                else:
                    declared.append(float(c['valor']))
            for token in NUMERO.findall(d['texto']):
                try:
                    number = float(token.replace(',', '.'))
                except ValueError:
                    errors.append('cifra_ilegible:'+d['id']); continue
                if number not in declared:
                    errors.append('cifra_en_texto_sin_respaldo:'+d['id'])
            if d['citas']:
                if corpus is None or any(not isinstance(c, dict) or not isinstance(c.get('fragmento_id'),str)
                                        or c['fragmento_id'] not in fragmentos for c in d['citas']):
                    errors.append('cita_fuera_de_recuperacion:'+d['id'])
                else:
                    try:
                        fuentes.verificar_citas(corpus, d['citas'], huella_corpus)
                    except ValueError:
                        errors.append('cita_no_verificada:'+d['id'])
            if PROHIBIDO.search(d['texto']):
                errors.append('afirmacion_no_permitida:'+d['id'])
        for a in parsed['abstenciones']:
            if not isinstance(a, dict) or set(a) != {'tema', 'motivo'} or not all(isinstance(a[k], str) and a[k].strip() for k in a):
                errors.append('abstencion_invalida')
        return sorted(set(errors))

    # -- proyección ---------------------------------------------------------------------
    def _salida(self, record):
        if not record.get('sha256_salida'):
            return None
        raw = self._leer(record['id'], 'salida.json')
        if _sha(raw) != record['sha256_salida']:
            raise ErrorExplicaciones('salida_alterada')
        return json.loads(raw)

    def _publico(self, record, state, *, comprobar=True):
        vigente, salida = True, None
        try:
            salida = self._salida(record)
            if comprobar:
                self._revalidar(record)
        except ERRORES:
            vigente = False
        out = {k: record[k] for k in ('id', 'caso', 'expediente_sha256', 'resultado', 'huella_resultados', 'derivados',
                                      'modelo_declarado', 'opciones', 'huella_preparacion', 'sha256_deterministico',
                                      'sha256_peticion')}
        return out | {'proveedor': _proveedor(record), 'endpoint_declarado': record.get('endpoint_declarado', cliente.ENDPOINT), 'estado': state, 'vigente': vigente,
                      'problemas': [] if vigente else ['fuentes_o_explicacion_no_vigentes'],
                      'requiere_recuperacion': state == 'incierto', 'modo_transporte': record.get('modo_transporte'),
                      'salida': salida if vigente else None, 'aprueba_resultados': False, 'aprueba_informe': False,
                      'conformidad_normativa': 'no_evaluada'}

    # -- operaciones ---------------------------------------------------------------------
    def preparar(self, body):
        try:
            with self.app.lock, self._conexion() as db:
                if not isinstance(body, dict) or set(body) not in (CAMPOS_PREPARAR, CAMPOS_PREPARAR | {'proveedor'}):
                    raise ErrorExplicaciones('campos_invalidos')
                cliente.validar_proveedor(body.get('proveedor', 'openai'))
                _uuid(body['clave_solicitud']); _uuid(body['resultado'])
                _hex64(body['expediente_sha256']); _hex64(body['huella_resultados'])
                derivados = body['derivados']
                if not isinstance(derivados, dict) or set(derivados) != set(TIPOS_DERIVADO):
                    raise ErrorExplicaciones('derivados_invalidos')
                for value in derivados.values():
                    if value is not None:
                        _uuid(value)
                opts = body['opciones']
                if (not isinstance(opts, dict) or set(opts) != {'max_tokens', 'timeout_s'}
                        or type(opts['max_tokens']) is not int or not 256 <= opts['max_tokens'] <= 16384
                        or type(opts['timeout_s']) is not int or not 1 <= opts['timeout_s'] <= 180):
                    raise ErrorExplicaciones('opciones_invalidas')
                if not isinstance(body['modelo'], str) or re.fullmatch(r'[A-Za-z0-9_.:/-]{1,128}', body['modelo']) is None:
                    raise ErrorExplicaciones('modelo_declarado_invalido')
                folder, _, current = self.app.expediente(body['caso'])
                if current != body['expediente_sha256']:
                    raise ErrorExplicaciones('expediente_cambio')
                payload = _sha(_bytes(body))
                db.execute('BEGIN IMMEDIATE')
                existing = db.execute('SELECT * FROM trabajos WHERE caso=? AND clave=?',
                                      (body['caso'], body['clave_solicitud'])).fetchone()
                if existing:
                    if existing['payload'] != payload:
                        raise ErrorExplicaciones('clave_reutilizada_con_otros_datos')
                    return self._publico(json.loads(existing['registro']), existing['estado'])
                datos, extra, vistos, _ = self._fuentes(body['caso'], current, body['resultado'],
                                                        body['huella_resultados'], derivados)
                det = self._deterministico(body['caso'], body['resultado'], body['huella_resultados'], datos, extra)
                peticion = _bytes(self._peticion(det, body['modelo'], opts, body.get('proveedor', 'openai')))
                ident = uuid4().hex
                _nuevo(self._carpeta(ident)/'deterministico.json', _bytes(det))
                _nuevo(self._carpeta(ident)/'peticion.json', peticion)
                core = {'id': ident, 'caso': body['caso'], 'expediente_sha256': current, 'resultado': body['resultado'],
                        'huella_resultados': body['huella_resultados'], 'derivados': dict(derivados), 'fuentes': vistos,
                        'modelo_declarado': body['modelo'], 'opciones': dict(opts), 'proveedor': body.get('proveedor', 'openai'),
                        'endpoint_declarado': cliente.proveedores.obtener(body.get('proveedor', 'openai')).endpoint(body['modelo']),
                        'sha256_deterministico': _sha(_bytes(det)), 'sha256_peticion': _sha(peticion)}
                record = {**core, 'huella_preparacion': _sha(_bytes(core)), 'sha256_salida': None}
                self._revalidar(record)
                _nuevo(self._carpeta(ident)/'preparacion.json', _bytes(record))
                db.execute('INSERT INTO trabajos VALUES (?,?,?,?,?,?)',
                           (ident, body['caso'], body['clave_solicitud'], payload, 'preparado', _bytes(record).decode()))
                return self._publico(record, 'preparado', comprobar=False)
        except ErrorExplicaciones:
            raise
        except ERRORES:
            raise ErrorExplicaciones('preparacion_rechazada') from None

    def _huerfano(self, record, state):
        if state != 'en_ejecucion':
            return record, state
        try:
            control = BloqueoExclusivo(self.control).adquirir()
        except ErrorBloqueo:
            return record, state
        try:
            record, state = self._trabajo(record['caso'], record['id'])
            if state != 'en_ejecucion':
                return record, state
            return self._estado(record, 'incierto', causa='interrupcion_no_confirmada'), 'incierto'
        finally:
            control.liberar()

    def consultar(self, caso, trabajo):
        try:
            with self.app.lock:
                return self._publico(*self._huerfano(*self._trabajo(caso, trabajo)))
        except ErrorExplicaciones:
            raise
        except ERRORES:
            raise ErrorExplicaciones('consulta_rechazada') from None

    def listar(self, caso):
        try:
            with self.app.lock, self._conexion() as db:
                ids = [r['id'] for r in db.execute('SELECT id FROM trabajos WHERE caso=? ORDER BY rowid', (caso,))]
                return {'caso': caso, 'trabajos': [self.consultar(caso, ident) for ident in ids]}
        except ErrorExplicaciones:
            raise
        except ERRORES:
            raise ErrorExplicaciones('consulta_rechazada') from None

    def _publicar_salida(self, record, state, det, *, modo, causa=None, declaraciones=None, observado=None, errores=None):
        salida = {'contrato': CONTRATO_SALIDA, 'version': VERSION, 'modo': modo, 'causa': causa,
                  'generacion_llm_real': modo == 'llm_verificado' and record.get('modo_transporte') == 'real',
                  'modo_transporte': record.get('modo_transporte'), 'deterministico': det,
                  'declaraciones_llm': declaraciones, 'errores_validacion': errores or [],
                  'modelo_declarado': record['modelo_declarado'], 'observado': observado,
                  'estado_revision': 'propuesta_pendiente_revision_humana', 'aprueba_resultados': False,
                  'aprueba_informe': False, 'conformidad_normativa': 'no_evaluada'}
        raw = _bytes(salida)
        _nuevo(self._carpeta(record['id'])/'salida.json', raw)
        return self._estado(record, state, sha256_salida=_sha(raw), causa=causa)

    def ejecutar(self, body):
        control = None
        try:
            with self.app.lock:
                if not isinstance(body, dict) or set(body) != CAMPOS_EJECUTAR:
                    raise ErrorExplicaciones('campos_invalidos')
                if body['confirmacion_explicita'] is not True:
                    raise ErrorExplicaciones('confirmacion_requerida')
                record, state = self._huerfano(*self._trabajo(body['caso'], body['trabajo']))
                if body['huella_preparacion'] != record['huella_preparacion'] or body['expediente_sha256'] != record['expediente_sha256']:
                    raise ErrorExplicaciones('preparacion_cambio')
                if state != 'preparado':
                    return self._publico(record, state)  # idempotente: nunca un segundo envío
                control = BloqueoExclusivo(self.control).adquirir()
                with self._conexion() as db:
                    for row in db.execute('SELECT registro FROM trabajos WHERE caso=? AND estado=?',
                                          (record['caso'], 'en_ejecucion')).fetchall():
                        self._estado(json.loads(row['registro']), 'incierto', causa='interrupcion_no_confirmada')
                    db.execute('BEGIN IMMEDIATE')
                    if db.execute('SELECT COUNT(*) FROM trabajos WHERE caso=? AND estado IN (?,?)',
                                  (record['caso'], *BLOQUEANTES)).fetchone()[0]:
                        raise ErrorExplicaciones('incertidumbre_pendiente_en_caso')
                    try:
                        det, _, _ = self._revalidar(record)
                    except ERRORES:
                        db.execute('UPDATE trabajos SET estado=? WHERE id=?', ('fallido_sin_envio', record['id']))
                        db.commit()
                        raise ErrorExplicaciones('entradas_no_vigentes') from None
                    record = {**record, 'modo_transporte': 'transporte_prueba_python' if self._transporte else 'real'}
                    if self._transporte is None:
                        db.commit()
                        record = self._publicar_salida(record, 'contingencia', det, modo='contingencia_deterministica',
                                                       causa='api_restringida_a_revision_planos')
                        return self._publico(record, 'contingencia')
                    db.execute('UPDATE trabajos SET estado=?,registro=? WHERE id=?',
                               ('en_ejecucion', _bytes(record).decode(), record['id']))
                _nuevo(self._carpeta(record['id'])/('evento_'+uuid4().hex+'.json'), _bytes({'estado': 'en_ejecucion', 'registro': record}))
                thread = threading.Thread(target=self._worker, args=(record, control), daemon=True)
                self._threads[record['id']] = thread
                thread.start()
                control = None
                return self._publico(record, 'en_ejecucion', comprobar=False)
        except ErrorExplicaciones:
            raise
        except ErrorBloqueo:
            raise ErrorExplicaciones('otro_envio_activo') from None
        except ERRORES:
            raise ErrorExplicaciones('ejecucion_rechazada') from None
        finally:
            if control is not None:
                control.liberar()

    def _worker(self, record, control):
        try:
            with self.app.lock:
                det, payload, corpus = self._revalidar(record)
            huella_corpus = (record['fuentes']['recuperacion']['fuentes']['corpus']['huella']
                             if 'recuperacion' in record['fuentes'] else None)
            # Reserva durable antes del transporte: un reinicio posterior nunca reenvía.
            _nuevo(self._carpeta(record['id'])/'intento.json', _bytes({'id': record['id'], 'estado': 'reservado_no_reintentar'}))
            try:
                if self._transporte is not None:
                    response = self._transporte(payload, record['opciones']['timeout_s'])
                else:
                    # Segunda guarda para trabajos antiguos/worker: ninguna explicación
                    # puede usar credenciales reales bajo la autorización vigente.
                    from .politica_uso_ia import exigir_autorizacion
                    exigir_autorizacion(_proveedor(record), 'explicacion_resultados')
                    key = _clave(_proveedor(record))
                    response = cliente.cliente_api(_proveedor(record))._http(payload, key, record['opciones']['timeout_s'])
                    if key and key in json.dumps(response, ensure_ascii=False):
                        raise ErrorExplicaciones('respuesta_con_credencial')
            except cliente.ErrorProveedor as error:
                definitive = getattr(error, 'http_status', None) is not None or str(error).startswith('OpenAI devolvió HTTP')
                with self.app.lock:
                    if definitive:
                        self._publicar_salida(record, 'contingencia', det, modo='contingencia_deterministica', causa='rechazo_llm')
                    else:
                        self._estado(record, 'incierto', causa='envio_no_confirmado')
                return
            except ErrorExplicaciones:
                raise
            except Exception:  # noqa: BLE001 timeout/pérdida: consumo incierto, sin reintento
                with self.app.lock:
                    self._estado(record, 'incierto', causa='envio_no_confirmado')
                return
            _nuevo(self._carpeta(record['id'])/'respuesta_api.json', _bytes(response) if isinstance(response, dict) else b'null\n')
            observado = None
            if isinstance(response, dict):
                observado = {**cliente.proveedores.metadatos(_proveedor(record), response),
                             'sha256_respuesta_api': _sha(_bytes(response))}
            with self.app.lock:
                try:
                    parsed = cliente.cliente_api(_proveedor(record)).leer_respuesta_api(response)
                except (ValueError, TypeError):
                    self._publicar_salida(record, 'contingencia', det, modo='contingencia_deterministica',
                                          causa='respuesta_llm_invalida', observado=observado)
                    return
                errors = self.validar_llm(parsed, det, corpus, huella_corpus)
                try:
                    self._revalidar(record)  # cambios durante el envío invalidan la aceptación
                except ERRORES:
                    self._estado(record, 'fallido_fuentes_cambiadas', causa='fuentes_cambio_durante_envio')
                    return
                if errors:
                    self._publicar_salida(record, 'contingencia', det, modo='contingencia_deterministica',
                                          causa='contenido_no_sustentado', observado=observado, errores=errors)
                    return
                declaraciones = [{**d, 'estado': 'propuesta_pendiente_revision_humana'} for d in parsed['declaraciones']]
                self._publicar_salida(record, 'completado_llm_verificado', det, modo='llm_verificado',
                                      declaraciones={'declaraciones': declaraciones, 'abstenciones': parsed['abstenciones']},
                                      observado=observado)
        except Exception as error:  # noqa: BLE001
            try:
                sent = (self._carpeta(record['id'])/'intento.json').exists()
                with self.app.lock:
                    self._estado(record, 'incierto' if sent else 'fallido_sin_envio',
                                 causa='worker_'+(error.codigo if isinstance(error, ErrorExplicaciones) else type(error).__name__))
            except Exception:  # noqa: BLE001
                pass  # queda en_ejecucion con control libre: se reconocerá como huérfano
        finally:
            control.liberar()

    def recuperar(self, body):
        """Cierre explícito de un incierto sin reintento; deja salida determinística de contingencia."""
        try:
            with self.app.lock:
                if not isinstance(body, dict) or set(body) != CAMPOS_RECUPERAR:
                    raise ErrorExplicaciones('campos_invalidos')
                if body['confirmacion_explicita'] is not True or body['resolucion'] != 'cerrar_sin_reintento':
                    raise ErrorExplicaciones('confirmacion_requerida')
                record, state = self._huerfano(*self._trabajo(body['caso'], body['trabajo']))
                if body['huella_preparacion'] != record['huella_preparacion']:
                    raise ErrorExplicaciones('preparacion_cambio')
                if state != 'incierto':
                    raise ErrorExplicaciones('trabajo_no_incierto')
                control = BloqueoExclusivo(self.control).adquirir()
                try:
                    try:
                        det, _, _ = self._revalidar(record)
                    except ERRORES:
                        record = self._estado(record, 'incierto_resuelto', causa='envio_incierto_cerrado_fuentes_no_vigentes')
                        return self._publico(record, 'incierto_resuelto')
                    record = self._publicar_salida(record, 'incierto_resuelto', det, modo='contingencia_deterministica',
                                                   causa='envio_incierto_cerrado')
                    return self._publico(record, 'incierto_resuelto')
                finally:
                    control.liberar()
        except ErrorExplicaciones:
            raise
        except ErrorBloqueo:
            raise ErrorExplicaciones('otro_envio_activo') from None
        except ERRORES:
            raise ErrorExplicaciones('recuperacion_rechazada') from None
