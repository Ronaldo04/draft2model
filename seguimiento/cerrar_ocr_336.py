"""Consolidar el OCR verificado como desarrollo aislado, sin cambiar331."""
import hashlib
import json
from pathlib import Path
import re
import zipfile
from datetime import datetime,timezone

root=Path(__file__).resolve().parents[1]
base=root/'tmp/validacion_ocr_335'
source=root/'tmp/desarrollo_ocr_333'
state=json.loads((base/'estado.json').read_text(encoding='utf-8'))
report=json.loads((base/'verificacion.json').read_text(encoding='utf-8'))
assert state['estado']=='terminado' and state['codigo']==0 and state['fuentes_intactas'] and state['entrega331_intacta']
assert report['validacion_local_completa'] and report['archivos_estables_durante_ejecucion']
assert all(c['codigo']==0 and not c['omisiones'] for c in report['comprobaciones'])
suite=next(c for c in report['comprobaciones'] if c['nombre']=='suite')
count=int(re.search(r'Ran (\d+) tests',(source/suite['registro']).read_text(encoding='utf-8')).group(1))
archive=base/'Fuentes_OCR_335.zip'
assert not archive.exists(),'Conservar instantánea ya verificada.'
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
 for name,digest in sorted(state['archivos'].items()):
  raw=(source/name).read_bytes()
  assert hashlib.sha256(raw).hexdigest()==digest
  info=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
  z.writestr(info,raw)
with zipfile.ZipFile(archive) as z:
 assert set(z.namelist())==set(state['archivos'])
 for name,digest in state['archivos'].items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
result={'fecha_utc':datetime.now(timezone.utc).isoformat(),'python':count,'interfaz':36,'omisiones':[],
        'archivos':len(state['archivos']),'fuentes_estables':True,
        'instantanea':str(archive.relative_to(root)),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
        'registro':'tmp/validacion_ocr_335/verificacion.json','entrega331_intacta':True,
        'estado':'desarrollo_aislado_verificado_no_publicado','goal_completo':False}
(root/'seguimiento/VALIDACION_OCR_336.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
checkpoint=json.loads((root/'seguimiento/RETOMAR_CODEX_335.json').read_text(encoding='utf-8'))
checkpoint.update(fecha_utc=result['fecha_utc'],anterior='seguimiento/RETOMAR_CODEX_335.json',
                  estado_hito='OCR aislado335 validado, instantánea guardada; diagnóstico de conversión336 verificado.')
checkpoint['global335'].update(estado_al_guardar='terminal0',codigo=0,resultado=result)
checkpoint['desarrollo_ocr_333']['estado']='integracion_aislada_verificada_no_publicada'
checkpoint['diagnostico_conversion336']={
 'registro':'seguimiento/DIAGNOSTICO_CONVERSION_336.json',
 'evidencia':'conversion_geometria.py declara correspondencias/ejes/coordenadas por operador; no interpreta píxeles ni conectividad.',
 'primera_lamina':'34palabras vectoriales y48444segmentos;9ejesxdetectados;sin cotas vectoriales de escala;ejey2insuficiente.',
 'siguiente_criterio':'Propuesta genérica de calibración/geométrica desde OCR/vector, con unidades declaradas, sin coordenadas hardcodeadas ni calibración contra ETABS.',
 'aceptacion_humana':'La anotación IA328 fue autorizada por el usuario; no solicitar otra vez el anotador humano como condición del software. Comparación manual sigue aplazada.'}
checkpoint['siguiente']=[
 'Mantener331 y anexo334 para presentación; no sustituir ni modificar sus archivos antes del deadline comunicado15:15Lima.',
 '93306 terminó0;1515Python+36interfaz, sin omisiones y620fuentes estables. No repetir la suite ni reabrir ese proceso.',
 'Conservar Fuentes_OCR_335.zip como evidencia inmutable; no atribuir su funcionalidad a la entrega331.',
 'Próximo desarrollo en otra copia aislada: calibración y propuesta de geometría a partir de evidencia OCR/vectorial, unidades explícitas y abstención por ambigüedad. No limitar el avance a localización de rótulos.',
 'Pendiente antes de distribuir OCR: revisión visual de interfaz real y documentación histórica de README/contexto acorde al nuevo corte. No hacer pasar referencia IA por humana.',
 'Sin APIs, claves, Claude, subagentes, nuevos proyectos2/3 ni modelo manual. El objetivo global permanece abierto.'
]
for name,value in [('RETOMAR_CODEX_336.json',checkpoint),('RETOMAR_ACTUAL.json',
 {'checkpoint':'seguimiento/RETOMAR_CODEX_336.json','fecha_utc':result['fecha_utc'],'goal_completo':False})]:
 (root/'seguimiento'/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
