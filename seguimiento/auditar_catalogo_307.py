"""Contraste del catálogo completo con la suite306, sin inventar revisiones humanas."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
from seguimiento.control import evaluate

root=Path(__file__).resolve().parents[1]
source=root/'tmp/validacion_distribucion_306/fuentes'
catalog=json.loads((source/'seguimiento/hitos.json').read_text(encoding='utf-8'))
manifest=json.loads((root/'entregas/AECODE_RC_306/MANIFIESTO.json').read_text(encoding='utf-8'))
v=json.loads((root/'tmp/validacion_distribucion_306/verificacion.json').read_text(encoding='utf-8'))
assert v['validacion_local_completa'] and v['archivos_estables_durante_ejecucion']
logs={r['nombre']:source/r['registro'] for r in v['comprobaciones']}
suite=logs['suite'].read_text(encoding='utf-8')
modules={}
for name,status in re.findall(r'^test\S+ \(([^)]+)\) \.\.\. (ok)\s*$',suite,re.M):
    filename=name.split('.')[0]+'.py'
    row=modules.setdefault(filename,{'passed':True,'count':0});row['count']+=1
files={}
for name,digest in manifest['archivos'].items():
    raw=(source/name).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==digest
    files[name]=hashlib.sha1(raw).hexdigest()  # Formato del controlador histórico, no sustituye SHA256 del ZIP.
reviews=json.loads((root/'seguimiento/evidencias.json').read_text(encoding='utf-8')).get('reviews',[])
result=evaluate(catalog,files,{'files':files,'modules':modules,'skipped':[],
    'finished':v['fecha_utc']},reviews)
result.update(fecha_utc=datetime.now(timezone.utc).isoformat(),huella_fuentes=manifest['huella_fuentes'],
    advertencia='Coincidencia con criterios del catálogo histórico, no porcentaje de terminación del goal. La suite acredita software; no acredita piloto ni revisión humana/ingeniería. Los pending históricos pueden estar desactualizados.',
    modulos_con_casos_contados=len(modules),pruebas_contadas=sum(x['count'] for x in modules.values()),
    goal_completo=False)
(root/'seguimiento/AUDITORIA_CATALOGO_307.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
pending=[{'id':c['id'],'titulo':c['title'],'estado':c['state'],'faltan_archivos':c['missing']}
    for m in result['milestones'] for c in m['criteria'] if c['state']!='verificado']
print(json.dumps({'criterios':result['total'],'coincidencia_automatica':result['done'],
                  'pruebas_contadas':result['pruebas_contadas'],'requieren_contraste':pending},ensure_ascii=False))
