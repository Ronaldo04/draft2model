"""310: comprobación de FORMA de los prefijos, no solo tinta.

Para cada línea de texto (posiciones de caracteres de MuPDF rawdict, en pt) y cada uno de sus 4 primeros caracteres visibles:
  - recorta la caja del carácter en el render a comparar (p. ej. Poppler 96 dpi) y en el render de referencia MuPDF al mismo dpi;
  - binariza (gris < 160) y calcula IoU con el mejor desplazamiento de ±2 px (tolerancia de antialiasing/hinting);
  - registra además la primera columna con tinta en la banda de la línea frente a la x esperada del primer glifo.
Un prefijo omitido («do:» en vez de «Estado:») da IoU ≈ 0 en «E», «s», «t», «a» y primera tinta desplazada a la derecha.
Uso: python comparar_prefijos_forma.py PDF RENDER.png PAGINA DPI SALIDA.json
"""
import json, sys
import pymupdf


def gris(pm):
    if pm.alpha:
        pm = pymupdf.Pixmap(pm, 0)
    if pm.n != 1:
        pm = pymupdf.Pixmap(pymupdf.csGRAY, pm)
    return pm


def mascara(pm, r):
    x0, y0, x1, y1 = (max(int(v), 0) for v in r)
    x1, y1 = min(x1, pm.width), min(y1, pm.height)
    s = pm.samples
    return {(x - x0, y - y0) for y in range(y0, y1) for x in range(x0, x1) if s[y * pm.stride + x] < 160}


def iou(a, b):
    mejor = 0.0
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            bb = {(x + dx, y + dy) for x, y in b}
            u = len(a | bb)
            mejor = max(mejor, len(a & bb) / u if u else 1.0)
    return mejor


def primera_tinta(pm, y0, y1, x_desde):
    s = pm.samples
    for x in range(max(int(x_desde), 0), pm.width):
        if any(s[y * pm.stride + x] < 160 for y in range(max(int(y0), 0), min(int(y1), pm.height))):
            return x
    return None


def main(pdf, render, pagina, dpi, salida):
    doc = pymupdf.open(pdf); pg = doc[pagina - 1]; k = dpi / 72
    ref = gris(pg.get_pixmap(dpi=dpi)); obj = gris(pymupdf.Pixmap(render))
    assert (ref.width, ref.height) == (obj.width, obj.height), "tamaños distintos"
    filas = []
    for b in pg.get_text("rawdict")["blocks"]:
        for l in b.get("lines", []):
            chars = [c for sp in l["spans"] for c in sp["chars"] if c["c"].strip()]
            if not chars:
                continue
            txt = "".join(c["c"] for sp in l["spans"] for c in sp["chars"]).strip()
            ious = []
            for c in chars[:4]:
                r = pymupdf.Rect(c["bbox"]) * k
                r = (r.x0 - 1, r.y0 - 1, r.x1 + 1, r.y1 + 1)
                ious.append(round(iou(mascara(ref, r), mascara(obj, r)), 3))
            lb = pymupdf.Rect(l["bbox"]) * k
            esperado = chars[0]["bbox"][0] * k
            fr, fo = primera_tinta(ref, lb.y0, lb.y1, esperado - 6), primera_tinta(obj, lb.y0, lb.y1, esperado - 6)
            filas.append({"texto": txt[:40], "iou_4_primeros": ious, "primera_tinta_ref_px": fr, "primera_tinta_obj_px": fo,
                          "desplazamiento_px": None if fr is None or fo is None else fo - fr})
    sospechosas = [f for f in filas if min(f["iou_4_primeros"]) < 0.5 or f["desplazamiento_px"] is None or abs(f["desplazamiento_px"]) > 2]
    res = {"pdf": pdf, "render": render, "pagina": pagina, "dpi": dpi, "lineas": len(filas),
           "iou_min": min(min(f["iou_4_primeros"]) for f in filas), "sospechosas": sospechosas, "filas": filas}
    with open(salida, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(f"p{pagina} {render}: lineas {len(filas)} iou_min {res['iou_min']} sospechosas {len(sospechosas)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5])
