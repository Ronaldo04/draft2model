"""309: ligaduras tipográficas en el texto extraíble (U+FB00–FB06) del PDF publicado y prueba aislada de mitigación por CSS."""
import sys, json, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import pymupdf
from draft2model.informe import _pdf
OUT = Path(__file__).parent; LIG = re.compile("[\ufb00-\ufb06]")
doc = pymupdf.open("tmp/recorrido_09d3/resultados/informe/informe.pdf")
pub = {p + 1: len(LIG.findall(doc[p].get_text())) for p in range(doc.page_count)}
base = "<p>Estado: evaluado; satisfacción de regla configurada: False. Fuente de regla DECLARADA; flujo eficaz; afianzado.</p>"
variantes = {"sin_css": base, "font-variant-ligatures:none": "<style>body{font-variant-ligatures:none}</style>" + base,
             "font-feature-settings liga 0": "<style>body{font-feature-settings:'liga' 0}</style>" + base}
pruebas = {}
for k, h in variantes.items():
    t = pymupdf.open(stream=_pdf(h), filetype="pdf")[0].get_text()
    pruebas[k] = {"ligaduras": len(LIG.findall(t)), "contiene_configurada": "configurada" in t}
res = {"ligaduras_por_pagina_publicado": pub, "prueba_aislada_css": pruebas}
(OUT / "ligaduras.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8"); print(json.dumps(res, ensure_ascii=False))
