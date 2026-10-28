"""Portado exclusivo de archivos nuevos revisados; no ejecuta ETABS."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'tmp/validador_masa_ensamblada_254'


def main():
    receipt_path = ROOT / 'tmp/ensayo_masa_contenido_251/runs/codex253f/registro.json'
    receipt_bytes = receipt_path.read_bytes()
    receipt_sha = hashlib.sha256(receipt_bytes).hexdigest()
    receipt = json.loads(receipt_bytes)
    fixture_bytes = (SRC / 'fixtures/extracto_sintetico_253f.json').read_bytes()
    fixture = json.loads(fixture_bytes)
    manifest = json.loads((SRC / 'fixtures/manifest.json').read_bytes())
    assert receipt['status'] == 'verified'
    assert fixture['provenance']['source_receipt_sha256'] == receipt_sha == manifest['source_receipt_sha256']
    assert hashlib.sha256(fixture_bytes).hexdigest() == manifest['sha256']
    assert len(fixture['controls']) == len(receipt['mass_reads']) == len(receipt['phases']) == 3
    calls = [c for c in receipt['api_calls'] if c['method'] == 'Results.AssembledJointMass_1']
    assert len(calls) == 3 and all(c['return_code'] == 0 for c in calls)
    g = receipt['gravity_calibration'][0]['W_kN_m3'] / receipt['gravity_calibration'][0]['M_kN_s2_m4']
    for c, r, p, fraction in zip(fixture['controls'], receipt['mass_reads'], receipt['phases'], (0, .25, 1)):
        assert c['id'] == p['id']
        assert all(c['raw'][k] == r[k] for k in ('number_results', 'point_elements', 'mass_sources', 'U1', 'U2', 'U3', 'R1', 'R2', 'R3'))
        assert c['observations']['rows'] == p['assembled']['rows']
        assert c['raw']['return_code'] == 0 and c['units'] == c['raw']['units'] == c['observations']['units'] == p['units']
        assert c['raw']['capture_id'] == c['observations']['capture_id'] and receipt_sha in c['raw']['capture_id']
        assert math.isclose(c['expected_mass'], 2*2.15*2.22*10*fraction/g, rel_tol=1e-12, abs_tol=1e-12)
    module = (SRC / 'validador_masa.py').read_bytes()
    test = (SRC / 'test_validador_masa.py').read_text(encoding='utf-8')
    assert test.count('from validador_masa import') == 1
    assert test.count('HERE = Path(__file__).resolve().parent') == 1
    test = test.replace('from validador_masa import', 'from draft2model.masa_ensamblada import')
    test = test.replace('HERE = Path(__file__).resolve().parent', 'HERE = Path(__file__).resolve().parent / "fixtures/masa_ensamblada_253f"')
    test = test.replace('HERE / "fixtures/extracto_sintetico_253f.json"', 'HERE / "extracto_sintetico_253f.json"')
    test = test.replace('HERE / "fixtures/manifest.json"', 'HERE / "manifest.json"')
    doc = (SRC / 'README.md').read_text(encoding='utf-8')
    doc = doc.replace('Preparado en una carpeta aislada. No modifica el producto ni archivos de Claude. No importa ETABS, no abre archivos, no usa red y no ejecuta análisis. `validador_masa.py` es la biblioteca; únicamente las pruebas leen el fixture local.', 'Biblioteca pura incorporada por Codex como archivo nuevo `draft2model/masa_ensamblada.py`, sin modificar los archivos que Claude integra. No importa ETABS, no abre archivos, no usa red y no ejecuta análisis. Únicamente las pruebas leen el fixture histórico local en `tests/fixtures/masa_ensamblada_253f/`.')
    doc = doc.replace('python -m unittest discover -s tmp/validador_masa_ensamblada_254 -p test_validador_masa.py -v', 'python -B -m unittest tests.test_masa_ensamblada -v')
    doc = doc.replace('Archivos listos para revisión y portado por el dueño del producto: módulo, pruebas, fixture y manifest.', 'Módulo, pruebas, fixture y manifest portados tras revisión de Codex; sus consumidores siguen pendientes.')
    targets = {
        'draft2model/masa_ensamblada.py': module,
        'tests/test_masa_ensamblada.py': test.encode('utf-8'),
        'tests/fixtures/masa_ensamblada_253f/extracto_sintetico_253f.json': fixture_bytes,
        'tests/fixtures/masa_ensamblada_253f/manifest.json': (SRC / 'fixtures/manifest.json').read_bytes(),
        'docs/MASA_ENSAMBLADA.md': doc.encode('utf-8'),
    }
    for target in targets:
        if (ROOT / target).exists():
            raise FileExistsError('No sobrescribir: ' + target)
    for target, data in targets.items():
        path = ROOT / target
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as f:
            f.write(data)
    out = {'estado': 'portado_pendiente_prueba_destino', 'responsable': 'Codex: archivos nuevos independientes', 'fuente_recibo_sha256': receipt_sha, 'fixture_contrastado_con_crudos_y_filas': True, 'archivos': [{'ruta': k, 'sha256': hashlib.sha256(v).hexdigest()} for k, v in targets.items()], 'limites': ['Validación de payload, no nueva ejecución nativa ni verificaciónEDB', 'Sin consumidores en contrato/plan/lector/UI; R249-02 permanece abierto', 'Sin edición de archivos existentes de Claude']}
    (ROOT / 'seguimiento/PORTADO_MASA_ENSAMBLADA_254.json').write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'portados': len(targets), 'fixture_ligado_a_recibo': receipt_sha}))


if __name__ == '__main__':
    main()
