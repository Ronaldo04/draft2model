"""Configuración en preparación: autoría web persistente antes del contrato formal.

La geometría y los puntos se incorporan automáticamente. Los datos de
ingeniería ausentes permanecen ausentes; guardar un borrador de trabajo no
equivale a aprobarlo ni a habilitar ETABS.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import tempfile
from uuid import uuid4

from . import gestion_configuracion as gc
from . import gestion_geometria as gg
from .gestion_extraccion import _carpeta_propia, _publicar, json_desde_bytes
from .modelo_estructural import comprobar_configuracion
from .plantilla_configuracion import borrador
from .plantilla_configuracion import documento_conexiones
from .validacion_geometria import validar_geometria

CARPETA='configuraciones_en_preparacion'


def _bytes(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode('utf-8')
def _sha(raw):return hashlib.sha256(raw).hexdigest()
def _id(value):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{32}',value):raise ValueError('Versión de preparación inválida.')
    return value


def lecturas_tecnicas(datos):
    """Datos efectivos de lectura; nunca trata un resultado impreso como entrada."""
    output=[]
    for row in datos['candidatos']:
        revision=row.get('revision') or {'estado':'pendiente','historial':[]}
        if revision['estado']=='rechazado':continue
        final=revision['historial'][-1] if revision['estado']!='pendiente' and revision['historial'] else {}
        kind=final.get('tipo_revisado',row['tipo'])
        if kind not in ('propiedad','carga'):continue
        value=final.get('valor_revisado',row['valor_propuesto']);unit=final.get('unidad_revisada',row['unidad'])
        text=row.get('texto_fuente','');symbol=row.get('simbolo','')
        literal_fc=re.search(r"\bf\s*['’′]\s*c\b",text,re.I) is not None
        # Un bloque de notas puede contener f'c, fy y f'm a la vez. Su texto
        # compartido no convierte cada valor del bloque en resistencia del concreto.
        if symbol.strip():
            identificacion_fc=re.fullmatch(r"f\s*['’′]?\s*c",symbol.strip(),re.I) is not None
        else:
            identificacion_fc=re.search(r"\bf\s*['’′]?\s*[ym]\b",text,re.I) is None
        fc=kind=='propiedad' and literal_fc and identificacion_fc
        output.append({'id':row['id'],'tipo':kind,'valor':value,'unidad':unit,'texto':text,
                       'estado_lectura':revision['estado'],'evidencia':copy.deepcopy(row['evidencia']),
                       'resistencia_concreto':fc and unit in ('kgf/cm2','MPa') and type(value) in (int,float) and value>0})
    return output


def conexiones_exactas(geometria):
    """Solapes de aristas exteriores colineales exactas; sin unir por proximidad."""
    if not validar_geometria(geometria).consistente:raise ValueError('Geometría inconsistente.')
    vertices={v['id']:(v['x'],v['y'],v['z']) for v in geometria['vertices']};groups={};rings=set()
    for surface in geometria['superficies']:
        ids=surface['vertices'];xyz=[vertices[p] for p in ids]
        canonical=min(tuple(r[i:]+r[:i]) for r in (xyz,list(reversed(xyz))) for i in range(len(r)))
        if canonical in rings:raise ValueError('Superficies coincidentes completas: revisar si existe una duplicación o una capa intencional.')
        rings.add(canonical)
        # El contrato de compatibilidad admite aristas exteriores, no bordes de huecos.
        for a,b in zip(ids,ids[1:]+ids[:1]):
            p,q=[tuple(Fraction(x) for x in vertices[k]) for k in (a,b)]
            d=tuple(y-x for x,y in zip(p,q));axis=next(i for i,x in enumerate(d) if x)
            direction=tuple(x/d[axis] for x in d)
            moment=(p[1]*direction[2]-p[2]*direction[1],p[2]*direction[0]-p[0]*direction[2],p[0]*direction[1]-p[1]*direction[0])
            key=(direction,moment)
            groups.setdefault(key,[]).append((min(p[axis],q[axis]),max(p[axis],q[axis]),{'superficie':surface['id'],'desde':a,'hasta':b}))
    output=[]
    for key,items in sorted(groups.items()):
        active=[]
        for lo,hi,b in sorted(items,key=lambda row:(row[0],row[1],row[2]['superficie'],row[2]['desde'])):
            active=[row for row in active if row[1]>lo]
            for _,_,a in active:
                if a['superficie']==b['superficie']:continue
                output.append({'id':'CX'+str(len(output)+1),'a':a,'b':b,'fuente':'SOFTWARE-CONEXIONES'})
                if len(output)>30000:raise ValueError('Demasiadas coincidencias para esta preparación; revisar la geometría.')
            active.append((lo,hi,b))
    return output


class ServicioPreparacionConfiguracion:
    def __init__(self,app):self.app=app

    def _caso(self,caso,fp):
        folder,manifest,actual=self.app.expediente(caso)
        if actual!=fp:raise ValueError('El expediente cambió.')
        for source in manifest['archivos']:self.app._original(caso,source['id'])
        return Path(folder),manifest

    def _leer(self,path):
        if path.resolve()!=path.absolute() or path.is_symlink() or path.stat().st_size>2*1024*1024:
            raise ValueError('Documento de preparación inválido o excesivo.')
        return path.read_bytes()

    def _cargar(self,caso,fp,ident):
        folder,_=self._caso(caso,fp);base=_carpeta_propia(folder,CARPETA);current=_id(ident);seen=set();initial=None
        expected=None
        while current is not None:
            if current in seen:raise ValueError('Cadena de preparación circular.')
            seen.add(current);target=_carpeta_propia(base,_id(current))
            raw=self._leer(target/'configuracion.json');meta_raw=self._leer(target/'registro.json')
            data=json_desde_bytes(raw,'configuración en preparación');meta=json_desde_bytes(meta_raw,'registro de preparación')
            if (meta.get('contrato')!='draft2model.configuracion_en_preparacion' or meta.get('id')!=current
                    or meta.get('caso')!=caso or meta.get('expediente_sha256')!=fp or meta.get('sha256_configuracion')!=_sha(raw)
                    or data.get('caso')!=caso or data.get('revision')!={'estado':'borrador','aprobacion':None}
                    or data.get('geometria_origen')!=meta.get('geometria_origen')):
                raise ValueError('Configuración y registro no corresponden.')
            if expected and expected!={'id':current,'sha256_registro':_sha(meta_raw),'sha256_configuracion':_sha(raw)}:
                raise ValueError('Vínculo de la preparación anterior alterado.')
            geo=gg.consultar_version(self.app.raiz,caso,data['geometria_origen']['version_id'])
            if (not geo.comprobacion.correcta or data['geometria_origen']['sha256_geometria']!=geo.comprobacion.sha256_geometria
                    or data['geometria_origen']['huella_contenido']!=geo.comprobacion.huella_contenido):
                raise ValueError('Geometría de preparación sin vigencia.')
            if initial is None:initial=(data,meta,_sha(meta_raw))
            expected=meta.get('padre');current=expected['id'] if expected else None
        return initial

    def _guardar(self,caso,fp,data,*,padre=None,origen=None):
        folder,_=self._caso(caso,fp);ident=uuid4().hex;raw=_bytes(data)
        if len(raw)>1500*1024:raise ValueError('Configuración de preparación demasiado grande.')
        meta={'contrato':'draft2model.configuracion_en_preparacion','version_contrato':'0.1.0','id':ident,
              'caso':caso,'expediente_sha256':fp,'sha256_configuracion':_sha(raw),
              'geometria_origen':copy.deepcopy(data['geometria_origen']),'padre':padre,
              'creado_utc':datetime.now(timezone.utc).isoformat(),'origen':origen,
              'aprobacion_ingenieria':None}
        _publicar(folder,CARPETA,ident,{'configuracion.json':raw,'registro.json':_bytes(meta)})
        return self.consultar(caso,fp,ident)

    def crear(self,body):
        if not isinstance(body,dict) or set(body)!={'caso','expediente_sha256','geometria'}:raise ValueError('Campos de preparación inválidos.')
        with self.app.lock:
            caso,fp=body['caso'],body['expediente_sha256'];folder,manifest=self._caso(caso,fp)
            version=_id(body['geometria']);geo=gg.consultar_version(self.app.raiz,caso,version)
            if not geo.comprobacion.correcta:raise ValueError('Geometría no comprobada.')
            data=borrador(self.app.raiz,caso,version,version_contrato='0.5.0')
            data['datos_sinteticos']=bool(geo.comprobacion.validacion.get('datos_sinteticos'))
            data['fuentes']=[{'id':'PLANO-'+s['id'],'descripcion':'Original registrado: '+s['nombre_original'],
                             'referencia':s['archivo'],'sha256':s['sha256']} for s in manifest['archivos']]
            template_path=Path(__file__).with_name('plantilla_configuracion.py');template_sha=_sha(template_path.read_bytes())
            data['fuentes'].append({'id':'SOFTWARE-PLANTILLA','descripcion':'Perfil de representación propuesto por el programa; por revisar.',
                                   'referencia':'draft2model/plantilla_configuracion.py','sha256':template_sha})
            data['plantilla']={'id':'shell-frame-lineal','version':'0.1.0','sha256':template_sha,
                'representacion':'Superficies y barras en una propuesta elástica lineal; representación estructural por revisar.',
                'limitaciones':['La preparación no acredita equivalencia estructural ni cumplimiento normativo.',
                                'Materiales, cargas, apoyos y representación de cada elemento requieren datos y revisión.'],
                'fuente':'SOFTWARE-PLANTILLA'}
            origin={'tipo':'preparacion_automatica','geometria':version,'frames_vinculados':0,'incidencias':[]}
            base=_carpeta_propia(folder,'reconstrucciones')
            if base.is_dir():
                for path in sorted(base.iterdir()):
                    if not re.fullmatch('[0-9a-f]{32}',path.name):continue
                    value=self.app.reconstruccion.consultar(caso,fp,path.name)
                    result=value.get('resultado') or {}
                    if result.get('geometria_version')!=version:continue
                    if value.get('simulado') and not data['datos_sinteticos']:
                        raise ValueError('No vincular resultados sintéticos con una geometría real.')
                    for frame in result.get('frames_propuestos',[]):
                        refs=frame.get('puntos',[]);evidence=frame.get('evidencias',[])
                        source='PLANO-'+evidence[0]['archivo_id'] if evidence else None
                        if len(refs)!=2 or source not in {s['id'] for s in data['fuentes']}:
                            origin['incidencias'].append('Elemento '+str(frame.get('id'))+': faltan extremos o fuente de la lectura.');continue
                        data['frames'].append({'id':frame['id'],'inicio':refs[0],'fin':refs[1],
                                               'tipo':frame['tipo'],'fuente':source})
                        data['asignaciones_frames'].append({'objetivo':frame['id'],'seccion':None,'fuente':source})
                    origin.update(reconstruccion=path.name,frames_vinculados=len(data['frames']))
                    break
            return self._guardar(caso,fp,data,origen=origin)

    def consultar(self,caso,fp,ident):
        data,meta,meta_sha=self._cargar(caso,fp,ident)
        validation=comprobar_configuracion(self.app.raiz,data).a_dict()
        return {'id':ident,'caso':caso,'expediente_sha256':fp,'datos':data,'registro':meta,
                'sha256_registro':meta_sha,'sha256_configuracion':meta['sha256_configuracion'],
                'validacion':validation,'puede_registrar':validation['consistente'],
                'aprueba_ingenieria':False,'ejecuta_etabs':False}

    def listar(self,caso,fp):
        folder,_=self._caso(caso,fp);base=_carpeta_propia(folder,CARPETA)
        return sorted(p.name for p in base.iterdir() if re.fullmatch('[0-9a-f]{32}',p.name)) if base.is_dir() else []

    def para_geometria(self,caso,fp,geometria):
        _id(geometria);versions=[];parents=set()
        for ident in self.listar(caso,fp):
            data,meta,_=self._cargar(caso,fp,ident)
            if data['geometria_origen']['version_id']!=geometria:continue
            versions.append(ident)
            if meta['padre']:parents.add(meta['padre']['id'])
        leaves=sorted(set(versions)-parents)
        return {'versiones':leaves,'reutilizable':leaves[0] if len(leaves)==1 else None,'crear':not versions}

    def guardar(self,body):
        keys={'caso','expediente_sha256','version','sha256_configuracion','configuracion_json'}
        if not isinstance(body,dict) or set(body)!=keys or not isinstance(body['configuracion_json'],str):raise ValueError('Campos de guardado inválidos.')
        with self.app.lock:
            caso,fp=body['caso'],body['expediente_sha256'];old,meta,meta_sha=self._cargar(caso,fp,body['version'])
            if body['sha256_configuracion']!=meta['sha256_configuracion']:raise ValueError('El borrador cambió.')
            raw=body['configuracion_json'].encode('utf-8')
            if len(raw)>1500*1024:raise ValueError('Borrador demasiado grande.')
            data=json_desde_bytes(raw,'borrador de ingeniería')
            if (not isinstance(data,dict) or data.get('revision')!={'estado':'borrador','aprobacion':None}
                    or any(data.get(k)!=old[k] for k in ('id','caso','contrato','version_contrato','datos_sinteticos','geometria_origen'))):
                raise ValueError('No cambiar identidad, origen, naturaleza ni aprobación del borrador.')
            parent={'id':body['version'],'sha256_registro':meta_sha,'sha256_configuracion':meta['sha256_configuracion']}
            return self._guardar(caso,fp,data,padre=parent,origen={'tipo':'edicion_en_interfaz'})

    def leer_propiedades(self,body):
        if not isinstance(body,dict) or set(body)!={'caso','expediente_sha256','extraccion'}:raise ValueError('Campos de lectura inválidos.')
        self._caso(body['caso'],body['expediente_sha256'])
        value=self.app.version(body['caso'],_id(body['extraccion']))
        if value['expediente_sha256']!=body['expediente_sha256']:raise ValueError('La lectura pertenece a otro expediente.')
        return {'extraccion':body['extraccion'],'huella_lectura':value['huella'],'lecturas':lecturas_tecnicas(value['datos']),
                'aprueba_lecturas':False,'aprueba_ingenieria':False}

    def material_desde_lectura(self,body):
        keys={'caso','expediente_sha256','version','sha256_configuracion','extraccion','huella_lectura','lectura',
              'material_id','peso_kN_m3','concreto_normal_sin_ensayos','declaracion','confirmacion_explicita'}
        if not isinstance(body,dict) or set(body)!=keys or body['confirmacion_explicita'] is not True:
            raise ValueError('Confirma la aplicación de esta lectura al material.')
        if body['concreto_normal_sin_ensayos'] is not True:raise ValueError('La fórmula requiere declarar concreto de peso normal y ausencia de ensayos sustitutorios.')
        ident=body['material_id'];weight=body['peso_kN_m3'];declaration=body['declaracion']
        if not isinstance(ident,str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_-]{0,63}',ident):raise ValueError('Identificador del material inválido.')
        import math
        from datetime import date
        if type(weight) not in (int,float) or not math.isfinite(weight) or weight<=0:raise ValueError('Peso específico positivo y finito requerido.')
        if (not isinstance(declaration,dict) or set(declaration)!={'declarado_por','fecha','alcance'}
                or any(not isinstance(v,str) or not v.strip() or len(v)>2000 for v in declaration.values())):
            raise ValueError('Completa declarante, fecha y alcance de la decisión del material.')
        try:
            if len(declaration['fecha'])!=10:raise ValueError()
            date.fromisoformat(declaration['fecha'])
        except ValueError:raise ValueError('Fecha de declaración inválida.') from None
        with self.app.lock:
            caso,fp=body['caso'],body['expediente_sha256'];data,meta,meta_sha=self._cargar(caso,fp,body['version'])
            if meta['sha256_configuracion']!=body['sha256_configuracion']:raise ValueError('La preparación cambió.')
            if any(m['id']==ident for m in data['materiales']):raise ValueError('Ese material ya existe; no se sobrescribe automáticamente.')
            reads=self.leer_propiedades({k:body[k] for k in ('caso','expediente_sha256','extraccion')})
            if reads['huella_lectura']!=body['huella_lectura']:raise ValueError('La lectura cambió; vuelve a consultarla.')
            reading=next((r for r in reads['lecturas'] if r['id']==body['lectura']),None)
            if not reading or not reading['resistencia_concreto']:raise ValueError('La lectura no identifica una resistencia de concreto utilizable.')
            from .normativa_rne import modulo_concreto
            from .configuracion_normativa import fuente_oficial
            properties=modulo_concreto(reading['valor'],reading['unidad'])
            norm=fuente_oficial('RNE-E060-DS010-2009','8.5.2 y 8.5.4')
            source='LECTURA-'+ident;decision='DECISION-'+ident
            data['fuentes']=[f for f in data['fuentes'] if f['id'] not in (source,decision,norm['id'])]+[
                {'id':source,'descripcion':'Resistencia detectada; estado de lectura: '+reading['estado_lectura'],
                 'referencia':'extracciones/'+body['extraccion']+'/extraccion.json#'+reading['id'],'sha256':body['huella_lectura']},
                {'id':decision,'descripcion':'Clase de concreto, peso específico y condiciones de aplicación declaradas en la interfaz.',
                 'referencia':'Decisión conservada en el origen del registro de esta preparación.','sha256':_sha(_bytes(body))},norm]
            data['materiales'].append({'id':ident,'tipo':'isotropo_lineal','E_kN_m2':properties['Ec_kN_m2'],
                'poisson':properties['nu_derivado_isotropia'],'peso_kN_m3':weight,'fuente':norm['id']})
            data['hipotesis'] += [{'id':'H-'+ident+'-FC','descripcion':f"Resistencia usada: {reading['valor']} {reading['unidad']}; lectura {reading['id']} ({reading['estado_lectura']}). No se modifica su revisión.",'fuente':source},
                {'id':'H-'+ident+'-COND','descripcion':f"Concreto de peso normal sin ensayos sustitutorios declarado; peso específico {weight} kN/m³. E y G calculados con E.060 8.5.2/8.5.4; Poisson derivado de isotropía. No implica aprobación del modelo.",'fuente':decision}]
            parent={'id':body['version'],'sha256_registro':meta_sha,'sha256_configuracion':meta['sha256_configuracion']}
            return self._guardar(caso,fp,data,padre=parent,origen={'tipo':'material_desde_lectura_en_interfaz','entrada':copy.deepcopy(body),'lectura':reading,'calculo':properties})

    def registrar(self,body):
        if not isinstance(body,dict) or set(body)!={'caso','expediente_sha256','version','sha256_configuracion'}:raise ValueError('Campos de registro inválidos.')
        with self.app.lock:
            caso,fp=body['caso'],body['expediente_sha256'];data,meta,_=self._cargar(caso,fp,body['version'])
            if body['sha256_configuracion']!=meta['sha256_configuracion']:raise ValueError('Borrador cambiado.')
            validation=comprobar_configuracion(self.app.raiz,data)
            if not validation.consistente:return {'registrada':False,'validacion':validation.a_dict(),'aprueba_ingenieria':False}
            folder,_=self._caso(caso,fp)
            target=_carpeta_propia(_carpeta_propia(folder,CARPETA),_id(body['version']))
            marker=target/'registro_formal.json'
            if marker.exists():
                record=json_desde_bytes(self._leer(marker),'registro formal')
                if record.get('estado')!='registrada':raise ValueError('Registro interrumpido; revisar antes de repetir.')
                formal=gc.consultar(self.app.raiz,caso,record['configuracion'])
                if formal['configuracion']!=data:raise ValueError('El registro formal no corresponde al borrador.')
                return record
            with marker.open('xb') as stream:stream.write(_bytes({'estado':'iniciado_no_repetir','version':body['version']}))
            with tempfile.TemporaryDirectory(prefix='.config-preparada-',dir=folder) as temp:
                path=Path(temp)/'configuracion.json';path.write_bytes(_bytes(data))
                result=gc.importar(self.app.raiz,caso,path)
            record={'registrada':True,'configuracion':result['id'],'caso':caso,'expediente_sha256':fp,
                    'aprueba_ingenieria':False,'estado':'registrada','revision':'borrador'}
            marker.write_bytes(_bytes(record))
            return record

    def proponer_conexiones(self,body):
        keys={'caso','expediente_sha256','version','sha256_configuracion'}
        if not isinstance(body,dict) or set(body)!=keys:raise ValueError('Campos de propuesta inválidos.')
        data,meta,_=self._cargar(body['caso'],body['expediente_sha256'],body['version'])
        if meta['sha256_configuracion']!=body['sha256_configuracion']:raise ValueError('Preparación modificada.')
        geo=gg.consultar_version(self.app.raiz,body['caso'],data['geometria_origen']['version_id']).geometria
        proposal=conexiones_exactas(geo)
        algorithm=_sha(Path(__file__).read_bytes())
        return {'conexiones':proposal,'cantidad':len(proposal),'requiere_revision_ingeniero':True,
                'sha256_propuesta':_sha(_bytes({'conexiones':proposal,'algoritmo':algorithm})),
                'modifica_configuracion':False,'une_por_proximidad':False,
                'limites':['Solo bordes exteriores con solape de longitud positiva y colinealidad exacta.',
                           'No conecta por proximidad, contacto puntual, cruces interiores ni bordes de aberturas.',
                           'El ingeniero debe excluir juntas o contactos que no transmitan esfuerzos.']}

    def declarar_conexiones(self,body):
        keys={'caso','expediente_sha256','version','sha256_configuracion','declaracion','confirmacion_explicita','sha256_propuesta','conexiones_seleccionadas'}
        if not isinstance(body,dict) or set(body)!=keys or body['confirmacion_explicita'] is not True:
            raise ValueError('Confirma la revisión de la continuidad propuesta.')
        with self.app.lock:
            caso,fp=body['caso'],body['expediente_sha256'];data,meta,meta_sha=self._cargar(caso,fp,body['version'])
            if meta['sha256_configuracion']!=body['sha256_configuracion']:raise ValueError('Preparación modificada.')
            geo=gg.consultar_version(self.app.raiz,caso,data['geometria_origen']['version_id']).geometria
            proposed=self.proponer_conexiones({k:body[k] for k in ('caso','expediente_sha256','version','sha256_configuracion')})
            if body['sha256_propuesta']!=proposed['sha256_propuesta']:raise ValueError('La propuesta cambió; vuelve a calcularla y revisarla.')
            selected=body['conexiones_seleccionadas'];available={c['id'] for c in proposed['conexiones']}
            if (not isinstance(selected,list) or any(not isinstance(x,str) for x in selected)
                    or len(set(selected))!=len(selected) or not set(selected)<=available):raise ValueError('Selección de conexiones inválida.')
            proposal=[c for c in proposed['conexiones'] if c['id'] in selected]
            declaration=body['declaracion']
            if (not isinstance(declaration,dict) or set(declaration)!={'declarado_por','fecha','alcance'}
                    or any(not isinstance(v,str) or not v.strip() or len(v)>2000 for v in declaration.values())):
                raise ValueError('Completa declarante, fecha y alcance de la revisión.')
            try:
                from datetime import date
                if len(declaration['fecha'])!=10:raise ValueError()
                date.fromisoformat(declaration['fecha'])
            except ValueError:raise ValueError('Fecha de revisión inválida.') from None
            sources=[{'id':'SOFTWARE-CONEXIONES','descripcion':'Propuesta de bordes colineales exactos calculada por el programa y seleccionada por el revisor.',
                      'referencia':'draft2model/preparacion_configuracion.py','sha256':_sha(Path(__file__).read_bytes())}]
            data['fuentes']=[f for f in data['fuentes'] if f['id']!='SOFTWARE-CONEXIONES']+sources
            data['conexiones_borde']=documento_conexiones(geo,proposal,sources,body['declaracion'])
            data['malla']['fuente']='SOFTWARE-CONEXIONES'
            parent={'id':body['version'],'sha256_registro':meta_sha,'sha256_configuracion':meta['sha256_configuracion']}
            return self._guardar(caso,fp,data,padre=parent,origen={'tipo':'continuidad_revisada_en_interfaz',
                'cantidad_conexiones':len(proposal),'declaracion':copy.deepcopy(body['declaracion'])})
