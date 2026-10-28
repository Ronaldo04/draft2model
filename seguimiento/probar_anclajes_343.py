"""Ensayo local OCR+trazos del sistema en proyecto3; no escribe en el caso."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'tmp/desarrollo_geometria_337'))
from draft2model.anclajes_cotas import proponer_anclajes_pdf
from draft2model.ocr_local import reconocer_pagina_pdf

case=root/'data/private/vivienda-unifamiliar-003'
manifest=json.loads((case/'expediente.json').read_text(encoding='utf-8'))
extraction=case/'extracciones/edb0e7f4c1ac45fa91c2103f693ed2a4/extraccion.json'
reads=json.loads(extraction.read_text(encoding='utf-8'))
folder=root/'seguimiento/ANCLAJES_OCR_343'
folder.mkdir(exist_ok=True)
results=[]
for source in manifest['archivos']:
    started=time.monotonic()
    raw=(case/source['archivo']).read_bytes()
    digest=hashlib.sha256(raw).hexdigest()
    ocr_path=folder/(source['id']+'_ocr.json')
    if ocr_path.exists():
        ocr=json.loads(ocr_path.read_text(encoding='utf-8'))
        assert ocr['original_sha256']==digest
    else:
        ocr=reconocer_pagina_pdf(raw,1)
        ocr_path.write_text(json.dumps(ocr,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    try:
        result=proponer_anclajes_pdf(raw,1,source['id'],reads,ocr=ocr)
    except ValueError as error:
        result={'archivo_id':source['id'],'estado':'busqueda_no_realizada','causa':str(error),'lecturas':[]}
    result['duracion_segundos']=round(time.monotonic()-started,3)
    results.append(result)
    print(json.dumps({'archivo':source['id'],'palabras_ocr':len(ocr['palabras']),
       'segundos':result['duracion_segundos'],'estados':dict(Counter(r['estado'] for r in result['lecturas'])),
       'error':result.get('causa')},ensure_ascii=False),flush=True)
    (folder/'resultado.json').write_text(json.dumps({'fecha_utc':datetime.now(timezone.utc).isoformat(),
       'software':'desarrollo337+343; no entrega331','paginas':results,
       'finalizado':len(results)==len(manifest['archivos']),'nuevas_api':0,'modifica_expediente':False,
       'genera_modelo':False,'goal_completo':False},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
