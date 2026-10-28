"""Medición experimental sobre referencia IA fijada; parejas revisadas visualmente por Codex."""
from pathlib import Path
from datetime import datetime,timezone
import copy,hashlib,json
from draft2model.evaluacion_vision import evaluar_lecturas
from draft2model.extraccion_preliminar import huella

root=Path(__file__).resolve().parents[1];base=root/'seguimiento/revision_antigravity_328';dest=base/'evaluaciones';dest.mkdir(exist_ok=True)
refpath=base/'referencia_asistida_328.json';ref=json.loads(refpath.read_bytes())
lock=json.loads((base/'REFERENCIA_FIJADA_328.json').read_bytes())
assert hashlib.sha256(refpath.read_bytes()).hexdigest()==lock['sha256_referencia']
inv=json.loads((root/'seguimiento/claude_ruta/preparacion_benchmark_311/INVENTARIO_COHORTES_311.json').read_bytes())
exposure={x['cohorte']:x for x in json.loads((base/'EXPOSICION_328.json').read_bytes())}
# Decisiones explícitas tras revisar los diez recortes de candidato y sus contextos.
decisions={
 'openai_1':[('AG-0013','C011',False,'Región situada sobre la viga; no muestra el rótulo VS.'),
             ('AG-0017','C021',True,'Título CORTE1-1 reconocible en su ubicación; primer carácter parcialmente cortado.'),
             ('AG-0018','C025',False,'No contiene la dimensión alternativa. La referencia es ambigua y se excluye de exactitud.')],
 'openai_3':[],
 'openai_4':[('AG-0020','C074',False,'Recorte no contiene el sufijo completo de la etiqueta Kg/m2.'),
             ('AG-0026','C070',True,'Cota .30 visible en la región del detalle de aligerado.'),
             ('AG-0027','C071',False,'Solo aparece el dígito final; no respalda .10 completa.'),
             ('AG-0028','C066',False,'Cota .05 cortada: no respalda el valor completo.'),
             ('AG-0029','C067',True,'Cota .12 visible en la sección de aligerado.'),
             ('AG-0032','C054',True,'Cota2.15 visible en planta TECHO CISTERNA; no equivale a altura de corte.')],
 'gemini_1':[('AG-0010','C032',True,'1.50 m. visible en nota de suelos.')]
}
summary=[];journal=[]
for c in inv['cohortes']:
 name=c['cohorte'];item=c.get('extraccion_previa_correccion')
 if not item:
  summary.append({'cohorte':name,'estado':'fallida_sin_extraccion_evaluable','candidatos':None});continue
 path=root/item['ruta'];assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256']
 ext=json.loads(path.read_bytes());scoped=copy.deepcopy(ref)
 eligible=set(exposure[name]['contextos_completos']);assert eligible
 scoped['observaciones']=[o for o in scoped['observaciones'] if o['evidencia'][0]['archivo_id'] in eligible]
 suggestion=json.loads((base/(name+'_sugerencias.json')).read_bytes())
 pairs=[]
 for oid,cid,correct,reason in decisions[name]:
  p=next(x for x in suggestion['sugerencias'] if x['observacion_id']==oid and x['candidato_id']==cid)
  pairs.append({k:p[k] for k in ('observacion_id','candidato_id','indice_evidencia_referencia','indice_evidencia_candidato')}|{'principal':True,'evidencia_correcta':correct})
  journal.append({'cohorte':name,'observacion':oid,'candidato':cid,'evidencia_correcta':correct,'motivo':reason})
 corr={'contrato':'draft2model.correspondencias_vision','version_contrato':'0.1.0','caso':ref['caso'],
       'huella_referencia':huella(scoped),'huella_extraccion':huella(ext),
       'revision':{'estado':'revisado','revisor_declarado':'Codex (IA), revisión visual asistida; no humana','fecha':'2026-10-24'},
       'pares':pairs,'sin_respaldo':[]}
 result=evaluar_lecturas(scoped,ext,corr)
 folder=dest/name;folder.mkdir(exist_ok=True)
 for filename,data in [('referencia.json',scoped),('extraccion_original.json',ext),('correspondencias.json',corr),('metricas.json',result)]:
  (folder/filename).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
 summary.append({'cohorte':name,'estado':'evaluacion_experimental_asistida','laminas_enviadas':sorted(eligible),
                 'candidatos':len(ext['candidatos']),'metricas':result['metricas'],
                 'evidencia_confirmada_sobre_emitidos':result['evidencia_confirmada_sobre_emitidos'],
                 'sin_clasificar':len(result['sin_clasificar'])})
report={'contrato':'seguimiento.benchmark_asistido_328','fecha_utc':datetime.now(timezone.utc).isoformat(),
 'revision_humana_realizada':False,'referencia_origen':'Antigravity IA revisado y corregido por Codex IA, excepción solicitada por usuario.',
 'fuente_referencia_fijada':lock,'observaciones_referencia_total':33,'observaciones_ambiguas':1,
 'peticiones_originales':6,'cohortes_con_extraccion_valida':4,'fallidas':2,'peticiones_nuevas':0,
 'criterio_pares':'Tipo, documento, página y ubicación física; revisión explícita. No se seleccionaron por igualdad del valor.',
 'criterio_ambito':'Solo observaciones en láminas de contexto efectivamente enviadas en cada cohorte. No sumar resultados de tareas distintas.',
 'cohortes':summary,'decisiones_pares':journal,
 'limites':['Referencia asistida por IA, no verdad humana independiente ni aprobación de ingeniería.',
            'Muestra parcial con taxonomía explícita: identificadores estructurales se anotaron como elemento; ejes y títulos como etiqueta. Discrepancias de tipo reducen emparejamientos.',
            'No clasificar como falsas todas las propuestas sin referencia en una muestra parcial.',
            'No hay umbral de aceptación comercial aprobado; una exactitud condicionada alta no demuestra cobertura ni automatización.',
            'Resultados previos a las correcciones geométricas del modelo. No confundir con la calidad del modelo final supervisado.']}
(base/'BENCHMARK_ASISTIDO_328.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps([{'cohorte':x['cohorte'],'cobertura':(x.get('metricas')or{}).get('cobertura'),'completas':(x.get('metricas')or{}).get('lecturas_completas_sobre_legibles')} for x in summary],ensure_ascii=False))
