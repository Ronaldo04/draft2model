"""Borrador de geometría 0.3 del caso real (encargo 09, paso 3) por el flujo normal: tablas CSV → importacion_tabular.

Ejecutar desde la raíz: python seguimiento/claude_ruta/geometria_09.py
Salidas: tmp/ruta201/geometria09/ (metadatos + CSV) y tmp/ruta201/geometria09/geometria.json (contrato validado).

Incluye solo lo sustentado: niveles (leídos o hipótesis uniforme declarada), losas por nivel con contorno en ejes
A–H × 3–1 (hipótesis de contorno en ejes) y sus huecos detectados vectorialmente (X en L0002/L0003). Los muros de
albañilería, las placas, las columnas (frames de la configuración), la escalera y el tanque quedan como FALTANTES
explícitos: sin ellos el modelo no es apto para análisis y no se ejecuta ETABS del caso real.
"""
import csv
import io
import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "tmp/ruta201/geometria09"
X_H, Y_1 = 15.010, 10.000          # ejes H y 1 en el sistema estructural registrado (BORRADOR_CASO_08)
NIVELES = [("N0", 0.00, "plano", "L0004 «N.P.T. ±0.00»"), ("N1", 2.60, "plano", "L0005 «N.P.T. +2.60» (planta típica 2.º–4.º)"),
           ("N2", 5.20, "supuesto", "Hipótesis de progresión uniforme de 2,60 m (auditoría 237); NPT del 3.º no impreso"),
           ("N3", 7.80, "supuesto", "Hipótesis de progresión uniforme de 2,60 m (auditoría 237); NPT del 4.º no impreso"),
           ("N4", 10.40, "plano", "L0006 «TECHO N.T.T. +10.40»")]
# Huecos detectados por pares de diagonales cruzadas (m, sistema estructural); losa de N1 = plano «1er nivel», etc.
HUECOS = {
    "N1": [(0.13, 3.75, 2.53, 6.30), (5.99, 0.17, 6.59, 1.27), (5.99, 8.78, 6.59, 9.88), (8.71, 3.17, 11.12, 4.95), (8.71, 5.10, 11.12, 6.87)],
    "N2": [(0.13, 3.75, 2.54, 6.30), (5.99, 0.17, 6.59, 1.27), (5.99, 8.78, 6.59, 9.88), (8.72, 3.17, 11.12, 4.95), (8.72, 5.11, 11.12, 6.87)],
    "N3": [(0.13, 3.75, 2.54, 6.30), (5.99, 0.17, 6.59, 1.27), (5.99, 8.78, 6.59, 9.88), (8.72, 3.17, 11.12, 4.95), (8.72, 5.11, 11.12, 6.87)],
    "N4": [(0.15, 3.73, 2.55, 6.28), (6.00, 0.15, 6.60, 1.25), (6.00, 8.76, 6.60, 9.86), (8.73, 3.15, 11.13, 4.93), (8.73, 5.09, 11.13, 6.86)],
}
LAMINA = {"N1": "L0002 (planta 1er nivel)", "N2": "L0002 (planta 2do y 3er nivel)", "N3": "L0002 (planta 2do y 3er nivel)", "N4": "L0003"}


def proc(tipo, descripcion, lamina=None, justificacion=None):
    p = {"tipo": tipo, "descripcion": descripcion, "expediente_id": "pueblo-libre-002"}
    if lamina:
        p["lamina"] = lamina
    if justificacion:
        p["justificacion"] = justificacion
    return p


def csv_texto(cabecera, filas):
    b = io.StringIO()
    w = csv.writer(b, lineterminator="\n")
    w.writerow(cabecera)
    for f in filas:
        w.writerow([json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for v in f])
    return b.getvalue()


niveles = [(n, z, json.dumps(proc(t, d, None if t == "supuesto" else d.split(" ")[0],
                                       "Uniformidad sustentada por tipicidad y extremos impresos; no es cota impresa." if t == "supuesto" else None),
                                  ensure_ascii=False)) for n, z, t, d in NIVELES]
vertices, superficies, aberturas = [], [], []
for nivel, z in ((n, z) for n, z, _, _ in NIVELES[1:]):
    p_losa = proc("plano", f"Contorno de losa en ejes A–H × 3–1, escala registrada con arquitectura (residuo ≤ 9 mm)", LAMINA[nivel],
                  "Hipótesis: borde de losa sobre los ejes; el espesor de muros perimetrales no se descuenta.")
    ids = []
    for i, (x, y) in enumerate(((0.0, 0.0), (X_H, 0.0), (X_H, Y_1), (0.0, Y_1)), 1):
        vid = f"{nivel}-L{i}"
        vertices.append((vid, round(x, 3), round(y, 3), z, p_losa))
        ids.append(vid)
    superficies.append((f"LOSA-{nivel}", ids, "losa de piso" if nivel != "N4" else "losa de techo", p_losa))
    for j, (x0, y0, x1, y1) in enumerate(HUECOS[nivel], 1):
        p_h = proc("plano", f"Hueco marcado con X; detección vectorial de diagonales cruzadas", LAMINA[nivel])
        hid = []
        for i, (x, y) in enumerate(((x0, y0), (x1, y0), (x1, y1), (x0, y1)), 1):
            vid = f"{nivel}-H{j}-{i}"
            vertices.append((vid, x, y, z, p_h))
            hid.append(vid)
        aberturas.append((f"HUECO-{nivel}-{j}", f"LOSA-{nivel}", hid, p_h))

faltantes = [
    {"descripcion": "Muros portantes de albañilería: 73 ejes candidatos de franja de cimiento 0,50 (L0001) sin revisar; espesor, "
                    "excentricidad en medianeras y vanos de arquitectura pendientes. Sin ellos el modelo no es apto para análisis."},
    {"descripcion": "Placas PL-1…PL-10: contornos vectoriales (INVENTARIO_GEOMETRICO_09.json); PL-4/5/6/8/9 no rectangulares; altura de PL-10 por definir."},
    {"descripcion": "Columnas C-1…C-6 (23 ubicaciones ajustadas): se declaran como frames de la configuración."},
    {"descripcion": "Hueco de escalera en niveles 2–3 no detectado (las diagonales las corta C-6); escalera y descansos por digitalizar."},
    {"descripcion": "Tanque elevado sobre N4 (A03, NTT +14.60) y cisterna (NFC −2.65): geometría y apoyos por definir; F/tanque en discrepancia."},
    {"descripcion": "Orientación 3↔A: hipótesis de piloto (auditoría 237), no corroborada por dos rasgos independientes."},
]
meta = {"contrato": "draft2model.geometria", "version_contrato": "0.3.0", "id": "pueblo-libre-002", "unidad_longitud": "m",
        "procedencia": proc("plano", "Borrador del caso real desde láminas L0001–L0006 con calibración registrada; encargo 09.",
                            "L0001–L0006", "Solo elementos sustentados; el resto en faltantes."),
        "faltantes": faltantes, "revision": {"estado": "borrador", "aprobacion": None}}
SALIDA.mkdir(parents=True, exist_ok=True)
tablas = {
    "niveles": csv_texto(["id", "cota", "procedencia"], [(n, z, json.loads(p)) for n, z, p in niveles]),
    "nodos": "id,x,y\n", "muros": "id,nodo_inicio,nodo_fin,nivel_inferior,nivel_superior,espesor\n",
    "vertices": csv_texto(["id", "x", "y", "z", "procedencia"], vertices),
    "superficies": csv_texto(["id", "vertices", "papel_geometrico", "procedencia"], superficies),
    "aberturas": csv_texto(["id", "superficie", "vertices", "procedencia"], aberturas),
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
r = subprocess.run(cmd + ["--salida", str(destino)], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", errors="replace", env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
print(r.returncode, (r.stdout + r.stderr)[-1500:])
