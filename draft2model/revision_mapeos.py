"""Correspondencias versionadas y normalización offline ligada a un análisis."""
import copy
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4
from .adaptador_etabs import BloqueoExclusivo
from .evidencia_analisis import verificar_analisis_aceptado, verificar_evidencia
from .gestion_extraccion import _publicar, json_desde_bytes
from .normalizacion_etabs import previsualizar_resultados, registrar_resultados
from .resultados_estructurales import huella_declaracion, aprobacion_vigente
from .normalizacion_web import pendientes, candidatos, anteriores


def _bytes(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False,indent=2)+'\n').encode('utf-8')
def _sha(raw):return hashlib.sha256(raw).hexdigest()
def _id(value):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{32}',value):raise ValueError('Identificador inválido.')
    return value
def _leer(path):
    if path.resolve()!=path or not path.is_file():raise ValueError('Archivo ausente o enlazado.')
    return path.read_bytes()
def _json(raw):return json_desde_bytes(raw,'correspondencias')


class ErrorNormalizacionPendiente(ValueError):
    pass


def _confirmar(path,raw,*,conservar_anterior=False):
    temp=path.parent/('.recibo-'+uuid4().hex)
    with temp.open('xb') as output:output.write(raw)
    if path.exists():
        if not conservar_anterior:raise ValueError('Recibo existente; no se sobrescribe.')
        _leer(path)
        path.rename(path.parent/('aceptacion_no_vigente_'+uuid4().hex+'.json'))
    temp.rename(path)


class ServicioMapeos:
    def __init__(self,app):self.app=app

    def fuente(self,caso,analisis,*,expediente_sha256):
        with self.app.lock:
            return self._fuentes(caso,analisis,expediente_sha256)[1]

    def _caso(self,caso,fingerprint):
        folder,_,actual=self.app.expediente(caso)
        if fingerprint!=actual:raise ValueError('Expediente cambiado.')
        if folder.resolve()!=folder:raise ValueError('Expediente enlazado.')
        return folder

    def _fuentes(self,caso,analisis,fingerprint):
        folder=self._caso(caso,fingerprint);run=folder/'analisis_etabs'/_id(analisis)
        proof=verificar_analisis_aceptado(self.app.raiz,caso,run)
        config=_leer(folder/'modelos_construidos'/proof['modelo_id']/'configuracion.json')
        return folder,proof,config

    def _verificar(self,caso,analisis,fingerprint,config_raw,response_raw,mapping):
        folder,proof,config=self._fuentes(caso,analisis,fingerprint)
        if config!=config_raw:raise ValueError('Configuración distinta del modelo analizado.')
        expected={'archivo':'analisis_etabs/'+analisis+'/analizado.edb','sha256':proof['sha256_edb_analizado']}
        if not isinstance(mapping,dict) or mapping.get('modelo')!=expected:
            raise ValueError('El mapeo debe citar el EDB analizado del expediente.')
        raw=_json(response_raw);data=raw.get('datos') if isinstance(raw,dict) else None
        if (not isinstance(data,dict) or raw.get('modo_ejecucion')!=proof['modo']
                or data.get('version_etabs')!=proof['version_etabs']
                or not isinstance(data.get('casos'),list) or not data['casos']
                or not all(isinstance(c,str) and c for c in data['casos'])
                or len(data['casos'])!=len(set(data['casos']))
                or not set(data['casos'])<=set(proof['casos'])
                or not isinstance(data.get('estado_casos'),dict)
                or any(type(data['estado_casos'].get(c)) is not int or data['estado_casos'][c]!=4 for c in data['casos'])
                or data.get('combinaciones') or data.get('modelo')!=str(folder/expected['archivo'])):
            raise ValueError('Lectura incompatible con el análisis seleccionado.')
        return proof

    def _lectura(self,caso,analisis,fingerprint,response,origin):
        if origin is None:return
        if not isinstance(origin,dict) or set(origin)!={'trabajo','lectura_id','sha256_respuesta'}:
            raise ValueError('Procedencia de lectura inválida.')
        job=self.app.lecturas.consultar(caso,_id(origin['trabajo']))
        if (job['estado']!='aceptado' or job['vigente'] is not True or job['lectura_verificada'] is not True
                or job['analisis']!=analisis or job['expediente_sha256']!=fingerprint
                or job['lectura_id']!=origin['lectura_id'] or job['sha256_respuesta']!=origin['sha256_respuesta']
                or _sha(response)!=origin['sha256_respuesta']
                or self.app.lecturas.respuesta_bytes(caso,job['id'],expediente_sha256=fingerprint)!=response):
            raise ValueError('Lectura nativa sin evidencia vigente.')

    def _publicar(self,caso,analisis,fingerprint,config,response,mapping,parent=None,lectura=None):
        proof=self._verificar(caso,analisis,fingerprint,config,response,mapping)
        self._lectura(caso,analisis,fingerprint,response,lectura)
        folder=self._caso(caso,fingerprint);ident=uuid4().hex
        files={'configuracion.json':config,'respuesta.json':response,'mapeo.json':_bytes(mapping)}
        # Comprobar desde snapshots antes de publicar el paquete visible.
        import tempfile
        with tempfile.TemporaryDirectory(prefix='.mapeo-',dir=folder) as temp:
            stage=Path(temp).resolve()
            for name,raw in files.items():(stage/name).write_bytes(raw)
            previsualizar_resultados(self.app.raiz,stage/'configuracion.json',stage/'respuesta.json',stage/'mapeo.json')
        if self._verificar(caso,analisis,fingerprint,config,response,mapping)!=proof:raise ValueError('Fuentes cambiadas.')
        meta={'tipo':'draft2model.mapeo_versionado','version':'0.1.0','id':ident,'caso':caso,
              'analisis':analisis,'padre':parent,'expediente_sha256':fingerprint,'lectura':lectura,
              'creado_utc':datetime.now(timezone.utc).isoformat(),
              'archivos':{name:_sha(raw) for name,raw in files.items()}}
        _publicar(folder,'mapeos_resultados',ident,{**files,'version.json':_bytes(meta)})
        return self.consultar(caso,ident,expediente_sha256=fingerprint)

    def _cargar(self,caso,version,fingerprint,seen=None):
        seen=set() if seen is None else seen
        _id(version)
        if version in seen:raise ValueError('Cadena circular de mapeos.')
        seen.add(_id(version));folder=self._caso(caso,fingerprint)/'mapeos_resultados'/version
        meta_raw=_leer(folder/'version.json');meta=_json(meta_raw)
        fields={'tipo','version','id','caso','analisis','padre','expediente_sha256','creado_utc','archivos'}
        if (not isinstance(meta,dict) or set(meta) not in (fields,fields|{'lectura'}) or meta['tipo']!='draft2model.mapeo_versionado'
                or meta['version']!='0.1.0' or meta['id']!=version or meta['caso']!=caso
                or meta['expediente_sha256']!=fingerprint or not isinstance(meta['archivos'],dict)
                or set(meta['archivos'])!={'configuracion.json','respuesta.json','mapeo.json'}):raise ValueError('Versión inválida.')
        files={name:_leer(folder/name) for name in meta['archivos']}
        if any(_sha(raw)!=meta['archivos'][name] for name,raw in files.items()):raise ValueError('Mapeo alterado.')
        mapping=_json(files['mapeo.json'])
        self._lectura(caso,meta['analisis'],fingerprint,files['respuesta.json'],meta.get('lectura'))
        proof=self._verificar(caso,meta['analisis'],fingerprint,files['configuracion.json'],files['respuesta.json'],mapping)
        if meta['padre'] is not None:
            parent,previous,old_files,_,_=self._cargar(caso,meta['padre'],fingerprint,seen)
            if parent['analisis']!=meta['analisis'] or parent.get('lectura')!=meta.get('lectura') or any(old_files[n]!=files[n] for n in ('configuracion.json','respuesta.json')):
                raise ValueError('La revisión cambió sus fuentes.')
            if aprobacion_vigente(mapping) and huella_declaracion(mapping)!=huella_declaracion(previous):
                raise ValueError('Aprobación distinta del contenido padre.')
        preview=previsualizar_resultados(self.app.raiz,folder/'configuracion.json',folder/'respuesta.json',folder/'mapeo.json')
        if self._verificar(caso,meta['analisis'],fingerprint,files['configuracion.json'],files['respuesta.json'],mapping)!=proof:
            raise ValueError('Las fuentes cambiaron durante la consulta.')
        if _leer(folder/'version.json')!=meta_raw or any(_leer(folder/name)!=raw for name,raw in files.items()):
            raise ValueError('La versión cambió durante la previsualización.')
        self._lectura(caso,meta['analisis'],fingerprint,files['respuesta.json'],meta.get('lectura'))
        return meta,mapping,files,preview,proof

    def consultar(self,caso,version,*,expediente_sha256):
        with self.app.lock:
            meta,mapping,_,preview,proof=self._cargar(caso,version,expediente_sha256)
            return {'id':version,'caso':caso,'analisis':meta['analisis'],'padre':meta['padre'],
                    'expediente_sha256':expediente_sha256,'huella_mapeo':huella_declaracion(mapping),
                    'mapeo':mapping,'previsualizacion':preview,'analisis_verificado':proof,
                    'lectura':'lectura_aceptada_verificada' if meta.get('lectura') else 'respuesta_conservada_declarada',
                    'procedencia_lectura':meta.get('lectura'),'aprueba_resultados':False}

    def listar(self,caso,*,expediente_sha256):
        with self.app.lock:
            base=self._caso(caso,expediente_sha256)/'mapeos_resultados'
            if base.resolve()!=base:raise ValueError('Directorio enlazado.')
            rows=[]
            for path in sorted(base.iterdir()) if base.is_dir() else []:
                if not re.fullmatch('[0-9a-f]{32}',path.name):continue
                try:
                    item=self.consultar(caso,path.name,expediente_sha256=expediente_sha256)
                    rows.append({'id':path.name,'analisis':item['analisis'],'vigente':True,'estado':item['mapeo']['revision']['estado']})
                except (ValueError,OSError,KeyError,TypeError):rows.append({'id':path.name,'vigente':False})
            self._caso(caso,expediente_sha256)
            return {'versiones':rows}

    def importar(self,body):
        if not isinstance(body,dict) or set(body)!={'caso','analisis','expediente_sha256','respuesta_json','mapeo_json'}:
            raise ValueError('Campos incompletos de mapeo.')
        with self.app.lock:
            if not all(isinstance(body[k],str) for k in ('respuesta_json','mapeo_json')):raise ValueError('Se requiere JSON completo.')
            mapping=_json(body['mapeo_json'].encode('utf-8'))
            if not isinstance(mapping,dict) or mapping.get('revision')!={'estado':'borrador','aprobacion':None}:raise ValueError('Importa un borrador sin aprobación.')
            _,_,config=self._fuentes(body['caso'],body['analisis'],body['expediente_sha256'])
            return self._publicar(body['caso'],body['analisis'],body['expediente_sha256'],config,
                                  body['respuesta_json'].encode('utf-8'),mapping)

    def importar_lectura(self,body):
        if not isinstance(body,dict) or set(body)!={'caso','trabajo_lectura','expediente_sha256','mapeo_json'}:
            raise ValueError('Campos incompletos de lectura.')
        with self.app.lock:
            caso,fp=body['caso'],body['expediente_sha256']
            job=self.app.lecturas.consultar(caso,_id(body['trabajo_lectura']))
            response=self.app.lecturas.respuesta_bytes(caso,job['id'],expediente_sha256=fp)
            origin={'trabajo':job['id'],'lectura_id':job['lectura_id'],'sha256_respuesta':job['sha256_respuesta']}
            self._lectura(caso,job['analisis'],fp,response,origin)
            if not isinstance(body['mapeo_json'],str):raise ValueError('Se requiere JSON completo.')
            mapping=_json(body['mapeo_json'].encode('utf-8'))
            if not isinstance(mapping,dict) or mapping.get('revision')!={'estado':'borrador','aprobacion':None}:
                raise ValueError('Importa un borrador sin aprobación.')
            _,_,config=self._fuentes(caso,job['analisis'],fp)
            return self._publicar(caso,job['analisis'],fp,config,response,mapping,lectura=origin)

    def revisar(self,body):
        if not isinstance(body,dict) or set(body)!={'caso','version','expediente_sha256','huella_mapeo','mapeo_json'}:raise ValueError('Campos incompletos.')
        with self.app.lock:
            meta,previous,files,_,_=self._cargar(body['caso'],body['version'],body['expediente_sha256'])
            if huella_declaracion(previous)!=body['huella_mapeo']:raise ValueError('Mapeo cambiado.')
            if not isinstance(body['mapeo_json'],str):raise ValueError('Se requiere JSON completo.')
            mapping=_json(body['mapeo_json'].encode('utf-8'))
            if not isinstance(mapping,dict) or mapping.get('revision')!={'estado':'borrador','aprobacion':None}:raise ValueError('La revisión debe ser borrador.')
            return self._publicar(body['caso'],meta['analisis'],body['expediente_sha256'],files['configuracion.json'],files['respuesta.json'],mapping,body['version'],meta.get('lectura'))

    def aprobar(self,body):
        fields={'caso','version','expediente_sha256','huella_mapeo','revisor','fecha','motivo','alcance','confirmacion_explicita'}
        if not isinstance(body,dict) or set(body)!=fields or body['confirmacion_explicita'] is not True:raise ValueError('Aprobación explícita requerida.')
        with self.app.lock:
            meta,mapping,files,_,_=self._cargar(body['caso'],body['version'],body['expediente_sha256'])
            if mapping['revision']!={'estado':'borrador','aprobacion':None} or huella_declaracion(mapping)!=body['huella_mapeo']:
                raise ValueError('Revisa un borrador y su huella vigente.')
            if not all(isinstance(body[k],str) and body[k].strip() for k in ('revisor','fecha','motivo','alcance')):raise ValueError('Declaración incompleta.')
            if date.fromisoformat(body['fecha']).isoformat()!=body['fecha']:raise ValueError('Fecha inválida.')
            approved=copy.deepcopy(mapping)
            approved['revision']={'estado':'aprobado','aprobacion':{'revisor_declarado':body['revisor'],'fecha':body['fecha'],
                'motivo':body['motivo'],'alcance':body['alcance'],'huella_contenido':huella_declaracion(mapping)}}
            return self._publicar(body['caso'],meta['analisis'],body['expediente_sha256'],files['configuracion.json'],files['respuesta.json'],approved,body['version'],meta.get('lectura'))

    def normalizar(self,body):
        fields={'caso','version','expediente_sha256','huella_mapeo','clave_solicitud','confirmacion_explicita'}
        if not isinstance(body,dict) or set(body)!=fields or body['confirmacion_explicita'] is not True:raise ValueError('Confirma la normalización explícitamente.')
        with self.app.lock:
            case=self._caso(body['caso'],body['expediente_sha256']);key=_id(body['clave_solicitud'])
            lock=case/'normalizacion.lock'
            if lock.resolve()!=lock:raise ValueError('Bloqueo enlazado.')
            with BloqueoExclusivo(lock):
                meta,mapping,snapshots,_,_=self._cargar(body['caso'],body['version'],body['expediente_sha256'])
                if huella_declaracion(mapping)!=body['huella_mapeo'] or not aprobacion_vigente(mapping):raise ValueError('Mapeo sin aprobación vigente.')
                payload=_bytes(body);operation=case/'normalizaciones_resultados'/key
                if operation.exists():
                    if _leer(operation/'solicitud.json')!=payload:raise ValueError('Clave usada para otras entradas.')
                    if not (operation/'aceptacion.json').exists():raise ErrorNormalizacionPendiente('Normalización pendiente de recuperación.')
                    receipt=_json(_leer(operation/'aceptacion.json'))
                    expected={'resultado','mapeo_version','huella_mapeo','evidencia_analisis','aprueba_resultados','conformidad_normativa'}
                    if (not isinstance(receipt,dict) or set(receipt)!=expected or receipt['mapeo_version']!=body['version']
                            or receipt['huella_mapeo']!=body['huella_mapeo'] or receipt['aprueba_resultados'] is not False
                            or receipt['conformidad_normativa']!='no_evaluada'):raise ValueError('Recibo de otra normalización.')
                    if _leer(case/'resultados_estructurales'/_id(receipt['resultado'])/'mapeo.json')!=_leer(case/'mapeos_resultados'/body['version']/'mapeo.json'):
                        raise ValueError('Resultado de otro mapeo.')
                    evidence=verificar_evidencia(self.app.raiz,body['caso'],_id(receipt['resultado']),case/'analisis_etabs'/meta['analisis'])
                    if receipt['evidencia_analisis']!=evidence:raise ValueError('Normalización anterior sin vigencia.')
                    return receipt
                if pendientes(case):raise ErrorNormalizacionPendiente('Hay una normalización pendiente; comprueba su recuperación antes de publicar otra.')
                base=case/'resultados_estructurales'
                if base.resolve()!=base:raise ValueError('Resultados enlazados.')
                previous=[p.name for p in base.iterdir() if re.fullmatch('[0-9a-f]{32}',p.name)] if base.is_dir() else []
                _publicar(case,'normalizaciones_resultados',key,{'solicitud.json':payload,**snapshots,
                    'preparacion.json':_bytes({'resultados_previos':previous,'archivos':{name:_sha(raw) for name,raw in snapshots.items()}})})
                folder=case/'mapeos_resultados'/body['version']
                result=registrar_resultados(self.app.raiz,folder/'configuracion.json',folder/'respuesta.json',folder/'mapeo.json')
                self._cargar(body['caso'],body['version'],body['expediente_sha256'])
                evidence=verificar_evidencia(self.app.raiz,body['caso'],result.name,case/'analisis_etabs'/meta['analisis'])
                receipt={'resultado':result.name,'mapeo_version':body['version'],'huella_mapeo':body['huella_mapeo'],
                         'evidencia_analisis':evidence,'aprueba_resultados':False,'conformidad_normativa':'no_evaluada'}
                _confirmar(operation/'aceptacion.json',_bytes(receipt))
                return receipt

    def estado_normalizacion(self,caso,*,expediente_sha256):
        with self.app.lock:
            case=self._caso(caso,expediente_sha256);rows=[]
            for operation,request in pendientes(case):
                found=candidatos(case,operation,request)
                previous=anteriores(operation)
                rows.append({'clave_solicitud':operation.name,'mapeo_version':request['version'],
                    'huella_mapeo':request['huella_mapeo'],'resultados_candidatos':found,
                    'puede_cancelar':previous is not None and not found,'inventario_previo_conocido':previous is not None,'requiere_recuperacion':True})
            return {'caso':caso,'expediente_sha256':expediente_sha256,'pendientes':rows}

    def recuperar(self,body):
        fields={'caso','expediente_sha256','clave_solicitud','resultado','confirmacion_explicita'}
        if not isinstance(body,dict) or set(body)!=fields or body['confirmacion_explicita'] is not True:
            raise ValueError('Confirma explícitamente la recuperación.')
        with self.app.lock:
            case=self._caso(body['caso'],body['expediente_sha256']);key=_id(body['clave_solicitud'])
            lock=case/'normalizacion.lock'
            if lock.resolve()!=lock:raise ValueError('Bloqueo enlazado.')
            with BloqueoExclusivo(lock):
                selected=[(p,r) for p,r in pendientes(case) if p.name==key]
                if len(selected)!=1:raise ValueError('No hay una operación pendiente con esa clave.')
                operation,request=selected[0]
                if request['expediente_sha256']!=body['expediente_sha256']:raise ValueError('Operación de otro expediente.')
                found=candidatos(case,operation,request)
                if body['resultado'] is None:
                    if anteriores(operation) is None or found:raise ValueError('No se puede cancelar una operación con resultado o inventario incierto.')
                    _confirmar(operation/'cancelacion.json',_bytes({'clave_solicitud':key,'cancelada_sin_resultado':True}))
                    return {'cancelada_sin_resultado':True,'clave_solicitud':key,'aprueba_resultados':False}
                meta,mapping,_,_,_=self._cargar(body['caso'],request['version'],body['expediente_sha256'])
                if huella_declaracion(mapping)!=request['huella_mapeo'] or not aprobacion_vigente(mapping):raise ValueError('Mapeo sin revisión vigente.')
                result=_id(body['resultado'])
                if found!=[result]:raise ValueError('Selecciona el único resultado correspondiente; una mezcla ambigua requiere revisión independiente.')
                evidence=verificar_evidencia(self.app.raiz,body['caso'],result,case/'analisis_etabs'/meta['analisis'])
                self._cargar(body['caso'],request['version'],body['expediente_sha256'])
                if candidatos(case,operation,request)!=[result]:raise ValueError('Los resultados cambiaron durante la recuperación.')
                receipt={'resultado':result,'mapeo_version':request['version'],'huella_mapeo':request['huella_mapeo'],
                    'evidencia_analisis':evidence,'aprueba_resultados':False,'conformidad_normativa':'no_evaluada'}
                _confirmar(operation/'aceptacion.json',_bytes(receipt),conservar_anterior=True)
                return receipt
