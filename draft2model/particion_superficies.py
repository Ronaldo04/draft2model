"""Partición geométrica conforme de una superficie plana con huecos (geometría 0.3); sin ETABS.

API pura: `particionar_superficie(geometria, superficie_id) -> dict`; errores `ErrorParticion(ValueError)`.

Método (sin dependencias):
1. `validar_geometria` 0.3 consistente; coordenadas en metros desde `geometria_m`.
2. Proyección exacta: traslación al primer vértice del host y descarte del eje dominante de su normal
   (sin escalado), en aritmética racional `Fraction` desde los binary64 de entrada.
3. Barrido por franjas en TODAS las abscisas de vértices (host y huecos). En cada franja, las aristas
   no verticales activas se ordenan exactamente y la regla par/impar delimita trapecios interiores.
4. Conformidad: cada trapecio incorpora todos los nodos situados sobre sus lados verticales (también los
   que aportan las franjas vecinas o los extremos de huecos), de modo que no hay nodos colgantes.
5. Todo nodo es un vértice fuente o un punto de una arista fuente con parámetro t racional exacto; su XYZ se
   interpola sobre esa arista en 3D con un único redondeo.
6. Verificación previa a la publicación: área exacta (celdas = bruta − huecos), aristas interiores con dos
   incidencias opuestas y de frontera con una, cadenas ordenadas por arista fuente, sin nodos colgantes,
   orientación según la normal del host, nodos distintos tras binary64 y celdas no degeneradas con el
   criterio computacional existente. Si algo no se verifica, se rechaza: no hay partición parcial.

No decide tamaño de elemento, calidad de malla ni criterios de ingeniería; no asigna material, ejes, cargas
ni masa; no acredita compatibilidad entre superficies distintas (pendiente). No ejecutable.
"""
from __future__ import annotations

import copy
import hashlib
import json
import marshal
import math
from collections import OrderedDict
from threading import RLock
from bisect import bisect_left, bisect_right
from fractions import Fraction
from typing import Any

from . import contratos as c
from .validacion_geometria import validar_geometria

CONTRATO = "draft2model.particion_superficie"
VERSION = "0.1.0"
MAX_PARTICIONES_BYTES = 16 * 1024 * 1024
MAX_PARTICIONES_ENTRADAS = 8192
PENDIENTES = [
    "Asignación de sección/material, ejes locales, cargas y masa a las piezas (Codex).",
    "Compatibilidad de nodos con superficies vecinas, muros y frames: la partición solo acredita conformidad intrahost.",
    "Revisión de calidad de malla (proporciones, ángulos de 180° por nodos de conformidad, tamaño máximo) con criterios declarados.",
    "Transporte ETABS de las piezas, guardado, reapertura y relectura independiente.",
]


class ErrorParticion(ValueError):
    """Entrada no admitida o partición no verificable; nunca se publica un resultado parcial."""


def _canonico(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(data: Any) -> str:
    return hashlib.sha256(_canonico(data)).hexdigest()


def _binario_local(data):
    """Captura completa tipada y efímera; solo dumps. JSON canónico conserva SHA y fallback.

    Formato2 evita referencias/identidad de objetos. Nunca se carga este binario ni se persiste.
    Una captura distinta NO decide equivalencia: se vuelve a comparar JSON canónico.
    """
    try:
        return marshal.dumps(data, 2)
    except (TypeError, ValueError, OverflowError, RecursionError):
        return None


class _ContextoGeometria:
    """Validación e índices privados para una preparación; nunca se comparte entre invocaciones.

    Se valida una copia propia, no un resultado aportado por el llamador. Cada consumo
    compara la fuente completa: la identidad del dict o una huella declarada no bastan.
    La serialización sustituye la que ya hacía cada partición para su SHA de origen.
    """

    def __init__(self, geometria):
        fuente = copy.deepcopy(geometria)
        self._validacion = validar_geometria(fuente)
        try:
            self._fuente = _canonico(fuente)
        except (TypeError, ValueError) as exc:
            raise ErrorParticion("Geometría no serializable como JSON estricto.") from exc
        self._sha = hashlib.sha256(self._fuente).hexdigest()
        self._captura_binaria = _binario_local(fuente)
        # Solo cálculos puros de esta fuente/contexto. Nunca evidencias ni archivos.
        self._particiones = OrderedDict()
        self._particiones_bytes = 0
        self._particiones_lock = RLock()
        g = self._validacion.geometria_m or {}
        self._superficies = {s["id"]: s for s in g.get("superficies", [])}
        self._xyz = {v["id"]: (v["x"], v["y"], v["z"]) for v in g.get("vertices", [])}
        self._huecos = {}
        for a in g.get("aberturas", []):
            self._huecos.setdefault(a["superficie"], []).append(a)

    def verificar(self, geometria):
        if self._captura_binaria is not None:
            actual_binario = _binario_local(geometria)
            if actual_binario is not None and actual_binario == self._captura_binaria:
                return self._sha, self._validacion
        try:
            actual = _canonico(geometria)
        except (TypeError, ValueError) as exc:
            raise ErrorParticion("Geometría no serializable como JSON estricto.") from exc
        if actual != self._fuente:
            raise ErrorParticion("La geometría cambió durante la preparación de la malla.")
        return self._sha, self._validacion

    def _particion_previa(self, sid):
        with self._particiones_lock:
            entry = self._particiones.get(sid)
            if entry is None:
                return None
            raw, digest, weight = entry
            if hashlib.sha256(raw).digest() != digest:
                self._particiones_bytes -= weight
                del self._particiones[sid]
                return None
            self._particiones.move_to_end(sid)
        return json.loads(raw)

    def _conservar_particion(self, sid, datos):
        from .cache_malla_pura import _exacto_o_none
        raw = _exacto_o_none(datos)
        if raw is None:
            return
        weight = len(raw) + len(sid.encode('utf-8')) + 32
        if weight > MAX_PARTICIONES_BYTES:
            return
        entry = (raw, hashlib.sha256(raw).digest(), weight)
        with self._particiones_lock:
            old = self._particiones.pop(sid, None)
            if old is not None:
                self._particiones_bytes -= old[2]
            while self._particiones and (len(self._particiones) >= MAX_PARTICIONES_ENTRADAS
                                         or self._particiones_bytes + weight > MAX_PARTICIONES_BYTES):
                key, removed = self._particiones.popitem(last=False)
                self._particiones_bytes -= removed[2]
            self._particiones[sid] = entry
            self._particiones_bytes += weight


def _area2(puntos):
    """Doble del área orientada (exacta con Fraction)."""
    n = len(puntos)
    return sum(puntos[i][0] * puntos[(i + 1) % n][1] - puntos[(i + 1) % n][0] * puntos[i][1] for i in range(n))


def _orient(a, b, p):
    v = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
    return (v > 0) - (v < 0)


def _dentro(p, poligono):
    """Par/impar exacto; p no debe estar sobre el borde (se comprueba aparte)."""
    dentro = False
    n = len(poligono)
    for i in range(n):
        a, b = poligono[i], poligono[(i + 1) % n]
        if (a[1] > p[1]) != (b[1] > p[1]):
            x = a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if x > p[0]:
                dentro = not dentro
    return dentro


def _fraccion_texto(f: Fraction) -> str:
    return f"{f.numerator}/{f.denominator}"


def _nodos_laterales(recta_izquierda, recta_derecha, bl, br, tr, tl):
    """Nodos estrictamente interiores de los lados verticales (conformidad con franjas vecinas y huecos)."""
    derecha = [p for p in recta_derecha if br[1] < p[1] < tr[1]]
    izquierda = [p for p in reversed(recta_izquierda) if bl[1] < p[1] < tl[1]]
    return derecha, izquierda


def particionar_superficie(geometria: Any, superficie_id: Any, *, _contexto=None) -> dict:
    """Partición conforme verificada de `superficie_id` y todos sus huecos. No modifica la entrada."""
    if not isinstance(geometria, dict):
        raise ErrorParticion("La geometría debe ser un objeto JSON.")
    if geometria.get("version_contrato") != c.VERSION_GEOMETRIA_ABERTURAS:
        raise ErrorParticion("Se exige geometría 0.3.0 explícita; no se reinterpreta otra versión.")
    if _contexto is None:
        try:
            sha_fuente = _sha(geometria)
        except (TypeError, ValueError) as exc:
            raise ErrorParticion("Geometría no serializable como JSON estricto.") from exc
        vg = validar_geometria(copy.deepcopy(geometria))
    else:
        sha_fuente, vg = _contexto.verificar(geometria)
    if not vg.consistente:
        raise ErrorParticion("Geometría inconsistente: " + "; ".join(str(e) for e in vg.errores)[:1500])
    g, der = vg.geometria_m, vg.derivados_m
    superficies = _contexto._superficies if _contexto is not None else {s["id"]: s for s in g["superficies"]}
    if not isinstance(superficie_id, str) or superficie_id not in superficies:
        raise ErrorParticion("Superficie inexistente en la geometría.")
    if _contexto is not None:
        # La fuente COMPLETA ya se comprobó arriba, incluso en cada acierto.
        previa = _contexto._particion_previa(superficie_id)
        if previa is not None:
            return previa
    host = superficies[superficie_id]
    dhost = der["superficies"][superficie_id]
    huecos = (_contexto._huecos.get(superficie_id, []) if _contexto is not None
              else [a for a in g["aberturas"] if a["superficie"] == superficie_id])
    xyz = _contexto._xyz if _contexto is not None else {v["id"]: (v["x"], v["y"], v["z"]) for v in g["vertices"]}
    normal = dhost["normal_unitaria"]
    eps = dhost["epsilon_relativo_computacional"]
    eje = max(range(3), key=lambda k: abs(normal[k]))
    ejes = [k for k in range(3) if k != eje]
    origen = xyz[host["vertices"][0]]
    # Signo que relaciona la orientación proyectada (u, v) con la normal del host.
    signo = (1 if normal[eje] > 0 else -1) * (-1 if eje == 1 else 1)

    def proyectar(vid):
        p = xyz[vid]
        return (Fraction(p[ejes[0]]) - Fraction(origen[ejes[0]]), Fraction(p[ejes[1]]) - Fraction(origen[ejes[1]]))

    contornos = [("superficie:" + superficie_id, list(host["vertices"]))] + [("hueco:" + a["id"], list(a["vertices"])) for a in huecos]
    p2 = {}
    for _, ids in contornos:
        for vid in ids:
            p2[vid] = proyectar(vid)
    if len(set(p2.values())) != len(p2):
        raise ErrorParticion("Vértices distintos coinciden en la proyección del host; caso ambiguo rechazado.")
    aristas = []  # (contorno, indice, desde, hasta)
    for nombre, ids in contornos:
        for i in range(len(ids)):
            aristas.append((nombre, i, ids[i], ids[(i + 1) % len(ids)]))

    abscisas = sorted({p[0] for p in p2.values()})
    nodos = {}  # punto exacto -> datos

    def nodo_en(arista, x):
        nombre, i, a, b = arista
        pa, pb = p2[a], p2[b]
        if x == pa[0]:
            return pa, {"tipo": "original", "vertice": a}
        if x == pb[0]:
            return pb, {"tipo": "original", "vertice": b}
        t = (x - pa[0]) / (pb[0] - pa[0])
        return (x, pa[1] + t * (pb[1] - pa[1])), {"tipo": "sobre_arista", "contorno": nombre, "arista": i, "desde": a, "hasta": b, "t": t}

    def registrar(punto, traza):
        previo = nodos.get(punto)
        if previo is None:
            nodos[punto] = traza
        elif previo["tipo"] == "sobre_arista" and traza["tipo"] == "sobre_arista" and \
                (previo["contorno"], previo["arista"]) != (traza["contorno"], traza["arista"]):
            raise ErrorParticion("Un punto calculado pertenece a dos aristas fuente distintas; caso no admitido.")
        return punto

    for vid, p in p2.items():
        registrar(p, {"tipo": "original", "vertice": vid})
    # Puntos de cada recta de barrido: vértices y cortes de aristas que la atraviesan.
    en_recta = {x: set() for x in abscisas}
    for ar in aristas:
        ua, ub = p2[ar[2]][0], p2[ar[3]][0]
        lo, hi = min(ua, ub), max(ua, ub)
        for x in abscisas[bisect_left(abscisas, lo):bisect_right(abscisas, hi)]:
            if ua == ub:
                for vid in (ar[2], ar[3]):
                    en_recta[x].add(p2[vid])
            else:
                punto, traza = nodo_en(ar, x)
                en_recta[x].add(registrar(punto, traza))
    ordenados = {x: sorted(s, key=lambda p: p[1]) for x, s in en_recta.items()}

    celdas = []
    for k in range(len(abscisas) - 1):
        x0, x1 = abscisas[k], abscisas[k + 1]
        medio = (x0 + x1) / 2
        activas = []
        for ar in aristas:
            ua, ub = p2[ar[2]][0], p2[ar[3]][0]
            if ua != ub and min(ua, ub) <= x0 and max(ua, ub) >= x1:
                y = nodo_en(ar, medio)[0][1]
                activas.append((y, ar))
        activas.sort(key=lambda e: e[0])
        if len({e[0] for e in activas}) != len(activas):
            raise ErrorParticion("Aristas superpuestas en una franja; caso no admitido.")
        if len(activas) % 2:
            raise ErrorParticion("Paridad impar en una franja: contornos no cerrados o no simples.")
        for j in range(0, len(activas), 2):
            inferior, superior = activas[j][1], activas[j + 1][1]
            bl, br = nodo_en(inferior, x0)[0], nodo_en(inferior, x1)[0]
            tr, tl = nodo_en(superior, x1)[0], nodo_en(superior, x0)[0]
            derecha, izquierda = _nodos_laterales(ordenados[x0], ordenados[x1], bl, br, tr, tl)
            poligono = [bl, br] + derecha + ([tr] if tr != br else []) + ([tl] if tl != bl else []) + izquierda
            if tl == bl and izquierda or tr == br and derecha:
                raise ErrorParticion("Lado degenerado con nodos interiores; caso no admitido.")
            celdas.append({"franja": k, "puntos2": poligono})

    # -- identificadores deterministas --
    en_celdas = {p for celda in celdas for p in celda["puntos2"]}
    calculados = sorted(p for p in en_celdas if nodos[p]["tipo"] != "original")
    ident = {p: t["vertice"] for p, t in nodos.items() if t["tipo"] == "original"}
    for i, p in enumerate(calculados, 1):
        ident[p] = f"{superficie_id}#n{i}"

    def xyz_de(p):
        t = nodos[p]
        if t["tipo"] == "original":
            return list(xyz[t["vertice"]])
        a, b, f = xyz[t["desde"]], xyz[t["hasta"]], t["t"]
        return [float(Fraction(a[i]) + f * (Fraction(b[i]) - Fraction(a[i]))) for i in range(3)]

    usados = sorted(en_celdas | set(p2.values()), key=lambda p: (p[0], p[1]))
    coords = {p: xyz_de(p) for p in usados}
    if len({tuple(v) for v in coords.values()}) != len(coords):
        raise ErrorParticion("Nodos distintos colapsan al convertir a binary64; partición no verificable.")
    salida_celdas = []
    for i, celda in enumerate(celdas, 1):
        pts = celda["puntos2"] if signo > 0 else list(reversed(celda["puntos2"]))
        salida_celdas.append({"id": f"{superficie_id}#c{i}", "nodos": [ident[p] for p in pts], "franja": celda["franja"],
                              "tipo": "triangulo" if len(pts) == 3 else "convexa", "_p2": pts})

    resultado = _verificar_y_publicar(geometria, sha_fuente, vg, host, dhost, huecos, der, contornos, aristas, p2, nodos,
                                      ident, coords, salida_celdas, eje, ejes, origen, signo, eps, normal)
    if _contexto is not None:
        _contexto._conservar_particion(superficie_id, resultado)
    return resultado


def _verificar_y_publicar(geometria, sha_fuente, vg, host, dhost, huecos, der, contornos, aristas, p2, nodos, ident,
                          coords, celdas, eje, ejes, origen, signo, eps, normal):
    problemas = []
    # 1. Área exacta proyectada y orientación coherente con la normal.
    area_host = abs(_area2([p2[v] for v in contornos[0][1]]))
    area_huecos = sum(abs(_area2([p2[v] for v in ids])) for _, ids in contornos[1:])
    suma = 0
    for celda in celdas:
        a2 = _area2(celda["_p2"]) * signo
        if a2 <= 0:
            problemas.append(f"Celda {celda['id']} con área proyectada no positiva u orientación incoherente.")
        suma += a2
        for i in range(len(celda["_p2"])):  # convexidad (ángulos de 180° admitidos por nodos de conformidad)
            a, b, d = celda["_p2"][i - 1], celda["_p2"][i], celda["_p2"][(i + 1) % len(celda["_p2"])]
            if _orient(a, b, d) * signo < 0:
                problemas.append(f"Celda {celda['id']} no convexa.")
                break
    if suma != area_host - area_huecos:
        problemas.append("La suma exacta de celdas no iguala área bruta menos huecos.")
    # 2. Celdas dentro del host y fuera de todo hueco (centroide exacto, nunca sobre un borde por convexidad).
    host2 = [p2[v] for v in contornos[0][1]]
    huecos2 = [[p2[v] for v in ids] for _, ids in contornos[1:]]
    for celda in celdas:
        pts = celda["_p2"]
        cen = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
        if not _dentro(cen, host2) or any(_dentro(cen, h) for h in huecos2):
            problemas.append(f"Celda {celda['id']} fuera del host o dentro de un hueco.")
    # 3. Incidencias de aristas.
    dirigidas = {}
    for celda in celdas:
        ids = celda["nodos"]
        for i in range(len(ids)):
            clave = (ids[i], ids[(i + 1) % len(ids)])
            dirigidas[clave] = dirigidas.get(clave, 0) + 1
    if any(n != 1 for n in dirigidas.values()):
        problemas.append("Arista dirigida repetida: solape u orientación incoherente.")
    no_dirigidas = {}
    for (a, b) in dirigidas:
        no_dirigidas.setdefault(frozenset((a, b)), []).append((a, b))
    frontera = {k for k, v in no_dirigidas.items() if len(v) == 1}
    interiores = {k for k, v in no_dirigidas.items() if len(v) == 2}
    if len(frontera) + len(interiores) != len(no_dirigidas):
        problemas.append("Arista con más de dos incidencias.")
    # 4. Cadenas: cada arista fuente se conserva como cadena ordenada de segmentos de frontera.
    por_id = {v: k for k, v in ident.items()}
    cadenas, cubiertas = [], set()
    for nombre, i, a, b in aristas:
        pa, pb = p2[a], p2[b]
        en_arista = [p for p in por_id.values() if _orient(pa, pb, p) == 0
                     and min(pa[0], pb[0]) <= p[0] <= max(pa[0], pb[0]) and min(pa[1], pb[1]) <= p[1] <= max(pa[1], pb[1])]
        clave = (lambda p: p[0]) if pa[0] != pb[0] else (lambda p: p[1])
        inversa = clave(pb) < clave(pa)
        cadena = sorted(en_arista, key=clave, reverse=inversa)
        nombres = [ident[p] for p in cadena]
        if not nombres or nombres[0] != a or nombres[-1] != b:
            problemas.append(f"Cadena de {nombre}[{i}] sin sus extremos fuente.")
        for u, w in zip(nombres, nombres[1:]):
            seg = frozenset((u, w))
            if seg not in frontera:
                problemas.append(f"Segmento de {nombre}[{i}] no es frontera simple de la partición.")
            cubiertas.add(seg)
        cadenas.append({"contorno": nombre, "arista": i, "desde": a, "hasta": b, "nodos": nombres})
    if frontera != cubiertas:
        problemas.append("Hay aristas de frontera que no pertenecen a ningún contorno fuente.")
    # 5. Sin nodos colgantes: ningún nodo dentro de una arista de celda.
    todos = sorted(por_id.values())
    xs = [p[0] for p in todos]
    for celda in celdas:
        pts = celda["_p2"]
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            for p in todos[bisect_left(xs, min(a[0], b[0])):bisect_right(xs, max(a[0], b[0]))]:
                if p not in (a, b) and _orient(a, b, p) == 0 and min(a[1], b[1]) <= p[1] <= max(a[1], b[1]):
                    problemas.append(f"Nodo colgante {ident[p]} sobre una arista de {celda['id']}.")
    # 6. Representación binary64: área 3D (Newell) positiva y no degenerada según el criterio existente.
    escala = max(abs(x - o) for p in coords.values() for x, o in zip(p, origen)) or 0
    area_celdas_m2 = []
    for celda in celdas:
        q = [coords[por_id[n]] for n in celda["nodos"]]
        newell = [math.fsum((q[i][(k + 1) % 3] - q[(i + 1) % len(q)][(k + 1) % 3]) * (q[i][(k + 2) % 3] + q[(i + 1) % len(q)][(k + 2) % 3])
                            for i in range(len(q))) for k in range(3)]
        proyectada = math.fsum(nk * hk for nk, hk in zip(newell, normal)) / 2
        if not math.isfinite(proyectada) or proyectada <= eps * escala * escala:
            problemas.append(f"Celda {celda['id']} degenerada u orientada al revés en binary64.")
        area_celdas_m2.append(proyectada)
    if problemas:
        raise ErrorParticion("Partición no verificable; no se publica: " + " | ".join(sorted(set(problemas)))[:2000])

    factor = 1 / abs(normal[eje])  # área real = proyectada / |n_eje|
    nodos_salida = []
    for p in sorted(por_id.values(), key=lambda p: (p[0], p[1])):
        t = nodos[p]
        traza = {"tipo": "original", "vertice": t["vertice"]} if t["tipo"] == "original" else {
            "tipo": "sobre_arista", "contorno": t["contorno"], "arista": t["arista"], "desde": t["desde"], "hasta": t["hasta"],
            "t": _fraccion_texto(t["t"]), "t_aprox": float(t["t"]), "origen_calculo": "intersección con recta de barrido"}
        nodos_salida.append({"id": ident[p], "xyz_m": coords[p], "traza": traza})
    celdas_salida = [{"id": cl["id"], "nodos": cl["nodos"], "tipo": cl["tipo"], "franja": cl["franja"],
                      "area_m2": a, "pieza_de": host["id"]} for cl, a in zip(celdas, area_celdas_m2)]
    datos = {
        "contrato": CONTRATO, "version_contrato": VERSION, "ejecutable": False, "aprueba_ingenieria": False,
        "aviso": "Partición geométrica intrahost verificada; no es malla de ingeniería, ni asignación, ni prueba ETABS.",
        "origen": {"contrato_geometria": c.CONTRATO_GEOMETRIA, "version_geometria": c.VERSION_GEOMETRIA_ABERTURAS,
                   "sha256_geometria_canonica": sha_fuente, "huella_contenido": vg.huella_contenido,
                   "unidad_longitud_fuente": geometria["unidad_longitud"], "datos_sinteticos": vg.datos_sinteticos},
        "superficie": {"id": host["id"], "vertices": list(host["vertices"]), "papel_geometrico": host["papel_geometrico"],
                       "procedencia": copy.deepcopy(host["procedencia"]), "normal_unitaria": list(normal),
                       "area_bruta_m2": dhost["area_bruta_m2"]},
        "huecos": [{"id": a["id"], "vertices": list(a["vertices"]), "procedencia": copy.deepcopy(a["procedencia"]),
                    "area_m2": der["aberturas"][a["id"]]["area_m2"]} for a in huecos],
        "proyeccion": {"eje_descartado": "xyz"[eje], "ejes_proyectados": ["xyz"[k] for k in ejes], "origen_m": list(origen),
                       "signo_orientacion": signo, "aritmetica": "racional exacta desde binary64"},
        "nodos": nodos_salida,
        "celdas": celdas_salida,
        "cadenas_contorno": cadenas,
        "cobertura": {"area_bruta_m2": dhost["area_bruta_m2"], "area_huecos_m2": dhost["area_aberturas_m2"],
                      "area_neta_m2": dhost["area_neta_m2"], "area_celdas_m2": math.fsum(area_celdas_m2),
                      "igualdad_exacta_proyectada": True,
                      "area_proyectada_exacta": {"bruta_x2": _fraccion_texto(area_host), "huecos_x2": _fraccion_texto(area_huecos),
                                                 "celdas_x2": _fraccion_texto(area_host - area_huecos)},
                      "factor_area_real": factor},
        "comprobaciones": {"celdas": len(celdas), "nodos": len(nodos_salida), "nodos_originales": sum(1 for n in nodos_salida if n["traza"]["tipo"] == "original"),
                           "aristas_interiores": len(interiores), "aristas_frontera": len(frontera), "nodos_colgantes": 0,
                           "aristas_fuente_conservadas": len(cadenas), "orientacion": "según normal del host"},
        "compatibilidad_interhost": "pendiente: no se acreditan vínculos con otras superficies, muros o frames",
        "pendientes": list(PENDIENTES),
    }
    datos["huella_particion"] = _sha(datos)
    return datos
