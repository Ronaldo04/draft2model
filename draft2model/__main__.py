"""Interfaz de línea de comandos de Draft2Model."""

import argparse
import json
import sys
from pathlib import Path

from .ingreso import ErrorIngreso, registrar_expediente


def _valor_json(texto: str):
    """Número o cadena JSON; no convierte texto a número ni evalúa expresiones."""

    def no_finito(nombre):
        raise ValueError(f"valor no finito {nombre}")

    try:
        valor = json.loads(texto, parse_constant=no_finito)
    except ValueError as error:
        raise ValueError(f"--valor-json no es JSON válido: {error}") from error
    if isinstance(valor, bool) or not isinstance(valor, (int, float, str)):
        raise ValueError('--valor-json admite un número JSON (2.6) o una cadena JSON ("EJE A").')
    return valor


def _imprimir_comprobacion(comprobacion) -> None:
    resultado = comprobacion.resultado
    for problema in comprobacion.problemas:
        print(f"  Problema de evidencia: {problema}")
    if resultado is None:
        return
    for error in resultado.errores:
        print(f"  Error: {error}")
    for advertencia in resultado.advertencias:
        print(f"  Advertencia: {advertencia}")
    resumen = resultado.resumen
    if resumen:
        print(
            "  Candidatos: {candidatos} (pendientes {pendientes}, revisados {revisados}, rechazados {rechazados}); "
            "valores desconocidos {valores_desconocidos}, unidades desconocidas {unidades_desconocidas}.".format(**resumen)
        )
    estados = [e for lista in resultado.referencias.values() for e in lista]
    if estados:
        conteo = ", ".join(f"{estado} {estados.count(estado)}" for estado in sorted(set(estados)))
        print(f"  Referencias de evidencia: {conteo}.")
    for archivo in comprobacion.archivos_verificados:
        print(f"  SHA256 comprobado: {archivo['tipo']} {archivo['id']}")


def _extracciones(args, root: Path) -> int:
    from . import gestion_extraccion as g

    aviso = "Revisión técnica pendiente: revisar candidatos no aprueba datos de ingeniería."
    try:
        if args.command == "importar-extraccion":
            resultado = g.importar_extraccion(root, args.caso, args.entrada)
            print(f"Extracción registrada: {resultado.identificador}")
            print(f"  Carpeta: {resultado.ruta}")
        elif args.command == "validar-extraccion":
            comprobacion = g.validar_version(root, args.caso, args.extraccion)
            print(f"Extracción {args.extraccion}: {'correcta' if comprobacion.correcta else 'NO supera la comprobación'}")
            _imprimir_comprobacion(comprobacion)
            print(aviso)
            return 0 if comprobacion.correcta else 2
        elif args.command == "corregir-extraccion":
            extra = {}
            if args.valor_json is not None:
                extra["valor_revisado"] = _valor_json(args.valor_json)
            if args.unidad is not None:
                extra["unidad_revisada"] = args.unidad
            resultado = g.corregir_version(
                root, args.caso, args.extraccion, args.candidato, estado=args.estado,
                motivo=args.motivo, fecha=args.fecha, revisor_declarado=args.revisor, **extra,
            )
            print(f"Nueva versión: {resultado.identificador} (padre {args.extraccion}, que no se modifica)")
            print("  Revisor declarado; su identidad no se verifica.")
        else:
            resultado = g.exportar_version(root, args.caso, args.extraccion)
            excluidos = resultado.datos["excluidos"]
            print(f"Exportación: {resultado.ruta}")
            print(
                f"  Revisados exportados: {len(resultado.datos['candidatos'])}; "
                f"pendientes excluidos: {len(excluidos['pendientes'])}; rechazados excluidos: {len(excluidos['rechazados'])}."
            )
            print("  No se generó geometría; aprobacion_ingenieria permanece null.")
        _imprimir_comprobacion(resultado.comprobacion)
        print(aviso)
        return 0
    except g.ErrorEvidencia as error:
        print(f"Operación rechazada; no se guardó nada. {error}", file=sys.stderr)
        return 2
    except (ValueError, OSError) as error:
        print(f"Operación no completada: {error}", file=sys.stderr)
        return 1


def main(argv=None, raiz=None) -> int:
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
    crop = commands.add_parser("recortar", help="Ampliar una región PDF conservando sus coordenadas")
    crop.add_argument("--caso", required=True)
    crop.add_argument("--archivo", required=True, help="ID L0001, L0002, etc.")
    crop.add_argument("--pagina", type=int, required=True)
    crop.add_argument("--bbox", nargs=4, type=float, required=True, metavar=("X0", "Y0", "X1", "Y1"))
    crop.add_argument("--dpi", type=int, default=150)
    crop.add_argument("--etiqueta", default="region")
    imp = commands.add_parser("importar-extraccion", help="Registrar una extracción preliminar tras comprobar su evidencia")
    imp.add_argument("--caso", required=True)
    imp.add_argument("--entrada", type=Path, required=True, help="JSON draft2model.extraccion_preliminar")
    val = commands.add_parser("validar-extraccion", help="Volver a comprobar una versión registrada sin modificarla")
    val.add_argument("--caso", required=True)
    val.add_argument("--extraccion", required=True, help="ID de versión (32 hexadecimales)")
    cor = commands.add_parser("corregir-extraccion", help="Crear una versión nueva con la revisión de un candidato")
    cor.add_argument("--caso", required=True)
    cor.add_argument("--extraccion", required=True, help="ID de la versión padre")
    cor.add_argument("--candidato", required=True)
    cor.add_argument("--estado", required=True, choices=("pendiente", "revisado", "rechazado"))
    cor.add_argument("--motivo", required=True)
    cor.add_argument("--fecha", required=True, help="AAAA-MM-DD")
    cor.add_argument("--revisor", required=True, help="Declaración de quien revisa; no se verifica")
    cor.add_argument("--valor-json", help='Solo para revisado: número (2.6) o cadena JSON ("EJE A")')
    cor.add_argument("--unidad", help="Solo para revisado: m, cm, mm, desconocida o no_aplica")
    exp = commands.add_parser("exportar-extraccion", help="Exportar solo candidatos revisados con su evidencia")
    exp.add_argument("--caso", required=True)
    exp.add_argument("--extraccion", required=True)
    args = parser.parse_args(argv)
    root = Path(raiz) if raiz is not None else Path(__file__).resolve().parents[1] / "data" / "private"
    if args.command.endswith("-extraccion"):
        return _extracciones(args, root)
    try:
        if args.command == "recortar":
            from .recortes import generar_recorte
            case_dir = (root / args.caso).resolve()
            if case_dir == root.resolve() or not case_dir.is_relative_to(root.resolve()):
                raise ErrorIngreso("Caso fuera de la carpeta de expedientes.")
            output = generar_recorte(case_dir / "expediente.json", args.archivo, args.pagina, args.bbox, dpi=args.dpi, etiqueta=args.etiqueta)
            print(f"Recorte y coordenadas: {output}")
            return 0
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
