"""ETABS: preparar operaciones locales o ejecutarlas mediante una opción explícita."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from .adaptador_etabs import AdaptadorEtabs, ConfiguracionPuente, SolicitudPreparada, codigo_salida


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trabajo',type=Path,default=Path('tmp/etabs'),help='Carpeta de solicitudes y registros')
    parser.add_argument('--bloqueo',type=Path,help='Compartir este archivo entre todos los clientes de la instancia')
    parser.add_argument('--timeout',type=float,default=120)
    commands=parser.add_subparsers(dest='operacion',required=True)
    diag=commands.add_parser('diagnosticar',help='Consultar versión y modelo de la instancia')
    opening=commands.add_parser('abrir-copia',help='Copiar plantilla verificada a una carpeta nueva')
    opening.add_argument('--plantilla',type=Path,required=True);opening.add_argument('--sha256',required=True)
    opening.add_argument('--destino',type=Path,required=True,help='Carpeta nueva para la copia')
    opening.add_argument('--instancia',choices=('nueva','activa'),default='nueva')
    opening.add_argument('--reemplazar-modelo-activo',action='store_true')
    tables=commands.add_parser('leer-tablas',help='Leer resultados existentes; no analiza')
    tables.add_argument('--modelo',type=Path,required=True)
    tables.add_argument('--tabla',action='append',required=True)
    tables.add_argument('--caso',action='append',default=[]);tables.add_argument('--combinacion',action='append',default=[])
    save=commands.add_parser('guardar-como',help='Guardar el modelo abierto a un archivo nuevo')
    save.add_argument('--modelo',type=Path,required=True);save.add_argument('--destino',type=Path,required=True)
    for command in (diag,opening,tables,save):
        command.add_argument('--id-proceso',type=int)
        command.add_argument('--ejecutar',action='store_true',help='Llamar al puente ETABS; omitir solo prepara archivos')
    recovery=commands.add_parser('recuperar',help='Registrar comprobación externa tras timeout del motor')
    recovery.add_argument('--motor-inactivo',action='store_true',required=True)
    recovery.add_argument('--revisor',required=True);recovery.add_argument('--motivo',required=True)
    args=parser.parse_args(argv)
    try:
        work=args.trabajo.absolute();work.mkdir(parents=True,exist_ok=True)
        config=ConfiguracionPuente.real(work,bloqueo=args.bloqueo,timeout_s=args.timeout)
        adapter=AdaptadorEtabs(config)
        if args.operacion=='recuperar':
            path=adapter.confirmar_recuperacion(motor_inactivo_declarado=args.motor_inactivo,
                                                revisor_declarado=args.revisor,motivo=args.motivo)
            print(json.dumps({'recuperacion_declarada':True,'evidencia_archivada':str(path)},ensure_ascii=False))
            return 0
        extra={'solo_preparar':not args.ejecutar,'id_proceso':args.id_proceso}
        if args.operacion=='diagnosticar':result=adapter.diagnosticar(**extra)
        elif args.operacion=='abrir-copia':
            result=adapter.abrir_copia_plantilla(args.plantilla.absolute(),args.sha256,args.destino.absolute(),
                instancia=args.instancia,reemplazar_modelo_activo=args.reemplazar_modelo_activo,**extra)
        elif args.operacion=='leer-tablas':
            result=adapter.leer_tablas(args.modelo.absolute(),args.tabla,casos=args.caso,combinaciones=args.combinacion,**extra)
        else:result=adapter.guardar_como(args.modelo.absolute(),args.destino.absolute(),**extra)
        if isinstance(result,SolicitudPreparada):
            output={'modo':'preparado','operacion':result.operacion,'solicitud':str(result.solicitud),
                    'ejecuto_etabs':False,'artefactos':result.artefactos}
        else:
            output={'modo':result.modo_ejecucion,'operacion':result.operacion,'corrida':str(result.corrida),
                    'datos':result.datos,'avisos':result.avisos,'artefactos':result.artefactos}
        print(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False))
        return 0
    except (ValueError,RuntimeError,OSError,TypeError) as error:
        print(f'ETABS: {error}',file=sys.stderr)
        return codigo_salida(error)


if __name__=='__main__':raise SystemExit(main())
