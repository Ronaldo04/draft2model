"""Conservar la entrega331 aceptada como software supervisado, sin cerrar el objetivo global."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[1]
folder = root/'seguimiento'
now = datetime.now(timezone.utc).isoformat()
delivery = json.loads((folder/'ENTREGA_ACADEMICA_331_FINAL.json').read_text(encoding='utf-8'))
assert hashlib.sha256((root/delivery['archivo']).read_bytes()).hexdigest() == delivery['sha256']
validation = json.loads((root/'entregas/AECODE_PRESENTACION_331/VALIDACION_PAQUETE.json').read_text(encoding='utf-8'))
global_state = json.loads((root/'tmp/validacion_distribucion_331/estado.json').read_text(encoding='utf-8'))
assert global_state['estado'] == 'terminado' and global_state['codigo'] == 0
assert all(hashlib.sha256((root/n).read_bytes()).hexdigest() == h for n,h in global_state['cambios'].items())
state = {
 'fecha_utc': now, 'goal_completo': False, 'anterior': 'seguimiento/RETOMAR_CODEX_331.json',
 'responsable_unico': 'Codex; sin Claude ni nuevas delegaciones.',
 'estado_hito': 'Entrega331 consolidada y verificada; lista para revisión académica como sistema supervisado.',
 'entrega': delivery, 'validacion_paquete': validation,
 'guia': 'entregas/AECODE_PRESENTACION_331/LEER_PRIMERO.md',
 'reporte': 'entregas/AECODE_PRESENTACION_331/REPORTE_ESTADO.md',
 'guion': 'entregas/AECODE_PRESENTACION_331/PRESENTACION_5_MINUTOS.md',
 'procesos': {'20690': 'terminal0/global329', '31832': 'terminal0/global331', '50585': 'terminal0/empaquetado331'},
 'edb_archivado_sha256_verificado': '42371308a03d4f1bac8f5ed3aa5daf0421cdf3de27ff823f8f582c13ad2af394',
 'ejecucion': 'Código331 exacto validado en copia aislada; sin nueva instalación, API ni ejecución nativa. Modelo/informes anteriores conservados.',
 'no_repetir': ['Suites329/331 ya correctas y sin omisiones.', 'Empaquetador331 ya ejecutado; rechaza sobreescritura.',
                'Benchmark328 ya reproducido; no pedir de nuevo anotador humano al usuario.', 'Recorrido nativo322 ya conservado.'],
 'cambios_operativos': ['Avisos de cotas/unidades mostrados por candidato.',
                       'Búsqueda local de texto vectorial y propuestas de región con abstención ante duplicados; no guarda automáticamente.'],
 'limites_materiales': ['Entrada aún supervisada; no modelado autónomo de cualquier construcción acreditado.',
                        'Otros proyectos/tipologías sin validación.', 'Suelo y sistema son escenarios sin EMS; reglas RNE parciales.',
                        'Comparación manual aplazada;18comparaciones técnicas conservadas,10no satisfactorias.',
                        'Latencia alta en expediente grande.', 'OCR local solo experimental, no integrado ni presentado como operativo.'],
 'restricciones': ['Conservar intacta entrega331 para presentación;328 es respaldo.',
                  'Sin APIs, claves, modelo manual ni proyectos2/3.',
                  'No nuevas funciones antes de finalizar entrega al usuario.',
                  'Cualquier desarrollo posterior debe aislarse del software congelado; no sustituirlo sin validación.',
                  'No declarar aprobación estructural, RNE integral ni objetivo global completo.'],
 'siguiente': ['Entregar enlaces a ZIP331FINAL, guía y reporte. No hace falta reejecutar ETABS para presentar resultados archivados.',
              'Mantener objetivo activo. El cierre académico de software supervisado no prueba automatización universal.',
              'Para continuar después de la entrega, priorizar robustez de entrada con reconocimiento local de imagen y evidencia verificable, en copia aislada; no alterar el paquete presentado.'],
}
for name,value in [('RETOMAR_CODEX_332.json',state),('RETOMAR_ACTUAL.json',
 {'checkpoint':'seguimiento/RETOMAR_CODEX_332.json','fecha_utc':now,'goal_completo':False})]:
 (folder/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Entrega331 y checkpoint332 verificados; objetivo global no declarado completo.')
