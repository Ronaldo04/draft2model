"""Validación acotada de la distribución258: instalación/demo/HTTP, no piloto."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'entregas/AECODE_CANDIDATO_258'
OUT = ROOT / 'tmp/validacion_paquete_258'


def main():
    OUT.mkdir(exist_ok=False)
    source = OUT / 'fuentes'
    source.mkdir()
    manifest = json.loads((PACKAGE / 'MANIFIESTO.json').read_bytes())
    report = {'fecha_utc': datetime.now(timezone.utc).isoformat(), 'estado': 'iniciado',
              'huella_fuentes': manifest['huella_fuentes'], 'piloto_verificado': False,
              'apis_remotas': 0, 'etabs_ejecutado': False, 'comprobaciones': []}
    def check(name, value):
        report['comprobaciones'].append({'nombre': name, 'correcta': bool(value)})
        if not value:
            raise ValueError(name)
    try:
        archive = PACKAGE / manifest['zip']
        check('zip_sha', hashlib.sha256(archive.read_bytes()).hexdigest() == manifest['zip_sha256'])
        with zipfile.ZipFile(archive) as z:
            check('inventario', set(z.namelist()) == set(manifest['archivos']))
            for name, digest in manifest['archivos'].items():
                target = (source / name).resolve()
                if not target.is_relative_to(source.resolve()):
                    raise ValueError('Ruta fuera de copia')
                raw = z.read(name)
                if hashlib.sha256(raw).hexdigest() != digest:
                    raise ValueError('Hash incorrecto: ' + name)
                target.parent.mkdir(exist_ok=True, parents=True)
                target.write_bytes(raw)
        check('sin_datos_heredados', not (source / 'tmp').exists() and not (source / 'data').exists())
        env = dict(os.environ, PYTHONIOENCODING='utf-8', PIP_NO_INDEX='1')
        for key in ('PYTHONHOME', 'PYTHONPATH', 'OPENAI_API_KEY', 'GEMINI_API_KEY', 'GOOGLE_API_KEY'):
            env.pop(key, None)
        result = subprocess.run([sys.executable, 'scripts/verificar_instalacion_limpia.py',
                                 '--wheels', 'wheels', '--salida', str(OUT / 'instalacion')],
                                cwd=source, env=env, capture_output=True, timeout=500)
        (OUT / 'instalacion.log').write_bytes(result.stdout + result.stderr)
        check('instalacion_codigo', result.returncode == 0)
        installation = json.loads((OUT / 'instalacion/verificacion.json').read_bytes())
        report['instalacion'] = installation
        check('instalacion_seis_pasos', installation.get('completa') is True and
              len(installation['comprobaciones']) == 6 and installation.get('corridas_completadas') == 6)
        python = OUT / 'instalacion/v/Scripts/python.exe'
        probe = subprocess.run([str(python), '-c',
            'import json,sys,site,draft2model;print(json.dumps(dict(archivo=draft2model.__file__,aislado=sys.prefix!=sys.base_prefix,user_site=site.ENABLE_USER_SITE)))'],
            cwd=source, env=env, capture_output=True, check=True, timeout=30)
        runtime = json.loads(probe.stdout)
        report['entorno'] = runtime
        check('importacion_copia_aislada', runtime['aislado'] and not runtime['user_site'] and
              Path(runtime['archivo']).resolve().is_relative_to(source.resolve()))
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        with (OUT / 'http.log').open('wb') as log:
            server = subprocess.Popen([str(python), '-m', 'draft2model.revision_visual',
                '--raiz', str(OUT / 'expedientes_nuevos'), '--puerto', str(port), '--sin-navegador'],
                cwd=source, env=env, stdout=log, stderr=log)
            try:
                page = None
                for _ in range(50):
                    if server.poll() is not None:
                        raise ValueError('Servidor terminó antes de responder')
                    try:
                        with urlopen(f'http://127.0.0.1:{port}/', timeout=1) as response:
                            page = response.read()
                            check('http_inicio', response.status == 200 and b'<html' in page.lower())
                        break
                    except OSError:
                        time.sleep(.2)
                check('servidor_responde', page is not None)
                (OUT / 'inicio.html').write_bytes(page)
            finally:
                # Solo proceso creado aquí; no se buscan ni terminan otras instancias.
                server.terminate()
                server.wait(timeout=15)
                report['servidor_propio_cerrado'] = server.poll() is not None
        report['estado'] = 'instalacion_demo_y_arranque_http_verificados'
        report['limites'] = ['Sin revisión visual del navegador', 'Sin llamadas reales de visión',
                            'Sin ETABS ni análisis del caso real', 'No es aceptación global']
    except Exception as error:
        report['estado'] = 'fallido'
        report['error'] = str(error)
    finally:
        (OUT / 'verificacion.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'estado': report['estado'], 'huella_fuentes': report['huella_fuentes'],
                      'comprobaciones': len(report['comprobaciones']), 'piloto_verificado': False}))
    return int(report['estado'] == 'fallido')


if __name__ == '__main__':
    raise SystemExit(main())
