"""Control local de evidencias; no ejecuta ETABS ni interpreta ingeniería."""
from __future__ import annotations

import argparse
import base64
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'tmp' / 'control_avance'
IGNORED = {'.git', '.venv', 'venv', '__pycache__', 'node_modules', 'tmp', 'output', 'runs',
           '.codex', '.agents', '.claude', '.aws', '.streamlit', '.vscode', '.idea', '.pytest_cache', '.mypy_cache', '.ruff_cache'}
SECRET_SUFFIXES = {'.pem', '.key', '.pfx', '.p12', '.db', '.sqlite', '.sqlite3', '.log', '.pyc'}
REPO = 'Ronaldo04/draft2model'


def now():
    return datetime.now(timezone.utc).isoformat()


def load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except FileNotFoundError:
        return default


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + secrets.token_hex(4) + '.tmp')
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def blob_file(path, size):
    digest = hashlib.sha1(b'blob ' + str(size).encode() + b'\0')
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def private_path(path):
    return path.startswith(('data/', 'planos_muestra/', 'models/generated/'))


def public_path(path):
    parts = Path(path).parts
    return bool(parts) and not any(p in IGNORED for p in parts) and not private_path(path) and not any(
        p.startswith('.env') or p == 'settings.local.json' for p in parts
    ) and Path(path).suffix.lower() not in SECRET_SUFFIXES


def scan(root, cache=None):
    """No sigue enlaces; originales privados se observan solo mediante huellas locales."""
    result, next_cache, errors = {}, {}, []
    cache = cache or {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED and not (Path(directory) / d).is_symlink())
        for name in sorted(files):
            p = Path(directory) / name
            rel = p.relative_to(root).as_posix()
            if p.is_symlink() or name.startswith('.env') or p.suffix.lower() in SECRET_SUFFIXES:
                continue
            if name in {'Thumbs.db', '.DS_Store'}:
                continue
            try:
                st = p.stat()
                signature = (st.st_mtime_ns, st.st_size, st.st_ctime_ns)
                previous = cache.get(rel)
                sha = previous[1] if previous and previous[0] == signature else blob_file(p, st.st_size)
                end = p.stat()
                if signature != (end.st_mtime_ns, end.st_size, end.st_ctime_ns):
                    errors.append(rel if not private_path(rel) else 'archivo privado en modificación')
                    continue
                result[rel] = sha
                next_cache[rel] = (signature, sha)
            except OSError:
                errors.append(rel if not private_path(rel) else 'archivo privado no legible')
    return result, next_cache, errors


def diff(before, after):
    return [{'path': p, 'kind': 'nuevo' if p not in before else 'eliminado' if p not in after else 'modificado'}
            for p in sorted(before.keys() | after.keys()) if before.get(p) != after.get(p)]


def evaluate(catalog, files, proof=None, reviews=None, meta=None):
    """Solo cuenta criterios con evidencia vigente; existencia de código no basta."""
    proof, reviews, meta = proof or {}, reviews or [], meta or {}
    rows = []
    for milestone in catalog['milestones']:
        criteria = []
        for rule in milestone['criteria']:
            paths = rule.get('files', [])
            present = [p for p in paths if p in files]
            state, reason, evidence = 'pendiente', rule.get('pending', 'Falta implementar o aportar evidencia.'), []
            if present:
                state, reason = 'en_desarrollo', 'Hay archivos relacionados; falta completar la entrega.'
            if paths and len(present) == len(paths):
                state, reason = 'implementado', 'Archivos presentes. Aún falta una comprobación vigente del criterio.'
            tests = rule.get('tests', [])
            check_paths = rule.get('check_files', paths)
            matches = bool(check_paths) and all(p in files and files[p] == proof.get('files', {}).get(p) for p in check_paths)
            tested = bool(tests) and all(proof.get('modules', {}).get(t, {}).get('passed', False) and
                                         proof.get('modules', {}).get(t, {}).get('count', 0) > 0 for t in tests)
            skipped = [x for x in proof.get('skipped', []) if x['module'] in tests]
            if state == 'implementado' and matches and skipped:
                reason = f"Hay {len(skipped)} pruebas omitidas en este entorno; su comprobación sigue pendiente."
            if state == 'implementado' and matches and tested:
                state, reason = 'verificado', 'Pruebas aprobadas sobre estos archivos exactos; no implica aprobación de ingeniería.'
                evidence.append({'kind': 'pruebas', 'date': proof.get('finished'), 'tests': sum(proof['modules'][t]['count'] for t in tests)})
            for review in reviews:
                hashes = review.get('files', {})
                if (review.get('criterion') == rule['id'] and review.get('reviewer') and review.get('date') and
                    review.get('note') and hashes and all(files.get(p) == h for p, h in hashes.items()) and
                    all(p in hashes for p in paths)):
                    state, reason = 'verificado', review['note']
                    evidence.append({'kind': 'revision_declarada', 'reviewer': review['reviewer'], 'date': review['date']})
            probe = rule.get('probe')
            if probe and meta.get(probe) is True:
                state, reason = 'verificado', 'Comprobación directa de metadatos de GitHub en la fecha de consulta.'
                evidence.append({'kind': 'github', 'date': meta.get('checked_at')})
            if rule.get('blocker') and state == 'pendiente':
                state, reason = 'bloqueado', rule['blocker']
            criteria.append({**rule, 'state': state, 'reason': reason, 'evidence': evidence,
                             'present': present, 'missing': [p for p in paths if p not in files]})
        done = sum(c['state'] == 'verificado' for c in criteria)
        rows.append({**milestone, 'criteria': criteria, 'done': done, 'total': len(criteria),
                     'percent': round(100 * done / len(criteria)) if criteria else 0})
    total = sum(m['total'] for m in rows)
    done = sum(m['done'] for m in rows)
    return {'milestones': rows, 'done': done, 'total': total, 'percent': round(100 * done / total) if total else 0}


def credential():
    for name in ('GH_TOKEN', 'GITHUB_TOKEN'):
        if os.environ.get(name):
            return os.environ[name], 'variable de entorno'
    if shutil.which('gh'):
        try:
            r = subprocess.run(['gh', 'auth', 'token', '--hostname', 'github.com'], capture_output=True, text=True, timeout=8)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip(), 'GitHub CLI'
        except (OSError, subprocess.TimeoutExpired):
            pass
    if shutil.which('git'):
        try:
            r = subprocess.run(['git', 'credential', 'fill'], input=f'protocol=https\nhost=github.com\npath={REPO}.git\n\n',
                               capture_output=True, text=True, timeout=8,
                               env={**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GCM_INTERACTIVE': 'Never'})
            values = dict(line.split('=', 1) for line in r.stdout.splitlines() if '=' in line)
            if r.returncode == 0 and values.get('password'):
                return values['password'], 'administrador de credenciales Git'
        except (OSError, subprocess.TimeoutExpired):
            pass
    return None, None


def api(path, token):
    req = Request('https://api.github.com/repos/' + REPO + '/' + path, headers={
        'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'Draft2Model-control-local'})
    with urlopen(req, timeout=15) as response:
        return json.load(response)


def remote_snapshot(token):
    repo = api('', token)
    branch_name = repo['default_branch']
    branch = api('branches/' + quote(branch_name, safe=''), token)
    sha = branch['commit']['sha']
    tree = api('git/trees/' + branch['commit']['commit']['tree']['sha'] + '?recursive=1', token)
    if tree.get('truncated'):
        raise ValueError('GitHub devolvió un árbol incompleto; se conserva la lectura anterior.')
    files = {x['path']: x['sha'] for x in tree['tree'] if x['type'] == 'blob' and public_path(x['path'])}
    reviews = []
    # Solo datos JSON, nunca se descarga ni ejecuta código remoto.
    for path in ('seguimiento/evidencias.json',):
        if path in files:
            obj = api('contents/' + path + '?ref=' + sha, token)
            if obj.get('encoding') == 'base64':
                reviews = json.loads(base64.b64decode(obj['content'])).get('reviews', [])
    # La rama puede avanzar durante la consulta; el snapshot queda fijado al SHA leído.
    return {'repository': REPO, 'branch': branch_name, 'sha': sha, 'files': files, 'reviews': reviews,
            'checked_at': now(), 'source': 'API GitHub',
            'meta': {'private_repository': repo.get('private') is True,
                     'issues_enabled': repo.get('has_issues') is True,
                     'pages_disabled': repo.get('has_pages') is False}}


class Controller:
    def __init__(self, root=ROOT, state=STATE):
        self.root, self.state_dir = Path(root), Path(state)
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.cache = {}
        self.files = {}
        self.events = load(self.state_dir / 'activity.json', [])
        self.proof = load(self.state_dir / 'tests.json', {})
        self.remote = load(self.state_dir / 'github.json', {})
        self.remote_error = None
        self.remote_mode = 'snapshot'
        self.token = None
        self.auth_source = None
        self.testing = False
        self.pending_tests = False
        self.tests_due = 0
        self.github_due = 0
        self.scan_errors = []
        self.last_scan = None
        self.secret = secrets.token_urlsafe(32)
        self.last_result = load(self.state_dir / 'criteria.json', {})

    def record_progress(self):
        catalog = load(self.root / 'seguimiento/hitos.json')
        reviews = load(self.root / 'seguimiento/evidencias.json', {'reviews': []})['reviews']
        result = evaluate(catalog, self.files, self.proof, reviews)
        current = {c['id']: c['state'] for m in result['milestones'] for c in m['criteria']}
        for criterion, state in current.items():
            previous = self.last_result.get(criterion)
            if previous and previous != state:
                self.event('criterio', f"{criterion}: {previous} → {state}", criteria=[criterion],
                           interpretation='Avance comprobado.' if state == 'verificado' else
                           'Comprobación invalidada; requiere nueva evidencia.' if previous == 'verificado' else 'Estado actualizado según evidencia disponible.')
        self.last_result = current
        save(self.state_dir / 'criteria.json', current)

    def event(self, kind, message, **extra):
        self.events.insert(0, {'date': now(), 'kind': kind, 'message': message, **extra})
        self.events = self.events[:500]
        save(self.state_dir / 'activity.json', self.events)

    def scan_once(self):
        files, cache, errors = scan(self.root, self.cache)
        old = load(self.state_dir / 'inventory.json', None) if not self.files else self.files
        changes = diff(old, files) if old is not None else []
        with self.lock:
            self.files, self.cache, self.scan_errors, self.last_scan = files, cache, errors, now()
            if changes:
                catalog = load(self.root / 'seguimiento/hitos.json')
                for change in changes:
                    path = change['path']
                    related = [c['id'] for m in catalog['milestones'] for c in m['criteria']
                               if any(fnmatch.fnmatch(path, p) for p in c.get('watch', c.get('files', [])))]
                    display = path if not private_path(path) else 'Documento privado · ' + hashlib.sha256(path.encode()).hexdigest()[:10]
                    self.event('archivo', f"{change['kind'].capitalize()}: {display}", path=display,
                               change=change['kind'], criteria=related,
                               interpretation='Requiere comprobar su efecto.' if related else 'Sin criterio asociado; requiere clasificación.')
                test_dependencies = {p for m in catalog['milestones'] for c in m['criteria'] if c.get('tests')
                                     for p in c.get('check_files', c.get('files', []))}
                if any(x['path'].endswith('.py') or x['path'] == 'requirements.txt' or x['path'] in test_dependencies for x in changes):
                    self.pending_tests = True
                    self.tests_due = time.monotonic() + 3
            save(self.state_dir / 'inventory.json', files)
            self.record_progress()

    def start_tests(self):
        with self.lock:
            if self.testing:
                self.pending_tests = True
                return False
            self.testing = True
            self.pending_tests = False
        threading.Thread(target=self.run_tests, daemon=True).start()
        return True

    def run_tests(self):
        with self.lock:
            inputs = {p: h for p, h in self.files.items() if public_path(p)}
        try:
            scratch = (self.state_dir / 'test_tmp').resolve()
            scratch.mkdir(parents=True, exist_ok=True)
            p = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                               cwd=self.root, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120,
                               env={**os.environ, 'PYTHONIOENCODING': 'utf-8', 'TEMP': str(scratch), 'TMP': str(scratch)})
            output = p.stdout + '\n' + p.stderr
            modules, skipped = {}, []
            for test_name, module, status in re.findall(r'^(\S+) \((test_[^. )]+)[^)]*\) .*?\.\.\. (ok|FAIL|ERROR|skipped[^\n]*)', output, re.M):
                entry = modules.setdefault(module + '.py', {'count': 0, 'passed': True})
                entry['count'] += 1
                entry['passed'] = entry['passed'] and status == 'ok'
                if status.startswith('skipped'):
                    skipped.append({'module': module + '.py', 'test': test_name, 'reason': status.strip()})
            final, _, _ = scan(self.root)
            end_inputs = {p: h for p, h in final.items() if public_path(p)}
            stable = inputs == end_inputs
            proof = {'finished': now(), 'files': inputs, 'modules': modules if stable else {},
                     'passed': p.returncode == 0 and stable and bool(modules), 'stable': stable,
                     'count': sum(x['count'] for x in modules.values()), 'exit_code': p.returncode}
            proof['skipped'] = skipped
            # No se exponen logs de tests: podrían incluir datos privados o secretos de futuras pruebas.
        except (OSError, subprocess.TimeoutExpired):
            proof = {'finished': now(), 'files': inputs, 'modules': {}, 'passed': False, 'count': 0,
                     'error': 'No se completó la suite (límite de 120 s o error de ejecución).'}
        with self.lock:
            self.proof = proof
            self.testing = False
            if not proof.get('stable', True):
                self.pending_tests, self.tests_due = True, time.monotonic() + 3
            save(self.state_dir / 'tests.json', proof)
            self.event('pruebas', f"{proof['count']} pruebas · " + ('sin fallos' if proof['passed'] else 'con fallos o sin evidencia vigente') +
                       (f" · {len(proof.get('skipped', []))} omitidas" if proof.get('skipped') else ''))
            self.record_progress()

    def sync_github(self):
        if not self.token:
            self.token, self.auth_source = credential()
        if not self.token:
            with self.lock:
                self.remote_mode = 'snapshot'
                self.remote_error = 'Lectura guardada. Para consultar continuamente, conecta GitHub en este tablero.'
            return
        try:
            snapshot = remote_snapshot(self.token)
            with self.lock:
                changed = snapshot.get('sha') != self.remote.get('sha')
                self.remote, self.remote_error, self.remote_mode = snapshot, None, 'automatico'
                save(self.state_dir / 'github.json', snapshot)
                if changed:
                    self.event('github', 'Nueva versión publicada: ' + snapshot['sha'][:8])
        except (HTTPError, URLError, TimeoutError, ValueError, OSError, KeyError):
            with self.lock:
                self.remote_mode = 'sin_conexion'
                self.remote_error = 'No se pudo consultar GitHub. Se conserva la última lectura, con su fecha; revisa acceso o conexión.'

    def snapshot(self):
        with self.lock:
            catalog = load(self.root / 'seguimiento/hitos.json')
            reviews = load(self.root / 'seguimiento/evidencias.json', {'reviews': []})['reviews']
            remote_meta = {**self.remote.get('meta', {}), 'checked_at': self.remote.get('checked_at')}
            # Los criterios de repositorio solo se verifican en publicado; no se confunden con archivos locales.
            local = evaluate(catalog, self.files, self.proof, reviews)
            remote = evaluate(catalog, self.remote.get('files', {}), self.proof,
                              self.remote.get('reviews', []), remote_meta)
            public = {p: h for p, h in self.files.items() if public_path(p)}
            changes = diff(self.remote.get('files', {}), public) if self.remote else []
            for change in changes:
                if change['kind'] == 'eliminado':
                    change['kind'] = 'solo_github'
            state = {'local': local, 'published': remote, 'last_scan': self.last_scan,
                     'scan_errors': self.scan_errors, 'testing': self.testing, 'tests': {k: v for k, v in self.proof.items() if k != 'files'},
                     'github': {k: v for k, v in self.remote.items() if k not in {'files', 'reviews'}},
                     'github_mode': self.remote_mode, 'github_error': self.remote_error,
                     'differences': changes, 'activity': self.events[:100], 'catalog_version': catalog['version'],
                     'catalog_source': 'seguimiento/hitos.json · criterios locales aplicados a ambas vistas',
                     'session': self.secret}
            return state

    def watch(self):
        while not self.stop.is_set():
            try:
                self.scan_once()
                if self.pending_tests and not self.testing and time.monotonic() >= self.tests_due:
                    self.start_tests()
                if time.monotonic() >= self.github_due:
                    self.github_due = time.monotonic() + 60
                    threading.Thread(target=self.sync_github, daemon=True).start()
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
                with self.lock:
                    self.scan_errors = ['No se pudo actualizar el catálogo o leer archivos: ' + type(error).__name__]
            self.stop.wait(2)


def handler(controller):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, code, data, mime='application/json; charset=utf-8'):
            data = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', mime)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; form-action 'self'")
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def valid_host(self):
            return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

        def do_GET(self):
            if not self.valid_host():
                return self.send(403, {'error': 'Host no permitido.'})
            route = urlsplit(self.path).path
            if route == '/api/state':
                try:
                    return self.send(200, controller.snapshot())
                except (OSError, ValueError, KeyError, TypeError, AttributeError):
                    return self.send(503, {'error': 'Catálogo temporalmente no disponible.'})
            assets = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                      '/style.css': ('style.css', 'text/css; charset=utf-8')}
            if route not in assets:
                return self.send(404, {'error': 'No encontrado.'})
            name, mime = assets[route]
            return self.send(200, (controller.root / 'seguimiento/web' / name).read_bytes(), mime)

        def do_POST(self):
            if not self.valid_host() or self.headers.get('Origin') != f'http://127.0.0.1:{self.server.server_port}' or not secrets.compare_digest(
                self.headers.get('X-Control-Session', ''), controller.secret):
                return self.send(403, {'error': 'Sesión local requerida.'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 <= length <= 10000:
                    return self.send(413, {'error': 'Solicitud demasiado grande.'})
                data = json.loads(self.rfile.read(length) or b'{}')
                route = urlsplit(self.path).path
                if route == '/api/tests':
                    controller.start_tests()
                elif route == '/api/refresh':
                    controller.scan_once()
                    controller.github_due = 0
                elif route == '/api/connect':
                    token = data.get('token', '').strip()
                    if not token or len(token) > 512 or any(x.isspace() for x in token):
                        return self.send(400, {'error': 'Credencial no válida.'})
                    with controller.lock:
                        controller.token, controller.auth_source = token, 'sesión del tablero'
                    controller.github_due = 0
                else:
                    return self.send(404, {'error': 'No encontrado.'})
                return self.send(202, {'ok': True})
            except (ValueError, TypeError, OSError, AttributeError):
                return self.send(400, {'error': 'No se pudo procesar la solicitud.'})
    return Handler


def main():
    parser = argparse.ArgumentParser(description='Tablero local y publicado de Draft2Model.')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--once', action='store_true', help='Generar resumen JSON sin mantener servidor.')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    c = Controller()
    c.scan_once()
    if args.once:
        state = c.snapshot()
        state.pop('session', None)
        save(STATE / 'resumen.json', state)
        print(STATE / 'resumen.json')
        return
    c.pending_tests, c.tests_due = True, time.monotonic() + 1
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(c))
    threading.Thread(target=c.watch, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}/'
    print('Control de avance: ' + url, flush=True)
    if not args.no_browser:
        import webbrowser
        # Algunos manejadores de URL tardan en responder; no detener el servidor.
        threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        c.stop.set()
        server.server_close()


if __name__ == '__main__':
    main()
