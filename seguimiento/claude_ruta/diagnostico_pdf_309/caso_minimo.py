"""309: caso mínimo aislado. Usa draft2model.informe._pdf (solo lectura) con un HTML diminuto, sin expediente ni cálculos,
y reporta la estructura de fuentes generada por PyMuPDF Story/DocumentWriter + pie insert_text + garbage=4."""
import sys, json, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import pymupdf
from draft2model.informe import _pdf
OUT = Path(__file__).parent
html = ("<h2>7. Prueba mínima</h2><h3>DERIVA-S1-ALB-SX / SX / X / N3</h3>"
        "<p>Estado: evaluado; entrada: 0.001402 1; evaluado: 0.006309 1; límite configurado: &lt;= 0.005 1.</p>"
        "<p style='font-family:monospace'>resultados: 2cc454129a1d17a2 f8696d0639c1f406</p>")
pdf = _pdf(html); (OUT / "caso_minimo.pdf").write_bytes(pdf)
doc = pymupdf.open(stream=pdf, filetype="pdf"); info = {"version_pdf": doc.metadata.get("format"), "fuentes": []}
for f in doc[0].get_fonts(full=True):
    x = f[0]; d = {"xref": x, "tipo": f[2], "basefont": f[3], "nombre_recurso": f[4]}
    if f[2] == "Type0":
        desc = int(doc.xref_get_key(x, "DescendantFonts")[1].strip("[]").split()[0]); fd = int(doc.xref_get_key(desc, "FontDescriptor")[1].split()[0])
        ff = int(doc.xref_get_key(fd, "FontFile3")[1].split()[0]); cff = doc.xref_stream(ff)
        d.update({"descendiente": doc.xref_get_key(desc, "Subtype")[1], "fontfile3": doc.xref_get_key(ff, "Subtype")[1],
                  "cff_con_ROS": b"\x0c\x1e" in cff[:300], "glifos": pymupdf.Font(fontbuffer=cff).glyph_count, "tounicode": doc.xref_get_key(x, "ToUnicode")[1]})
    else:
        d["incrustada"] = doc.xref_get_key(x, "FontFile")[0] != "null" or doc.xref_get_key(x, "FontFile2")[0] != "null"
    info["fuentes"].append(d)
(OUT / "caso_minimo_estructura.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(info, ensure_ascii=False))
