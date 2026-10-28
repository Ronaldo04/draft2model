"""Valida una copia reubicada con runtime fijo. Sin ETABS, red ni cambios al caso."""
from pathlib import Path
import sys
import json
import hashlib
import time
from datetime import datetime,timezone

root=Path(__file__).resolve().parents[1]
runtime=root/'tmp/runtime_repro_269'
private=root/'tmp/anexo_reubicado_268'
sys.path.insert(0,str(runtime))
from draft2model import evidencia_analisis as ev, malla_preparacion as mp
assert Path(ev.__file__).resolve().is_relative_to(runtime.resolve())
assert Path(mp.__file__).resolve().is_relative_to(runtime.resolve())

case='pueblo-libre-002'
analysis=private/case/'analisis_etabs/7203c79a3ece4438b36d267ba80f3c4b'
result='697bb37e9ce64f90ba1ef3e25733c8cc'
manifest=json.loads((runtime/'RUNTIME_MANIFIESTO.json').read_text(encoding='utf-8'))
before={p.relative_to(private).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (private/case).rglob('*') if p.is_file()}
report={'fecha_utc':datetime.now(timezone.utc).isoformat(),'huella_runtime':manifest['huella_fuentes'],
        'caso':case,'raiz_reubicada':str(private),'pasos':[],
        'instalacion_nueva':False,'etabs_ejecutado':False,'api_remota':False,
        'aprueba_ingenieria':False,'goal_completo':False}

def save():
    (root/'seguimiento/REUBICACION_CASO_269.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

for name,fn in (
    ('analisis_aceptado',lambda:ev.verificar_analisis_aceptado(private,case,analysis)),
    ('resultado_normalizado_vinculado',lambda:ev.verificar_evidencia(private,case,result,analysis))):
    print('INICIO '+name,flush=True);t=time.perf_counter()
    try:
        output=fn()
        step={'paso':name,'estado':'verificado','segundos':time.perf_counter()-t,
              'sha256_salida':hashlib.sha256(json.dumps(output,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()}
    except Exception as exc:
        step={'paso':name,'estado':'no_verificado','segundos':time.perf_counter()-t,
              'tipo':type(exc).__name__,'error':str(exc)}
    report['pasos'].append(step);save();print(json.dumps(step,ensure_ascii=False),flush=True)

report['expediente_sin_cambios']=before=={
    p.relative_to(private).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
    for p in (private/case).rglob('*') if p.is_file()}
report['runtime_sin_cambios']=all(hashlib.sha256((runtime/n).read_bytes()).hexdigest()==digest
                                 for n,digest in manifest['archivos'].items())
report['cache']=mp.preparar_malla.cache_info()
report['estado']='verificado' if (all(s['estado']=='verificado' for s in report['pasos'])
                                 and report['expediente_sin_cambios'] and report['runtime_sin_cambios']) else 'requiere_correccion'
report['limites']='Verificación de evidencia archivada desde otra carpeta con dependencias instaladas existentes. No instalación nueva, relectura nativa en ruta nueva, reconstrucción del caso ni conformidad de ingeniería.'
save();print(json.dumps({k:report[k] for k in ('estado','expediente_sin_cambios','runtime_sin_cambios','cache')},ensure_ascii=False),flush=True)
raise SystemExit(0 if report['estado']=='verificado' else 1)
