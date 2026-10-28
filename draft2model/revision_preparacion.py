"""Preparación visual local de fuentes controladas, sin proveedor ni aprobación."""
import hashlib
from functools import wraps
from pathlib import Path
import re
from .gestion_extraccion import json_desde_bytes
from .revision_documental import revisar_expediente
from .recortes import generar_recorte
from .entrada_vision import preparar_paquete, cargar_paquete
from . import revision_preprocesamiento as derivadas


def _id(value):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{32}',value):raise ValueError('Identificador inválido.')
    return value


def _id_preprocesamiento(value):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{64}',value):
        raise ValueError('ID de preprocesamiento SHA256 inválido.')
    return value


def _leer(path):
    if path.resolve()!=path or not path.is_file():raise ValueError('Fuente enlazada o ausente.')
    return path.read_bytes()


def _publico(method):
    @wraps(method)
    def run(*args,**kwargs):
        try:return method(*args,**kwargs)
        except (KeyError,TypeError,AttributeError,IndexError,OverflowError):
            raise ValueError('Metadatos de preparación inválidos o incompletos.') from None
    return run


class ServicioPreparacion:
    def __init__(self,app):self.app=app

    def _caso(self,caso,fp):
        folder,manifest,current=self.app.expediente(caso)
        if fp!=current or folder.resolve()!=folder:raise ValueError('Expediente sin vigencia.')
        for entry in manifest['archivos']:self.app._original(caso,entry['id'])
        if self.app.expediente(caso)[2]!=fp:raise ValueError('Expediente cambiado.')
        return folder,manifest

    def _revision(self,caso,fp,version):
        folder,_=self._caso(caso,fp);path=folder/'revision_documental'/_id(version)/'revision.json'
        raw=_leer(path);data=json_desde_bytes(raw,'revisión documental')
        if (not isinstance(data,dict) or data.get('caso')!=caso or data.get('expediente_sha256')!=fp
                or not isinstance(data.get('documentos'),list) or not isinstance(data.get('resumen'),dict)):
            raise ValueError('Revisión documental sin vigencia.')
        self._caso(caso,fp)
        if _leer(path)!=raw:raise ValueError('Revisión cambiada durante consulta.')
        return path,data

    def _recorte(self,caso,fp,version):
        folder,manifest=self._caso(caso,fp);path=folder/'recortes'/_id(version)/'recorte.json'
        raw=_leer(path);data=json_desde_bytes(raw,'recorte')
        if (not isinstance(data,dict) or data.get('id')!=version or data.get('caso')!=caso
                or data.get('expediente_sha256')!=fp or data.get('imagen')!='recorte.png'):
            raise ValueError('Recorte sin vigencia.')
        entries=[e for e in manifest['archivos'] if e['id']==data.get('archivo_id')]
        if len(entries)!=1 or entries[0]['sha256']!=data.get('origen_sha256'):raise ValueError('Original de otro recorte.')
        image=_leer(path.parent/'recorte.png')
        if hashlib.sha256(image).hexdigest()!=data.get('imagen_sha256'):raise ValueError('Imagen alterada.')
        marcas_derivado=any(k in data for k in ('preprocesamiento_id','bbox_derivado_normalizada','tipo_transformacion'))
        if marcas_derivado and data.get('tipo_fuente')!='raster_preprocesado':
            raise ValueError('No se puede ocultar la cadena derivada como un recorte original.')
        if data.get('tipo_fuente')=='raster_preprocesado':
            from .entrada_vision import _verificar_render
            _id_preprocesamiento(data.get('preprocesamiento_id'))
            original=folder/entries[0]['archivo']
            _verificar_render(original,data['pagina'],path.parent/'recorte.png',data,recorte=True,
                              expediente=folder/'expediente.json')
        self._caso(caso,fp)
        if _leer(path)!=raw or _leer(path.parent/'recorte.png')!=image:raise ValueError('Recorte cambiado durante consulta.')
        return path,data,image

    @staticmethod
    def _campos(body,extra):
        if not isinstance(body,dict) or set(body)!={'caso','expediente_sha256'}|set(extra):raise ValueError('Campos de preparación inválidos.')

    @_publico
    def revisar(self,body):
        self._campos(body,())
        with self.app.lock:
            folder,_=self._caso(body['caso'],body['expediente_sha256'])
            path=revisar_expediente(folder/'expediente.json')
            self._caso(body['caso'],body['expediente_sha256'])
            return self.revision(body['caso'],path.parent.name,expediente_sha256=body['expediente_sha256'])

    @_publico
    def revision(self,caso,version,*,expediente_sha256):
        with self.app.lock:
            _,data=self._revision(caso,expediente_sha256,version)
            return {'id':version,'caso':caso,'expediente_sha256':expediente_sha256,'resumen':data['resumen'],
                'documentos':[{'id':d['id'],'con_error':bool(d.get('error')),'paginas':[{
                    'numero':p['numero'],'con_error':bool(p.get('error')),
                    'dimensiones_preview_px':[p.get('ancho_preview_px'),p.get('alto_preview_px')],
                    'legibilidad':'pendiente_revision_humana'} for p in d['paginas']]} for d in data['documentos']],
                'estado':'pendiente_revision_humana','aprueba_ingenieria':False}

    @_publico
    def recortar(self,body):
        extra=('preprocesamiento',) if isinstance(body,dict) and 'preprocesamiento' in body else ()
        self._campos(body,('archivo','pagina','bbox','dpi','etiqueta')+extra)
        with self.app.lock:
            folder,_=self._caso(body['caso'],body['expediente_sha256'])
            kwargs={}
            if extra:kwargs['preprocesamiento_id']=_id_preprocesamiento(body['preprocesamiento'])
            path=generar_recorte(folder/'expediente.json',body['archivo'],body['pagina'],body['bbox'],
                                 dpi=body['dpi'],etiqueta=body['etiqueta'],**kwargs)
            return self.recorte(body['caso'],path.parent.name,expediente_sha256=body['expediente_sha256'])

    @_publico
    def recorte(self,caso,version,*,expediente_sha256):
        with self.app.lock:
            _,data,_=self._recorte(caso,expediente_sha256,version)
            return {k:data[k] for k in ('id','caso','archivo_id','pagina','etiqueta','bbox_normalizada','dimensiones_px','imagen_sha256')}|{
                'expediente_sha256':expediente_sha256,'tipo_fuente':data.get('tipo_fuente','pdf'),
                'estado':'pendiente_revision_humana','escala_geometrica':None,'aprueba_ingenieria':False,
                **({k:data[k] for k in ('preprocesamiento_id','bbox_derivado_normalizada','dimensiones_derivado_px',
                    'tipo_transformacion','pixel_a_pagina_visible','pagina_visible_a_pixel','pagina_visible_px')}
                   if data.get('tipo_fuente')=='raster_preprocesado' else {}),
                'aviso':'Original e imagen comprobados por huella. El render y su transformación se contrastan al preparar el paquete.'}

    @staticmethod
    def _proyeccion_preprocesamiento(consulta):
        record=consulta['registro']
        return {'id':consulta['id'],'caso':record['caso'],'archivo_id':record['archivo_id'],
                'expediente_sha256':record['expediente_sha256'],'registro':record,'config':consulta['config'],
                'transformacion':{k:v for k,v in consulta['transformacion'].items() if k!='original'},
                'estado':'transformacion_declarada','aprueba_ingenieria':False,'escala_metrica':None,
                'mejora_precision_vision':'no_evaluada'}

    def _preprocesamiento(self,caso,version,fp):
        folder,_=self._caso(caso,fp)
        consulta=derivadas.consultar_preprocesamiento(folder/'expediente.json',_id_preprocesamiento(version))
        self._caso(caso,fp)
        return consulta

    @_publico
    def original_raster(self,caso,archivo,*,expediente_sha256):
        with self.app.lock:
            folder,_=self._caso(caso,expediente_sha256)
            info=derivadas.informacion_original(folder/'expediente.json',archivo)
            self._caso(caso,expediente_sha256)
            return info

    @_publico
    def preprocesar(self,body):
        self._campos(body,('archivo','config','revisor_declarado','motivo'))
        with self.app.lock:
            caso,fp=body['caso'],body['expediente_sha256'];folder,_=self._caso(caso,fp)
            path=derivadas.registrar_preprocesamiento(folder/'expediente.json',body['archivo'],body['config'],
                revisor_declarado=body['revisor_declarado'],motivo=body['motivo'])
            return self.preprocesamiento(caso,path.parent.name,expediente_sha256=fp)

    @_publico
    def preprocesamiento(self,caso,version,*,expediente_sha256):
        with self.app.lock:
            return self._proyeccion_preprocesamiento(self._preprocesamiento(caso,version,expediente_sha256))

    @_publico
    def imagen_preprocesada(self,caso,version,*,expediente_sha256):
        with self.app.lock:
            return self._preprocesamiento(caso,version,expediente_sha256)['imagen_bytes']

    @_publico
    def preprocesamientos(self,caso,archivo,*,expediente_sha256):
        with self.app.lock:
            folder,_=self._caso(caso,expediente_sha256)
            # Validar identidad/tipo aun cuando todavía no existan versiones.
            derivadas.informacion_original(folder/'expediente.json',archivo)
            rows=derivadas.historial_preprocesamientos(folder/'expediente.json',archivo_id=archivo)
            self._caso(caso,expediente_sha256)
            return {'caso':caso,'archivo_id':archivo,'expediente_sha256':expediente_sha256,
                    'versiones':[self._proyeccion_preprocesamiento(row) for row in rows]}

    @_publico
    def imagen(self,caso,version,*,expediente_sha256):
        with self.app.lock:
            path,data,raw=self._recorte(caso,expediente_sha256,version)
            self._caso(caso,expediente_sha256)
            if _leer(path.parent/'recorte.png')!=raw or json_desde_bytes(_leer(path),'recorte')!=data:
                raise ValueError('Recorte cambiado durante consulta.')
            return raw

    @_publico
    def preparar(self,body):
        self._campos(body,('revision','recortes'))
        if (not isinstance(body['recortes'],list) or not body['recortes'] or len(body['recortes'])>40
                or not all(isinstance(v,str) for v in body['recortes']) or len(set(body['recortes']))!=len(body['recortes'])):
            raise ValueError('Selecciona de 1 a 40 recortes distintos.')
        with self.app.lock:
            caso,fp=body['caso'],body['expediente_sha256'];folder,_=self._caso(caso,fp)
            revision,_=self._revision(caso,fp,body['revision'])
            crops=[self._recorte(caso,fp,version)[0] for version in body['recortes']]
            path=preparar_paquete(folder/'expediente.json',revision,crops)
            return self.paquete(caso,path.parent.name,expediente_sha256=fp)

    @_publico
    def paquete(self,caso,version,*,expediente_sha256):
        with self.app.lock:
            folder,_=self._caso(caso,expediente_sha256)
            path=folder/'vision/solicitudes'/_id(version)/'solicitud.json';_leer(path)
            request,sha,_,_=cargar_paquete(folder/'expediente.json',path)
            if request.get('transmision_externa') is not False:raise ValueError('El paquete no es una preparación local.')
            return {'id':version,'solicitud_id':request['id'],'caso':caso,'expediente_sha256':expediente_sha256,
                'sha256_solicitud':sha,'imagenes':[{k:image[k] for k in ('id','rol','archivo_id','pagina','dimensiones_px','admite_evidencia')} for image in request['imagenes']],
                'recortes':[crop['id'] for crop in request['recortes']],'transmision_externa':False,
                'estado':'preparado_sin_envio','aprueba_ingenieria':False}

    @_publico
    def listar(self,caso,*,expediente_sha256):
        with self.app.lock:
            folder,_=self._caso(caso,expediente_sha256);result={}
            for label,group,read in (('revisiones','revision_documental',self.revision),('recortes','recortes',self.recorte),('paquetes','vision/solicitudes',self.paquete)):
                base=folder/group
                if base.resolve()!=base:raise ValueError('Directorio enlazado.')
                rows=[]
                for path in sorted(base.iterdir()) if base.is_dir() else []:
                    if not re.fullmatch('[0-9a-f]{32}',path.name):continue
                    try:rows.append({'id':path.name,'vigente':True,'datos':read(caso,path.name,expediente_sha256=expediente_sha256)})
                    except (ValueError,OSError,KeyError,TypeError,RuntimeError):rows.append({'id':path.name,'vigente':False})
                result[label]=rows
            self._caso(caso,expediente_sha256)
            return {'caso':caso,'expediente_sha256':expediente_sha256,**result}
