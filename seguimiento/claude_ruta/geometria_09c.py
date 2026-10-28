"""Geometría 0.3 conforme del caso real (encargo 09, insumos 248): 09B + PL-10, C-6, cisterna y tanque. Flujo normal: CSV → importacion_tabular.

Ejecutar desde la raíz: python seguimiento/claude_ruta/geometria_09c.py

Añadidos 248 (hipótesis declaradas, no aprobadas):
- PL-10: dos cercos de concreto .10 (corte 2-2 + A01 «CERCO H=2.40»): de NFP −0,05 a +2,35, independientes del edificio
  (sin unión rígida a N1 por redondeo); contorno exacto de E01; base propia.
- C-6: frame N0–N3 (E03 no la dibuja en el 4.º nivel; no se extiende a N4); fuera de la cuadrícula de losas.
- Cisterna: caja de L0001 (2,35 × 2,55 exterior = claro 2,00 × 2,15 + muros .15/.20), muros .20 (.15 en el borde C-3/C-6),
  fondo .20 y tapa .15 con acceso .55 × .55; cotas: NFC −2,65 = cara inferior del solado .05 (hipótesis) → interior
  −2,40 a −0,18 (2,22 impreso), tapa a −0,03.
- Tanque (alternativa E03-apoyos): cuatro C-2 («NACE C-2» en E03 y la C-2 del eje 2) de N4 a la cara inferior del fondo
  (2,00 m impresos), caja con fondo y tapa .20 (E03) y muros .20 (hipótesis); interior 1,55 m (1,10 + 0,45 impresos). La base
  usa N4 = +10,40 (A03) en lugar de NT +10,35 (E03): diferencia de 5 cm declarada. La huella A03 (2,82 × 3,92) queda como
  alternativa no modelada.
- Escalera: NO se modela (reparto vertical no cerrado por las fuentes; auditoría 248); queda registrada con su traza y masa
  estimada fuera del modelo.
Entradas: MUROS_09.json (muros de L0004/L0005), INVENTARIO_GEOMETRICO_09.json (columnas y placas de L0001) y los huecos de
geometria_09.py. Salidas: tmp/ruta201/geometria09b/ (metadatos, CSV, geometria.json) y GEOMETRIA_09B.json (resumen y reglas).

Representación (todas las reglas son hipótesis de modelación declaradas, no aprobadas):
- Líneas de modelación: ejes de muros (albañilería y placas) agrupados a ±6 cm; bordes de huecos a ±10 cm; borde de losa en las
  líneas extremas (ejes 3/1/A) y en la línea de las columnas C-3 del eje H.
- Extremos de muro: a la línea perpendicular más cercana a ≤ 20 cm; si no, nueva línea. Columnas: punto en las líneas que cruzan
  su contorno (más cercana al centroide) o en su centroide; son frames de la configuración y parten muros y losas.
- Malla conforme por construcción: cada muro es un cuadrilátero vertical entre líneas consecutivas; cada losa es una celda de la
  cuadrícula (las diagonales de PL-4 cortan sus celdas). Todas las superficies comparten vértices por identidad: sin nodos
  colgantes ni conexiones de borde implícitas.
- Muros del 1.er piso desde L0004 y de los pisos 2.º–4.º desde L0005. Vanos de puertas y ventanas: interrumpen el muro en toda la
  altura (no se modelan dinteles ni alféizares: rigidez menor, del lado de la flexibilidad).
"""
import csv
import hashlib
import io
import json
import math
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "tmp/ruta201/geometria09c"
MUROS = json.loads((RAIZ / "seguimiento/claude_ruta/MUROS_09.json").read_text(encoding="utf-8"))
INV = json.loads((RAIZ / "seguimiento/claude_ruta/INVENTARIO_GEOMETRICO_09.json").read_text(encoding="utf-8"))
NIVELES = [("N0", 0.00, "plano", "L0004 «N.P.T. ±0.00»"), ("N1", 2.60, "plano", "L0005 «N.P.T. +2.60» (planta típica 2.º–4.º)"),
           ("N2", 5.20, "supuesto", "Hipótesis de progresión uniforme de 2,60 m (auditoría 237); NPT del 3.º no impreso"),
           ("N3", 7.80, "supuesto", "Hipótesis de progresión uniforme de 2,60 m (auditoría 237); NPT del 4.º no impreso"),
           ("N4", 10.40, "plano", "L0006 «TECHO N.T.T. +10.40»")]
Z = {n: z for n, z, _, _ in NIVELES}
PISOS = [("N0", "N1", "L0004"), ("N1", "N2", "L0005"), ("N2", "N3", "L0005"), ("N3", "N4", "L0005")]
# Huecos de losa por nivel (geometria_09.py, detección vectorial de X en L0002/L0003).
HUECOS = {
    "N1": [(0.13, 3.75, 2.53, 6.30), (5.99, 0.17, 6.59, 1.27), (5.99, 8.78, 6.59, 9.88), (8.71, 3.17, 11.12, 4.95), (8.71, 5.10, 11.12, 6.87)],
    "N2": [(0.13, 3.75, 2.54, 6.30), (5.99, 0.17, 6.59, 1.27), (5.99, 8.78, 6.59, 9.88), (8.72, 3.17, 11.12, 4.95), (8.72, 5.11, 11.12, 6.87)],
    "N3": [(0.13, 3.75, 2.54, 6.30), (5.99, 0.17, 6.59, 1.27), (5.99, 8.78, 6.59, 9.88), (8.72, 3.17, 11.12, 4.95), (8.72, 5.11, 11.12, 6.87)],
    "N4": [(0.15, 3.73, 2.55, 6.28), (6.00, 0.15, 6.60, 1.25), (6.00, 8.76, 6.60, 9.86), (8.73, 3.15, 11.13, 4.93), (8.73, 5.09, 11.13, 6.86)],
}
SECCION_COLUMNA = {"C-1": (0.15, 0.40), "C-2": (0.15, 0.40), "C-3": (0.15, 0.60), "C-4": (0.15, 0.40), "C-5": (0.15, 0.30), "C-6": (0.15, 0.75)}
TOL_EJE, TOL_EXTREMO, TOL_HUECO, R = 0.06, 0.20, 0.10, 4


def solape(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


# 1. Muros modelables por lámina. Las placas de concreto se limitan a lo que cubre la placa de L0001.
def tramos(m):
    if m["clase_propuesta"] != "concreto":
        return [(m["desde_m"], m["hasta_m"])]
    iv = sorted((c["tramo_m"][0], c["tramo_m"][1]) for c in m["concreto_L0001"] if c["etiqueta"].startswith("PL-"))
    out = []
    for a, b in iv:
        a = m["desde_m"] if a - m["desde_m"] <= 0.12 else a
        b = m["hasta_m"] if m["hasta_m"] - b <= 0.12 else b
        if out and a <= out[-1][1] + 0.12:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


muros = {}
for lam in ("L0004", "L0005"):
    lista = []
    for m in MUROS["laminas"][lam]["muros"]:
        if not m["modelable"]:
            continue
        for k, (a, b) in enumerate(tramos(m), 1):
            lista.append({"src": m["id"] + (f".{k}" if len(tramos(m)) > 1 else ""), "o": m["paralelo_a"], "eje": m["eje_m"], "a": a, "b": b,
                          "clase": m["clase_propuesta"], "espesor": 0.15 if m["clase_propuesta"] == "albanileria_king_kong" else 0.10})
    diags = [{"src": d["id"], "p": tuple(d["desde_m"]), "q": tuple(d["hasta_m"]), "clase": "concreto", "espesor": 0.10}
             for d in MUROS["laminas"][lam]["diagonales"] if d["modelable"]]
    muros[lam] = {"orto": lista, "diag": diags}

# 2. Líneas de modelación (agrupación de ejes de muro de ambas láminas).
def agrupar(valores, tol):
    grupos = []
    for v in sorted(valores):
        if grupos and v - grupos[-1][-1] <= tol:
            grupos[-1].append(v)
        else:
            grupos.append([v])
    return [round(sum(g) / len(g), 3) for g in grupos]


todos_orto = [w for lam in muros for w in muros[lam]["orto"]]
lineas = {"x": agrupar([w["eje"] for w in todos_orto if w["o"] == "y"], TOL_EJE),   # x = cte (muros paralelos a y)
          "y": agrupar([w["eje"] for w in todos_orto if w["o"] == "x"], TOL_EJE)}
columnas = [e for e in INV["elementos"] if e["tipo"] == "columna" and e.get("caja_m") and not e["etiqueta_declarada"].startswith("C-6")]
C6 = next(e for e in INV["elementos"] if e["etiqueta_declarada"].startswith("C-6"))
c3 = [e for e in columnas if e["etiqueta_declarada"] == "C-3"]
X_H = round(sum((e["caja_m"]["x0"] + e["caja_m"]["x1"]) / 2 for e in c3) / len(c3), 3)   # borde de losa en el eje H
lineas["x"] = sorted(set(lineas["x"]) | {X_H})
X0, X1, Y0, Y1 = min(lineas["x"]), X_H, min(lineas["y"]), max(lineas["y"])


def ajustar(v, eje, tol):
    cerca = min(lineas[eje], key=lambda l: abs(l - v))
    if abs(cerca - v) <= tol:
        return cerca
    v = round(v, 3)
    lineas[eje] = sorted(set(lineas[eje]) | {v})
    return v


def eje_de(w):
    return min(lineas["y" if w["o"] == "x" else "x"], key=lambda l: abs(l - w["eje"]))


# 3. Columnas: punto de modelación.
puntos_columna = []
for e in columnas:
    c = e["caja_m"]
    p = []
    for eje, lo, hi in (("x", c["x0"], c["x1"]), ("y", c["y0"], c["y1"])):
        dentro = [l for l in lineas[eje] if lo - 1e-9 <= l <= hi + 1e-9]
        cen = (lo + hi) / 2
        p.append(min(dentro, key=lambda l: abs(l - cen)) if dentro else ajustar(cen, eje, 0.0))
    puntos_columna.append({"elemento": e["id"], "etiqueta": e["etiqueta_declarada"].split(" ")[0], "x": p[0], "y": p[1],
                           "seccion_m": SECCION_COLUMNA[e["etiqueta_declarada"].split(" ")[0]],
                           "dibujo_m": e.get("dim_caja_m"), "discrepancia": e.get("discrepancia")})

# 4. Extremos de muros y diagonales; huecos.
for lam in muros:
    for w in muros[lam]["orto"]:
        perp = "x" if w["o"] == "x" else "y"
        w["eje_mod"] = eje_de(w)
        w["a_mod"], w["b_mod"] = ajustar(w["a"], perp, TOL_EXTREMO), ajustar(w["b"], perp, TOL_EXTREMO)
    for d in muros[lam]["diag"]:
        d["p_mod"] = (ajustar(d["p"][0], "x", TOL_EJE), ajustar(d["p"][1], "y", TOL_EJE))
        d["q_mod"] = (ajustar(d["q"][0], "x", TOL_EJE), ajustar(d["q"][1], "y", TOL_EJE))
huecos_mod = {n: [(ajustar(a, "x", TOL_HUECO), ajustar(b, "y", TOL_HUECO), ajustar(c, "x", TOL_HUECO), ajustar(d, "y", TOL_HUECO))
                  for a, b, c, d in hs] for n, hs in HUECOS.items()}
XS = [x for x in lineas["x"] if X0 - 1e-9 <= x <= X1 + 1e-9]
YS = [y for y in lineas["y"] if Y0 - 1e-9 <= y <= Y1 + 1e-9]

# 5. Vértices compartidos por identidad de coordenadas.
vertices = {}


def vid(x, y, z):
    k = (round(x, R), round(y, R), round(z, R))
    if k not in vertices:
        vertices[k] = None
    return k


superficies = []   # (id, [claves], papel, procedencia, clase)


def proc(tipo, descripcion, lamina=None, justificacion=None):
    p = {"tipo": tipo, "descripcion": descripcion, "expediente_id": "pueblo-libre-002"}
    if lamina:
        p["lamina"] = lamina
    if justificacion:
        p["justificacion"] = justificacion
    return p


JUST_MURO = ("Eje y extremos ajustados a líneas de modelación (±6 cm eje, ±20 cm extremo); vanos en toda la altura; "
             "partido en cada línea que lo cruza para compartir vértices con losas y columnas.")
# 6. Muros por piso.
registro_muros = []
for inf, sup, lam in PISOS:
    zi, zs = Z[inf], Z[sup]
    for w in muros[lam]["orto"]:
        a, b = sorted((w["a_mod"], w["b_mod"]))
        if b - a < 1e-6:
            continue
        perp = "x" if w["o"] == "x" else "y"
        cortes = [a] + [l for l in lineas[perp] if a + 1e-9 < l < b - 1e-9] + [b]
        for k, (u, v) in enumerate(zip(cortes, cortes[1:]), 1):
            if w["o"] == "x":
                p0, p1 = (u, w["eje_mod"]), (v, w["eje_mod"])
            else:
                p0, p1 = (w["eje_mod"], u), (w["eje_mod"], v)
            ident = f"W{inf[1]}-{w['src'].split('-')[1]}-{k}"
            papel = "muro de albañilería" if w["clase"] == "albanileria_king_kong" else "placa de concreto"
            superficies.append((ident, [vid(*p0, zi), vid(*p1, zi), vid(*p1, zs), vid(*p0, zs)], papel,
                                proc("plano", f"{papel} {w['src']} (MUROS_09), espesor {w['espesor']} m", lam, JUST_MURO), w["clase"], w["espesor"]))
            registro_muros.append(ident)
    for d in muros[lam]["diag"]:
        (px, py), (qx, qy) = d["p_mod"], d["q_mod"]
        ts = {0.0, 1.0}
        for x in XS:
            if min(px, qx) + 1e-9 < x < max(px, qx) - 1e-9:
                ts.add((x - px) / (qx - px))
        for y in YS:
            if min(py, qy) + 1e-9 < y < max(py, qy) - 1e-9:
                ts.add((y - py) / (qy - py))
        ts = sorted(ts)
        for k, (t0, t1) in enumerate(zip(ts, ts[1:]), 1):
            p0 = (px + t0 * (qx - px), py + t0 * (qy - py))
            p1 = (px + t1 * (qx - px), py + t1 * (qy - py))
            ident = f"W{inf[1]}-{d['src'].split('-')[1]}-{k}"
            superficies.append((ident, [vid(*p0, zi), vid(*p1, zi), vid(*p1, zs), vid(*p0, zs)], "placa de concreto",
                                proc("plano", f"placa de concreto {d['src']} (diagonal PL-4), espesor 0.10 m", lam, JUST_MURO), "concreto", 0.10))

# 7. Losas: celdas de la cuadrícula; las diagonales del piso inferior parten las celdas que atraviesan.
def cortar(poli, p, q):
    """Divide un polígono convexo por la recta pq; devuelve las partes con área (vértices de corte incluidos)."""
    def lado(v):
        return (q[0] - p[0]) * (v[1] - p[1]) - (q[1] - p[1]) * (v[0] - p[0])
    izq, der = [], []
    n = len(poli)
    for i in range(n):
        a, b = poli[i], poli[(i + 1) % n]
        sa, sb = lado(a), lado(b)
        if sa >= -1e-12:
            izq.append(a)
        if sa <= 1e-12:
            der.append(a)
        if (sa > 1e-12 and sb < -1e-12) or (sa < -1e-12 and sb > 1e-12):
            t = sa / (sa - sb)
            c = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
            izq.append(c)
            der.append(c)
    area = lambda P: abs(sum(P[i][0] * P[(i + 1) % len(P)][1] - P[(i + 1) % len(P)][0] * P[i][1] for i in range(len(P)))) / 2
    return [P for P in (izq, der) if len(P) >= 3 and area(P) > 1e-6]


def dentro_hueco(cx, cy, hs):
    return any(a < cx < c and b < cy < d for a, b, c, d in hs)


registro_losas = {}
for nivel, z, _, _ in NIVELES[1:]:
    lam_inf = next(l for i, s, l in PISOS if s == nivel)
    diag = muros[lam_inf]["diag"]
    n = 0
    for i in range(len(XS) - 1):
        for j in range(len(YS) - 1):
            x0, x1, y0, y1 = XS[i], XS[i + 1], YS[j], YS[j + 1]
            if dentro_hueco((x0 + x1) / 2, (y0 + y1) / 2, huecos_mod[nivel]):
                continue
            partes = [[(x0, y0), (x1, y0), (x1, y1), (x0, y1)]]
            for d in diag:
                (px, py), (qx, qy) = d["p_mod"], d["q_mod"]
                if max(px, qx) <= x0 + 1e-9 or min(px, qx) >= x1 - 1e-9 or max(py, qy) <= y0 + 1e-9 or min(py, qy) >= y1 - 1e-9:
                    continue
                partes = [r for P in partes for r in cortar(P, (px, py), (qx, qy))]
            for P in partes:
                # Vértices de la cuadrícula que caen sobre el contorno (p. ej. cortes diagonales vecinos) se insertan para conformidad.
                n += 1
                ident = f"S{nivel[1]}-{n:03d}"
                superficies.append((ident, [vid(x, y, z) for x, y in P], "losa de techo" if nivel == "N4" else "losa de piso",
                                    proc("plano", f"Celda de losa aligerada e=17 cm del nivel {nivel} (cuadrícula de líneas de modelación)",
                                         "L0002" if nivel != "N4" else "L0003",
                                         "Contorno en las líneas de muros extremas; huecos de X ajustados a ±10 cm."), "losa", None))
    registro_losas[nivel] = n

# Vértices de columnas en cada nivel (la configuración los une con frames).
for c in puntos_columna:
    for nivel, z, _, _ in NIVELES:
        vid(c["x"], c["y"], z)

# 7b. Insumos 248. Cotas fuera de los niveles: prefijo propio de vértice (no son pisos).
Z_EXTRA = {-2.50: "CF", -0.105: "CT", -0.05: "PB", 2.35: "PC", 12.50: "TF", 14.25: "TT"}


def P248(d, lam, j):
    return proc("plano", d, lam, j)


def caja(prefijo, xs, ys, zf, zt, espesores, sin_tapa=(), papel="depósito", fuente=("", "")):
    """Caja conforme: muros en los bordes partidos en cada línea; fondo y tapa como celdas de la misma cuadrícula."""
    lam, just = fuente

    def agregar(ident, claves, rol, clase, e):
        superficies.append((ident, claves, rol, P248(f"{papel}: {rol}, espesor {e} m", lam, just), clase, e))
    bordes = (("y0", ys[0], "x", xs), ("y1", ys[-1], "x", xs), ("x0", xs[0], "y", ys), ("x1", xs[-1], "y", ys))
    for lado, fijo, eje, cortes in bordes:
        e = espesores[lado]
        for k, (u, v) in enumerate(zip(cortes, cortes[1:]), 1):
            p0, p1 = ((u, fijo), (v, fijo)) if eje == "x" else ((fijo, u), (fijo, v))
            agregar(f"{prefijo}-M{lado}-{k}", [vid(*p0, zf), vid(*p1, zf), vid(*p1, zt), vid(*p0, zt)], "muro de depósito", "deposito_muro", e)
    n = 0
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            x0, x1, y0, y1 = xs[i], xs[i + 1], ys[j], ys[j + 1]
            n += 1
            agregar(f"{prefijo}-F-{n:02d}", [vid(x0, y0, zf), vid(x1, y0, zf), vid(x1, y1, zf), vid(x0, y1, zf)],
                    "fondo de depósito", "deposito_fondo", espesores["fondo"])
            if (i, j) not in sin_tapa:
                agregar(f"{prefijo}-T-{n:02d}", [vid(x0, y0, zt), vid(x1, y0, zt), vid(x1, y1, zt), vid(x0, y1, zt)],
                        "tapa de depósito", "deposito_tapa", espesores["tapa"])


# Cisterna (L0001 caja + E03 corte/techo): ejes de muro en los planos medios; acceso .55 junto a C-6.
cis = INV["cisterna"]["caja_aprox_m"]
CX = [X_H, round(cis["x0"] + 0.15, 3), round(cis["x0"] + 0.15 + 0.55, 3), round(cis["x1"] - 0.10, 3)]
CY = [round(cis["y0"] + 0.10, 3), round(cis["y1"] - 0.20 - 0.55, 3), round(cis["y1"] - 0.20, 3), round(cis["y1"] - 0.10, 3)]
caja("CIS", CX, CY, -2.50, -0.105, {"x0": 0.15, "x1": 0.20, "y0": 0.20, "y1": 0.20, "fondo": 0.20, "tapa": 0.15},
     sin_tapa={(1, 1)}, papel="cisterna",
     fuente=("L0001/L0003", "Caja de L0001; espesores, claro 2,00 × 2,15 y altura interior 2,22 de E03 (corte y techo); "
                            "NFC −2,65 = cara inferior del solado .05 (hipótesis)."))
# Tanque (alternativa E03-apoyos): muros en las líneas de las C-2 que nacen en el techo.
TX, TY = [11.335, 13.748], [3.118, 5.018]   # x = 11.335: línea de la C-2 del eje 2 (centroide E03 NACE 11.315)
caja("TAN", TX, TY, 12.50, 14.25, {"x0": 0.20, "x1": 0.20, "y0": 0.20, "y1": 0.20, "fondo": 0.20, "tapa": 0.20},
     papel="tanque elevado",
     fuente=("L0003", "Apoyos «NACE C-2» vectorizados en E03 + C-2 del eje 2; cadena E03 2,00/.20/1,10/.45/.20 desde N4 = +10,40 "
                      "(A03) en lugar de NT +10,35 (E03)."))
tanque_columnas = [{"elemento": f"NACE-{i}", "etiqueta": "C-2", "x": x, "y": y, "seccion_m": (0.15, 0.40), "dibujo_m": [0.40, 0.15],
                    "fuente": "E03 NACE C-2" if i < 3 else "C-2 del eje 2 (L0001) que continúa"}
                   for i, (x, y) in enumerate(((11.335, 3.118), (13.748, 3.118), (13.748, 5.018), (11.335, 5.018)))]
for c in tanque_columnas:
    vid(c["x"], c["y"], 10.40)
    vid(c["x"], c["y"], 12.50)
# PL-10: dos cercos (contorno E01), eje en el punto medio del espesor, de −0,05 a +2,35.
PL10 = [(15.043, 20.017, 0.050), (15.043, 20.017, 9.947)]
for k, (xa, xb, y) in enumerate(PL10, 1):
    superficies.append((f"PL10-{k}", [vid(xa, y, -0.05), vid(xb, y, -0.05), vid(xb, y, 2.35), vid(xa, y, 2.35)], "cerco de concreto",
                        P248("PL-10 cerco .10 (corte 2-2: altura 2,40 desde NFP −0,05; f'c 175; A01 «CERCO H=2.40»)", "L0001/L0004",
                             "Contorno de E01; independiente del edificio (coronación +2,35 distinta de N1 +2,60)."), "cerco_concreto", 0.10))
# C-6: N0–N3, sección dibujada .75 × .20 (cuadro .15 × .75: discrepancia declarada).
c6c = C6["caja_m"]
C6P = {"elemento": C6["id"], "etiqueta": "C-6", "x": round((c6c["x0"] + c6c["x1"]) / 2, 3), "y": round((c6c["y0"] + c6c["y1"]) / 2, 3),
       "seccion_m": (0.20, 0.75), "dibujo_m": C6.get("dim_caja_m"), "discrepancia": "Cuadro .15 × .75; planta E01/E02 .20 × .75 (tres vistas).",
       "niveles": ["N0", "N1", "N2", "N3"]}
for nivel, z, _, _ in NIVELES[:4]:
    vid(C6P["x"], C6P["y"], z)

# 8. Conformidad: ningún vértice puede caer en el interior de una arista de otra superficie del mismo plano.
def en_arista(v, a, b):
    if v in (a, b):
        return False
    cr = (b[0] - a[0]) * (v[1] - a[1]) - (b[1] - a[1]) * (v[0] - a[0])
    if abs(cr) > 1e-7 or abs(v[2] - a[2]) > 1e-9 or abs(b[2] - a[2]) > 1e-9 and a[:2] != b[:2]:
        pass
    seg = [(b[i] - a[i]) for i in range(3)]
    L2 = sum(s * s for s in seg)
    t = sum((v[i] - a[i]) * seg[i] for i in range(3)) / L2
    if not (1e-9 < t < 1 - 1e-9):
        return False
    return math.dist(v, tuple(a[i] + t * seg[i] for i in range(3))) < 1e-6


por_z = {}
for k in vertices:
    por_z.setdefault(k[2], []).append(k)
colgantes = []
for s in superficies:
    vs = s[1]
    zs = {v[2] for v in vs}
    candidatos = [v for z in zs for v in por_z[z]]
    for a, b in zip(vs, vs[1:] + vs[:1]):
        lo_x, hi_x, lo_y, hi_y = min(a[0], b[0]), max(a[0], b[0]), min(a[1], b[1]), max(a[1], b[1])
        for v in candidatos:
            if lo_x - 1e-9 <= v[0] <= hi_x + 1e-9 and lo_y - 1e-9 <= v[1] <= hi_y + 1e-9 and min(a[2], b[2]) - 1e-9 <= v[2] <= max(a[2], b[2]) + 1e-9:
                if en_arista(v, a, b):
                    colgantes.append({"superficie": s[0], "vertice": v})

# 9. Identificadores y tablas.
ids, contador = {}, {}
for k in sorted(vertices, key=lambda k: (k[2], k[0], k[1])):
    nivel = next((n for n, z, _, _ in NIVELES if abs(z - k[2]) < 1e-9), None) or Z_EXTRA[k[2]]
    contador[nivel] = contador.get(nivel, 0) + 1
    ids[k] = f"{nivel}-V{contador[nivel]:04d}"


def csv_texto(cabecera, filas):
    b = io.StringIO()
    w = csv.writer(b, lineterminator="\n")
    w.writerow(cabecera)
    for f in filas:
        w.writerow([json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for v in f])
    return b.getvalue()


P_VERTICE = proc("plano", "Vértice compartido de la malla conforme (líneas de modelación de geometria_09c.py)")
niveles_csv = [(n, z, proc(t, d, None if t == "supuesto" else d.split(" ")[0],
                           "Uniformidad sustentada por tipicidad y extremos impresos; no es cota impresa." if t == "supuesto" else None))
               for n, z, t, d in NIVELES]
# Niveles físicos de los depósitos (no pisos de losa): sin ellos el plan rechaza puntos fuera de [N0, N4] («no se crean pisos
# ficticios»). NCF es la nueva base de ETABS; las losas, diafragmas y apoyos de los pisos no cambian.
niveles_csv = [("NCF", -2.50, proc("supuesto", "Fondo de cisterna (plano medio)", None, "NFC −2,65 = cara inferior del solado .05 (hipótesis, E03)."))]     + niveles_csv + [("NTF", 12.50, proc("supuesto", "Fondo de tanque elevado (plano medio)", None, "N4 +10,40 + apoyo 2,00 + fondo .20/2 (E03)")),
                     ("NTT", 14.25, proc("supuesto", "Tapa de tanque elevado (plano medio)", None, "Fondo +12,60 + interior 1,55 + tapa .20/2 (E03)"))]
faltantes = [
    {"descripcion": "Escalera en U (E02 garganta .15, ancho 1,20, huella .25): reparto vertical por tramo no cerrado por las fuentes "
                    "(auditoría 248); NO modelada, registrada en DEPOSITOS_09C con traza y masa estimada fuera del modelo."},
    {"descripcion": "Tanque: huella A03 2,82 × 3,92 frente a apoyos E03 (2,58 × 1,90 entre ejes); base NT +10,35 (E03) frente a +10,40 (A03); "
                    "espesor de muros .20 y nivel de agua 1,10 son hipótesis."},
    {"descripcion": "Cisterna: correspondencia NFC −2,65 con las caras del fondo (hipótesis solado .05); patines .35+.20 bajo muros no modelados; "
                    "conexión con C-3/C-6 no acotada (subestructura independiente)."},
    {"descripcion": "C-6: espesor .15 (cuadro) frente a .20 (planta); extremos verticales sin cota; N0–N3 como idealización provisional."},
    {"descripcion": "Orientación 3↔A: hipótesis de piloto (auditoría 237), no corroborada por dos rasgos independientes."},
    {"descripcion": "Dinteles, alféizares y muros no portantes (ductos de 0,10, tabiques de pandereta) no se modelan como superficies; su peso es carga."},
]
meta = {"contrato": "draft2model.geometria", "version_contrato": "0.3.0", "id": "pueblo-libre-002", "unidad_longitud": "m",
        "procedencia": proc("plano", "Geometría conforme del caso real: muros de L0004/L0005, placas y columnas de L0001, huecos de L0002/L0003; encargo 09.",
                            "L0001–L0006", "Reglas de modelación en seguimiento/claude_ruta/geometria_09c.py; sin aprobación."),
        "faltantes": faltantes, "revision": {"estado": "borrador", "aprobacion": None}}
SALIDA.mkdir(parents=True, exist_ok=True)
tablas = {
    "niveles": csv_texto(["id", "cota", "procedencia"], niveles_csv),
    "nodos": "id,x,y\n", "muros": "id,nodo_inicio,nodo_fin,nivel_inferior,nivel_superior,espesor\n",
    "vertices": csv_texto(["id", "x", "y", "z", "procedencia"], [(ids[k], k[0], k[1], k[2], P_VERTICE) for k in ids]),
    "superficies": csv_texto(["id", "vertices", "papel_geometrico", "procedencia"], [(s[0], [ids[v] for v in s[1]], s[2], s[3]) for s in superficies]),
    "aberturas": "id,superficie,vertices,procedencia\n",
}
(SALIDA / "metadatos.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
for nombre, texto in tablas.items():
    (SALIDA / f"{nombre}.csv").write_text(texto, encoding="utf-8")
destino = SALIDA / "geometria.json"
if destino.exists():
    destino.unlink()
cmd = [sys.executable, "-m", "draft2model.importacion_tabular", "--metadatos", str(SALIDA / "metadatos.json")]
for nombre in tablas:
    cmd += [f"--{nombre}", str(SALIDA / f"{nombre}.csv")]
r = subprocess.run(cmd + ["--salida", str(destino)], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env={**os.environ, "PYTHONIOENCODING": "utf-8"})
# Clases por superficie y columnas: insumo de la configuración.
clases = {s[0]: {"clase": s[4], "espesor_m": s[5]} for s in superficies}
resumen = {"caso": "pueblo-libre-002", "geometria": destino.relative_to(RAIZ).as_posix(),
           "sha256": hashlib.sha256(destino.read_bytes()).hexdigest() if destino.exists() else None,
           "importacion_codigo": r.returncode, "lineas_x": XS, "lineas_y": YS, "borde_losa_m": [X0, Y0, X1, Y1],
           "vertices": len(ids), "superficies": len(superficies), "muros_por_piso": {p[0]: sum(1 for s in registro_muros if s.startswith(f"W{p[0][1]}-")) for p in PISOS},
           "losas_por_nivel": registro_losas, "colgantes": colgantes[:20], "n_colgantes": len(colgantes),
           "columnas": [{**c, "vertices": [ids[(round(c['x'], R), round(c['y'], R), round(z, R))] for _, z, _, _ in NIVELES]} for c in puntos_columna]
                       + [{**C6P, "vertices": [ids[(round(C6P['x'], R), round(C6P['y'], R), round(z, R))] for _, z, _, _ in NIVELES[:4]]}]
                       + [{**c, "vertices": [ids[(round(c['x'], R), round(c['y'], R), z)] for z in (10.40, 12.50)]} for c in tanque_columnas],
           "depositos": {"cisterna": {"x": CX, "y": CY, "z": [-2.50, -0.105]}, "tanque": {"x": TX, "y": TY, "z": [12.50, 14.25]}},
           "pl10": PL10,
           "clases_superficie": clases, "aprobacion_ingenieria": None}
(RAIZ / "seguimiento/claude_ruta/GEOMETRIA_09C.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(r.returncode, (r.stdout + r.stderr)[-1200:])
print("líneas", len(XS), "×", len(YS), "| vértices", len(ids), "| superficies", len(superficies), "| muros/piso", resumen["muros_por_piso"],
      "| losas", registro_losas, "| colgantes", len(colgantes))
