"""Trabajos web persistentes de construcción deliberada; sin análisis ni aprobaciones."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import threading
from uuid import uuid4

from . import adaptador_etabs as ad
from . import ejecutor_etabs as ej
from . import gestion_configuracion as configuraciones
from . import operaciones_etabs as operaciones
from . import revision_modelo as modelos
from .ejecucion_modelo import EjecutorVerificado


class ErrorEjecucion(ValueError):
    """Errores públicos sin rutas; HTTP puede devolver 409 con su código."""
    def __init__(self, codigo):
        self.codigo = codigo
        super().__init__(codigo)


def _bytes(data):
    return (json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False,
                       separators=(',', ':'))+'\n').encode('utf-8')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _seguro(path, *, falta=False):
    path = Path(path)
    try:
        info = path.lstat()
    except FileNotFoundError:
        if falta:
            return path
        raise
    if (path.resolve() != path or stat.S_ISLNK(info.st_mode)
            or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
        raise ErrorEjecucion('ruta_no_permitida')
    return path


def _uuid(value):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{32}', value) is None:
        raise ErrorEjecucion('identificador_invalido')
    return value


def _nuevo(path, data):
    _seguro(path, falta=True)
    with path.open('xb') as stream:
        stream.write(data)


class ServicioEjecucion:
    """El modo real es el predeterminado. Las fábricas solo se inyectan desde pruebas."""
    def __init__(self, app, *, fabrica_adaptador=None, fabrica_ejecutor=None):
        self.app = app
        self.base = _seguro(Path(app.raiz)) / '.ejecucion_web'
        _seguro(self.base, falta=True).mkdir(exist_ok=True)
        self.db = self.base / 'trabajos.sqlite3'
        self.lease = self.base / 'trabajo.lock'
        self.motor_lock = self.base / 'motor.lock'
        self.pendiente = self.base / 'operacion_pendiente.json'
        self._adapter = fabrica_adaptador or (lambda work, lock: ad.AdaptadorEtabs(
            ad.ConfiguracionPuente.real(work, lock, timeout_s=900)))
        self._executor = fabrica_ejecutor or (lambda work, lock: EjecutorVerificado(
            ej.configuracion_real(work, lock, timeout_s=900)))
        self._threads = {}
        with self._conexion() as db:
            db.execute('CREATE TABLE IF NOT EXISTS trabajos (id TEXT PRIMARY KEY, caso TEXT NOT NULL, clave TEXT NOT NULL, payload TEXT NOT NULL, estado TEXT NOT NULL, registro TEXT NOT NULL, UNIQUE(caso,clave))')
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS ejecucion_unica ON trabajos((1)) WHERE estado='en_ejecucion'")

    def _conexion(self):
        _seguro(self.base)
        _seguro(self.db, falta=True)
        db = sqlite3.connect(self.db, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def _caso(self, caso, fingerprint=None):
        folder, manifest, current = self.app.expediente(caso)
        folder = _seguro(Path(folder))
        if folder.parent != Path(self.app.raiz):
            raise ErrorEjecucion('caso_invalido')
        if fingerprint is not None and (not isinstance(fingerprint, str) or current != fingerprint):
            raise ErrorEjecucion('expediente_cambio')
        return folder, manifest, current

    def _carpeta(self, caso, ident):
        folder, _, _ = self._caso(caso)
        base = _seguro(folder/'trabajos_construccion')
        return _seguro(base/_uuid(ident))

    def _leer(self, caso, ident):
        _uuid(ident)
        with self._conexion() as db:
            row = db.execute('SELECT * FROM trabajos WHERE id=? AND caso=?', (ident, caso)).fetchone()
        if row is None:
            raise ErrorEjecucion('trabajo_ausente')
        return json.loads(row['registro']), row['estado']

    def _estado(self, record, state, **extra):
        record = {**record, **extra}
        with self._conexion() as db:
            db.execute('UPDATE trabajos SET estado=?,registro=? WHERE id=?',
                       (state, _bytes(record).decode(), record['id']))
        _nuevo(self._carpeta(record['caso'], record['id']) / ('evento_'+uuid4().hex+'.json'),
               _bytes({'estado': state, 'registro': record}))
        return record

    def _ruta_relativa(self, folder, name):
        if not isinstance(name, str) or not name or '\\' in name or ':' in name:
            raise ErrorEjecucion('plantilla_relativa_invalida')
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts or relative.as_posix() != name:
            raise ErrorEjecucion('plantilla_relativa_invalida')
        path = folder
        for part in relative.parts:
            path = _seguro(path/part)
        if not path.is_file() or path.suffix.lower() != '.edb':
            raise ErrorEjecucion('plantilla_relativa_invalida')
        return path

    @staticmethod
    def _rutas_motor(folder, work, template):
        # Las rutas que consumirán CreateProcess/PowerShell/CSI deben ser nativas
        # cortas: no descubrir esta restricción después de abrir ETABS.
        candidates = (folder/'motor_web'/('0'*32)/'solicitud.json',
                      work/'copia'/template.name, work/'modelo_construido.edb')
        if os.name == 'nt' and any(len(str(p)) >= 260 for p in candidates):
            raise ErrorEjecucion('ruta_motor_demasiado_larga_use_raiz_mas_corta')

    def _revalidar(self, record):
        folder, _, _ = self._caso(record['caso'], record['expediente_sha256'])
        work = self._carpeta(record['caso'], record['id'])
        raw = _seguro(work/'preparacion.json').read_bytes()
        if _sha(raw) != record['huella_preparacion']:
            raise ErrorEjecucion('preparacion_alterada')
        prepared = json.loads(raw)
        if prepared['id'] != record['id'] or prepared['caso'] != record['caso']:
            raise ErrorEjecucion('preparacion_alterada')
        config = configuraciones.consultar(self.app.raiz, record['caso'], record['configuracion_version'])
        if not config['comprobacion']['apto_para_adaptador']:
            raise ErrorEjecucion('configuracion_no_vigente')
        data = config['configuracion']
        if _sha(_bytes(data)) != prepared['sha256_configuracion_snapshot']:
            raise ErrorEjecucion('configuracion_cambio')
        if _seguro(work/'configuracion.json').read_bytes() != _bytes(data):
            raise ErrorEjecucion('configuracion_cambio')
        template = self._ruta_relativa(folder, prepared['plantilla_relativa'])
        self._rutas_motor(folder, work, template)
        if _sha(template.read_bytes()) != data['plantilla']['sha256']:
            raise ErrorEjecucion('plantilla_cambio')
        opts = {**prepared['opciones'], 'destino_guardado': str(work/'modelo_construido.edb')}
        plan = operaciones.generar_plan_por_version(self.app.raiz, data, **opts).datos
        if _seguro(work/'plan.json').read_bytes() != _bytes(plan) or plan['huella_plan'] != record['huella_plan']:
            raise ErrorEjecucion('plan_cambio')
        for name, digest in prepared['snapshots'].items():
            target = work/name
            if target.parent not in (work, work/'originales') or _sha(_seguro(target).read_bytes()) != digest:
                raise ErrorEjecucion('snapshot_alterado')
        self._caso(record['caso'], record['expediente_sha256'])
        return data, plan, template

    def _publico(self, record, state, *, comprobar=True):
        vigente = True
        if comprobar:
            try:
                self._revalidar(record)
                if state == 'aceptado':
                    modelos.consultar(self.app.raiz, record['caso'], record['modelo_id'])
            except (ValueError, OSError, RuntimeError, KeyError, TypeError):
                vigente = False
        return {k: record[k] for k in ('id', 'caso', 'configuracion_version', 'expediente_sha256',
                                       'huella_preparacion', 'huella_plan', 'operaciones_totales',
                                       'datos_sinteticos')} | {
            'estado': state, 'vigente': vigente, 'modelo_id': record.get('modelo_id'),
            'problemas': ([] if vigente else ['entradas_o_evidencias_no_vigentes']),
            'modo_ejecucion': record.get('modo_ejecucion'), 'analisis_ejecutado': False,
            'aprueba_modelo': False, 'aprueba_resultados': False,
            'requiere_recuperacion': state == 'incierto'}

    def preparar(self, body):
        try:
            with self.app.lock, self._conexion() as db:
                required = {'caso','configuracion_version','plantilla_relativa','expediente_sha256','clave_solicitud','opciones'}
                if not isinstance(body, dict) or set(body) != required:
                    raise ErrorEjecucion('campos_invalidos')
                _uuid(body['clave_solicitud']); _uuid(body['configuracion_version'])
                opts = body['opciones']
                allowed = {'tipo_shell_muro','tipo_shell_losa','gravedad_programa_m_s2','parametros_modales',
                           'amortiguamiento_funciones','excentricidad_espectral','respuesta_rigida_espectral'}
                if not isinstance(opts, dict) or set(opts)-allowed:
                    raise ErrorEjecucion('opciones_invalidas')
                folder, manifest, fingerprint = self._caso(body['caso'], body['expediente_sha256'])
                payload = _sha(_bytes(body))
                db.execute('BEGIN IMMEDIATE')
                existing = db.execute('SELECT * FROM trabajos WHERE caso=? AND clave=?',
                                      (body['caso'], body['clave_solicitud'])).fetchone()
                if existing:
                    if existing['payload'] != payload:
                        raise ErrorEjecucion('clave_reutilizada_con_otros_datos')
                    return self._publico(json.loads(existing['registro']), existing['estado'])
                config = configuraciones.consultar(self.app.raiz, body['caso'], body['configuracion_version'])
                data = config['configuracion']
                if not config['comprobacion']['apto_para_adaptador']:
                    raise ErrorEjecucion('configuracion_no_aprobada')
                template = self._ruta_relativa(folder, body['plantilla_relativa'])
                if _sha(template.read_bytes()) != data['plantilla']['sha256']:
                    raise ErrorEjecucion('plantilla_cambio')
                ident = uuid4().hex
                base = _seguro(folder/'trabajos_construccion', falta=True)
                base.mkdir(exist_ok=True)
                work = base/ident
                self._rutas_motor(folder, work, template)
                work.mkdir()
                plan = operaciones.generar_plan_por_version(self.app.raiz, data,
                    **opts, destino_guardado=str(work/'modelo_construido.edb')).datos
                snapshots = {'configuracion.json': _bytes(data), 'expediente.json': (folder/'expediente.json').read_bytes()}
                (work/'originales').mkdir()
                for index, item in enumerate(manifest['archivos']):
                    relative = item['archivo']
                    if (not isinstance(relative, str) or Path(relative).is_absolute()
                            or Path(relative).drive or '..' in Path(relative).parts):
                        raise ErrorEjecucion('original_no_vigente')
                    source = folder
                    for part in Path(relative).parts:
                        source = _seguro(source/part)
                    raw = source.read_bytes()
                    if _sha(raw) != item['sha256']:
                        raise ErrorEjecucion('original_no_vigente')
                    snapshots['originales/'+str(index)+'.bin'] = raw
                for name, raw in snapshots.items():
                    _nuevo(work/name, raw)
                _nuevo(work/'plan.json', _bytes(plan))
                prepared = {'id': ident, **body, 'sha256_configuracion_snapshot': _sha(_bytes(data)),
                            'snapshots': {name: _sha(raw) for name, raw in snapshots.items()}}
                _nuevo(work/'preparacion.json', _bytes(prepared))
                record = {'id': ident, 'caso': body['caso'], 'configuracion_version': body['configuracion_version'],
                          'expediente_sha256': fingerprint, 'huella_preparacion': _sha(_bytes(prepared)),
                          'huella_plan': plan['huella_plan'], 'operaciones_totales': len(plan['operaciones']),
                          'datos_sinteticos': data['datos_sinteticos']}
                self._revalidar(record)
                db.execute('INSERT INTO trabajos VALUES (?,?,?,?,?,?)',
                           (ident, body['caso'], body['clave_solicitud'], payload, 'preparado', _bytes(record).decode()))
                return self._publico(record, 'preparado', comprobar=False)
        except ErrorEjecucion:
            raise
        except (ValueError, OSError, RuntimeError, KeyError, TypeError, sqlite3.Error):
            raise ErrorEjecucion('preparacion_rechazada') from None

    def _huerfano(self, record, state):
        if state != 'en_ejecucion':
            return record, state
        try:
            lease = ad.BloqueoExclusivo(_seguro(self.lease, falta=True)).adquirir()
        except ad.ErrorBloqueo:
            return record, state
        try:
            record, state = self._leer(record['caso'], record['id'])
            if state != 'en_ejecucion':
                return record, state
            if not self.pendiente.exists():
                _nuevo(self.pendiente, _bytes({'id': record['id'], 'estado': 'interrupcion_no_confirmada'}))
            return self._estado(record, 'incierto'), 'incierto'
        finally:
            lease.liberar()

    def confirmar_recuperacion(self, body):
        """Recuperación EXPLÍCITA del motor web tras una interrupción (trabajo «incierto», operacion_pendiente.json).

        Equivale a adaptador_etabs.confirmar_recuperacion para el control compartido de los servicios web: exige motor inactivo
        declarado tras comprobación externa, revisor y motivo; toma el lease (falla si algún worker sigue vivo) y ARCHIVA los
        marcadores renombrándolos (nunca los borra). Los trabajos inciertos conservan su estado: no se reanudan ni se aceptan.
        No cierra ETABS ni autentica la declaración.
        """
        if not isinstance(body, dict) or set(body) != {'motor_inactivo_declarado', 'revisor_declarado', 'motivo', 'confirmacion_explicita'}:
            raise ErrorEjecucion('campos_invalidos')
        if body['confirmacion_explicita'] is not True or body['motor_inactivo_declarado'] is not True:
            raise ErrorEjecucion('confirmacion_requerida')
        if not all(isinstance(body[k], str) and body[k].strip() for k in ('revisor_declarado', 'motivo')):
            raise ErrorEjecucion('revisor_y_motivo_requeridos')
        with self.app.lock:
            try:
                lease = ad.BloqueoExclusivo(_seguro(self.lease, falta=True)).adquirir()
            except ad.ErrorBloqueo:
                raise ErrorEjecucion('otra_ejecucion_activa') from None
            try:
                with self._conexion() as db:
                    if db.execute("SELECT 1 FROM trabajos WHERE estado='en_ejecucion'").fetchone():
                        raise ErrorEjecucion('trabajo_en_ejecucion')
                marcadores = [m for m in (self.pendiente, Path(str(self.motor_lock) + '.incierto.json')) if m.exists()]
                if not marcadores:
                    raise ErrorEjecucion('sin_incertidumbre')
                ident = uuid4().hex
                archivados = []
                for marcador in marcadores:
                    _seguro(marcador)
                    destino = marcador.with_name(marcador.name + '.resuelto.' + ident)
                    marcador.rename(destino)
                    archivados.append(destino.name)
                registro = {'motor_inactivo_declarado': True, 'revisor_declarado': body['revisor_declarado'], 'motivo': body['motivo'],
                            'identidad_revisor': 'declarada_no_verificada', 'archivados': archivados,
                            'fecha_utc': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}
                _nuevo(self.base / ('recuperacion_' + ident + '.json'), _bytes(registro))
                return {'recuperado': True, 'id': ident, 'archivados': archivados}
            finally:
                lease.liberar()

    def consultar(self, caso, trabajo):
        try:
            with self.app.lock:
                self._caso(caso)
                record, state = self._huerfano(*self._leer(caso, trabajo))
                return self._publico(record, state)
        except ErrorEjecucion:
            raise
        except (ValueError, OSError, RuntimeError, KeyError, TypeError, sqlite3.Error):
            raise ErrorEjecucion('consulta_rechazada') from None

    def listar(self, caso):
        try:
            with self.app.lock, self._conexion() as db:
                _, _, fingerprint = self._caso(caso)
                ids = [r['id'] for r in db.execute('SELECT id FROM trabajos WHERE caso=? ORDER BY rowid', (caso,))]
                return {'caso': caso, 'expediente_sha256': fingerprint,
                        'trabajos': [self.consultar(caso, ident) for ident in ids]}
        except ErrorEjecucion:
            raise
        except (ValueError, OSError, RuntimeError, KeyError, TypeError, sqlite3.Error):
            raise ErrorEjecucion('consulta_rechazada') from None

    def ejecutar(self, body):
        lease = None
        try:
            with self.app.lock:
                if not isinstance(body, dict) or set(body) != {'caso','trabajo','huella_preparacion','expediente_sha256','confirmacion_explicita'}:
                    raise ErrorEjecucion('campos_invalidos')
                if body['confirmacion_explicita'] is not True:
                    raise ErrorEjecucion('confirmacion_requerida')
                record, state = self._huerfano(*self._leer(body['caso'], body['trabajo']))
                self._caso(body['caso'], body['expediente_sha256'])
                if body['huella_preparacion'] != record['huella_preparacion'] or body['expediente_sha256'] != record['expediente_sha256']:
                    raise ErrorEjecucion('preparacion_cambio')
                if state != 'preparado':
                    return self._publico(record, state)
                lease = ad.BloqueoExclusivo(_seguro(self.lease, falta=True)).adquirir()
                if self.pendiente.exists() or Path(str(self.motor_lock)+'.incierto.json').exists():
                    raise ErrorEjecucion('motor_incierto')
                with self._conexion() as db:
                    db.execute('BEGIN IMMEDIATE')
                    row = db.execute('SELECT estado FROM trabajos WHERE id=?', (record['id'],)).fetchone()
                    if row['estado'] != 'preparado':
                        raise ErrorEjecucion('trabajo_cambio')
                    try:
                        self._revalidar(record)
                    except (ValueError, OSError, RuntimeError, KeyError, TypeError):
                        db.execute("UPDATE trabajos SET estado='fallido_sin_lanzar' WHERE id=?", (record['id'],))
                        db.commit()
                        raise ErrorEjecucion('entradas_no_vigentes') from None
                    _nuevo(self.pendiente, _bytes({'id': record['id'], 'estado': 'lanzamiento_no_confirmado'}))
                    db.execute("UPDATE trabajos SET estado='en_ejecucion' WHERE id=?", (record['id'],))
                thread = threading.Thread(target=self._worker, args=(record, lease), daemon=True)
                self._threads[record['id']] = thread
                thread.start()
                lease = None  # el worker conserva la exclusión hasta su salida
                return self._publico(record, 'en_ejecucion', comprobar=False)
        except ErrorEjecucion:
            raise
        except ad.ErrorBloqueo:
            raise ErrorEjecucion('otra_ejecucion_activa') from None
        except (ValueError, OSError, RuntimeError, KeyError, TypeError, sqlite3.Error):
            raise ErrorEjecucion('ejecucion_rechazada') from None
        finally:
            if lease is not None:
                lease.liberar()

    def _worker(self, record, lease):
        touched = False
        try:
            work = self._carpeta(record['caso'], record['id'])
            data, plan, template = self._revalidar(record)
            # Las corridas de transporte no se anidan dentro del UUID del trabajo:
            # CreateProcessW rechaza cwd >260 incluso con prefijo extendido.
            motor_work = _seguro(work.parent.parent/'motor_web', falta=True)
            motor_work.mkdir(exist_ok=True)
            _seguro(self.motor_lock, falta=True)
            adapter = self._adapter(motor_work, self.motor_lock)
            if adapter.config.modo == 'doble' and data['datos_sinteticos'] is not True:
                raise ErrorEjecucion('doble_requiere_datos_sinteticos')
            # Todavía no hay motor: se prepara copia y solicitud sin proceso.
            request = adapter.abrir_copia_plantilla(template, data['plantilla']['sha256'],
                work/'copia', instancia='nueva', solo_preparar=True)
            _nuevo(work/'apertura_ref.json', _bytes({'grupo': 'motor_web', 'corrida_id': request.id}))
            self._revalidar(record)
            touched = True  # incluso un fallo antes de respuesta puede haber creado ETABS
            opened = adapter.ejecutar(request)
            pid = opened.datos.get('id_proceso')
            copy = work/'copia'/template.name
            if (type(pid) is not int or pid <= 0 or opened.datos.get('instancia') != 'nueva'
                    or Path(str(opened.datos.get('modelo_abierto', ''))) != copy
                    or _sha(_seguro(copy).read_bytes()) != data['plantilla']['sha256']):
                raise ErrorEjecucion('apertura_no_confirmada')
            _nuevo(work/'instancia_propia.json', _bytes({'id_proceso': pid, 'solicitud': request.id}))
            self._revalidar(record)
            executor = self._executor(motor_work, self.motor_lock)
            if executor.config.modo != opened.modo_ejecucion:
                raise ErrorEjecucion('modo_incoherente')
            prepared = executor.preparar(self.app.raiz, data, plan, copia=copy,
                                         modelo_esperado=copy, id_proceso=pid)
            _nuevo(work/'construccion_ref.json', _bytes({'grupo': 'motor_web', 'corrida_id': prepared.solicitud.id}))
            result = executor.ejecutar(prepared, confirmar_mutacion=True)
            self._revalidar(record)
            # Registro público verifica de nuevo aceptación integrada, retorno/traza y EDB.
            published = modelos.registrar(self.app.raiz, record['caso'], data, plan, prepared.carpeta)
            model = modelos.consultar(self.app.raiz, record['caso'], published.name)
            self._revalidar(record)
            _nuevo(work/'estado_motor_resuelto.json', _seguro(self.pendiente).read_bytes())
            self.pendiente.unlink()
            self._estado(record, 'aceptado', modelo_id=model['modelo_id'], modo_ejecucion=result.modo_ejecucion)
        except Exception as error:
            # Tras entregar al worker no se reanuda la operación aunque el fallo
            # aparente preceder a la apertura. Conservar la reserva es conservador.
            state = 'incierto'
            # Nunca borrar evidencia de incertidumbre por fallo ni reintentar aquí.
            if touched and not self.pendiente.exists():
                _nuevo(self.pendiente, _bytes({'id': record['id'], 'estado': 'aceptacion_no_confirmada'}))
            try:
                _nuevo(self._carpeta(record['caso'], record['id'])/'error_worker.json',
                       _bytes({'tipo': type(error).__name__, 'mensaje': str(error)}))
                self._estado(record, state)
            except Exception:
                pass  # DB en ejecución + lease liberado se reconocerá como huérfano
        finally:
            lease.liberar()
