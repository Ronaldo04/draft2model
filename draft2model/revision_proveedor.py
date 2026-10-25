"""Trabajos web del proveedor visual: plan local sin clave ni red y envío deliberado.

Reutiliza preparar_plan/preparar_peticion/ejecutar_plan del cliente existente. El
transporte Python solo se inyecta desde pruebas y nunca acredita una llamada real.
No aprueba ingeniería ni resultados; el traslado a revisión es una acción separada.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
from uuid import uuid4

from . import proveedor_openai as cliente
from .adaptador_etabs import BloqueoExclusivo, ErrorBloqueo
from .gestion_extraccion import json_desde_bytes

CAMPOS_PREPARAR = {'caso', 'expediente_sha256', 'paquete', 'modelo', 'opciones', 'clave_solicitud'}
CAMPOS_OPCIONES = {'max_tokens', 'detalle', 'timeout_s'}
CAMPOS_EJECUTAR = {'caso', 'trabajo', 'huella_preparacion', 'expediente_sha256', 'confirmacion_explicita'}
CAMPOS_RECUPERAR = {'caso', 'trabajo', 'huella_preparacion', 'confirmacion_explicita', 'resolucion'}
BLOQUEANTES = ('en_ejecucion', 'incierto')
ERRORES = (ValueError, OSError, RuntimeError, KeyError, TypeError, sqlite3.Error)


class ErrorProveedorWeb(ValueError):
    """Error público sin rutas ni detalles del transporte; HTTP puede devolver 409 con su código."""
    def __init__(self, codigo):
        self.codigo = codigo
        super().__init__(codigo)


def _bytes(data):
    return (json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False,
                       separators=(',', ':'))+'\n').encode('utf-8')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _uuid(value):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{32}', value) is None:
        raise ErrorProveedorWeb('identificador_invalido')
    return value


def _hex64(value):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ErrorProveedorWeb('huella_invalida')
    return value


def _directa(path):
    """Ruta existente, sin enlaces ni junctions en su último componente."""
    path = Path(path)
    if path.resolve() != path or path.is_symlink():
        raise ErrorProveedorWeb('ruta_no_permitida')
    return path


def _leer(path):
    path = _directa(path)
    if not path.is_file():
        raise ErrorProveedorWeb('archivo_ausente')
    return path.read_bytes()


def _nuevo(path, data):
    with Path(path).open('xb') as stream:
        stream.write(data)


def _proveedor(record):
    return cliente.validar_proveedor(record.get('proveedor', 'openai'))


def _clave_presente(proveedor='openai'):
    # Solo se comprueba presencia; el valor nunca se lee a variables persistidas ni se devuelve.
    return bool(cliente.clave_api(proveedor))


class ServicioProveedor:
    """`transporte(payload, timeout)` solo desde pruebas Python; nunca recibe la credencial."""

    def __init__(self, app, transporte=None):
        self.app = app
        if transporte is not None and not callable(transporte):
            raise TypeError('transporte inválido')
        self._transporte = transporte
        raiz = _directa(Path(app.raiz))
        self.base = raiz/'.proveedor_web'
        if not self.base.exists():
            self.base.mkdir()
        _directa(self.base)
        (self.base/'trabajos').mkdir(exist_ok=True)
        _directa(self.base/'trabajos')
        self.db = self.base/'trabajos.sqlite3'
        self.control = self.base/'proveedor.lock'  # control propio; no es el lease de ETABS
        self._threads = {}
        with self._conexion() as db:
            db.execute('CREATE TABLE IF NOT EXISTS trabajos (id TEXT PRIMARY KEY, caso TEXT NOT NULL, clave TEXT NOT NULL, '
                       'payload TEXT NOT NULL, estado TEXT NOT NULL, registro TEXT NOT NULL, UNIQUE(caso,clave))')
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS envio_unico ON trabajos((1)) WHERE estado='en_ejecucion'")

    # -- persistencia ------------------------------------------------------------
    def _conexion(self):
        if self.db.exists():
            _directa(self.db)
        db = sqlite3.connect(self.db, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def _carpeta(self, ident):
        folder = self.base/'trabajos'/_uuid(ident)
        if not folder.exists():
            folder.mkdir()
        return _directa(folder)

    def _leer_trabajo(self, caso, ident):
        _uuid(ident)
        with self._conexion() as db:
            row = db.execute('SELECT * FROM trabajos WHERE id=? AND caso=?', (ident, caso)).fetchone()
        if row is None:
            raise ErrorProveedorWeb('trabajo_ausente')
        return json.loads(row['registro']), row['estado']

    def _estado(self, record, state, **extra):
        record = {**record, **extra}
        with self._conexion() as db:
            db.execute('UPDATE trabajos SET estado=?,registro=? WHERE id=?', (state, _bytes(record).decode(), record['id']))
        _nuevo(self._carpeta(record['id'])/('evento_'+uuid4().hex+'.json'), _bytes({'estado': state, 'registro': record}))
        return record

    # -- fuentes -------------------------------------------------------------------
    def _caso(self, caso, fingerprint=None):
        folder, _, current = self.app.expediente(caso)
        folder = _directa(Path(folder))
        if folder.parent != Path(self.app.raiz):
            raise ErrorProveedorWeb('caso_invalido')
        if fingerprint is not None and current != fingerprint:
            raise ErrorProveedorWeb('expediente_cambio')
        grupos = ('vision', 'vision/solicitudes', 'vision/respuestas') + tuple(
            'vision/'+tipo+'_'+p for p in cliente.proveedores.CATALOGO for tipo in ('planes', 'intentos'))
        for group in grupos:
            if (folder/group).exists():
                _directa(folder/group)
        return folder, current

    def _solicitud(self, folder, paquete):
        return _directa(folder/'vision/solicitudes'/_uuid(paquete)/'solicitud.json')

    def _revalidar(self, record):
        """Paquete vigente, plan intacto y petición recalculada idéntica; sin red ni clave."""
        folder, fingerprint = self._caso(record['caso'], record['expediente_sha256'])
        package = self.app.preparacion.paquete(record['caso'], record['paquete'], expediente_sha256=fingerprint)
        if package['sha256_solicitud'] != record['sha256_solicitud'] or package['transmision_externa'] is not False:
            raise ErrorProveedorWeb('paquete_cambio')
        plan_path = _directa(folder/('vision/planes_'+_proveedor(record))/_uuid(record['plan'])/'plan.json')
        raw = _leer(plan_path)
        if _sha(raw) != record['sha256_plan']:
            raise ErrorProveedorWeb('plan_alterado')
        plan = json_desde_bytes(raw, 'plan')
        expected = 'vision/solicitudes/'+record['paquete']+'/solicitud.json'
        if (not isinstance(plan, dict) or plan.get('contrato') != 'draft2model.plan_vision_'+_proveedor(record)
                or plan.get('caso') != record['caso'] or plan.get('solicitud') != expected):
            raise ErrorProveedorWeb('plan_alterado')
        opts = record['opciones']
        _, current = cliente.preparar_peticion(folder/'expediente.json', self._solicitud(folder, record['paquete']),
                                               modelo=record['modelo_declarado'], max_tokens=opts['max_tokens'],
                                               detalle=opts['detalle'], proveedor=_proveedor(record))
        if plan.get('configuracion') != current or current['peticion_sha256'] != record['sha256_peticion']:
            raise ErrorProveedorWeb('peticion_cambio')
        self._caso(record['caso'], record['expediente_sha256'])
        if _sha(_leer(plan_path)) != record['sha256_plan']:
            raise ErrorProveedorWeb('plan_alterado')
        return folder, plan_path

    # -- proyección pública --------------------------------------------------------
    def _publico(self, record, state, *, comprobar=True):
        vigente = True
        if comprobar and state in ('preparado', 'completado_verificado'):
            try:
                self._revalidar(record)
                if state == 'completado_verificado':
                    self._verificar_salida(record, record['salida'])
            except ERRORES:
                vigente = False
        out = {k: record[k] for k in ('id', 'caso', 'paquete', 'expediente_sha256', 'modelo_declarado', 'opciones',
                                      'huella_preparacion', 'sha256_solicitud', 'sha256_plan', 'sha256_peticion')}
        salida = record.get('salida') or {}
        return out | {
            'proveedor': _proveedor(record), 'endpoint_declarado': record.get('endpoint_declarado', cliente.ENDPOINT), 'estado': state, 'vigente': vigente, 'problemas': [] if vigente else ['entradas_o_evidencias_no_vigentes'],
            'requiere_recuperacion': state == 'incierto',
            'modo': record.get('modo'), 'proveedor_declarado': record.get('proveedor_declarado'),
            'llamada_real_acreditada': record.get('modo') == 'real' and state == 'completado_verificado',
            'observado': {k: salida.get(k) for k in ('modelo_devuelto', 'respuesta_id_declarado', 'usage',
                                                     'sha256_respuesta_api', 'duracion_api_segundos')},
            'costo_estimado': None,
            'respuesta_visual': ({'id': salida['respuesta_visual_id'], 'sha256_extraccion': salida['sha256_extraccion']}
                                 if salida.get('respuesta_visual_id') else None),
            'resolucion': record.get('resolucion'),
            'aprueba_ingenieria': False, 'aprueba_resultados': False}

    # -- operaciones -------------------------------------------------------------
    def preparar(self, body):
        try:
            with self.app.lock, self._conexion() as db:
                if not isinstance(body, dict) or set(body) not in (CAMPOS_PREPARAR, CAMPOS_PREPARAR | {'proveedor'}):
                    raise ErrorProveedorWeb('campos_invalidos')
                cliente.validar_proveedor(body.get('proveedor', 'openai'))
                if self._transporte is None:  # recorrido real: solo Google/OpenAI para planos (adaptadores extra solo con dobles)
                    from .politica_uso_ia import exigir_autorizacion, FINALIDAD_AUTORIZADA
                    try:
                        exigir_autorizacion(body.get('proveedor', 'openai'), FINALIDAD_AUTORIZADA)
                    except ValueError:
                        raise ErrorProveedorWeb('proveedor_no_autorizado') from None
                _uuid(body['clave_solicitud']); _uuid(body['paquete']); _hex64(body['expediente_sha256'])
                opts = body['opciones']
                if (not isinstance(opts, dict) or set(opts) != CAMPOS_OPCIONES
                        or type(opts['max_tokens']) is not int or not 256 <= opts['max_tokens'] <= 16384
                        or opts['detalle'] not in ('low', 'high', 'auto')
                        or type(opts['timeout_s']) is not int or not 1 <= opts['timeout_s'] <= 180):
                    raise ErrorProveedorWeb('opciones_invalidas')
                if not isinstance(body['modelo'], str) or re.fullmatch(r'[A-Za-z0-9_.:/-]{1,128}', body['modelo']) is None:
                    raise ErrorProveedorWeb('modelo_declarado_invalido')
                folder, fingerprint = self._caso(body['caso'], body['expediente_sha256'])
                payload = _sha(_bytes(body))
                db.execute('BEGIN IMMEDIATE')
                existing = db.execute('SELECT * FROM trabajos WHERE caso=? AND clave=?',
                                      (body['caso'], body['clave_solicitud'])).fetchone()
                if existing:
                    if existing['payload'] != payload:
                        raise ErrorProveedorWeb('clave_reutilizada_con_otros_datos')
                    return self._publico(json.loads(existing['registro']), existing['estado'])
                package = self.app.preparacion.paquete(body['caso'], body['paquete'], expediente_sha256=fingerprint)
                plan_path = cliente.preparar_plan(folder/'expediente.json', self._solicitud(folder, body['paquete']),
                                                  modelo=body['modelo'], max_tokens=opts['max_tokens'], detalle=opts['detalle'], proveedor=body.get('proveedor', 'openai'))
                plan = json_desde_bytes(_leer(plan_path), 'plan')
                ident = uuid4().hex
                core = {'id': ident, 'caso': body['caso'], 'paquete': body['paquete'], 'expediente_sha256': fingerprint,
                        'modelo_declarado': body['modelo'], 'opciones': dict(opts), 'proveedor': body.get('proveedor', 'openai'),
                        'sha256_solicitud': package['sha256_solicitud'], 'plan': plan_path.parent.name,
                        'endpoint_declarado': plan['configuracion']['endpoint'],
                        'sha256_plan': _sha(_leer(plan_path)), 'sha256_peticion': plan['configuracion']['peticion_sha256']}
                record = {**core, 'huella_preparacion': _sha(_bytes(core))}
                self._revalidar(record)
                _nuevo(self._carpeta(ident)/'preparacion.json', _bytes(record))
                db.execute('INSERT INTO trabajos VALUES (?,?,?,?,?,?)',
                           (ident, body['caso'], body['clave_solicitud'], payload, 'preparado', _bytes(record).decode()))
                return self._publico(record, 'preparado', comprobar=False)
        except ErrorProveedorWeb:
            raise
        except ERRORES:
            raise ErrorProveedorWeb('preparacion_rechazada') from None

    def _huerfano(self, record, state):
        """en_ejecucion sin worker vivo (control libre) pasa a incierto; nunca se relanza."""
        if state != 'en_ejecucion':
            return record, state
        try:
            control = BloqueoExclusivo(self.control).adquirir()
        except ErrorBloqueo:
            return record, state
        try:
            record, state = self._leer_trabajo(record['caso'], record['id'])
            if state != 'en_ejecucion':
                return record, state
            return self._estado(record, 'incierto', causa='interrupcion_no_confirmada'), 'incierto'
        finally:
            control.liberar()

    def consultar(self, caso, trabajo):
        try:
            with self.app.lock:
                self._caso(caso)
                return self._publico(*self._huerfano(*self._leer_trabajo(caso, trabajo)))
        except ErrorProveedorWeb:
            raise
        except ERRORES:
            raise ErrorProveedorWeb('consulta_rechazada') from None

    def listar(self, caso):
        try:
            with self.app.lock, self._conexion() as db:
                _, fingerprint = self._caso(caso)
                ids = [r['id'] for r in db.execute('SELECT id FROM trabajos WHERE caso=? ORDER BY rowid', (caso,))]
                return {'caso': caso, 'expediente_sha256': fingerprint,
                        'trabajos': [self.consultar(caso, ident) for ident in ids]}
        except ErrorProveedorWeb:
            raise
        except ERRORES:
            raise ErrorProveedorWeb('consulta_rechazada') from None

    def ejecutar(self, body):
        control = None
        try:
            with self.app.lock:
                if not isinstance(body, dict) or set(body) != CAMPOS_EJECUTAR:
                    raise ErrorProveedorWeb('campos_invalidos')
                if body['confirmacion_explicita'] is not True:
                    raise ErrorProveedorWeb('confirmacion_requerida')
                record, state = self._huerfano(*self._leer_trabajo(body['caso'], body['trabajo']))
                if (body['huella_preparacion'] != record['huella_preparacion']
                        or body['expediente_sha256'] != record['expediente_sha256']):
                    raise ErrorProveedorWeb('preparacion_cambio')
                if state != 'preparado':
                    return self._publico(record, state)  # idempotente: nunca un segundo envío
                if self._transporte is None and not _clave_presente(_proveedor(record)):
                    raise ErrorProveedorWeb('clave_ausente_sin_envio')
                control = BloqueoExclusivo(self.control).adquirir()
                with self._conexion() as db:
                    for row in db.execute('SELECT id,estado,registro FROM trabajos WHERE caso=? AND estado=?',
                                          (record['caso'], 'en_ejecucion')).fetchall():
                        # Con el control tomado, un en_ejecucion de este caso es huérfano.
                        self._estado(json.loads(row['registro']), 'incierto', causa='interrupcion_no_confirmada')
                    db.execute('BEGIN IMMEDIATE')
                    blocking = db.execute('SELECT COUNT(*) FROM trabajos WHERE caso=? AND estado IN (?,?)',
                                          (record['caso'], *BLOQUEANTES)).fetchone()[0]
                    if blocking:
                        raise ErrorProveedorWeb('incertidumbre_pendiente_en_caso')
                    row = db.execute('SELECT estado FROM trabajos WHERE id=?', (record['id'],)).fetchone()
                    if row['estado'] != 'preparado':
                        raise ErrorProveedorWeb('trabajo_cambio')
                    try:
                        self._revalidar(record)
                    except ERRORES:
                        db.execute('UPDATE trabajos SET estado=? WHERE id=?', ('fallido_sin_envio', record['id']))
                        db.commit()
                        raise ErrorProveedorWeb('entradas_no_vigentes') from None
                    record = {**record, 'modo': 'transporte_prueba_python' if self._transporte else 'real',
                              'proveedor_declarado': 'simulado' if self._transporte else _proveedor(record)}
                    db.execute('UPDATE trabajos SET estado=?,registro=? WHERE id=?',
                               ('en_ejecucion', _bytes(record).decode(), record['id']))
                _nuevo(self._carpeta(record['id'])/('evento_'+uuid4().hex+'.json'),
                       _bytes({'estado': 'en_ejecucion', 'registro': record}))
                thread = threading.Thread(target=self._worker, args=(record, control), daemon=True)
                self._threads[record['id']] = thread
                thread.start()
                control = None  # el worker conserva el control hasta su salida
                return self._publico(record, 'en_ejecucion', comprobar=False)
        except ErrorProveedorWeb:
            raise
        except ErrorBloqueo:
            raise ErrorProveedorWeb('otro_envio_activo') from None
        except ERRORES:
            raise ErrorProveedorWeb('ejecucion_rechazada') from None
        finally:
            if control is not None:
                control.liberar()

    def _verificar_salida(self, record, salida):
        """Resultado del cliente: contrato, archivos y huellas antes de declarar éxito."""
        folder, _ = self._caso(record['caso'])
        attempt = _directa(folder/('vision/intentos_'+_proveedor(record))/_uuid(salida['intento']))
        report = json_desde_bytes(_leer(attempt/'resultado.json'), 'resultado')
        simulated = record['modo'] == 'transporte_prueba_python'
        expected_state = 'simulacion_completada' if simulated else 'respuesta_pendiente_revision'
        if (not isinstance(report, dict) or report.get('estado') != expected_state or report.get('simulada') is not simulated
                or report.get('aprobacion_ingenieria') is not None or report.get('version_importada') is not None
                or report.get('configuracion', {}).get('peticion_sha256') != record['sha256_peticion']
                or report.get('configuracion', {}).get('proveedor') != _proveedor(record)):
            raise ErrorProveedorWeb('resultado_no_verificado')
        api_raw = _leer(attempt/'respuesta_api.json')
        if _sha(api_raw) != report.get('respuesta_api_sha256'):
            raise ErrorProveedorWeb('resultado_no_verificado')
        relative = report.get('extraccion')
        match = re.fullmatch(r'vision/respuestas/([0-9a-f]{32})/extraccion\.json', relative or '')
        if match is None:
            raise ErrorProveedorWeb('resultado_no_verificado')
        target = _directa(folder/'vision/respuestas'/match.group(1))
        extraction = _leer(target/'extraccion.json')
        registro = json_desde_bytes(_leer(target/'registro.json'), 'registro')
        if (not isinstance(registro, dict) or registro.get('solicitud_sha256') != record['sha256_solicitud']
                or registro.get('extraccion_sha256') != _sha(extraction) or registro.get('modo_prueba') is not simulated
                or registro.get('modelo_declarado') != record['modelo_declarado']
                or registro.get('proveedor_declarado') != ('simulado' if simulated else _proveedor(record))
                or registro.get('aprobacion_ingenieria') is not None):
            raise ErrorProveedorWeb('resultado_no_verificado')
        if salida.get('respuesta_visual_id') not in (None, match.group(1)):
            raise ErrorProveedorWeb('resultado_no_verificado')
        return {'intento': attempt.name, 'respuesta_visual_id': match.group(1), 'sha256_extraccion': _sha(extraction),
                'sha256_respuesta_api': report['respuesta_api_sha256'], 'modelo_devuelto': report.get('modelo_devuelto'),
                'respuesta_id_declarado': report.get('respuesta_id_declarado'), 'usage': report.get('usage'),
                'duracion_api_segundos': report.get('duracion_api_segundos')}

    def _intento(self, folder, record):
        marker = folder/('vision/planes_'+_proveedor(record))/record['plan']/'intento.json'
        if not marker.exists():
            return None
        data = json_desde_bytes(_leer(marker), 'intento')
        return data.get('id') if isinstance(data, dict) else None

    def _worker(self, record, control):
        transport = None
        if self._transporte is not None:
            fake = self._transporte
            transport = lambda payload, _clave, timeout: fake(payload, timeout)  # noqa: E731 la clave no sale
        folder = None
        try:
            folder, plan_path = self._revalidar(record)
            path = cliente.ejecutar_plan(folder/'expediente.json', plan_path, autorizar_envio=True,
                                         timeout=record['opciones']['timeout_s'], transporte=transport,
                                         importar_automaticamente=False)
            attempt = path.parent
            if attempt.parent != folder/('vision/intentos_'+_proveedor(record)) or attempt.name != self._intento(folder, record):
                raise ErrorProveedorWeb('intento_ajeno')
            report = json_desde_bytes(_leer(path), 'resultado')
            observed = {'intento': attempt.name, 'sha256_respuesta_api': report.get('respuesta_api_sha256'),
                        'modelo_devuelto': report.get('modelo_devuelto'), 'usage': report.get('usage'),
                        'respuesta_id_declarado': report.get('respuesta_id_declarado'),
                        'duracion_api_segundos': report.get('duracion_api_segundos')}
            if report.get('estado') == 'fallido':
                # Sin respuesta conservada no hay evidencia de lo ocurrido en el transporte.
                state = 'respuesta_rechazada' if report.get('respuesta_api_sha256') else 'incierto'
                with self.app.lock:
                    self._estado(record, state, salida=observed, causa='cliente_' + state)
                return
            try:
                with self.app.lock:
                    salida = self._verificar_salida(record, observed)
                    self._revalidar(record)  # cambios durante el envío impiden aceptar
            except ERRORES:
                with self.app.lock:
                    self._estado(record, 'respuesta_rechazada', salida=observed, causa='verificacion_posterior_fallida')
                return
            with self.app.lock:
                self._estado(record, 'completado_verificado', salida=salida)
        except Exception as error:  # noqa: BLE001 se conserva evidencia y no se reintenta
            sent = False
            try:
                sent = folder is not None and self._intento(folder, record) is not None
            except Exception:  # noqa: BLE001
                sent = True  # ante duda, conservador
            state = 'incierto' if sent else 'fallido_sin_envio'
            try:
                codigo = error.codigo if isinstance(error, ErrorProveedorWeb) else type(error).__name__
                with self.app.lock:
                    self._estado(record, state, causa='worker_'+codigo)
            except Exception:  # noqa: BLE001
                pass  # queda en_ejecucion con control libre: se reconocerá como huérfano (incierto)
        finally:
            control.liberar()

    def recuperar(self, body):
        """Cierre explícito de un incierto, sin reintento. Solo se acepta con evidencia completa."""
        try:
            with self.app.lock:
                if not isinstance(body, dict) or set(body) != CAMPOS_RECUPERAR:
                    raise ErrorProveedorWeb('campos_invalidos')
                if body['confirmacion_explicita'] is not True or body['resolucion'] != 'cerrar_sin_reintento':
                    raise ErrorProveedorWeb('confirmacion_requerida')
                record, state = self._huerfano(*self._leer_trabajo(body['caso'], body['trabajo']))
                if body['huella_preparacion'] != record['huella_preparacion']:
                    raise ErrorProveedorWeb('preparacion_cambio')
                if state != 'incierto':
                    raise ErrorProveedorWeb('trabajo_no_incierto')
                control = BloqueoExclusivo(self.control).adquirir()
                try:
                    folder, _ = self._caso(record['caso'])
                    intento = self._intento(folder, record)
                    evidence = None
                    if intento and (folder/('vision/intentos_'+_proveedor(record))/intento/'resultado.json').exists():
                        try:
                            evidence = self._verificar_salida(record, {'intento': intento})
                            self._revalidar(record)
                        except ERRORES:
                            evidence = None
                    resolution = {'resolucion': 'cerrar_sin_reintento', 'intento_registrado': intento is not None,
                                  'evidencia_completa': evidence is not None}
                    if evidence is not None:
                        record = self._estado(record, 'completado_verificado', salida=evidence, resolucion=resolution)
                        return self._publico(record, 'completado_verificado')
                    record = self._estado(record, 'incierto_resuelto', resolucion=resolution)
                    return self._publico(record, 'incierto_resuelto')
                finally:
                    control.liberar()
        except ErrorProveedorWeb:
            raise
        except ErrorBloqueo:
            raise ErrorProveedorWeb('otro_envio_activo') from None
        except ERRORES:
            raise ErrorProveedorWeb('recuperacion_rechazada') from None
