"""Comandos de preparación y registro visual locales, sin transporte de red."""
from pathlib import Path
import re
import sys

from PIL import Image

from . import entrada_vision as vision
from . import gestion_extraccion as gestion
from . import proveedor_openai as openai

COMANDOS = {'preparar-vision', 'preparar-openai', 'preparar-proveedor', 'registrar-respuesta-vision'}


def agregar_comandos(commands):
    pack = commands.add_parser('preparar-vision', help='Preparar imágenes comprobadas y prompt sin envío')
    pack.add_argument('--caso', required=True)
    pack.add_argument('--revision', required=True, help='ID de revisión documental (32 hexadecimales)')
    pack.add_argument('--recortes', nargs='+', required=True, help='IDs de recortes del caso')
    for nombre in ('preparar-openai', 'preparar-proveedor'):
        plan = commands.add_parser(nombre, help='Preparar plan de proveedor sin clave ni red')
        plan.add_argument('--caso', required=True)
        plan.add_argument('--solicitud', required=True, help='ID del paquete visual')
        plan.add_argument('--modelo', required=True, help='Identificador explícito; compatibilidad real pendiente')
        plan.add_argument('--max-tokens', type=int, default=4096)
        plan.add_argument('--detalle', choices=('low', 'high', 'auto'), default=None)
        if nombre == 'preparar-proveedor':
            plan.add_argument('--proveedor', choices=tuple(sorted(__import__('draft2model.politica_uso_ia', fromlist=['x']).PROVEEDORES_AUTORIZADOS)), required=True)
        else:
            plan.set_defaults(proveedor='openai')
    response = commands.add_parser('registrar-respuesta-vision', help='Adaptar una respuesta JSON local a lecturas pendientes')
    response.add_argument('--caso', required=True)
    response.add_argument('--solicitud', required=True)
    response.add_argument('--respuesta', type=Path, required=True)
    response.add_argument('--proveedor', required=True, help='Origen declarado, no autenticado')
    response.add_argument('--modelo', required=True)
    response.add_argument('--modo-prueba', action='store_true', help='Marcar datos sintéticos sin importarlos a versiones del caso')
    response.add_argument('--importar', action='store_true', help='Importar las lecturas adaptadas como versión pendiente')
    response.add_argument('--cuarentena', action='store_true',
                          help='0.2.0: recuperar candidatos válidos y apartar los inválidos con sus errores (no corrige nada)')


def _ruta(caso_dir, *parts):
    expected = caso_dir.joinpath(*parts)
    if expected.resolve() != expected:
        raise ValueError('Una carpeta o archivo del flujo visual está enlazado; no se usa.')
    return expected


def _id(identifier):
    if not isinstance(identifier, str) or not re.fullmatch(gestion.PATRON_VERSION, identifier):
        raise ValueError('Se requiere un ID de 32 caracteres hexadecimales, no una ruta.')
    return identifier


def ejecutar(args, raiz):
    """0: registro local completo; 1: precondición/error; 2: adaptación guardada sin importar."""
    try:
        folder = gestion.carpeta_caso(raiz, args.caso)
        if folder != Path(raiz).resolve() / args.caso:
            raise ValueError('El caso es un enlace o alias de otro expediente.')
        manifest = _ruta(folder, 'expediente.json')
        _ruta(folder, 'vision')
        if args.command == 'preparar-vision':
            revision = _ruta(folder, 'revision_documental', _id(args.revision), 'revision.json')
            if len(set(args.recortes)) != len(args.recortes):
                raise ValueError('No repitas IDs de recortes.')
            crops = [_ruta(folder, 'recortes', _id(identifier), 'recorte.json') for identifier in args.recortes]
            _ruta(folder, 'vision', 'solicitudes')
            output = vision.preparar_paquete(manifest, revision, crops)
            print('Paquete visual: ' + output.parent.name)
        else:
            request = _ruta(folder, 'vision', 'solicitudes', _id(args.solicitud), 'solicitud.json')
            if args.command in ('preparar-openai', 'preparar-proveedor'):
                proveedor = getattr(args, 'proveedor', 'openai')
                _ruta(folder, 'vision', 'planes_'+proveedor)
                output = openai.preparar_plan(manifest, request, modelo=args.modelo,
                                              max_tokens=args.max_tokens, detalle=args.detalle or ('auto' if openai.proveedores.obtener(proveedor).detalle_auto else 'high'), proveedor=proveedor)
                print('Plan '+('OpenAI' if proveedor == 'openai' else proveedor)+' sin envío: ' + output.parent.name)
                print('  No requiere clave. Modelo solicitado: ' + args.modelo)
            elif args.command == 'registrar-respuesta-vision':
                if args.modo_prueba and args.importar:
                    raise ValueError('--modo-prueba no admite --importar; los datos sintéticos no se importan como lecturas reales.')
                _ruta(folder, 'vision', 'respuestas')
                output = vision.registrar_respuesta(manifest, request, args.respuesta,
                                                    proveedor=args.proveedor, modelo=args.modelo,
                                                    modo_prueba=args.modo_prueba, cuarentena=args.cuarentena)
                print('Respuesta adaptada: ' + str(output))
                if args.importar:
                    try:
                        imported = gestion.importar_extraccion(raiz, args.caso, output)
                    except (ValueError, OSError, TypeError) as error:
                        print('La adaptación está guardada, pero no se importó: ' + str(error), file=sys.stderr)
                        print('Reintenta solo la importación local con importar-extraccion; no repitas el registro ni una llamada API.', file=sys.stderr)
                        return 2
                    print('Versión pendiente de revisión: ' + imported.identificador)
                if args.modo_prueba:
                    print('  SIMULACIÓN: procedencia y método sintéticos; sin importación al caso.')
                else:
                    print('  Origen declarado; este registro local no autentica al proveedor ni acredita una llamada API.')
            else:
                raise ValueError('Comando visual desconocido.')
        print('  Archivo: ' + str(output))
        print('Este comando no transmite imágenes. Lecturas y aprobación técnica pendientes de revisión.')
        return 0
    except (ValueError, OSError, KeyError, TypeError, OverflowError, RecursionError, Image.DecompressionBombError) as error:
        print('Operación visual no completada: ' + str(error), file=sys.stderr)
        return 1
