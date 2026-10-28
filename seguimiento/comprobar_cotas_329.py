"""Revisa cuatro respuestas históricas sin modificarlas ni hacer llamadas externas."""
import hashlib
import json
from collections import Counter
from pathlib import Path

from draft2model.extraccion_preliminar import validar_extraccion

root = Path(__file__).resolve().parents[1]
base = root / 'seguimiento/revision_antigravity_328/evaluaciones'
resultados = []
for cohort in ('openai_1', 'openai_3', 'openai_4', 'gemini_1'):
    path = base / cohort / 'extraccion_original.json'
    raw = path.read_bytes()
    data = json.loads(raw)
    result = validar_extraccion(data)
    alerts = [a for a in result.advertencias if a.codigo in (
        'valor_sin_correspondencia_literal', 'unidad_sin_respaldo_literal', 'unidad_sin_texto_fuente')]
    assert path.read_bytes() == raw
    resultados.append({'cohorte': cohort, 'sha256_intacto': hashlib.sha256(raw).hexdigest(),
                       'consistente': result.consistente,
                       'candidatos': len(data['candidatos']),
                       'avisos': dict(Counter(a.codigo for a in alerts)),
                       'detalle': [vars(a) for a in alerts]})
salida = {'api_calls': 0, 'modifica_datos': False, 'cohortes': resultados,
          'limite': 'Detecta incoherencia declarada; no verifica texto ni regiones en imágenes.'}
out = root / 'seguimiento/COHERENCIA_COTAS_329.json'
out.write_text(json.dumps(salida, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
for item in resultados:
    print(item['cohorte'], 'candidatos=', item['candidatos'], 'avisos=', item['avisos'])
