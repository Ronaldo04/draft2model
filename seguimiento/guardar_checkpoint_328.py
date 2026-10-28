"""Consolida el estado de entrega sin modificar el programa ni el caso."""
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[1]
folder = root / 'seguimiento'
delivery = json.loads((folder / 'ENTREGA_ACADEMICA_328_FINAL.json').read_text(encoding='utf-8'))
now = datetime.now(timezone.utc).isoformat()
state = {
    'fecha_utc': now,
    'anterior': 'seguimiento/RETOMAR_CODEX_326.json',
    'goal_completo': False,
    'responsable_unico': 'Codex; sin Claude, subagentes ni nuevas delegaciones.',
    'estado_hito': 'Antigravity revisado; referencia asistida corregida y evaluada; entrega académica preparada.',
    'distribucion_validada': 'entregas/AECODE_ENTREGA_325',
    'entrega_presentacion': delivery,
    'guia': 'entregas/AECODE_PRESENTACION_328/LEER_PRIMERO.md',
    'reporte': 'entregas/AECODE_PRESENTACION_328/REPORTE_ESTADO.md',
    'revision_antigravity': {
        'directorio': 'seguimiento/revision_antigravity_328',
        'observaciones_revisadas': 33,
        'observaciones_ajustadas': 13,
        'naturaleza': 'Asistida por IA; no humana ni independiente.',
        'referencia_fijada_antes_de_respuestas': True,
        'evaluaciones_cli_reproducidas': 4,
        'denominadores_legibles_por_cohorte': [32, 11, 21, 11],
        'advertencia': 'Muestra parcial con criterio estricto de tipo y región; no precisión global OCR.',
        'usuario_pendiente_de_anotador': False,
    },
    'verificacion': {
        'software': '325: 1471 Python + 36 interfaz; cinco comprobaciones correctas; código intacto.',
        'nuevo_trabajo': 'Cuatro evaluaciones CLI reproducidas, once enlaces nuevos válidos y hashes del paquete verificados.',
        'edb_original_intacto': True,
        'nuevas_llamadas_api': 0,
        'nueva_ejecucion_nativa_etabs': False,
        'trabajos_pendientes_en_ejecucion': [],
        'no_repetir': 'No repetir suites 325, perfiles ni recorrido 322 sin cambios que lo justifiquen.',
    },
    'pendientes_materiales': [
        'Robustez de entrada automática: localización, taxonomía, unidades y configuración supervisada.',
        'Generalización a otros proyectos y tipologías; todavía no está acreditada.',
        'Rendimiento interactivo del expediente grande.',
        'Revisión independiente de ingeniería para uso real; escenarios sin EMS y reglas RNE parciales.',
    ],
    'restricciones': [
        'No leer credenciales ni realizar nuevas llamadas LLM.',
        'No procesar proyectos 2/3 hasta resolver la instrucción previa de validar el primero.',
        'Modelo ETABS manual y comparación aplazados por el usuario.',
        'Conservar 18 comparaciones, incluidas 10 no satisfactorias, y tolerancias originales.',
        'No declarar aprobación estructural ni automatización universal.',
        'Heartbeat de Claude permanece pausado.',
    ],
    'siguiente': [
        'Presentar el paquete FINAL y el reporte de límites; no modificar el software congelado por preparación de entrega.',
        'Si continúa desarrollo, priorizar entrada automática con casos reproducibles de localización/unidades y abstenciones explícitas.',
        'Usar evidencias 328 existentes; no volver a pedir referencia humana al usuario como condición de esta entrega asistida.',
    ],
}
def write(name, value):
    (folder / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

write('RETOMAR_CODEX_328.json', state)
write('RETOMAR_ACTUAL.json', {'checkpoint': 'seguimiento/RETOMAR_CODEX_328.json', 'fecha_utc': now, 'goal_completo': False})
print('Checkpoint 328 guardado; objetivo activo, no declarado completo.')
