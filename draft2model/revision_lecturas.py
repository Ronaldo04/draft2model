"""Lecturas web deliberadas: trabajos persistentes y evidencia conservada verificable."""
from datetime import datetime
import json
import os
import re
import sqlite3
from uuid import uuid4
from types import SimpleNamespace

from . import adaptador_etabs as ad
from .evidencia_analisis import verificar_analisis_aceptado
from .lectura_analisis import LectorAnalisis, configuracion_real, UNIDADES, TABLAS_CASE, RESULTADOS_API
from .revision_ejecucion import ServicioEjecucion, ErrorEjecucion, _bytes, _sha, _seguro, _uuid, _nuevo


class ErrorLecturas(ErrorEjecucion):
    """Código público constante; nunca contiene rutas ni mensajes del motor."""


class ServicioLecturas(ServicioEjecucion):
    def __init__(self, app, fabrica_lector=None):
        self.app = app
        control = app.ejecucion
        self.base, self.lease = control.base, control.lease
        self.motor_lock, self.pendiente = control.motor_lock, control.pendiente
        self.db = self.base/'lecturas.sqlite3'
        self._lector = fabrica_lector or (lambda work, lock: LectorAnalisis(configuracion_real(work, lock)))
        self._inyectada = fabrica_lector is not None
        self._threads = {}
        with self._conexion() as db:
            db.execute('CREATE TABLE IF NOT EXISTS trabajos (id TEXT PRIMARY KEY, caso TEXT NOT NULL, clave TEXT NOT NULL, payload TEXT NOT NULL, estado TEXT NOT NULL, registro TEXT NOT NULL, UNIQUE(caso,clave))')
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS ejecucion_unica ON trabajos((1)) WHERE estado='en_ejecucion'")

    def _carpeta(self, caso, ident):
        folder, _, _ = self._caso(caso)
        return _seguro(_seguro(folder/'trabajos_lecturas')/_uuid(ident))

    @staticmethod
    def _resultados_api(record):
        if 'resultados_api' not in record:
            return {}
        values = record['resultados_api']
        if (not isinstance(values, list) or not values or not all(type(v) is str for v in values)
                or len(set(values)) != len(values) or not set(values) <= set(RESULTADOS_API)):
            raise ErrorLecturas('resultados_api_invalidos')
        return {'resultados_api': list(values)}

    def _fuentes(self, record):
        self._resultados_api(record)
        folder, _, _ = self._caso(record['caso'], record['expediente_sha256'])
        run = _seguro(_seguro(folder/'analisis_etabs')/_uuid(record['analisis']))
        proof = verificar_analisis_aceptado(self.app.raiz, record['caso'], run)
        for field in ('tablas', 'casos'):
            values = record[field]
            if (not isinstance(values, list) or not values or not all(isinstance(v, str) and v.strip() for v in values)
                    or len(set(values)) != len(values)):
                raise ErrorLecturas('seleccion_invalida')
        if not set(record['casos']) <= set(proof['casos']):
            raise ErrorLecturas('casos_de_otro_analisis')
        if not self._inyectada and proof['modo'] != 'real':
            raise ErrorLecturas('analisis_doble_no_ejecutable_real')
        if proof['modo'] == 'doble' and proof['datos_sinteticos'] is not True:
            raise ErrorLecturas('doble_requiere_datos_sinteticos')
        candidates = [folder/'lecturas_etabs'/('0'*32)/'solicitud.json', run/'analizado.edb']
        if os.name == 'nt' and any(len(str(p)) >= 260 for p in candidates):
            raise ErrorLecturas('ruta_motor_demasiado_larga_use_raiz_mas_corta')
        self._caso(record['caso'], record['expediente_sha256'])
        return proof, folder, run

    def _revalidar(self, record):
        work = self._carpeta(record['caso'], record['id'])
        raw = _seguro(work/'preparacion.json').read_bytes()
        if _sha(raw) != record['huella_preparacion']:
            raise ErrorLecturas('preparacion_alterada')
        prep = json.loads(raw)
        if not isinstance(prep, dict) or any(prep.get(k) != record[k] for k in
                ('id','caso','analisis','expediente_sha256','tablas','casos')):
            raise ErrorLecturas('preparacion_alterada')
        if self._resultados_api(prep) != self._resultados_api(record):
            raise ErrorLecturas('preparacion_alterada')
        proof, folder, run = self._fuentes(record)
        snapshot = _seguro(work/'evidencia_analisis.json').read_bytes()
        manifest = _seguro(work/'expediente.json').read_bytes()
        if (prep.get('sha256_evidencia') != _sha(snapshot) or json.loads(snapshot) != proof
                or prep.get('sha256_expediente') != _sha(manifest)
                or manifest != _seguro(folder/'expediente.json').read_bytes()):
            raise ErrorLecturas('fuentes_o_snapshot_alterados')
        return proof, folder, run

    def preparar(self, body):
        try:
            with self.app.lock, self._conexion() as db:
                if not isinstance(body, dict) or set(body) - {'resultados_api'} != {'caso','analisis','expediente_sha256','clave_solicitud','tablas','casos'}:
                    raise ErrorLecturas('campos_invalidos')
                self._resultados_api(body)
                _uuid(body['analisis']); _uuid(body['clave_solicitud'])
                self._caso(body['caso'], body['expediente_sha256'])
                payload = _sha(_bytes(body))
                db.execute('BEGIN IMMEDIATE')
                existing = db.execute('SELECT * FROM trabajos WHERE caso=? AND clave=?', (body['caso'],body['clave_solicitud'])).fetchone()
                if existing:
                    if existing['payload'] != payload:
                        raise ErrorLecturas('clave_reutilizada_con_otros_datos')
                    record, state = json.loads(existing['registro']), existing['estado']
                    db.commit()  # la recuperación de huérfanos escribe con otra conexión
                    record, state = self._huerfano(record, state)
                    return self._publico(record, state)
                proof, folder, _ = self._fuentes(body)
                base = _seguro(folder/'trabajos_lecturas', falta=True); base.mkdir(exist_ok=True)
                ident = uuid4().hex; work = base/ident; work.mkdir()
                snapshot = _bytes(proof); manifest = _seguro(folder/'expediente.json').read_bytes()
                _nuevo(work/'evidencia_analisis.json', snapshot); _nuevo(work/'expediente.json', manifest)
                prep = {'id':ident, **body, 'sha256_evidencia':_sha(snapshot), 'sha256_expediente':_sha(manifest)}
                _nuevo(work/'preparacion.json', _bytes(prep))
                record = {key:body[key] for key in ('caso','analisis','expediente_sha256','tablas','casos')} | {
                    'id':ident, 'huella_preparacion':_sha(_bytes(prep)),
                    'datos_sinteticos':proof['datos_sinteticos'], 'modo_ejecucion':proof['modo'],
                    'sha256_edb':proof['sha256_edb_analizado'], **self._resultados_api(body)}
                self._revalidar(record)
                db.execute('INSERT INTO trabajos VALUES (?,?,?,?,?,?)',
                    (ident,body['caso'],body['clave_solicitud'],payload,'preparado',_bytes(record).decode()))
                return self._publico(record, 'preparado', comprobar=False)
        except ErrorEjecucion as error:
            raise ErrorLecturas(error.codigo) from None
        except (ValueError,OSError,RuntimeError,KeyError,TypeError,sqlite3.Error):
            raise ErrorLecturas('preparacion_rechazada') from None

    @staticmethod
    def _utc(value):
        if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,7})?(?:Z|\+00:00)',value):
            raise ErrorLecturas('fecha_lectura_invalida')
        # .NET emite hasta 7 decimales; Python 3.10 solo admite 3 o 6: se normaliza a 6 SOLO para validar (09d1, 7 decimales reales).
        normalizado = re.sub(r'\.(\d{1,7})(?=Z|\+00:00)', lambda m: '.' + m[1][:6].ljust(6, '0'), value)
        try:
            datetime.fromisoformat(normalizado.replace('Z','+00:00'))
        except ValueError:
            raise ErrorLecturas('fecha_lectura_invalida') from None

    def _paquete(self, record):
        proof, folder, analysis = self._revalidar(record)
        run = _seguro(_seguro(folder/'lecturas_etabs')/_uuid(record['lectura_id']))
        if (run/'lectura_no_aceptada.json').exists():
            raise ErrorLecturas('lectura_no_aceptada')
        names = ('solicitud.json','respuesta.json','aceptacion_lectura.json','evidencia_analisis.json')
        raw = {name:_seguro(run/name).read_bytes() for name in names}
        request, response, receipt, snapshot = (json.loads(raw[name]) for name in names)
        if not all(isinstance(v, dict) for v in (request,response,receipt,snapshot)):
            raise ErrorLecturas('lectura_no_verificable')
        expected_request = {'contrato':ad.CONTRATO_SOLICITUD,'version_contrato':ad.VERSION_CONTRATO,
            'id':run.name,'operacion':'leer_tablas','modo_configurado':proof['modo'],
            'corrida_analisis_id':record['analisis'],'modelo_esperado':str(analysis/'analizado.edb'),
            'sha256_edb':proof['sha256_edb_analizado'],'sha256_aceptacion_analisis':proof['sha256_aceptacion'],
            'version_etabs_esperada':proof['version_etabs'],'unidades_esperadas':UNIDADES,
            'tablas':record['tablas'],'casos':record['casos'],'combinaciones':[], **self._resultados_api(record)}
        expected_receipt = {'aceptada':True,'operacion':'leer_tablas','modo':proof['modo'],
            'lectura_id':run.name,'corrida_analisis_id':record['analisis'],
            'sha256_aceptacion_analisis':proof['sha256_aceptacion'],'sha256_edb':proof['sha256_edb_analizado'],
            'sha256_solicitud':_sha(raw['solicitud.json']),'sha256_respuesta':_sha(raw['respuesta.json']),
            'casos':record['casos'],'instancia_nueva_cerrada':True,'analisis_ejecutado':False,'aprueba_resultados':False}
        if (set(request) != set(expected_request)|{'dll'} or not isinstance(request.get('dll'),str)
                or any(request.get(k) != v for k,v in expected_request.items())
                or receipt != expected_receipt or any(receipt.get(k) is not v for k,v in
                    {'aceptada':True,'instancia_nueva_cerrada':True,'analisis_ejecutado':False,'aprueba_resultados':False}.items())
                or snapshot != proof or response.get('contrato') != ad.CONTRATO_RESPUESTA
                or response.get('version_contrato') != ad.VERSION_CONTRATO or response.get('id_solicitud') != run.name
                or response.get('operacion') != 'leer_tablas' or response.get('modo_ejecucion') != proof['modo']
                or response.get('estado') != 'ok' or not isinstance(response.get('datos'),dict)
                or not isinstance(response.get('avisos'),list)
                or not all(isinstance(v,str) and v.strip() for v in response['avisos'])):
            raise ErrorLecturas('lectura_no_verificable')
        self._utc(response.get('fin_utc'))
        data = response['datos']; states = data.get('estado_casos')
        expected_data = {'modelo':str(analysis/'analizado.edb'),'version_etabs':proof['version_etabs'],
            'unidades':UNIDADES,'casos':record['casos'],'combinaciones':[],
            'corrida_analisis_id':record['analisis'],'sha256_modelo_verificado':proof['sha256_edb_analizado'],
            'instancia':'nueva','instancia_cerrada':True,'analisis_ejecutado':False,'aprueba_resultados':False}
        if (any(data.get(k) != v for k,v in expected_data.items())
                or data.get('instancia_cerrada') is not True or data.get('analisis_ejecutado') is not False
                or data.get('aprueba_resultados') is not False or type(data.get('id_proceso')) is not int
                or data['id_proceso'] <= 0 or not isinstance(states,dict) or set(states) != set(record['casos'])
                or any(type(v) is not int or v != 4 for v in states.values())):
            raise ErrorLecturas('instancia_o_casos_no_verificables')
        self._utc(data.get('inicio_proceso_utc'))
        tables = data.get('tablas')
        if not isinstance(tables,list) or len(tables) != len(record['tablas']):
            raise ErrorLecturas('tablas_no_verificables')
        seen = set()
        for table in tables:
            if not isinstance(table,dict) or not isinstance(table.get('clave'),str) or table['clave'] not in record['tablas'] or table['clave'] in seen:
                raise ErrorLecturas('tablas_no_verificables')
            seen.add(table['clave']); fields = table.get('campos'); rows = table.get('filas')
            if (not isinstance(fields,list) or not fields or not all(isinstance(f,str) and f for f in fields)
                    or len(set(fields)) != len(fields) or not isinstance(rows,list)):
                raise ErrorLecturas('filas_no_verificables')
            field = 'OutputCase' if 'OutputCase' in fields else ('Case' if table['clave'] in TABLAS_CASE and 'Case' in fields else None)
            if field is None:
                raise ErrorLecturas('filas_no_verificables')
            for row in rows:
                if (not isinstance(row,dict) or set(row) != set(fields)
                        or any(v is not None and not isinstance(v,str) for v in row.values()) or row[field] not in record['casos']):
                    raise ErrorLecturas('filas_no_verificables')
        LectorAnalisis._comprobar_datos(SimpleNamespace(contenido=request), data)
        self._revalidar(record)
        if any(_seguro(run/name).read_bytes() != value for name,value in raw.items()):
            raise ErrorLecturas('lectura_cambio_durante_consulta')
        return raw, {key:data[key] for key in ('unidades','version_etabs','casos','estado_casos','tablas')} | ({'resultados_api':data['resultados_api']} if 'resultados_api' in data else {})

    def _aceptada(self, record):
        work = self._carpeta(record['caso'],record['id'])
        receipt_raw = _seguro(work/'aceptacion_web.json').read_bytes()
        if _sha(receipt_raw) != record['huella_aceptacion']:
            raise ErrorLecturas('aceptacion_web_alterada')
        receipt = json.loads(receipt_raw)
        raw, data = self._paquete(record)
        expected = {'lectura_id':record['lectura_id'],'archivos':{k:_sha(v) for k,v in raw.items()}}
        if receipt != expected or record['sha256_respuesta'] != _sha(raw['respuesta.json']):
            raise ErrorLecturas('aceptacion_web_alterada')
        if _seguro(work/'aceptacion_web.json').read_bytes() != receipt_raw:
            raise ErrorLecturas('aceptacion_web_alterada')
        return raw['respuesta.json'], data

    def _publico(self, record, state, *, comprobar=True):
        valid = True; data = None
        if comprobar:
            try:
                self._revalidar(record)
                if state == 'aceptado':
                    _, data = self._aceptada(record)
            except (ValueError,OSError,RuntimeError,KeyError,TypeError):
                valid = False
        return {k:record[k] for k in ('id','caso','analisis','expediente_sha256','huella_preparacion',
            'casos','tablas','datos_sinteticos','modo_ejecucion','sha256_edb')} | {
            'lectura_id':record.get('lectura_id'),'estado':state,'vigente':valid,
            'sha256_respuesta':record.get('sha256_respuesta'),
            'lectura_verificada':state == 'aceptado' and valid and data is not None,
            **self._resultados_api(record),
            'datos_tablas':({k:v for k,v in data.items() if k != 'resultados_api'} if data is not None else None),'analisis_ejecutado':False,'aprueba_resultados':False,
            'resultado_normalizado':False,'requiere_recuperacion':state == 'incierto',
            'problemas':[] if valid else ['entradas_o_evidencias_no_vigentes']}

    def _worker(self, record, lease):
        try:
            work = self._carpeta(record['caso'],record['id'])
            proof, folder, analysis = self._revalidar(record)
            base = _seguro(folder/'lecturas_etabs', falta=True); base.mkdir(exist_ok=True)
            reader = self._lector(base,self.motor_lock)
            if reader.config.modo != proof['modo'] or reader.config.bloqueo != self.motor_lock:
                raise ErrorLecturas('lector_no_comparte_control_motor')
            context = reader.preparar_lectura(self.app.raiz,record['caso'],analysis,
                tablas=record['tablas'],casos=record['casos'],**self._resultados_api(record))
            record = self._estado(record,'en_ejecucion',lectura_id=context.solicitud.id)
            self._revalidar(record)
            reader.ejecutar_lectura(context,confirmar_lectura=True)
            raw, _ = self._paquete(record)
            receipt = {'lectura_id':record['lectura_id'],'archivos':{k:_sha(v) for k,v in raw.items()}}
            _nuevo(work/'aceptacion_web.json',_bytes(receipt))
            record = {**record,'huella_aceptacion':_sha(_bytes(receipt)),
                'sha256_respuesta':_sha(raw['respuesta.json'])}
            self._aceptada(record)
            _nuevo(work/'estado_motor_resuelto.json',_seguro(self.pendiente).read_bytes())
            self.pendiente.unlink()
            self._estado(record,'aceptado')
        except Exception as error:
            if not self.pendiente.exists():
                _nuevo(self.pendiente,_bytes({'id':record['id'],'estado':'lectura_no_confirmada'}))
            try:
                _nuevo(self._carpeta(record['caso'],record['id'])/'error_worker.json',
                    _bytes({'tipo':type(error).__name__,'mensaje':str(error)}))
                self._estado(record,'incierto')
            except Exception:
                pass
        finally:
            lease.liberar()

    def captura_masa_para_informe(self, caso, trabajo, *, lectura_id, sha256_respuesta,
                                  analisis, sha256_edb, expediente_sha256):
        """Puente conservado y comprobado; no abre motor ni acepta rutas externas."""
        try:
            with self.app.lock:
                _uuid(trabajo); _uuid(lectura_id); _uuid(analisis)
                if any(not isinstance(v, str) or not re.fullmatch(r'[0-9a-f]{64}', v)
                       for v in (sha256_respuesta, sha256_edb, expediente_sha256)):
                    raise ErrorLecturas('referencia_masa_invalida')
                self._caso(caso, expediente_sha256)
                record, state = self._leer(caso, trabajo)
                expected = {'id':trabajo, 'caso':caso, 'lectura_id':lectura_id,
                    'sha256_respuesta':sha256_respuesta, 'analisis':analisis,
                    'sha256_edb':sha256_edb, 'expediente_sha256':expediente_sha256}
                if (state != 'aceptado' or any(record.get(k) != v for k,v in expected.items())
                        or record.get('modo_ejecucion') != 'real' or record.get('datos_sinteticos') is not False
                        or 'AssembledJointMass' not in self._resultados_api(record).get('resultados_api', [])):
                    raise ErrorLecturas('captura_masa_real_no_verificable')
                _, data = self._aceptada(record)
                proof, _, _ = self._revalidar(record)
                if (proof['modo'] != 'real' or proof['datos_sinteticos'] is not False
                        or proof['sha256_edb_analizado'] != sha256_edb):
                    raise ErrorLecturas('captura_masa_real_no_verificable')
                return {**({'configuracion_auto':data['resultados_api']['ConfiguracionAuto']} if 'ConfiguracionAuto' in data['resultados_api'] else {}),
                    'captura':data['resultados_api']['AssembledJointMass'],
                    'recibo':{'lectura_id':lectura_id, 'corrida_analisis_id':analisis,
                        'sha256_edb':sha256_edb, 'sha256_respuesta':sha256_respuesta, 'modo':'real'}}
        except ErrorEjecucion as error:
            raise ErrorLecturas(error.codigo) from None
        except (ValueError,OSError,RuntimeError,KeyError,TypeError,sqlite3.Error):
            raise ErrorLecturas('captura_masa_no_verificable') from None

    def respuesta_bytes(self, caso, trabajo, *, expediente_sha256):
        try:
            with self.app.lock:
                self._caso(caso,expediente_sha256)
                record, state = self._huerfano(*self._leer(caso,trabajo))
                if state != 'aceptado' or record['expediente_sha256'] != expediente_sha256:
                    raise ErrorLecturas('lectura_no_aceptada')
                return self._aceptada(record)[0]
        except ErrorEjecucion as error:
            raise ErrorLecturas(error.codigo) from None
        except (ValueError,OSError,RuntimeError,KeyError,TypeError,sqlite3.Error):
            raise ErrorLecturas('respuesta_no_verificable') from None

    def ejecutar(self, body):
        try:return super().ejecutar(body)
        except ErrorEjecucion as error:raise ErrorLecturas(error.codigo) from None

    def consultar(self, caso, trabajo):
        try:return super().consultar(caso,trabajo)
        except ErrorEjecucion as error:raise ErrorLecturas(error.codigo) from None

    def listar(self, caso):
        try:return super().listar(caso)
        except ErrorEjecucion as error:raise ErrorLecturas(error.codigo) from None
