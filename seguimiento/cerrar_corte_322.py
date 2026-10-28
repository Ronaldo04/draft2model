"""Consolidar322 únicamente con suite terminada y recorrido nativo comprobado."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import shutil

root=Path(__file__).resolve().parents[1]
out=root/'entregas/AECODE_ENTREGA_322'
work=root/'tmp/validacion_distribucion_322'
state=json.loads((work/'estado.json').read_bytes())
validation=json.loads((work/'verificacion.json').read_bytes())
flow=json.loads((root/'seguimiento/FLUJO_AUTO_322.json').read_bytes())
manifest=json.loads((out/'MANIFIESTO.json').read_bytes())
assert state['estado']=='terminado' and state['codigo']==0 and state['fuentes_intactas'] is True
assert validation['comprobaciones'] and all(c['codigo']==0 and not c['omisiones'] for c in validation['comprobaciones'])
assert flow['estado']=='terminado' and flow['sha_edb_antes']==flow['sha_edb_despues']
ev=out/'EVIDENCIAS';ev.mkdir(exist_ok=True)
counts={}
for c in validation['comprobaciones']:
    p=work/'fuentes'/c['registro'];text=p.read_text(encoding='utf-8')
    shutil.copyfile(p,ev/(c['nombre']+'.log'))
    if c['nombre']=='suite':
        counts['python']=int(re.search(r'Ran (\d+) tests in',text)[1]);assert '\nOK\n' in text
    if c['nombre']=='interfaz':
        counts['interfaz']=int(re.search(r'# tests (\d+)',text)[1])
        assert all(int(re.search(r'# '+k+r' (\d+)',text)[1])==0 for k in ('fail','cancelled','skipped','todo'))
assert counts['python']>=1464 and counts['interfaz']==36, counts
shutil.copyfile(work/'verificacion.json',ev/'verificacion_global.json')
shutil.copyfile(root/'seguimiento/FLUJO_AUTO_322.json',ev/'recorrido_real_auto.json')
report=root/'data/private/pueblo-libre-002/informes'/flow['informe']
qa_path=root/'seguimiento/QA_PDF_AUTO_322.json'
qa=json.loads(qa_path.read_bytes())
assert qa['informe']==flow['informe'] and qa['inspeccion_visual']!='pendiente'
assert qa['sha256_pdf']==hashlib.sha256((report/'informe.pdf').read_bytes()).hexdigest()
qa.update(publicado=True,aceptacion_pendiente=None)
qa_path.write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copyfile(qa_path,ev/'qa_pdf_auto.json')
shutil.copyfile(root/'seguimiento/QA_ENLACES_322.json',ev/'qa_enlaces.json')
annex=out/'ANEXO_QA_AUTO';annex.mkdir(exist_ok=True)
hashes={}
for name in ('informe.json','informe.html','informe.pdf'):
    p=report/name;raw=p.read_bytes();hashes[name]=hashlib.sha256(raw).hexdigest()
    (annex/name).write_bytes(raw)
capture=root/'data/private/pueblo-libre-002/lecturas_etabs'/flow['lectura_id']
capture_out=annex/'lectura_nativa';capture_out.mkdir(exist_ok=True)
for name in ('solicitud.json','respuesta.json','registro.json','evidencia_analisis.json',
             'aceptacion_lectura.json','traza_lectura.jsonl'):
    raw=(capture/name).read_bytes();(capture_out/name).write_bytes(raw)
    hashes['lectura_nativa/'+name]=hashlib.sha256(raw).hexdigest()
receipt=root/'data/private/pueblo-libre-002/trabajos_lecturas'/flow['trabajo']/'aceptacion_web.json'
raw=receipt.read_bytes();(capture_out/'aceptacion_web.json').write_bytes(raw)
hashes['lectura_nativa/aceptacion_web.json']=hashlib.sha256(raw).hexdigest()
summary={'fecha_utc':datetime.now(timezone.utc).isoformat(),'huella_fuentes':manifest['huella_fuentes'],
    'archivos':len(manifest['archivos']),'global':counts,'omisiones':[], 'fuentes_estables':True,
    'entorno':'Instalación offline303 reutilizada, lock y wheels idénticos. No nueva instalación322.',
    'recorrido_real':flow,'anexo_qa_sha256':hashes,'goal_completo':False,
    'limites':['El anexo QA no sustituye el informe técnico con18evaluaciones del complemento303.',
               'Referencia humana y correspondencias pendientes; no hay precisión empírica acreditada.',
               'Se conservan el contraste bruto no_coherente, diez comparaciones no satisfactorias y la ausencia de EMS.',
               'Estimación experimental dentro de un perfil limitado; sin automatización universal ni aprobación profesional.']}
(out/'VALIDACION.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(root/'seguimiento/VALIDACION_DISTRIBUCION_322.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
old=root/'entregas/AECODE_ENTREGA_312'
audit=json.loads((old/'AUDITORIA_P01_P14.json').read_bytes());audit['fecha_utc']=summary['fecha_utc']
for c in audit['criterios']:
    if c['id']=='P05':c['evidencia_y_limite']=f"{counts['python']}pruebas Python y36de interfaz en322, sin omisiones; no equivale a revisión profesional de las entradas."
    if c['id']=='P08':c['evidencia_y_limite']='Modelo nativo conservado. Lectura integrada322 y estimación independiente opcional comprobadas; contraste bruto no_coherente y residuo CM explícitos. No aprueba ingeniería.'
(out/'AUDITORIA_P01_P14.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
md='# Auditoría P01–P14\n\n'+ '\n\n'.join('## '+c['id']+' · '+c['criterio']+'\n\n'+c['estado']+'. '+c['evidencia_y_limite'] for c in audit['criterios'])+'\n'
(out/'AUDITORIA_P01_P14.md').write_text(md,encoding='utf-8')
shutil.copyfile(old/'REFERENCIA_DATOS_Y_NORMATIVA.md',out/'REFERENCIA_DATOS_Y_NORMATIVA.md')
guide=(old/'LEER_PRIMERO.md').read_text(encoding='utf-8')
guide=guide.replace('600 archivos',str(len(manifest['archivos']))+' archivos')
start=guide.index('La distribución312 pasó');end=guide.index('## Instalar',start)
guide=guide[:start]+f"La distribución322 pasó **{counts['python']} pruebas Python y36de interfaz**, sin omisiones, con fuentes estables. Se reutilizó el entorno offline303 con lock/wheels idénticos. La lectura real322 y el informe opcional terminado se describen en VALIDACION.json.\n\nEl [anexo QA Auto](ANEXO_QA_AUTO/informe.html) demuestra la sección experimental integrada; conserva la discrepancia bruta y no sustituye el informe técnico con18evaluaciones del complemento303. No se consumieron APIs ni se recalculó el edificio en este recorrido.\n\n"+guide[end:]
guide=guide.replace('sin reconciliación independiente completa','con estimación independiente opcional322 dentro del perfil comprobado y residuo CM sin atribuir')
(out/'LEER_PRIMERO.md').write_text(guide,encoding='utf-8')
print(json.dumps({'estado':'software322_validado','global':counts,'goal_completo':False},ensure_ascii=False))
