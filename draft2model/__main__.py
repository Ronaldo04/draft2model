"""Interfaz de línea de comandos de Draft2Model."""

import argparse
import sys
from pathlib import Path

from .ingreso import ErrorIngreso, registrar_expediente


def main() -> int:
    parser = argparse.ArgumentParser(description="Registro local de planos y originales.")
    commands = parser.add_subparsers(dest="command", required=True)
    ingreso = commands.add_parser("ingresar", help="Crear un expediente en borrador")
    ingreso.add_argument("--caso", required=True, help="Identificador sin datos personales")
    ingreso.add_argument("--archivos", type=Path, nargs="+", required=True)
    ingreso.add_argument("--uso-autorizado", action="store_true", help="Declarar autorización de uso")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / "data" / "private"
    try:
        manifest = registrar_expediente(
            args.caso, args.archivos, root, uso_autorizado=args.uso_autorizado
        )
    except (ErrorIngreso, OSError) as error:
        print(f"No se creó el expediente: {error}", file=sys.stderr)
        return 1
    print(f"Expediente en borrador: {manifest}")
    print("Pendiente de revisión técnica; no se generó ni analizó un modelo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
