"""Verificación offline de runtime285 en entorno nuevo; no ejecuta ETABS/APIs."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'tmp/runtime_qa_285'
DEST = ROOT / 'tmp/instalacion_limpia_287'
MANIFEST = RUNTIME / 'RUNTIME_MANIFIESTO.json'


def hashes():
    data = json.loads(MANIFEST.read_text(encoding='utf-8'))
    observed = {name: hashlib.sha256((RUNTIME / name).read_bytes()).hexdigest()
                for name in data['archivos']}
    if observed != data['archivos']:
        raise RuntimeError('La copia fija difiere de su manifiesto.')
    return data['huella_fuentes']


def main():
    before = hashes()
    DEST.mkdir(exist_ok=False)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PIP_NO_INDEX='1',
               PIP_DISABLE_PIP_VERSION_CHECK='1', PIP_CONFIG_FILE=os.devnull)
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    python = DEST / '.venv/Scripts/python.exe'
    commands = [
        [sys.executable, '-m', 'venv', str(DEST / '.venv')],
        [str(python), '-m', 'pip', 'install', '--no-index', '--find-links',
         str(ROOT / 'tmp/wheels_clean_001'), '--require-hashes',
         '-r', str(RUNTIME / 'requirements-win-py310.lock')],
        [str(python), '-m', 'pip', 'check'],
        [str(python), '-m', 'draft2model', '--help'],
        [str(python), '-m', 'draft2model.revision_visual', '--help'],
        [str(python), '-c',
         'import sys, draft2model, PIL, pymupdf; '
         'print(sys.version); print(sys.executable); '
         'print(draft2model.__file__); print(PIL.__version__); '
         'print(pymupdf.VersionBind)'],
    ]
    steps = []
    for number, command in enumerate(commands, 1):
        start = datetime.datetime.now(datetime.timezone.utc)
        run = subprocess.run(command, cwd=RUNTIME, env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log = DEST / f'paso_{number}.log'
        log.write_bytes(run.stdout)
        steps.append({'argv': command, 'exit_code': run.returncode,
                      'log': str(log.relative_to(ROOT)),
                      'segundos': (datetime.datetime.now(datetime.timezone.utc)-start).total_seconds()})
        print(f'Paso{number}: exit{run.returncode}', flush=True)
        if run.returncode:
            break
    after = hashes()
    result = {'fecha_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'runtime': str(RUNTIME.relative_to(ROOT)), 'huella_fuentes': before,
              'fuentes_estables': before == after, 'pasos': steps,
              'correcto': len(steps) == len(commands) and all(s['exit_code'] == 0 for s in steps),
              'etabs_ejecutado': False, 'api_remota': False, 'goal_completo': False,
              'alcance': 'Instalacion offline y entrada CLI de la copia fija285; no es paquete final ni prueba de todas las integraciones.'}
    (ROOT / 'seguimiento/REVISION_INSTALACION_287.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return 0 if result['correcto'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
