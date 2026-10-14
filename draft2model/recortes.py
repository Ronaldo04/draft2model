"""Recortes PDF con coordenadas trazables; sin inferir escala estructural."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from uuid import uuid4

import pymupdf

from .ingreso import file_hash


def punto_a_pagina(metadata: dict, x: float, y: float) -> tuple[float, float]:
    """Transforma un punto de píxel del recorte a puntos de página visible."""
    a, b, c, d, e, f = metadata["pixel_a_pagina_visible"]
    return a * x + c * y + e, b * x + d * y + f


def generar_recorte(
    manifest_path: Path,
    archivo_id: str,
    pagina: int,
    bbox: list[float],
    *,
    dpi: int = 150,
    etiqueta: str = "region",
) -> Path:
    """bbox=[x0,y0,x1,y1] normalizada sobre la página visible (rotación aplicada)."""
    if isinstance(pagina, bool) or not isinstance(pagina, int) or pagina < 1:
        raise ValueError("Página debe ser un entero positivo, empezando en 1.")
    if isinstance(dpi, bool) or not isinstance(dpi, int) or not 72 <= dpi <= 300:
        raise ValueError("DPI debe ser un entero entre 72 y 300.")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4 or any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in bbox
    ):
        raise ValueError("bbox requiere cuatro números finitos.")
    x0, y0, x1, y1 = bbox
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise ValueError("bbox debe tener área positiva y permanecer entre 0 y 1.")
    if not isinstance(etiqueta, str) or not etiqueta.strip():
        raise ValueError("Etiqueta debe ser texto no vacío.")
    manifest_path = manifest_path.resolve()
    case_dir = manifest_path.parent
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    entries = [e for e in manifest["archivos"] if e["id"] == archivo_id]
    if len(entries) != 1:
        raise ValueError("Identificador de archivo ausente o ambiguo.")
    entry = entries[0]
    source = (case_dir / entry["archivo"]).resolve()
    if not source.is_relative_to(case_dir):
        raise ValueError("El original sale del expediente.")
    if source.suffix.lower() != ".pdf":
        raise ValueError("Esta primera versión de recortes admite PDF; imágenes pendientes.")
    if file_hash(source) != entry["sha256"]:
        raise ValueError("Hash del original incompatible con el registro.")
    with pymupdf.open(source) as doc:
        if doc.needs_pass:
            raise ValueError("PDF protegido; no se desbloquea automáticamente.")
        if pagina > doc.page_count:
            raise ValueError("La página solicitada no existe.")
        page = doc.load_page(pagina - 1)
        bounds = page.rect
        clip = pymupdf.Rect(x0 * bounds.width, y0 * bounds.height, x1 * bounds.width, y1 * bounds.height)
        zoom = dpi / 72
        max_pixels = 8_000_000
        while (math.ceil(clip.width * zoom) + 2) * (math.ceil(clip.height * zoom) + 2) > max_pixels:
            zoom *= 0.9
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip, alpha=False)
        if not pix.width or not pix.height:
            raise ValueError("La región no produce un recorte utilizable.")
        pix.set_dpi(max(1, round(72 * zoom)), max(1, round(72 * zoom)))
        image_bytes = pix.tobytes("png")
        region_id = uuid4().hex
        metadata = {
            "version": "0.1.0",
            "id": region_id,
            "caso": manifest["id"],
            "archivo_id": archivo_id,
            "pagina": pagina,
            "etiqueta": etiqueta,
            "origen_sha256": entry["sha256"],
            "expediente_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "alcance": manifest.get("alcance", {"estado": "pendiente_verificar"}),
            "sistema_coordenadas": "pagina_visible_normalizada",
            "bbox_normalizada": list(bbox),
            "pagina_visible_pt": [bounds.width, bounds.height],
            "bbox_pagina_visible_pt": list(clip),
            "bbox_pagina_sin_rotacion_pt": list(clip * page.derotation_matrix),
            "pagina_visible_a_sin_rotacion": list(page.derotation_matrix),
            "rotacion_pdf_grados": page.rotation,
            "dpi_solicitado": dpi,
            "dpi_render_aproximado": 72 * zoom,
            "dimensiones_px": [pix.width, pix.height],
            "pixel_a_pagina_visible": [1 / zoom, 0, 0, 1 / zoom, pix.x / zoom, pix.y / zoom],
            "imagen": "recorte.png",
            "imagen_sha256": hashlib.sha256(image_bytes).hexdigest(),
            "estado": "pendiente_revision",
            "escala_geometrica": None,
        }
    if file_hash(source) != entry["sha256"]:
        raise ValueError("El original cambió durante el renderizado.")
    output = case_dir / "recortes" / region_id
    output.mkdir(parents=True, exist_ok=False)
    (output / "recorte.png").write_bytes(image_bytes)
    json_path = output / "recorte.json"
    json_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return json_path
