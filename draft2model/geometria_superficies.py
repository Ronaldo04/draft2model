"""Geometría plana 3D v0.2; no representación constitutiva ni aprobación técnica."""
from __future__ import annotations

import copy
import math

from . import contratos as c
from .validacion_geometria import _Validador

BLOQUEO_INTEGRACION = "Geometría v0.2: configuración estructural y operaciones ETABS de superficies pendientes de integración verificada."


def _resta(a, b):
    return tuple(x-y for x, y in zip(a, b))


def _cruz(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _punto(a, b):
    return math.fsum(x*y for x, y in zip(a, b))


def _poligono(puntos):
    """Operaciones sobre coordenadas trasladadas/escaladas; devuelve derivados o ValueError."""
    if len(set(puntos)) != len(puntos):
        raise ValueError("El contorno repite coordenadas físicas.")
    desplazados = [_resta(p, puntos[0]) for p in puntos]
    escala = max(abs(x) for p in desplazados for x in p)
    if not math.isfinite(escala) or escala == 0:
        raise ValueError("Extensión nula o no representable.")
    q = [tuple(x/escala for x in p) for p in desplazados]
    max_coord = max(abs(x) for p in puntos for x in p)
    eps = max(1e-12, 64*math.ulp(max_coord)/escala)
    if not math.isfinite(eps) or eps > 1e-6:
        raise ValueError("Coordenadas numéricamente inestables respecto de su extensión.")
    cruces = [_cruz(q[i], q[j]) for i in range(1, len(q)) for j in range(i+1, len(q))]
    normal = max(cruces, key=lambda v: math.hypot(*v))
    modulo = math.hypot(*normal)
    if modulo <= eps:
        raise ValueError("Área nula o contorno numéricamente degenerado.")
    normal = tuple(x/modulo for x in normal)
    if any(abs(_punto(p, normal)) > eps for p in q):
        raise ValueError("Vértices no coplanares bajo el criterio computacional declarado.")
    eje = max(range(3), key=lambda k: abs(normal[k]))
    xy = [tuple(x for k, x in enumerate(p) if k != eje) for p in q]

    def orient(a, b, z):
        v = (b[0]-a[0])*(z[1]-a[1])-(b[1]-a[1])*(z[0]-a[0])
        return 0 if abs(v) <= eps else (1 if v > 0 else -1)

    def sobre(a, b, z):
        return all(min(a[k], b[k])-eps <= z[k] <= max(a[k], b[k])+eps for k in (0, 1))

    n = len(q)
    for i in range(n):
        a, b = xy[i], xy[(i+1) % n]
        if math.dist(a, b) <= eps:
            raise ValueError("Arista nula o numéricamente degenerada.")
        # Dos aristas adyacentes colineales no pueden retroceder sobre sí mismas.
        previo = xy[(i-1) % n]
        if orient(previo, a, b) == 0 and _punto(_resta(previo, a), _resta(b, a)) > eps:
            raise ValueError("Aristas adyacentes se superponen.")
        for j in range(i+1, n):
            if j == i+1 or (i == 0 and j == n-1):
                continue
            z, w = xy[j], xy[(j+1) % n]
            o = (orient(a, b, z), orient(a, b, w), orient(z, w, a), orient(z, w, b))
            if ((o[0]*o[1] < 0 and o[2]*o[3] < 0)
                    or any(s == 0 and sobre(u, v, p) for s, u, v, p in
                           ((o[0], a, b, z), (o[1], a, b, w), (o[2], z, w, a), (o[3], z, w, b)))):
                raise ValueError("Contorno no simple: cruce o contacto entre aristas no adyacentes.")
    suma = tuple(math.fsum(_cruz(q[i], q[(i+1) % n])[k] for i in range(n)) for k in range(3))
    area_rel = abs(_punto(suma, normal))/2
    area = (area_rel*escala)*escala
    if area_rel <= eps or not math.isfinite(area) or area <= 0:
        raise ValueError("Área nula, degenerada o no representable en m2.")
    # La orientación de la normal sigue el contorno, sin reordenarlo.
    if _punto(suma, normal) < 0:
        normal = tuple(-x for x in normal)
    return {"vertices_m": [list(p) for p in puntos], "area_m2": area,
            "normal_unitaria": list(normal), "epsilon_relativo_computacional": eps}


class _ValidadorSuperficies(_Validador):
    version = c.VERSION_GEOMETRIA_SUPERFICIES
    campos_raiz = c.CAMPOS_RAIZ_SUPERFICIES
    nombres_colecciones = tuple(c.COLECCIONES) + ("vertices", "superficies")

    def __init__(self, data):
        super().__init__(data)
        self.r.version_contrato = self.version

    def coleccion(self, nombre, elementos):
        if nombre in c.COLECCIONES:
            if isinstance(elementos, list) and not elementos:
                return  # v0.2 permite geometría solo de superficies, sin muros ficticios.
            return super().coleccion(nombre, elementos)
        ruta = "$."+nombre
        if not isinstance(elementos, list):
            self.error(ruta, "tipo_invalido", "Se requiere una lista explícita.")
            return
        spec = c.CAMPOS_VERTICE if nombre == "vertices" else c.CAMPOS_SUPERFICIE
        for i, elem in enumerate(elementos):
            r = f"{ruta}[{i}]"
            if not self.objeto(r, elem, spec):
                continue
            ident = self.identificador(r+".id", elem.get("id"))
            if ident is not None:
                if ident in self.ids[nombre]:
                    self.error(r+".id", "id_duplicado", "ID repetido en la colección.")
                else:
                    self.ids[nombre][ident] = elem
            if "procedencia" in elem:
                self.procedencia(r+".procedencia", elem["procedencia"])
            if nombre == "vertices":
                for clave in ("x", "y", "z"):
                    self.longitud(r+"."+clave, elem, clave, anulable=False, positivo=False)
            else:
                self.texto(r+".papel_geometrico", elem.get("papel_geometrico"))
                ids = elem.get("vertices")
                if not isinstance(ids, list) or len(ids) < 3:
                    self.error(r+".vertices", "contorno_invalido", "Se requieren al menos tres IDs ordenados, sin repetir el primero al final.")
                    continue
                vistos = set()
                for j, valor in enumerate(ids):
                    referencia = self.identificador(f"{r}.vertices[{j}]", valor)
                    if referencia is None:
                        continue
                    if referencia in vistos:
                        self.error(r+".vertices", "vertice_repetido", "El contorno repite un ID.")
                    if referencia not in self.ids["vertices"]:
                        self.error(f"{r}.vertices[{j}]", "referencia_inexistente", "Vértice no declarado.")
                    vistos.add(referencia)

    def normalizar(self):
        # Base conserva normalización/derivados y revisión del contenido COMPLETO.
        if not super().normalizar():
            return False
        g = self.r.geometria_m
        divisor = c.DIVISORES_A_METROS[self.data["unidad_longitud"]]
        for i, vertice in enumerate(g["vertices"]):
            for clave in ("x", "y", "z"):
                original = vertice[clave]
                metros = original/divisor
                if metros == 0 and original != 0:
                    self.error(f"$.vertices[{i}].{clave}", "normalizacion_a_cero", "Valor no representable en metros.")
                vertice[clave] = metros
        vertices = {v["id"]: tuple(v[k] for k in ("x", "y", "z")) for v in g["vertices"]}
        derivados = {}
        for i, superficie in enumerate(g["superficies"]):
            try:
                derivados[superficie["id"]] = _poligono([vertices[v] for v in superficie["vertices"]])
            except (ValueError, OverflowError) as exc:
                self.error(f"$.superficies[{i}].vertices", "superficie_invalida", str(exc))
        if self.r.errores:
            self.r.geometria_m = self.r.derivados_m = self.r.huella_contenido = None
            return False
        self.r.derivados_m["superficies"] = derivados
        self.r.bloqueos.append(BLOQUEO_INTEGRACION)
        return True


def validar_superficies(data):
    """Entrada pública habitual: validacion_geometria.validar_geometria(data)."""
    return _ValidadorSuperficies(data).ejecutar()


def migrar_a_superficies(data):
    """Copia v0.1 consistente a v0.2 borrador; no cambia el original ni hereda aprobación."""
    if not isinstance(data, dict) or data.get("version_contrato") != c.VERSION_GEOMETRIA:
        raise ValueError("La migración exige geometría v0.1 explícita.")
    if not _Validador(data).ejecutar().consistente:
        raise ValueError("La geometría v0.1 contiene errores; no se migra.")
    nueva = copy.deepcopy(data)
    nueva.update(version_contrato=c.VERSION_GEOMETRIA_SUPERFICIES, vertices=[], superficies=[],
                 revision={"estado": "borrador", "aprobacion": None})
    return nueva
