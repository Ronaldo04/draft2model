"""Consolidar325 solo tras validar el ZIP, manteniendo la evidencia nativa322 separada."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re,shutil

root=Path(__file__).resolve().parents[1];out=root/'entregas/AECODE_ENTREGA_325'
work=root/'tmp/validacion_distribucion_325';old=root/'entregas/AECODE_ENTREGA_322'
state=json.loads((work/'estado.json').read_bytes());checks=json.loads((work/'verificacion.json').read_bytes())
assert state['estado']=='terminado' and state['codigo']==0 and state['fuentes_intactas'] is True
assert all(c['codigo']==0 and not c['omisiones'] for c in checks['comprobaciones'])
manifest=json.loads((out/'MANIFIESTO.json').read_bytes());previous=json.loads((old/'MANIFIESTO.json').read_bytes())
changed=sorted(n for n in set(manifest['archivos'])|set(previous['archivos']) if manifest['archivos'].get(n)!=previous['archivos'].get(n))
assert changed==sorted(['README.md','docs/ENTREGA_AECODE.md','docs/GUIA_REPRODUCIBLE.md',
                       'draft2model/particion_superficies.py','tests/test_cache_particiones_325.py']),changed
profile=json.loads((root/'seguimiento/PERFIL_MODELO_323_cache325.json').read_bytes())
assert profile['modelo']=='0f37271307b6449c89c458c60a1640c7' and profile['estado']=='pendiente'
assert not profile['etabs_abierto'] and not profile['red']
ev=out/'EVIDENCIAS';ev.mkdir(exist_ok=True);counts={}
for c in checks['comprobaciones']:
    p=work/'fuentes'/c['registro'];text=p.read_text(encoding='utf-8');shutil.copyfile(p,ev/(c['nombre']+'.log'))
    if c['nombre']=='suite':
        counts['python']=int(re.search(r'Ran (\d+) tests in',text)[1]);assert '\nOK\n' in text
    if c['nombre']=='interfaz':
        counts['interfaz']=int(re.search(r'# tests (\d+)',text)[1])
        assert all(int(re.search(r'# '+k+r' (\d+)',text)[1])==0 for k in ('fail','cancelled','skipped','todo'))
assert counts=={'python':1471,'interfaz':36},counts
shutil.copyfile(work/'verificacion.json',ev/'verificacion_global.json')
for name in ('PERFIL_MODELO_323.json','PERFIL_MODELO_323_cache325.json','COMPARACION_CACHE_325.json'):
    shutil.copyfile(root/'seguimiento'/name,ev/name)
for name in ('qa_pdf_auto.json','recorrido_real_auto.json'):
    shutil.copyfile(old/'EVIDENCIAS'/name,ev/(name.removesuffix('.json')+'_historico322.json'))
shutil.copytree(old/'ANEXO_QA_AUTO',out/'ANEXO_QA_AUTO',dirs_exist_ok=True)
old_v=json.loads((old/'VALIDACION.json').read_bytes())
assert all(hashlib.sha256((out/'ANEXO_QA_AUTO'/n).read_bytes()).hexdigest()==h for n,h in old_v['anexo_qa_sha256'].items())
summary={'fecha_utc':datetime.now(timezone.utc).isoformat(),'huella_fuentes':manifest['huella_fuentes'],
    'archivos':len(manifest['archivos']),'global':counts,'omisiones':[],'fuentes_estables':True,
    'cambios_frente322':changed,'entorno':'Offline303 reutilizado; lock y wheels idénticos. No nueva instalación325.',
    'perfil_consulta_real':profile,'comparacion':json.loads((root/'seguimiento/COMPARACION_CACHE_325.json').read_bytes()),
    'anexo_qa_sha256':old_v['anexo_qa_sha256'],'evidencia_nativa':'Recorrido322 conservado íntegro; no nueva ejecución ETABS, lectura nativa ni informe325.',
    'limites':['Una consulta por variante bajo perfil; mejora temporal modesta, sin SLA ni prueba de rendimiento universal.',
               'Verificaciones completas del expediente siguen siendo costosas.',
               'Benchmark humano pendiente; ausencia de EMS, contraste bruto no_coherente y diez comparaciones no satisfactorias conservados.',
               'No certifica ingeniería ni modelado validado de cualquier construcción.'],'goal_completo':False}
(out/'VALIDACION.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(root/'seguimiento/VALIDACION_DISTRIBUCION_325.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
audit=json.loads((old/'AUDITORIA_P01_P14.json').read_bytes());audit['fecha_utc']=summary['fecha_utc']
for c in audit['criterios']:
    if c['id']=='P05':c['evidencia_y_limite']='1471pruebas Python y36de interfaz del ZIP325, sin omisiones. No equivale a revisión profesional de entradas.'
    if c['id']=='P14':c['evidencia_y_limite']='Distribución325 validada. Cadena nativa322 conservada; consulta325 regenera y coteja el plan completo del mismo modelo. P04 pendiente; sin automatización universal acreditada.'
(out/'AUDITORIA_P01_P14.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'AUDITORIA_P01_P14.md').write_text('# Auditoría P01–P14\n\n'+'\n\n'.join('## '+c['id']+' · '+c['criterio']+'\n\n'+c['estado']+'. '+c['evidencia_y_limite'] for c in audit['criterios'])+'\n',encoding='utf-8')
shutil.copyfile(old/'REFERENCIA_DATOS_Y_NORMATIVA.md',out/'REFERENCIA_DATOS_Y_NORMATIVA.md')
guide=(old/'LEER_PRIMERO.md').read_text(encoding='utf-8').replace('608 archivos','609 archivos')
start=guide.index('La distribución322 pasó');end=guide.index('## Instalar',start)
guide=guide[:start]+('La distribución325 pasó **1471 pruebas Python y36de interfaz**, sin omisiones, con609fuentes estables. '
    'Se reutilizó el entorno offline303 con lock/wheels idénticos. La reutilización de particiones mantiene verificación completa de fuente, límites de memoria y copias independientes.\n\n'
    'Una consulta regeneró y cotejó íntegramente el plan del piloto; bajo perfil pasó de205,39a195,45s. Es una observación puntual, sin SLA ni velocidad garantizada para otros proyectos. Las verificaciones siguen siendo lentas.\n\n'
    'El [anexo QA Auto](ANEXO_QA_AUTO/informe.html) y su lectura nativa corresponden a322 y se conservan byte por byte. No hubo una nueva corrida, lectura ETABS ni generación de informe325. El anexo no sustituye el informe técnico con18evaluaciones del complemento303.\n\n')+guide[end:]
(out/'LEER_PRIMERO.md').write_text(guide,encoding='utf-8')
print(json.dumps({'hito':'software325_validado','global':counts,'goal_completo':False},ensure_ascii=False))
