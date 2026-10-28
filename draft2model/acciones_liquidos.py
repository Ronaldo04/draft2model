"""Derivación hidrostática declarada sobre superficies/huecos; nunca aplica cargas."""
from __future__ import annotations

import copy
from datetime import date
import hashlib
import json
import math
import re

from . import contratos as c
from .validacion_geometria import validar_geometria

CONTRATO = 'draft2model.acciones_liquidos'
VERSION = '0.1.0'
EPS = 1e-12  # criterio computacional, no tolerancia de ingeniería


class ErrorAccionesLiquidos(ValueError):
    """Declaración/fuentes/geometría incompatibles o cálculo no representable."""


def _objeto(valor, campos, ruta):
    if not isinstance(valor, dict) or set(valor) != set(campos):
        raise ErrorAccionesLiquidos(ruta+': campos exactos requeridos: '+', '.join(campos))


def _numero(valor):
    return type(valor) in (int, float) and math.isfinite(valor)


def _canonico(valor):
    def revisar(x):
        if isinstance(x, dict):
            if any(not isinstance(k, str) for k in x):
                raise ErrorAccionesLiquidos('JSON requiere claves de texto.')
            for v in x.values(): revisar(v)
        elif isinstance(x, list):
            for v in x: revisar(v)
        elif x is not None and type(x) not in (str, bool, int, float):
            raise ErrorAccionesLiquidos('Se requieren tipos JSON explícitos.')
    revisar(valor)
    try:
        return json.dumps(valor,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')
    except (ValueError,TypeError,OverflowError,RecursionError) as exc:
        raise ErrorAccionesLiquidos('JSON no representable de forma estricta.') from exc


def _sha(valor): return hashlib.sha256(_canonico(valor)).hexdigest()


def _texto(valor, ruta):
    if not isinstance(valor,str) or not valor.strip():
        raise ErrorAccionesLiquidos(ruta+': se requiere texto no vacío.')


def _revision(valor, *, referencias=False):
    campos=['estado','declarada_por','fecha','motivo']+(['fuentes'] if referencias else [])
    _objeto(valor,campos,'revision')
    if valor['estado'] != 'revisado':
        raise ErrorAccionesLiquidos('La revisión debe estar declarada revisada; no se verifica identidad profesional.')
    for clave in ('declarada_por','fecha','motivo'): _texto(valor[clave],'revision.'+clave)
    try:
        fecha = date.fromisoformat(valor['fecha']).isoformat()
    except ValueError as exc:
        raise ErrorAccionesLiquidos('Fecha ISO no válida.') from exc
    if fecha != valor['fecha']:
        raise ErrorAccionesLiquidos('Fecha ISO no válida.')


def _refs(valor, tabla):
    if not isinstance(valor,list) or not valor or any(not isinstance(v,str) or v not in tabla for v in valor) or len(set(valor)) != len(valor):
        raise ErrorAccionesLiquidos('Declare IDs de fuentes existentes, revisadas, distintos y no vacíos.')
    return set(valor)


def declarar_acciones_liquidos(geometria, declaracion, fuentes):
    """Vincula parámetros EXPLÍCITOS, geometría completa y fuentes revisadas por SHA.

    No requiere aprobación geométrica para derivar software; no la concede.
    `fuentes` son objetos JSON proporcionados por el llamador, no rutas ni red.
    """
    try:
        _canonico(geometria); _canonico(declaracion); _canonico(fuentes)
        validacion=validar_geometria(geometria)
        if not validacion.consistente or validacion.faltantes or geometria.get('version_contrato') != c.VERSION_GEOMETRIA_ABERTURAS:
            raise ErrorAccionesLiquidos('Se requiere geometría0.3 consistente y completa, sin inferir datos.')
        campos=('contrato','version_contrato','id','nivel_libre_z_m','peso_especifico_kn_m3','origen_momentos_m','superficies','revision')
        _objeto(declaracion,campos,'declaracion')
        if declaracion['contrato'] != CONTRATO or declaracion['version_contrato'] != VERSION:
            raise ErrorAccionesLiquidos('Contrato/version de acciones no admitidos.')
        if not isinstance(declaracion['id'],str) or re.fullmatch(c.PATRON_ID,declaracion['id']) is None:
            raise ErrorAccionesLiquidos('ID de declaración no válido.')
        if not _numero(declaracion['nivel_libre_z_m']) or not _numero(declaracion['peso_especifico_kn_m3']) or declaracion['peso_especifico_kn_m3'] <= 0:
            raise ErrorAccionesLiquidos('Nivel libre finito y peso específico positivo finito explícitos en m/kN/m3.')
        origen=declaracion['origen_momentos_m']
        if not isinstance(origen,list) or len(origen)!=3 or not all(_numero(v) for v in origen):
            raise ErrorAccionesLiquidos('Origen de momentos XYZ explícito, finito y en metros.')
        if not isinstance(fuentes,list) or not fuentes:
            raise ErrorAccionesLiquidos('Declare fuentes revisadas explícitas.')
        tabla={}
        for fuente in fuentes:
            _objeto(fuente,('id','contenido','revision'),'fuente')
            ident=fuente['id']
            if not isinstance(ident,str) or re.fullmatch(c.PATRON_ID,ident) is None or ident in tabla:
                raise ErrorAccionesLiquidos('ID de fuente ausente, inválido o duplicado.')
            if not isinstance(fuente['contenido'],dict) or not fuente['contenido']:
                raise ErrorAccionesLiquidos('Fuente requiere contenido JSON explícito no vacío.')
            _revision(fuente['revision']); tabla[ident]=fuente
        _revision(declaracion['revision'],referencias=True)
        usados=_refs(declaracion['revision']['fuentes'],tabla)
        seleccion=declaracion['superficies']; existentes={s['id'] for s in geometria['superficies']}; vistos=set()
        if not isinstance(seleccion,list) or not seleccion:
            raise ErrorAccionesLiquidos('Seleccione anfitrionas explícitas.')
        for item in seleccion:
            # Opcional (R253): desplazamiento de la cara mojada FÍSICA respecto de la superficie media declarada, medido hacia el
            # líquido (opuesto a la normal de carga). La presión se evalúa en esa cara; sin la clave, el resultado no cambia.
            if 'desplazamiento_cara_m' in item:
                _objeto(item,('superficie','sentido_normal','fuentes','desplazamiento_cara_m'),'seleccion')
                if not _numero(item['desplazamiento_cara_m']) or item['desplazamiento_cara_m'] < 0:
                    raise ErrorAccionesLiquidos('desplazamiento_cara_m: número finito >= 0 (m) hacia el líquido.')
            else:
                _objeto(item,('superficie','sentido_normal','fuentes'),'seleccion')
            ident=item['superficie']
            if not isinstance(ident,str) or ident not in existentes or ident in vistos:
                raise ErrorAccionesLiquidos('Superficie anfitriona no existente o repetida.')
            if type(item['sentido_normal']) is not int or item['sentido_normal'] not in (-1,1):
                raise ErrorAccionesLiquidos('Cada anfitriona requiere sentido_normal entero +1 o -1 declarado.')
            vistos.add(ident); usados.update(_refs(item['fuentes'],tabla))
        if usados != set(tabla):
            raise ErrorAccionesLiquidos('No adjunte fuentes ajenas a la declaración/selección.')
        contenido={'contrato':CONTRATO,'version_contrato':VERSION,'declaracion':copy.deepcopy(declaracion),
                   'geometria_origen':{'id':geometria['id'],'version_contrato':geometria['version_contrato'],
                                      'huella_contenido':validacion.huella_contenido,'sha256_json_canonico_completo':_sha(geometria)},
                   'fuentes':[{'id':ident,'sha256_json_canonico_completo':_sha(fuente)} for ident,fuente in sorted(tabla.items())],
                   'estado':'derivacion_pendiente','aplicado':False,'ejecutable':False,'aprobacion_ingenieria':None,
                   'identidad_revisor':'declarada_no_verificada'}
        return {**contenido,'huella_declaracion':_sha(contenido)}
    except (TypeError,KeyError,OverflowError,RecursionError) as exc:
        raise ErrorAccionesLiquidos('Declaración no válida o no representable.') from exc


def _resta(a,b): return [x-y for x,y in zip(a,b)]
def _cruz(a,b): return [math.fsum((a[1]*b[2],-a[2]*b[1])), math.fsum((a[2]*b[0],-a[0]*b[2])), math.fsum((a[0]*b[1],-a[1]*b[0]))]
def _orient(a,b,p): return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])


def _triangular(puntos,normal,eps):
    """Ear clipping de contorno simple validado; no fan sobre un polígono cóncavo."""
    origen=puntos[0];escala=max(abs(x) for p in puntos for x in _resta(p,origen))
    eje=max(range(3),key=lambda k:abs(normal[k]))
    xy=[tuple((x-origen[k])/escala for k,x in enumerate(p) if k!=eje) for p in puntos]
    doble=math.fsum(xy[i][0]*xy[(i+1)%len(xy)][1]-xy[(i+1)%len(xy)][0]*xy[i][1] for i in range(len(xy)))
    signo=1 if doble>0 else -1
    activos=list(range(len(puntos))); triangulos=[]
    while len(activos)>3:
        for j,b in enumerate(activos):
            a,c=activos[j-1],activos[(j+1)%len(activos)]
            if signo*_orient(xy[a],xy[b],xy[c])<=eps: continue
            if any(all(signo*_orient(xy[u],xy[v],xy[p])>=-eps for u,v in ((a,b),(b,c),(c,a))) for p in activos if p not in (a,b,c)):continue
            triangulos.append((a,b,c));del activos[j];break
        else:raise ErrorAccionesLiquidos('Triangulación numéricamente ambigua: no se repara ni sustituye el contorno.')
    if signo*_orient(*(xy[i] for i in activos))<=eps:
        raise ErrorAccionesLiquidos('Triángulo final degenerado bajo el criterio computacional.')
    triangulos.append(tuple(activos))
    return triangulos


def _presion(z,nivel,gamma):
    profundidad=nivel-z
    if not math.isfinite(profundidad):raise ErrorAccionesLiquidos('Profundidad no representable.')
    valor=gamma*max(0,profundidad)
    if not math.isfinite(valor) or (profundidad>0 and valor==0):raise ErrorAccionesLiquidos('Presión positiva no representable.')
    return valor


def _recortar(vertices,nivel):
    salida=[]
    for a,b in zip(vertices,vertices[1:]+vertices[:1]):
        da,db=nivel-a['xyz_m'][2],nivel-b['xyz_m'][2]
        if not math.isfinite(da) or not math.isfinite(db):raise ErrorAccionesLiquidos('Recorte no representable.')
        dentro_a,dentro_b=da>=0,db>=0
        if dentro_a:salida.append(copy.deepcopy(a))
        if dentro_a != dentro_b:
            escala=max(abs(da),abs(db));aa,bb=abs(da)/escala,abs(db)/escala;t=aa/(aa+bb)
            xyz=[(1-t)*x+t*y for x,y in zip(a['xyz_m'],b['xyz_m'])];xyz[2]=nivel
            if not all(math.isfinite(x) for x in xyz):raise ErrorAccionesLiquidos('Intersección no representable.')
            salida.append({'xyz_m':xyz,'origen':{'tipo':'interseccion_calculada_no_medida','arista_triangulacion':[a['vertice_id'],b['vertice_id']],'fraccion_desde_primero':t}})
    sin_repetidos=[]
    for punto in salida:
        if not sin_repetidos or punto['xyz_m']!=sin_repetidos[-1]['xyz_m']:sin_repetidos.append(punto)
    if len(sin_repetidos)>1 and sin_repetidos[0]['xyz_m']==sin_repetidos[-1]['xyz_m']:sin_repetidos.pop()
    return sin_repetidos if any(p['xyz_m'][2]<nivel for p in sin_repetidos) else []


def _integral_triangulo(puntos,presiones,origen):
    area=math.hypot(*_cruz(_resta(puntos[1],puntos[0]),_resta(puntos[2],puntos[0])))/2
    if area==0:return 0.,0.,[0.,0.,0.]
    if not math.isfinite(area):raise ErrorAccionesLiquidos('Área de integración no representable.')
    pico=max(presiones)
    if pico==0:return area,0.,[0.,0.,0.]
    normalizados=[p/pico for p in presiones];suma=math.fsum(normalizados)
    carga=area*(pico*(suma/3))
    if not math.isfinite(carga) or carga<=0:raise ErrorAccionesLiquidos('Integral de presión positiva no representable.')
    pesos=[.25*(1+p/suma) for p in normalizados]
    relativos=[_resta(p,origen) for p in puntos]
    primero=[carga*math.fsum(p[k]*w for p,w in zip(relativos,pesos)) for k in range(3)]
    if not all(math.isfinite(x) for x in primero):raise ErrorAccionesLiquidos('Primer momento de presión no representable.')
    return area,carga,primero


def _contorno(item,vertices,derivado,nivel,gamma,origen,tipo):
    puntos=derivado['vertices_m'];ids=item['vertices'];triangulos=_triangular(puntos,derivado['normal_unitaria'],derivado['epsilon_relativo_computacional'])
    partes=[];areas_completas=[]
    for indices in triangulos:
        originales=[{'vertice_id':ids[i],'xyz_m':list(puntos[i]),'procedencia':copy.deepcopy(vertices[ids[i]]['procedencia']),
                      'origen':{'tipo':'vertice_geometria_declarada'}} for i in indices]
        area_completa=math.hypot(*_cruz(_resta(puntos[indices[1]],puntos[indices[0]]),_resta(puntos[indices[2]],puntos[indices[0]])))/2
        areas_completas.append(area_completa)
        recorte=_recortar(originales,nivel)
        for punto in recorte:punto['presion_kn_m2']=_presion(punto['xyz_m'][2],nivel,gamma)
        areas=[];cargas=[];primeros=[]
        for i in range(1,len(recorte)-1):
            trio=[recorte[k] for k in (0,i,i+1)]
            area,carga,primero=_integral_triangulo([p['xyz_m'] for p in trio],[p['presion_kn_m2'] for p in trio],origen)
            areas.append(area);cargas.append(carga);primeros.append(primero)
        partes.append({'vertices_origen':list(ids[i] for i in indices),'region_sumergida':recorte,'area_sumergida_m2':math.fsum(areas),
                       'integral_presion_kn':math.fsum(cargas),'primer_momento_presion_kn_m':[math.fsum(p[k] for p in primeros) for k in range(3)]})
    reconstruida=math.fsum(areas_completas);error=abs(reconstruida-derivado['area_m2']);tol=max(EPS,8*derivado['epsilon_relativo_computacional'])*derivado['area_m2']
    if not math.isfinite(reconstruida) or error>tol:raise ErrorAccionesLiquidos('La triangulación no conserva el área del contorno fuente.')
    return {'id':item['id'],'tipo':tipo,'signo_integracion':1 if tipo=='anfitriona' else -1,
            'procedencia':copy.deepcopy(item['procedencia']),
            'vertices_declarados':[{'vertice_id':ident,'xyz_m':list(p),'presion_kn_m2':_presion(p[2],nivel,gamma),
                                   'procedencia':copy.deepcopy(vertices[ident]['procedencia'])} for ident,p in zip(ids,puntos)],
            'triangulos':partes,'area_completa_m2':derivado['area_m2'],'error_reconstruccion_area_m2':error,
            'criterio_reconstruccion_area_m2':tol,'area_sumergida_m2':math.fsum(p['area_sumergida_m2'] for p in partes),
            'integral_presion_kn':math.fsum(p['integral_presion_kn'] for p in partes),
            'primer_momento_presion_kn_m':[math.fsum(p['primer_momento_presion_kn_m'][k] for p in partes) for k in range(3)]}


def calcular_acciones_liquidos(geometria,declarada,fuentes):
    """Revalida vínculos y deriva presión/integrales exactas sobre polígonos planos.

    Exactitud algebraica de integración lineal; evaluación numérica binary64.
    No transporta ni sustituye las presiones por cargas puntuales en ETABS.
    """
    try:
        if not isinstance(declarada,dict) or 'declaracion' not in declarada:
            raise ErrorAccionesLiquidos('Se requiere una declaración vinculada por declarar_acciones_liquidos.')
        esperada=declarar_acciones_liquidos(geometria,declarada['declaracion'],fuentes)
        if _canonico(declarada)!=_canonico(esperada):raise ErrorAccionesLiquidos('Geometría/fuentes/declaración cambiaron; se requiere nueva declaración vinculada.')
        r=validar_geometria(geometria);g=r.geometria_m;d=declarada['declaracion']
        vertices={v['id']:v for v in g['vertices']};tabla={s['id']:s for s in g['superficies']};resultados=[]
        origen=d['origen_momentos_m']
        for seleccion in d['superficies']:
            sid=seleccion['superficie'];host=tabla[sid]
            normal=[x*seleccion['sentido_normal'] for x in r.derivados_m['superficies'][sid]['normal_unitaria']]
            # p = gamma*(h - z_cara), z_cara = z - delta*n_z  <=>  nivel efectivo h + delta*n_z sobre la superficie media.
            delta=seleccion.get('desplazamiento_cara_m',0)
            nivel=d['nivel_libre_z_m']+delta*normal[2] if 'desplazamiento_cara_m' in seleccion else d['nivel_libre_z_m']
            contornos=[_contorno(host,vertices,r.derivados_m['superficies'][sid],nivel,d['peso_especifico_kn_m3'],origen,'anfitriona')]
            for abertura in g['aberturas']:
                if abertura['superficie']==sid:contornos.append(_contorno(abertura,vertices,r.derivados_m['aberturas'][abertura['id']],nivel,d['peso_especifico_kn_m3'],origen,'abertura'))
            area=math.fsum(p['signo_integracion']*p['area_sumergida_m2'] for p in contornos)
            carga=math.fsum(p['signo_integracion']*p['integral_presion_kn'] for p in contornos)
            primero=[math.fsum(p['signo_integracion']*p['primer_momento_presion_kn_m'][k] for p in contornos) for k in range(3)]
            if area<0 or carga<0 or (contornos[0]['integral_presion_kn']>0 and (area==0 or carga==0)):
                raise ErrorAccionesLiquidos('Sustracción de huecos no positiva o numéricamente no resoluble; no se rellena ni redondea a cero.')
            fuerza=[carga*x for x in normal];momento=_cruz(primero,normal)
            centro=[origen[k]+primero[k]/carga for k in range(3)] if carga else None
            resultados.append({'superficie':sid,'sentido_normal':seleccion['sentido_normal'],'normal_carga':normal,
                               'aberturas_ids':[p['id'] for p in contornos[1:]],'contornos':contornos,
                               'area_sumergida_bruta_m2':contornos[0]['area_sumergida_m2'],
                               'area_sumergida_aberturas_m2':math.fsum(p['area_sumergida_m2'] for p in contornos[1:]),
                               'area_sumergida_neta_m2':area,'integral_presion_neta_kn':carga,
                               'primer_momento_presion_neta_kn_m':primero,'fuerza_kn':fuerza,'momento_kn_m':momento,
                               'centro_presion_m':centro,'procedencia':copy.deepcopy(host['procedencia']),'fuentes':list(seleccion['fuentes']),
                               **({'desplazamiento_cara_m':delta,'nivel_efectivo_z_m':nivel} if 'desplazamiento_cara_m' in seleccion else {})})
        salida={'contrato':CONTRATO+'.resultado','version_contrato':VERSION,'huella_declaracion':declarada['huella_declaracion'],
                'declaracion_vinculada':copy.deepcopy(declarada),'estado':'derivacion_pendiente','aplicado':False,'ejecutable':False,
                'aprobacion_ingenieria':None,'origen_momentos_m':list(origen),'superficies':resultados,
                'fuerza_total_kn':[math.fsum(s['fuerza_kn'][k] for s in resultados) for k in range(3)],
                'momento_total_kn_m':[math.fsum(s['momento_kn_m'][k] for s in resultados) for k in range(3)],
                'alcance':'Presión manométrica estática de una cara declarada; no hidrodinámica, suelo, flotación, apoyos ni diseño.',
                'criterio_computacional':'Recorte exacto z<=nivel, región con profundidad positiva; ear clipping e integrales lineales binary64, sin tolerancia de ingeniería.'}
        _canonico(salida)  # rechaza overflow/NaN incluso en combinaciones vectoriales
        return salida
    except (OverflowError,ZeroDivisionError,KeyError,TypeError,RecursionError) as exc:
        raise ErrorAccionesLiquidos('Derivación numéricamente no representable o entrada no válida.') from exc


def main(argv=None):
    """Derivación local reproducible desde tres JSON explícitos; no usa proveedores ni ETABS."""
    import argparse
    from pathlib import Path
    import sys
    from .gestion_extraccion import json_desde_bytes
    parser=argparse.ArgumentParser(description='Derivar presión hidrostática declarada; no aplicar cargas ni aprobar ingeniería.')
    parser.add_argument('--geometria',type=Path,required=True)
    parser.add_argument('--declaracion',type=Path,required=True)
    parser.add_argument('--fuentes',type=Path,required=True)
    parser.add_argument('--salida',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        entradas=[json_desde_bytes(p.read_bytes(),str(p)) for p in (args.geometria,args.declaracion,args.fuentes)]
        geometria,declaracion,fuentes=entradas
        vinculada=declarar_acciones_liquidos(geometria,declaracion,fuentes)
        resultado=calcular_acciones_liquidos(geometria,vinculada,fuentes)
        raw=json.dumps(resultado,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
        # Exclusión atómica de destino existente: nunca reemplazar geometría, fuentes o salidas previas.
        with args.salida.open('x',encoding='utf-8',newline='\n') as stream:
            stream.write(raw)
    except (OSError,ValueError) as exc:
        print('Derivación no completada: '+str(exc),file=sys.stderr)
        return 2
    print('Derivación conservada: '+str(args.salida)+' | aplicado=false | ejecutable=false | aprobación de ingeniería pendiente')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
