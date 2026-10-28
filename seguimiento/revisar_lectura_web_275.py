"""Revisión focal de recibos/valores archivados; no reemplaza revalidación completa."""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from draft2model.lectura_analisis import LectorAnalisis

case = ROOT / 'data/private/pueblo-libre-002'
web = case / 'trabajos_lecturas/f56fdeaffd5142379d3350c4527854a3'
tracked = {}

def raw(path):
    data = path.read_bytes()
    tracked[path] = data
    return data

def read(path):
    return json.loads(raw(path))

def sha(data):
    return hashlib.sha256(data).hexdigest()

prep = read(web / 'preparacion.json')
webproof = read(web / 'evidencia_analisis.json')
assert sha(tracked[web / 'evidencia_analisis.json']) == prep['sha256_evidencia']
assert raw(web / 'expediente.json') == raw(case / 'expediente.json')
assert sha(tracked[case / 'expediente.json']) == prep['expediente_sha256'] == prep['sha256_expediente']
accepted = read(web / 'aceptacion_web.json')
folder = case / 'lecturas_etabs' / accepted['lectura_id']
for name, digest in accepted['archivos'].items():
    assert name in {'solicitud.json', 'respuesta.json', 'aceptacion_lectura.json', 'evidencia_analisis.json'}
    assert sha(raw(folder / name)) == digest, name
assert set(accepted['archivos']) == {'solicitud.json', 'respuesta.json', 'aceptacion_lectura.json', 'evidencia_analisis.json'}
request = read(folder / 'solicitud.json')
response = read(folder / 'respuesta.json')
receipt = read(folder / 'aceptacion_lectura.json')
assert read(folder / 'evidencia_analisis.json') == webproof
analysis = case / 'analisis_etabs' / prep['analisis']
assert sha(raw(analysis / 'aceptacion_analisis.json')) == webproof['sha256_aceptacion']
assert sha(raw(analysis / 'analizado.edb')) == webproof['sha256_edb_analizado']
assert receipt['aceptada'] is True and receipt['instancia_nueva_cerrada'] is True
assert receipt['modo'] == 'real' and receipt['analisis_ejecutado'] is False
assert receipt['sha256_solicitud'] == sha(tracked[folder / 'solicitud.json'])
assert receipt['sha256_respuesta'] == sha(tracked[folder / 'respuesta.json'])
assert receipt['corrida_analisis_id'] == request['corrida_analisis_id'] == prep['analisis']
assert request['sha256_edb'] == receipt['sha256_edb'] == webproof['sha256_edb_analizado']
assert request['casos'] == prep['casos'] == receipt['casos']
assert request['tablas'] == prep['tablas']
LectorAnalisis._comprobar_datos(SimpleNamespace(contenido=request), response['datos'])
tables = {t['clave']: t for t in response['datos']['tablas']}
assert set(tables) == set(prep['tablas'])
modal = tables['Modal Participating Mass Ratios']['filas']
assert len(modal) == 12
last = max(modal, key=lambda row: int(row['Mode']))
assert float(last['SumUX']) >= .9 and float(last['SumUY']) >= .9
prior_reactions = next((case / 'lecturas_analisis').glob('74d78008*/respuesta.json'))
prior_modal = next((case / 'lecturas_analisis').glob('ddcf*/respuesta.json'))
older_reactions = next(t for t in read(prior_reactions)['datos']['tablas'] if t['clave'] == 'Base Reactions')['filas']
older_modal = next(t for t in read(prior_modal)['datos']['tablas'] if t['clave'] == 'Modal Participating Mass Ratios')['filas']
schema_differences = []
for name in ('CM', 'CAGUA'):
    new = [row for row in tables['Base Reactions']['filas'] if row['OutputCase'] == name]
    old = [row for row in older_reactions if row['OutputCase'] == name]
    assert len(new) == len(old) == 1, name
    a, b = new[0], old[0]
    assert set(b) <= set(a) and set(a)-set(b) <= {'StepNumber'}
    assert all(a[k] == b[k] for k in b), name
    assert all(a[k] is None for k in set(a)-set(b)), name
    schema_differences.append({'caso':name, 'campos_adicionales_web':{k:a[k] for k in set(a)-set(b)}})
assert modal == older_modal
assert all(path.read_bytes() == data for path, data in tracked.items())
report = {
    'fecha_utc': datetime.now(timezone.utc).isoformat(),
    'trabajo_web': web.name, 'lectura': folder.name,
    'analisis': prep['analisis'], 'sha256_edb': webproof['sha256_edb_analizado'],
    'recibos_y_enlaces_revisados': True, 'fuentes_estables': True,
    'casos': prep['casos'], 'filas_por_tabla': {k: len(t['filas']) for k,t in tables.items()},
    'participacion_ultimo_modo': {k: last[k] for k in ('Mode', 'SumUX', 'SumUY', 'SumRZ')},
    'coincidencia_lecturas_previas': ['CM: todos los campos de la lectura anterior', 'CAGUA: todos los campos de la lectura anterior', 'modal: 12 filas completas'],
    'diferencias_esquema': schema_differences,
    'fuentes_sha256': {str(p.relative_to(ROOT)): sha(b) for p,b in tracked.items()},
    'alcance': 'Revisión focal independiente de integridad y valores conservados de lectura web real. No invoca verificar_analisis_aceptado ni sustituye su revalidación completa, controles finales o QA del navegador. Cierre de instancia respaldado por recibos, sin observación propia del PID.',
    'etabs_ejecutado': False, 'api_remota': False, 'goal_completo': False,
}
(ROOT / 'seguimiento/REVISION_LECTURA_WEB_275.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({k: report[k] for k in ('lectura', 'recibos_y_enlaces_revisados', 'fuentes_estables', 'participacion_ultimo_modo')}, ensure_ascii=False))
