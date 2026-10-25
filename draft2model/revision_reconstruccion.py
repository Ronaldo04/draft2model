"""Trabajo versionado: imágenes verificadas → relaciones → geometría borrador.

No ejecuta ETABS ni fabrica revisiones. Un intento no se reenvía al reiniciar.
La cuota se reserva antes del transporte y los fallos también la consumen.
"""
from __future__ import annotations

import copy
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import time
from uuid import uuid4

from . import proveedor_openai as cliente
from .adaptador_etabs import BloqueoExclusivo
from .credenciales_locales import cargar as credenciales
from .entrada_vision import cargar_paquete
from .gestion_extraccion import _carpeta_propia, json_desde_bytes
from .gestion_geometria import importar_geometria, comprobar_version
from .politica_uso_ia import exigir_autorizacion, FINALIDAD_AUTORIZADA
from .reconstruccion_automatica import esquema_vision, expandir_respuesta, instruccion, reconstruir
from .validacion_geometria import validar_geometria
from .revision_documental import revisar_expediente
from .recortes import generar_recorte
from .entrada_vision import preparar_paquete


def _bytes(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False,separators=(',',':'))+'\n').encode('utf-8')


def _sha(value):return hashlib.sha256(value).hexdigest()
def _now():return datetime.now(timezone.utc).isoformat()


def _codigo():
    paths=[Path(__file__),Path(__file__).with_name('reconstruccion_automatica.py')]
    return {p.name:_sha(p.read_bytes()) for p in paths}


CODIGO_CARGADO=_codigo()


def _exigir_codigo():
    if _codigo()!=CODIGO_CARGADO:raise ValueError('El programa cambió durante la sesión; actualiza el servidor antes de preparar otra ejecución.')


def _uuid(value):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{32}',value):raise ValueError('Identificador de trabajo inválido.')
    return value


def _write(path,value,*,new=False):
    data=_bytes(value)
    if new:
        with path.open('xb') as stream:stream.write(data)
    else:
        temp=path.with_name('.'+uuid4().hex+'.tmp')
        with temp.open('xb') as stream:stream.write(data)
        os.replace(temp,path)


def _read(path):
    if path.resolve()!=path.absolute() or path.is_symlink() or path.stat().st_size>40*1024*1024:
        raise ValueError('Artefacto ausente, enlazado o excesivo.')
    return json_desde_bytes(path.read_bytes(),'reconstrucción')


def peticion(manifest,solicitud,*,proveedor,modelo,max_tokens):
    if proveedor not in ('openai','gemini'):raise ValueError('Proveedor no autorizado para planos.')
    if type(max_tokens) is not int or not 256<=max_tokens<=65536:
        raise ValueError('max_tokens debe estar entre 256 y 65536.')
    payload,_=cliente.preparar_peticion(manifest,solicitud,modelo=modelo,max_tokens=min(max_tokens,16384),detalle='auto',proveedor='openai')
    payload['max_output_tokens']=max_tokens
    request,sha,exp,_=cargar_paquete(manifest,solicitud)
    originals={a['id']:a['sha256'] for a in exp['archivos']}
    metadata={'caso':request['caso'],'solicitud_sha256':sha,
        'imagenes':[{**{k:im[k] for k in ('id','archivo_id','pagina','rol')},
                     'original_sha256':originals[im['archivo_id']]} for im in request['imagenes']]}
    prompt=instruccion(request['caso'])+'\nInventario de imágenes y originales:\n'+json.dumps(metadata,ensure_ascii=False)
    prompt+='\nContrato de red0.2.0: declara una sola tabla evidencias con IDs cortos E1,E2,…; cada nivel, punto, medida y elemento referencia esos IDs. No repitas objetos de evidencia ni hashes: el programa vincula el SHA256 del original comprobado. No incluyas detalles de armado ni decoración como puntos del modelo global.'
    payload['input'][0]['content'][0]['text']=prompt
    payload['text']['format'].update(name='draft2model_reconstruccion',schema=esquema_vision())
    if proveedor!='openai':payload=cliente.cliente_api(proveedor).convertir_peticion(payload)
    raw=_bytes(payload)
    if len(raw)>cliente.MAX_BYTES:raise ValueError('Petición demasiado grande.')
    return payload,{'sha256_peticion':_sha(raw),'sha256_solicitud':sha,'imagenes':len(request['imagenes']),
                   'modelo':modelo,'proveedor':proveedor,'max_tokens':max_tokens}


class ServicioReconstruccion:
    def __init__(self,app,transporte=None,registro_cuota=None):
        self.app=app;self.transporte=transporte;self._threads={}
        if transporte is not None and not callable(transporte):raise TypeError('Transporte de prueba inválido.')
        # Reutiliza la autorización histórica cuando existe; no reinicia su contador.
        legacy=Path(app.raiz).parent.parent/'seguimiento/CONSUMO_API_211.json'
        self.cuota=Path(registro_cuota) if registro_cuota is not None else legacy if legacy.is_file() else Path(app.raiz)/'.consumo_vision.json'

    def estado_cuota(self):
        ledger=_read(self.cuota) if self.cuota.is_file() else {}
        return {p:{'configurada':self.cuota.is_file(),'limite':self._limite(ledger,p),'usadas':len(ledger.get(p,[])),
                   'restantes':max(0,self._limite(ledger,p)-len(ledger.get(p,[]))),
                   'credencial_configurada':bool(self._key(p))} for p in ('openai','gemini')}

    @staticmethod
    def _limite(ledger,provider):
        limit=ledger.get('limites_autorizados',{}).get(provider,5)
        if type(limit) is not int or not 0<=limit<=1000:raise ValueError('Límite de uso inválido.')
        return limit

    def preparar_originales(self,body):
        fields={'caso','expediente_sha256','proveedor','modelo','max_tokens','clave_solicitud'}
        if not isinstance(body,dict) or set(body)!=fields:raise ValueError('Campos de preparación automática inválidos.')
        with self.app.lock:
            target,folder,_=self._folder(body['caso'],body['expediente_sha256'],body['clave_solicitud'])
            if (target/'entrada.json').exists():
                old=_read(target/'entrada.json')['parametros']
                if any(old[k]!=body[k] for k in fields):raise ValueError('La solicitud ya contiene otros parámetros.')
                return self.consultar(body['caso'],body['expediente_sha256'],body['clave_solicitud'])
            revision=revisar_expediente(folder/'expediente.json',max_lado=1600)
            document=_read(revision);pages=[]
            for entry in document['documentos']:
                if entry.get('error'):raise ValueError('Un original no se puede procesar; revisa la etapa documental.')
                pages.extend((entry['id'],p['numero']) for p in entry['paginas'])
            if not 1<=len(pages)<=8:
                raise ValueError('Esta ejecución admite hasta8páginas; falta implementar la reconstrucción entre lotes mayores.')
            crops=[generar_recorte(folder/'expediente.json',ident,page,[0,0,1,1],dpi=150,
                                   etiqueta='pagina_completa_reconstruccion_automatica') for ident,page in pages]
            self._caso(body['caso'],body['expediente_sha256'])
            request=preparar_paquete(folder/'expediente.json',revision,crops)
            return self.preparar({**body,'paquete':request.parent.name})

    def _caso(self,caso,fp):
        folder,manifest,current=self.app.expediente(caso)
        if current!=fp:raise ValueError('El expediente cambió; vuelve a consultarlo.')
        for source in manifest['archivos']:self.app._original(caso,source['id'])
        return Path(folder),manifest

    def _folder(self,caso,fp,job):
        folder,manifest=self._caso(caso,fp)
        base=_carpeta_propia(folder,'reconstrucciones')
        return _carpeta_propia(base,_uuid(job)),folder,manifest

    def preparar(self,body):
        _exigir_codigo()
        if not isinstance(body,dict) or set(body)!={'caso','expediente_sha256','paquete','proveedor','modelo','max_tokens','clave_solicitud'}:
            raise ValueError('Campos de reconstrucción inválidos.')
        with self.app.lock:
            job=_uuid(body['clave_solicitud']);_uuid(body['paquete'])
            target,folder,_=self._folder(body['caso'],body['expediente_sha256'],job)
            _,proof=peticion(folder/'expediente.json',folder/'vision/solicitudes'/body['paquete']/'solicitud.json',
                 proveedor=body['proveedor'],modelo=body['modelo'],max_tokens=body['max_tokens'])
            entry={'id':job,'parametros':copy.deepcopy(body),'peticion':proof,'creado_utc':_now(),
                   'implementacion':copy.deepcopy(CODIGO_CARGADO),
                   'modo':'prueba_python' if self.transporte is not None else 'real'}
            if target.exists():
                old=_read(target/'entrada.json')
                if (old['parametros']!=body or old['peticion']!=proof or old.get('implementacion')!=CODIGO_CARGADO
                        or old.get('modo')!=entry['modo']):
                    raise ValueError('Clave reutilizada con otros datos o código.')
                return self.consultar(body['caso'],body['expediente_sha256'],job)
            target.mkdir(parents=True)
            _write(target/'entrada.json',entry,new=True)
            _write(target/'estado.json',{'estado':'preparado','paso':'Preparación local terminada; sin envío.','fecha_utc':_now()},new=True)
            return self.consultar(body['caso'],body['expediente_sha256'],job)

    def _entrada(self,caso,fp,job):
        target,folder,manifest=self._folder(caso,fp,job);entry=_read(target/'entrada.json');body=entry['parametros']
        if entry['id']!=job or body['caso']!=caso or body['expediente_sha256']!=fp:raise ValueError('Trabajo de otro expediente.')
        return target,folder,manifest,entry

    def consultar(self,caso,fp,job):
        target,_,_,entry=self._entrada(caso,fp,job);state=_read(target/'estado.json')
        thread=self._threads.get(job)
        if state['estado']=='en_ejecucion' and (not thread or not thread.is_alive()):
            state={**state,'estado':'incierto','paso':'Ejecución interrumpida. Revisar evidencias; no se reenvía automáticamente.'}
        result=_read(target/'resultado.json') if (target/'resultado.json').is_file() else None
        if result and result.get('geometria_version'):
            if not comprobar_version(self.app.raiz,caso,result['geometria_version']).correcta:
                raise ValueError('La geometría generada perdió vigencia.')
        interventions=_read(target/'intervenciones_ingenieria.json') if (target/'intervenciones_ingenieria.json').is_file() else None
        return {'id':job,'caso':caso,'expediente_sha256':fp,'estado':state['estado'],'paso':state['paso'],
                'preparacion':entry['peticion'],'resultado':result,'aprueba_ingenieria':False,
                'tiene_respuesta_conservada':(target/'respuesta_api.json').is_file(),
                'intervenciones':interventions,
                'simulado':entry.get('modo')=='prueba_python' or bool(result and result.get('simulado'))}

    def listar(self,caso,fp):
        folder,_=self._caso(caso,fp);base=_carpeta_propia(folder,'reconstrucciones')
        return [p.name for p in sorted(base.iterdir()) if re.fullmatch('[0-9a-f]{32}',p.name)] if base.exists() else []

    def _key(self,proveedor):
        key=cliente.clave_api(proveedor)
        if key:return key
        path=Path(self.app.raiz)/'credenciales.local.md'
        return credenciales(path).get({'openai':'OPENAI_API_KEY','gemini':'GEMINI_API_KEY'}[proveedor]) if path.is_file() else None

    def _reservar(self,provider,job,model):
        if not self.cuota.is_file():raise ValueError('Falta configurar el límite de solicitudes de la cuenta.')
        lock=BloqueoExclusivo(self.cuota.with_suffix('.reconstruccion.lock')).adquirir()
        try:
            ledger=_read(self.cuota);rows=ledger.get(provider)
            if not isinstance(rows,list) or len(rows)>=self._limite(ledger,provider):raise ValueError('Se agotó el límite autorizado de solicitudes para este proveedor.')
            if any(r.get('trabajo_reconstruccion')==job for r in rows):raise ValueError('Trabajo con reserva previa; no se reenvía.')
            rows.append({'numero':len(rows)+1,'modelo':model,'trabajo_reconstruccion':job,
                         'estado':'reservado_no_reintentar','fecha_utc':_now(),'finalidad':FINALIDAD_AUTORIZADA})
            _write(self.cuota,ledger)
        finally:lock.liberar()

    def ejecutar(self,body):
        _exigir_codigo()
        if not isinstance(body,dict) or set(body)!={'caso','expediente_sha256','trabajo','confirmacion_explicita'} or body['confirmacion_explicita'] is not True:
            raise ValueError('Revisa las imágenes y confirma el envío al proveedor.')
        with self.app.lock:
            target,_,_,entry=self._entrada(body['caso'],body['expediente_sha256'],body['trabajo'])
            if (target/'iniciado.json').exists():raise ValueError('Este trabajo ya se inició; consulta su estado sin reenviar.')
            if entry.get('implementacion')!=CODIGO_CARGADO:raise ValueError('El código del trabajo preparado cambió; prepara otra versión.')
            if (entry.get('modo')=='prueba_python')!=(self.transporte is not None):
                raise ValueError('Una preparación sintética no se convierte en una llamada real.')
            if self.transporte is None:
                provider=entry['parametros']['proveedor'];exigir_autorizacion(provider,FINALIDAD_AUTORIZADA)
                if not self._key(provider):raise ValueError('Credencial local no configurada; no se envió.')
            _write(target/'iniciado.json',{'fecha_utc':_now(),'entrada_sha256':_sha((target/'entrada.json').read_bytes())},new=True)
            _write(target/'estado.json',{'estado':'en_ejecucion','paso':'Comprobando fuentes y preparando lectura de relaciones.','fecha_utc':_now()})
            thread=threading.Thread(target=self._worker,args=(entry,),daemon=True);self._threads[entry['id']]=thread;thread.start()
            return {'id':entry['id'],'estado':'en_ejecucion','aprueba_ingenieria':False}

    def _procesar_respuesta(self,entry,response,*,duracion_segundos,unidad_revisada=None,state_cb=None):
        b=entry['parametros'];target,folder,manifest,_=self._entrada(b['caso'],b['expediente_sha256'],entry['id'])
        simulated=self.transporte is not None or entry.get('modo')=='prueba_python'
        api=cliente.cliente_api(b['proveedor'])
        parsed_raw=api.leer_respuesta_api(response);_write(target/'respuesta_reconstruccion.json',parsed_raw)
        parsed=expandir_respuesta(parsed_raw,manifest) if parsed_raw.get('version_contrato')=='0.2.0' else parsed_raw
        _write(target/'respuesta_expandida.json',parsed)
        if state_cb:state_cb('Resolviendo coordenadas y comprobando conexiones, unidades y contornos.')
        self._caso(b['caso'],b['expediente_sha256'])
        request,_,_,_=cargar_paquete(folder/'expediente.json',folder/'vision/solicitudes'/b['paquete']/'solicitud.json')
        allowed={(im['archivo_id'],im['pagina']) for im in request['imagenes']}
        for group in ('niveles','puntos','elementos','medidas','alineaciones'):
            for item in parsed.get(group,[]):
                if any((e['archivo_id'],e['pagina']) not in allowed for e in item.get('evidencias',[])):
                    raise ValueError('Respuesta cita una página que no se envió.')
        result=reconstruir(parsed,manifest,unidad_revisada=unidad_revisada)
        previous=_read(target/'resultado.json') if (target/'resultado.json').is_file() else None
        result.update(simulado=simulated,geometria_version=None,duracion_segundos=duracion_segundos)
        if result['geometria'] and simulated:
            geo=result['geometria']
            for item in [geo,*geo['vertices'],*geo['superficies']]:
                item['procedencia'].update(tipo='sintetico',descripcion='Transporte Python de prueba; no lectura real de planos.')
            result['validacion']=validar_geometria(geo).a_dict()
        if result['geometria'] and not simulated:
            old_bytes=_bytes(previous['geometria']) if previous and previous.get('geometria') else None
            if (previous and previous.get('geometria_version') and old_bytes==_bytes(result['geometria'])
                    and comprobar_version(self.app.raiz,b['caso'],previous['geometria_version']).correcta):
                result['geometria_version']=previous['geometria_version']
            else:
                if state_cb:state_cb('Registrando automáticamente una nueva geometría en borrador, sin aprobación.')
                _write(target/'geometria.json',result['geometria'])
                imported=importar_geometria(self.app.raiz,b['caso'],target/'geometria.json')
                if not imported.comprobacion.correcta:raise ValueError('La geometría registrada no superó su comprobación.')
                result['geometria_version']=imported.identificador
        _write(target/'resultado.json',result)
        has_geo=bool(result['geometria'])
        _write(target/'estado.json',{'estado':'geometria_borrador' if has_geo else ('terminado_con_faltantes' if result['faltantes'] else 'geometria_borrador'),
            'paso':('Geometría borrador registrada con pendientes de ingeniería visibles en la interfaz.' if (has_geo and result['faltantes'])
                    else 'Revisa los datos faltantes indicados en la interfaz.' if result['faltantes']
                    else 'Geometría reconstruida; falta revisión y configuración de ingeniería.'),
            'fecha_utc':_now()})
        return result

    def recuperar(self,body):
        _exigir_codigo()
        base_fields={'caso','expediente_sha256','trabajo'}
        if not isinstance(body,dict) or not base_fields<=set(body) or not set(body)<=(base_fields|{'unidad_revisada'}):
            raise ValueError('Campos de recuperación de reconstrucción inválidos.')
        with self.app.lock:
            target,_,_,entry=self._entrada(body['caso'],body['expediente_sha256'],body['trabajo'])
            thread=self._threads.get(entry['id'])
            if thread and thread.is_alive():raise ValueError('El trabajo sigue en ejecución; espera a que termine.')
            if not (target/'respuesta_api.json').is_file():
                raise ValueError('No hay respuesta conservada del proveedor para reevaluar localmente.')
            existing=_read(target/'intervenciones_ingenieria.json') if (target/'intervenciones_ingenieria.json').is_file() else {}
            reviewed_unit=body['unidad_revisada'] if 'unidad_revisada' in body else existing.get('unidad_revisada')
            started=time.monotonic()
            response=_read(target/'respuesta_api.json')
            result=self._procesar_respuesta(entry,response,duracion_segundos=round(time.monotonic()-started,3),
                                            unidad_revisada=reviewed_unit)
            if 'unidad_revisada' in body:
                _write(target/'intervenciones_ingenieria.json',
                       {'unidad_revisada':result['unidad_declarada_ingenieria'],'fecha_utc':_now(),
                        'implementacion':copy.deepcopy(CODIGO_CARGADO)})
            b=entry['parametros']
            simulated=self.transporte is not None or entry.get('modo')=='prueba_python'
            if not simulated and self.cuota.is_file():
                metadata=cliente.proveedores.metadatos(b['proveedor'],response)
                try:self.sincronizar_consumo(b['caso'],b['expediente_sha256'],entry['id'],metadata=metadata)
                except ValueError:pass
            return self.consultar(b['caso'],b['expediente_sha256'],entry['id'])

    def _worker(self,entry):
        b=entry['parametros'];target,folder,manifest,_=self._entrada(b['caso'],b['expediente_sha256'],entry['id'])
        key=None;started=time.monotonic();reserved=False;metadata={}
        def state(text):_write(target/'estado.json',{'estado':'en_ejecucion','paso':text,'fecha_utc':_now()})
        try:
            payload,proof=peticion(folder/'expediente.json',folder/'vision/solicitudes'/b['paquete']/'solicitud.json',
                proveedor=b['proveedor'],modelo=b['modelo'],max_tokens=b['max_tokens'])
            if proof!=entry['peticion']:raise ValueError('Las entradas cambiaron antes del envío.')
            if self.transporte is None:
                key=self._key(b['proveedor']);self._reservar(b['proveedor'],entry['id'],b['modelo']);reserved=True
            state('Leyendo relaciones y medidas en el proveedor. No se repetirá esta petición automáticamente.')
            api=cliente.cliente_api(b['proveedor'])
            response=self.transporte(payload,600) if self.transporte is not None else api._http(payload,key,600)
            metadata=cliente.proveedores.metadatos(b['proveedor'],response)
            if key and key in _bytes(response).decode('utf-8'):raise ValueError('Respuesta con contenido de credencial; no se conserva.')
            _write(target/'respuesta_api.json',response,new=True)
            self._procesar_respuesta(entry,response,duracion_segundos=round(time.monotonic()-started,3),state_cb=state)
        except (ValueError,OSError,RuntimeError,KeyError,TypeError) as error:
            if getattr(error,'http_status',None):metadata['http_status']=error.http_status
            _write(target/'estado.json',{'estado':'fallido_no_reintentar','paso':str(error) if isinstance(error,ValueError) else 'Ejecución interrumpida; conserva las evidencias y no reenvía.',
                                         'fecha_utc':_now()})
        finally:
            key=None
            if reserved:
                try:self.sincronizar_consumo(b['caso'],b['expediente_sha256'],entry['id'],metadata=metadata)
                except (ValueError,OSError,RuntimeError):
                    _write(target/'consumo_pendiente.json',{'reserva_conservada':True,'requiere_sincronizacion':True},new=True)

    def sincronizar_consumo(self,caso,fp,job,*,metadata=None):
        target,_,_,entry=self._entrada(caso,fp,job);state=_read(target/'estado.json')
        lock=BloqueoExclusivo(self.cuota.with_suffix('.reconstruccion.lock')).adquirir()
        try:
            ledger=_read(self.cuota)
            rows=ledger.get(entry['parametros']['proveedor'],[])
            matches=[r for r in rows if r.get('trabajo_reconstruccion')==job]
            if len(matches)!=1:raise ValueError('Reserva de consumo ausente o repetida.')
            row=matches[0];row.update(estado=state['estado'],caso=caso,fin_utc=state['fecha_utc'])
            if metadata is not None:row['observado']=metadata
            _write(self.cuota,ledger)
        finally:lock.liberar()
