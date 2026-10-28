"""Lectura dirigida de parámetros con el motor de cuota y transporte existente."""
from __future__ import annotations
import copy
from pathlib import Path
import tempfile

from . import proveedor_openai as cliente
from . import gestion_geometria as gg
from . import gestion_extraccion as ge
from .entrada_vision import cargar_paquete
from .validacion_geometria import validar_geometria
from .lectura_parametros import esquema, instruccion, validar_respuesta
from .revision_reconstruccion import ServicioReconstruccion, _bytes, _sha, _read, _write, _now, _uuid


def _codigo_adicional():
    names=('revision_parametros.py','lectura_parametros.py','parametros_a_configuracion.py','parametros_a_lecturas.py','preparacion_configuracion.py')
    files=[Path(__file__).with_name(name) for name in names]
    if any(not p.is_file() for p in files):raise ValueError('El módulo de parámetros todavía no está completamente instalado.')
    return {p.name:_sha(p.read_bytes()) for p in files}


class ServicioParametros(ServicioReconstruccion):
    carpeta_trabajos='lecturas_ingenieria'
    parametros_adicionales=('configuracion_preparacion','sha256_configuracion')
    mensaje_envio='Leyendo materiales, secciones y cargas de los planos. No se repetirá esta petición automáticamente.'

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self._codigo_cargado_adicional=_codigo_adicional()

    def _exigir_codigo(self):
        super()._exigir_codigo()
        if _codigo_adicional()!=self._codigo_cargado_adicional:
            raise ValueError('Los módulos de parámetros cambiaron; actualiza el servidor antes de continuar.')

    def _implementacion(self):return {**super()._implementacion(),**self._codigo_cargado_adicional}

    def _contexto(self,body):
        data,meta,meta_sha=self.app.preparacion_configuracion._cargar(body['caso'],body['expediente_sha256'],body['configuracion_preparacion'])
        if meta['sha256_configuracion']!=body['sha256_configuracion']:raise ValueError('La configuración preparada cambió.')
        geo=gg.consultar_version(self.app.raiz,body['caso'],data['geometria_origen']['version_id']).geometria
        vertices={v['id']:[v['x'],v['y'],v['z']] for v in geo['vertices']};elements={};description=[]
        geometry_validation=validar_geometria(geo)
        if not geometry_validation.consistente:raise ValueError('Geometría de contexto inconsistente.')
        for surface in geo['superficies']:
            points=[vertices[v] for v in surface['vertices']]
            derived=geometry_validation.derivados_m['superficies'][surface['id']]
            elements[surface['id']]={'tipo':'superficie','vertical':abs(derived['normal_unitaria'][2])<=derived['epsilon_relativo_computacional']}
            description.append({'id':surface['id'],'tipo':surface['papel_geometrico'],'puntos':points})
        point_map={p['id']:vertices.get(p.get('vertice_geometria')) for p in data['puntos']}
        for frame in data['frames']:
            elements[frame['id']]={'tipo':'frame'}
            description.append({'id':frame['id'],'tipo':frame['tipo'],'puntos':[point_map.get(frame['inicio']),point_map.get(frame['fin'])]})
        context={'geometria_parcial':True,'unidad_longitud_modelo':geo['unidad_longitud'],
                 'elementos_identificados':description,'datos_pendientes_geometria':geo['faltantes']}
        return data,meta,meta_sha,elements,context

    def _peticion(self,manifest,solicitud,*,proveedor,modelo,max_tokens,cuerpo):
        self._exigir_codigo()
        if proveedor not in ('openai','gemini'):raise ValueError('Proveedor no autorizado para lectura de planos.')
        if type(max_tokens) is not int or not 256<=max_tokens<=65536:raise ValueError('Límite de salida entre256y65536 requerido.')
        _,_,_,_,context=self._contexto(cuerpo)
        payload,_=cliente.preparar_peticion(manifest,solicitud,modelo=modelo,max_tokens=min(max_tokens,16384),detalle='auto',proveedor='openai')
        payload['max_output_tokens']=max_tokens
        request,request_sha,exp,_=cargar_paquete(manifest,solicitud)
        originals={s['id']:s['sha256'] for s in exp['archivos']}
        inventory=[{k:image[k] for k in ('id','archivo_id','pagina','rol')} for image in request['imagenes']]
        import json
        prompt=instruccion(request['caso'],context)+'\nInventario verificado de imágenes:\n'+json.dumps(inventory,ensure_ascii=False)
        payload['input'][0]['content'][0]['text']=prompt
        payload['text']['format'].update(name='draft2model_parametros_planos',schema=esquema())
        if proveedor!='openai':payload=cliente.cliente_api(proveedor).convertir_peticion(payload)
        raw=_bytes(payload)
        if len(raw)>cliente.MAX_BYTES:raise ValueError('Petición de parámetros demasiado grande.')
        return payload,{'sha256_peticion':_sha(raw),'sha256_solicitud':request_sha,'imagenes':len(inventory),
                        'modelo':modelo,'proveedor':proveedor,'max_tokens':max_tokens,
                        'contexto_sha256':_sha(_bytes(context)),'originales_sha256':originals}

    def _procesar_respuesta(self,entry,response,*,duracion_segundos,unidad_revisada=None,state_cb=None):
        self._exigir_codigo()
        if unidad_revisada is not None:raise ValueError('La unidad se revisa en la geometría, no mediante esta lectura de parámetros.')
        body=entry['parametros'];target,folder,manifest,_=self._entrada(body['caso'],body['expediente_sha256'],entry['id'])
        data,meta,meta_sha,elements,_=self._contexto(body)
        parsed=cliente.cliente_api(body['proveedor']).leer_respuesta_api(response)
        _write(target/'respuesta_parametros.json',parsed)
        request,_,_,_=cargar_paquete(folder/'expediente.json',folder/'vision/solicitudes'/body['paquete']/'solicitud.json')
        allowed={(image['archivo_id'],image['pagina']) for image in request['imagenes']}
        checked=validar_respuesta(parsed,manifest,allowed,set(elements))
        previous=_read(target/'resultado.json') if (target/'resultado.json').is_file() else None
        from .parametros_a_lecturas import convertir_a_lecturas, materiales_para_revision
        simulated=self.transporte is not None or entry.get('modo')=='prueba_python'
        extraction,extraction_pending=convertir_a_lecturas(folder/'expediente.json',folder/'vision/solicitudes'/body['paquete']/'solicitud.json',
            checked,proveedor=body['proveedor'],modelo=body['modelo'],simulado=simulated)
        extraction_id=None
        # El registro de lecturas del expediente rechaza expresamente procedencia
        # sintética, incluso si su geometría es una fixture. No se cambia esa marca.
        if not simulated:
            if previous and previous.get('extraccion'):
                old=self.app.version(body['caso'],previous['extraccion'])
                if old['datos']==extraction:extraction_id=previous['extraccion']
            if extraction_id is None:
                with tempfile.TemporaryDirectory(prefix='.parametros-lecturas-',dir=folder) as temporary:
                    path=Path(temporary)/'extraccion.json';path.write_bytes(_bytes(extraction))
                    extraction_id=ge.importar_extraccion(self.app.raiz,body['caso'],path).identificador
        from .parametros_a_configuracion import aplicar_parametros
        applied=aplicar_parametros(data,checked,elementos_permitidos=elements)
        proposed=applied['configuracion']
        result={'lectura':checked,'aplicacion':applied,'simulado':simulated,'duracion_segundos':duracion_segundos,
                'configuracion_preparacion':None,'sha256_configuracion':None,'geometria_version':None,
                'extraccion':extraction_id,'faltantes_adaptacion_lecturas':extraction_pending,
                'materiales_para_revision':materiales_para_revision(checked),
                'lecturas_propuestas':extraction if simulated else None,
                'faltantes':applied.get('faltantes',[]),'aprueba_ingenieria':False,'ejecutable_etabs':False}
        # Un doble no puede incorporar resultados a un expediente de ingeniería real.
        if not simulated or data['datos_sinteticos']:
            saved=None
            if previous and previous.get('configuracion_preparacion'):
                old,old_meta,_=self.app.preparacion_configuracion._cargar(body['caso'],body['expediente_sha256'],previous['configuracion_preparacion'])
                if old==proposed:saved={'id':previous['configuracion_preparacion'],'sha256_configuracion':old_meta['sha256_configuracion']}
            if saved is None:
                if state_cb:state_cb('Incorporando datos respaldados a una nueva preparación; los ausentes siguen pendientes.')
                parent={'id':body['configuracion_preparacion'],'sha256_registro':meta_sha,'sha256_configuracion':meta['sha256_configuracion']}
                saved=self.app.preparacion_configuracion._guardar(body['caso'],body['expediente_sha256'],proposed,padre=parent,
                       origen={'tipo':'lectura_dirigida_parametros','trabajo':entry['id'],'lectura_sha256':_sha(_bytes(checked)),'simulado':simulated})
            result.update(configuracion_preparacion=saved['id'],sha256_configuracion=saved['sha256_configuracion'])
        _write(target/'resultado.json',result)
        _write(target/'estado.json',{'estado':'parametros_borrador','paso':'Lectura de ingeniería conservada en borrador. Revisa faltantes y condiciones; no se ejecutó ETABS.','fecha_utc':_now()})
        return result

    def recuperar(self,body):
        if not isinstance(body,dict) or set(body)!={'caso','expediente_sha256','trabajo'}:raise ValueError('Campos de recuperación de parámetros inválidos.')
        return super().recuperar(body)

    def aplicar(self,body):
        """Reaplica una lectura conservada a un descendiente de la misma geometría, sin API."""
        fields={'caso','expediente_sha256','trabajo','configuracion_preparacion','sha256_configuracion','clave_aplicacion'}
        if not isinstance(body,dict) or set(body)!=fields:raise ValueError('Campos de aplicación de parámetros inválidos.')
        self._exigir_codigo()
        with self.app.lock:
            target,folder,manifest,entry=self._entrada(body['caso'],body['expediente_sha256'],body['trabajo'])
            thread=self._threads.get(body['trabajo'])
            if thread and thread.is_alive():raise ValueError('Espera a que termine la lectura antes de aplicarla.')
            original,_,_,_,_=self._contexto(entry['parametros'])
            current,meta,meta_sha,elements,_=self._contexto({**entry['parametros'],
                'configuracion_preparacion':body['configuracion_preparacion'],'sha256_configuracion':body['sha256_configuracion']})
            if original['geometria_origen']!=current['geometria_origen']:raise ValueError('No se aplica una lectura a otra geometría.')
            simulated=self.transporte is not None or entry.get('modo')=='prueba_python'
            if simulated and not current['datos_sinteticos']:raise ValueError('No aplicar un transporte sintético a una configuración real.')
            marker=target/('aplicacion-'+_uuid(body['clave_aplicacion'])+'.json')
            if marker.exists():
                record=_read(marker)
                if record.get('entrada')!=body or record.get('estado')!='conservada':raise ValueError('Aplicación interrumpida o clave reutilizada; consulta su estado sin recalcular a ciegas.')
                _,child_meta,_=self.app.preparacion_configuracion._cargar(body['caso'],body['expediente_sha256'],record['configuracion_preparacion'])
                if child_meta['sha256_configuracion']!=record['sha256_configuracion']:raise ValueError('La aplicación conservada perdió vigencia.')
                return record
            response=_read(target/'respuesta_api.json')
            parsed=cliente.cliente_api(entry['parametros']['proveedor']).leer_respuesta_api(response)
            request,_,_,_=cargar_paquete(folder/'expediente.json',folder/'vision/solicitudes'/entry['parametros']['paquete']/'solicitud.json')
            checked=validar_respuesta(parsed,manifest,{(im['archivo_id'],im['pagina']) for im in request['imagenes']},set(elements))
            from .parametros_a_configuracion import aplicar_parametros
            applied=aplicar_parametros(current,checked,elementos_permitidos=elements)
            _write(marker,{'estado':'iniciada_no_repetir','entrada':copy.deepcopy(body)},new=True)
            parent={'id':body['configuracion_preparacion'],'sha256_registro':meta_sha,'sha256_configuracion':meta['sha256_configuracion']}
            saved=self.app.preparacion_configuracion._guardar(body['caso'],body['expediente_sha256'],applied['configuracion'],padre=parent,
                origen={'tipo':'reaplicacion_parametros_sin_api','trabajo':body['trabajo'],'clave_aplicacion':body['clave_aplicacion'],'lectura_sha256':_sha(_bytes(checked)),'simulado':simulated})
            record={'estado':'conservada','entrada':copy.deepcopy(body),'configuracion_preparacion':saved['id'],
                    'sha256_configuracion':saved['sha256_configuracion'],'caso':body['caso'],
                    'expediente_sha256':body['expediente_sha256'],'aplicacion':applied,'aprueba_ingenieria':False,'envios_api':0}
            _write(marker,record)
            return record

    def consultar(self,caso,fp,job):
        result=super().consultar(caso,fp,job);data=result.get('resultado') or {}
        if data.get('lectura') and 'materiales_para_revision' not in data:
            from .parametros_a_lecturas import materiales_para_revision
            data['materiales_para_revision']=materiales_para_revision(data['lectura'])
        _,_,_,entry=self._entrada(caso,fp,job)
        result.update(origen_preparacion=entry['parametros']['configuracion_preparacion'],
                      origen_sha256_configuracion=entry['parametros']['sha256_configuracion'])
        if data.get('configuracion_preparacion'):
            _,meta,_=self.app.preparacion_configuracion._cargar(caso,fp,data['configuracion_preparacion'])
            if meta['sha256_configuracion']!=data['sha256_configuracion']:raise ValueError('La preparación de parámetros perdió vigencia.')
        return result
