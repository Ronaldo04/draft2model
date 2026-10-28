"""Contrastar wheels locales con SHA256 de PyPI; emitir manifest nuevo."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile
from email.parser import BytesParser


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--carpeta',type=Path,required=True)
    parser.add_argument('--salida',type=Path,required=True)
    args=parser.parse_args()
    if args.salida.exists():raise ValueError('El manifest debe ser nuevo.')
    wheels=sorted(args.carpeta.glob('*.whl'))
    if not wheels:raise ValueError('No hay wheels.')
    result=[]
    for path in wheels:
        with ZipFile(path) as archive:
            names=[n for n in archive.namelist() if n.endswith('.dist-info/METADATA')]
            if len(names)!=1:raise ValueError('METADATA inválido.')
            metadata=BytesParser().parsebytes(archive.read(names[0]))
        name,version=metadata['Name'],metadata['Version']
        # Identificadores del paquete se validan antes de construir la URL.
        import re
        if not re.fullmatch(r'[A-Za-z0-9_.-]+',name or '') or not re.fullmatch(r'[A-Za-z0-9_.+!-]+',version or ''):
            raise ValueError('Identificador de paquete inválido.')
        url=f'https://pypi.org/pypi/{name}/{version}/json'
        with urlopen(url,timeout=30) as response:data=json.load(response)
        matches=[entry for entry in data['urls'] if entry['filename']==path.name]
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if len(matches)!=1 or matches[0]['digests']['sha256']!=digest or matches[0]['size']!=path.stat().st_size:
            raise ValueError('El wheel no coincide con la distribución oficial: '+path.name)
        result.append({'paquete':name,'version':version,'archivo':path.name,'sha256':digest,
                       'bytes':path.stat().st_size,'fuente_metadatos':url})
    output={'verificado_con_pypi':True,'wheels':result}
    with args.salida.open('x',encoding='utf-8') as file:json.dump(output,file,ensure_ascii=False,indent=2)
    print('Wheels verificados:',len(result))


if __name__=='__main__':main()
