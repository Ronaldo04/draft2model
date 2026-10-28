"""Contrasta fuentes de la suite conservada; registra revisión incremental, no cierre."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
frozen = ROOT / 'tmp/revision_codex_246'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
verification = json.loads((ROOT/'tmp/c211/fuentes/tmp/verificacion.json').read_text(encoding='utf-8'))
checks = []
not_packaged = []
for name, expected in verification['huellas_archivos'].items():
    path = frozen / name.replace('\\', '/')
    if not path.exists():
        not_packaged.append(name)
        continue
    checks.append({'archivo': name, 'igual': path.exists() and sha(path) == expected})
assert checks and all(c['igual'] for c in checks), [c for c in checks if not c['igual']]
assert all(c['codigo'] == 0 for c in verification['comprobaciones'])
norm = json.loads((ROOT/'seguimiento/REVISION_VS30_245.json').read_text(encoding='utf-8'))
assert sha(frozen/'draft2model/normativa_e030.py') == norm['modulo_sha256']
suite = ROOT/'tmp/c211/fuentes/tmp/verificacion/2eefcb23944546b3825504b5d6f503f0'
assert 'Ran 1211 tests' in (suite/'suite.log').read_text(encoding='utf-8')
assert (suite/'suite.log').read_text(encoding='utf-8').rstrip().endswith('OK')
node = (suite/'interfaz.log').read_text(encoding='utf-8')
assert '# pass 31' in node and '# fail 0' in node
result = {
    'estado': 'revisado_incremental_con_limites',
    'snapshot': str(frozen.relative_to(ROOT)),
    'integridad': 'seguimiento/INTEGRIDAD_ENTREGAS_246.json',
    'fuentes_suite_contrastadas': len(checks),
    'archivos_no_incluidos_en_entrega': len(not_packaged),
    'logs_conservados': {'python': 1211, 'node': 31, 'sha_suite': sha(suite/'suite.log'), 'sha_node': sha(suite/'interfaz.log')},
    'pruebas_propias': '7 focales R241/R243 OK en 0.305s (host); sandbox WinError5 en temporales, no fallo funcional.',
    'vs30': 'Módulo idéntico a captura245 con38 comprobaciones independientes; no clasifica suelo real.',
    'limites': ['No acredita piloto nativo completo', 'C1/C6/PL10/escaleras/depósitos y aberturas siguen en implementación', 'Escenarios de suelo no equivalen a EMS', 'Plantilla propia bajo revisión separada', 'Optimización malla en reserva246'],
}
output = ROOT/'seguimiento/REVISION_ENTREGAS_247.json'
output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
reviews_path = ROOT/'seguimiento/claude_ruta/REVISIONES.json'
reviews = json.loads(reviews_path.read_text(encoding='utf-8'))
for item in json.loads((ROOT/'seguimiento/INTEGRIDAD_ENTREGAS_246.json').read_text(encoding='utf-8'))['entregas']:
    if item['id'] not in reviews['revisadas']:
        reviews['revisadas'].append(item['id'])
if not any(o['id'] == 'R247-01' for o in reviews['observaciones']):
    reviews['observaciones'].append({'id': 'R247-01', 'prioridad': 'revision_incremental', 'etapas': ['04', '06'], 'hallazgo': result, 'criterio_aceptacion': 'Incremento revisado, no cierre del encargo09. Continuar alcance íntegro y verificar piloto real.'})
reviews_path.write_text(json.dumps(reviews, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k != 'limites'}, ensure_ascii=False))
