"""Integral independiente por triángulos de las superficies declaradas09D; no malla ni ETABS."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

from draft2model import gestion_geometria as gg

ROOT=Path(__file__).resolve().parents[1]
CFG=ROOT/'tmp/ruta201/configuracion09dt.json'
INFO=ROOT/'seguimiento/claude_ruta/CONFIGURACION_CASO_09DT.json'
REFERENCIAS={
    'AGUA-TAN':{'interior':[11.415,13.491,3.193,4.918],'fondo_fisico':12.6,'nivel':13.7},
    'AGUA-CIS':{'interior':[15.012,17.015,2.549,4.698],'fondo_fisico':-2.4,'nivel':-.18}}

def sub(a,b):return [a[k]-b[k] for k in range(3)]
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def clip(poly,h):
    out=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        ia,ib=a[2]<=h,b[2]<=h
        if ia:out.append(a)
        if ia!=ib:
            t=(h-a[2])/(b[2]-a[2])
            out.append([a[k]+t*(b[k]-a[k]) for k in range(3)])
    return out

def integral(poly,n,h,gamma,origin):
    parts=[]
    for a,b,c in ((poly[0],poly[i],poly[i+1]) for i in range(1,len(poly)-1)):
        area=math.sqrt(sum(x*x for x in cross(sub(b,a),sub(c,a))))/2
        points=[sub(p,origin) for p in (a,b,c)]
        pressures=[gamma*(h-p[2]) for p in (a,b,c)]
        load=area*math.fsum(pressures)/3
        first=[area/12*(math.fsum(p[k] for p in points)*math.fsum(pressures)+
                        math.fsum(p[k]*v for p,v in zip(points,pressures))) for k in range(3)]
        parts.append(([load*v for v in n],cross(first,n),area))
    return ([math.fsum(f[k] for f,m,a in parts) for k in range(3)],
            [math.fsum(m[k] for f,m,a in parts) for k in range(3)],math.fsum(a for f,m,a in parts))

def main():
    raw=CFG.read_bytes();cfg=json.loads(raw);info_raw=INFO.read_bytes();info=json.loads(info_raw)
    if hashlib.sha256(raw).hexdigest()!=info['sha256']:raise ValueError('Recibo no corresponde a configuración actual')
    version=cfg['geometria_origen']['version_id']
    source=gg.consultar_version(ROOT/'data/private',cfg['caso'],version)
    if not source.comprobacion.correcta or source.geometria['unidad_longitud']!='m':raise ValueError('Geometría no comprobada en metros')
    if source.comprobacion.sha256_geometria!=cfg['geometria_origen']['sha256_geometria']:raise ValueError('SHA geometría no coincide')
    geo=source.geometria
    vertices={v['id']:[v[k] for k in ('x','y','z')] for v in geo['vertices']}
    surfaces={s['id']:s for s in geo['superficies']}
    inventory=info['recibo_malla']['contenido']
    inventory=inventory.get('inventario',inventory)
    records=[]
    for entry in cfg['liquidos']['declaraciones']:
        d=entry['declaracion'];ref=REFERENCIAS[d['id']]
        if d['nivel_libre_z_m']!=ref['nivel'] or d['origen_momentos_m']!=[0,0,0]:raise ValueError('Referencia de escenario distinta')
        parts=[];bottoms=[]
        for selected in d['superficies']:
            name=selected['superficie']
            if any(a['superficie']==name for a in geo['aberturas']):raise ValueError('Este contraste exige hosts cargados sin huecos')
            points=[vertices[v] for v in surfaces[name]['vertices']]
            normal=cross(sub(points[1],points[0]),sub(points[2],points[0]))
            norm=math.sqrt(sum(v*v for v in normal));normal=[v/norm*selected['sentido_normal'] for v in normal]
            delta=selected.get('desplazamiento_cara_m',0.)
            effective=d['nivel_libre_z_m']+delta*normal[2]
            immersed=clip(points,effective)
            f,m,area=integral(immersed,normal,effective,d['peso_especifico_kn_m3'],d['origen_momentos_m']) if len(immersed)>=3 else ([0]*3,[0]*3,0)
            parts.append({'host':name,'fuerza_kn':f,'momento_kn_m':m,'area_m2':area,'delta_m':delta,'nivel_efectivo':effective})
            if abs(normal[2])>.999:
                if abs(points[0][2]-delta*normal[2]-ref['fondo_fisico'])>1e-9:raise ValueError('Cara física del fondo distinta')
                bottoms.extend(points)
        x0,x1,y0,y1=ref['interior'];volume=(x1-x0)*(y1-y0)*(ref['nivel']-ref['fondo_fisico'])
        weight=d['peso_especifico_kn_m3']*volume;cx=(x0+x1)/2;cy=(y0+y1)/2
        expected_f=[0,0,-weight];expected_m=[-weight*cy,weight*cx,0]
        total_f=[math.fsum(p['fuerza_kn'][k] for p in parts) for k in range(3)]
        total_m=[math.fsum(p['momento_kn_m'][k] for p in parts) for k in range(3)]
        bounds=[min(p[0] for p in bottoms),max(p[0] for p in bottoms),min(p[1] for p in bottoms),max(p[1] for p in bottoms)]
        errors=[abs(a-b) for a,b in zip(total_f+total_m+bounds,expected_f+expected_m+ref['interior'])]
        inv=next(s for s in inventory['escenarios'] if s['declaracion']==d['id'])
        errors.append(abs(inv['peso_kn']-weight))
        records.append({'declaracion':d['id'],'volumen_m3':volume,'peso_kn':weight,'fuerza_kn':total_f,'momento_kn_m':total_m,
                        'fuerza_referencia_kn':expected_f,'momento_referencia_kn_m':expected_m,'error_max':max(errors),
                        'correcto':max(errors)<1e-7,'hosts':parts})
    if CFG.read_bytes()!=raw or INFO.read_bytes()!=info_raw:raise ValueError('Fuentes cambiaron durante contraste')
    report={'fecha_utc':datetime.now(timezone.utc).isoformat(),'configuracion_sha256':hashlib.sha256(raw).hexdigest(),
            'version_geometria':version,'contrastes':records,'correcto':all(r['correcto'] for r in records),
            'alcance':'Integración algebraica independiente de superficies declaradas/caras y contabilidad, con dominio explícito de09D',
            'limites':['No acredita cotas originales del plano ni hipótesis','No genera ni verifica tabla de cargas nativa',
                       'No análisis, masa ensamblada, hidrodinámica ni seguridad estructural'],'etabs':False,'apis_remotas':0}
    with (ROOT/'seguimiento/CONTRASTE_PRESIONES_264.json').open('x',encoding='utf-8') as stream:
        json.dump(report,stream,ensure_ascii=False,indent=2)
    print(json.dumps({'correcto':report['correcto'],'depositos':len(records),'errores_max':[r['error_max'] for r in records]}))
    return int(not report['correcto'])

if __name__=='__main__':raise SystemExit(main())
