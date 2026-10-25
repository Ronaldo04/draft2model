"""Auditoría objetiva de la evidencia visual de una extracción: ¿la región citada contiene trazos?

Para cada candidato se renderiza el original (hash comprobado) y se mide la fracción de píxeles oscuros dentro de
su bbox. Una región sin trazos («vacia») demuestra que la evidencia no muestra lo leído (bbox desplazada u
omitida); una región con trazos NO demuestra que el valor sea correcto: no hay OCR ni lectura semántica.
También resume lecturas por recorte y la cobertura declarada (0.2.0). No modifica la extracción ni aprueba nada.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pymupdf
from PIL import Image

from .extraccion_preliminar import cargar_extraccion, validar_extraccion
from .ingreso import file_hash

UMBRAL_OSCURO = 128          # gris 0..255
UMBRAL_VACIA = 0.002         # fracción de tinta por debajo de la cual la región no contiene trazos
LADO_RENDER = 6000           # px del lado mayor de la página visible
AVISO = ("Indicador de tinta: «vacia» prueba que la bbox no muestra trazos; «con_trazos» no confirma el valor "
         "leído ni que la bbox enmarque el texto correcto. Revisión humana obligatoria.")


def _paginas(expediente: Path, ids: set[tuple[str, int]]):
    manifest = cargar_extraccion(expediente)
    root = Path(expediente).resolve().parent
    entradas = {a["id"]: a for a in manifest["archivos"]}
    salida = {}
    for fid, pagina in sorted(ids):
        ent = entradas[fid]
        ruta = root / ent["archivo"]
        if file_hash(ruta) != ent["sha256"]:
            raise ValueError(f"Original {fid} alterado; no se audita.")
        if ruta.suffix.lower() == ".pdf":
            with pymupdf.open(ruta) as doc:
                page = doc.load_page(pagina - 1)
                z = LADO_RENDER / max(page.rect.width, page.rect.height)
                pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z), alpha=False, colorspace=pymupdf.csGRAY)
                salida[(fid, pagina)] = Image.frombytes("L", (pix.width, pix.height), pix.samples)
        else:
            from .recortes import cargar_raster_orientado
            image, _ = cargar_raster_orientado(ruta)
            salida[(fid, pagina)] = image.convert("L")
    return salida


def auditar(expediente: Path, extraccion: dict) -> dict:
    check = validar_extraccion(extraccion)
    if not check.consistente:
        raise ValueError("Extracción inconsistente: " + "; ".join(map(str, check.errores)))
    ids = {(ev["archivo_id"], ev["pagina"]) for c in extraccion["candidatos"] for ev in c["evidencia"]}
    paginas = _paginas(expediente, ids)
    candidatos, por_recorte = [], {}
    for c in extraccion["candidatos"]:
        evidencias = []
        for ev in c["evidencia"]:
            im = paginas[(ev["archivo_id"], ev["pagina"])]
            w, h = im.size
            x0, y0, x1, y1 = ev["bbox_normalizada"]
            region = im.crop((int(x0 * w), int(y0 * h), max(int(x0 * w) + 1, int(x1 * w)), max(int(y0 * h) + 1, int(y1 * h))))
            hist = region.histogram()
            tinta = sum(hist[:UMBRAL_OSCURO]) / max(1, sum(hist))
            evidencias.append({"recorte_id": ev.get("recorte_id"), "tinta": round(tinta, 4),
                               "estado": "vacia" if tinta < UMBRAL_VACIA else "con_trazos"})
            if ev.get("recorte_id"):
                por_recorte[ev["recorte_id"]] = por_recorte.get(ev["recorte_id"], 0) + 1
        candidatos.append({"id": c["id"], "tipo": c["tipo"], "valor_propuesto": c["valor_propuesto"], "unidad": c["unidad"],
                           "evidencias": evidencias,
                           "estado": "vacia" if all(e["estado"] == "vacia" for e in evidencias) else "con_trazos"})
    vacias = [c["id"] for c in candidatos if c["estado"] == "vacia"]
    return {"contrato": "draft2model.auditoria_evidencia", "version_contrato": "0.1.0", "aviso": AVISO,
            "version_extraccion_contrato": extraccion["version_contrato"],
            "umbrales": {"gris_oscuro": UMBRAL_OSCURO, "fraccion_vacia": UMBRAL_VACIA, "lado_render_px": LADO_RENDER},
            "candidatos": candidatos, "resumen": {"candidatos": len(candidatos), "evidencia_vacia": len(vacias),
                                                   "ids_evidencia_vacia": vacias, "lecturas_por_recorte": por_recorte},
            "cobertura_declarada": extraccion.get("cobertura"), "aprobacion_ingenieria": None}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--expediente", type=Path, required=True)
    ap.add_argument("--extraccion", type=Path, required=True, help="extraccion.json de una versión registrada")
    ap.add_argument("--salida", type=Path, required=True, help="JSON nuevo; no se sobrescribe")
    a = ap.parse_args(argv)
    try:
        r = auditar(a.expediente, cargar_extraccion(a.extraccion))
        with open(a.salida, "x", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False, indent=2) + "\n")
    except (ValueError, OSError, KeyError) as exc:
        print("Auditoría no completada: " + str(exc), file=sys.stderr)
        return 1
    s = r["resumen"]
    print(f"{s['candidatos']} candidatos; evidencia vacía en {s['evidencia_vacia']}: {', '.join(s['ids_evidencia_vacia']) or '-'}")
    print(AVISO)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
