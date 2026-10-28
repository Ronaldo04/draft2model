"""Correcciones visuales Codex sobre propuesta327, conservando originales y procedencia IA."""
from pathlib import Path
from datetime import date
import copy,hashlib,json
from draft2model.evaluacion_vision import validar_referencia
root=Path(__file__).resolve().parents[1];base=root/'seguimiento/ANTIGRAVITY_REFERENCIA_327'
dest=root/'seguimiento/revision_antigravity_328'
assert not (dest/'REFERENCIA_FIJADA_328.json').exists(), 'Referencia fijada: no modificarla después de consultar candidatos.'
proposal=json.loads((base/'salidas/referencia_propuesta_ia.json').read_bytes())
kit=json.loads((base/'entradas/fuentes.json').read_bytes())
patches={
 'AG-0012':[.161,.049,.175,.067], 'AG-0013':[.135,.073,.167,.082],
 'AG-0015':[.117,.116,.127,.126], 'AG-0016':[.410,.190,.426,.199],
 'AG-0017':[.710,.171,.750,.183], 'AG-0019':[.725,.125,.738,.136],
 'AG-0020':[.785,.409,.907,.438], 'AG-0021':[.461,.168,.475,.177],
 'AG-0024':[.407,.309,.429,.326], 'AG-0025':[.643,.185,.757,.202],
 'AG-0030':[.817,.3675,.831,.377], 'AG-0031':[.704,.708,.861,.731]
}
observations=[];changes=[];corrected=copy.deepcopy(proposal)
for o in corrected['observaciones']:
 before=copy.deepcopy(o)
 if o['id'] in patches:o['evidencia'][0]['bbox_normalizada']=patches[o['id']]
 if o['id']=='AG-0024':
  o['valor']='PL-9';o['nota']='Sustitución de referencia: PL-9 visible en la franja junto a escalera del cuarto nivel. La región propuesta no acreditaba PL-7.'
 if o['id']=='AG-0030':
  extra=copy.deepcopy(o['evidencia'][0]);extra['bbox_normalizada']=[.814,.354,.837,.366]
  o['evidencia'].append(extra)
 if o['id']=='AG-0032':o['nota']='Cota vertical en la planta TECHO CISTERNA; no se interpreta como altura libre del corte.'
 if o['id']=='AG-0031':
  o['valor']='DETALLE. MURO PORTANTE TIPICO'
  o['nota']='Título leído en el original vectorial: se conserva el punto tras DETALLE y se transcribe el espaciado tipográfico con un espacio.'
 if before!=o:changes.append({'id':o['id'],'antes':before,'despues':o,'criterio':'Inspección visual del original, sin consultar candidatos anteriores de los modelos.'})
 observations.append({k:copy.deepcopy(o[k]) for k in ('id','tipo','valor','unidad','legibilidad')} | {
  # El contrato vincula imagen_sha256 a un recorte registrado. Aquí son vistas
  # completas del kit: conservar sus SHA en el sidecar, sin inventar recortes.
  'evidencia':[{k:v for k,v in ev.items() if k in ('archivo_id','pagina','original_sha256','bbox_normalizada')} for ev in o['evidencia']]})
ref={'contrato':'draft2model.referencia_vision','version_contrato':'0.1.0','caso':kit['caso'],
 'procedencia':{'tipo':'expediente','descripcion':'Referencia asistida por Antigravity(IA), revisada visualmente por Codex(IA), por petición del usuario. NO es revisión humana ni aprobación de ingeniería.'},
 'alcance':kit['alcance'],'sistema_coordenadas':'pagina_visible_normalizada',
 'revision':{'revisor_declarado':'Codex (IA): revisión visual asistida, no humana','fecha':date(2026,10,24).isoformat(),'estado':'revisado'},
 'observaciones':observations}
validar_referencia(ref)
(dest/'propuesta_corregida_328.json').write_text(json.dumps(corrected,ensure_ascii=False,indent=2),encoding='utf-8')
(dest/'referencia_asistida_328.json').write_text(json.dumps(ref,ensure_ascii=False,indent=2),encoding='utf-8')
log={'revision_humana_realizada':False,'autor_propuesta':'Antigravity (IA)','revisor':'Codex (IA)',
 'fuentes_imagen':kit['paginas'],
 'observaciones':len(observations),'cambios':changes,'estado':'pendiente_confirmacion_visual_de_regiones_corregidas',
 'respuestas_modelos_benchmark_consultadas_antes_de_fijar_referencia':False,
 'sha256_referencia':hashlib.sha256((dest/'referencia_asistida_328.json').read_bytes()).hexdigest()}
(dest/'CAMBIOS_328.json').write_text(json.dumps(log,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'referencia_valida':True,'observaciones':len(observations),'observaciones_corregidas':len(changes),'revision_humana':False}))
