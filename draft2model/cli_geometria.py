"""Comandos de versiones geométricas sobre `gestion_geometria`, sin red ni ETABS.

Códigos de retorno: 0 operación completa; 1 solicitud inválida (argumentos,
identificadores, rutas, JSON ilegible); 2 geometría o evidencia rechazada o una
versión que no supera la comprobación. En los rechazos no se guarda nada.
"""

import json
import sys
from pathlib import Path

from . import gestion_geometria as g
from .gestion_extraccion import carpeta_caso, json_desde_bytes

COMANDOS = {
    "migrar-geometria-superficies", "importar-geometria", "consultar-geometria", "comprobar-geometria", "revisar-geometria", "aprobar-geometria",
}

AVISO = (
    "Revisor declarado; su identidad y competencia no se verifican. Una aprobación registrada no certifica "
    "seguridad estructural ni aprueba planes, modelos o resultados derivados."
)

# Campos de texto que cada comando exige; se comprueban aquí para responder con código 1.
OBLIGATORIOS = {
    "migrar-geometria-superficies": ("huella_esperada", "motivo", "fecha", "revisor"),
    "revisar-geometria": ("propuesta", "motivo", "fecha", "revisor"),
    "aprobar-geometria": ("huella_esperada", "revisor", "fecha", "motivo", "alcance"),
}


def agregar_comandos(commands):
    imp = commands.add_parser("importar-geometria", help="Registrar un contrato draft2model.geometria como versión raíz")
    imp.add_argument("--caso", required=True)
    imp.add_argument("--entrada", type=Path, required=True, help="JSON draft2model.geometria en borrador")
    for nombre, ayuda in (("consultar-geometria", "Mostrar geometría, metadatos y comprobación de una versión"),
                          ("comprobar-geometria", "Volver a comprobar una versión y su cadena sin modificarla")):
        sub = commands.add_parser(nombre, help=ayuda)
        sub.add_argument("--caso", required=True)
        sub.add_argument("--geometria", required=True, help="ID de versión (32 hexadecimales)")
        sub.add_argument("--json", action="store_true", help="Imprimir el resultado completo en JSON")
        if nombre == "consultar-geometria":
            sub.add_argument("--salida", type=Path, help="Archivo JSON nuevo con el resultado; no se sobrescribe")
    rev = commands.add_parser("revisar-geometria", help="Guardar una geometría completa revisada como versión hija")
    rev.add_argument("--caso", required=True)
    rev.add_argument("--geometria", required=True, help="ID de la versión padre")
    rev.add_argument("--propuesta", type=Path, help="(obligatorio) JSON completo en borrador y aprobacion null")
    rev.add_argument("--motivo", help="(obligatorio)")
    rev.add_argument("--fecha", help="(obligatorio) AAAA-MM-DD")
    rev.add_argument("--revisor", help="(obligatorio) Declaración de quien revisa; no se verifica")
    mig = commands.add_parser("migrar-geometria-superficies", help="Crear hija v0.2 borrador de una geometría v0.1 comprobada")
    mig.add_argument("--caso", required=True)
    mig.add_argument("--geometria", required=True)
    for campo in ("huella-esperada", "motivo", "fecha", "revisor"):
        mig.add_argument("--" + campo, help="(obligatorio)")
    apr = commands.add_parser("aprobar-geometria", help="Registrar una aprobación explícita ligada a la huella esperada")
    apr.add_argument("--caso", required=True)
    apr.add_argument("--geometria", required=True, help="ID de la versión que se aprueba")
    apr.add_argument("--huella-esperada", help="(obligatorio) huella_contenido revisada (SHA256)")
    apr.add_argument("--revisor", help="(obligatorio) Declaración de quien aprueba; no se verifica")
    apr.add_argument("--fecha", help="(obligatorio) AAAA-MM-DD")
    apr.add_argument("--motivo", help="(obligatorio)")
    apr.add_argument("--alcance", help="(obligatorio) Qué se revisó, p. ej. 'Niveles, nodos y muros'")


def _caso(raiz, caso):
    carpeta = carpeta_caso(raiz, caso)
    if carpeta != Path(raiz).resolve() / caso:
        raise g.ErrorGestion("El caso es un enlace o alias de otro expediente.")


def _propuesta(ruta: Path):
    try:
        contenido = Path(ruta).read_bytes()
    except OSError as error:
        raise g.ErrorGestion(f"No se pudo leer la propuesta {Path(ruta).name}: {error}") from error
    return json_desde_bytes(contenido, Path(ruta).name)


def _imprimir(comp) -> None:
    print(f"  Comprobación: {'correcta' if comp.correcta else 'NO superada'}")
    for problema in comp.problemas:
        print(f"  Problema de evidencia: {problema}")
    print(f"  huella_contenido: {comp.huella_contenido}")
    print(f"  sha256_geometria: {comp.sha256_geometria}")
    print(f"  Expediente SHA256: {comp.expediente_sha256}")
    for original in comp.originales_verificados:
        print(f"  SHA256 comprobado: original {original['id']}")
    print(f"  Cadena: {' <- '.join(comp.cadena)}")
    validacion = comp.validacion
    if validacion:
        print(
            f"  Consistente: {validacion['consistente']} | disponible_para_modelado: "
            f"{validacion['disponible_para_modelado']} | datos sintéticos: {validacion['datos_sinteticos']}"
        )
        for faltante in validacion["faltantes"]:
            print(f"  Faltante: {faltante}")
        for bloqueo in validacion["bloqueos"]:
            print(f"  Bloqueo: {bloqueo}")


def _escribir_nuevo(ruta: Path, texto: str) -> None:
    try:
        with open(ruta, "x", encoding="utf-8") as archivo:  # nunca sobrescribe
            archivo.write(texto)
    except FileExistsError as error:
        raise g.ErrorGestion(f"La salida {ruta} ya existe; no se sobrescribe.") from error


def ejecutar(args, raiz) -> int:
    """Ejecuta un comando de COMANDOS con la raíz privada indicada."""
    try:
        faltan = [f"--{campo.replace('_', '-')}" for campo in OBLIGATORIOS.get(args.command, ())
                  if getattr(args, campo) is None]
        if faltan:
            raise g.ErrorGestion("Faltan argumentos obligatorios: " + ", ".join(faltan) + ".")
        _caso(raiz, args.caso)
        if args.command == "importar-geometria":
            resultado = g.importar_geometria(raiz, args.caso, args.entrada)
            print(f"Geometría registrada: {resultado.identificador}")
        elif args.command in ("consultar-geometria", "comprobar-geometria"):
            if args.command == "comprobar-geometria":
                comp = g.comprobar_version(raiz, args.caso, args.geometria)
                datos = comp.a_dict()
            else:
                consulta = g.consultar_version(raiz, args.caso, args.geometria)
                comp = consulta.comprobacion
                datos = {"caso": consulta.caso, "version_id": consulta.identificador,
                         "geometria": consulta.geometria, "metadatos": consulta.metadatos,
                         "comprobacion": comp.a_dict(), "aviso": g.AVISO}
            texto = json.dumps(datos, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
            if getattr(args, "salida", None) is not None:
                _escribir_nuevo(args.salida, texto)
            if args.json:
                sys.stdout.write(texto)
            else:
                print(f"Versión geométrica {args.geometria}: {'correcta' if comp.correcta else 'NO supera la comprobación'}")
                _imprimir(comp)
                if getattr(args, "salida", None) is not None:
                    print(f"  Resultado guardado en: {args.salida}")
                print(AVISO)
            if not comp.correcta:
                print("La versión no supera la comprobación; no la use como origen.", file=sys.stderr)
            return 0 if comp.correcta else 2
        elif args.command == "migrar-geometria-superficies":
            resultado = g.migrar_geometria_superficies(
                raiz, args.caso, args.geometria, huella_esperada=args.huella_esperada,
                motivo=args.motivo, fecha=args.fecha, revisor_declarado=args.revisor)
            print(f"Migración guardada: {resultado.identificador} (hija en borrador; padre {args.geometria} intacto)")
        elif args.command == "revisar-geometria":
            resultado = g.revisar_geometria(
                raiz, args.caso, args.geometria, _propuesta(args.propuesta),
                motivo=args.motivo, fecha=args.fecha, revisor_declarado=args.revisor,
            )
            print(f"Nueva versión geométrica: {resultado.identificador} (padre {args.geometria}, que no se modifica)")
            print("  Revisión en borrador y sin aprobación.")
        else:
            resultado = g.aprobar_geometria(
                raiz, args.caso, args.geometria, huella_esperada=args.huella_esperada,
                revisor_declarado=args.revisor, fecha=args.fecha, motivo=args.motivo, alcance_revision=args.alcance,
            )
            print(f"Aprobación registrada: {resultado.identificador} (sobre {args.geometria}, que no se modifica)")
        print(f"  Carpeta: {resultado.ruta}")
        _imprimir(resultado.comprobacion)
        print(AVISO)
        return 0
    except g.ErrorEvidencia as error:
        print(f"Operación rechazada; no se guardó nada. {error}", file=sys.stderr)
        return 2
    except (ValueError, OSError) as error:
        print(f"Operación no completada: {error}", file=sys.stderr)
        return 1
