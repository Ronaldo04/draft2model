"""Adjuntar resultados observados al ZIP congelado, sin modificar sus fuentes."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import shutil

root=Path(__file__).resolve().parents[1]
work=root/'tmp/validacion_distribucion_306'
package=root/'entregas/AECODE_RC_306'
manifest=json.loads((package/'MANIFIESTO.json').read_text(encoding='utf-8'))
validation=json.loads((work/'verificacion.json').read_text(encoding='utf-8'))
state=json.loads((work/'estado.json').read_text(encoding='utf-8'))
assert state['codigo']==0 and state['fuentes_intactas']
assert validation['validacion_local_completa'] and validation['archivos_estables_durante_ejecucion']
assert not validation['bloqueos_entorno']
assert all(row['codigo']==0 and not row['omisiones'] for row in validation['comprobaciones'])
sha=lambda raw:hashlib.sha256(raw).hexdigest()
assert all(sha((work/'fuentes'/n).read_bytes())==h for n,h in manifest['archivos'].items())
evidence=package/'EVIDENCIAS';evidence.mkdir(exist_ok=True)
shutil.copyfile(work/'verificacion.json',evidence/'verificacion_global.json')
logs={}
for row in validation['comprobaciones']:
    source=work/'fuentes'/row['registro']
    target=evidence/(row['nombre']+'.log')
    shutil.copyfile(source,target)
    logs[target.name]=sha(target.read_bytes())
suite=(evidence/'suite.log').read_text(encoding='utf-8',errors='replace')
count,seconds=re.search(r'Ran (\d+) tests in ([\d.]+)s',suite).groups()
interface=(evidence/'interfaz.log').read_text(encoding='utf-8',errors='replace')
node=int(re.search(r'^# pass (\d+)',interface,re.M)[1])
summary={'fecha_utc':datetime.now(timezone.utc).isoformat(),'huella_fuentes':manifest['huella_fuentes'],
         'archivos':len(manifest['archivos']),'fuentes_intactas':True,
         'validacion_local_completa':True,'python_pruebas':int(count),'python_segundos':float(seconds),
         'frontend_pruebas':node,'omisiones':[],
         'entorno':'Entorno nuevo offline303 reutilizado; lock y wheels idénticos. No es una nueva instalación306.',
         'integridad_conjunto':'seguimiento/REVISION_CONJUNTO_306.json',
         'evidencias_sha256':{**logs,'verificacion_global.json':sha((evidence/'verificacion_global.json').read_bytes())},
         'qa306':'pendiente: apertura de resultados solicitada una vez en IAB18306',
         'descarga_real':'pendiente confirmación y archivo Chrome; no acreditada por API ni publicación',
         'etabs_nuevo_ejecutado_en_esta_suite':False,'aprueba_ingenieria':False,'goal_completo':False}
(package/'VALIDACION_LOCAL.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(root/'seguimiento/VALIDACION_DISTRIBUCION_306.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
note=package/'ESTADO_VALIDACION.md'
text=note.read_text(encoding='utf-8').replace('**Estado al crear esta nota: suite global306 en curso; QA final306 pendiente.**',
    '**Suite global306 terminada y revisada:1424pruebas Python en1107,104s y36de interfaz, sin omisiones;599fuentes intactas. QA final306 y descarga real pendientes.**')
note.write_text(text,encoding='utf-8')
print(json.dumps({k:summary[k] for k in ('python_pruebas','frontend_pruebas','fuentes_intactas','goal_completo')}))
