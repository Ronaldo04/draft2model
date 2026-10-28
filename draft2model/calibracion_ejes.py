"""Calibración por cadenas de cotas impresas y registro entre láminas, con residuos por referencia.

Trabaja sobre texto vectorial del PDF (sin OCR ni píxeles):
1. `ejes_desde_texto`: posición de cada rótulo de eje declarado (mediana de sus apariciones) en una dirección.
2. `calibrar_cadena`: cotas impresas «n.nn» centradas entre ejes consecutivos → k (m/pt) por tramo, k mediano,
   residuo de cada tramo y total. Un tramo sin cota impresa queda «sin_referencia»; nunca se rellena.
3. `registrar`: correspondencias declaradas entre ejes de dos láminas (p. ej. estructural H ↔ arquitectura 2) →
   escala de la segunda lámina por mínimos cuadrados, residuo por correspondencia y posición derivada de cada eje.

Las correspondencias, la dirección y el origen son DECLARACIONES del revisor; la escala nominal del rótulo no se usa.
Que una distancia resulte redonda no prueba la escala: solo cuentan las referencias impresas y sus residuos.
"""
from __future__ import annotations

import re
import statistics
from pathlib import Path

import pymupdf

PATRON_COTA = re.compile(r"\d*\.\d{2}")


def _palabras(pdf: Path, pagina: int):
    with pymupdf.open(pdf) as doc:
        if not 1 <= pagina <= doc.page_count:
            raise ValueError("Página inexistente.")
        return doc[pagina - 1].get_text("words")


def ejes_desde_texto(pdf: Path, pagina: int, rotulos: list[str], direccion: str, *,
                     fijar: dict[str, float] | None = None) -> dict:
    """Coordenada (pt, espacio sin rotar del PDF) de cada rótulo a lo largo de `direccion` ('x' o 'y').

    Usa la mediana de las apariciones y exige al menos dos coherentes (≤ 2 pt): globos en ambos extremos.
    `fijar` declara la posición de un rótulo ambiguo (p. ej. un corte «B–B» homónimo); queda registrado.
    """
    if direccion not in ("x", "y") or len(set(rotulos)) != len(rotulos) or len(rotulos) < 2:
        raise ValueError("Dirección x/y y al menos dos rótulos distintos.")
    idx = 0 if direccion == "x" else 1
    palabras = _palabras(pdf, pagina)
    salida, fijados = {}, {}
    for r in rotulos:
        if fijar and r in fijar:
            salida[r] = fijados[r] = float(fijar[r])
            continue
        pos = [((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)[idx] for w in palabras if w[4] == r]
        # El mismo rótulo puede aparecer en otros textos (p. ej. «DORMITORIO 1»): se toma el grupo más numeroso
        # de apariciones coincidentes (globos de ambos extremos); un empate es ambiguo y no se resuelve.
        grupos = sorted(([q for q in pos if abs(q - c) <= 2.0] for c in pos), key=len, reverse=True)
        if not grupos or len(grupos[0]) < 2:
            raise ValueError(f"Eje {r!r}: menos de dos apariciones coherentes; declarar su posición de otro modo.")
        rivales = [g for g in grupos if len(g) == len(grupos[0]) and abs(statistics.median(g) - statistics.median(grupos[0])) > 2.0]
        if rivales:
            raise ValueError(f"Eje {r!r}: grupos de apariciones empatados; posición ambigua.")
        salida[r] = statistics.median(grupos[0])
    return {"direccion": direccion, "posiciones_pt": salida, "orden": sorted(salida, key=salida.get), "fijados": fijados}


def calibrar_cadena(pdf: Path, pagina: int, ejes: dict, *, tolerancia_pt: float = 4.0, fila_pt: float | None = None) -> dict:
    """k por tramo entre ejes consecutivos a partir de una fila de cotas impresas centradas en cada tramo.

    Las cotas se agrupan por fila (coordenada perpendicular, ±3 pt). Sin `fila_pt` se usa la fila que acota más
    tramos con un único valor; un empate entre filas es ambiguo y se rechaza.
    """
    idx = 0 if ejes["direccion"] == "x" else 1
    pos, orden = ejes["posiciones_pt"], ejes["orden"]
    cotas = [(float(w[4]), ((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)) for w in _palabras(pdf, pagina)
             if PATRON_COTA.fullmatch(w[4])]
    filas = sorted({round(c[1 - idx] / 3) * 3 for _, c in cotas})

    def tramos_de(fila):
        salida = []
        for a, b in zip(orden, orden[1:]):
            medio, largo = (pos[a] + pos[b]) / 2, pos[b] - pos[a]
            valores = sorted({v for v, c in cotas if abs(c[idx] - medio) <= tolerancia_pt and v > 0
                              and abs(c[1 - idx] - fila) <= 3.0})
            tramo = {"tramo": f"{a}-{b}", "pt": largo}
            if len(valores) == 1:
                tramo.update(cota_m=valores[0], k=valores[0] / largo)
            else:
                tramo.update(estado="sin_referencia" if not valores else "ambiguo", valores=valores)
            salida.append(tramo)
        return salida

    if fila_pt is None:
        puntaje = sorted(((sum("k" in t for t in tramos_de(f)), f) for f in filas), reverse=True)
        if not puntaje or puntaje[0][0] == 0:
            raise ValueError("Ninguna fila de cotas impresas acota tramos entre ejes consecutivos.")
        empatadas = [f for n, f in puntaje if n == puntaje[0][0]]
        fila_pt = empatadas[0]
        distintas = [f for f in empatadas if {t.get("cota_m") for t in tramos_de(f)} != {t.get("cota_m") for t in tramos_de(fila_pt)}]
        if distintas:
            raise ValueError(f"Filas de cotas empatadas con valores distintos ({[fila_pt] + distintas}); declarar fila_pt.")
    tramos = tramos_de(fila_pt)
    ks = [t["k"] for t in tramos if "k" in t]
    if not ks:
        raise ValueError("La fila indicada no acota ningún tramo.")
    k = statistics.median(ks)
    for t in tramos:
        if "k" in t:
            t["residuo_m"] = t["pt"] * k - t["cota_m"]
    total_pt = pos[orden[-1]] - pos[orden[0]]
    return {"k_m_por_pt": k, "k_min": min(ks), "k_max": max(ks), "referencias": len(ks), "fila_pt": fila_pt,
            "tramos": tramos, "total_m": total_pt * k,
            "residuo_max_m": max(abs(t["residuo_m"]) for t in tramos if "residuo_m" in t)}


def registrar(ejes_a: dict, k_a: float, ejes_b: dict, correspondencias: dict[str, str], *, origen_a: str) -> dict:
    """Ajuste lineal de la lámina B sobre la A (calibrada) con correspondencias declaradas {eje_B: eje_A}.

    Devuelve la escala de B, su sentido, el residuo por correspondencia y la posición (m, origen `origen_a`)
    de todos los ejes de B. Requiere al menos dos correspondencias en puntos distintos.
    """
    if len(correspondencias) < 2:
        raise ValueError("Se requieren al menos dos correspondencias declaradas.")
    pa, pb = ejes_a["posiciones_pt"], ejes_b["posiciones_pt"]
    if origen_a not in pa or any(b not in pb or a not in pa for b, a in correspondencias.items()):
        raise ValueError("Eje de correspondencia u origen inexistente.")
    xb = [pb[b] for b in correspondencias]
    ym = [(pa[a] - pa[origen_a]) * k_a for a in correspondencias.values()]
    mx, my = statistics.fmean(xb), statistics.fmean(ym)
    sxx = sum((x - mx) ** 2 for x in xb)
    if sxx == 0:
        raise ValueError("Correspondencias en un único punto.")
    pend = sum((x - mx) * (y - my) for x, y in zip(xb, ym)) / sxx
    ord0 = my - pend * mx
    residuos = {b: pend * pb[b] + ord0 - (pa[a] - pa[origen_a]) * k_a for b, a in correspondencias.items()}
    return {"k_b_m_por_pt": abs(pend), "sentido": "igual" if pend > 0 else "opuesto", "residuos_m": residuos,
            "residuo_max_m": max(abs(r) for r in residuos.values()),
            "posiciones_b_m": {e: pend * p + ord0 for e, p in pb.items()}}
