"""Recalcula los 13 indicadores del piloto desde filas CSI archivadas, sin motor."""
from pathlib import Path
from decimal import Decimal
import hashlib
import json
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[1]
case = root/'data/private/pueblo-libre-002'
result_id = '697bb37e9ce64f90ba1ef3e25733c8cc'
folder = case/'resultados_estructurales'/result_id
names = ('resultados.json','trazabilidad.json','mapeo.json','respuesta_puente.json','configuracion.json')
raw = {name:(folder/name).read_bytes() for name in names}
r,t,m,response,cfg = (json.loads(raw[name].decode('utf-8-sig')) for name in names)
sha = lambda data: hashlib.sha256(data).hexdigest()
native = case/'lecturas_analisis'/r['corrida_id']/'respuesta.json'
assert sha(raw['respuesta_puente.json']) == t['sha256_respuesta'] == m['sha256_respuesta'] == sha(native.read_bytes())
edb = case/t['modelo']['archivo']
assert sha(edb.read_bytes()) == t['modelo']['sha256']
tables = {row['clave']:row for row in response['datos']['tablas']}
selectors = {s['id']:s for s in m['selectores']}
traces = {s['resultado_id']:s for s in t['correspondencias']}
assert len(selectors) == len(traces) == len(r['resultados']) == 13
checks = []
for item in r['resultados']:
    s = selectors[item['id']]; trace = traces[item['id']]
    rows = tables[s['tabla']]['filas']
    matches = [(index,row) for index,row in enumerate(rows) if all(row.get(key)==value for key,value in s['filtros'].items())]
    assert len(matches)==1
    index,row = matches[0]
    assert trace['fila_indice']==index and trace['campo']==s['campo_valor'] and trace['filtros']==s['filtros']
    assert all(item[key]==s[key] for key in ('variable','caso','direccion','ubicacion'))
    factor = Decimal('0.001') if item['variable']=='cortante' and s['unidad_origen']=='N' else Decimal('1')
    assert Decimal(str(trace['factor']))==factor
    value = Decimal(str(row[s['campo_valor']]))*factor
    assert value==Decimal(str(item['valor']))
    checks.append({'id':item['id'],'tabla':s['tabla'],'fila':index,'campo':s['campo_valor'],'valor':str(value),'unidad':item['unidad']})
report = {'fecha_utc':datetime.now(timezone.utc).isoformat(),'resultado_id':result_id,
          'comprobaciones':checks,'lectura_fuente':r['corrida_id'],'sha256_edb':t['modelo']['sha256'],
          'fuentes_sha256':{n:sha(data) for n,data in raw.items()},
          'fuentes_estables':all((folder/n).read_bytes()==data for n,data in raw.items()),
          'alcance':'Valores normalizados iguales a filas unívocas de la misma respuesta nativa archivada y EDB por hash. No revalidación completa de aprobación/configuración, no nuevo análisis ni cumplimiento normativo.',
          'aprueba_ingenieria':False,'goal_completo':False}
assert report['fuentes_estables']
(root/'seguimiento/REVISION_NORMALIZACION_268.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'indicadores_coincidentes':len(checks),'fuentes_estables':True,'resultado':result_id}))
