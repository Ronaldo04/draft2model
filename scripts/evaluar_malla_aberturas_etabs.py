"""Diagnóstico geométrico NECESARIO del ensayo sintético179; no certifica mallado ni ingeniería."""
import argparse
import hashlib
import json
import math
from collections import Counter,defaultdict
from pathlib import Path


def area(poly):
    return abs(math.fsum(p[0]*q[1]-q[0]*p[1] for p,q in zip(poly,poly[1:]+poly[:1])))/2 if len(poly)>2 else 0.


def clip_rect(poly):
    for k,b,sgn in ((0,1,1),(0,2,-1),(1,1,1),(1,2,-1)):
        clipped=[]
        for p,q in zip(poly,poly[1:]+poly[:1]):
            dp,dq=sgn*(p[k]-b),sgn*(q[k]-b)
            if dp>=0:clipped.append(p)
            if (dp>=0)!=(dq>=0):
                t=dp/(dp-dq);clipped.append([p[j]+t*(q[j]-p[j]) for j in range(2)])
        poly=clipped
    return poly


def topologia(elementos):
    """Diagnóstico adicional del ensayo4x3/hueco1x1; umbral computacional, no calidad de ingeniería."""
    nodes={};edges=Counter();coordnames=defaultdict(set);inverted=[];polygons=[];nonconvex=[]
    for elm in elementos:
        names=[p['nombre'] for p in elm['puntos']];uvs=[p['uv'] for p in elm['puntos']]
        polygons.append(uvs)
        signed=sum(p[0]*q[1]-q[0]*p[1] for p,q in zip(uvs,uvs[1:]+uvs[:1]))
        if signed<=0:inverted.append(elm['nombre'])
        if any((b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0]) < -1e-10 for a,b,c in zip(uvs,uvs[1:]+uvs[:1],uvs[2:]+uvs[:2])):nonconvex.append(elm['nombre'])
        for n,p in zip(names,uvs):
            if n in nodes and nodes[n]!=p:raise ValueError('Nodo nativo con dos coordenadas diferentes.')
            nodes[n]=p;coordnames[tuple(p)].add(n)
        edges.update(zip(names,names[1:]+names[:1]))
    duplicates=[sorted(x) for x in coordnames.values() if len(x)>1]
    def source_boundary(a,b):
        for k,v in ((0,0),(0,4),(1,0),(1,3)):
            if abs(a[k]-v)<=1e-9 and abs(b[k]-v)<=1e-9:return True
        for k,v in ((0,1),(0,2),(1,1),(1,2)):
            other=1-k
            if abs(a[k]-v)<=1e-9 and abs(b[k]-v)<=1e-9 and all(1-1e-9<=p[other]<=2+1e-9 for p in (a,b)):return True
        return False
    gaps=[];repeated=[];hanging=[]
    for (a,b),count in edges.items():
        if count!=1 or edges[(b,a)]>1:repeated.append([a,b])
        if edges[(b,a)]==0 and not source_boundary(nodes[a],nodes[b]):gaps.append([a,b])
        x,y=nodes[a],nodes[b];dx,dy=y[0]-x[0],y[1]-x[1];length=math.hypot(dx,dy)
        if not length:raise ValueError('Arista nativa de longitud cero.')
        for n,p in nodes.items():
            if n in (a,b):continue
            distance=abs(dx*(p[1]-x[1])-dy*(p[0]-x[0]))/length
            t=((p[0]-x[0])*dx+(p[1]-x[1])*dy)/(length*length)
            if distance<=1e-9 and 1e-9<t<1-1e-9:hanging.append({'nodo':n,'arista':[a,b]})
    # Solape positivo de polígonos convexos nativos por recorte independiente.
    overlaps=[]
    for i,poly in enumerate(polygons):
        for j in range(i):
            clipped=poly
            for a,b in zip(polygons[j],polygons[j][1:]+polygons[j][:1]):
                result=[]
                for p,q in zip(clipped,clipped[1:]+clipped[:1]):
                    cross=lambda r:(b[0]-a[0])*(r[1]-a[1])-(b[1]-a[1])*(r[0]-a[0])
                    dp,dq=cross(p),cross(q)
                    if dp>=0:result.append(p)
                    if (dp>=0)!=(dq>=0):
                        t=dp/(dp-dq);result.append([p[k]+t*(q[k]-p[k]) for k in (0,1)])
                clipped=result
            if area(clipped)>1e-8:overlaps.append([j,i])
    return {'nodos':len(nodes),'coordenadas_con_varios_nombres':duplicates,'aristas_sin_pareja_interior':gaps,
            'aristas_repetidas':repeated,'nodos_colgantes':hanging,'elementos_invertidos':inverted,'elementos_no_convexos':nonconvex,'solapes':overlaps,
            'conformidad_geometrica_comprobada':bool(elementos) and not any((duplicates,gaps,repeated,hanging,inverted,nonconvex,overlaps))}


def evaluar(record):
    if record.get('datos_sinteticos') is not True:raise ValueError('Solo el ensayo sintético conocido.')
    rows=[]
    for scenario in record['escenarios']:
        caso=scenario['caso']
        if caso not in ('piso','muro','inclinado') or scenario['unidades']!='kN_m_C':raise ValueError('Escenario/unidades desconocidos.')
        scale=math.sqrt(2) if caso=='inclinado' else 1
        contributions=[];unread=[];opening_elements=0;native=[];out_of_plane=[]
        for obj in scenario['areas']:
            if obj['retorno_getelm']!=0:unread.append(obj['nombre'])
            if obj['abertura']:
                opening_elements+=len(obj['elementos']);continue
            for elm in obj['elementos']:
                xyz=[p['xyz'] for p in elm['puntos']]
                if any(not isinstance(p,list) or len(p)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) for x in p) for p in xyz):raise ValueError('Coordenadas no representables.')
                for named,p in zip(elm['puntos'],xyz):
                    residual=p[2]-3 if caso=='piso' else p[1] if caso=='muro' else p[2]-p[1]
                    if abs(residual)>1e-9:out_of_plane.append(named['nombre'])
                uv=[[p[0],p[2] if caso=='muro' else p[1]] for p in xyz]
                native.append({'nombre':elm['nombre'],'puntos':[{'nombre':p['nombre'],'uv':q} for p,q in zip(elm['puntos'],uv)]})
                contributions.append({'elemento':elm['nombre'],'area_m2':area(uv)*scale,'interseccion_hueco_m2':area(clip_rect(uv))*scale})
        total=math.fsum(x['area_m2'] for x in contributions)
        overlap=math.fsum(x['interseccion_hueco_m2'] for x in contributions)
        expected=11*scale
        rows.append({'caso':caso,'elementos_host':len(contributions),'elementos_abertura':opening_elements,
                     'objetos_con_lectura_fallida':unread,'area_host_m2':total,'area_neta_esperada_m2':expected,
                     'area_host_dentro_hueco_m2':overlap,'elementos':contributions,
                     'topologia':topologia(native),
                     'puntos_fuera_plano':sorted(set(out_of_plane)),
                     'criterios_geometricos_necesarios':not unread and not out_of_plane and bool(contributions) and opening_elements==0 and abs(total-expected)<=1e-8 and overlap<=1e-8})
    return {'datos_sinteticos':True,'cierre_confirmado':record.get('cierre_confirmado') is True,
            'error_motor':record.get('error'),'escenarios':rows,'aprueba_modelo':False,'autoriza_ejecucion_produccion':False,
            'limites':['Solo suma de áreas e intersección con hueco rectangular sintético; no prueba calidad/conectividad/rigidez de malla ni ingeniería.','Un retorno GetElm fallido es lectura incompleta, no ausencia comprobada de elementos.','No se ejecutó solver ni se comprobaron cargas.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('registro',type=Path);parser.add_argument('--salida',type=Path,required=True)
    args=parser.parse_args();raw=args.registro.read_bytes();out=evaluar(json.loads(raw.decode('utf-8-sig')))
    out['sha256_registro']=hashlib.sha256(raw).hexdigest()
    with args.salida.open('x',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps([{k:r[k] for k in ('caso','elementos_host','objetos_con_lectura_fallida','area_host_m2','area_host_dentro_hueco_m2','criterios_geometricos_necesarios')} for r in out['escenarios']],ensure_ascii=False))


if __name__=='__main__':main()
