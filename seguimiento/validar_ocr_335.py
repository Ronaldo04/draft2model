"""Única validación completa de la integración OCR aislada; no publica ni integra331."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime,timezone

root=Path(__file__).resolve().parents[1]
source=root/'tmp/desarrollo_ocr_333'
base=root/'tmp/validacion_ocr_335'
assert not base.exists(),'No reiniciar una validación existente.'
previous=json.loads((root/'tmp/validacion_distribucion_331/estado.json').read_text(encoding='utf-8'))
assert previous['estado']=='terminado' and previous['codigo']==0
base.mkdir()
manifest=json.loads((root/'entregas/AECODE_PRESENTACION_331/software/MANIFIESTO.json').read_text(encoding='utf-8'))
paths=sorted(set(manifest['archivos'])|{'draft2model/ocr_local.py','tests/test_ocr_local.py',
                                    'tests/test_cache_ocr_local.py','docs/OCR_LOCAL.md'})
before={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in paths}
delivery=json.loads((root/'seguimiento/ENTREGA_ACADEMICA_331_FINAL.json').read_text(encoding='utf-8'))
assert hashlib.sha256((root/delivery['archivo']).read_bytes()).hexdigest()==delivery['sha256']
state={'fecha_utc':datetime.now(timezone.utc).isoformat(),'estado':'en_ejecucion','pid':os.getpid(),
       'fuentes':str(source.relative_to(root)),'archivos':before,'goal_completo':False,
       'publicado':False,'entrega331_modificada':False,'focales_python':60,'focales_interfaz':36,
       'ensayo_real':'seguimiento/FLUJO_OCR_LOCAL_335.json','api_calls':0,'nuevo_etabs_nativo':False}
def save():
 (base/'estado.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
save()
python=root/'tmp/i334/v/Scripts/python.exe'
args=[str(python),'-X','utf8','scripts/verificar_proyecto.py','--salida',str(base/'verificacion.json'),
      '--temporales',str(root/'tmp/t304')]
state['argv']=args;save()
with (base/'ejecucion.log').open('w',encoding='utf-8') as log:
 result=subprocess.run(args,cwd=source,stdout=log,stderr=subprocess.STDOUT)
state.update(estado='terminado',codigo=result.returncode,
             fuentes_intactas=all(hashlib.sha256((source/p).read_bytes()).hexdigest()==h for p,h in before.items()),
             entrega331_intacta=hashlib.sha256((root/delivery['archivo']).read_bytes()).hexdigest()==delivery['sha256'])
save()
print(json.dumps({k:v for k,v in state.items() if k not in ('archivos','argv')},ensure_ascii=False))
raise SystemExit(result.returncode)
