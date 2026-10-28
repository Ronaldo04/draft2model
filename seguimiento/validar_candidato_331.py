"""Congelar una versión integrada; ejecutar solo tras terminar la validación329."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[1]
base = root / 'tmp/validacion_distribucion_331'
source = base / 'fuentes'
state_path = base / 'estado.json'
changes = ('draft2model/coherencia_literal.py', 'draft2model/extraccion_preliminar.py',
 'draft2model/localizacion_literal_pdf.py', 'draft2model/revision_visual.py',
 'draft2model/revision_web/app.js', 'draft2model/revision_web/index.html',
 'tests/test_coherencia_literal.py', 'tests/test_localizacion_literal_pdf.py',
 'tests/test_localizacion_lectura_http.py', 'tests/revision_lecturas_semanticas_frontend.cjs',
 'docs/COHERENCIA_LITERAL_DE_COTAS.md', 'docs/LOCALIZACION_LITERAL_PDF.md', 'docs/GUIA_REPRODUCIBLE.md')

def save(state):
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

if sys.argv[1:] == ['--preparar']:
    assert not base.exists(), 'No reemplazar una validación existente.'
    base.mkdir()
    with zipfile.ZipFile(root/'entregas/AECODE_PRESENTACION_328/software/Draft2Model.zip') as archive:
        for name in archive.namelist():
            assert (source/name).resolve().is_relative_to(source.resolve()), name
        archive.extractall(source)
    for name in changes:
        (source/name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root/name, source/name)
    state = {'fecha_utc': datetime.now(timezone.utc).isoformat(), 'estado': 'preparado',
             'base': 'software325', 'goal_completo': False, 'publicado': False,
             'cambios': {n: hashlib.sha256((source/n).read_bytes()).hexdigest() for n in changes},
             'api_calls': 0, 'etabs_nativo_nuevo': False,
             'focales': ['tmp/coherencia_literal_329_tests.log:118 sin omisiones',
                         'tmp/localizacion_pdf_331_tests.log:38 sin omisiones',
                         'tmp/frontend_localizacion_331.log:36 sin omisiones'],
             'contraste_real': 'seguimiento/localizacion_331/contraste.json'}
    save(state)
    print('Candidato331 congelado; aún no ejecutado ni publicado.')
elif sys.argv[1:] == ['--ejecutar']:
    previous = json.loads((root/'tmp/validacion_distribucion_329/estado.json').read_text(encoding='utf-8'))
    assert previous['estado'] == 'terminado', 'Esperar proceso329; no ejecutar suites simultáneas.'
    state = json.loads(state_path.read_text(encoding='utf-8'))
    assert state['estado'] == 'preparado', 'No reiniciar ni duplicar una validación.'
    assert all(hashlib.sha256((source/n).read_bytes()).hexdigest() == h for n,h in state['cambios'].items())
    python = root/'tmp/validacion_distribucion_303/.venv/Scripts/python.exe'
    args = [str(python), '-X', 'utf8', 'scripts/verificar_proyecto.py', '--salida',
            str(base/'verificacion.json'), '--temporales', str(root/'tmp/t304')]
    state.update(estado='en_ejecucion', pid=os.getpid(), argv=args)
    save(state)
    with (base/'ejecucion.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(args, cwd=source, stdout=log, stderr=subprocess.STDOUT)
    state.update(estado='terminado', codigo=result.returncode)
    save(state)
    print(json.dumps(state, ensure_ascii=False))
    raise SystemExit(result.returncode)
else:
    raise SystemExit('Usar --preparar o --ejecutar.')
