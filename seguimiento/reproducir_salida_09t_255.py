"""Evalúa solo el predicado de salida del AST original, sin importar el runner."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'seguimiento/claude_ruta/recorrido_etabs_09t.py'
raw = source.read_bytes()
tree = ast.parse(raw.decode('utf-8-sig'))
main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
assignment = next(n for n in main.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'fallo' for t in n.targets))
expression = ast.Expression(assignment.value)
ast.fix_missing_locations(expression)
code = compile(expression, str(source), 'eval')
fixtures = {
    'cierre_false': {'construccion': {'estado': 'ok', 'cierre_confirmado': False}},
    'error_cierre': {'construccion': {'estado': 'ok', 'error_cierre': 'cierre no confirmado'}},
    'relectura_discrepancias': {'relectura': {'estado': 'discrepancias', 'discrepancias': 1, 'incompletos': 0}},
    'relectura_incompleta': {'relectura': {'estado': 'incompleto', 'discrepancias': 0, 'incompletos': 1}},
    'control_error_explicito': {'construccion': {'estado': 'error'}},
}
results = []
for name, phases in fixtures.items():
    failed = eval(code, {'__builtins__': {'any': any, 'isinstance': isinstance, 'dict': dict}, 'rep': {'fases': phases}})
    results.append({'caso': name, 'fallo_detectado': failed, 'salida_que_deriva_main': 1 if failed else 0})
out = {'alcance': 'Solo predicado extraido del AST; no imports ni ejecucion del runner, ETABS o aprobaciones', 'fuente': str(source.relative_to(ROOT)), 'fuente_sha256': hashlib.sha256(raw).hexdigest(), 'casos': results, 'hallazgo': 'Predicado ignora cierres no confirmados y relecturas no verificadas; no acredita exito operativo'}
(ROOT / 'seguimiento/REPRODUCCION_SALIDA_09T_255.json').write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
assert all(r['salida_que_deriva_main'] == 0 for r in results[:4])
assert results[-1]['salida_que_deriva_main'] == 1
print(json.dumps({'reproducciones': len(results), 'falsos_exitos_identificados': 4, 'sin_ejecutar_runner': True}))
