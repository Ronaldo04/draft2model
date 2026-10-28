"""309: comprobación objetiva de prefijos visibles. Para cada línea de texto (MuPDF get_text) se mide la tinta en la caja
de sus 3 primeros caracteres en (a) render MuPDF y (b) render de Windows.Data.Pdf. Sin OCR: tinta ausente = prefijo no dibujado."""
import json, sys
from pathlib import Path
import pymupdf
SRC = sys.argv[1]; WIN = Path(sys.argv[2]); OUT = Path(sys.argv[3])
doc = pymupdf.open(SRC); res = {}


def tinta(pm, r, sx, sy):
    x0, y0, x1, y1 = int(r[0]*sx), int(r[1]*sy), int(r[2]*sx)+1, int(r[3]*sy)+1; n = pm.n; s = pm.samples; c = 0
    for y in range(max(y0, 0), min(y1, pm.height)):
        for x in range(max(x0, 0), min(x1, pm.width)):
            i = y*pm.stride + x*n
            if min(s[i:i+3]) < 160: c += 1
    return c


for p in range(1, doc.page_count + 1):
    pg = doc[p-1]; mu = pg.get_pixmap(dpi=144); wp = WIN / f"windows_aislado_p{p}.png"
    win = pymupdf.Pixmap(str(wp)) if wp.exists() else None
    if win and win.alpha: win = pymupdf.Pixmap(win, 0)
    filas = []
    for b in pg.get_text("rawdict")["blocks"]:
        for l in b.get("lines", []):
            chars = [ch for sp in l["spans"] for ch in sp["chars"] if ch["c"].strip()]
            if not chars: continue
            r = pymupdf.Rect(chars[0]["bbox"]);
            for ch in chars[1:3]: r |= pymupdf.Rect(ch["bbox"])
            txt = "".join(ch["c"] for sp in l["spans"] for ch in sp["chars"])[:40]
            f = {"texto": txt, "caja_pt": [round(v, 1) for v in r], "tinta_mupdf": tinta(mu, r, 2, 2)}
            if win: f["tinta_windows"] = tinta(win, r, win.width/pg.rect.width, win.height/pg.rect.height)
            filas.append(f)
    res_min = {"min_tinta_mupdf": min(f["tinta_mupdf"] for f in filas), "min_tinta_windows": min((f.get("tinta_windows", -1) for f in filas), default=-1)}
    sin = [f for f in filas if f["tinta_mupdf"] == 0 or f.get("tinta_windows", 1) == 0]
    res[p] = {"lineas": len(filas), **res_min, "sin_tinta_en_prefijo": sin}
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print({p: (v["lineas"], v["min_tinta_mupdf"], v["min_tinta_windows"], len(v["sin_tinta_en_prefijo"])) for p, v in res.items()})
