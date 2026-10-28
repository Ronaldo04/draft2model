"""Persistir la continuación durante la única comprobación global del hito."""
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[1]
folder = root / 'seguimiento'
now = datetime.now(timezone.utc).isoformat()
state = {
    'fecha_utc': now, 'goal_completo': False,
    'anterior': 'seguimiento/RETOMAR_CODEX_328.json',
    'responsable_unico': 'Codex; sin delegación ni Claude.',
    'entrega_presentacion_intacta': 'entregas/AECODE_PRESENTACION_328_FINAL.zip',
    'sha256_entrega': '6a1dc4f39d24839fb03bf5be252734fe975327fb4cf4ba82f1f12be0cd734949',
    'cambio': 'Avisos integrados en validar_extraccion sobre coherencia de números/unidades con texto_fuente; sin alterar lecturas ni convertir unidades.',
    'documentacion': 'docs/COHERENCIA_LITERAL_DE_COTAS.md',
    'pruebas_focales': {'cantidad': 118, 'codigo': 0, 'omisiones': 0,
                        'registro': 'tmp/coherencia_literal_329_tests.log'},
    'revision_historica': 'seguimiento/COHERENCIA_COTAS_329.json: 92 cotas automáticas sin texto literal; aviso, no prueba de valor erróneo.',
    'validacion_global': {'session_id': 20690, 'registro': 'tmp/validacion_distribucion_329/estado.json',
                          'fuentes': 'tmp/validacion_distribucion_329/fuentes',
                          'observacion': 'Handle confirmado vivo tras lanzamiento; no reiniciar por timeout de observación.',
                          'estado_al_guardar': 'en_ejecucion'},
    'siguiente': [
        'Sondear el mismo handle 20690 o su PID verificado. Si termina, leer verificacion.json: todas las comprobaciones deben pasar, sin omisiones y con fuentes estables.',
        'Si pasa, preparar distribución posterior diferenciada, conservar ZIP328 y actualizar evidencias; no afirmar nueva prueba ETABS ni nuevo OCR real.',
        'Resolver cualquier fallo antes de publicar; no repetir global si ya pasó y no hubo cambios.',
        'Continuar robustez de localización y entrada; la coherencia literal no verifica imagen, no acredita generalización ni completa el objetivo.',
    ],
    'restricciones': ['Sin nuevas APIs ni lectura de claves.', 'No modelo manual ni proyectos 2/3.',
                      'No cambiar tolerancias, resultados ni EDB.', 'No declarar todo RNE ni automatización universal.'],
}
for name, value in [('RETOMAR_CODEX_329.json', state), ('RETOMAR_ACTUAL.json',
    {'checkpoint': 'seguimiento/RETOMAR_CODEX_329.json', 'fecha_utc': now, 'goal_completo': False})]:
    (folder / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Checkpoint 329 guardado.')
