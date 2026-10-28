"""Inspección y vistas previas locales; sin aprobación de ingeniería ni OCR."""

from __future__ import annotations

import json
import hashlib
import math
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pymupdf
from PIL import Image, ImageOps

from .ingreso import file_hash


def revisar_expediente(manifest_path: Path, max_lado: int = 2400) -> Path:
    if isinstance(max_lado, bool) or not isinstance(max_lado, int) or not 128 <= max_lado <= 4096:
        raise ValueError("max_lado debe ser un entero entre 128 y 4096 píxeles.")
    manifest_path = manifest_path.resolve()
    case_dir = manifest_path.parent
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("archivos"), list) or not manifest.get("id"):
        raise ValueError("Manifiesto de expediente inválido.")
    for entry in manifest["archivos"]:
        if not isinstance(entry, dict) or not all(isinstance(entry.get(key), str) for key in ("id", "archivo", "sha256")):
            raise ValueError("Referencia de original incompleta en el manifiesto.")
    run = case_dir / "revision_documental" / uuid4().hex
    run.mkdir(parents=True, exist_ok=False)
    documents = []
    for index, entry in enumerate(manifest["archivos"], 1):
        result = {"id": entry["id"], "archivo": entry["archivo"], "paginas": [], "error": None}
        documents.append(result)
        try:
            source = (case_dir / entry["archivo"]).resolve()
            if not source.is_relative_to(case_dir):
                raise ValueError("La referencia al original sale del expediente.")
            if file_hash(source) != entry["sha256"]:
                raise ValueError("El hash del original no coincide con el registro.")
            if source.suffix.lower() == ".pdf":
                with pymupdf.open(source) as document:
                    if document.needs_pass:
                        raise ValueError("PDF protegido; requiere desbloqueo por su propietario.")
                    if not document.is_pdf or document.page_count == 0:
                        raise ValueError("Documento sin páginas PDF utilizables.")
                    result["paginas_declaradas"] = document.page_count
                    result["reparacion_detectada"] = document.is_repaired
                    for number in range(document.page_count):
                        page_result = {"numero": number + 1, "error": None}
                        result["paginas"].append(page_result)
                        try:
                            page = document.load_page(number)
                            rectangle = page.rect
                            if not all(math.isfinite(v) and v > 0 for v in (rectangle.width, rectangle.height)):
                                raise ValueError("Dimensiones de página no utilizables.")
                            zoom = min(2, (max_lado - 1) / max(rectangle.width, rectangle.height))
                            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
                            pix.set_dpi(max(1, round(72 * zoom)), max(1, round(72 * zoom)))
                            preview = run / f"archivo-{index:04d}-pagina-{number + 1:04d}.png"
                            pix.save(preview)
                            text_count = len(page.get_text().strip())
                            page_result.update({
                                "ancho_puntos": rectangle.width,
                                "alto_puntos": rectangle.height,
                                "rotacion_pdf_grados": page.rotation,
                                "ancho_preview_px": pix.width,
                                "alto_preview_px": pix.height,
                                "dpi_render_aproximado": 72 * zoom,
                                "caracteres_texto_embebido": text_count,
                                "vista_previa": preview.relative_to(case_dir).as_posix(),
                                "legibilidad": "pendiente_revision_humana",
                                "advertencias": (["Sin texto embebido; valorar OCR."] if not text_count else [])
                                + (["Comprobar orientación de lectura."] if page.rotation else []),
                            })
                        except (ValueError, RuntimeError, OSError) as error:
                            page_result["error"] = str(error)
            elif source.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                with Image.open(source) as image:
                    image.verify()
                with Image.open(source) as image:
                    image.load()
                    original_size = image.size
                    exif_orientation = image.getexif().get(274, 1)
                    dpi = image.info.get("dpi")
                    corrected = ImageOps.exif_transpose(image).convert("RGB")
                    corrected.thumbnail((max_lado, max_lado))
                    preview = run / f"archivo-{index:04d}-pagina-0001.png"
                    corrected.save(preview)
                    result["paginas_declaradas"] = 1
                    result["paginas"].append({
                        "numero": 1, "error": None,
                        "dimensiones_original_px": list(original_size),
                        "dpi_declarado": list(dpi) if dpi else None,
                        "orientacion_exif": exif_orientation,
                        "ancho_preview_px": corrected.width,
                        "alto_preview_px": corrected.height,
                        "vista_previa": preview.relative_to(case_dir).as_posix(),
                        "legibilidad": "pendiente_revision_humana",
                        "advertencias": ["Revisar legibilidad y escala; no se infieren del DPI."],
                    })
            else:
                raise ValueError("Formato no soportado para revisión.")
            if file_hash(source) != entry["sha256"]:
                raise ValueError("El original cambió durante la revisión; descarte esta ejecución.")
        except (ValueError, RuntimeError, OSError, Image.DecompressionBombError) as error:
            result["error"] = str(error)
    report = {
        "version": "0.1.0",
        "caso": manifest["id"],
        "expediente_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "revisado_utc": datetime.now(timezone.utc).isoformat(),
        "alcance": manifest.get("alcance", {"estado": "pendiente_verificar"}),
        "estado": "pendiente_revision_humana",
        "documentos": documents,
        "resumen": {
            "archivos": len(documents),
            "archivos_con_error": sum(bool(d["error"]) for d in documents),
            "paginas_renderizadas": sum(not p["error"] for d in documents if not d["error"] for p in d["paginas"]),
            "paginas_con_error": sum(bool(p["error"]) for d in documents for p in d["paginas"]),
        },
    }
    output = run / "revision.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output
