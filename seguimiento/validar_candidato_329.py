"""Congela cuatro cambios sobre 325 y comprueba la copia; no publica entrega."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[1]
base = root / 'tmp/validacion_distribucion_329'
source = base / 'fuentes'
state_path = base / 'estado.json'
changes = ('draft2model/coherencia_literal.py', 'draft2model/extraccion_preliminar.py',
           'tests/test_coherencia_literal.py', 'docs/COHERENCIA_LITERAL_DE_COTAS.md')
assert not base.exists(), 'No reiniciar una comprobación existente.'
base.mkdir()
with zipfile.ZipFile(root / 'entregas/AECODE_PRESENTACION_328/software/Draft2Model.zip') as archive:
    for name in archive.namelist():
        target = (source / name).resolve()
        assert target.is_relative_to(source.resolve()), name
    archive.extractall(source)
for name in changes:
    dest = source / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / name, dest)
changed_hashes = {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in changes}
state = {'fecha_utc': datetime.now(timezone.utc).isoformat(), 'estado': 'en_ejecucion',
         'pid': os.getpid(), 'goal_completo': False, 'base': 'software325',
         'cambios': changed_hashes, 'focales': {'pruebas': 118, 'codigo': 0, 'omisiones': 0},
         'sin_apis': True, 'sin_etabs': True, 'publicado': False}
def save():
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
save()
python = root / 'tmp/validacion_distribucion_303/.venv/Scripts/python.exe'
assert python.is_file()
args = [str(python), '-X', 'utf8', 'scripts/verificar_proyecto.py', '--salida',
        str(base / 'verificacion.json'), '--temporales', str(root / 'tmp/t304')]
state['argv'] = args
save()
with (base / 'ejecucion.log').open('w', encoding='utf-8') as log:
    result = subprocess.run(args, cwd=source, stdout=log, stderr=subprocess.STDOUT)
state.update(estado='terminado', codigo=result.returncode,
             fuentes_cambiadas_intactas=all(hashlib.sha256((source/n).read_bytes()).hexdigest() == v
                                           for n, v in changed_hashes.items()))
save()
print(json.dumps(state, ensure_ascii=False))
raise SystemExit(result.returncode)
