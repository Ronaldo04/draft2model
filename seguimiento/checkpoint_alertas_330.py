"""Persistencia de la interfaz comprobada y de la validación aislada todavía viva."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[1]
folder = root / 'seguimiento'
now = datetime.now(timezone.utc).isoformat()
state = json.loads((folder / 'RETOMAR_CODEX_329.json').read_text(encoding='utf-8'))
state.update(fecha_utc=now, anterior='seguimiento/RETOMAR_CODEX_329.json',
             interfaz='Alertas de validación visibles por candidato, insertadas como texto; no guardan ni envían.',
             pruebas_interfaz={'registro': 'tmp/frontend_cotas_330.log', 'cantidad': 36,
                               'correctas': 36, 'omisiones': 0},
             integracion='seguimiento/INTEGRACION_ALERTAS_330.json: PDF sintético, importación/consulta reales, avisos en respuesta API y candidato pendiente intacto.')
state['cambios_posteriores_a_copia329'] = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
    for name in ('draft2model/revision_web/app.js', 'tests/revision_lecturas_semanticas_frontend.cjs',
                 'docs/COHERENCIA_LITERAL_DE_COTAS.md')}
state['siguiente'] = [
    'Sondear handle20690 (última observación: vivo), sin reiniciar. Al terminar leer estado/verificacion.json de329.',
    'La copia329 global contiene backend nuevo y UI anterior. La UI330 posterior está probada con36scripts de interfaz sin omisiones y comprobación API sintética; no atribuirle la huella exacta de329.',
    'Si se publica nueva distribución330, documentar con precisión ambas fases y hashes, o completar validación de su huella exacta cuando sea necesaria; no afirmar pruebas no realizadas.',
    'Conservar ZIP328 para la presentación; no requiere claves y contiene caso/informes reales. No sustituirlo mientras no haya nueva entrega aceptada.',
    'Siguiente brecha de producto: localizar evidencia de lecturas en fuentes, con abstención ante duplicados/escaneos; los avisos de coherencia no prueban veracidad visual.',
]
for name, value in [('RETOMAR_CODEX_330.json', state), ('RETOMAR_ACTUAL.json',
    {'checkpoint': 'seguimiento/RETOMAR_CODEX_330.json', 'fecha_utc': now, 'goal_completo': False})]:
    (folder / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Interfaz330 e integración comprobadas; validación329 conservada sin cambios.')
