"""Instalar wheels con hashes en un entorno nuevo y comprobar la demo sin red."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import struct
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheels',type=Path,required=True)
    parser.add_argument('--salida',type=Path,required=True,help='Carpeta nueva para entorno/logs/demo')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    if sys.platform!='win32' or sys.version_info[:2]!=(3,10) or struct.calcsize('P')!=8:
        raise ValueError('El lock comprobado requiere Windows x64 y CPython 3.10.')
    wheels=args.wheels.resolve();folder=args.salida.resolve()
    if not wheels.is_dir():raise ValueError('Carpeta de wheels ausente.')
    folder.mkdir(parents=True,exist_ok=False)
    (folder/'temporales').mkdir()
    env=dict(os.environ,TEMP=str(folder/'temporales'),TMP=str(folder/'temporales'),PYTHONIOENCODING='utf-8')
    checks=[]
    report={'fecha_utc':datetime.now(timezone.utc).isoformat(),'completa':False,'sin_red':True,
            'datos_sinteticos':True,'analisis_etabs':False,'vision_real':False,'comprobaciones':checks}
    def run(name,command):
        result=subprocess.run([str(v) for v in command],cwd=root,env=env,encoding='utf-8',errors='replace',
                              capture_output=True,timeout=180)
        log=folder/(name+'.log');log.write_text(result.stdout+result.stderr,encoding='utf-8')
        checks.append({'nombre':name,'comando':[str(v) for v in command],'codigo':result.returncode,'registro':str(log)})
        if result.returncode:raise RuntimeError('Falló '+name+'; consultar '+str(log))
    try:
        run('crear_entorno',[sys.executable,'-m','venv',folder/'v'])
        python=folder/'v/Scripts/python.exe'
        cfg=(folder/'v/pyvenv.cfg').read_text(encoding='utf-8')
        if 'include-system-site-packages = false' not in cfg:raise RuntimeError('Entorno no aislado.')
        run('instalar',[python,'-m','pip','install','--no-index','--find-links',wheels,'--require-hashes',
                        '-r',root/'requirements-win-py310.lock','--disable-pip-version-check'])
        run('dependencias',[python,'-m','pip','check'])
        run('arranque',[python,'-m','draft2model','--help'])
        run('demo',[python,'-m','draft2model','demo-integrada','--salida',folder/'demo'])
        run('verificar_demo',[python,'-m','draft2model','demo-integrada','--salida',folder/'demo','--verificar'])
        check=json.loads((folder/'verificar_demo.log').read_text(encoding='utf-8'))
        if check.get('correcta') is not True or check.get('corridas_completadas')!=6:
            raise RuntimeError('La demo no confirmó las seis corridas.')
        report.update(completa=True,entorno_aislado=True,corridas_completadas=6)
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as error:
        report['error']=str(error)
    finally:
        (folder/'verificacion.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(folder/'verificacion.json')
    return 0 if report['completa'] else 1


if __name__=='__main__':raise SystemExit(main())
