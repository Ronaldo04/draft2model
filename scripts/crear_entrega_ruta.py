"""Entrega inmutable de una etapa de la ruta autónoma 201: entregas/<NN>-<id>/ con fuentes.zip, manifiesto y logs.

Uso:
  python scripts/crear_entrega_ruta.py --etapa 01 --estado entregado --archivos a.py b.js ... \
      --logs tmp/x.log ... --datos manifiesto_parcial.json

`--datos` aporta pruebas, limitaciones, bloqueos y siguiente_etapa (JSON). El directorio debe ser NUEVO; nunca se
sobrescribe. Rechaza rutas fuera del proyecto, data/private, tmp/ (salvo logs copiados aparte) y archivos de claves.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PREFIJOS = ("draft2model/", "scripts/", "tests/", "examples/", "docs/")
# Archivos raíz autorizados explícitamente (R202-04); ningún otro archivo raíz se admite.
RAIZ_AUTORIZADA = frozenset(("README.md", "requirements.txt", "requirements-win-py310.lock",
                             "Abrir revision de planos.cmd", "Abrir control de avance.cmd"))
RESERVADOS = frozenset(("tarea", "id", "etapa", "estado", "snapshot", "archivos", "logs", "creado_utc"))
PROHIBIDOS = ("data/", "tmp/", "entregas/", ".venv/")
# R223-06: código legítimo cuyo nombre contiene «credencial» (lee la variable local, nunca la guarda).
# Cualquier otra ruta con ese nombre, y los archivos de claves, siguen rechazados.
CODIGO_CREDENCIALES = frozenset(("draft2model/credenciales_locales.py", "scripts/usar_credenciales_locales.py",
                                 "tests/test_credenciales_locales.py"))
SUFIJOS_SECRETOS = (".env", ".key", ".pem", ".pfx", ".p12")
PATRON_SECRETO = re.compile(rb"(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,})")
MARCAS_FICTICIAS = (b"prueba", b"test", b"fixture", b"ficticia", b"falsa", b"ejemplo")


def _contiene_secreto(raw: bytes) -> bool:
    """Patrón de clave real; se admiten valores ficticios marcados (p. ej. «sk-prueba…»)."""
    return any(not any(m in x.group(0).lower() for m in MARCAS_FICTICIAS) for x in PATRON_SECRETO.finditer(raw))


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _relativa(ruta: str) -> str:
    p = (RAIZ / ruta).resolve()
    rel = p.relative_to(RAIZ).as_posix()  # ValueError si sale del proyecto
    nombre = rel.lower()
    if (rel.startswith(PROHIBIDOS) or (not rel.startswith(PREFIJOS) and rel not in RAIZ_AUTORIZADA)
            or ("credencial" in nombre and rel not in CODIGO_CREDENCIALES) or nombre.endswith(SUFIJOS_SECRETOS)
            or ".local." in nombre or not p.is_file() or p.is_symlink()):
        raise ValueError(f"Archivo no admitido en la instantánea: {ruta}")
    if _contiene_secreto(p.read_bytes()):
        raise ValueError(f"Posible clave real en {ruta}; no se empaqueta.")
    return rel


def crear(etapa: str, estado: str, archivos: list[str], logs: list[str], datos: dict) -> Path:
    if etapa not in ("01", "02", "03", "04", "05", "06") or estado not in ("entregado", "bloqueado"):
        raise ValueError("Etapa 01..06 y estado entregado/bloqueado.")
    if not isinstance(datos, dict) or RESERVADOS & set(datos) or not {"pruebas", "limitaciones", "siguiente_etapa"} <= set(datos):
        raise ValueError("datos requiere pruebas, limitaciones y siguiente_etapa, sin claves reservadas.")
    rels = sorted({_relativa(a) for a in archivos})
    ident = uuid.uuid4().hex
    carpeta = RAIZ / "entregas" / f"{etapa}-{ident}"
    carpeta.mkdir(parents=True, exist_ok=False)
    contenido = {r: (RAIZ / r).read_bytes() for r in rels}
    zip_ruta = carpeta / "fuentes.zip"
    with zipfile.ZipFile(zip_ruta, "x", compression=zipfile.ZIP_DEFLATED) as z:
        for r in rels:
            info = zipfile.ZipInfo(r, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, contenido[r])
    copiados = {}
    (carpeta / "logs").mkdir()
    for log in logs:
        origen = (RAIZ / log).resolve()
        origen.relative_to(RAIZ)
        destino = carpeta / "logs" / origen.name
        shutil.copyfile(origen, destino)
        copiados[destino.relative_to(RAIZ).as_posix()] = _sha(destino.read_bytes())
    manifiesto = {
        "tarea": "ruta_autonoma_201", "id": ident, "etapa": etapa, "estado": estado,
        "creado_utc": datetime.now(timezone.utc).isoformat(),
        "snapshot": {"ruta": zip_ruta.relative_to(RAIZ).as_posix(), "sha256": _sha(zip_ruta.read_bytes())},
        "archivos": {r: _sha(b) for r, b in contenido.items()},
        "logs": copiados,
        **datos,
    }
    with open(carpeta / "manifiesto.json", "x", encoding="utf-8") as f:
        f.write(json.dumps(manifiesto, ensure_ascii=False, indent=2) + "\n")
    return carpeta / "manifiesto.json"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--etapa", required=True)
    ap.add_argument("--estado", required=True)
    ap.add_argument("--archivos", nargs="+", required=True)
    ap.add_argument("--logs", nargs="*", default=[])
    ap.add_argument("--datos", type=Path, required=True)
    a = ap.parse_args(argv)
    try:
        datos = json.loads(a.datos.read_text(encoding="utf-8"))
        print(crear(a.etapa, a.estado, a.archivos, a.logs, datos).relative_to(RAIZ).as_posix())
        return 0
    except (ValueError, OSError) as exc:
        print("Entrega no creada: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
