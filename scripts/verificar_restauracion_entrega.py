"""Restaura una entrega inmutable en una carpeta nueva y comprueba que el código se importa y prueba sin red.

Uso: python scripts/verificar_restauracion_entrega.py entregas/<NN>-<id>/manifiesto.json --destino tmp/<NUEVA>
     [--pruebas tests.test_a tests.test_b]

Comprueba SHA del ZIP y de cada miembro contra el manifiesto, extrae en una carpeta que no debe existir, compila
todo el paquete, importa cada módulo de draft2model y ejecuta las pruebas indicadas con las variables de claves
retiradas del entorno (no se leen ni se imprimen). Devuelve 0 solo si todo se cumple.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
VARIABLES_CLAVE = ("OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY")
PRUEBAS_BASE = ("tests.test_credenciales_locales", "tests.test_crear_entrega_ruta201")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def restaurar(manifiesto: Path, destino: Path, pruebas: list[str]) -> dict:
    m = json.loads(manifiesto.read_text(encoding="utf-8"))
    zip_ruta = RAIZ / m["snapshot"]["ruta"]
    if _sha(zip_ruta.read_bytes()) != m["snapshot"]["sha256"]:
        raise ValueError("SHA del ZIP distinto del manifiesto.")
    destino.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(zip_ruta) as z:
        nombres = {i.filename for i in z.infolist() if not i.is_dir()}
        if nombres != set(m["archivos"]):
            raise ValueError("Inventario del ZIP distinto del manifiesto.")
        for nombre in sorted(nombres):
            if nombre.startswith(("/", "\\")) or ".." in Path(nombre).parts:
                raise ValueError(f"Ruta insegura en el ZIP: {nombre}")
            raw = z.read(nombre)
            if _sha(raw) != m["archivos"][nombre]:
                raise ValueError(f"Bytes distintos del manifiesto: {nombre}")
            salida = destino / nombre
            salida.parent.mkdir(parents=True, exist_ok=True)
            salida.write_bytes(raw)
    entorno = {k: v for k, v in os.environ.items() if k not in VARIABLES_CLAVE}
    entorno.update(PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(destino))
    modulos = sorted(p.stem for p in (destino / "draft2model").glob("*.py") if p.stem != "__main__")
    pasos = {
        "compilar": [sys.executable, "-m", "compileall", "-q", "draft2model", "scripts", "tests"],
        "importar": [sys.executable, "-c", "import importlib\nfor m in %r: importlib.import_module('draft2model.' + m)" % modulos],
        "pruebas": [sys.executable, "-m", "unittest", *pruebas],
    }
    resultado = {"manifiesto": manifiesto.as_posix(), "destino": destino.as_posix(), "miembros": len(nombres),
                 "modulos_importados": len(modulos), "variables_clave_retiradas": list(VARIABLES_CLAVE), "pasos": {}}
    for nombre, comando in pasos.items():
        r = subprocess.run(comando, cwd=destino, env=entorno, capture_output=True, text=True, timeout=1800)
        resultado["pasos"][nombre] = {"codigo": r.returncode, "salida": (r.stdout + r.stderr)[-1500:]}
    resultado["correcta"] = all(p["codigo"] == 0 for p in resultado["pasos"].values())
    return resultado


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("manifiesto", type=Path)
    ap.add_argument("--destino", type=Path, required=True)
    ap.add_argument("--pruebas", nargs="*", default=list(PRUEBAS_BASE))
    a = ap.parse_args(argv)
    try:
        r = restaurar(a.manifiesto, a.destino, a.pruebas)
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as exc:
        print("Restauración no verificada: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r["correcta"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
