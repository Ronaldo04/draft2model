"""Prueba local del detector en los originales, sin modificar el expediente."""
import collections
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'tmp/desarrollo_geometria_337'))
from draft2model.anclajes_cotas import proponer_anclajes_pdf

case=root/'data/private/vivienda-unifamiliar-003'
manifest=json.loads((case/'expediente.json').read_text(encoding='utf-8'))
extraction=case/'extracciones/edb0e7f4c1ac45fa91c2103f693ed2a4/extraccion.json'
reads=json.loads(extraction.read_text(encoding='utf-8'))
out=root/'seguimiento/ANCLAJES_PROYECTO3_342.json'
if out.exists():raise SystemExit('Resultado existente: no sobrescribir ni repetir sin cambios.')
results=[]
for source in manifest['archivos']:
    raw=(case/source['archivo']).read_bytes()
    try:
        results.append(proponer_anclajes_pdf(raw,1,source['id'],reads))
    except ValueError as error:
        results.append({'archivo_id':source['id'],'estado':'busqueda_no_realizada',
                        'causa':str(error),'lecturas':[]})
counts=collections.Counter(r['estado'] for p in results for r in p['lecturas'])
report={'fecha_utc':datetime.now(timezone.utc).isoformat(),'software':'desarrollo aislado337+342, no entrega331',
        'datos':'originales proyecto3 y extracción existente; sin completar coordenadas ni revisiones',
        'resumen':dict(counts),'paginas':results,'nueva_api':False,'nueva_geometria':False,
        'cambio_expediente':False,'goal_completo':False}
out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'registro':str(out.relative_to(root)),'resumen':dict(counts),
                  'paginas_no_procesadas':[p['archivo_id'] for p in results if p.get('causa')]},ensure_ascii=False))
