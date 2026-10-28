"""Diagnóstico de rutas/bloqueo en runtime292 fijo: nunca registra query, cuerpos o variables locales."""
from pathlib import Path
import functools
import json
import re
import sys
import threading
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'tmp/runtime_qa_292'
OUTPUT = ROOT / 'tmp/diagnostico_qa_293'
OUTPUT.mkdir(exist_ok=False)
sys.path.insert(0, str(RUNTIME))
from draft2model import revision_visual as rv

apps, active = [], {}
original_init = rv.RevisionLocal.__init__


@functools.wraps(original_init)
def init(self, *args, **kwargs):
    original_init(self, *args, **kwargs)
    apps.append(self)


def observe_get(original):
    @functools.wraps(original)
    def run(self):
        ident = threading.get_ident()
        active[ident] = (urlsplit(self.path).path, time.monotonic())
        try:
            return original(self)
        finally:
            active.pop(ident, None)
    return run


def snapshots():
    while True:
        try:
            now = time.monotonic()
            rows = {ident: {'ruta': route, 'segundos': round(now-start, 3)}
                    for ident, (route, start) in list(active.items())}
            owner, lock_description = None, None
            if apps:
                lock_description = repr(apps[0].lock)
                match = re.search(r'owner=(\d+)', lock_description)
                owner = int(match[1]) if match else None
            frame = sys._current_frames().get(owner)
            stack = []
            while frame is not None:
                source = Path(frame.f_code.co_filename)
                name = source.relative_to(RUNTIME).as_posix() if source.is_relative_to(RUNTIME) else source.name
                stack.append({'archivo': name, 'funcion': frame.f_code.co_name, 'linea': frame.f_lineno})
                frame = frame.f_back
            data = {'hora_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                    'solicitudes_activas': list(rows.values()), 'ruta_duena_del_lock': rows.get(owner),
                    'stack_dueno': stack[:20], 'owner_identificado': owner is not None}
            (OUTPUT / 'estado.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            with (OUTPUT / 'muestras.jsonl').open('a', encoding='utf-8') as f:
                f.write(json.dumps(data, ensure_ascii=False)+'\n')
        except Exception as exc:
            (OUTPUT / 'observacion_fallida.txt').write_text(type(exc).__name__, encoding='utf-8')
        time.sleep(10)


rv.RevisionLocal.__init__ = init
rv.ManejadorRevision.do_GET = observe_get(rv.ManejadorRevision.do_GET)
threading.Thread(target=snapshots, daemon=True).start()
if __name__ == '__main__':
    sys.argv = [__file__, '--raiz', str(ROOT/'data/private'), '--puerto', '18293', '--sin-navegador']
    raise SystemExit(rv.main())
