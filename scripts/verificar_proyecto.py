"""Comprobaciones locales reproducibles sin red, sin ETABS y sin secretos."""
import argparse
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
from datetime import datetime, timezone


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida', type=Path, default=Path('tmp/verificacion_local.json'))
    parser.add_argument('--temporales', type=Path, help='Carpeta de temporales corta para procesos Windows.')
    parser.add_argument('--node', type=Path, help='Ejecutable Node.js para las pruebas de interfaz; por defecto se busca node en PATH.')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    # Cada informe conserva sus propios logs; otro ensayo no los reemplaza.
    work = root / 'tmp' / 'verificacion' / uuid4().hex
    work.mkdir(parents=True, exist_ok=True)
    temporaries=args.temporales.resolve() if args.temporales else work
    temporaries.mkdir(parents=True,exist_ok=True)
    env = dict(os.environ, TEMP=str(temporaries), TMP=str(temporaries), PYTHONIOENCODING='utf-8')
    checks = []
    def huellas():
        return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                for folder in ('draft2model', 'tests', 'scripts', 'seguimiento', 'examples')
                for path in (root / folder).rglob('*')
                if path.is_file() and path.suffix in ('.py', '.js', '.json', '.html', '.css', '.ps1', '.cjs', '.zip')
                and '__pycache__' not in path.parts}
    before = huellas()
    commands = [
        ('dependencias', [sys.executable, '-m', 'pip', 'check']),
        ('arranque_cli', [sys.executable, '-m', 'draft2model', '--help']),
    ]
    # Poder iniciar powershell.exe o compilar con Add-Type no acredita que el
    # host permita ejecutar un .ps1. Probar -File sin cambiar ninguna política.
    marker = 'DRAFT2MODEL_SONDA_PS51_FILE_OK'
    if os.name == 'nt':
        powershell = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        probe = work / 'sonda_powershell.ps1'
        probe.write_text("Write-Output '"+marker+"'\n", encoding='utf-8-sig')
        commands.append(('powershell_scripts', [str(powershell), '-NoProfile', '-NonInteractive', '-File', str(probe)]))
    commands.append(('suite', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v']))
    frontend_tests = sorted((root/'tests').glob('*frontend.cjs'))
    if frontend_tests:
        node = str(args.node.resolve()) if args.node else (shutil.which('node') or 'node')
        commands.append(('interfaz', [node, '--test', '--test-reporter=tap',
                                     *[str(path.relative_to(root)) for path in frontend_tests]]))
    for name, command in commands:
        # Presupuesto de observación (no relaja pruebas): la suite de la ruta 201 incluye puentes dobles PowerShell lentos.
        timeout=3000 if name=='suite' else 300 if name=='interfaz' else 60
        try:
            run = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            def texto(value):
                return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else (value or '')
            run = subprocess.CompletedProcess(command, 124, texto(exc.stdout), texto(exc.stderr)+f'\nComprobación agotó {timeout} s; no se acredita.\n')
        except OSError as exc:
            run = subprocess.CompletedProcess(command, 127, '', f'No se pudo iniciar la comprobación: {exc}\n')
        if name == 'powershell_scripts' and run.returncode == 0 and marker not in run.stdout.splitlines():
            run = subprocess.CompletedProcess(command, 126, run.stdout,
                run.stderr+'\nLa sonda -File no confirmó ejecución; no se acredita PowerShell.\n')
        log = work / (name + '.log')
        log.write_text(run.stdout + run.stderr, encoding='utf-8')
        omitted = [line for line in (run.stdout + run.stderr).splitlines()
                   if ' ... skipped ' in line or line.startswith("skipped '")
                   or (name == 'interfaz' and (re.search(r'^# skipped [1-9][0-9]*\s*$', line)
                                              or re.search(r'\s#\s*(SKIP|TODO)\b', line, re.I)
                                              or re.search(r'^# todo [1-9][0-9]*\s*$', line)))]
        checks.append({'nombre': name, 'comando': command, 'codigo': run.returncode,
                       'registro': str(log.relative_to(root)),
                       'omisiones': omitted})
    output = root / args.salida
    output.parent.mkdir(parents=True, exist_ok=True)
    stable = before == huellas()
    complete=stable and not any(check['codigo'] or check['omisiones'] for check in checks)
    environment_blocks = [{'comprobacion': check['nombre'], 'codigo': check['codigo'], 'registro': check['registro'],
                           'motivo': 'Windows PowerShell 5.1 no confirmó la ejecución de una sonda -File sin modificar políticas; revisar el log.'}
                          for check in checks if check['nombre'] == 'powershell_scripts' and check['codigo']]
    output.write_text(json.dumps({'fecha_utc': datetime.now(timezone.utc).isoformat(),
                                 'python': sys.version, 'comprobaciones': checks,
                                 'bloqueos_entorno': environment_blocks,
                                 'huellas_archivos': before,
                                 'archivos_estables_durante_ejecucion': stable,
                                 'validacion_local_completa': complete,
                                 'alcanza_validacion_piloto': False}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(output)
    return int(not complete)


if __name__ == '__main__':
    raise SystemExit(main())
