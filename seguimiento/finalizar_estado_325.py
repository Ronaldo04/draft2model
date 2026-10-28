"""Cerrar el hito325 y dejar explícito el bloqueo de referencia independiente."""
from pathlib import Path
from datetime import datetime,timezone
import json,shutil
root=Path(__file__).resolve().parents[1];out=root/'entregas/AECODE_ENTREGA_325'
integrity=json.loads((root/'tmp/integridad_conjunto_325.json').read_text(encoding='utf-8-sig'))
links=json.loads((root/'seguimiento/QA_ENLACES_325.json').read_bytes())
assert integrity['estado']=='integridad_verificada_no_aceptacion_funcional' and not links['rotos']
p=out/'VALIDACION.json';v=json.loads(p.read_bytes());v.update(integridad_conjunto=integrity,enlaces_locales=links)
p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copyfile(p,root/'seguimiento/VALIDACION_DISTRIBUCION_325.json')
shutil.copyfile(root/'tmp/integridad_conjunto_325.json',out/'EVIDENCIAS/integridad_conjunto.json')
shutil.copyfile(root/'seguimiento/QA_ENLACES_325.json',out/'EVIDENCIAS/qa_enlaces.json')
p=root/'seguimiento/RETOMAR_CODEX_325.json';d=json.loads(p.read_bytes());now=datetime.now(timezone.utc).isoformat()
d.update(fecha_utc=now,estado_hito='325validado; referencia humanaP04 todavía ausente. SoloCodex.',
    distribucion_validada='entregas/AECODE_ENTREGA_325',guia='entregas/AECODE_ENTREGA_325/LEER_PRIMERO.md',
    evidencia_validacion='seguimiento/VALIDACION_DISTRIBUCION_325.json',
    advertencia='325:1471Python+36interfaz,5comprobaciones0,sin omisiones,609fuentes estables,82enlaces válidos.322preservado;323NOaceptado.',
    cuota={'restante5h_observado':8,'restante_semanal_observado':39,'reset_manual':'intacto'})
d['global325'].update(estado='terminal0',exec=None,exec_terminal=64009,codigo=0)
d['siguiente']=[
    'Referencia humanaP04ausente también tras este hito:Downloads/referencia_humana*.json y kit sin archivo. El usuario había prometido completarla. No inventar verdad ni métricas.',
    'Al recibir la ruta/JSON, recepción311, correspondencias revisadas por archivo/página/región/tipo (no por valores acertados) y métricas por cohortes originales. No repetir extracciones conservadas ni APIs.',
    'No repetir suites/perfiles/ETABS/informes322/325:todos terminaron. No trabajos de actividad aparente ni nuevas optimizaciones por sondear el bloqueo.',
    'Si se reanuda un goal bloqueado, iniciar auditoría fresca del bloqueo. Mantener soloCodex; no Claude/subagentes/modelomanual/proyectos2/3 hasta validar primero.',
    'Conservar límites:sinEMS,sin aprobación profesional,contrastebruto no_coherente,10comparaciones no satisfactorias,perfilAutoexperimental,latencia aún alta. No afirmar universalidad.'
]
d['auditoria_bloqueo']={'condicion':'Falta referencia humana independienteP04 y revisión de correspondencias; no existe JSON ni ruta entregada.',
    'turnos_consecutivos_con_condicion':['cierre322','diagnostico323','cierre325'],
    'independiente_completado':'Software integrado, suite1471+36, integridad, documentación, caso nativo322, consulta regenerada325 y optimización verificada. No quedan procesos críticos en curso.',
    'goal_completo':False}
p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
(root/'seguimiento/RETOMAR_ACTUAL.json').write_text(json.dumps({'checkpoint':'seguimiento/RETOMAR_CODEX_325.json','fecha_utc':now,'goal_completo':False},ensure_ascii=False,indent=2),encoding='utf-8')
print('Hito325 consolidado; bloqueo humanoP04 documentado, sin declarar objetivo logrado.')
