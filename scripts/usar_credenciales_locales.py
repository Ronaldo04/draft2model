"""Comprobar presencia o arrancar revisión local heredando claves del Markdown privado."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from draft2model.credenciales_locales import cargar, estado


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archivo',type=Path,default=ROOT/'data/private/credenciales.local.md')
    p.add_argument('--comprobar',action='store_true',help='Solo presencia; sin red, saldo, autenticación ni mostrar claves')
    p.add_argument('--raiz',type=Path,default=ROOT/'data/private')
    p.add_argument('--puerto',type=int,default=8777)
    args=p.parse_args(argv)
    try:
        values=cargar(args.archivo)
    except (ValueError,OSError):
        print('No se pudo cargar el archivo privado: revise formato, tamaño y ruta. No se muestran valores.',file=sys.stderr)
        return 1
    if args.comprobar:
        print(json.dumps({'presencia_en_archivo':estado(values),'autenticacion_comprobada':False,'envio_realizado':False}))
        return 0
    env=dict(os.environ);env.update(values)
    # Sin shell, evaluación, persistencia en el entorno del usuario o transcripciones.
    return subprocess.call([sys.executable,'-m','draft2model.revision_visual',
        '--raiz',str(args.raiz),'--puerto',str(args.puerto)],env=env,cwd=ROOT)


if __name__=='__main__':
    raise SystemExit(main())
