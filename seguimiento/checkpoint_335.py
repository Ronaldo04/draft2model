"""Persistir la validación de desarrollo OCR, manteniendo inmutable331."""
import json
from pathlib import Path
from datetime import datetime,timezone

root=Path(__file__).resolve().parents[1]
folder=root/'seguimiento'
now=datetime.now(timezone.utc).isoformat()
state=json.loads((folder/'RETOMAR_CODEX_334.json').read_text(encoding='utf-8'))
state.update(fecha_utc=now,anterior='seguimiento/RETOMAR_CODEX_334.json',
 estado_hito='OCR local integrado en copia aislada; pruebas focales y motor real correctos; global335 en curso.')
state['desarrollo_ocr_333'].update(
 estado='integracion_aislada_en_validacion_no_publicada',
 implementacion=['Servicio/API e interfaz con acción OCR separada, sin transmisión.',
                 'Caché2páginas/8MiB por SHA original/página/ejecutable/modelos/parámetros, objetos independientes.',
                 'Exclusión de lecturas simultáneas, errores de motor/plazo, validación de fuente al terminar.',
                 'Opciones ambiguas y confianza sin aprobación; respuestas tardías descartadas.'],
 pruebas='tmp/ocr_335_tests.log:60backend sin omisiones; tmp/frontend_ocr_335.log:36interfaz sin omisiones.',
 flujo_real='seguimiento/FLUJO_OCR_LOCAL_335.json:2consultasHTTPenmemoria y1Tesseract real, C-1única yC-2con4opciones;6,215s/0,151s, noSLA.',
 documentacion='tmp/desarrollo_ocr_333/docs/OCR_LOCAL.md',
 limites=['PDF únicamente; falta cubrir originales PNG/JPEG.',
          'No extrae automáticamente clases, escala, geometría ni parámetros de ingeniería; no completa el objetivo global.',
          'Sin revisión visual de toda la interfaz335 ni todas las700palabras.'])
state['global335']={'session_id':93306,'registro':'tmp/validacion_ocr_335/estado.json',
                    'estado_al_guardar':'en_ejecucion','fuentes':'tmp/desarrollo_ocr_333',
                    'instruccion':'Sondear mismo handle; no reiniciar por timeout ni cambiar fuentes durante la comprobación.'}
state['siguiente']=[
 'Mantener331y su anexo offline334 como entrega de presentación. No sustituir ni reempaquetar esos archivos.',
 'Esperar handle93306. Si termina0, inspeccionar verificacion.json:5comprobaciones, fuentes estables, sin omisiones y conteos observados. Esperado1515Python+36interfaz, no afirmarlo antes de leer logs.',
 'No tocar fuentes335 mientras la validación esté viva ni ejecutar otra suite. Un informe parcial/timeout no autoriza reiniciar.',
 'Tras validación, registrar resultados como desarrollo aislado, no una nueva entrega ni aprobación universal. Puede requerir revisión visual e integración adicional antes de distribuir.',
 'El objetivo global permanece activo: entrada y geometría aún supervisadas, otras tipologías/rendimiento sin acreditar. Respetar veto previo a proyectos2/3 y comparación manual aplazada.',
 'Sin APIs, claves, Claude, subagentes ni ETABS nuevo. Cualquier trabajo posterior permanece separado del paquete331 durante la presentación.'
]
for name,value in [('RETOMAR_CODEX_335.json',state),('RETOMAR_ACTUAL.json',
 {'checkpoint':'seguimiento/RETOMAR_CODEX_335.json','fecha_utc':now,'goal_completo':False})]:
 (folder/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Estado335 guardado; presentación331 intacta.')
