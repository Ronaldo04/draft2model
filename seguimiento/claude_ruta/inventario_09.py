"""Inventario geométrico real de pueblo-libre-002 (encargo 09, paso 2). Reproducible con módulos del producto.

Ejecutar desde la raíz: python seguimiento/claude_ruta/inventario_09.py
Salidas: seguimiento/claude_ruta/INVENTARIO_GEOMETRICO_09.json y evidencia09/inventario_L0001.png (superposición).

Método por elemento (campo `metodo`):
- `componente_vectorial`: contorno de trazo 1,32 pt (concreto) agrupado por extremos comunes.
- `ajuste_vectorial`: punto declarado por revisión visual + ajuste del contorno a trazos de la longitud de su sección.
- `franja_vectorial`: par de líneas paralelas de cimiento (0,84 pt) → eje y ancho de la franja.
- `revision_visual`: ubicación leída en la imagen; sin geometría vectorial ajustada (pendiente).
Los rótulos son trazos, no texto: la etiqueta de cada elemento es una DECLARACIÓN de revisión visual.
Coordenadas: metros, origen en el eje estructural A (x) y 3 (y, creciente hacia 1), escala registrada con arquitectura
(BORRADOR_CASO_08) e hipótesis de orientación 3↔A (auditoría 237: favorecida, no corroborada por dos rasgos).
"""
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw
import pymupdf

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from draft2model import inventario_vectorial as iv  # noqa: E402

PDF = RAIZ / "data/private/pueblo-libre-002/originales/lamina-0001.pdf"
REGION = (330, 230, 1990, 1090)
KX, KY = 0.012595, 0.012581          # m/pt registrados (estructura ↔ arquitectura, residuos ≤ 9 mm)
XA, Y3 = 364.2, 260.48               # ejes A y 3 en L0001 (líneas punto-raya)
A_PT = lambda dx, dy: (330 + dx * 1.328 / 1.6, 230 + dy * 1.328 / 1.6)   # punto declarado sobre la superposición
m = lambda caja: {"x0": round((caja[0] - XA) * KX, 3), "y0": round((caja[1] - Y3) * KY, 3),
                  "x1": round((caja[2] - XA) * KX, 3), "y1": round((caja[3] - Y3) * KY, 3)}

todos = iv.segmentos(PDF, 1, REGION)
rojos = [s for s in todos if s.get("tipo") == "l" and abs(s["grosor"] - 1.32) < 0.02]
comps = [c for c in iv.componentes(rojos) if max(c["caja_pt"][2] - c["caja_pt"][0], c["caja_pt"][3] - c["caja_pt"][1]) * KX >= 0.25]
comps.sort(key=lambda c: (round(c["caja_pt"][1] / 40), c["caja_pt"][0]))
E = {f"E{i}": c for i, c in enumerate(comps, 1)}

# Identificación declarada por revisión visual de la superposición (evidencia09/inventario_L0001.png).
ETIQUETAS_COMPONENTE = {
    "E1": "C-1", "E27": "C-1", "E3": "C-2", "E28": "C-2", "E16": "C-2", "E17": "C-2", "E13": "C-5", "E15": "C-4", "E18": "C-4",
    "E2": "PL-1", "E4": "PL-1", "E23": "PL-1", "E26": "PL-1", "E6": "PL-2", "E24": "PL-2", "E7": "PL-3", "E25": "PL-3",
    "E8": "PL-4", "E19": "PL-4", "E9": "PL-6 (dos placas unidas en un solo trazo)", "E10": "PL-5", "E20": "PL-5",
    "E11": "PL-7", "E21": "PL-7", "E12": "PL-8", "E22": "PL-8", "E14": "PL-9", "E5": "PL-10", "E29": "PL-10"}
SECCION = {"C-2": (0.15, 0.40), "C-3": (0.15, 0.60), "C-4": (0.15, 0.40), "C-5": (0.15, 0.30), "C-6": (0.15, 0.75)}
DECLARADOS = [  # columnas en trazo fino (primitivas re/qu): punto visual + sección del cuadro
    ("C-2", (692, 43)), ("C-2", (1135, 43)), ("C-2", (1458, 43)), ("C-2", (692, 987)), ("C-2", (1135, 987)), ("C-2", (1458, 987)),
    ("C-3", (1470, 290)), ("C-4", (47, 373)), ("C-5", (47, 618))]
DIBUJO_DISTINTO = [  # se ajustan a lo DIBUJADO y se registra la discrepancia con el cuadro
    ("C-3", (1470, 742), (0.15, 0.55), "Dibujada 0,15×0,55; el cuadro de columnas indica 0,15×0,60."),
    ("C-6", (1455, 500), (0.17, 0.74), "Dibujada ≈0,20×0,75 junto al muro de la cisterna; el cuadro indica 0,15×0,75.")]

elementos = []
for eid, etiqueta in ETIQUETAS_COMPONENTE.items():
    c = E[eid]
    x0, y0, x1, y1 = c["caja_pt"]
    elementos.append({"id": f"L0001-{eid}", "etiqueta_declarada": etiqueta, "tipo": "columna" if etiqueta.startswith("C-") else "placa",
                      "metodo": "componente_vectorial", "caja_m": m(c["caja_pt"]), "segmentos": len(c["segmentos"]),
                      "dim_caja_m": [round((x1 - x0) * KX, 3), round((y1 - y0) * KY, 3)], "fuente": "L0001 · trazo 1,32 pt"})
for i, (etiqueta, punto) in enumerate(DECLARADOS, 1):
    r = iv.ajustar_rectangulo(todos, A_PT(*punto), SECCION[etiqueta], KX)
    elementos.append({"id": f"L0001-A{i}", "etiqueta_declarada": etiqueta, "tipo": "columna", "metodo": "ajuste_vectorial",
                      "estado_ajuste": r["estado"], "caja_m": m(r["caja_pt"]) if r["estado"] == "ajustado" else None,
                      "dim_caja_m": r.get("dim_m"), "fuente": "L0001 · primitiva re/qu"})
for i, (etiqueta, punto, dibujo, nota) in enumerate(DIBUJO_DISTINTO, 1):
    r = iv.ajustar_rectangulo(todos, A_PT(*punto), dibujo, KX)
    elementos.append({"id": f"L0001-D{i}", "etiqueta_declarada": etiqueta, "tipo": "columna", "metodo": "ajuste_vectorial",
                      "estado_ajuste": r["estado"], "caja_m": m(r["caja_pt"]) if r["estado"] == "ajustado" else None,
                      "dim_caja_m": r.get("dim_m"), "discrepancia": nota, "fuente": "L0001"})

# Franjas de cimiento corrido (candidatas a ejes de muros portantes); se fusionan duplicados (±0,12 m).
finas = [s for s in todos if s.get("tipo") == "l" and abs(s["grosor"] - 0.84) < 0.02 and s["largo"] * KX >= 0.5]
crudas = iv.franjas_paralelas(finas, ancho_pt=(0.35 / KX, 0.55 / KX), solape_min_pt=0.5 / KX)
franjas = []
for f in sorted(crudas, key=lambda f: (f["orientacion"], f["eje_pt"], f["desde_pt"])):
    for g in franjas:
        if g["orientacion"] == f["orientacion"] and abs(g["eje_pt"] - f["eje_pt"]) * KX <= 0.12 \
                and f["desde_pt"] <= g["hasta_pt"] and f["hasta_pt"] >= g["desde_pt"]:
            g["desde_pt"], g["hasta_pt"] = min(g["desde_pt"], f["desde_pt"]), max(g["hasta_pt"], f["hasta_pt"])
            g["anchos_m"].add(round(f["ancho_pt"] * KX, 2))
            break
    else:
        franjas.append({**f, "anchos_m": {round(f["ancho_pt"] * KX, 2)}})
muros = []
for i, f in enumerate(franjas, 1):
    if f["orientacion"] == "h":
        ini, fin = (f["desde_pt"] - XA) * KX, (f["hasta_pt"] - XA) * KX
        eje = (f["eje_pt"] - Y3) * KY
        tramo = {"y_m": round(eje, 3), "x_desde_m": round(ini, 3), "x_hasta_m": round(fin, 3)}
    else:
        ini, fin = (f["desde_pt"] - Y3) * KY, (f["hasta_pt"] - Y3) * KY
        eje = (f["eje_pt"] - XA) * KX
        tramo = {"x_m": round(eje, 3), "y_desde_m": round(ini, 3), "y_hasta_m": round(fin, 3)}
    muros.append({"id": f"L0001-F{i}", "orientacion": f["orientacion"], **tramo, "anchos_franja_m": sorted(f["anchos_m"]),
                  "largo_m": round(fin - ini, 3), "metodo": "franja_vectorial",
                  "nota": "Eje de la franja de cimiento; el muro portante puede ser excéntrico (medianeras, corte 1-1)."})

pendientes = [
    {"elemento": "Franjas diagonales (zona PL-4, muros a 57°19')", "por_que": "La detección solo cubre franjas horizontales/verticales."},
    {"elemento": "Huecos de losa (cajas con X en L0002/L0003) y losas macizas (rayado)", "por_que": "Digitalización pendiente sobre L0002 (rotada 270°) y L0003."},
    {"elemento": "Escalera (dos tramos, descanso)", "por_que": "Ubicada a la derecha de H en el eje central (auditoría 237); contorno por digitalizar."},
    {"elemento": "Tanque elevado en planta", "por_que": "A03 lo rotula entre B y D; apoyos E03 (NACE C-2) sin enlace inequívoco (237)."},
    {"elemento": "Vigas VS 0,15×0,30 y peraltadas", "por_que": "Trazos en L0002/L0003 por asociar a ejes."},
    {"elemento": "Muros no portantes / tabiques de arquitectura", "por_que": "Solo informativos para cargas (E.020)."},
]
cisterna = {"metodo": "revision_visual + cotas impresas", "caja_aprox_m": m((1544.2, 447.2, 1731.0, 649.8)),
            "interior_m": [2.00, 2.15], "altura_interior_m": 2.22, "NFC_m": -2.65, "fuente": "L0001 planta; L0003 corte y techo"}

# Superposición de verificación.
z, (X0, Y0, X1, Y1) = 1.6, REGION
with pymupdf.open(PDF) as doc:
    pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(z, z), clip=pymupdf.Rect(X0, Y0, X1, Y1))
im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("L").convert("RGB")
d = ImageDraw.Draw(im)
px = lambda xm, ym: ((xm / KX + XA - X0) * z, (ym / KY + Y3 - Y0) * z)
for e in elementos:
    if e["caja_m"]:
        c = e["caja_m"]
        d.rectangle([px(c["x0"], c["y0"]), px(c["x1"], c["y1"])], outline=(220, 0, 0) if e["tipo"] == "columna" else (0, 90, 220), width=3)
        d.text((px(c["x1"], c["y0"])[0] + 3, px(c["x1"], c["y0"])[1]), e["etiqueta_declarada"].split(" ")[0], fill=(0, 0, 0))
for w in muros:
    if w["orientacion"] == "h":
        d.line([px(w["x_desde_m"], w["y_m"]), px(w["x_hasta_m"], w["y_m"])], fill=(0, 170, 0), width=3)
    else:
        d.line([px(w["x_m"], w["y_desde_m"]), px(w["x_m"], w["y_hasta_m"])], fill=(170, 0, 170), width=3)
salida_png = RAIZ / "seguimiento/claude_ruta/evidencia09/inventario_L0001.png"
salida_png.parent.mkdir(exist_ok=True)
im.save(salida_png)

conteo = {}
for e in elementos:
    k = e["etiqueta_declarada"].split(" ")[0]
    conteo[k] = conteo.get(k, 0) + 1
salida = {"caso": "pueblo-libre-002", "lamina": "L0001", "sha256": hashlib.sha256(PDF.read_bytes()).hexdigest(),
          "sistema": {"origen": "eje A (x), eje 3 (y→1)", "k_m_por_pt": [KX, KY], "orientacion": "3↔A hipótesis de piloto (237)"},
          "conteo_por_etiqueta": dict(sorted(conteo.items())), "elementos": elementos, "muros_candidatos": muros,
          "cisterna": cisterna, "pendientes": pendientes,
          "superposicion": {"archivo": salida_png.relative_to(RAIZ).as_posix(), "sha256": hashlib.sha256(salida_png.read_bytes()).hexdigest()},
          "aprobacion_ingenieria": None}
(RAIZ / "seguimiento/claude_ruta/INVENTARIO_GEOMETRICO_09.json").write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
no_aj = [e["id"] for e in elementos if e.get("estado_ajuste") == "no_ajustado"]
print("elementos", len(elementos), "| sin ajustar", no_aj, "| franjas", len(muros), "|", salida["conteo_por_etiqueta"])
