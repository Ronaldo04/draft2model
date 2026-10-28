"""Análisis web deliberado desde modelo/aprobación propios; no normaliza resultados."""
import json
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

from . import adaptador_etabs as ad
from . import revision_modelo as rm
from .analisis_etabs import AnalizadorEtabs, SCRIPT
from .revision_ejecucion import ServicioEjecucion, ErrorEjecucion, _bytes, _sha, _seguro, _uuid, _nuevo


class ErrorAnalisis(ErrorEjecucion):
    """Código público constante, compatible con el manejador de ErrorEjecucion."""


class ServicioAnalisis(ServicioEjecucion):
    """Comparte control de trabajos con construcción, pero usa su propia base de filas."""
    def __init__(self, app, fabrica_analizador=None):
        self.app = app
        control = app.ejecucion
        self.base = control.base
        self.db = self.base/'analisis.sqlite3'
        self.lease = control.lease
        self.motor_lock = control.motor_lock
        self.pendiente = control.pendiente
        self._analyzer = fabrica_analizador or (lambda work, lock: AnalizadorEtabs(
            ad.ConfiguracionPuente.real(work, lock, timeout_s=900, script=SCRIPT)))
        self._fabrica_inyectada = fabrica_analizador is not None
        self._threads = {}
        with self._conexion() as db:
            db.execute('CREATE TABLE IF NOT EXISTS trabajos (id TEXT PRIMARY KEY, caso TEXT NOT NULL, clave TEXT NOT NULL, payload TEXT NOT NULL, estado TEXT NOT NULL, registro TEXT NOT NULL, UNIQUE(caso,clave))')
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS ejecucion_unica ON trabajos((1)) WHERE estado='en_ejecucion'")

    def _carpeta(self, caso, ident):
        folder, _, _ = self._caso(caso)
        return _seguro(_seguro(folder/'trabajos_analisis')/_uuid(ident))

    @staticmethod
    def _rutas_analisis(folder):
        candidates = [folder/'analisis_etabs'/('0'*32)/name
                      for name in ('solicitud.json','respuesta.json','entrada.edb','analizado.edb')]
        if os.name == 'nt' and any(len(str(path)) >= 260 for path in candidates):
            raise ErrorAnalisis('ruta_motor_demasiado_larga_use_raiz_mas_corta')

    def _fuentes(self, caso, modelo, aprobacion, fingerprint):
        _uuid(modelo); _uuid(aprobacion)
        folder, _, _ = self._caso(caso, fingerprint)
        projected = self.app.resultados.consultar_modelo(caso, modelo, expediente_sha256=fingerprint)
        try:
            checked = rm.consultar_aprobacion(self.app.raiz, caso, aprobacion)
        except AttributeError:
            raise ErrorAnalisis('aprobacion_no_vigente') from None
        if checked['modelo_id'] != modelo or checked['huella_modelo'] != projected['huella_modelo']:
            raise ErrorAnalisis('aprobacion_de_otro_modelo')
        self._rutas_analisis(folder)
        if not self._fabrica_inyectada and checked['origen']['modo'] != 'real':
            raise ErrorAnalisis('modelo_doble_no_ejecutable_real')
        if checked['origen']['modo'] == 'doble' and checked['origen']['datos_sinteticos'] is not True:
            raise ErrorAnalisis('doble_requiere_datos_sinteticos')
        model_dir = _seguro(_seguro(folder/'modelos_construidos')/modelo)
        approval_dir = _seguro(_seguro(folder/'aprobaciones_modelo')/aprobacion)
        sources = {'modelo.edb': _seguro(model_dir/'modelo.edb').read_bytes(),
                   'version_modelo.json': _seguro(model_dir/'version.json').read_bytes(),
                   'configuracion.json': _seguro(model_dir/'configuracion.json').read_bytes(),
                   'aprobacion.json': _seguro(approval_dir/'aprobacion.json').read_bytes(),
                   'expediente.json': _seguro(folder/'expediente.json').read_bytes()}
        if _sha(sources['modelo.edb']) != checked['origen']['sha256_modelo'] or _sha(sources['aprobacion.json']) != checked['sha256_aprobacion']:
            raise ErrorAnalisis('fuentes_cambiaron')
        config = json.loads(sources['configuracion.json'])
        cases = config['analisis']['casos_ejecutar']
        if not isinstance(cases, list) or not cases or not all(isinstance(c, str) and c for c in cases) or len(set(cases)) != len(cases):
            raise ErrorAnalisis('casos_invalidos')
        self._caso(caso, fingerprint)
        return checked, sources, cases

    def _revalidar(self, record):
        work = self._carpeta(record['caso'], record['id'])
        raw = _seguro(work/'preparacion.json').read_bytes()
        if _sha(raw) != record['huella_preparacion']:
            raise ErrorAnalisis('preparacion_alterada')
        prepared = json.loads(raw)
        for key in ('id','caso','modelo','aprobacion','expediente_sha256'):
            if prepared[key] != record[key]:
                raise ErrorAnalisis('preparacion_alterada')
        checked, sources, cases = self._fuentes(record['caso'], record['modelo'], record['aprobacion'], record['expediente_sha256'])
        if (checked['huella_modelo'] != record['huella_modelo']
                or checked['sha256_aprobacion'] != record['sha256_aprobacion'] or cases != record['casos']):
            raise ErrorAnalisis('fuentes_cambiaron')
        if set(prepared['snapshots']) != set(sources):
            raise ErrorAnalisis('snapshot_alterado')
        for name, data in sources.items():
            if _sha(data) != prepared['snapshots'][name] or _seguro(work/name).read_bytes() != data:
                raise ErrorAnalisis('snapshot_alterado')
        return checked

    def preparar(self, body):
        try:
            with self.app.lock, self._conexion() as db:
                if not isinstance(body, dict) or set(body) != {'caso','modelo','aprobacion','expediente_sha256','clave_solicitud'}:
                    raise ErrorAnalisis('campos_invalidos')
                for key in ('modelo','aprobacion','clave_solicitud'):
                    _uuid(body[key])
                folder, _, fingerprint = self._caso(body['caso'], body['expediente_sha256'])
                payload = _sha(_bytes(body))
                db.execute('BEGIN IMMEDIATE')
                existing = db.execute('SELECT * FROM trabajos WHERE caso=? AND clave=?', (body['caso'],body['clave_solicitud'])).fetchone()
                if existing:
                    if existing['payload'] != payload:
                        raise ErrorAnalisis('clave_reutilizada_con_otros_datos')
                    return self._publico(json.loads(existing['registro']), existing['estado'])
                checked, sources, cases = self._fuentes(body['caso'],body['modelo'],body['aprobacion'],fingerprint)
                base = _seguro(folder/'trabajos_analisis', falta=True);base.mkdir(exist_ok=True)
                ident = uuid4().hex;work = base/ident;work.mkdir()
                for name, data in sources.items():
                    _nuevo(work/name, data)
                preparation = {'id': ident, **body, 'snapshots': {name:_sha(data) for name,data in sources.items()}}
                _nuevo(work/'preparacion.json', _bytes(preparation))
                record = {'id': ident, 'caso': body['caso'], 'modelo': body['modelo'], 'aprobacion': body['aprobacion'],
                          'expediente_sha256': fingerprint, 'huella_preparacion': _sha(_bytes(preparation)),
                          'huella_modelo': checked['huella_modelo'], 'sha256_aprobacion': checked['sha256_aprobacion'],
                          'datos_sinteticos': checked['origen']['datos_sinteticos'], 'casos': cases}
                self._revalidar(record)
                db.execute('INSERT INTO trabajos VALUES (?,?,?,?,?,?)',
                           (ident,body['caso'],body['clave_solicitud'],payload,'preparado',_bytes(record).decode()))
                return self._publico(record,'preparado',comprobar=False)
        except ErrorEjecucion as error:
            raise ErrorAnalisis(error.codigo) from None
        except (ValueError,OSError,RuntimeError,KeyError,TypeError,sqlite3.Error):
            raise ErrorAnalisis('preparacion_rechazada') from None

    def _recibo(self, record):
        work = self._carpeta(record['caso'], record['id'])
        receipt_raw = _seguro(work/'aceptacion_web.json').read_bytes()
        if _sha(receipt_raw) != record['huella_aceptacion']:
            raise ErrorAnalisis('aceptacion_web_alterada')
        receipt = json.loads(receipt_raw)
        run = _seguro(_seguro(work.parent.parent/'analisis_etabs')/_uuid(record['corrida_id']))
        names = {'solicitud.json','respuesta.json','aceptacion_analisis.json','entrada.edb','analizado.edb'}
        if (not isinstance(receipt,dict) or not isinstance(receipt.get('archivos'),dict)
                or set(receipt['archivos']) != names or receipt.get('corrida_id') != record['corrida_id']):
            raise ErrorAnalisis('aceptacion_web_alterada')
        for name, digest in receipt['archivos'].items():
            if _sha(_seguro(run/name).read_bytes()) != digest:
                raise ErrorAnalisis('analisis_alterado')
        return receipt

    def _verificar_salida(self, record, run):
        _uuid(run.name)
        if run.parent != self._carpeta(record['caso'],record['id']).parent.parent/'analisis_etabs':
            raise ErrorAnalisis('corrida_fuera_del_caso')
        if (run/'analisis_no_aceptado.json').exists():
            raise ErrorAnalisis('analisis_no_aceptado')
        raw = {name:_seguro(run/name).read_bytes() for name in
               ('solicitud.json','respuesta.json','aceptacion_analisis.json','entrada.edb','analizado.edb')}
        request, response, acceptance = (json.loads(raw[name]) for name in
                                      ('solicitud.json','respuesta.json','aceptacion_analisis.json'))
        acceptance_fields = {'aceptada','modo','modelo_id','huella_modelo','aprobacion_id','sha256_aprobacion',
                             'datos_sinteticos','guardado','casos_ejecutados','estados_casos',
                             'analisis_ejecutado','aprueba_resultados','fecha_utc'}
        if (not all(isinstance(value,dict) for value in (request,response,acceptance))
                or set(acceptance) != acceptance_fields or not isinstance(response.get('datos'),dict)):
            raise ErrorAnalisis('aceptacion_no_verificable')
        expected = self._revalidar(record)
        cases = record['casos'];states = {name:4 for name in cases}
        identity = {'modelo_id': record['modelo'], 'huella_modelo': record['huella_modelo'],
                    'aprobacion_id': record['aprobacion'], 'sha256_aprobacion': record['sha256_aprobacion'],
                    'datos_sinteticos': record['datos_sinteticos']}
        mode = expected['origen']['modo']
        saved = {'ruta':str(run/'analizado.edb'),'sha256':_sha(raw['analizado.edb'])}
        data = response['datos']
        for state in (acceptance.get('estados_casos'),data.get('estados_casos')):
            if not isinstance(state,dict) or set(state) != set(cases) or any(type(v) is not int or v != 4 for v in state.values()):
                raise ErrorAnalisis('casos_no_terminados')
        if (request.get('contrato') != ad.CONTRATO_SOLICITUD or request.get('version_contrato') != ad.VERSION_CONTRATO
                or response.get('contrato') != ad.CONTRATO_RESPUESTA or response.get('version_contrato') != ad.VERSION_CONTRATO
                or request.get('datos_sinteticos') is not record['datos_sinteticos']
                or acceptance.get('datos_sinteticos') is not record['datos_sinteticos']
                or request.get('id') != run.name or request.get('operacion') != 'analizar_modelo'
                or request.get('modo_configurado') != mode or request.get('casos') != cases
                or request.get('entrada') != str(run/'entrada.edb') or request.get('destino') != saved['ruta']
                or request.get('sha256_entrada') != _sha(raw['entrada.edb'])
                or _sha(raw['entrada.edb']) != expected['origen']['sha256_modelo']
                or any(request.get(k) != v or acceptance.get(k) != v for k,v in identity.items())
                or acceptance.get('aceptada') is not True or acceptance.get('modo') != mode
                or acceptance.get('guardado') != saved or acceptance.get('casos_ejecutados') != cases
                or acceptance.get('estados_casos') != states or acceptance.get('analisis_ejecutado') is not True
                or acceptance.get('aprueba_resultados') is not False
                or response.get('estado') != 'ok' or response.get('id_solicitud') != run.name
                or response.get('operacion') != 'analizar_modelo' or response.get('modo_ejecucion') != mode
                or data.get('guardado') != saved or data.get('casos_ejecutados') != cases
                or data.get('estados_casos') != states or data.get('sha256_entrada') != request.get('sha256_entrada')
                or data.get('analisis_ejecutado') is not True or data.get('aprueba_resultados') is not False
                or not isinstance(data.get('version_etabs'),str) or not data['version_etabs']):
            raise ErrorAnalisis('aceptacion_no_verificable')
        return {'corrida_id':run.name,'archivos':{name:_sha(content) for name,content in raw.items()},
                'casos':cases,'estados_casos':states,'modo_ejecucion':mode}

    def _publico(self, record, state, *, comprobar=True):
        valid = True
        if comprobar:
            try:
                self._revalidar(record)
                if state == 'aceptado':
                    receipt = self._recibo(record)
                    run = self._carpeta(record['caso'],record['id']).parent.parent/'analisis_etabs'/record['corrida_id']
                    if self._verificar_salida(record,run) != receipt:
                        raise ErrorAnalisis('aceptacion_web_alterada')
            except (ValueError,OSError,RuntimeError,KeyError,TypeError):
                valid = False
        return {key:record[key] for key in ('id','caso','modelo','aprobacion','expediente_sha256',
            'huella_preparacion','huella_modelo','sha256_aprobacion','datos_sinteticos','casos')} | {
            'estado':state,'vigente':valid,'corrida_id':record.get('corrida_id'),
            'estados_casos':record.get('estados_casos',{}),'modo_ejecucion':record.get('modo_ejecucion'),
            'analisis_ejecutado':state=='aceptado','calculo_verificado':state=='aceptado' and valid,
            'resultado_normalizado':False,'aprueba_resultados':False,'revision_resultados':'pendiente',
            'conformidad_normativa':'no_evaluada','requiere_recuperacion':state=='incierto',
            'problemas':[] if valid else ['entradas_o_evidencias_no_vigentes']}

    def _worker(self, record, lease):
        try:
            work = self._carpeta(record['caso'],record['id'])
            expected = self._revalidar(record)
            run_base = _seguro(work.parent.parent/'analisis_etabs',falta=True);run_base.mkdir(exist_ok=True)
            _seguro(self.motor_lock,falta=True)
            analyzer = self._analyzer(run_base,self.motor_lock)
            if analyzer.config.modo != expected['origen']['modo']:
                raise ErrorAnalisis('modo_incoherente')
            prepared = analyzer.preparar_analisis(self.app.raiz,record['caso'],record['aprobacion'])
            record = self._estado(record,'en_ejecucion',corrida_id=prepared.solicitud.id)
            self._revalidar(record)
            analyzer.ejecutar_analisis(prepared,confirmar_analisis=True)
            receipt = self._verificar_salida(record,prepared.solicitud.carpeta)
            _nuevo(work/'aceptacion_web.json',_bytes(receipt))
            self._revalidar(record)
            _nuevo(work/'estado_motor_resuelto.json',_seguro(self.pendiente).read_bytes())
            self.pendiente.unlink()
            self._estado(record,'aceptado',corrida_id=receipt['corrida_id'],
                huella_aceptacion=_sha(_bytes(receipt)),estados_casos=receipt['estados_casos'],
                modo_ejecucion=receipt['modo_ejecucion'])
        except Exception as error:
            if not self.pendiente.exists():
                _nuevo(self.pendiente,_bytes({'id':record['id'],'estado':'analisis_no_confirmado'}))
            try:
                _nuevo(self._carpeta(record['caso'],record['id'])/'error_worker.json',
                       _bytes({'tipo':type(error).__name__,'mensaje':str(error)}))
                self._estado(record,'incierto')
            except Exception:
                pass
        finally:
            lease.liberar()

    def ejecutar(self, body):
        try:
            return super().ejecutar(body)
        except ErrorEjecucion as error:
            raise ErrorAnalisis(error.codigo) from None

    def consultar(self, caso, trabajo):
        try:
            return super().consultar(caso,trabajo)
        except ErrorEjecucion as error:
            raise ErrorAnalisis(error.codigo) from None

    def listar(self, caso):
        try:
            return super().listar(caso)
        except ErrorEjecucion as error:
            raise ErrorAnalisis(error.codigo) from None
