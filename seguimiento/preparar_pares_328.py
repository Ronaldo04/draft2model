from pathlib import Path
import hashlib,json
from seguimiento.claude_ruta.preparacion_benchmark_311.recepcion_311 import recibir,sugerir
root=Path(__file__).resolve().parents[1];dest=root/'seguimiento/revision_antigravity_328'
refpath=dest/'referencia_asistida_328.json';ref=json.loads(refpath.read_bytes())
locked=json.loads((dest/'REFERENCIA_FIJADA_328.json').read_bytes())
assert hashlib.sha256(refpath.read_bytes()).hexdigest()==locked['sha256_referencia']
inv=json.loads((root/'seguimiento/claude_ruta/preparacion_benchmark_311/INVENTARIO_COHORTES_311.json').read_bytes())
kit=json.loads((root/'seguimiento/referencia_humana_308/fuentes.json').read_bytes())
receipt=recibir(ref,kit);receipt['revision_humana_realizada']=False
(dest/'recepcion_asistida.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
summary=[];text=[]
for c in inv['cohortes']:
 item=c.get('extraccion_previa_correccion')
 if not item:
  summary.append({'cohorte':c['cohorte'],'estado':'sin_extraccion_evaluable','estado_original':c['estado']});continue
 p=root/item['ruta'];assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256']
 ext=json.loads(p.read_bytes());proposal=sugerir(ref,ext,c['cohorte'])
 (dest/(c['cohorte']+'_sugerencias.json')).write_text(json.dumps(proposal,ensure_ascii=False,indent=2),encoding='utf-8')
 indexed={x['id']:x for x in ext['candidatos']}
 text.append('\nCOHORTE '+c['cohorte'])
 for o in ref['observaciones']:
  pairs=[x for x in proposal['sugerencias'] if x['observacion_id']==o['id']]
  if pairs:
   text.append(o['id']+' '+o['tipo']+' '+str(o['valor'])+' => '+json.dumps([{'candidato':x['candidato_id'],'valor':indexed[x['candidato_id']]['valor_propuesto'],'unidad':indexed[x['candidato_id']]['unidad'],'iou':x['iou_regiones'],'ev_r':x['indice_evidencia_referencia'],'ev_c':x['indice_evidencia_candidato'],'bbox':indexed[x['candidato_id']]['evidencia'][x['indice_evidencia_candidato']]['bbox_normalizada']} for x in pairs],ensure_ascii=False))
 summary.append({'cohorte':c['cohorte'],'candidatos':len(ext['candidatos']),'sugerencias':len(proposal['sugerencias']),'observaciones_con_sugerencia':33-len(proposal['observaciones_sin_candidato'])})
(dest/'LISTA_REVISION_PARES.txt').write_text('\n'.join(text),encoding='utf-8')
(dest/'RESUMEN_SUGERENCIAS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
