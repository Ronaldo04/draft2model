"""Respuestas visuales declaradas: registro local y traslado a revisión, sin envío."""
import hashlib
import json
from pathlib import Path
import re
import tempfile
from .entrada_vision import adaptar_respuesta, registrar_respuesta
from .gestion_extraccion import importar_extraccion, json_desde_bytes, comprobar_evidencia, validar_version
from .adaptador_etabs import BloqueoExclusivo


def _id(value):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{32}',value):raise ValueError('Identificador inválido.')
    return value


def _leer(path):
    if path.resolve()!=path or not path.is_file():raise ValueError('Fuente ausente o enlazada.')
    return path.read_bytes()


def _sha(raw):return hashlib.sha256(raw).hexdigest()


class ServicioRespuestas:
    def __init__(self,app):self.app=app

    def _caso(self,caso,fp):
        folder,_,current=self.app.expediente(caso)
        if current!=fp or folder.resolve()!=folder:raise ValueError('Expediente cambiado.')
        for group in ('vision','vision/respuestas','vision/solicitudes'):
            if (folder/group).resolve()!=folder/group:raise ValueError('Directorio enlazado.')
        return folder

    def registrar(self,body):
        fields={'caso','expediente_sha256','paquete','respuesta_json','proveedor_declarado','modelo_declarado','modo_prueba'}
        # `cuarentena` (R235/R236): decisión explícita de recuperar los válidos y apartar los inválidos sin corregirlos.
        if (not isinstance(body,dict) or set(body) not in (fields,fields|{'cuarentena'}) or type(body['modo_prueba']) is not bool
                or type(body.get('cuarentena',False)) is not bool
                or not isinstance(body['respuesta_json'],str) or len(body['respuesta_json'].encode('utf-8'))>1536*1024):
            raise ValueError('Respuesta local incompleta o fuera de límite.')
        for key in ('proveedor_declarado','modelo_declarado'):
            if not isinstance(body[key],str) or not 1<=len(body[key].strip())<=150:raise ValueError('Declara proveedor y modelo de origen.')
        with self.app.lock:
            caso,fp=body['caso'],body['expediente_sha256'];folder=self._caso(caso,fp)
            package=_id(body['paquete']);self.app.preparacion.paquete(caso,package,expediente_sha256=fp)
            request=folder/'vision/solicitudes'/package/'solicitud.json'
            with tempfile.TemporaryDirectory(prefix='.respuesta-',dir=folder) as temp:
                raw_path=Path(temp)/'respuesta.json';raw_path.write_text(body['respuesta_json'],encoding='utf-8')
                output=registrar_respuesta(folder/'expediente.json',request,raw_path,
                    proveedor=body['proveedor_declarado'],modelo=body['modelo_declarado'],modo_prueba=body['modo_prueba'],
                    cuarentena=body.get('cuarentena',False))
            target=output.parent
            if target.resolve()!=target or target.parent!=folder/'vision/respuestas':raise ValueError('Registro fuera del caso.')
            names=('respuesta_original.json','extraccion.json','registro.json')
            meta={'tipo':'draft2model.respuesta_visual_web','id':target.name,'caso':caso,'expediente_sha256':fp,
                'paquete':package,'archivos':{name:_sha(_leer(target/name)) for name in names}}
            with (target/'origen_web.json').open('x',encoding='utf-8') as stream:
                json.dump(meta,stream,ensure_ascii=False,allow_nan=False)
            return self.consultar(caso,target.name,expediente_sha256=fp)

    def _proveedor(self,caso,fp,trabajo,huella,version=None,sha=None):
        job=self.app.proveedor.consultar(caso,_id(trabajo))
        if (job.get('estado')!='completado_verificado' or job.get('vigente') is not True
                or job.get('expediente_sha256')!=fp or job.get('huella_preparacion')!=huella
                or not isinstance(job.get('respuesta_visual'),dict)):
            raise ValueError('Trabajo del proveedor no completado o no vigente.')
        response=job['respuesta_visual']
        _id(response.get('id'))
        if (version is not None and response['id']!=version
                or sha is not None and response.get('sha256_extraccion')!=sha):
            raise ValueError('Respuesta de otro trabajo.')
        return job

    def vincular_proveedor(self,body):
        fields={'caso','expediente_sha256','trabajo','huella_preparacion','confirmacion_explicita'}
        if not isinstance(body,dict) or set(body)!=fields or body['confirmacion_explicita'] is not True:
            raise ValueError('Confirma vincular la respuesta del proveedor.')
        with self.app.lock:
            caso,fp=body['caso'],body['expediente_sha256'];folder=self._caso(caso,fp)
            job=self._proveedor(caso,fp,body['trabajo'],body['huella_preparacion'])
            ident=job['respuesta_visual']['id'];target=folder/'vision/respuestas'/ident
            names=('respuesta_original.json','extraccion.json','registro.json')
            meta={'tipo':'draft2model.respuesta_visual_web','id':ident,'caso':caso,'expediente_sha256':fp,
                'paquete':job['paquete'],'archivos':{name:_sha(_leer(target/name)) for name in names},
                'trabajo_proveedor':{'id':job['id'],'huella_preparacion':job['huella_preparacion']}}
            if meta['archivos']['extraccion.json']!=job['respuesta_visual']['sha256_extraccion']:
                raise ValueError('La respuesta cambió durante el vínculo.')
            origin=target/'origen_web.json'
            if origin.exists():
                if json_desde_bytes(_leer(origin),'origen')!=meta:raise ValueError('Respuesta ya vinculada a otro origen.')
            else:
                with origin.open('x',encoding='utf-8') as stream:json.dump(meta,stream,ensure_ascii=False,allow_nan=False)
            return self.consultar(caso,ident,expediente_sha256=fp)

    def _cargar(self,caso,version,fp):
        folder=self._caso(caso,fp);target=folder/'vision/respuestas'/_id(version)
        meta_raw=_leer(target/'origen_web.json');meta=json_desde_bytes(meta_raw,'origen')
        fields={'tipo','id','caso','expediente_sha256','paquete','archivos'}
        if (not isinstance(meta,dict) or set(meta) not in (fields,fields|{'trabajo_proveedor'})
                or meta['tipo']!='draft2model.respuesta_visual_web' or meta['id']!=version or meta['caso']!=caso
                or meta['expediente_sha256']!=fp or not isinstance(meta['archivos'],dict)
                or set(meta['archivos'])!={'respuesta_original.json','extraccion.json','registro.json'}):raise ValueError('Registro inválido.')
        raw={name:_leer(target/name) for name in meta['archivos']}
        if any(_sha(value)!=meta['archivos'][name] for name,value in raw.items()):raise ValueError('Respuesta alterada.')
        record=json_desde_bytes(raw['registro.json'],'registro');extraction=json_desde_bytes(raw['extraccion.json'],'extracción')
        base={'solicitud_id','solicitud_sha256','respuesta_sha256','extraccion_sha256','proveedor_declarado','modelo_declarado',
              'modo_prueba','transmision_externa','alcance_declaracion_transmision','aprobacion_ingenieria'}
        cuarentena=isinstance(record,dict) and set(record)==base|{'recuperacion_con_cuarentena','candidatos_en_cuarentena'}
        if (not isinstance(record,dict) or (set(record)!=base and not cuarentena)
                or (cuarentena and (record.get('recuperacion_con_cuarentena') is not True
                                    or len(json_desde_bytes(raw['extraccion.json'],'extracción').get('cuarentena',[]))!=record.get('candidatos_en_cuarentena')))
                or type(record.get('modo_prueba')) is not bool
                or record.get('aprobacion_ingenieria') is not None or record.get('transmision_externa') is not False
                or record.get('respuesta_sha256')!=_sha(raw['respuesta_original.json'])
                or record.get('extraccion_sha256')!=_sha(raw['extraccion.json'])):raise ValueError('Declaración de origen inválida.')
        package=self.app.preparacion.paquete(caso,_id(meta['paquete']),expediente_sha256=fp)
        if record.get('solicitud_id')!=package['solicitud_id'] or record.get('solicitud_sha256')!=package['sha256_solicitud']:
            raise ValueError('Respuesta de otro paquete.')
        expected=adaptar_respuesta(folder/'expediente.json',folder/'vision/solicitudes'/meta['paquete']/'solicitud.json',
            json_desde_bytes(raw['respuesta_original.json'],'respuesta'),proveedor=record['proveedor_declarado'],
            modelo=record['modelo_declarado'],modo_prueba=record['modo_prueba'],cuarentena=cuarentena)
        if extraction!=expected:raise ValueError('La extracción no corresponde a la respuesta y evidencias.')
        if 'trabajo_proveedor' in meta:
            ref=meta['trabajo_proveedor']
            if not isinstance(ref,dict) or set(ref)!={'id','huella_preparacion'}:raise ValueError('Origen del proveedor inválido.')
            job=self._proveedor(caso,fp,ref['id'],ref['huella_preparacion'],version,_sha(raw['extraccion.json']))
            if (job['paquete']!=meta['paquete'] or job['modelo_declarado']!=record['modelo_declarado']
                    or (job['modo']=='transporte_prueba_python') is not record['modo_prueba']):
                raise ValueError('Declaración de proveedor incompatible.')
        self._caso(caso,fp)
        if _leer(target/'origen_web.json')!=meta_raw or any(_leer(target/name)!=value for name,value in raw.items()):raise ValueError('Respuesta cambiada durante consulta.')
        return target,meta,record,extraction,raw

    def consultar(self,caso,version,*,expediente_sha256):
        with self.app.lock:
            _,meta,record,extraction,raw=self._cargar(caso,version,expediente_sha256)
            job=(self._proveedor(caso,expediente_sha256,meta['trabajo_proveedor']['id'],
                  meta['trabajo_proveedor']['huella_preparacion'],version,_sha(raw['extraccion.json']))
                 if 'trabajo_proveedor' in meta else None)
            return {'id':version,'caso':caso,'expediente_sha256':expediente_sha256,'paquete':meta['paquete'],
                'sha256_extraccion':_sha(raw['extraccion.json']),'extraccion':extraction,
                'proveedor_declarado':record['proveedor_declarado'],'modelo_declarado':record['modelo_declarado'],
                'modo_prueba':record['modo_prueba'],'origen':'proveedor_verificado' if job else 'respuesta_local_declarada',
                'trabajo_proveedor':job['id'] if job else None,
                'llamada_real_acreditada':job['llamada_real_acreditada'] if job else False,
                'transmision_externa':job['llamada_real_acreditada'] if job else False,
                'traslado_permitido':extraction['procedencia']['tipo']=='expediente',
                'candidatos_en_cuarentena':len(extraction.get('cuarentena',[])),
                'cobertura':extraction.get('cobertura'),
                'estado':'pendiente_revision','aprueba_ingenieria':False}

    def importar(self,body):
        fields={'caso','expediente_sha256','respuesta','sha256_extraccion','confirmacion_explicita'}
        if not isinstance(body,dict) or set(body)!=fields or body['confirmacion_explicita'] is not True:raise ValueError('Confirma el traslado de la extracción pendiente.')
        with self.app.lock:
            caso,fp=body['caso'],body['expediente_sha256']
            folder=self._caso(caso,fp);lock=folder/'respuesta_web.lock'
            if lock.resolve()!=lock:raise ValueError('Control enlazado.')
            with BloqueoExclusivo(lock):
                target,_,_,extraction,raw=self._cargar(caso,body['respuesta'],fp)
                sha=_sha(raw['extraccion.json'])
                if sha!=body['sha256_extraccion']:raise ValueError('Extracción cambiada.')
                accepted=target/'importacion_web.json';pending=target/'importacion_pendiente.json'
                if accepted.exists():
                    saved=json_desde_bytes(_leer(accepted),'importación')
                    if (not isinstance(saved,dict) or set(saved)!={'respuesta','sha256_extraccion','extraccion','archivos'}
                            or saved['respuesta']!=body['respuesta'] or saved['sha256_extraccion']!=sha):
                        raise ValueError('Importación anterior alterada.')
                    ident=_id(saved['extraccion']);base=folder/'extracciones'/ident
                    if (not isinstance(saved['archivos'],dict) or set(saved['archivos'])!={'extraccion.json','version.json'}
                            or any(_sha(_leer(base/name))!=value for name,value in saved['archivos'].items())
                            or not validar_version(self.app.raiz,caso,ident).correcta
                            or json_desde_bytes(_leer(base/'extraccion.json'),'extracción')!=extraction):
                        raise ValueError('La extracción importada dejó de estar vigente.')
                else:
                    if pending.exists():raise ValueError('Importación interrumpida; requiere revisión antes de repetir.')
                    if not comprobar_evidencia(folder,caso,extraction).correcta:raise ValueError('Extracción no importable al caso.')
                    with pending.open('x',encoding='utf-8') as stream:
                        json.dump({'respuesta':body['respuesta'],'sha256_extraccion':sha},stream)
                    result=importar_extraccion(self.app.raiz,caso,target/'extraccion.json');ident=result.identificador
                    self._cargar(caso,body['respuesta'],fp)
                    base=folder/'extracciones'/ident
                    saved={'respuesta':body['respuesta'],'sha256_extraccion':sha,'extraccion':ident,
                        'archivos':{name:_sha(_leer(base/name)) for name in ('extraccion.json','version.json')}}
                    with accepted.open('x',encoding='utf-8') as stream:json.dump(saved,stream)
                self._cargar(caso,body['respuesta'],fp)
                return {'caso':caso,'extraccion':ident,'estado':'pendiente_revision','aprueba_ingenieria':False}

    def listar(self,caso,*,expediente_sha256):
        with self.app.lock:
            base=self._caso(caso,expediente_sha256)/'vision/respuestas';rows=[]
            for path in sorted(base.iterdir()) if base.is_dir() else []:
                if not re.fullmatch('[0-9a-f]{32}',path.name):continue
                try:
                    value=self.consultar(caso,path.name,expediente_sha256=expediente_sha256)
                    rows.append({'id':path.name,'vigente':True,'paquete':value['paquete'],'estado':'pendiente_revision'})
                except (ValueError,OSError,KeyError,TypeError):rows.append({'id':path.name,'vigente':False})
            return {'caso':caso,'expediente_sha256':expediente_sha256,'versiones':rows}
