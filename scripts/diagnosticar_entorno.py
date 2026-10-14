"""Inventario local de O1; no inicia ETABS ni lee archivos de licencia o secretos."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path


PACKAGES = ("comtypes", "pydantic", "Pillow", "PyMuPDF", "pytest")
IGNORED = {".venv", "venv", "tmp", ".git", "node_modules", "__pycache__"}
MODEL_SUFFIXES = {".edb", ".e2k", ".dwg", ".dxf"}


def installed_packages() -> dict[str, str | None]:
    versions = {}
    for name in PACKAGES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def etabs_installations() -> list[dict[str, object]]:
    root = Path("C:/Program Files/Computers and Structures")
    if not root.is_dir():
        return []
    return [
        {
            "directory": str(directory),
            "executable_exists": (directory / "ETABS.exe").is_file(),
            "api_library_exists": (directory / "ETABSv1.dll").is_file(),
            "api_help_exists": (directory / "CSI API ETABS v1.chm").is_file(),
        }
        for directory in sorted(root.glob("ETABS*"))
        if directory.is_dir()
    ]


def registered_com_classes() -> dict[str, bool | None]:
    names = ("CSI.ETABS.API.ETABSObject", "ETABSv1.Helper", "CSiAPIv1.Helper")
    if sys.platform != "win32":
        return {name: None for name in names}
    import winreg

    result = {}
    for name in names:
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, name + "\\CLSID"):
                result[name] = True
        except FileNotFoundError:
            result[name] = False
        except PermissionError:
            result[name] = None
    return result


def model_candidates(root: Path) -> list[str]:
    result = []
    pending = [root]
    while pending:
        directory = pending.pop()
        for entry in directory.iterdir():
            if entry.is_dir() and entry.name not in IGNORED:
                pending.append(entry)
            elif entry.is_file() and entry.suffix.lower() in MODEL_SUFFIXES:
                result.append(entry.relative_to(root).as_posix())
    return sorted(result)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="JSON local; no se envía a servicios externos")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": {
            "version": platform.python_version(),
            "bits": struct.calcsize("P") * 8,
            "executable": sys.executable,
            "isolated_environment": sys.prefix != sys.base_prefix,
        },
        "platform": platform.system(),
        "packages": installed_packages(),
        "etabs_installations": etabs_installations(),
        "com_registered": registered_com_classes(),
        "local_model_candidates": model_candidates(root),
        "license_status": "not_verified",
        "api_connection_status": "not_executed",
        "analysis_status": "not_executed",
    }
    content = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content + "\n", encoding="utf-8")
    print(content)


if __name__ == "__main__":
    main()
