"""Verificación independiente de recibo de geometría auxiliar; no llama ETABS."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
base = ROOT / 'tmp/ensayo_cotas_auxiliares_257'
receipt = base / 'runs/codex257a/registro.json'
d = json.loads(receipt.read_text(encoding='utf-8-sig'))
checks = []


def check(name, value):
    checks.append({'control': name, 'pasa': bool(value)})


check('resultado final y llamadas', d['status'] == 'verified' and len(d['calls']) == 98 and all(type(c['rc']) is int and c['rc'] == 0 for c in d['calls']))
expected = {'base_m': 0, 'number_stories': 4, 'names': ['N1', 'N2', 'N3', 'N4'], 'elevations_m': [2.6, 5.2, 7.8, 10.4], 'heights_m': [2.6]*4}
for label in ('stories_before', 'stories_built', 'stories_reopened'):
    check(label + '/pisos sin referencias ficticias', d[label] == expected)
check('ocho cotas probadas', {p['requested_xyz_m'][2] for p in d['points']} == {-2.5, -.105, -.05, 0, 10.4, 12.5, 13.7, 14.25} and len(d['points']) == 12)
for p in d['points']:
    for label in ('read', 'reopened'):
        check(p['read']['name'] + '/' + label, p[label]['name'] == p['read']['name'] and all(type(v) in (int, float) and math.isfinite(v) and abs(v - expected_v) <= 1e-9 for v, expected_v in zip(p[label]['xyz_m'], p['requested_xyz_m'])))
check('dos areas extremas persistidas', len(d['areas']) == 2 and all(a['number_points'] == a['reopened_number_points'] == 3 and a['reopened_points'][:3] == a['requested_points'] for a in d['areas']))
check('dos barras fuera del intervalo persistidas', len(d['frames']) == 2 and all(f['point_i'] == f['reopened_point_i'] and f['point_j'] == f['reopened_point_j'] for f in d['frames']))
check('cierre propio e instancias ajenas conservadas', d['close_code'] == 0 and d['owned_pid_absent'] is True and sorted(d['preexisting']) == sorted(d['remaining_preexisting']))
check('hash EDB', hashlib.sha256((receipt.parent / 'modelo.edb').read_bytes()).hexdigest() == d['edb_sha256'])
check('script ejecutado estable', hashlib.sha256((base / 'ensayar.ps1').read_bytes()).hexdigest() == d['script_sha256'])
out = {'estado': 'verificado_sintetico' if all(c['pasa'] for c in checks) else 'no_verificado', 'comprobaciones': checks, 'recibo': str(receipt.relative_to(ROOT)), 'sha256_recibo': hashlib.sha256(receipt.read_bytes()).hexdigest(), 'alcance': 'Coordenadas auxiliares, conectividad y pisos en guardado/reapertura; no cálculo ni piloto', 'aviso_observado': 'ETABS imprimió Cannot open file / BufferFileIn modelo.Y_ durante reapertura; llamadas retornaron0, geometria y pisos se releyeron; no hubo solver. No se oculta ni se afirma la causa del aviso.', 'no_aplicado_producto': True}
(ROOT / 'seguimiento/ENSAYO_COTAS_AUXILIARES_257.json').write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'estado': out['estado'], 'controles': len(checks), 'fallos': [c['control'] for c in checks if not c['pasa']]}))
raise SystemExit(0 if out['estado'] == 'verificado_sintetico' else 1)
