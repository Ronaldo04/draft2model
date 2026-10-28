"""Contraste independiente de lecturas dinámicas; no calcula ni aprueba modelos."""
import math
import hashlib
from pathlib import Path
from .modelo_estructural import comprobar_configuracion, huella_configuracion


def comprobar(raiz, configuracion, opciones, lectura, *, modelo_esperado):
    checked=comprobar_configuracion(raiz,configuracion)
    if not checked.apto_para_adaptador:raise ValueError('Configuración/geometría no vigentes y aprobadas.')
    if not isinstance(lectura,dict) or lectura.get('solo_lectura') is not True or lectura.get('unidades')!='kN_m_C':
        raise ValueError('Lectura independiente y unidades explícitas requeridas.')
    model=Path(modelo_esperado)
    if (not model.is_absolute() or model.resolve()!=model or model.suffix.lower()!='.edb'
            or not model.is_file() or Path(str(lectura.get('modelo','')))!=model):
        raise ValueError('La lectura debe corresponder al EDB esperado exacto, sin enlaces.')
    model_sha=hashlib.sha256(model.read_bytes()).hexdigest()
    if not isinstance(opciones,dict):raise ValueError('Opciones explícitas requeridas.')
    entries=lectura.get('lecturas')
    if not isinstance(entries,list):raise ValueError('Faltan lecturas.')
    getters={}
    for row in entries:
        if (not isinstance(row,dict) or type(row.get('retorno')) is not int or row['retorno']!=0
                or not isinstance(row.get('valores'),dict) or not isinstance(row.get('interfaz'),str)
                or not isinstance(row.get('metodo'),str) or not (isinstance(row.get('nombre'),str)
                    or (row.get('nombre') is None and row.get('interfaz')=='cPropMaterial' and row.get('metodo')=='GetMassSource_1'))):
            raise ValueError('Getter fallido o sin valores.')
        key=(row.get('interfaz'),row.get('metodo'),row.get('nombre'))
        if key in getters and getters[key]!=row['valores']:raise ValueError('Lecturas duplicadas contradictorias.')
        getters[key]=row['valores']
    tables={}
    for table in lectura.get('tablas',[]):
        if not isinstance(table,dict) or table.get('tabla') in tables or not isinstance(table.get('filas'),list):
            raise ValueError('Tablas inválidas o ambiguas.')
        tables[table['tabla']]=table['filas']
    controls=[];missing=[]
    def equal(actual,expected):
        if isinstance(expected,bool):return actual is expected
        if isinstance(expected,(int,float)):
            return type(actual) in (int,float) and math.isfinite(actual) and math.isclose(actual,expected,rel_tol=1e-10,abs_tol=1e-10)
        if isinstance(expected,list):return isinstance(actual,list) and len(actual)==len(expected) and all(equal(a,b) for a,b in zip(actual,expected))
        return actual==expected
    def control(label,actual,expected):
        controls.append({'control':label,'observado':actual,'esperado':expected,'coincide':equal(actual,expected)})
    def get(interface,method,name,field):
        data=getters.get((interface,method,name),{})
        if field not in data:missing.append(interface+'.'+method+'/'+name+'/'+field)
        return data.get(field)
    def table_row(table,name):
        rows=[r for r in tables.get(table,[]) if isinstance(r,dict) and r.get('Name')==name]
        if len(rows)!=1:
            missing.append(table+'/'+name+' (fila única requerida)');return {}
        return rows[0]
    def number(value):
        try:result=float(value)
        except (ValueError,TypeError):return None
        return result if math.isfinite(result) else None
    count=0
    for case in configuracion['casos']:
        name=case['id'];params=case['parametros']
        if case['tipo']=='modal_eigen':
            count+=1;eigen=opciones.get('parametros_modales',{}).get(name)
            if not isinstance(eigen,dict):raise ValueError('Opciones Eigen explícitas requeridas.')
            for field in ('MinModes','MaxModes'):
                control(name+'/'+field,get('cCaseModalEigen','GetNumberModes',name,field),params['numero_modos'])
            expected={'EigenShiftFreq':eigen['frecuencia_desplazamiento_hz'],'EigenCutOff':eigen['frecuencia_corte_hz'],
                      'EigenTol':eigen['tolerancia'],'AllowAutoFreqShift':1 if eigen['desplazamiento_automatico'] else 0}
            for field,value in expected.items():control(name+'/'+field,get('cCaseModalEigen','GetParameters',name,field),value)
            control(name+'/cargas_iniciales',get('cCaseModalEigen','GetLoads',name,'NumberLoads'),0)
        elif case['tipo']=='espectro_respuesta':
            count+=1;interface='cCaseResponseSpectrum'
            control(name+'/modal',get(interface,'GetModalCase',name,'ModalCase'),params['modal'])
            loads={'NumberLoads':1,'LoadName':[{'UX':'U1','UY':'U2','UZ':'U3'}[params['direccion']]],
                   'Func':[params['espectro']],'SF':[params['factor']],'CSys':['Global'],'Ang':[0.0]}
            for field,value in loads.items():control(name+'/'+field,get(interface,'GetLoads',name,field),value)
            control(name+'/excentricidad',get(interface,'GetEccentricity',name,'Eccen'),opciones['excentricidad_espectral'][name])
            control(name+'/amortiguamiento',get(interface,'GetDampConstant',name,'Damp'),params['amortiguamiento'])
            for field,value in [('NumberItems',0),('Mode',[]),('Damp',[])]:
                control(name+'/sin_override/'+field,get(interface,'GetDampOverrides',name,field),value)
            response=table_row('Load Case Definitions - Response Spectrum',name)
            control(name+'/combinacion_modal',response.get('ModalCombo'),params['combinacion_modal'])
            control(name+'/respuesta_rigida',response.get('RigidResp'),'No')
            damping=table_row('Load Case Definitions - Damping - Modal',name)
            control(name+'/tipo_amortiguamiento',damping.get('DampType'),'Constant')
            control(name+'/amortiguamiento_tabla',number(damping.get('ConstDamp')),params['amortiguamiento'])
    if not count:raise ValueError('La configuración no tiene casos dinámicos.')
    for function in configuracion['espectros']:
        name=function['id']
        for field,value in [('NumberItems',len(function['puntos'])),('MyTime',[p[0] for p in function['puntos']]),('Value',[p[1] for p in function['puntos']])]:
            actual=get('cFunction','GetValues',name,field)
            raw=getters.get(('cFunction','GetValues',name),{})
            n=raw.get('NumberItems');times=raw.get('MyTime');values=raw.get('Value')
            if (field in ('MyTime','Value') and type(n) is int and n>0
                    and isinstance(times,list) and isinstance(values,list)
                    and len(times)==len(values)==n+1 and times[0]==values[0]==0):actual=actual[1:]
            control(name+'/'+field,actual,value)
        rows=[r for r in tables.get('Functions - Response Spectrum - User Defined',[]) if isinstance(r,dict) and r.get('Name')==name and r.get('DampRatio') not in ('',None)]
        if not rows:missing.append('DampRatio/'+name)
        control(name+'/amortiguamiento_funcion',[number(r.get('DampRatio')) for r in rows],
                [opciones['amortiguamiento_funciones'][name]]*len(rows))
    if hashlib.sha256(model.read_bytes()).hexdigest()!=model_sha:
        raise ValueError('El EDB cambió durante la comprobación.')
    return {'correcta':not missing and all(c['coincide'] for c in controls),'huella_configuracion':huella_configuracion(configuracion),
            'modelo':{'archivo':str(model),'sha256':model_sha},
            'datos_sinteticos':configuracion['datos_sinteticos'],'controles':controls,'faltantes':missing,
            'aprueba_modelo':False,'certifica_seguridad':False,'tolerancia_numerica_software':1e-10,
            'aviso':'Contrasta datos declarados y lecturas; no autentica productor ni verifica respuesta física.'}
