"""Conservar evidencia revisada sin cambiar las fuentes congeladas303."""
from pathlib import Path
import json
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[1]
now = datetime.now(timezone.utc).isoformat()
def load(name):
    return json.loads((root/name).read_text(encoding='utf-8'))
def save(name, value):
    (root/name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

e = load('seguimiento/VALIDACION_DISTRIBUCION_305.json')
assert e['validacion_local_completa'] and e['fuentes_intactas']
note = root/'entregas/AECODE_RC_303/NOTAS_VALIDACION_304.md'
text = note.read_text(encoding='utf-8')
text = text.replace('No atribuirle aprobación mientras no se revise su estado final.',
    'Resultado final revisado: 1419 pruebas Python correctas en 1569,984 s y 35 pruebas de interfaz correctas, sin omisiones. Dependencias, CLI y scripts PowerShell correctos; fuentes estables durante la ejecución y los 597 archivos extraídos siguen coincidiendo con el manifiesto. Evidencia: seguimiento/VALIDACION_DISTRIBUCION_305.json y verificacion_304.json. Esta suite no ejecuta un nuevo análisis nativo del piloto.')
text = text.replace('Falta la aceptación funcional conjunta y el recorrido final de informe/descarga.',
    'El informe UI de QA d0aae89744524766b122d604c59e0d3e ya se publicó y sus tres archivos coinciden con paquete.json. Sigue pendiente confirmar la descarga por navegador y cerrar la aceptación funcional conjunta; no se considera resuelta por la publicación en disco.')
note.write_text(text, encoding='utf-8')

audit = load('seguimiento/AUDITORIA_CIERRE_304.json')
audit['fecha_corte'] = now
for item in audit['criterios']:
    if item['id'] == 'instalacion_y_arranque':
        item['estado'] = 'instalacion_offline_arranque_y_suite_global_correctos_mismoZIP303'
        item['falta'] = 'Conservar instrucciones de rutas cortas; no equivale a ejecución ETABS en otro equipo.'
        item['evidencia_actual'].append('seguimiento/VALIDACION_DISTRIBUCION_305.json')
    if item['id'] in ('analisis_y_resultados', 'panel_e_informes', 'paquete_final_y_guia'):
        item['falta'] = 'Informe UI publicado con hashes verificados; descarga Chrome y aceptación conjunta pendientes. Conservar limitaciones de ingeniería, rendimiento y renderizadores PDF.'
save('seguimiento/AUDITORIA_CIERRE_305.json', audit)

checkpoint = {
    'fecha_utc': now, 'goal_completo': False,
    'anterior': 'seguimiento/RETOMAR_CODEX_304.json',
    'fuentes_congeladas': 'entregas/AECODE_RC_303',
    'huella_fuentes': '5fd73861327c0e447b87158032ffc9a69899a01c1376c736e03920f7a6e6aa1c',
    'complemento': 'entregas/COMPLEMENTO_CORREGIDO_303',
    'global304': {'estado': 'terminada_correcta', 'exec_historico':18091,
        'evidencia':'seguimiento/VALIDACION_DISTRIBUCION_305.json',
        'no_repetir':'1419 Python y35 Node sin omisiones;597 fuentes intactas. No reinstalar ni reiniciar suite.'},
    'servidor': {'exec':36115, 'pid':34488, 'inicio_local':'2026-10-23T20:37:27',
        'url':'http://127.0.0.1:18303/', 'fuentes':'tmp/validacion_distribucion_303/fuentes',
        'regla':'No reiniciar ni interrumpir operaciones existentes. Comprobar identidad si handle no existe.'},
    'ui': {'iab':'qa304, browser2/tab1', 'chrome':'chrome305, browser3/tab1381157152',
        'origen':'Usuario abrió Chrome por barra de direcciones; navegación automatizada anterior marcada cross-site rechazó correctamente.',
        'informe':'d0aae89744524766b122d604c59e0d3e',
        'publicado_utc':'2026-10-24T01:56:46.774561+00:00',
        'estado':'Archivos publicados con hashes correctos. IAB sigue en generación/listado; Chrome en Consultando versiones. No repetir creación ni recargar.',
        'siguiente':'Observar sin repetir solicitudes; cuando termine seleccionar resultado697bb37e9ce64f90ba1ef3e25733c8cc en Chrome UNA vez; abrir informe ya existente y descargarPDF/JSON UNA vez. Verificar hash del archivo realmente descargado.'},
    'auditoria':'seguimiento/AUDITORIA_CIERRE_305.json',
    'restricciones':['No nuevas API: OpenAI4/5 y Gemini2/5; solo lectura de planos.',
        'No procesar proyectos2/3 ni comparar modelo manual aplazado.',
        'Claude entregó; Codex cierra. NativeCU suspendido tras Escape; no usarlo sin reanudación humana.',
        'Heartbeat pausado. <=5% no nuevos trabajos pesados; <=1% guardar y terminar.'],
    'limitaciones':['Sin EMS ni aprobación profesional; hipótesis de suelo/sistema.',
        '10comparaciones no satisfechas y masa oficial no_coherente, sin alterar tolerancias.',
        'Operaciones completas costosas; no confundir inventario rápido con verificación completa.',
        'Salvedades de rasterizado PDF documentadas en REVISION_INFORME_302; HTML alternativo.',
        'Un piloto no demuestra modelado autónomo de cualquier construcción.'],
    'cierre':'Pendiente descarga real, rendimiento observado y auditoría conjunta; no declarar goal logrado.'
}
save('seguimiento/RETOMAR_CODEX_305.json', checkpoint)
save('seguimiento/RETOMAR_ACTUAL.json', {'checkpoint':'seguimiento/RETOMAR_CODEX_305.json','fecha_utc':now,'goal_completo':False})
print('Evidencia305, notas y checkpoint guardados; fuentes303 sin modificar.')
