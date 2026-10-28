"""Verifica cuatro entregas pendientes y restaura la última completa, sin tocar producto."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

ROOT=Path(__file__).resolve().parent.parent
names=['04-f6bf94ddfcfa4e82a2c65a00ead643ea','06-1da89b0ce9d042a9a19ad1d7c320a289',
       '04-dd25d50b73964115939212915084f78d','06-26f220ab94c540b1abb7b8263ba44d10']
target=ROOT/'tmp/revision_codex_246'
target.mkdir(exist_ok=False)
proof=[]
for name in names:
    manifest=json.loads((ROOT/'entregas'/name/'manifiesto.json').read_text(encoding='utf-8'))
    archive=ROOT/manifest['snapshot']['ruta']
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==manifest['snapshot']['sha256']
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist())==set(manifest['archivos'])
        assert sum(i.file_size for i in z.infolist())<64*1024*1024
        for member,expected in manifest['archivos'].items():
            p=PurePosixPath(member)
            assert not p.is_absolute() and '..' not in p.parts and '\\' not in member
            data=z.read(member)
            assert hashlib.sha256(data).hexdigest()==expected
            if name==names[-1]:
                dest=target.joinpath(*p.parts)
                assert dest.resolve().is_relative_to(target.resolve())
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes(data)
    for member,expected in manifest['logs'].items():
        assert hashlib.sha256((ROOT/member).read_bytes()).hexdigest()==expected
    proof.append(dict(id=manifest['id'],fuentes=len(manifest['archivos']),logs=len(manifest['logs']),integridad='correcta'))
out=dict(snapshot='tmp/revision_codex_246',entregas=proof)
(ROOT/'seguimiento/INTEGRIDAD_ENTREGAS_246.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out))
