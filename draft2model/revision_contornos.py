"""Planos → propuestas normalizadas → calibración → geometría nueva en borrador.

Comparte cuota y transporte con las lecturas existentes. Recuperar trabaja sobre
la respuesta conservada y no reenvía al proveedor. Nunca aprueba ingeniería.
"""
from __future__ import annotations
import copy
from fractions import Fraction
import json
import math
from pathlib import Path
import tempfile

from . import gestion_geometria as gg
from . import proveedor_openai as cliente
from .digitizacion_calibrada import LIMITES
from .entrada_vision import cargar_paquete
from .revision_reconstruccion import ServicioReconstruccion, _bytes, _sha, _read, _write, _now


def _codigo():
    names=('revision_contornos.py','lectura_contornos.py','contornos_a_geometria.py',
           'revision_digitizacion.py','digitizacion_calibrada.py','revision_parametros.py','preparacion_configuracion.py')
    return {name:_sha(Path(__file__).with_name(name).read_bytes()) for name in names}


def _limites(value):
    if not isinstance(value,dict) or set(value)!=set(LIMITES):raise ValueError('Declara todos los criterios del cálculo calibrado.')
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in value.values()):
        raise ValueError('Los criterios deben ser números finitos positivos.')
    if value['condicion_max']<1 or value['localizacion_uv']>1 or value['escala_min_m_por_uv']>=value['escala_max_m_por_uv']:
        raise ValueError('Rangos de criterios de calibración inválidos.')
    return copy.deepcopy(value)


def _planos(geometria):
    """Catálogo de planos cartesianos ya definidos; no crea niveles ni cotas."""
    result=[]
    for constant,axes in (('z',['x','y']),('y',['x','z']),('x',['y','z'])):
        groups={}
        for vertex in geometria['vertices']:groups.setdefault(vertex[constant],[]).append(vertex)
        for index,(level,vertices) in enumerate(sorted(groups.items())):
            a=vertices[0];b=next((v for v in vertices if any(v[k]!=a[k] for k in axes)),None)
            if b is None:continue
            u,v=axes
            noncollinear=any((Fraction(b[u])-Fraction(a[u]))*(Fraction(p[v])-Fraction(a[v])) !=
                            (Fraction(b[v])-Fraction(a[v]))*(Fraction(p[u])-Fraction(a[u])) for p in vertices)
            if noncollinear:
                result.append({'id':'PL_'+constant.upper()+'_'+str(index),'ejes':axes,'eje_constante':constant,
                               'valor_constante':level,'unidad_longitud':geometria['unidad_longitud'],
                               'puntos_resueltos':sorted(p['id'] for p in vertices)})
    return result


class ServicioContornos(ServicioReconstruccion):
    carpeta_trabajos='lecturas_contornos'
    parametros_adicionales=('configuracion_preparacion','sha256_configuracion','limites_digitizacion')
    mensaje_envio='Leyendo contornos y correspondencias desde los planos. Una solicitud; sin reintentos automáticos.'

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self._codigo_contornos=_codigo()

    def _exigir_codigo(self):
        super()._exigir_codigo()
        if _codigo()!=self._codigo_contornos:raise ValueError('El módulo de contornos cambió; actualiza el servidor antes de continuar.')

    def _implementacion(self):return {**super()._implementacion(),**self._codigo_contornos}

    def _contexto(self,body):
        from .lectura_contornos import huella, validar_contexto
        data,meta,meta_sha,_,_=self.app.parametros._contexto(body)
        consulta=gg.consultar_version(self.app.raiz,body['caso'],data['geometria_origen']['version_id'])
        if not consulta.comprobacion.correcta:raise ValueError('Geometría de contexto sin vigencia.')
        geo=consulta.geometria;planes=_planos(geo)
        if not planes:raise ValueError('Faltan tres referencias coplanares no colineales; completa la geometría en la interfaz.')
        ctx={'geometria':{**copy.deepcopy(data['geometria_origen']),'sha256_geometria_canonica':huella(geo),
                         'unidad_longitud':geo['unidad_longitud'],'datos_sinteticos':data['datos_sinteticos']},
             'planos':planes,'puntos_resueltos':sorted(p['id'] for p in geo['vertices']),
             'superficies':sorted(p['id'] for p in geo['superficies']),'frames':sorted(p['id'] for p in data['frames']),
             'catalogo_vertices':copy.deepcopy(geo['vertices'])}
        return data,meta,meta_sha,geo,validar_contexto(ctx)

    def _peticion(self,manifest,solicitud,*,proveedor,modelo,max_tokens,cuerpo):
        from .lectura_contornos import esquema, instruccion
        self._exigir_codigo();_limites(cuerpo['limites_digitizacion'])
        if proveedor not in ('openai','gemini') or type(max_tokens) is not int or not 256<=max_tokens<=65536:
            raise ValueError('Proveedor o límite de salida inválidos.')
        config,_,_,geo,ctx=self._contexto(cuerpo)
        payload,_=cliente.preparar_peticion(manifest,solicitud,modelo=modelo,max_tokens=min(max_tokens,16384),detalle='auto',proveedor='openai')
        payload['max_output_tokens']=max_tokens
        request,sha,_,_=cargar_paquete(manifest,solicitud)
        current={'superficies_existentes':[{k:s[k] for k in ('id','vertices','papel_geometrico')} for s in geo['superficies']],
                 'aberturas_existentes':geo['aberturas'],
                 'barras_existentes':[{k:f[k] for k in ('id','inicio','fin','tipo')} for f in config['frames']],
                 'observaciones_geometria_parcial':geo['faltantes']}
        payload['input'][0]['content'][0]['text']=(instruccion(request['caso'],ctx)+
            '\nTopología ya conservada y observaciones pendientes (no dupliques caras ni barras existentes con otros IDs):\n'+
            json.dumps(current,ensure_ascii=False)+
            '\nPropón únicamente adiciones respaldadas por estos planos. Si faltan niveles o correspondencias, '
            'decláralo en faltantes; no marques observaciones previas como resueltas por suposición.')
        payload['text']={'format':{'type':'json_schema','name':'contornos_normalizados','schema':esquema(),'strict':True}}
        if proveedor!='openai':payload=cliente.cliente_api(proveedor).convertir_peticion(payload)
        return payload,{'peticion_sha256':_sha(_bytes(payload)),'solicitud_sha256':sha,
                        'contexto_sha256':_sha(_bytes(ctx)),'criterios':_limites(cuerpo['limites_digitizacion'])}

    def _procesar_respuesta(self,entry,response,*,duracion_segundos,unidad_revisada=None,state_cb=None):
        from .lectura_contornos import validar_respuesta
        from .contornos_a_geometria import incorporar_contornos
        if unidad_revisada is not None:raise ValueError('La unidad procede de la geometría comprobada.')
        self._exigir_codigo();b=entry['parametros']
        target,folder,manifest,_=self._entrada(b['caso'],b['expediente_sha256'],entry['id'])
        config,meta,meta_sha,geo,ctx=self._contexto(b)
        parsed=cliente.cliente_api(b['proveedor']).leer_respuesta_api(response)
        _write(target/'respuesta_contornos.json',parsed)
        req,_,_,_=cargar_paquete(folder/'expediente.json',folder/'vision/solicitudes'/b['paquete']/'solicitud.json')
        checked=validar_respuesta(parsed,manifest,{(i['archivo_id'],i['pagina']) for i in req['imagenes']},ctx)
        simulated=self.transporte is not None or entry.get('modo')=='prueba_python'
        if simulated and not config['datos_sinteticos']:
            result={'lectura':checked,'simulado':True,'geometria_version':None,'configuracion_preparacion':None,
                    'faltantes':['Una prueba sintética no incorpora contornos a una geometría real.'],'ejecutable_etabs':False}
        else:
            advance=_read(target/'avance.json') if (target/'avance.json').is_file() else {'digitizaciones':{}}
            records={};errors=[]
            for drawing in checked['datos']['dibujos']:
                if state_cb:state_cb('Calibrando dibujo '+drawing['id']+' desde las referencias geométricas; sin otra API.')
                try:
                    if drawing['id'] in advance['digitizaciones']:
                        record=self.app.digitizacion.consultar(b['caso'],b['expediente_sha256'],advance['digitizaciones'][drawing['id']])
                    else:
                        source=drawing['fuente'];plane=drawing['plano']
                        bind={'caso':b['caso'],'expediente_sha256':b['expediente_sha256'],
                              'geometria':ctx['geometria']['version_id'],'huella_geometria':ctx['geometria']['huella_contenido'],
                              'sha256_geometria':ctx['geometria']['sha256_geometria']}
                        origin={'modo':'propuesta_automatica_codex','referencia_origen':entry['id'],'editada_en_pantalla':False}
                        prepared=self.app.digitizacion.preparar({**bind,'fuente':source,'plano':plane,'origen_propuesta':origin})
                        clean=lambda items:[{k:v for k,v in item.items() if k!='evidencias'} for item in items]
                        record=self.app.digitizacion.calcular({**bind,'fuente':source,'plano':plane,
                            'propuesta_id':drawing['id'],'preparacion_id':prepared['id'],'huella_preparacion':prepared['huella_version'],
                            'limites':_limites(b['limites_digitizacion']),'anclas':clean(drawing['anclas']),
                            'controles':clean(drawing['controles']),'puntos':clean(drawing['puntos']),'origen_propuesta':origin})
                        advance['digitizaciones'][drawing['id']]=record['id'];_write(target/'avance.json',advance)
                    records[drawing['id']]=record
                except ValueError as error:errors.append({'dibujo':drawing['id'],'motivo':str(error)})
            merged=incorporar_contornos(geo,checked,records)
            result={'lectura':checked,'digitizaciones':advance['digitizaciones'],'errores_digitizacion':errors,
                    'incorporacion':merged,'simulado':simulated,'geometria_version':None,'configuracion_preparacion':None,
                    'sha256_configuracion':None,'frames_propuestos':merged['frames_propuestos'],
                    'faltantes':merged['faltantes'],'duracion_segundos':duracion_segundos,
                    'aprueba_ingenieria':False,'ejecutable_etabs':False}
            if merged['aplicado'] and merged['validacion']['consistente']:
                if state_cb:state_cb('Conservando geometría y preparación derivadas; siguen en borrador.')
                if not advance.get('geometria_version'):
                    with tempfile.TemporaryDirectory(prefix='.contornos-',dir=folder) as temporary:
                        path=Path(temporary)/'geometria.json';path.write_bytes(_bytes(merged['geometria']))
                        advance['geometria_version']=gg.importar_geometria(self.app.raiz,b['caso'],path).identificador
                    _write(target/'avance.json',advance)
                saved_geo=gg.consultar_version(self.app.raiz,b['caso'],advance['geometria_version'])
                if not saved_geo.comprobacion.correcta or saved_geo.geometria!=merged['geometria']:
                    raise ValueError('La geometría incorporada perdió su vínculo exacto con el resultado.')
                if not advance.get('configuracion_preparacion'):
                    prepared=self._preparacion_derivada(b,config,meta,meta_sha,saved_geo,merged)
                    advance.update(configuracion_preparacion=prepared['id'],sha256_configuracion=prepared['sha256_configuracion'])
                    _write(target/'avance.json',advance)
                result.update({k:advance[k] for k in ('geometria_version','configuracion_preparacion','sha256_configuracion')})
        _write(target/'resultado.json',result)
        _write(target/'estado.json',{'estado':'contornos_borrador','paso':'Propuestas calibradas conservadas. Revisa las observaciones y la geometría; no se aprobó ingeniería ni ejecutó ETABS.','fecha_utc':_now()})
        return result

    def _preparacion_derivada(self,b,config,meta,meta_sha,consulta,merged):
        from .plantilla_configuracion import borrador
        fresh=borrador(self.app.raiz,b['caso'],consulta.identificador,version_contrato='0.5.0')
        data=copy.deepcopy(config);data['revision']={'estado':'borrador','aprobacion':None}
        data['geometria_origen']=fresh['geometria_origen'];data['puntos']=fresh['puntos']
        for name in ('asignaciones_superficies','asignaciones_muros'):
            old={v['objetivo']:v for v in data.get(name,[])}
            data[name]=[old.get(v['objetivo'],v) for v in fresh.get(name,[])]
        for f in merged['frames_propuestos']:
            source='PLANO-'+f['evidencias'][0]['archivo_id']
            data['frames'].append({'id':f['id'],'tipo':f['tipo'],'inicio':f['puntos'][0],'fin':f['puntos'][1],'fuente':source})
            data['asignaciones_frames'].append({'objetivo':f['id'],'seccion':None,'fuente':source})
        # La malla depende de la geometría exacta. Se conserva la versión padre
        # con sus decisiones y se invalida su aplicación a la geometría nueva.
        for key in ('malla','conexiones_borde','nodos_derivados','subdivision_frames'):
            if key in fresh:data[key]=copy.deepcopy(fresh[key])
        parent={'id':b['configuracion_preparacion'],'sha256_registro':meta_sha,'sha256_configuracion':meta['sha256_configuracion']}
        return self.app.preparacion_configuracion._guardar(b['caso'],b['expediente_sha256'],data,padre=parent,
            origen={'tipo':'incorporacion_automatica_contornos','geometria_padre':config['geometria_origen'],
                    'malla_anterior_conservada_en_padre':True,'revision_humana_fabricada':False})

    def recuperar(self,body):
        if not isinstance(body,dict) or set(body)!={'caso','expediente_sha256','trabajo'}:raise ValueError('Campos de recuperación de contornos inválidos.')
        return super().recuperar(body)

    def consultar(self,caso,fp,job):
        value=super().consultar(caso,fp,job);_,_,_,entry=self._entrada(caso,fp,job)
        value.update(origen_preparacion=entry['parametros']['configuracion_preparacion'],
                     origen_sha256_configuracion=entry['parametros']['sha256_configuracion'],
                     criterios_calculo=copy.deepcopy(entry['parametros']['limites_digitizacion']))
        result=value.get('resultado') or {}
        for key in ('geometria_version','configuracion_preparacion'):
            if not result.get(key):continue
            if key=='geometria_version':
                if not gg.comprobar_version(self.app.raiz,caso,result[key]).correcta:raise ValueError('Geometría derivada sin vigencia.')
            else:
                data,meta,_=self.app.preparacion_configuracion._cargar(caso,fp,result[key])
                if (meta['sha256_configuracion']!=result['sha256_configuracion']
                        or data['geometria_origen']['version_id']!=result.get('geometria_version')
                        or (meta.get('padre') or {}).get('id')!=entry['parametros']['configuracion_preparacion']
                        or (meta.get('origen') or {}).get('tipo')!='incorporacion_automatica_contornos'):
                    raise ValueError('Preparación derivada sin vínculo con esta geometría y su preparación original.')
        return value
