"""Inventario de muros del caso real (encargo 09, paso 2). Reproducible con módulos del producto.

Ejecutar desde la raíz: python seguimiento/claude_ruta/muros_09.py
Salidas: seguimiento/claude_ruta/MUROS_09.json y evidencia09/muros_L0004.png, muros_L0005.png (superposiciones).

Método:
- Bandas de muro = pares de trazos paralelos de la pluma de muros de arquitectura (1,68 pt) en L0004 (1.er piso) y L0005
  (planta típica 2.º–4.º), separados 0,08–0,32 m (`inventario_vectorial.franjas_paralelas`). Coordenadas sin rotar →
  sistema estructural por los ejes impresos 8/1 (x) y A/E (y), con la k de arquitectura registrada (BORRADOR_CASO_08).
- Clasificación por espesor dibujado, con lecturas de L0001: 0,15 = albañilería King-Kong (corte 1-1, sobrecimiento .15;
  nota «paredes indicadas en aligerados serán de ladrillo King-Kong»); 0,10 = concreto (corte 5-5 .10 y cuadro de placas).
- Contraste con L0001 (INVENTARIO_GEOMETRICO_09): franjas de cimiento paralelas y placas/columnas que cubren ≥ 50 % del tramo.
- Selección para el modelo (`modelable`): albañilería con cimiento; concreto solo si una placa PL ajustada lo cubre. Los muros
  de 0,10 sin placa (ductos) y las bandas que coinciden con columnas (frames) quedan fuera con su motivo.
- Diagonales (PL-4): pares de trazos diagonales paralelos a 0,08–0,12 m → eje.
No aprueba nada: clasificación, selección y ejes son lecturas con hipótesis declaradas.
"""
import hashlib
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from draft2model import calibracion_ejes as ce  # noqa: E402
from draft2model import inventario_vectorial as iv  # noqa: E402

ORIG = RAIZ / "data/private/pueblo-libre-002/originales"
INV = json.loads((RAIZ / "seguimiento/claude_ruta/INVENTARIO_GEOMETRICO_09.json").read_text(encoding="utf-8"))
KX_A, KY_A = 0.01258293542713796, 0.01258446313142884       # k de arquitectura (BORRADOR_CASO_08 · calibracion)
FRANJAS = INV["muros_candidatos"]
CONCRETO = [e for e in INV["elementos"] if e.get("caja_m")]


def solape(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


def cimiento(g):
    """Franjas de L0001 paralelas a ≤ 0,30 m del eje que solapan el tramo (el muro de medianera es excéntrico)."""
    out = []
    for f in FRANJAS:
        if g["o"] == "x" and f["orientacion"] == "h" and abs(f["y_m"] - g["eje"]) <= 0.30:
            s = solape(g["a"], g["b"], f["x_desde_m"], f["x_hasta_m"])
        elif g["o"] == "y" and f["orientacion"] == "v" and abs(f["x_m"] - g["eje"]) <= 0.30:
            s = solape(g["a"], g["b"], f["y_desde_m"], f["y_hasta_m"])
        else:
            continue
        if s > 0:
            out.append({"franja": f["id"], "solape_m": round(s, 3)})
    return out


def elementos_concreto(g):
    """Elementos de L0001 cuyo contorno contiene el eje y cubre ≥ 50 % del tramo (o del elemento, si es menor)."""
    out = []
    for e in CONCRETO:
        c = e["caja_m"]
        lo, hi = (c["y0"], c["y1"]) if g["o"] == "x" else (c["x0"], c["x1"])
        t0, t1 = (c["x0"], c["x1"]) if g["o"] == "x" else (c["y0"], c["y1"])
        if lo - 0.03 <= g["eje"] <= hi + 0.03 and solape(g["a"], g["b"], t0, t1) >= 0.5 * min(g["b"] - g["a"], t1 - t0):
            out.append({"elemento": e["id"], "etiqueta": e["etiqueta_declarada"].split(" ")[0],
                        "tramo_m": [round(max(g["a"], t0), 3), round(min(g["b"], t1), 3)]})
    return out


def procesar(lamina, pdf):
    ex = ce.ejes_desde_texto(pdf, 1, list("12345678"), "y")["posiciones_pt"]
    ey = ce.ejes_desde_texto(pdf, 1, list("ACE"), "x")["posiciones_pt"]   # «B» y «D» empatan con los cortes B-B
    y8, xa = ex["8"], ey["A"]
    X = lambda y_pt: (y_pt - y8) * KX_A          # eje 8 ↔ eje estructural A (x = 0)
    Y = lambda x_pt: (xa - x_pt) * KY_A          # eje A ↔ eje estructural 3 (y = 0), creciente hacia E ↔ 1
    control = {"8-1_m": round(X(ex["1"]), 3), "A-E_m": round(Y(ey["E"]), 3), "A-C_m": round(Y(ey["C"]), 3)}
    todos = iv.segmentos(pdf, 1, (0, 0, 3000, 3000))
    pluma = [s for s in todos if s.get("tipo") == "l" and abs(s["grosor"] - 1.68) < 0.02]
    crudas = iv.franjas_paralelas(pluma, ancho_pt=(0.08 / KX_A, 0.32 / KX_A), solape_min_pt=0.08 / KX_A)
    bandas = []
    for f in crudas:
        if f["orientacion"] == "h":   # trazos a y_pt fijo = x estructural fija → muro paralelo a y
            bandas.append({"o": "y", "eje": X(f["eje_pt"]), "t": f["ancho_pt"] * KX_A, "a": Y(f["hasta_pt"]), "b": Y(f["desde_pt"])})
        else:
            bandas.append({"o": "x", "eje": Y(f["eje_pt"]), "t": f["ancho_pt"] * KY_A, "a": X(f["desde_pt"]), "b": X(f["hasta_pt"])})
    bandas = [b for b in bandas if -0.3 <= b["a"] and b["b"] <= 20.3 and -0.3 <= b["eje"] <= 20.3]   # fuera de la planta: rótulos
    # Fusión: misma orientación, eje (±3 cm) y espesor (±2 cm); tramos solapados o separados ≤ 0,11 m (junta de placa de 0,10).
    grupos = []
    for b in sorted(bandas, key=lambda b: (b["o"], round(b["t"], 2), b["eje"], b["a"])):
        for g in grupos:
            if g["o"] == b["o"] and abs(g["eje"] - b["eje"]) <= 0.03 and abs(g["t"] - b["t"]) <= 0.02 \
                    and b["a"] <= g["b"] + 0.11 and b["b"] >= g["a"] - 0.11:
                g["a"], g["b"], g["n"] = min(g["a"], b["a"]), max(g["b"], b["b"]), g["n"] + 1
                break
        else:
            grupos.append({**b, "n": 1})
    muros, descartes = [], []
    for i, g in enumerate(sorted(grupos, key=lambda g: (g["o"], g["eje"], g["a"])), 1):
        largo = g["b"] - g["a"]
        reg = {"id": f"{lamina}-M{i:02d}", "paralelo_a": g["o"], "eje_m": round(g["eje"], 3), "desde_m": round(g["a"], 3),
               "hasta_m": round(g["b"], 3), "largo_m": round(largo, 3), "espesor_dibujado_m": round(g["t"], 3), "bandas": g["n"]}
        if largo < 0.30:
            descartes.append({**reg, "motivo": "Tramo < 0,30 m: jamba, derrame o encuentro; no es muro modelable por sí mismo."})
            continue
        t = g["t"]
        clase = "albanileria_king_kong" if 0.13 <= t <= 0.17 else "concreto" if 0.085 <= t <= 0.115 else "sin_clasificar"
        reg.update({"clase_propuesta": clase, "cimiento_L0001": cimiento(g), "concreto_L0001": elementos_concreto(g)})
        placas = sorted({c["etiqueta"] for c in reg["concreto_L0001"] if c["etiqueta"].startswith("PL-")})
        columnas = sorted({c["etiqueta"] for c in reg["concreto_L0001"] if c["etiqueta"].startswith("C-")})
        if clase == "albanileria_king_kong":
            reg["modelable"] = bool(reg["cimiento_L0001"])
            reg["motivo"] = "Muro portante de albañilería con cimiento corrido." if reg["modelable"] else "Sin cimiento paralelo en L0001."
        elif clase == "concreto" and placas:
            reg.update({"modelable": True, "placa": placas[0] if len(placas) == 1 else placas,
                        "motivo": "Tramo de placa de concreto ajustada en L0001."})
        elif clase == "concreto" and columnas:
            reg.update({"modelable": False, "motivo": f"Coincide con la columna {', '.join(columnas)}: se modela como frame."})
        else:
            reg.update({"modelable": False, "motivo": "Muro de 0,10 sin placa en L0001 (ducto o tabique): no estructural; su peso es carga."})
        muros.append(reg)
    # Diagonales: pares de trazos paralelos (PL-4) → eje medio.
    diag = []
    for s in pluma:
        dx, dy = X(s["q"][1]) - X(s["p"][1]), Y(s["q"][0]) - Y(s["p"][0])
        if abs(dx) > 0.2 and abs(dy) > 0.2 and 0 <= X(s["p"][1]) <= 20 and 0 <= Y(s["p"][0]) <= 10:
            diag.append(((X(s["p"][1]), Y(s["p"][0])), (X(s["q"][1]), Y(s["q"][0]))))
    ejes_diag, usados = [], set()
    for i, (p1, q1) in enumerate(diag):
        for j, (p2, q2) in enumerate(diag[i + 1:], i + 1):
            if i in usados or j in usados:
                continue
            u = (q1[0] - p1[0], q1[1] - p1[1])
            v = (q2[0] - p2[0], q2[1] - p2[1])
            if abs(u[0] * v[1] - u[1] * v[0]) > 0.02 * math.hypot(*u) * math.hypot(*v):
                continue
            n = math.hypot(*u)
            dist = abs((p2[0] - p1[0]) * u[1] - (p2[1] - p1[1]) * u[0]) / n
            if 0.08 <= dist <= 0.12:
                if u[0] * v[0] + u[1] * v[1] < 0:
                    p2, q2 = q2, p2
                a = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
                b = ((q1[0] + q2[0]) / 2, (q1[1] + q2[1]) / 2)
                usados |= {i, j}
                ejes_diag.append({"id": f"{lamina}-D{len(ejes_diag) + 1}", "desde_m": [round(a[0], 3), round(a[1], 3)],
                                  "hasta_m": [round(b[0], 3), round(b[1], 3)], "espesor_dibujado_m": round(dist, 3),
                                  "clase_propuesta": "concreto", "placa": "PL-4", "modelable": True,
                                  "motivo": "Tramo diagonal de PL-4 (L0001: muros a 57°19')."})
    return {"lamina": lamina, "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(), "ejes_pt": {"8": y8, "A": xa},
            "control_m": control, "bandas": len(bandas), "muros": muros, "diagonales": ejes_diag, "descartes": descartes,
            "_pluma": [((X(s["p"][1]), Y(s["p"][0])), (X(s["q"][1]), Y(s["q"][0]))) for s in pluma]}


def superponer(r):
    S = 70
    im = Image.new("RGB", (int(21.2 * S), int(10.6 * S)), "white")
    d = ImageDraw.Draw(im)
    P = lambda x, y: ((x + 0.3) * S, (y + 0.3) * S)
    for a, b in r["_pluma"]:
        d.line([P(*a), P(*b)], fill=(170, 170, 170), width=1)
    for e in CONCRETO:
        c = e["caja_m"]
        d.rectangle([P(c["x0"], c["y0"]), P(c["x1"], c["y1"])], outline=(0, 90, 220), width=2)
    for f in FRANJAS:
        if f["orientacion"] == "h":
            d.line([P(f["x_desde_m"], f["y_m"]), P(f["x_hasta_m"], f["y_m"])], fill=(0, 170, 0), width=1)
        else:
            d.line([P(f["x_m"], f["y_desde_m"]), P(f["x_m"], f["y_hasta_m"])], fill=(0, 170, 0), width=1)
    for m in r["muros"] + r["diagonales"]:
        if "eje_m" in m:
            a, b = ((m["desde_m"], m["eje_m"]), (m["hasta_m"], m["eje_m"])) if m["paralelo_a"] == "x" else \
                ((m["eje_m"], m["desde_m"]), (m["eje_m"], m["hasta_m"]))
        else:
            a, b = m["desde_m"], m["hasta_m"]
        col = (150, 150, 150) if not m["modelable"] else (220, 0, 0) if m["clase_propuesta"] == "albanileria_king_kong" else (240, 140, 0)
        d.line([P(*a), P(*b)], fill=col, width=4)
        d.text(P((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), m["id"].split("-")[-1], fill=(0, 0, 0))
    png = RAIZ / f"seguimiento/claude_ruta/evidencia09/muros_{r['lamina']}.png"
    im.save(png)
    return {"archivo": png.relative_to(RAIZ).as_posix(), "sha256": hashlib.sha256(png.read_bytes()).hexdigest()}


def clave(m):
    return (m["paralelo_a"], round(m["eje_m"], 1), m["clase_propuesta"])


laminas = {}
for lam, archivo in (("L0004", "lamina-0004.pdf"), ("L0005", "lamina-0005.pdf")):
    r = procesar(lam, ORIG / archivo)
    r["superposicion"] = superponer(r)
    del r["_pluma"]
    laminas[lam] = r


def diferencias(a, b):
    """Tramos modelables de `a` que ningún tramo de `b` cubre (misma orientación, eje ±5 cm, clase)."""
    out = []
    for m in (x for x in laminas[a]["muros"] if x["modelable"]):
        cubierto = sum(solape(m["desde_m"], m["hasta_m"], n["desde_m"], n["hasta_m"]) for n in laminas[b]["muros"]
                       if n["modelable"] and n["paralelo_a"] == m["paralelo_a"] and abs(n["eje_m"] - m["eje_m"]) <= 0.05
                       and n["clase_propuesta"] == m["clase_propuesta"])
        if cubierto < m["largo_m"] - 0.05:
            out.append({"muro": m["id"], "largo_m": m["largo_m"], "cubierto_m": round(cubierto, 3)})
    return out


salida = {"caso": "pueblo-libre-002", "metodo": "pluma de muros 1,68 pt; ver docstring de muros_09.py",
          "sistema": {"origen": "eje A (x), eje 3 (y→1)", "k_m_por_pt": [KX_A, KY_A], "orientacion": "3↔A hipótesis de piloto (237)"},
          "laminas": laminas,
          "comparacion_L0004_L0005": {"solo_L0004": diferencias("L0004", "L0005"), "solo_L0005": diferencias("L0005", "L0004")},
          "lecturas_L0001": ["Corte 1-1: sobrecimiento .15 bajo muro (perímetro).", "Corte 5-5: muro de concreto .10, malla Ø3/8\"@0.25.",
                             "Especificaciones: ladrillo King-Kong a máquina, f'm = 35 kgf/cm²; nota: paredes indicadas en aligerados = King-Kong."],
          "observaciones": ["Eje H en planta típica: ventanas V-1 y puertas P-1 entre columnas C-3/C-6; sin muro portante dibujado con la pluma de muros.",
                            "PL-10 (zona de escalera, ejes 3 y 1 entre H e I): fuera de la planta de arquitectura de muros; altura por definir."],
          "aprobacion_ingenieria": None}
(RAIZ / "seguimiento/claude_ruta/MUROS_09.json").write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
for lam, r in laminas.items():
    mod = [m for m in r["muros"] if m["modelable"]]
    print(lam, r["control_m"], "| muros", len(r["muros"]), "modelables", len(mod), "| diagonales", len(r["diagonales"]),
          "| fuera:", [(m["id"].split("-")[-1], m["motivo"][:22]) for m in r["muros"] if not m["modelable"]])
print("comparación", salida["comparacion_L0004_L0005"])
for d in laminas["L0005"]["diagonales"]:
    print(d)
