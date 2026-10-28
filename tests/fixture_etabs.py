"""Replay de evidencia sintética conservada; no conecta con ETABS ni rutas históricas."""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import zipfile

PAQUETE=Path(__file__).parent/'fixtures/etabs21_sintetico'


def extraer_evidencia(destino):
    destino=Path(destino)
    if destino.exists():raise ValueError('El destino de la fixture debe ser nuevo.')
    manifest=json.loads((PAQUETE/'manifest.json').read_bytes())
    raw=(PAQUETE/'evidencia.zip').read_bytes()
    if (manifest.get('datos_sinteticos') is not True
            or hashlib.sha256(raw).hexdigest()!=manifest.get('sha256_zip')):
        raise ValueError('El paquete de evidencia sintética está alterado.')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names=z.namelist();expected=manifest['archivos']
        if len(names)!=len(set(names)) or set(names)!=set(expected):
            raise ValueError('El inventario del paquete no coincide.')
        contents={}
        for name in names:
            path=PurePosixPath(name)
            if (path.is_absolute() or '..' in path.parts or '\\' in name
                    or any(':' in part for part in path.parts) or path.as_posix()!=name):
                raise ValueError('Ruta no permitida en la fixture.')
            data=z.read(name);item=expected[name]
            if len(data)!=item['bytes'] or hashlib.sha256(data).hexdigest()!=item['sha256']:
                raise ValueError('Evidencia distinta de su inventario: '+name)
            contents[name]=data
    destino.mkdir(parents=True)
    for name,data in contents.items():
        path=destino.joinpath(*PurePosixPath(name).parts)
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as f:f.write(data)
    return destino
