"""Guardar el relevo a Codex sin modificar entregas históricas."""
from pathlib import Path
from datetime import datetime, timezone
import json

root = Path(__file__).resolve().parents[1]
now = datetime.now(timezone.utc).isoformat()
state = {
    'fecha_utc': now, 'goal_completo': False,
    'anterior': 'seguimiento/RETOMAR_CODEX_321.json',
    'responsable_unico': 'Codex; el usuario retiró Claude. Sin nuevas delegaciones ni Computer Use para Claude.',
    'distribucion_validada': 'entregas/AECODE_ENTREGA_312',
    'advertencia': 'Las fuentes de desarrollo cambiaron en322. La suite1425+36 corresponde exclusivamente a312.',
    'integracion': 'Estimación experimental opcional de peso efectivo Auto: lectura de configuración, núcleo con validación oficial del plan, libro bruto preservado, backend, CLI, informe e interfaz.',
    'pruebas_observadas': {'python_focal': '48OK, tmp/integracion_auto_322.log', 'frontend': '36archivos OK, tmp/frontend_auto_322.log'},
    'recorrido_real': {'registro': 'seguimiento/FLUJO_AUTO_322.json', 'exec': 30753,
                      'instruccion': 'Consultar proceso y registro antes de actuar. NO relanzar verificar_flujo_auto_322.py. Usa lectura real sin Save/recalculo/LLM.'},
    'siguiente': ['Resolver el recorrido ya iniciado; conservar su evidencia incluso si falla.',
                  'Completar pruebas de captura/configuración y regresión integrada; revisión visual de informe e interfaz nuevos.',
                  'Actualizar guía y producir distribución reproducible del código integrado, conservando312.',
                  'P04 sigue pendiente de referencia humana prometida por el usuario. No inventar verdad ni métricas.'],
    'restricciones': ['Sin llamadas LLM adicionales ni lectura de credenciales.',
                      'No modelo ETABS manual ni proyectos2/3.',
                      'Sin EMS ni aprobación profesional; conservar18evaluaciones y10no satisfactorias.',
                      'No ensanchar tolerancias ni corregir entradas a partir de resultados nativos.',
                      'Heartbeat Claude permanece pausado.'],
    'limites_estimacion': '21.1.0, kN_m_C, geometría rectangular cubierta y configuración nativa verificada. Abstenerse fuera del perfil; no acredita conformidad normativa global.'
}
(root/'seguimiento/RETOMAR_CODEX_322.json').write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
(root/'seguimiento/RETOMAR_ACTUAL.json').write_text(json.dumps({'checkpoint':'seguimiento/RETOMAR_CODEX_322.json','fecha_utc':now,'goal_completo':False},ensure_ascii=False,indent=2),encoding='utf-8')
p=root/'seguimiento/CLAUDE_ESTADO.json'
old=json.loads(p.read_bytes())
old.update(estado='revisado', propietario_implementacion='Codex, único responsable por decisión del usuario; candidato321 integrado en desarrollo322.',
           siguiente_dependencia='No asignar ni supervisar Claude. Continuar RETOMAR_CODEX_322.json.',
           computer_use_suspendido=True, cierre_coordinacion_utc=now)
p.write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding='utf-8')
print('Checkpoint322 guardado; Claude fuera de la ruta de ejecución.')
