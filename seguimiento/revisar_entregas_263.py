"""Revisión focal de snapshots258 y del portado262; sin ETABS ni APIs."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'tmp/revision_entregas_263'
OUT.mkdir(exist_ok=False)
SOURCE=OUT/'fuentes'
SOURCE.mkdir()
ids=('85895489a41a416593c2195f65f542dc','05696cd0914e4ff6a988540001e35c67')
review={'fecha_utc':datetime.now(timezone.utc).isoformat(),'aceptacion_global':False,'etabs':False,'apis_remotas':0,'entregas':[]}
def digest(raw):return hashlib.sha256(raw).hexdigest()
for identifier in ids:
    directory=ROOT/('entregas/06-'+identifier)
    manifest=json.loads((directory/'manifiesto.json').read_bytes())
    archive=(ROOT/manifest['snapshot']['ruta']).resolve()
    if not archive.is_relative_to(ROOT) or digest(archive.read_bytes())!=manifest['snapshot']['sha256']:
        raise ValueError('Snapshot no coincide con manifiesto')
    with zipfile.ZipFile(archive) as z:
        if len(z.namelist())!=len(set(z.namelist())) or set(z.namelist())!=set(manifest['archivos']):
            raise ValueError('Inventario ZIP incompleto o duplicado')
        for name,sha in manifest['archivos'].items():
            raw=z.read(name)
            if digest(raw)!=sha:raise ValueError('Archivo alterado: '+name)
            if identifier==ids[-1]:
                p=(SOURCE/name).resolve()
                if not p.is_relative_to(SOURCE):raise ValueError('Ruta de extracción fuera del destino')
                p.parent.mkdir(exist_ok=True,parents=True)
                p.write_bytes(raw)
    for name,sha in manifest['logs'].items():
        p=(ROOT/name).resolve()
        if not p.is_relative_to(ROOT) or digest(p.read_bytes())!=sha:raise ValueError('Log alterado')
    review['entregas'].append({'id':identifier,'archivos':len(manifest['archivos']),
                              'zip_sha256':manifest['snapshot']['sha256'],'integridad':True})

def run(label,command,cwd):
    temp=OUT/('temporales_'+label)
    temp.mkdir()
    env=dict(os.environ,TEMP=str(temp),TMP=str(temp),PYTHONIOENCODING='utf-8')
    for key in ('PYTHONPATH','PYTHONHOME','OPENAI_API_KEY','GEMINI_API_KEY','GOOGLE_API_KEY'):
        env.pop(key,None)
    result=subprocess.run(command,cwd=cwd,env=env,capture_output=True,timeout=180)
    log=OUT/(label+'.log')
    log.write_bytes(result.stdout+result.stderr)
    review[label]={'codigo':result.returncode,'log':str(log.relative_to(ROOT)),'sha256_log':digest(log.read_bytes())}
    return result.returncode==0

focal=[sys.executable,'-B','-m','unittest','-q',
    'tests.test_informe_contenido_261.InventarioInformeTests',
    'tests.test_contenido_liquidos_258.ContenidoTests.test_plan_lleva_inventario_ligado_a_sus_presiones',
    'tests.test_cotas_auxiliares_258.PlanTests']
snapshot_ok=run('focal_snapshot',focal,SOURCE)

# La adaptación portó el test a tests/; no debe escribir resultados en fuentes ni depender de tmp histórico.
names=('draft2model/reuso_preparacion.py','draft2model/modelo_estructural.py',
       'draft2model/operaciones_etabs.py','tests/test_reuso_preparacion_262.py')
before={name:digest((ROOT/name).read_bytes()) for name in names}
reuso_ok=run('focal_portado',[sys.executable,'-B','-m','unittest','tests.test_reuso_preparacion_262','-q'],ROOT)
after={name:digest((ROOT/name).read_bytes()) for name in names}
review['portado262']={'archivos':before,'fuentes_estables':before==after,
    'helper_igual_al_candidato':before[names[0]]==digest((ROOT/'tmp/reuso_preparacion_262/reuso_preparacion.py').read_bytes())}
review['aceptado_incremental']=snapshot_ok and reuso_ok and before==after
review['limites']=['No ejecución nativa ni piloto final','Portado262 es posterior a los snapshots258',
                  'Masa ensamblada sigue sin evidencia real','La prueba del informe usa contratos sintéticos']
with (ROOT/'seguimiento/REVISION_ENTREGAS_263.json').open('x',encoding='utf-8') as stream:
    json.dump(review,stream,ensure_ascii=False,indent=2)
print(json.dumps({'integridad':[x['archivos'] for x in review['entregas']],
                  'focal_snapshot':snapshot_ok,'focal_portado':reuso_ok,'estable':before==after,
                  'aceptado_incremental':review['aceptado_incremental'],'aceptacion_global':False}))
raise SystemExit(int(not review['aceptado_incremental']))
