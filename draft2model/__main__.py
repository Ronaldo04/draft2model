"""Interfaz de línea de comandos de Draft2Model."""

import argparse
import json
import sys
from pathlib import Path

from .ingreso import ErrorIngreso, registrar_expediente

# Los módulos conservan su CLI propia; este registro da un único punto de entrada.
MODULOS_CLI = {
    'acciones-liquidos': ('draft2model.acciones_liquidos', 'Derivar presiones estáticas declaradas sin aplicar cargas ni aprobar ingeniería'),
    'analizar-etabs': ('draft2model.analisis_etabs', 'Analizar copia de modelo revisado en instancia ETABS nueva'),
    'revision-modelo': ('draft2model.revision_modelo', 'Registrar modelo construido y declarar su revisión propia'),
    'construir-etabs': ('draft2model.ejecucion_modelo', 'Aplicar plan a copia ETABS con vigencia y exclusión verificadas'),
    'plan-etabs': ('draft2model.operaciones_etabs', 'Preparar plan estático de operaciones CSI sin ejecutarlo'),
    'configuracion': ('draft2model.gestion_configuracion', 'Versionar y aprobar configuración estructural explícita'),
    'normalizar-etabs': ('draft2model.normalizacion_etabs', 'Registrar indicadores desde tablas y correspondencias revisadas'),
    'etabs': ('draft2model.cli_etabs', 'Preparar o ejecutar operaciones ETABS explícitas'),
    'preprocesar': ('draft2model.preprocesamiento', 'Preparar imagen con transformación reversible'),
    'importar-tablas': ('draft2model.importacion_tabular', 'Convertir CSV supervisado al contrato geométrico'),
    'convertir-geometria': ('draft2model.conversion_geometria', 'Convertir lecturas revisadas con correspondencias explícitas'),
    'planes-versionados': ('draft2model.gestion_planes', 'Generar o comprobar plan ligado a versión geométrica'),
    'modelo-estructural': ('draft2model.modelo_estructural', 'Validar configuración estructural explícita'),
    'informe': ('draft2model.informe', 'Exportar informe preliminar JSON/HTML/PDF'),
    'auditar-evidencia': ('draft2model.auditoria_evidencia', 'Detectar evidencias de lectura sin trazos en el original'),
    'panel-tecnico': ('draft2model.panel_tecnico', 'Generar panel técnico interactivo local'),
    'demo-integrada': ('examples.flujo_integrado_sintetico', 'Recorrido sintético completo sin red ni ETABS'),
}


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
            if args.tipo is not None:
                extra["tipo_revisado"] = args.tipo
            resultado = g.corregir_version(
                root, args.caso, args.extraccion, args.candidato, estado=args.estado,
                motivo=args.motivo, fecha=args.fecha, revisor_declarado=args.revisor, **extra,
            )
            print(f"Nueva versión: {resultado.identificador} (padre {args.extraccion}, que no se modifica)")
            print("  Revisor declarado; su identidad no se verifica.")
        elif args.command == "reubicar-extraccion":
            resultado = g.reubicar_evidencia(root, args.caso, args.extraccion, args.candidato, indice=args.indice,
                                             bbox=list(args.bbox), motivo=args.motivo, fecha=args.fecha,
                                             revisor_declarado=args.revisor)
            print(f"Versión con evidencia reubicada: {resultado.identificador} (padre {args.extraccion}); lectura sin aprobar.")
        elif args.command == "lectura-manual-extraccion":
            resultado = g.agregar_lectura(root, args.caso, args.extraccion, tipo=args.tipo, valor=_valor_json(args.valor_json),
                                          unidad=args.unidad, texto_fuente=args.texto_fuente, simbolo=args.simbolo,
                                          archivo_id=args.archivo, pagina=args.pagina, bbox=list(args.bbox),
                                          motivo=args.motivo, fecha=args.fecha, revisor_declarado=args.revisor)
            print(f"Lectura manual {resultado.datos['lectura']['candidato']} en la versión {resultado.identificador}; pendiente de revisión.")
        elif args.command == "vigencia-extraccion":
            print(json.dumps(g.vigencia(root, args.caso, args.extraccion), ensure_ascii=False, indent=2))
            return 0
        elif args.command == "migrar-extraccion":
            datos = json.loads(args.propuestas.read_text(encoding="utf-8")) if args.propuestas else {}
            if not isinstance(datos, dict) or set(datos) - {"propuestas", "cobertura"}:
                raise ValueError("--propuestas: objeto con 'propuestas' y, opcionalmente, 'cobertura'.")
            resultado = g.migrar_version(root, args.caso, args.extraccion, datos.get("propuestas", {}),
                                         origen=args.origen, cobertura=datos.get("cobertura"))
            print(f"Versión 0.2.0: {resultado.identificador} (padre {args.extraccion}, que no se modifica)")
            print("  Lecturas intactas; las clasificaciones quedan propuestas y pendientes de revisión.")
        else:
            resultado = g.exportar_version(root, args.caso, args.extraccion)
            excluidos = resultado.datos["excluidos"]
            print(f"Exportación: {resultado.ruta}")
            print(
                f"  Revisados exportados: {len(resultado.datos['candidatos'])}; "
                f"pendientes excluidos: {len(excluidos['pendientes'])}; rechazados excluidos: {len(excluidos['rechazados'])}."
                + (f" Resultados impresos excluidos de entradas: {len(excluidos['resultados_impresos'])}."
                   if "resultados_impresos" in excluidos else "")
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
    argumentos = list(sys.argv[1:] if argv is None else argv)
    if argumentos and argumentos[0] in MODULOS_CLI:
        from importlib import import_module
        modulo = import_module(MODULOS_CLI[argumentos[0]][0])
        return modulo.main(argumentos[1:]) or 0
    parser = argparse.ArgumentParser(description="Expedientes, revisión de lecturas y planes geométricos locales.")
    commands = parser.add_subparsers(dest="command", required=True)
    for nombre, (_, ayuda) in MODULOS_CLI.items():
        commands.add_parser(nombre, help=ayuda, add_help=False)
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
    cor.add_argument("--unidad", help="Solo para revisado: unidad admitida por el tipo (m, kgf/m2, kgf/cm2, adimensional, no_aplica…)")
    cor.add_argument("--tipo", help="Solo para revisado en contrato 0.2.0: reclasifica (cota, cantidad, carga, propiedad, "
                                    "parametro, texto, resultado_impreso, etiqueta, elemento)")
    reu = commands.add_parser("reubicar-extraccion", help="Versión nueva con la región de evidencia corregida (no aprueba)")
    reu.add_argument("--caso", required=True)
    reu.add_argument("--extraccion", required=True)
    reu.add_argument("--candidato", required=True)
    reu.add_argument("--indice", type=int, default=0)
    reu.add_argument("--bbox", nargs=4, type=float, required=True, metavar=("X0", "Y0", "X1", "Y1"),
                     help="Página visible normalizada del original citado")
    reu.add_argument("--motivo", required=True)
    reu.add_argument("--fecha", required=True)
    reu.add_argument("--revisor", required=True)
    man = commands.add_parser("lectura-manual-extraccion", help="Alta manual de una lectura omitida, con evidencia")
    man.add_argument("--caso", required=True)
    man.add_argument("--extraccion", required=True)
    man.add_argument("--tipo", required=True)
    man.add_argument("--valor-json", required=True, help='Número (210) o cadena JSON ("GRAVA ARENOSA")')
    man.add_argument("--unidad", required=True)
    man.add_argument("--texto-fuente", required=True, help="Texto literal impreso")
    man.add_argument("--simbolo")
    man.add_argument("--archivo", required=True)
    man.add_argument("--pagina", type=int, required=True)
    man.add_argument("--bbox", nargs=4, type=float, required=True, metavar=("X0", "Y0", "X1", "Y1"))
    man.add_argument("--motivo", required=True)
    man.add_argument("--fecha", required=True)
    man.add_argument("--revisor", required=True)
    vig = commands.add_parser("vigencia-extraccion", help="Versiones descendientes y exportaciones superadas")
    vig.add_argument("--caso", required=True)
    vig.add_argument("--extraccion", required=True)
    mig = commands.add_parser("migrar-extraccion", help="Derivar versión 0.2.0 (tipos semánticos) sin alterar lecturas")
    mig.add_argument("--caso", required=True)
    mig.add_argument("--extraccion", required=True, help="ID de la versión 0.1.0")
    mig.add_argument("--origen", required=True, help="Quién propone las clasificaciones (declarado)")
    mig.add_argument("--propuestas", type=Path, help="JSON {propuestas: {C001: {tipo, valor, unidad, motivo}}, cobertura?: [...]}")
    exp = commands.add_parser("exportar-extraccion", help="Exportar solo candidatos revisados con su evidencia")
    exp.add_argument("--caso", required=True)
    exp.add_argument("--extraccion", required=True)
    plan = commands.add_parser("plan-modelado", help="Generar propuesta geométrica 3D sin ejecutar ETABS")
    plan.add_argument("--entrada", type=Path, required=True, help="Contrato draft2model.geometria, no extracción de lecturas")
    plan.add_argument("--salida", type=Path, required=True, help="Archivo JSON nuevo; no se sobrescribe")
    from .cli_vision import agregar_comandos, COMANDOS, ejecutar as ejecutar_vision
    agregar_comandos(commands)
    from .cli_geometria import agregar_comandos as agregar_geometria, COMANDOS as COMANDOS_GEOMETRIA, ejecutar as ejecutar_geometria
    agregar_geometria(commands)
    args = parser.parse_args(argv)
    root = Path(raiz) if raiz is not None else Path(__file__).resolve().parents[1] / "data" / "private"
    if args.command in COMANDOS:
        return ejecutar_vision(args, root)
    if args.command in COMANDOS_GEOMETRIA:
        return ejecutar_geometria(args, root)
    if args.command.endswith("-extraccion"):
        return _extracciones(args, root)
    if args.command == "plan-modelado":
        from .archivo_plan import generar_plan_archivo
        try:
            resultado = generar_plan_archivo(args.entrada, args.salida)
        except (ValueError, OSError, TypeError, OverflowError, RecursionError) as error:
            print(f"Plan no generado: {error}", file=sys.stderr)
            return 1
        data = resultado.datos
        print(f"Plan geométrico: {resultado.ruta}")
        print(f"  Estado de origen: {data['estado_origen']} | cobertura: {data['cobertura']}")
        print(f"  Superficies: {len(data['superficies'])} | omisiones: {len(data['omisiones'])}")
        for bloqueo in data['bloqueos']:
            print(f"  Bloqueo: {bloqueo}")
        print("  Propuesta geométrica; ejecutable_en_etabs: false. No se ejecutó análisis ni se otorgó aprobación.")
        return resultado.codigo
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
