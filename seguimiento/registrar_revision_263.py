"""Actualizar revisión incremental sin cerrar brechas funcionales del goal."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
review=json.loads((root/'seguimiento/REVISION_ENTREGAS_263.json').read_bytes())
if not review['aceptado_incremental'] or review['aceptacion_global']:
    raise ValueError('No hay revisión incremental satisfactoria')
path=root/'seguimiento/claude_ruta/REVISIONES.json'
state=json.loads(path.read_bytes())
for item in review['entregas']:
    if item['id'] not in state['revisadas']:state['revisadas'].append(item['id'])
if not any(item['id']=='R263-01' for item in state['observaciones']):
    state['observaciones'].append({'id':'R263-01','prioridad':'revision_incremental','etapas':['06'],
        'hallazgo':'Snapshots258 con10/559archivos e integridad ZIP/logs correctos;7pruebas propias focales en snapshotOK1.795s. Portado262 posterior:helper idéntico,cambios estables,6pruebas propias en destinoOK9.260s. No acredita análisis ni masa nativa del piloto.',
        'evidencia':'seguimiento/REVISION_ENTREGAS_263.json',
        'criterio_aceptacion':'Aceptar integración de software revisada, conservar R249-02 hasta evidencia nativa y cierre general; seguir construcción09D/resultados/entrega final.'})
path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

metric=root/'seguimiento/claude_ruta/METRICAS_EXTRACCION_09.json'
data=json.loads(metric.read_bytes())
diag=json.loads((root/'seguimiento/DIAGNOSTICO_GEMINI_235.json').read_bytes())
recovery=json.loads((root/'seguimiento/REVISION_NORMATIVA_RECUPERACION_236.json').read_bytes())
row=next(x for x in data['extraccion_vision']['intentos'] if x['proveedor']=='gemini' and x['numero']==2)
record={'fecha_utc':datetime.now(timezone.utc).isoformat(),'archivo':str(metric.relative_to(root)),
    'sha256_revisado':hashlib.sha256(metric.read_bytes()).hexdigest(),
    'observado_en_metrica':row,'contraste':{'candidatos_crudos':diag['candidatos'],
        'adaptables_en_memoria':recovery['recuperacion_real_en_memoria']['candidatos'],
        'cuarentena':recovery['recuperacion_real_en_memoria']['cuarentena'],'persistido_segun_recibo236':recovery['persistido']},
    'correccion_requerida':'Separar fallo inicial de validación,71candidatos originales y59/12en recuperación local no persistida según236. No informar0candidatos ni cambiar el fallo histórico por éxito productivo. Revisar denominadores por etapa y no reenviarAPI.',
    'apis_remotas':0,'etabs':False}
(root/'seguimiento/REVISION_METRICAS_263.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'entregas_marcadas_revisadas':len(review['entregas']),'hallazgo_metricas':'Gemini2 crudos71/local59+12 sin persistencia236','goal_completo':False}))
