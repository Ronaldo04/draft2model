"""Registrar revisión309, contraste independiente y encargo310 sin tocar producto."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import pymupdf

root=Path(__file__).resolve().parents[1]
now=datetime.now(timezone.utc).isoformat()
def load(name):return json.loads((root/name).read_text(encoding='utf-8'))
def save(name,data):(root/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
sha=lambda raw:hashlib.sha256(raw).hexdigest()
marker=load('seguimiento/claude_ruta/MARCADOR_PDF_309.json')
entries=marker['archivos_permitidos_sha256']
assert all(name.startswith('seguimiento/claude_ruta/diagnostico_pdf_309/') and sha((root/name).read_bytes())==h for name,h in entries.items())
pdf=root/'tmp/recorrido_09d3/resultados/informe/informe.pdf'
assert sha(pdf.read_bytes())==marker['pdf_auditado']['sha256']
same={}
for page in (7,8):
    with pymupdf.open(pdf) as doc:pix=doc[page-1].get_pixmap(dpi=96)
    recorded=pymupdf.Pixmap(str(root/f'seguimiento/claude_ruta/diagnostico_pdf_309/renders/mupdf_aislado_p{page}_96.png'))
    same[str(page)]=(pix.width,pix.height,pix.n,pix.samples)==(recorded.width,recorded.height,recorded.n,recorded.samples)
assert all(same.values())
manifest=load('entregas/AECODE_ENTREGA_308/MANIFIESTO.json')
diff=[n for n,h in manifest['archivos'].items() if not n.startswith('wheels/') and sha((root/n).read_bytes())!=h]
assert not diff,diff
review={'fecha_utc':now,'marcador309_sha256':sha((root/'seguimiento/claude_ruta/MARCADOR_PDF_309.json').read_bytes()),
    'archivos309_hash_verificado':len(entries),'pdf_original_sin_cambios':True,
    'reproduccion_independiente_mupdf96_identica':same,
    'revision_visual_windows':'Páginas7/8 revisadas por Codex: prefijos completos.',
    'poppler':{'ejecutable':'C:/Users/HP/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe',
        'version':'26.07.0','dpi':96,'salida_codigo':0,
        'paginas':{str(p):{'ruta':f'tmp/pdfs/revision_310/poppler-{p}.png','sha256':sha((root/f'tmp/pdfs/revision_310/poppler-{p}.png').read_bytes())} for p in (7,8)},
        'observacion':'Codex observa enp7 prefijos incompletos en los dos primeros bloques; no se acepta como cerrado el diagnóstico general.',
        'avisos':['No display font Symbol','No display font ArialUnicode']},
    'conclusion':'309 aceptada como investigación parcial y reproducción en dos motores; conclusión de artefacto de visualización no aceptada sin contrastar Poppler. Encargo310 adicional enviado.',
    'causa_CFF':'Hipótesis de Claude, no adoptada como causa demostrada por Codex.',
    'producto308_sin_cambios':True,'goal_completo':False}
save('seguimiento/REVISION_PDF_310.json',review)
control=load('seguimiento/CLAUDE_ESTADO.json')
control.update(estado='revisado_parcial',revision='seguimiento/REVISION_PDF_310.json')
save('seguimiento/CLAUDE_ESTADO_HISTORICO_309.json',control)
current={**control,'tarea':'pdf_310','modo':'auditoria_pdf','estado':'trabajando',
    'encargo':'seguimiento/ENCARGO_CLAUDE_PDF_310_POPPLER.md',
    'marcador':'seguimiento/claude_ruta/MARCADOR_PDF_310.json',
    'prefijos_autorizados':['seguimiento/claude_ruta/diagnostico_pdf_310/'],
    'revision_anterior':'seguimiento/REVISION_PDF_310.json','creado_utc':now,
    'confirmacion_envio':'Captura del proyecto/conversación correctos; compositor vacío. set_value en edit264; texto310 comprobado; Return; burbuja nueva en historial y compositor vacío. Respuesta y cambios310 pendientes de comprobar por archivos.',
    'propietario_implementacion':'Claude: solo diagnostico_pdf_310/ y marcador310. No editar309 ni producto.',
    'prueba_sonda':'seguimiento/test_sonda_pdf_309.py:6casosOK; modo PDF parametrizado por tarea, SHA y perímetro estrictos.'}
current.pop('revision',None)
save('seguimiento/CLAUDE_ESTADO.json',current)
checkpoint={'fecha_utc':now,'goal_completo':False,'anterior':'seguimiento/RETOMAR_CODEX_306.json',
 'distribucion_actual':'entregas/AECODE_ENTREGA_308','huella_fuentes':manifest['huella_fuentes'],
 'complemento':'entregas/COMPLEMENTO_CORREGIDO_303','guia':'entregas/AECODE_ENTREGA_308/LEER_PRIMERO.md',
 'validacion':'1424Python y36frontend306 correctas,599fuentes.308 solo6documentos, código/pruebas/dependencias idénticos.79enlaces comprobados. No repetir suites/instalación.',
 'evidencia_validacion':'entregas/AECODE_ENTREGA_308/VALIDACION.json',
 'auditoria':'seguimiento/AUDITORIA_P01_P14_308.json',
 'descarga':'seguimiento/QA_DESCARGA_Y_306_307.json: usuario descargóChrome303;117212B ySHAcoinciden. Apertura306 comprobada, no afirmar descarga308.',
 'arranque':'seguimiento/ARRANQUE_VACIO_308.json: ZIP308 extraído con raíz vacía, sinclaves/proveedores/ETABS; servidor18310 cerrado.',
 'claude':{'registro':'seguimiento/CLAUDE_ESTADO.json','tarea_actual':310,'encargo':'seguimiento/ENCARGO_CLAUDE_PDF_310_POPPLER.md',
  'marcador':'seguimiento/claude_ruta/MARCADOR_PDF_310.json','estado':'enviado, pendiente entrega; no afirmar terminación',
  'revisado309':'seguimiento/REVISION_PDF_310.json','control':'NativeCU reanudado por humano y solo usado para coordinación; ningún Escape posterior. No sondear ventana; primero estado_claude.py.',
  'cuota_visible':'Claude92%semanal usado al iniciar309; no prometer ejecución si se agota.'},
 'referencia_humana':{'estado':'Usuario respondió que completará el anotador; todavía no entregóruta/JSON. No puntuar ni inferir aprobación.',
  'kit':'seguimiento/referencia_humana_308/Anotar_referencia.html','instrucciones':'seguimiento/referencia_humana_308/LEER_PRIMERO.md',
  'qa':'seguimiento/QA_ANOTADOR_308.json:3imágenes mismas del primerproyecto,0observaciones, exportación vacía bloqueada, JSválido.',
  'fuente':'Caso inicial provisional-001, mismos3PDFestructurales del primerproyecto, no proyectos2/3.',
  'pendiente':'Al recibirJSON humano, validar y preparar/revisar correspondencias con candidatos anteriores a corrección antes de medir. No crear verdad humana con IA.'},
 'servidores':[{'exec':36115,'url':'http://127.0.0.1:18303/','runtime':'ZIP303','estado':'handle confirmado vivo en esta coordinación'},
               {'exec':95011,'url':'http://127.0.0.1:18306/','runtime':'ZIP306, códigoidéntico308','estado':'handle confirmado vivo en esta coordinación'}],
 'navegadores':'IABqa306 era tab2/18306; reconstruir binding si falta. Chrome debugger quedódesconectado tras waitForEvent(download); NUNCA repetir esa espera ni variante asíncrona/Promise.all: bloqueó1025s. Descarga real ya quedóverificada por archivo y usuario.',
 'restricciones':['No nuevasAPI: OpenAI4/5,Gemini2/5 consumidas, exclusivamenteplanos; no leercredenciales.',
  'No procesar proyectos2/3 hasta validarprimero. Modelo manual retenido/aplazado; no pedirlo.',
  'No modificar producto308 ni carpeta310 mientrasClaude trabaja; propuesta310 requiere revisión e integración porCodex.',
  'Heartbeat coordinar-entregas-de-claude siguePAUSADO; no reactivar sin petición.',
  'Sin aprobación profesional; hipótesis suelo/sistema, sinEMS;10comparaciones no satisfactorias y masa no_coherente conservados.'],
 'cuota':{'ultima_observacion_utc':'2026-10-24T06:41:55Z','restante5h_observado':100,'restanteSemanal_observado':69,
  'incidencia':'Auto-review porcuota bloqueócrearLEER_PRIMERO308 antes delreset; acciónnoejecutada. Trasrestablecimiento100% se repitiómismapatch yseguardó. Sinresetmanual.',
  'politica':'<=5%no iniciartrabajospesados;<=1%guardaryterminar; no declararlogrado poragotamiento.'},
 'siguiente':['Ejecutar solo estado_claude.py para entrega310. Ante candidato:SHA/perímetro, lectura breve y prueba focal; no confiar en conclusión por marcador.',
  'Completar índices/evidencias externas pendientes sin cambiar fuentes congeladas; matrizP12 sigueabierta porPoppler.',
  'Esperar referencia humana efectiva paraP04; aceptación de hacerla no equivale a archivo anotado.',
  'No reconstruirhistorial ni relanzarglobales. Mantenerobjetivoíntegro; no marcarcompleto conP04/P12 abiertos.']}
save('seguimiento/RETOMAR_CODEX_310.json',checkpoint)
save('seguimiento/RETOMAR_ACTUAL.json',{'checkpoint':'seguimiento/RETOMAR_CODEX_310.json','fecha_utc':now,'goal_completo':False})
print(json.dumps({'hashes309':len(entries),'reproduccion_mupdf':same,'producto_sin_cambios':not diff,'checkpoint':'310'}))
