"""Validar el ZIP323 exacto con el entorno offline303 y el mismo lock."""
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
package = ROOT/'entregas/AECODE_ENTREGA_323'
work = ROOT/'tmp/validacion_distribucion_323'
source = work/'fuentes'
manifest = json.loads((package/'MANIFIESTO.json').read_text(encoding='utf-8'))
old = json.loads((ROOT/'entregas/AECODE_RC_303/MANIFIESTO.json').read_text(encoding='utf-8'))
assert manifest['archivos']['requirements-win-py310.lock'] == old['archivos']['requirements-win-py310.lock']
assert {n:h for n,h in manifest['archivos'].items() if n.startswith('wheels/')} == {n:h for n,h in old['archivos'].items() if n.startswith('wheels/')}
sha = lambda raw:hashlib.sha256(raw).hexdigest()
assert sha((package/'Draft2Model.zip').read_bytes()) == manifest['zip_sha256']
source.mkdir(parents=True, exist_ok=False)
with zipfile.ZipFile(package/'Draft2Model.zip') as archive:
    assert len(archive.namelist()) == len(set(archive.namelist()))
    assert set(archive.namelist()) == set(manifest['archivos'])
    for name in archive.namelist():
        p=PurePosixPath(name)
        assert not p.is_absolute() and '..' not in p.parts and ':' not in name and '\\' not in name
        raw=archive.read(name)
        assert sha(raw)==manifest['archivos'][name]
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
python = ROOT/'tmp/validacion_distribucion_303/.venv/Scripts/python.exe'
args=[str(python),'scripts/verificar_proyecto.py','--salida',str(work/'verificacion.json'),
      '--temporales',str(ROOT/'tmp/t304')]
env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONNOUSERSITE='1')
for name in ('PYTHONPATH','PYTHONHOME'):env.pop(name,None)
state={'fecha_utc':datetime.now(timezone.utc).isoformat(),'estado':'global_en_curso',
       'entorno':'offline303 reutilizado; lock y wheels idénticos',
       'huella_fuentes':manifest['huella_fuentes'],'argv':args,'goal_completo':False}
def save():
    (work/'estado.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
with (work/'global.log').open('w',encoding='utf-8') as out:
    process=subprocess.Popen(args,cwd=source,env=env,stdout=out,stderr=subprocess.STDOUT)
    state['pid']=process.pid;save()
    code=process.wait(timeout=3700)
state['codigo']=code
state['fuentes_intactas']=all(sha((source/n).read_bytes())==h for n,h in manifest['archivos'].items())
state['estado']='terminado'
save()
print(json.dumps(state,ensure_ascii=False))
raise SystemExit(code or (0 if state['fuentes_intactas'] else 1))
