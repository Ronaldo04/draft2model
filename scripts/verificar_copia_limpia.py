"""Verificar fuentes en una carpeta nueva sin tmp, expedientes ni entorno heredados."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, timezone


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python',type=Path,required=True,help='Python del entorno aislado ya instalado.')
    parser.add_argument('--salida',type=Path,required=True,help='Carpeta nueva para fuentes e informe.')
    parser.add_argument('--node',type=Path,help='Ejecutable Node.js para verificar las pruebas de interfaz de la copia.')
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    output=args.salida.resolve();python=args.python.resolve()
    if not python.is_file():raise ValueError('No existe el Python seleccionado.')
    output.mkdir(parents=True,exist_ok=False);source=output/'fuentes';source.mkdir()
    report={'fecha_utc':datetime.now(timezone.utc).isoformat(),'completa':False,
            'sin_red':True,'etabs_ejecutado':False,'python':str(python),'archivos_copiados':{}}
    def write_report():
        (output/'copia_limpia.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    try:
        folders=('draft2model','tests','scripts','examples','seguimiento','docs')
        for name in folders:
            if not (root/name).is_dir():raise ValueError('Falta carpeta de fuentes: '+name)
            shutil.copytree(root/name,source/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.pyo'))
        top_names=('requirements.txt','requirements-win-py310.lock','README.md','.gitignore',
                   'Control de avance.html','Abrir control de avance.cmd','Abrir revision de planos.cmd')
        for name in top_names:
            if not (root/name).is_file():raise ValueError('Falta recurso de distribución: '+name)
            shutil.copyfile(root/name,source/name)
        catalog=json.loads((source/'seguimiento/hitos.json').read_bytes())
        for milestone in catalog['milestones']:
            for criterion in milestone['criteria']:
                for name in criterion.get('check_files',[]):
                    file=(source/name).resolve()
                    if not file.is_relative_to(source) or not file.is_file():
                        raise ValueError('Distribución incompleta para '+criterion['id']+': '+name)
        report['archivos_copiados']={p.relative_to(source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(source.rglob('*')) if p.is_file()}
        assert not (source/'tmp').exists() and not (source/'data/private').exists()
        env=dict(os.environ,PYTHONIOENCODING='utf-8',TEMP=str(output),TMP=str(output))
        for name in ('PYTHONPATH','PYTHONHOME'):env.pop(name,None)
        probe="import json,sys,site,draft2model;print(json.dumps({'aislado':sys.prefix!=sys.base_prefix,'user_site':site.ENABLE_USER_SITE,'modulo':draft2model.__file__}))"
        checked=subprocess.run([str(python),'-c',probe],cwd=source,env=env,capture_output=True,text=True,encoding='utf-8',timeout=30,check=True)
        runtime=json.loads(checked.stdout);report['entorno']=runtime
        if not runtime['aislado'] or runtime['user_site'] or not Path(runtime['modulo']).resolve().is_relative_to(source):
            raise ValueError('El entorno o la fuente importada no están aislados.')
        temporaries=output/'t';temporaries.mkdir()
        command=[str(python),'scripts/verificar_proyecto.py','--salida','tmp/verificacion.json','--temporales',str(temporaries)]
        if args.node:command.extend(['--node',str(args.node.resolve())])
        result=subprocess.run(command,
            cwd=source,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=3600)
        (output/'ejecucion.log').write_text(result.stdout+result.stderr,encoding='utf-8')
        report['codigo']=result.returncode;verification=source/'tmp/verificacion.json'
        if verification.is_file():report['verificacion']=json.loads(verification.read_bytes())
        if result.returncode:raise RuntimeError('La verificación de la copia limpia falló; consultar ejecución e informe.')
        report['completa']=True
    except Exception as error:
        report['error']=str(error);write_report();raise
    write_report();print(output/'copia_limpia.json')


if __name__=='__main__':main()
