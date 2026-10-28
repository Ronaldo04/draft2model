"""Contraste independiente de recibos sintéticos; no invoca ETABS ni producto."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'tmp/ensayo_masa_contenido_251'


def load(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def main():
    receipt = BASE / 'runs/codex253f/registro.json'
    d = load(receipt)
    checks = []

    def check(name, ok):
        checks.append({'control': name, 'pasa': bool(ok)})

    def near(a, b):
        return type(a) in (int, float) and math.isfinite(a) and math.isclose(a, b, rel_tol=1e-5, abs_tol=1e-7)

    check('recibo final y ensayo sintetico', d['status'] == 'verified' and d['synthetic_test'] is True and bool(d['finished_utc']))
    check('todos retornos nativos0', bool(d['api_calls']) and all(type(c['return_code']) is int and c['return_code'] == 0 for c in d['api_calls']))
    check('cierre y aislamiento', d['close_code'] == 0 and d['owned_instance_closed'] is True and d['owned_pid_absent'] is True and sorted(d['preexisting_instances']) == sorted(d['remaining_preexisting']))
    check('script sin cambios desde ejecucion', hashlib.sha256((BASE / 'ensayar_masa_contenido.ps1').read_bytes()).hexdigest() == d['script_sha256'])
    calibrations = d['gravity_calibration']
    g = calibrations[0]['W_kN_m3'] / calibrations[0]['M_kN_s2_m4']
    check('gravedad previa por dos materiales no asignados', len(calibrations) == 2 and all(c['material_assigned_to_objects'] is False and near(c['W_kN_m3'], expected) and near(c['W_kN_m3'] / c['M_kN_s2_m4'], g) for c, expected in zip(calibrations, (1, 2))) and near(g, 9.80665))
    # Oraculo fisico de esta caja, independiente de campos geometry/expected_mass.
    weight = 2 * 2.15 * 2.22 * 10
    check('tres controles completos', [p['id'] for p in d['phases']] == ['SIN_AGUA', 'AGUA_025', 'AGUA_100'] and len(d['mass_reads']) == 3)
    totals = []
    for phase, raw, factor, pattern in zip(d['phases'], d['mass_reads'], (0, .25, 1), ('NEUTRO', 'AGUA', 'AGUA')):
        label = phase['id']
        n = raw['number_results']
        fields = ('point_elements', 'mass_sources', 'U1', 'U2', 'U3', 'R1', 'R2', 'R3')
        lengths_ok = type(n) is int and n > 0 and all(len(raw[f]) in (n, n + 1) for f in fields)
        tails_ok = all(len(raw[f]) == n or raw[f][n] in (None, '') for f in fields[:2]) and all(len(raw[f]) == n or raw[f][n] == 0 for f in fields[2:])
        check(label + '/matrices y cola neutra', lengths_ok and tails_ok)
        check(label + '/estado final', phase['status'] == 'verified' and phase['error'] is None)
        for key in ('source_before', 'source_after'):
            s = phase[key]
            sf = 1 if pattern == 'NEUTRO' else factor
            check(label + '/' + key, s['include_elements'] is False and s['include_added'] is False and s['include_loads'] is True and s['number_loads'] == 1 and s['patterns'] == [pattern] and s['factors'] == [sf])
        total_x, total_y = sum(raw['U1'][:n]), sum(raw['U2'][:n])
        totals.append(total_x)
        check(label + '/masaXY desde crudos', near(total_x, weight * factor / g) and near(total_y, weight * factor / g))
        rows = phase['assembled']['rows']
        check(label + '/filas sin duplicados ni otra fuente', len(rows) == n and len({(r['point_element'], r['mass_source']) for r in rows}) == n and len(set(raw['mass_sources'][:n])) == 1 and all(r['mass_source'] for r in rows))
        check(label + '/filas ligadas a matrices crudas', all(r['point_element'] == raw['point_elements'][i] and r['mass_source'] == raw['mass_sources'][i] and all(r[field] == raw[field][i] for field in fields[2:]) for i, r in enumerate(rows)))
        check(label + '/ejes y masas finitas', all(r['point_axes_deg'] == [0, 0, 0] and all(math.isfinite(r[f]) and r[f] >= -1e-9 for f in ('U1', 'U2', 'U3')) for r in rows))
        if total_x > 0:
            centroid = [sum(r['global_xyz'][k] * r['U1'] for r in rows) / total_x for k in range(3)]
            check(label + '/centroide desde filas', all(near(a, b) for a, b in zip(centroid, (1, 1.075, 3))))
            check(label + '/masa positiva en fondo idealizado', all(near(r['global_xyz'][2], 3) for r in rows if r['U1'] > 1e-8))
        check(label + '/reaccion estatica independiente', phase['reaction']['load_case'] == 'AGUA' and near(phase['reaction']['FZ_kN'], weight))
    if len(totals) == 3:
        check('deltas0/25/100', near(totals[2] - totals[0], weight / g) and near(totals[1] - totals[0], weight / (4*g)) and near(totals[2] - totals[0], 4*(totals[1] - totals[0])))
    check('tres EDB propios con hashes', len(d['edb_files']) == 3 and all(Path(e['path']).is_file() and Path(e['path']).parent == receipt.parent and e['created_by_this_run'] is True and hashlib.sha256(Path(e['path']).read_bytes()).hexdigest() == e['sha256'] for e in d['edb_files']))
    failures = []
    for name in 'abcde':
        folder = BASE / ('runs/codex253' + name)
        candidates = [(p, load(p)) for p in folder.glob('*.json')]
        finals = [(p, x) for p, x in candidates if x.get('finished_utc')]
        if len(finals) == 1:
            p, x = finals[0]
            failures.append({'corrida': name, 'recibo': str(p.relative_to(ROOT)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'estado': x['status'], 'error': x['error'], 'cierre0': x['close_code'] == 0, 'pid_ausente': x['owned_pid_absent']})
    out = {'estado': 'verificado_sintetico' if all(c['pasa'] for c in checks) else 'no_verificado', 'recibo': str(receipt.relative_to(ROOT)), 'recibo_sha256': hashlib.sha256(receipt.read_bytes()).hexdigest(), 'comprobaciones': checks, 'gravedad_observada_m_s2': g, 'peso_oraculo_kn': weight, 'masas_crudas_X': totals, 'fallos_previos_conservados': failures, 'limites': ['Caja sintetica con carga uniforme en fondo, no piloto', 'Masa distribuida en plano del fondoZ3, no centroide real del aguaZ4.11 ni hidrodinamica', 'No conecta biblioteca250 al contrato/plan/lector/UI', 'No valida presiones caras mojadas ni geometria del tanque real']}
    (ROOT / 'seguimiento/REVISION_MASA_NATIVA_253.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'estado': out['estado'], 'controles': len(checks), 'fallos': [c['control'] for c in checks if not c['pasa']], 'masas': totals}))
    raise SystemExit(0 if out['estado'] == 'verificado_sintetico' else 1)


if __name__ == '__main__':
    main()
