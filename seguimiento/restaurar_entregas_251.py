"""Comprueba bytes de09D y extrae copia local. No ejecuta pruebas ni código extraído."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

ROOT=Path(__file__).resolve().parent.parent
names=['04-5b8365a8989f4fb7bc6574a730de2596','06-cd20a685e89b42b1888d5ec1d83d8095']
target=ROOT/'tmp/revision_codex_251'
target.mkdir(exist_ok=False)
proof=[]
for name in names:
    m=json.loads((ROOT/'entregas'/name/'manifiesto.json').read_text(encoding='utf-8'))
    archive=ROOT/m['snapshot']['ruta']
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==m['snapshot']['sha256']
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist())==set(m['archivos'])
        assert len(z.infolist())==len(m['archivos'])
        assert sum(i.file_size for i in z.infolist())<64*1024*1024
        for member, expected in m['archivos'].items():
            p=PurePosixPath(member)
            assert not p.is_absolute() and '..' not in p.parts and '\\' not in member and ':' not in member
            raw=z.read(member)
            assert hashlib.sha256(raw).hexdigest()==expected
            if name==names[-1]:
                dest=target.joinpath(*p.parts)
                assert dest.resolve().is_relative_to(target.resolve())
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes(raw)
    for member,expected in m['logs'].items():
        assert hashlib.sha256((ROOT/member).read_bytes()).hexdigest()==expected
    proof.append(dict(id=m['id'],fuentes=len(m['archivos']),logs=len(m['logs']),integridad='correcta'))
result=dict(snapshot='tmp/revision_codex_251',entregas=proof,ejecucion_codigo=False)
(ROOT/'seguimiento/INTEGRIDAD_ENTREGAS_251.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))
