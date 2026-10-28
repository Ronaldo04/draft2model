"""Guardar evidencia de instalación y desarrollo aislado sin cambiar la entrega."""
import json
from pathlib import Path
from datetime import datetime,timezone

root=Path(__file__).resolve().parents[1]
folder=root/'seguimiento'
now=datetime.now(timezone.utc).isoformat()
state=json.loads((folder/'RETOMAR_CODEX_332.json').read_text(encoding='utf-8'))
state.update(fecha_utc=now,anterior='seguimiento/RETOMAR_CODEX_332.json',
 estado_hito='Entrega331 intacta; instalación offline nueva334 verificada; OCR333 aislado sin integrar.')
state['instalacion_334']={
 'anexo':json.loads((folder/'INSTALACION_334.json').read_text(encoding='utf-8')),
 'registro':'tmp/i334/verificacion.json','entorno':'tmp/i334/v',
 'resultado':'6comprobaciones0, demo sintética6corridas, sin paquetes globales, módulos331 importables con Pillow12.3.0/PyMuPDF1.28.2 del entorno nuevo.',
 'alcance':'Misma estación, nuevo entorno; no otro equipo, ETABS ni visión real.',
 'fuentes616_intactas':True,'proceso83563':'terminal0'}
state['desarrollo_ocr_333']={
 'directorio':'tmp/desarrollo_ocr_333','base':'Software331 exacto extraído en copia separada.',
 'archivos_nuevos':['draft2model/ocr_local.py','tests/test_ocr_local.py'],
 'pruebas':'tmp/ocr_333_tests.log:10correctas; TSV estricto, duplicados, cotas sin convertir, rotaciones, dimensiones, ausencia de motor.',
 'ensayo_real':'seguimiento/OCR_LOCAL_333_REAL.json;700palabras de primera lámina; coincidencias C-1/C-6/PL-1 únicas y C-2/PL-10 ambiguas.',
 'qa_visual':'tmp/desarrollo_ocr_333/tmp/ocr_real/regiones.png leído:7recortes estructurales coinciden; no revisión de todas las700palabras.',
 'estado':'motor_probado_no_integrado_no_publicado',
 'no_confundir':'Entrega331 no contiene este OCR operativo. No cambiar sus manifiestos ni sus afirmaciones.',
 'siguiente_tecnico':'En copia aislada: integración optativa y acotada en servicio/API/interfaz, caché por original/perfil, concurrencia y pruebas de errores. No integrarlo en la entrega del deadline sin validación explícita de otra versión.'}
state['siguiente']=[
 'Entregar anexo de instalación334 como evidencia adicional; ZIP331 sigue siendo la entrega principal inmutable.',
 'No repetir suites329/331 ni instalación334 correctas. No hay procesos críticos pendientes.',
 'Mantener congelado331 durante la presentación del usuario (deadline comunicado15:15Lima24Oct). Las tareas futuras de desarrollo deben quedarse aisladas de331.',
 'Continuar el objetivo global sin declarar éxito universal: entrada supervisada, validación de tipologías y rendimiento siguen abiertos. Respetar veto previo a proyectos2/3 y comparación manual aplazada.',
 'No usar APIs ni leer claves; OCR local opcional no transmite documentos. No nuevos envíos a Claude ni subagentes.'
]
for name,value in [('RETOMAR_CODEX_334.json',state),('RETOMAR_ACTUAL.json',
 {'checkpoint':'seguimiento/RETOMAR_CODEX_334.json','fecha_utc':now,'goal_completo':False})]:
 (folder/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Checkpoint334 guardado; entrega331 permanece intacta.')
