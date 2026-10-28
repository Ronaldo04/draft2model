"""Superficies con huecos explícitos v0.3; cálculo geométrico, sin ETABS."""
from __future__ import annotations

import math

from . import contratos as c
from .geometria_superficies import _ValidadorSuperficies, _poligono, _resta, _punto, BLOQUEO_INTEGRACION as BLOQUEO_SUPERFICIES

BLOQUEO_INTEGRACION = "Geometría v0.3: configuración, conversión, tabular y operaciones ETABS con aberturas pendientes de integración verificada."


def _orient(a, b, p, eps):
    valor = (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
    return 0 if abs(valor) <= eps else (1 if valor > 0 else -1)


def _sobre(a, b, p, eps):
    return _orient(a, b, p, eps) == 0 and all(min(a[k], b[k])-eps <= p[k] <= max(a[k], b[k])+eps for k in (0, 1))


def _contacto(a, b, p, q, eps):
    o = (_orient(a,b,p,eps), _orient(a,b,q,eps), _orient(p,q,a,eps), _orient(p,q,b,eps))
    return (o[0]*o[1] < 0 and o[2]*o[3] < 0) or any((_sobre(a,b,p,eps), _sobre(a,b,q,eps), _sobre(p,q,a,eps), _sobre(p,q,b,eps)))


def _aristas(poligono):
    return zip(poligono, poligono[1:]+poligono[:1])


def _interior(p, poligono, eps):
    if any(_sobre(a,b,p,eps) for a,b in _aristas(poligono)):
        return False
    dentro = False
    for a,b in _aristas(poligono):
        if (a[1] > p[1]) != (b[1] > p[1]):
            x = a[0]+(p[1]-a[1])*(b[0]-a[0])/(b[1]-a[1])
            if x > p[0]:
                dentro = not dentro
    return dentro


def _cruzan(a, b, eps):
    return any(_contacto(p,q,r,s,eps) for p,q in _aristas(a) for r,s in _aristas(b))


class _ValidadorAberturas(_ValidadorSuperficies):
    version = c.VERSION_GEOMETRIA_ABERTURAS
    campos_raiz = c.CAMPOS_RAIZ_ABERTURAS
    nombres_colecciones = _ValidadorSuperficies.nombres_colecciones + ("aberturas",)

    def coleccion(self, nombre, elementos):
        if nombre != "aberturas":
            return super().coleccion(nombre, elementos)
        if not isinstance(elementos, list):
            self.error("$.aberturas", "tipo_invalido", "Se requiere una lista explícita.")
            return
        for i, elem in enumerate(elementos):
            ruta = f"$.aberturas[{i}]"
            if not self.objeto(ruta, elem, c.CAMPOS_ABERTURA):
                continue
            ident = self.identificador(ruta+".id", elem.get("id"))
            if ident is not None:
                if ident in self.ids[nombre]:
                    self.error(ruta+".id", "id_duplicado", "ID repetido en aberturas.")
                else:
                    self.ids[nombre][ident] = elem
            anfitriona = self.identificador(ruta+".superficie", elem.get("superficie"))
            if anfitriona is not None and anfitriona not in self.ids["superficies"]:
                self.error(ruta+".superficie", "referencia_inexistente", "Superficie anfitriona no declarada.")
            if "procedencia" in elem:
                self.procedencia(ruta+".procedencia", elem["procedencia"])
            vertices = elem.get("vertices")
            if not isinstance(vertices, list) or len(vertices) < 3:
                self.error(ruta+".vertices", "contorno_invalido", "Se requieren al menos tres IDs ordenados.")
                continue
            vistos = set()
            for j, vertice in enumerate(vertices):
                ref = self.identificador(f"{ruta}.vertices[{j}]", vertice)
                if ref is None:
                    continue
                if ref in vistos:
                    self.error(ruta+".vertices", "vertice_repetido", "El hueco repite un ID.")
                if ref not in self.ids["vertices"]:
                    self.error(ruta+".vertices", "referencia_inexistente", "Vértice no declarado.")
                vistos.add(ref)

    def normalizar(self):
        if not super().normalizar():
            return False
        self.r.bloqueos.remove(BLOQUEO_SUPERFICIES)
        g = self.r.geometria_m
        vertices = {v["id"]: tuple(v[k] for k in ("x","y","z")) for v in g["vertices"]}
        derivados = self.r.derivados_m
        huecos = {}
        por_superficie = {s["id"]: [] for s in g["superficies"]}
        for i, abertura in enumerate(g["aberturas"]):
            try:
                puntos = [vertices[v] for v in abertura["vertices"]]
                hueco = _poligono(puntos)
                host = derivados["superficies"][abertura["superficie"]]
                origen = host["vertices_m"][0]
                escala = max(abs(x) for p in host["vertices_m"] for x in _resta(p,origen))
                normal = host["normal_unitaria"]
                eje = max(range(3), key=lambda k: abs(normal[k]))
                eps = max(host["epsilon_relativo_computacional"], 64*math.ulp(max(abs(x) for p in puntos for x in p))/escala)
                if not math.isfinite(eps) or eps > 1e-6:
                    raise ValueError("Coordenadas del hueco numéricamente inestables respecto de la anfitriona.")
                q = [tuple(x/escala for x in _resta(p,origen)) for p in puntos]
                if any(abs(_punto(p,normal)) > eps for p in q):
                    raise ValueError("El hueco no es coplanar con la superficie anfitriona.")
                proyectar = lambda p: tuple(x/escala for k,x in enumerate(_resta(p,origen)) if k != eje)
                contorno = [proyectar(p) for p in host["vertices_m"]]
                interior = [proyectar(p) for p in puntos]
                if _cruzan(contorno,interior,eps) or not all(_interior(p,contorno,eps) for p in interior):
                    raise ValueError("El hueco debe ser estrictamente interior, sin contacto ni cruce con el borde anfitrión.")
                for previo, previo_eps in por_superficie[abertura["superficie"]]:
                    criterio = max(eps, previo_eps)
                    if _cruzan(previo,interior,criterio) or _interior(interior[0],previo,criterio) or _interior(previo[0],interior,criterio):
                        raise ValueError("Las aberturas no pueden tocarse, cruzarse ni anidarse.")
                por_superficie[abertura["superficie"]].append((interior,eps))
                hueco["superficie_id"] = abertura["superficie"]
                hueco["epsilon_relativo_anfitriona_computacional"] = eps
                huecos[abertura["id"]] = hueco
            except (ValueError, OverflowError) as exc:
                self.error(f"$.aberturas[{i}].vertices", "abertura_invalida", str(exc))
        for sid, host in derivados["superficies"].items():
            ids = [a["id"] for a in g["aberturas"] if a["superficie"] == sid and a["id"] in huecos]
            area_huecos = math.fsum(huecos[a]["area_m2"] for a in ids)
            neta = host["area_m2"]-area_huecos
            if not math.isfinite(neta) or neta <= 0:
                self.error("$.aberturas", "area_neta_invalida", "Área neta no positiva o no representable.")
            host.update(area_bruta_m2=host["area_m2"], area_aberturas_m2=area_huecos, area_neta_m2=neta, aberturas_ids=ids)
        if self.r.errores:
            self.r.geometria_m = self.r.derivados_m = self.r.huella_contenido = None
            return False
        derivados["aberturas"] = huecos
        self.r.bloqueos.append(BLOQUEO_INTEGRACION)
        return True


def validar_aberturas(data):
    """Valida sin modificar la fuente; dispatcher público: validar_geometria."""
    return _ValidadorAberturas(data).ejecutar()
