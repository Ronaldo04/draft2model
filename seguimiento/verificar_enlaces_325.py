"""Integridad de enlaces locales en la documentación vigente del ZIP325."""
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse
import hashlib,json,posixpath,re,zipfile

root=Path(__file__).resolve().parents[1]
out=root/'entregas/AECODE_ENTREGA_325'
m=json.loads((out/'MANIFIESTO.json').read_bytes())
selected=('README.md','docs/GUIA_REPRODUCIBLE.md','docs/ENTREGA_AECODE.md','docs/RETOMAR.md',
          'docs/CONTEXTO_PROYECTO.md','docs/NORMATIVA_APLICADA.md','docs/EVALUACION_VISION.md',
          'docs/MATRIZ_REQUISITOS_REFERENCIA.md','docs/ESTIMACION_EXTREMOS_AUTO.md','docs/MASA_ENSAMBLADA.md')
count=0;missing=[]
with zipfile.ZipFile(out/'Draft2Model.zip') as z:
    assert hashlib.sha256((out/'Draft2Model.zip').read_bytes()).hexdigest()==m['zip_sha256']
    for name in selected:
        for target in re.findall(r'\]\((<[^>]+>|[^)\n]+)\)',z.read(name).decode('utf-8')):
            target=target.strip('<>');url=urlparse(target)
            if url.scheme or target.startswith('#'):continue
            resolved=posixpath.normpath(str(PurePosixPath(name).parent/unquote(url.path)))
            count+=1
            if resolved not in m['archivos']:missing.append([name,target])
result={'enlaces':count,'rotos':missing,'huella_fuentes':m['huella_fuentes']}
(root/'seguimiento/QA_ENLACES_325.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
assert not missing,missing
