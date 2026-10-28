"""Actualizar seguimiento y evidencia de cierre del hito; no declara el goal logrado."""
from pathlib import Path
from datetime import datetime,timezone
import json,shutil

root=Path(__file__).resolve().parents[1];out=root/'entregas/AECODE_ENTREGA_322'
vpath=out/'VALIDACION.json';v=json.loads(vpath.read_bytes())
integrity=json.loads((root/'tmp/integridad_conjunto_322.json').read_text(encoding='utf-8-sig'))
v['integridad_conjunto']=integrity
flow=v['recorrido_real']
elapsed=(datetime.fromisoformat(flow['fin_utc'])-datetime.fromisoformat(flow['inicio_utc'])).total_seconds()
v['rendimiento_observado']={'recorrido_qa_pared_s':elapsed,
    'nota':'Incluye comprobaciones repetidas de evidencias, creación, incidencia del guion y reanudación de consulta. No es tiempo de modelado ni SLA.',
    'lectura_instancia_etabs_aproximada_s':46.4,
    'limitacion':'Las verificaciones del expediente real siguen siendo lentas; la suite no demuestra rendimiento interactivo para cualquier proyecto.'}
vpath.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copyfile(vpath,root/'seguimiento/VALIDACION_DISTRIBUCION_322.json')
shutil.copyfile(root/'tmp/integridad_conjunto_322.json',out/'EVIDENCIAS/integridad_conjunto.json')
p=root/'seguimiento/RETOMAR_CODEX_322.json';d=json.loads(p.read_bytes())
now=datetime.now(timezone.utc).isoformat()
d.update(fecha_utc=now,distribucion_validada='entregas/AECODE_ENTREGA_322',
         guia='entregas/AECODE_ENTREGA_322/LEER_PRIMERO.md',
         evidencia_validacion='seguimiento/VALIDACION_DISTRIBUCION_322.json',
         estado_hito='Software322 validado; goal global abierto. Solo Codex.',
         advertencia='322:608fuentes,1464Python+36interfaz,5comprobaciones0 ysinomisiones.312preservado como histórico.',
         qa_pdf='Seis páginas revisadas; SHA del PDF publicado idéntico al revisado. QA_PDF_AUTO_322.json.',
         rendimiento=v['rendimiento_observado'])
d['recorrido_real'].update(exec=None,exec_terminal=88113,codigo=0,estado='terminado',
    instruccion='88113terminó0;30753terminó1 porfirma del guion después de publicar. No repetir lectura/generación/consulta. Evidencia consolidada.')
d['siguiente']=[
    'No repetir suite, ETABS, generación ni consulta322: ya terminaron y están ligados a la huella del ZIP.',
    'Falta referencia humanaP04 prometida por el usuario. Comprobar solo la ruta/JSON que entregue o Downloads/referencia_humana.json; no inventar anotaciones.',
    'Al recibirla usar recepción311, revisar correspondencias y puntuar cohortes originales por separado. No nuevasAPI para repetir extracciones ya conservadas.',
    'La comparación ETABS manual sigue aplazada. No procesar proyectos2/3 hasta validar el primero.',
    'Conservar limitaciones: perfilAuto experimental, masa bruta no_coherente,10comparaciones no satisfactorias,sinEMS/sin aprobación profesional. No declarar soporte universal.',
    'Si no hay referencia ni cambio material, evitar GUI, nuevas pruebas y sondeos repetidos. Claude y heartbeat continúan fuera de ejecución.'
]
p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
(root/'seguimiento/RETOMAR_ACTUAL.json').write_text(json.dumps({'checkpoint':'seguimiento/RETOMAR_CODEX_322.json','fecha_utc':now,'goal_completo':False},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'hito':'322verificado','goal_completo':False,'pendiente_externo':'referencia humanaP04','recorrido_qa_pared_s':elapsed},ensure_ascii=False))
