"""Revisión focal del paquete real de controles publicado; sin repetir la cadena de malla."""
from pathlib import Path
from datetime import datetime, timezone
import base64
import copy
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from draft2model.controles_analisis import validar_controles

case=ROOT/'data/private/pueblo-libre-002'
folder=case/'controles_analisis/f4d1eb0004804d499d369587ff44c85e'
tracked={}
def read(p):
    tracked[p]=p.read_bytes()
    return json.loads(tracked[p])
def sha(raw):return hashlib.sha256(raw).hexdigest()

meta=read(folder/'version.json');doc=read(folder/'controles.json')
assert sha(tracked[folder/'controles.json'])==meta['sha256_controles']
link=meta['vinculo'];run=case/'analisis_etabs'/link['corrida_analisis']
assert link['corrida_analisis']=='7203c79a3ece4438b36d267ba80f3c4b'
assert sha((run/'analizado.edb').read_bytes())==link['modelo']['sha256_edb']
assert sha((run/'aceptacion_analisis.json').read_bytes())==link['sha256_aceptacion_analisis']
read(case/'expediente.json');assert sha(tracked[case/'expediente.json'])==meta['expediente_sha256']
response_path=case/'lecturas_etabs'/link['lectura_id']/'respuesta.json'
response=read(response_path)
assert sha(tracked[response_path])==link['sha256_respuesta']==doc['declaracion']['sha256_respuesta']
assert base64.b64decode(doc['fuentes']['respuesta']['bytes_base64'],validate=True)==tracked[response_path]
assert validar_controles(doc,respuesta_bytes=tracked[response_path]) is True
controls={c['id']:c for c in doc['controles']}
modal=next(t['filas'] for t in response['datos']['tablas'] if t['clave']=='Modal Participating Mass Ratios')
last=max((r for r in modal if r['Case']=='MODAL-E030'),key=lambda r:int(r['Mode']))
for name,field in [('MOD-X','SumUX'),('MOD-Y','SumUY')]:
    assert controls[name]['valores']['acumulado']==float(last[field])
    assert controls[name]['valores']['minimo']==.9
    assert controls[name]['estado']=='satisfactorio' and float(last[field])>=.9
assert controls['EQ-CM']['estado']=='no_aplicable' and controls['EQ-CM']['motivos']
analysis=read(run/'respuesta.json')
solver=json.loads(base64.b64decode(doc['fuentes']['avisos_solver']['bytes_base64'],validate=True))
assert analysis['avisos']==solver['advertencias']==[]
assert solver['corrida_analisis']==link['corrida_analisis']
assert solver['sha256_edb']==link['modelo']['sha256_edb']
assert controls['SOLVER']['verificacion']=='declarada_no_verificada'
assert doc['aprueba_resultados'] is False and doc['revision_profesional_verificada'] is False
assert doc['conformidad_normativa']=='no_evaluada'
altered=copy.deepcopy(doc);altered['controles'][0]['valores']['acumulado']=1.0
try:validar_controles(altered,respuesta_bytes=tracked[response_path])
except ValueError:pass
else:raise AssertionError('Alteración de control aceptada.')
stable=all(p.read_bytes()==v for p,v in tracked.items());assert stable
report={'fecha_utc':datetime.now(timezone.utc).isoformat(),'controles':folder.name,'sha256_controles':meta['sha256_controles'],
        'analisis':link['corrida_analisis'],'lectura':link['lectura_id'],'fuentes_sha256':{str(p.relative_to(ROOT)):sha(v) for p,v in tracked.items()},
        'nucleo_recalculado':True,'alteracion_rechazada':True,'fuentes_estables':stable,
        'estados':{k:v['estado'] for k,v in controls.items()},'ultimo_modo':last['Mode'],'UX':last['SumUX'],'UY':last['SumUY'],
        'solver':'Lista vacía declarada coincide con respuesta de análisis conservada; no autentica todos los avisos internos de ETABS.',
        'limites':['Equilibrio CM no aplicable en este paquete: NO declarar equilibrio global verificado.','No repite verificar_analisis_aceptado ni aceptación web completa; revalida núcleo, bytes y enlaces focales.','No certifica normativa, seguridad o aprobación profesional.'],
        'etabs_ejecutado':False,'api_remota':False,'goal_completo':False}
(ROOT/'seguimiento/REVISION_CONTROLES_REALES_285.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ('nucleo_recalculado','alteracion_rechazada','fuentes_estables','estados','UX','UY')}))
