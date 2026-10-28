"""Restaura base08 + delta09 inmutables y contrasta inventario; no toca producto."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

ROOT=Path(__file__).resolve().parent.parent
target=ROOT/'tmp/revision_codex_243'
target.mkdir(exist_ok=False)
proof=[]
for relative in ('entregas/06-c54f77043471420fac2dc2a30cee5749/manifiesto.json',
                 'entregas/04-2f1d24d2ad4b4cdfa4ff49f12299268e/manifiesto.json'):
    manifest=json.loads((ROOT/relative).read_text(encoding='utf-8'))
    zipped=ROOT/manifest['snapshot']['ruta']
    assert hashlib.sha256(zipped.read_bytes()).hexdigest()==manifest['snapshot']['sha256']
    with zipfile.ZipFile(zipped) as z:
        assert set(z.namelist())==set(manifest['archivos'])
        for name,expected in manifest['archivos'].items():
            path=PurePosixPath(name)
            assert not path.is_absolute() and '..' not in path.parts and '\\' not in name
            data=z.read(name)
            assert hashlib.sha256(data).hexdigest()==expected
            dest=target.joinpath(*path.parts)
            assert dest.resolve().is_relative_to(target.resolve())
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(data)
    for name,expected in manifest['logs'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected
    proof.append(dict(id=manifest['id'],fuentes=len(manifest['archivos']),logs=len(manifest['logs']),integridad='correcta'))
(ROOT/'seguimiento/INTEGRIDAD_09A_243.json').write_text(json.dumps(dict(snapshot=str(target.relative_to(ROOT)),entregas=proof),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(proof))
