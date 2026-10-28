"""Reintento HTTP focal sin reinstalar ni repetir la demo ya verificada."""
import json
import argparse
import os
from pathlib import Path
import socket
import subprocess
import time
from urllib.request import build_opener, ProxyHandler

root = Path(__file__).resolve().parents[1]
base = root / 'tmp/validacion_paquete_258'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--intento', choices=('reintento', 'host'), default='reintento')
attempt = parser.parse_args().intento
installation = json.loads((base / 'instalacion/verificacion.json').read_bytes())
if installation.get('completa') is not True:
    raise ValueError('La instalación anterior no está verificada')
report = {'estado': 'iniciado', 'reutiliza_instalacion_verificada': True, 'etabs': False, 'apis_remotas': 0}
env = dict(os.environ, PYTHONIOENCODING='utf-8')
for name in ('PYTHONHOME', 'PYTHONPATH', 'OPENAI_API_KEY', 'GEMINI_API_KEY', 'GOOGLE_API_KEY'):
    env.pop(name, None)
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
opener = build_opener(ProxyHandler({}))
with (base / ('http_' + attempt + '.log')).open('xb') as log:
    server = subprocess.Popen([str(base / 'instalacion/v/Scripts/python.exe'), '-m',
        'draft2model.revision_visual', '--raiz', str(base / 'expedientes_nuevos'), '--puerto', str(port),
        '--sin-navegador'], cwd=base / 'fuentes', env=env, stdout=log, stderr=log)
    try:
        errors = []
        for _ in range(100):
            if server.poll() is not None:
                raise RuntimeError('Servidor terminado; consultar log propio')
            try:
                with opener.open(f'http://127.0.0.1:{port}/', timeout=2) as response:
                    raw = response.read()
                    if response.status != 200 or b'<html' not in raw.lower():
                        raise ValueError('Inicio HTTP incorrecto')
                    (base / 'inicio.html').write_bytes(raw)
                    report.update(estado='arranque_http_verificado', codigo=response.status, bytes=len(raw))
                break
            except OSError as error:
                if len(errors) < 3:
                    errors.append(str(error))
                time.sleep(.2)
        else:
            raise RuntimeError('Sin respuesta HTTP: ' + repr(errors))
    except Exception as error:
        report.update(estado='fallido', error=str(error))
    finally:
        server.terminate()
        server.wait(timeout=15)
        report['servidor_propio_cerrado'] = server.poll() is not None
(base / ('http_' + attempt + '.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps(report))
raise SystemExit(int(report['estado'] == 'fallido'))
