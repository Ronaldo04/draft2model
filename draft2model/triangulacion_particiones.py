"""Celdas convexas de partición -> triángulos conformes; no criterios de ingeniería ni ETABS."""
from collections import Counter
import copy
from fractions import Fraction
import hashlib
import json

from .particion_superficies import particionar_superficie,ErrorParticion


class ErrorTriangulacion(ValueError):
    pass


def _area2(poly):
    return sum((p[0]*q[1]-q[0]*p[1] for p,q in zip(poly,poly[1:]+poly[:1])),Fraction(0))


def _cross(a,b,c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def triangular_particion(geometria,particion):
    """Reproduce la fuente y triangula conservando TODOS los nodos de aristas, incluso colineales."""
    try:
        real=particionar_superficie(geometria,particion['superficie']['id'])
        canonical=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))
        if canonical(real)!=canonical(particion):raise ErrorTriangulacion('Partición alterada o ajena a su geometría; no basta recalcular su hash.')
        axes=['xyz'.index(k) for k in particion['proyeccion']['ejes_proyectados']]
        xy={n['id']:tuple(Fraction(n['xyz_m'][k]) for k in axes) for n in particion['nodos']}
        if len(set(xy.values()))!=len(xy):raise ErrorTriangulacion('Nodos diferentes colapsan en la proyección.')
        triangles=[]
        for cell in particion['celdas']:
            ring=list(cell['nodos']);remaining=list(ring)
            total=_area2([xy[n] for n in ring]);sign=1 if total>0 else -1
            if total==0:raise ErrorTriangulacion('Celda degenerada.')
            generated=[]
            while len(remaining)>3:
                for i,b in enumerate(remaining):
                    a,c=remaining[i-1],remaining[(i+1)%len(remaining)]
                    if sign*_cross(xy[a],xy[b],xy[c])<=0:continue
                    if any(all(sign*_cross(xy[u],xy[v],xy[p])>=0 for u,v in ((a,b),(b,c),(c,a))) for p in remaining if p not in (a,b,c)):continue
                    generated.append([a,b,c]);del remaining[i];break
                else:raise ErrorTriangulacion('No existe oreja que conserve todos los nodos de borde.')
            if sign*_area2([xy[n] for n in remaining])<=0:raise ErrorTriangulacion('Triángulo final degenerado o invertido.')
            generated.append(remaining)
            # Comprobación topológica independiente de la selección de orejas.
            edges=Counter((u,v) for t in generated for u,v in zip(t,t[1:]+t[:1]))
            boundary=set(zip(ring,ring[1:]+ring[:1]))
            for edge,count in edges.items():
                if count!=1:raise ErrorTriangulacion('Arista orientada repetida.')
                if edge in boundary:
                    if edges[edge[::-1]]:raise ErrorTriangulacion('Borde fuente con incidencia interior.')
                elif edges[edge[::-1]]!=1:raise ErrorTriangulacion('Arista interior sin pareja opuesta.')
            if any(edges[e]!=1 for e in boundary):raise ErrorTriangulacion('Se omitió un segmento del borde fuente.')
            if sum((_area2([xy[n] for n in t]) for t in generated),Fraction(0))!=total:
                raise ErrorTriangulacion('La triangulación no conserva exactamente el área proyectada de su celda.')
            for i,t in enumerate(generated,1):
                triangles.append({'id':cell['id']+'#t'+str(i),'nodos':t,'celda_origen':cell['id'],
                                  'superficie_origen':particion['superficie']['id']})
        result={'contrato':'draft2model.triangulacion_particion','version_contrato':'0.1.0',
                'origen':copy.deepcopy(particion['origen']),'huella_particion':particion['huella_particion'],
                'superficie':copy.deepcopy(particion['superficie']),'huecos':copy.deepcopy(particion['huecos']),
                'nodos':copy.deepcopy(particion['nodos']),'triangulos':triangles,
                'cadenas_contorno':copy.deepcopy(particion['cadenas_contorno']),
                'cobertura':copy.deepcopy(particion['cobertura']),
                'ejecutable':False,'aprueba_ingenieria':False,
                'pendientes':['Asignación material/sección/ejes/cargas/masa','Compatibilidad interhost y con frames',
                              'Calidad de malla y efecto físico en ETABS con revisión propia']}
        result['huella_triangulacion']=hashlib.sha256(json.dumps(result,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()
        return result
    except ErrorTriangulacion:
        raise
    except (ErrorParticion,KeyError,TypeError,ValueError,ZeroDivisionError,OverflowError) as exc:
        raise ErrorTriangulacion('Fuente o partición no representable.') from exc


# -- salida de compatibilidad 182 (Claude 184) ------------------------------------

def _anillo_a_triangulos(ring, xy, eps_rel, etiqueta):
    """Orejas exactas que conservan todos los nodos; un ángulo casi llano (|cruz| <= eps·|u|·|w|) no es oreja."""
    total = _area2([xy[n] for n in ring])
    sign = 1 if total > 0 else -1
    if total == 0:
        raise ErrorTriangulacion(f'{etiqueta}: celda degenerada.')
    tol = Fraction(eps_rel)

    def no_degenerado(a, b, c):
        u = (xy[b][0] - xy[a][0], xy[b][1] - xy[a][1])
        w = (xy[c][0] - xy[b][0], xy[c][1] - xy[b][1])
        cruz = sign * _cross(xy[a], xy[b], xy[c])
        return cruz > 0 and cruz * cruz > tol * tol * (u[0] ** 2 + u[1] ** 2) * (w[0] ** 2 + w[1] ** 2)
    remaining = list(ring)
    generated = []
    while len(remaining) > 3:
        candidatos = []
        for i, b in enumerate(remaining):
            a, c = remaining[i - 1], remaining[(i + 1) % len(remaining)]
            if not no_degenerado(a, b, c):
                continue
            if any(all(sign * _cross(xy[u], xy[v], xy[p]) >= 0 for u, v in ((a, b), (b, c), (c, a)))
                   for p in remaining if p not in (a, b, c)):
                continue
            candidatos.append((i, a, b, c))
        if not candidatos:
            raise ErrorTriangulacion(f'{etiqueta}: no existe oreja no degenerada que conserve todos los nodos de borde.')
        i, a, b, c = candidatos[0]  # determinista: primera oreja válida en el orden del anillo
        generated.append([a, b, c])
        del remaining[i]
    a, b, c = remaining
    if not no_degenerado(a, b, c):
        raise ErrorTriangulacion(f'{etiqueta}: triángulo final degenerado o invertido.')
    generated.append(remaining)
    edges = Counter((u, v) for t in generated for u, v in zip(t, t[1:] + t[:1]))
    boundary = set(zip(ring, ring[1:] + ring[:1]))
    for edge, count in edges.items():
        if count != 1:
            raise ErrorTriangulacion(f'{etiqueta}: arista orientada repetida.')
        if edge in boundary:
            if edges[edge[::-1]]:
                raise ErrorTriangulacion(f'{etiqueta}: borde con incidencia interior.')
        elif edges[edge[::-1]] != 1:
            raise ErrorTriangulacion(f'{etiqueta}: arista interior sin pareja opuesta.')
    if any(edges[e] != 1 for e in boundary):
        raise ErrorTriangulacion(f'{etiqueta}: se omitió un segmento del borde.')
    if sum((_area2([xy[n] for n in t]) for t in generated), Fraction(0)) != total:
        raise ErrorTriangulacion(f'{etiqueta}: el área proyectada no se conserva exactamente.')
    return generated


def triangular_compatibilidad(geometria, particiones, conexiones, compatibilidad, *, _contexto=None):
    """Triangula la salida de `compatibilidad_particiones` reproduciéndola íntegramente desde sus fuentes.

    Conserva todos los nodos de borde (incluidos los insertados por conexiones), la celda/pieza/host de origen y la
    orientación de cada celda. Devuelve `draft2model.triangulacion_compatibilidad` 0.1.0; no ejecutable.
    """
    from .compatibilidad_particiones import compatibilizar_particiones, ErrorCompatibilidad
    canonical = lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    try:
        real = (compatibilizar_particiones(geometria, particiones, conexiones) if _contexto is None
                else compatibilizar_particiones(geometria, particiones, conexiones, _contexto=_contexto))
    except ErrorCompatibilidad as exc:
        raise ErrorTriangulacion('La compatibilidad no se reproduce desde sus fuentes: ' + str(exc)) from None
    try:
        if canonical(real) != canonical(compatibilidad):
            raise ErrorTriangulacion('Compatibilidad alterada o ajena a sus fuentes; no basta recalcular su hash.')
        nodos = {n['id']: n['xyz_m'] for n in compatibilidad['nodos']}
        por_sup = {p['superficie']['id']: p for p in particiones}
        triangulos = []
        for pieza in compatibilidad['piezas']:
            sid = pieza['superficie']
            part = por_sup[sid]
            axes = ['xyz'.index(k) for k in part['proyeccion']['ejes_proyectados']]
            ids = {n for c in pieza['celdas'] for n in c['nodos']}
            xy = {n: tuple(Fraction(nodos[n][k]) for k in axes) for n in ids}
            if len(set(xy.values())) != len(xy):
                raise ErrorTriangulacion(f'{sid}: nodos diferentes colapsan en la proyección.')
            eps = max(1e-12, part['superficie'].get('epsilon_relativo_computacional', 0) or 1e-12)
            for cell in pieza['celdas']:
                for i, t in enumerate(_anillo_a_triangulos(list(cell['nodos']), xy, eps, cell['id']), 1):
                    triangulos.append({'id': cell['id'] + '#t' + str(i), 'nodos': t, 'celda_origen': cell['id'],
                                       'superficie_origen': sid, 'pieza_de': cell['pieza_de']})
        result = {'contrato': 'draft2model.triangulacion_compatibilidad', 'version_contrato': '0.1.0',
                  'origen': {'huella_compatibilidad': compatibilidad['huella_compatibilidad'],
                             'compatibilidad': copy.deepcopy(compatibilidad['origen'])},
                  'nodos': copy.deepcopy(compatibilidad['nodos']), 'triangulos': triangulos,
                  'conexiones': copy.deepcopy(compatibilidad['conexiones']),
                  'bordes_no_conectados': copy.deepcopy(compatibilidad['bordes_no_conectados']),
                  'ejecutable': False, 'aprueba_ingenieria': False,
                  'pendientes': ['Asignación de propiedades/cargas/masa en configuración 0.4', 'Prueba ETABS real (Codex)']}
        result['huella_triangulacion'] = hashlib.sha256(canonical(result).encode()).hexdigest()
        return result
    except ErrorTriangulacion:
        raise
    except (KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
        raise ErrorTriangulacion('Compatibilidad no representable para triangular.') from exc
