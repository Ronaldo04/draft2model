"""Integridad y foco de entrega de masa; registra el hallazgo de tipado separado."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

root=Path(__file__).resolve().parents[1]
identifier='b6d886c5244b4eb68307ff4f60284620'
manifest=json.loads((root/f'entregas/06-{identifier}/manifiesto.json').read_bytes())
out=root/'tmp/revision_entrega_266';out.mkdir(exist_ok=False)
source=out/'fuentes';source.mkdir()
archive=root/manifest['snapshot']['ruta']
sha=lambda b:hashlib.sha256(b).hexdigest()
if sha(archive.read_bytes())!=manifest['snapshot']['sha256']:raise ValueError('ZIP alterado')
with zipfile.ZipFile(archive) as z:
    if len(z.namelist())!=len(set(z.namelist())) or set(z.namelist())!=set(manifest['archivos']):raise ValueError('Inventario distinto')
    for name,digest in manifest['archivos'].items():
        p=(source/name).resolve()
        if not p.is_relative_to(source):raise ValueError('Ruta ZIP fuera del destino')
        raw=z.read(name)
        if sha(raw)!=digest:raise ValueError('Archivo alterado: '+name)
        p.parent.mkdir(exist_ok=True,parents=True);p.write_bytes(raw)
for name,digest in manifest['logs'].items():
    p=(root/name).resolve()
    if not p.is_relative_to(root) or sha(p.read_bytes())!=digest:raise ValueError('Log alterado')
temp=out/'temporales';temp.mkdir()
env=dict(os.environ,TEMP=str(temp),TMP=str(temp),PYTHONIOENCODING='utf-8')
for name in ('PYTHONPATH','PYTHONHOME','OPENAI_API_KEY','GEMINI_API_KEY','GOOGLE_API_KEY'):env.pop(name,None)
command=[sys.executable,'-B','-m','unittest','-q','tests.test_libro_masa_263.ContrasteNativoTests',
         'tests.test_libro_masa_263.LibroSinteticoTests.test_contribuciones_independientes',
         'tests.test_informe_masa_nativa_263.MasaNativaInformeTests']
completed=subprocess.run(command,cwd=source,env=env,capture_output=True,timeout=120)
(out/'focal.log').write_bytes(completed.stdout+completed.stderr)
bug=json.loads((root/'seguimiento/REPRODUCCION_MASA_BOOL_266.json').read_bytes())
matches=all(manifest['archivos'][name]==digest for name,digest in bug['fuentes'].items())
report={'fecha_utc':datetime.now(timezone.utc).isoformat(),'entrega_id':identifier,'archivos':len(manifest['archivos']),
    'integridad_zip_archivos_logs':True,'foco_codigo':completed.returncode,'log':'tmp/revision_entrega_266/focal.log',
    'log_sha256':sha((out/'focal.log').read_bytes()),'reproduccion_bool_corresponde_a_snapshot':matches,
    'estado':'revisado_con_hallazgo_de_tipado','aceptado_sin_hallazgos':False,'aceptacion_global':False,
    'hallazgo':'REPRODUCCION_MASA_BOOL_266.json:boolTrue es convertidoa1 por el adaptador antes del validador estricto',
    'limites':manifest.get('limitaciones',[]),'apis_remotas':0,'etabs':False}
with (root/'seguimiento/REVISION_ENTREGA_266.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
print(json.dumps({'integridad':True,'focal_codigo':completed.returncode,'snapshot_corresponde_a_repro':matches,
                  'aceptado_sin_hallazgos':False,'aceptacion_global':False}))
raise SystemExit(completed.returncode)
