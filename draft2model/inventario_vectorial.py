"""Inventario geométrico desde el dibujo vectorial del PDF (sin OCR ni píxeles), con trazabilidad por elemento.

Técnicas:
- `segmentos`: segmentos rectos de una región, filtrados por grosor de trazo (en estos planos, 1,32 pt = concreto
  —columnas y placas— y 0,84 pt = cimientos, cotas y marcas). El grosor es una CONVENCIÓN del dibujo que el revisor
  confirma visualmente; no se supone en general.
- `componentes`: agrupa segmentos que comparten extremos (≤ tolerancia) en contornos; separa elementos (contornos
  con caja ≥ `min_m`) de trazos de rótulos (letras dibujadas como líneas, que no se leen).
- `franjas_paralelas`: pares de segmentos paralelos (horizontales/verticales) separados por un ancho dentro de un
  intervalo y con solape suficiente → eje y ancho de una franja (cimiento corrido, muro, placa).
- `a_metros`: transformación afín por eje (pt → m) desde una calibración registrada (`calibracion_ejes.registrar`).

Los rótulos (C-2, PL-4…) son trazos, no texto: la identificación se declara por revisión visual, nunca se infiere.
"""
from __future__ import annotations

import math
from pathlib import Path

import pymupdf


def segmentos(pdf: Path, pagina: int, region_pt: tuple[float, float, float, float], *, grosor: float | None = None,
              tol_grosor: float = 0.02, largo_min_pt: float = 0.5) -> list[dict]:
    """Segmentos 'l' cuyo extremo menor está en la región (coordenadas sin rotar del PDF)."""
    x0, y0, x1, y1 = region_pt
    salida = []
    with pymupdf.open(pdf) as doc:
        page = doc[pagina - 1]
        for dr in page.get_drawings():
            w = dr.get("width") or 0.0
            if grosor is not None and abs(w - grosor) > tol_grosor:
                continue
            for it in dr["items"]:
                if it[0] == "l":
                    lados = [(it[1], it[2])]
                elif it[0] == "re":  # rectángulo: sus cuatro lados (columnas dibujadas como primitivas)
                    r = it[1]
                    esq = [pymupdf.Point(r.x0, r.y0), pymupdf.Point(r.x1, r.y0), pymupdf.Point(r.x1, r.y1), pymupdf.Point(r.x0, r.y1)]
                    lados = list(zip(esq, esq[1:] + esq[:1]))
                elif it[0] == "qu":
                    q = it[1]
                    esq = [q.ul, q.ur, q.lr, q.ll]
                    lados = list(zip(esq, esq[1:] + esq[:1]))
                else:
                    continue
                for a, b in lados:
                    if not (x0 <= min(a.x, b.x) <= x1 and y0 <= min(a.y, b.y) <= y1):
                        continue
                    largo = math.hypot(a.x - b.x, a.y - b.y)
                    if largo >= largo_min_pt:
                        salida.append({"p": (a.x, a.y), "q": (b.x, b.y), "largo": largo, "grosor": w, "tipo": it[0]})
    return salida


def componentes(segs: list[dict], *, tol_pt: float = 0.6) -> list[dict]:
    """Componentes conexas por extremos coincidentes; caja y longitud total por componente."""
    padre = list(range(len(segs)))

    def raiz(i):
        while padre[i] != i:
            padre[i] = padre[padre[i]]
            i = padre[i]
        return i

    # Las celdas solo indexan candidatos (R243-02): la unión exige distancia euclídea ≤ tol entre extremos.
    claves = {}
    for i, s in enumerate(segs):
        for punto in (s["p"], s["q"]):
            celda = (round(punto[0] / tol_pt), round(punto[1] / tol_pt))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for j, otro in claves.get((celda[0] + dx, celda[1] + dy), ()):
                        if math.hypot(punto[0] - otro[0], punto[1] - otro[1]) <= tol_pt:
                            ra, rb = raiz(i), raiz(j)
                            if ra != rb:
                                padre[ra] = rb
            claves.setdefault(celda, []).append((i, punto))
    grupos = {}
    for i in range(len(segs)):
        grupos.setdefault(raiz(i), []).append(segs[i])
    salida = []
    for miembros in grupos.values():
        xs = [c for s in miembros for c in (s["p"][0], s["q"][0])]
        ys = [c for s in miembros for c in (s["p"][1], s["q"][1])]
        salida.append({"caja_pt": (min(xs), min(ys), max(xs), max(ys)), "segmentos": miembros,
                       "largo_total_pt": sum(s["largo"] for s in miembros)})
    return salida


def franjas_paralelas(segs: list[dict], *, ancho_pt: tuple[float, float], solape_min_pt: float,
                      tol_ang: float = 0.05) -> list[dict]:
    """Pares de segmentos horizontales o verticales separados por un ancho en `ancho_pt` y solapados."""
    def orient(s):
        dx, dy = s["q"][0] - s["p"][0], s["q"][1] - s["p"][1]
        if abs(dy) <= tol_ang * abs(dx):
            return "h"
        if abs(dx) <= tol_ang * abs(dy):
            return "v"
        return None

    por = {"h": [], "v": []}
    for s in segs:
        o = orient(s)
        if o:
            k, (a, b) = (1, (0, 0)) if o == "h" else (0, (1, 1))
            fijo = (s["p"][k] + s["q"][k]) / 2
            ini, fin = sorted((s["p"][1 - k], s["q"][1 - k]))
            por[o].append((fijo, ini, fin))
    franjas = []
    for o, lista in por.items():
        lista.sort()
        for i, (f1, a1, b1) in enumerate(lista):
            for f2, a2, b2 in lista[i + 1:]:
                sep = f2 - f1
                if sep > ancho_pt[1]:
                    break
                if sep < ancho_pt[0]:
                    continue
                ini, fin = max(a1, a2), min(b1, b2)
                if fin - ini >= solape_min_pt:
                    franjas.append({"orientacion": o, "eje_pt": (f1 + f2) / 2, "ancho_pt": sep, "desde_pt": ini, "hasta_pt": fin})
    return franjas


def a_metros(valor_pt: float, registro: dict, eje: str) -> float:
    """Convierte una coordenada de la lámina registrada a metros con su ajuste (pendiente y ordenada)."""
    r = registro[eje]
    return r["pendiente"] * valor_pt + r["ordenada"]


def rectangulos(segs: list[dict], *, lados_pt: tuple[float, float], tol_pt: float = 1.2) -> list[dict]:
    """Rectángulos alineados cerrados por cuatro segmentos (cualquier grosor), con lados en `lados_pt`.

    Un lado puede estar formado por un segmento más largo (p. ej. una columna adosada a la línea de un cimiento):
    se exige que cada lado esté cubierto por algún segmento colineal que lo contenga.
    """
    hs, vs = [], []
    for s in segs:
        (ax, ay), (bx, by) = s["p"], s["q"]
        if abs(ay - by) <= 0.05 * max(1e-9, abs(ax - bx)):
            hs.append(((ay + by) / 2, min(ax, bx), max(ax, bx)))
        elif abs(ax - bx) <= 0.05 * max(1e-9, abs(ay - by)):
            vs.append(((ax + bx) / 2, min(ay, by), max(ay, by)))

    def cubre(lista, fijo, a, b):
        return any(abs(f - fijo) <= tol_pt and i <= a + tol_pt and e >= b - tol_pt for f, i, e in lista)

    lo, hi = lados_pt
    candidatos = set()
    for y1, a1, b1 in hs:
        for y2, a2, b2 in hs:
            alto = y2 - y1
            if not lo - tol_pt <= alto <= hi + tol_pt:
                continue
            # Extremos x candidatos: los de cualquiera de los dos horizontales.
            for xa in (a1, a2):
                for xb in (b1, b2):
                    ancho = xb - xa
                    if lo - tol_pt <= ancho <= hi + tol_pt and cubre(hs, y1, xa, xb) and cubre(hs, y2, xa, xb) \
                            and cubre(vs, xa, y1, y2) and cubre(vs, xb, y1, y2):
                        candidatos.add((round(xa, 1), round(y1, 1), round(xb, 1), round(y2, 1)))
    # Quitar duplicados casi idénticos.
    salida = []
    for c in sorted(candidatos):
        if all(max(abs(c[i] - d["caja_pt"][i]) for i in range(4)) > tol_pt for d in salida):
            salida.append({"caja_pt": c})
    return salida


def _lado_cubierto(verticales, x, y0, y1, tol, junta_pt: float = 0.6) -> bool:
    """El lado x∈[y0,y1] está cubierto por la unión de segmentos verticales colineales (admite lados partidos).

    `tol` (dimensional) ubica el lado; las discontinuidades a lo largo del lado se juzgan a escala de junta
    (`junta_pt`), no con la tolerancia dimensional.
    """
    tramos = sorted((max(a, y0), min(b, y1)) for xv, a, b in verticales if abs(xv - x) <= tol and b > y0 and a < y1)
    alcance = y0
    for a, b in tramos:
        if a > alcance + junta_pt:
            return False
        alcance = max(alcance, b)
    return alcance >= y1 - junta_pt


def ajustar_rectangulo(segs: list[dict], punto_pt: tuple[float, float], lados_m: tuple[float, float], k_m_por_pt: float, *,
                       ventana_pt: float = 30.0, tol_m: float = 0.03) -> dict:
    """Ajusta el contorno de un elemento de sección conocida (p. ej. C-2 0,15×0,40) a los trazos cercanos a un punto.

    Toma los segmentos horizontales y verticales dentro de la ventana cuya longitud coincide con un lado esperado
    (± tol) — o que lo contienen, si el elemento está adosado a otra línea — y devuelve la caja si sus dimensiones
    concuerdan con la sección en alguna orientación. Si no concuerda, `estado = no_ajustado` (no se fuerza).
    """
    px, py = punto_pt
    a_pt, b_pt = (l / k_m_por_pt for l in lados_m)
    tol = tol_m / k_m_por_pt
    hs, vs = [], []
    # Todos los verticales cercanos (cualquier longitud) sirven para verificar cierres, también partidos.
    todos_v = [((s["p"][0] + s["q"][0]) / 2, min(s["p"][1], s["q"][1]), max(s["p"][1], s["q"][1])) for s in segs
               if abs(s["p"][0] - s["q"][0]) < 0.3 and abs(s["p"][1] - s["q"][1]) > 0
               and abs((s["p"][0] + s["q"][0]) / 2 - px) <= ventana_pt + max(a_pt, b_pt)]
    for s in segs:
        (x1, y1), (x2, y2) = s["p"], s["q"]
        if max(abs((x1 + x2) / 2 - px), abs((y1 + y2) / 2 - py)) > ventana_pt + max(a_pt, b_pt):
            continue
        largo = s["largo"]
        if abs(y1 - y2) < 0.3 and any(abs(largo - l) <= tol for l in (a_pt, b_pt)):
            hs.append(((y1 + y2) / 2, min(x1, x2), max(x1, x2)))
        elif abs(x1 - x2) < 0.3 and any(abs(largo - l) <= tol for l in (a_pt, b_pt)):
            vs.append(((x1 + x2) / 2, min(y1, y2), max(y1, y2)))
    mejor = None
    for orient, (ancho, alto) in (("x_largo", (max(a_pt, b_pt), min(a_pt, b_pt))), ("y_largo", (min(a_pt, b_pt), max(a_pt, b_pt)))):
        for y, x0, x1 in hs:
            if abs((x1 - x0) - ancho) > tol:
                continue
            for y2, x02, x12 in hs:
                if abs(abs(y2 - y) - alto) > tol or abs(x02 - x0) > tol or abs(x12 - x1) > tol:
                    continue
                caja = (x0, min(y, y2), x1, max(y, y2))
                if not (caja[0] - ventana_pt <= px <= caja[2] + ventana_pt and caja[1] - ventana_pt <= py <= caja[3] + ventana_pt):
                    continue
                lados_v = sum(_lado_cubierto(todos_v, x, caja[1], caja[3], tol) for x in (caja[0], caja[2]))
                d = math.hypot((caja[0] + caja[2]) / 2 - px, (caja[1] + caja[3]) / 2 - py)
                if mejor is None or (lados_v, -d) > (mejor[0], -mejor[1]):
                    mejor = (lados_v, d, caja, orient)
    if mejor is None:
        return {"estado": "no_ajustado", "punto_pt": punto_pt}
    lados_v, d, caja, orient = mejor
    if lados_v < 2:
        # R243-01: dos bordes paralelos sin ambos cierres no prueban el contorno del elemento.
        return {"estado": "incompleto", "punto_pt": punto_pt, "caja_candidata_pt": caja, "lados_verticales_confirmados": lados_v,
                "motivo": "Faltan cierres laterales verificables; no se confirma la sección por similitud."}
    return {"estado": "ajustado", "caja_pt": caja, "orientacion": orient, "lados_verticales_confirmados": lados_v,
            "distancia_al_punto_pt": d,
            "dim_m": [round((caja[2] - caja[0]) * k_m_por_pt, 3), round((caja[3] - caja[1]) * k_m_por_pt, 3)]}
