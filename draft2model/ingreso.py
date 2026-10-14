"""Registro local de originales; sin OCR, modelado ni aprobación técnica."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path


class ErrorIngreso(ValueError):
    """Entrada que no permite crear un expediente."""


EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
RESERVED = {"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(1, 10)
}


def check_source(path: Path) -> None:
    if not path.is_file():
        raise ErrorIngreso(f"Archivo no encontrado: {path.name}")
    suffix = path.suffix.lower()
    if suffix not in EXTENSIONS:
        raise ErrorIngreso(f"Formato no soportado: {suffix or 'sin extensión'}")
    with path.open("rb") as stream:
        header = stream.read(8)
    recognized = (
        (suffix == ".pdf" and header.startswith(b"%PDF-"))
        or (suffix == ".png" and header == b"\x89PNG\r\n\x1a\n")
        or (suffix in {".jpg", ".jpeg"} and header.startswith(b"\xff\xd8\xff"))
    )
    if not recognized:
        raise ErrorIngreso(f"Firma de archivo incompatible o vacía: {path.name}")


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def registrar_expediente(
    case_id: str,
    sources: list[Path],
    case_root: Path,
    *,
    uso_autorizado: bool = False,
    provisional_fuera_alcance: bool = False,
) -> Path:
    """Crea expediente.json y copias exactas en un directorio nuevo.

    La comprobación de firma no valida legibilidad ni integridad completa.
    El estado permanece en borrador hasta una revisión técnica posterior.
    """
    if not uso_autorizado:
        raise ErrorIngreso("Debe declararse la autorización de uso de los archivos.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", case_id) or case_id.upper() in RESERVED:
        raise ErrorIngreso("Identificador inválido; use letras, números, guion o guion bajo.")
    if not sources:
        raise ErrorIngreso("Se requiere al menos un PDF o imagen.")

    root = case_root.resolve()
    target = root / case_id
    if target.exists():
        raise ErrorIngreso("El expediente ya existe; no se sobrescribe.")
    resolved_sources = [source.resolve() for source in sources]
    fingerprints = []
    for source in resolved_sources:
        check_source(source)
        fingerprints.append(file_hash(source))
    if len(set(fingerprints)) != len(fingerprints):
        raise ErrorIngreso("Hay originales duplicados por contenido; revise la selección.")

    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".ingreso-", dir=root) as staging:
        prepared = Path(staging) / "expediente"
        originals = prepared / "originales"
        originals.mkdir(parents=True)
        files = []
        for index, (source, fingerprint) in enumerate(zip(resolved_sources, fingerprints), 1):
            relative = f"originales/lamina-{index:04d}{source.suffix.lower()}"
            copied = prepared / relative
            shutil.copyfile(source, copied)
            if file_hash(copied) != fingerprint:
                raise ErrorIngreso("Un archivo cambió durante el registro; vuelva a intentarlo.")
            files.append({
                "id": f"L{index:04d}",
                "nombre_original": source.name,
                "archivo": relative,
                "sha256": fingerprint,
                "bytes": copied.stat().st_size,
                "revision": "pendiente",
                "paginas": None,
            })
        manifest = {
            "version_contrato": "0.1.0",
            "id": case_id,
            "estado": "borrador",
            "registrado_utc": datetime.now(timezone.utc).isoformat(),
            "uso_autorizado_declarado": True,
            "alcance": {
                "estado": "fuera_mvp_declarado" if provisional_fuera_alcance else "pendiente_verificar",
                "uso": "pruebas_procesamiento" if provisional_fuera_alcance else "pendiente",
                "motivos": ["Sistema constructivo y cantidad de pisos fuera del MVP, según declaración."]
                if provisional_fuera_alcance else [],
            },
            "archivos": files,
            "datos_ingenieria": None,
            "aprobacion_tecnica": None,
            "faltantes": [
                "Revisar integridad, legibilidad y totalidad de láminas y páginas.",
                "Completar y revisar datos de ingeniería, fuentes e hipótesis.",
                "Registrar aprobación técnica antes de generar un modelo.",
            ],
        }
        (prepared / "expediente.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        if target.exists():
            raise ErrorIngreso("El expediente ya existe; no se sobrescribe.")
        prepared.rename(target)
    return target / "expediente.json"
