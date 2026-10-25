"""Refinamiento conforme de triángulos por niveles Z explícitos; no crea pisos ni propiedades."""
import copy
from fractions import Fraction
import hashlib
import json
import math


class ErrorCorte(ValueError):
    pass


def _canon(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))


def _area(a,b,c):
    u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
    return math.hypot(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])/2


def cortar_malla_por_niveles(nodos,triangulos,niveles_z_m):
    """Conserva ambas regiones de cada corte; interpola nodos compartidos sobre sus aristas.

    Las entradas son nodos {id,xyz_m,...} y triángulos {id,nodos,...}; los campos extra se conservan.
    Cada nuevo nodo tiene procedencia calculada, nunca coordenadas medidas inventadas.
    """
    try:
        source=_canon({'nodos':nodos,'triangulos':triangulos,'niveles_z_m':niveles_z_m})
        if not isinstance(niveles_z_m,list) or any(type(h) not in (int,float) or not math.isfinite(h) for h in niveles_z_m) or len(set(niveles_z_m))!=len(niveles_z_m):
            raise ErrorCorte('Niveles Z finitos, explícitos y distintos requeridos.')
        if not isinstance(nodos,list) or not nodos or not isinstance(triangulos,list) or not triangulos:
            raise ErrorCorte('Malla fuente no vacía requerida.')
        table={}
        for node in nodos:
            name=node['id'];xyz=node['xyz_m']
            if not isinstance(name,str) or not name or name in table or not isinstance(xyz,list) or len(xyz)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) for x in xyz):raise ErrorCorte('Nodo inválido o duplicado.')
            table[name]=copy.deepcopy(node)
        ids=set();pieces=[];original_area=0.
        for triangle in triangulos:
            ring=triangle['nodos'];name=triangle['id']
            if not isinstance(name,str) or not name or name in ids or not isinstance(ring,list) or len(ring)!=3 or len(set(ring))!=3 or any(n not in table for n in ring):raise ErrorCorte('Triángulo inválido o duplicado.')
            area=_area(*(table[n]['xyz_m'] for n in ring))
            if not math.isfinite(area) or area<=0:raise ErrorCorte('Triángulo fuente degenerado.')
            ids.add(name);original_area+=area;pieces.append((copy.deepcopy(triangle),list(ring)))
        cache={};generated=[]
        def intersection(a,b,h):
            if table[a]['xyz_m'][2]==h:return a
            if table[b]['xyz_m'][2]==h:return b
            key=(*sorted((a,b)),Fraction(h))
            if key in cache:return cache[key]
            a,b=key[:2];x,y=table[a]['xyz_m'],table[b]['xyz_m']
            t=(Fraction(h)-Fraction(x[2]))/(Fraction(y[2])-Fraction(x[2]))
            if not 0<t<1:raise ErrorCorte('Intersección fuera de su arista.')
            xyz=[float(Fraction(x[k])+t*(Fraction(y[k])-Fraction(x[k]))) for k in range(3)];xyz[2]=h
            if xyz==x or xyz==y or not all(math.isfinite(v) for v in xyz):raise ErrorCorte('Intersección no representable sin colapsar nodos.')
            name='CORTE#'+str(len(generated)+1)
            while name in table:name+='x'
            node={'id':name,'xyz_m':xyz,'traza':{'tipo':'interseccion_nivel_calculada','arista':[a,b],'nivel_z_m':h,'t':str(t)}}
            table[name]=node;generated.append(node);cache[key]=name
            return name
        def clip(ring,h,side):
            result=[]
            for a,b in zip(ring,ring[1:]+ring[:1]):
                da=side*(Fraction(table[a]['xyz_m'][2])-Fraction(h));db=side*(Fraction(table[b]['xyz_m'][2])-Fraction(h))
                if da>=0:result.append(a)
                if (da>=0)!=(db>=0):result.append(intersection(a,b,h))
            clean=[]
            for n in result:
                if not clean or clean[-1]!=n:clean.append(n)
            if len(clean)>1 and clean[0]==clean[-1]:clean.pop()
            return clean
        for h in sorted(niveles_z_m):
            next_pieces=[]
            for meta,ring in pieces:
                z=[table[n]['xyz_m'][2] for n in ring]
                if min(z)<h<max(z):
                    for side in (-1,1):
                        polygon=clip(ring,h,side)
                        if len(polygon)<3:raise ErrorCorte('Corte produce región degenerada.')
                        for i in range(1,len(polygon)-1):next_pieces.append((meta,[polygon[0],polygon[i],polygon[i+1]]))
                else:next_pieces.append((meta,ring))
            pieces=next_pieces
        result_triangles=[];areas=[];names=set(ids)
        for i,(meta,ring) in enumerate(pieces,1):
            area=_area(*(table[n]['xyz_m'] for n in ring))
            if not math.isfinite(area) or area<=0:raise ErrorCorte('Triángulo derivado no representable.')
            name=meta['id']+'#corte'+str(i)
            while name in names:name+='x'
            names.add(name);areas.append(area)
            result_triangles.append({**meta,'id':name,'nodos':ring,'triangulo_fuente':meta['id']})
        total=math.fsum(areas)
        if abs(total-original_area)>max(1e-10*original_area,64*math.ulp(original_area)):
            raise ErrorCorte('El área real no se conserva bajo el criterio computacional.')
        for tri in result_triangles:
            z=[table[n]['xyz_m'][2] for n in tri['nodos']]
            if any(min(z)<h<max(z) for h in niveles_z_m):raise ErrorCorte('Persisten triángulos atravesando un nivel.')
        out={'contrato':'draft2model.corte_malla_niveles','version_contrato':'0.1.0','nodos':copy.deepcopy(nodos)+generated,
             'triangulos':result_triangles,'niveles_z_m':sorted(niveles_z_m),'sha256_malla_fuente':hashlib.sha256(source.encode()).hexdigest(),
             'area_fuente_m2':original_area,'area_derivada_m2':total,'ejecutable':False,'aprueba_ingenieria':False,
             'pendientes':['Políticas explícitas de los nuevos nodos para apoyos/diafragmas y vínculos',
                           'Mapeo y relectura del plan/motor; calidad y verificación de ingeniería']}
        out['huella_corte']=hashlib.sha256(_canon(out).encode()).hexdigest()
        return out
    except ErrorCorte:raise
    except (TypeError,KeyError,ValueError,OverflowError,ZeroDivisionError) as exc:
        raise ErrorCorte('Fuente o niveles no válidos: '+str(exc)) from exc
