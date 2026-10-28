"""Relectura web deliberada del snapshot registrado; nunca aprueba ni analiza."""
import json
import os
import sqlite3
from uuid import uuid4

from . import vinculo_verificacion_modelo as vinculo
from . import verificacion_modelo_guardado as lector
from .revision_ejecucion import ServicioEjecucion, ErrorEjecucion, _bytes, _sha, _seguro, _uuid, _nuevo


class ServicioVerificacionModelo(ServicioEjecucion):
    def __init__(self, app, fabrica_verificador=None):
        self.app = app
        control = app.ejecucion
        self.base, self.lease = control.base, control.lease
        self.motor_lock, self.pendiente = control.motor_lock, control.pendiente
        self.db = self.base/'verificaciones_modelo.sqlite3'
        self._fabrica = fabrica_verificador or (lambda work, lock: lector.VerificadorModeloGuardado(lector.configuracion_real(work, lock)))
        self._inyectada = fabrica_verificador is not None
        self._threads = {}
        with self._conexion() as db:
            db.execute('CREATE TABLE IF NOT EXISTS trabajos (id TEXT PRIMARY KEY, caso TEXT NOT NULL, clave TEXT NOT NULL, payload TEXT NOT NULL, estado TEXT NOT NULL, registro TEXT NOT NULL, UNIQUE(caso,clave))')
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS ejecucion_unica ON trabajos((1)) WHERE estado='en_ejecucion'")

    def _carpeta(self, caso, ident):
        folder, _, _ = self._caso(caso)
        return _seguro(_seguro(folder/'trabajos_verificacion_modelo')/_uuid(ident))

    def _fuentes(self, record):
        folder, _, _ = self._caso(record['caso'], record['expediente_sha256'])
        _uuid(record['modelo'])
        state, plan, edb = vinculo._fuente(self.app.raiz, record['caso'], record['modelo'], record['huella_modelo'])
        origin = state['origen']
        if origin['modo'] != 'real' and not self._inyectada:
            raise ErrorEjecucion('modelo_doble_no_ejecutable_real')
        if origin['modo'] == 'doble' and origin['datos_sinteticos'] is not True:
            raise ErrorEjecucion('doble_requiere_datos_sinteticos')
        lector.validar_criterios(record['criterios'])
        expectation = lector.expectativa_desde_plan(plan, ejes_locales_area=record['ejes_locales_area'])
        if os.name == 'nt' and len(str(folder/'motor_vm'/('0'*32)/'solicitud.json')) >= 260:
            raise ErrorEjecucion('ruta_motor_demasiado_larga_use_raiz_mas_corta')
        return folder, state, plan, expectation

    def _revalidar(self, record):
        folder, state, plan, expectation = self._fuentes(record)
        work = self._carpeta(record['caso'], record['id'])
        raw = _seguro(work/'preparacion.json').read_bytes()
        if _sha(raw) != record['huella_preparacion']:
            raise ErrorEjecucion('preparacion_alterada')
        prepared = json.loads(raw)
        if any(prepared.get(k) != record[k] for k in ('id','caso','modelo','huella_modelo','expediente_sha256','criterios','ejes_locales_area')):
            raise ErrorEjecucion('preparacion_alterada')
        snapshots = {'origen.json':_bytes(state['origen']), 'plan.json':_bytes(plan),
                     'expectativa.json':_bytes(expectation), 'expediente.json':_seguro(folder/'expediente.json').read_bytes()}
        if prepared.get('snapshots') != {n:_sha(v) for n,v in snapshots.items()}:
            raise ErrorEjecucion('fuentes_cambiaron')
        if any(_seguro(work/n).read_bytes() != raw for n,raw in snapshots.items()):
            raise ErrorEjecucion('snapshot_alterado')
        return folder, state

    def preparar(self, body):
        try:
            with self.app.lock, self._conexion() as db:
                if not isinstance(body, dict) or set(body) != {'caso','modelo','huella_modelo','expediente_sha256','clave_solicitud','criterios','ejes_locales_area'}:
                    raise ErrorEjecucion('campos_invalidos')
                _uuid(body['clave_solicitud']); self._caso(body['caso'],body['expediente_sha256'])
                payload = _sha(_bytes(body)); db.execute('BEGIN IMMEDIATE')
                existing = db.execute('SELECT * FROM trabajos WHERE caso=? AND clave=?',(body['caso'],body['clave_solicitud'])).fetchone()
                if existing:
                    if existing['payload'] != payload:
                        raise ErrorEjecucion('clave_reutilizada_con_otros_datos')
                    record, state = json.loads(existing['registro']), existing['estado']; db.commit()
                    return self._publico(*self._huerfano(record,state))
                folder, state, plan, expectation = self._fuentes(body)
                base = _seguro(folder/'trabajos_verificacion_modelo',falta=True); base.mkdir(exist_ok=True)
                ident = uuid4().hex; work=base/ident; work.mkdir()
                snapshots={'origen.json':_bytes(state['origen']), 'plan.json':_bytes(plan),
                           'expectativa.json':_bytes(expectation),'expediente.json':_seguro(folder/'expediente.json').read_bytes()}
                for name,raw in snapshots.items(): _nuevo(work/name,raw)
                prep={'id':ident,**body,'snapshots':{n:_sha(raw) for n,raw in snapshots.items()}}
                _nuevo(work/'preparacion.json',_bytes(prep))
                record={k:v for k,v in body.items() if k!='clave_solicitud'} | {'id':ident,
                    'huella_preparacion':_sha(_bytes(prep)), 'modo_ejecucion':state['origen']['modo'],
                    'datos_sinteticos':state['origen']['datos_sinteticos'],'sha256_edb':state['origen']['sha256_modelo']}
                self._revalidar(record)
                db.execute('INSERT INTO trabajos VALUES (?,?,?,?,?,?)',(ident,body['caso'],body['clave_solicitud'],payload,'preparado',_bytes(record).decode()))
                return self._publico(record,'preparado',comprobar=False)
        except ErrorEjecucion: raise
        except (ValueError,OSError,RuntimeError,KeyError,TypeError,sqlite3.Error):
            raise ErrorEjecucion('preparacion_rechazada') from None

    def _resultado(self, record):
        self._revalidar(record)
        proof=vinculo.consultar(self.app.raiz,record['caso'],record['verificacion_id'])
        target=vinculo.modelos._folder(self.app.raiz,record['caso'],'verificaciones_modelo',record['verificacion_id'])
        criteria=json.loads(vinculo.modelos._leer(target/'criterios.json'))
        expectation=json.loads(vinculo.modelos._leer(target/'expectativa.json'))
        if criteria != record['criterios'] or expectation.get('ejes_locales_area') != record['ejes_locales_area']:
            raise ErrorEjecucion('criterios_de_otra_verificacion')
        if proof['modelo'] != record['modelo'] or proof['huella_modelo'] != record['huella_modelo'] or proof['sha256_registro'] != record['sha256_registro']:
            raise ErrorEjecucion('verificacion_ajena')
        return proof['resultado']

    def _publico(self, record, state, *, comprobar=True):
        valid=True; result=None
        if comprobar:
            try:
                self._revalidar(record)
                if state=='aceptado': result=self._resultado(record)
            except (ValueError,OSError,RuntimeError,KeyError,TypeError): valid=False
        return {k:record[k] for k in ('id','caso','modelo','huella_modelo','expediente_sha256','huella_preparacion','modo_ejecucion','datos_sinteticos','sha256_edb','criterios','ejes_locales_area')} | {
            'estado':state,'vigente':valid,'verificacion_id':record.get('verificacion_id'),'sha256_registro':record.get('sha256_registro'),
            'lectura_comprobada':state=='aceptado' and valid and result is not None,
            'resultado':result,'aprueba_modelo':False,'autoriza_analisis':False,
            'requiere_recuperacion':state=='incierto','problemas':[] if valid else ['entradas_o_evidencias_no_vigentes']}

    def _worker(self, record, lease):
        try:
            folder,state=self._revalidar(record)
            work=_seguro(folder/'motor_vm',falta=True); work.mkdir(exist_ok=True)
            verifier=self._fabrica(work,self.motor_lock)
            if verifier.config.modo != state['origen']['modo'] or verifier.config.bloqueo != self.motor_lock:
                raise ErrorEjecucion('lector_no_comparte_control_motor')
            target=vinculo.verificar(self.app.raiz,record['caso'],record['modelo'],huella_modelo=record['huella_modelo'],
                verificador=verifier,criterios=record['criterios'],ejes_locales_area=record['ejes_locales_area'],confirmar_lectura=True)
            proof=vinculo.consultar(self.app.raiz,record['caso'],target.name)
            record={**record,'verificacion_id':target.name,'sha256_registro':proof['sha256_registro']}
            self._resultado(record)
            _nuevo(self._carpeta(record['caso'],record['id'])/'estado_motor_resuelto.json',_seguro(self.pendiente).read_bytes())
            self.pendiente.unlink(); self._estado(record,'aceptado')
        except Exception as error:
            try:
                if not self.pendiente.exists(): _nuevo(self.pendiente,_bytes({'id':record['id'],'estado':'lectura_no_confirmada'}))
                _nuevo(self._carpeta(record['caso'],record['id'])/'error_worker.json',_bytes({'tipo':type(error).__name__,'mensaje':str(error)}))
                self._estado(record,'incierto')
            except Exception: pass
        finally: lease.liberar()
