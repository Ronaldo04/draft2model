"""Persistir avances comprobados259 sin atribuir aceptación del piloto."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
files = ('seguimiento/claude_ruta/recorrido_etabs_09t.py',
         'seguimiento/claude_ruta/validacion_etapas_255.py',
         'seguimiento/claude_ruta/test_recorrido_09t_256.py')
review = {'fecha_utc':datetime.now(timezone.utc).isoformat(),'responsable':'Codex',
    'archivos':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files},
    'prueba_focal':{'comando':'.venv/Scripts/python.exe -B seguimiento/claude_ruta/test_recorrido_09t_256.py -q',
                   'resultado':'16 pruebas OK, 0.230s'},
    'alcance':'Fusión del candidato seguro256 observada en runner actual, controles explícitos y salidas de fallo; sin ejecución nativa nueva',
    'aceptacion_global':False}
(root/'seguimiento/REVISION_RUNNER_259.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
qa = {'fecha_utc':datetime.now(timezone.utc).isoformat(),'huella_fuentes':'87f79d0511866223e1e51007e099474c3de9523fd7be5ec282736ba368f38fc2',
    'copia':'tmp/validacion_paquete_258/fuentes','revision_visual':True,'browser':'IAB',
    'observado':['Inicio visible sin expediente, formulario de ingreso y estados deshabilitados coherentes',
                 'Selección demo-integrada-sintetica responde y muestra condición de muestra provisional',
                 'No hay versiones de resultados en el selector de la demo: sus informes CLI no equivalen a resultados importados en la UI'],
    'limitaciones':['Inspección de inicio y selección, no recorrido web completo','No acredita piloto ni informe real'],
    'servidores_propios_cerrados':['28163','11213','12727'],
    'incidente':'Proceso en sandbox no alcanzable desde IAB; proceso host autorizado sí respondió. Sin cambiar políticas.',
    'apis_remotas':0,'etabs':False}
(root/'seguimiento/QA_VISUAL_DISTRIBUCION_259.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
path=root/'seguimiento/CLAUDE_ESTADO.json'
state=json.loads(path.read_bytes())
state['reserva_nuevos_archivos_258']['liberada_para_integracion']=True
state['reserva_nuevos_archivos_258']['evidencia_final']='seguimiento/REVISION_PAQUETE_258.json'
state['revision_relectura_259']='seguimiento/REVISION_RELECTURA_259.json'
state['revision_runner_259']='seguimiento/REVISION_RUNNER_259.json'
path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
path=root/'seguimiento/CONTINUACION_CLAUDE_253.md'
text=path.read_text(encoding='utf-8')
if 'Revisión propia259 terminada' not in text:
    text+='\n## Revisión propia259 terminada\n\nCodex recomparó los crudos persistidos09t4:10 comprobaciones propiasOK, mismos hashes EDB/solicitud/respuesta/expectativa, instancia nueva cerrada sin guardado,29416operaciones y0discrepancias/0incompletos. REVISION_RELECTURA_259.json. Es aceptación de esa relectura, no de cambios09d posteriores ni análisis/masaensamblada/hipótesis. Fusión del runner256 observada en archivos actuales y16pruebas propiasOK0.230s; REVISION_RUNNER_259.json. No repetir esos ensayos sin cambios. Codex terminó QA de inicio/selección de la distribución258; no hay prueba web integral ni informe real todavía. Reserva258 liberada para tu integración, sin nuevas ediciones de Codex en esos tres archivos. Continúa recorrido real y producto general conforme a las seis tareas.\n'
    path.write_text(text,encoding='utf-8')
print(json.dumps({'relectura':'recomparada','runner':'16pruebasOK','reserva258':'liberada','piloto_completo':False}))
