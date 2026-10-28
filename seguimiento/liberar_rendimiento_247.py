"""Registra aceptación focal y libera solo los archivos reservados verificados."""
import hashlib
import json
from pathlib import Path
root = Path(__file__).resolve().parent.parent
capture = json.loads((root/'seguimiento/CAPTURA_RENDIMIENTO_247.json').read_text(encoding='utf-8'))
agent = json.loads((root/'tmp/revision_rendimiento_246/huellas_despues.json').read_text(encoding='utf-8'))
assert capture['sha256'] == agent
for name, expected in agent.items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest() == expected, name
result = {
    'estado': 'aceptado_incremental',
    'snapshot': capture['snapshot'],
    'sha256': agent,
    'revision_codigo': 'Contexto privado por invocación, valida copia propia y compara fuente completa por consumo; sin cache global. Reproducción de particiones/compatibilidad y guardas finales conservadas. No cambia tolerancias/contratos.',
    'pruebas_propias': {'cantidad': 8, 'segundos': 11.859, 'resultado': 'OK', 'alcance': 'Igualdad íntegra/ruta pública/huellas previas,48hosts/576triángulos/147→1validación, errores y mutaciones,particiones manipuladas,invocaciones sucesivas y concurrentes'},
    'pruebas_delegadas': '36 focales; no se repitió suite general ni malla real.',
    'limitaciones': 'Guardas canónicas siguen O(N×tamaño del documento). Mejora acotada4.26→1.188s es medición delegada, no tiempo del piloto. No acredita cierre del proyecto.'
}
(root/'seguimiento/REVISION_RENDIMIENTO_247.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
path = root/'seguimiento/ACUERDO_RESERVA_246.json'
agreement = json.loads(path.read_text(encoding='utf-8'))
agreement['liberacion'] = {'fecha': '2026-10-22', 'por': 'Codex', 'estado': 'liberada_tras_revision', 'evidencia': 'seguimiento/REVISION_RENDIMIENTO_247.json', 'aviso_claude': 'pendiente_confirmar_envio'}
path.write_text(json.dumps(agreement, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print('5 hashes coinciden; 8 pruebas propias OK; reserva liberada por archivo, aviso pendiente.')
