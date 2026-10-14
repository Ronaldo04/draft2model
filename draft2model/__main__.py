"""Interfaz de línea de comandos de Draft2Model."""

import argparse
import json
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
    ingreso.add_argument("--provisional-fuera-alcance", action="store_true", help="Caso solo para pruebas de procesamiento fuera del MVP")
    revision = commands.add_parser("revisar", help="Inspeccionar páginas y generar vistas previas locales")
    revision.add_argument("--caso", required=True)
    revision.add_argument("--max-lado", type=int, default=2400)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / "data" / "private"
    try:
        if args.command == "revisar":
            from .revision_documental import revisar_expediente
            case_dir = (root / args.caso).resolve()
            if case_dir == root.resolve() or not case_dir.is_relative_to(root.resolve()):
                raise ErrorIngreso("Identificador de caso fuera de la carpeta de expedientes.")
            report = revisar_expediente(case_dir / "expediente.json", args.max_lado)
            print(f"Revisión documental: {report}")
            print("Legibilidad y aprobación técnica pendientes de revisión humana.")
            summary = json.loads(report.read_text(encoding="utf-8"))["resumen"]
            return 2 if summary["archivos_con_error"] or summary["paginas_con_error"] else 0
        manifest = registrar_expediente(
            args.caso, args.archivos, root, uso_autorizado=args.uso_autorizado,
            provisional_fuera_alcance=args.provisional_fuera_alcance,
        )
    except (ValueError, OSError) as error:
        print(f"Operación no completada: {error}", file=sys.stderr)
        return 1
    print(f"Expediente en borrador: {manifest}")
    print("Pendiente de revisión técnica; no se generó ni analizó un modelo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
