"""309: cobertura de anchos W y operadores de las páginas 7/8 (solo lectura del PDF publicado)."""
import re, sys, json
import pymupdf
SRC = sys.argv[1] if len(sys.argv) > 1 else "tmp/recorrido_09d3/resultados/informe/informe.pdf"
doc = pymupdf.open(SRC)


def ref(x, k):
    t, v = doc.xref_get_key(x, k)
    return int(v.split()[0]) if t == "xref" else v


def widths(x):
    w = ref(x, "W"); arr = doc.xref_object(w, compressed=True) if isinstance(w, int) else w
    toks = re.findall(r"\[|\]|-?\d+(?:\.\d+)?", arr)[1:-1]; out = {}; i = 0
    while i < len(toks):
        a = int(toks[i])
        if toks[i+1] == "[":
            j = i + 2; c = a
            while toks[j] != "]": out[c] = float(toks[j]); c += 1; j += 1
            i = j + 1
        else:
            b, v = int(toks[i+1]), float(toks[i+2]); out.update({c: v for c in range(a, b+1)}); i += 3
    return out


def fuentes_pagina(pg):
    r = ref(pg.xref, "Resources"); fd = doc.xref_get_key(r, "Font")[1]
    fd = doc.xref_object(int(fd.split()[0]), compressed=True) if fd.endswith("R") and not fd.startswith("<<") else fd
    return {n: int(x) for n, x in re.findall(r"/(\w+)\s+(\d+)\s+0\s+R", fd)}


informe = {}
for p in range(1, doc.page_count + 1):
    pg = doc[p-1]; fm = fuentes_pagina(pg); W = {}
    for n, x in fm.items():
        if doc.xref_get_key(x, "Subtype")[1] == "/Type0":
            W[n] = widths(int(doc.xref_get_key(x, "DescendantFonts")[1].strip("[]").split()[0]))
    conts = [int(v) for v in re.findall(r"(\d+)\s+0\s+R", doc.xref_get_key(pg.xref, "Contents")[1])]
    cur = None; faltan = {}; n = 0
    for c in conts:
        s = doc.xref_stream(c).decode("latin1")
        for m in re.finditer(r"/(\w+)\s+[\d.]+\s+Tf|<([0-9A-Fa-f]+)>", s):
            if m.group(1): cur = m.group(1); continue
            if cur in W:
                h = m.group(2)
                for k in range(0, len(h), 4):
                    cid = int(h[k:k+4], 16); n += 1
                    if cid not in W[cur]: faltan.setdefault(cur, set()).add(cid)
    informe[p] = {"fuentes": fm, "contenidos": conts, "glifos_cid": n, "cid_sin_ancho": {k: sorted(v) for k, v in faltan.items()}}
print(json.dumps(informe, ensure_ascii=False, indent=1))
