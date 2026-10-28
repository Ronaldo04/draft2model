"""Crear una copia de fuentes para AECODE; no acredita validación funcional."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath

CARPETAS = ('draft2model', 'scripts', 'tests', 'docs', 'examples')
RAIZ_PUBLICA = ('README.md', 'requirements.txt', 'requirements-win-py310.lock', '.gitignore',
                'Control de avance.html', 'Abrir control de avance.cmd', 'Abrir revision de planos.cmd')
SEGUIMIENTO = ('seguimiento/hitos.json', 'seguimiento/control.py', 'seguimiento/web/app.js',
               'seguimiento/web/index.html', 'seguimiento/web/style.css')
CODIGO_CREDENCIALES = {'draft2model/credenciales_locales.py', 'scripts/usar_credenciales_locales.py',
                       'tests/test_credenciales_locales.py'}
CACHES = {'__pycache__', '.pytest_cache', 'node_modules', '.git', '.venv', '.codex', '.claude',
          'private', 'originals_private', 'tmp', 'runs', 'output', 'entregas'}
EXT_SECRETAS = {'.key', '.pem', '.pfx', '.p12', '.log', '.db', '.sqlite', '.sqlite3', '.pyc', '.pyo'}
CLAVE = re.compile(rb'(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,})')
FICTICIAS = (b'sk-prueba', b'sk-test-', b'sk-ficticia', b'sk-ejemplo')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def comprobar_contenido(raw: bytes, nombre: str):
    if any(not m.group().lower().startswith(FICTICIAS) for m in CLAVE.finditer(raw)):
        raise ValueError('Posible credencial en archivo publicable: ' + nombre)
    if nombre.lower().endswith('.zip'):
        # Fixtures ZIP se inspeccionan en memoria, sin extraer ni ejecutar archivos.
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            infos = z.infolist()
            if sum(i.file_size for i in infos) > 64 * 1024 * 1024:
                raise ValueError('Archivo ZIP demasiado grande para revisión: ' + nombre)
            for info in infos:
                inner = PurePosixPath(info.filename.replace('\\', '/'))
                if inner.is_absolute() or '..' in inner.parts or ':' in info.filename or info.flag_bits & 1:
                    raise ValueError('Ruta o cifrado no admitidos en ZIP: ' + nombre)
                if info.is_dir():
                    continue
                if inner.suffix.lower() == '.zip':
                    raise ValueError('ZIP anidado no revisado: ' + nombre)
                comprobar_contenido(z.read(info), nombre + '/' + info.filename)


def _admitido(relative: str):
    p = PurePosixPath(relative)
    low = relative.lower()
    return not ({part.lower() for part in p.parts} & CACHES or p.suffix.lower() in EXT_SECRETAS or '.local.' in low
                or p.name.lower().startswith('.env')
                or (('credencial' in low or 'credential' in low or 'secret' in low) and relative not in CODIGO_CREDENCIALES))


def _leer(root: Path, path: Path):
    relative = path.relative_to(root).as_posix()
    # No seguir enlaces de archivo, directorio ni junctions de Windows.
    for parent in (path, *path.parents):
        if parent == root:
            break
        attrs = parent.lstat()
        if stat.S_ISLNK(attrs.st_mode) or getattr(attrs, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Enlace no permitido: ' + relative)
    if not path.resolve().is_relative_to(root):
        raise ValueError('Ruta fuera del proyecto: ' + relative)
    raw = path.read_bytes()
    comprobar_contenido(raw, relative)
    return raw


def capturar(raiz: Path):
    root = raiz.resolve(strict=True)
    paths = []
    for folder in CARPETAS:
        directory = root / folder
        if not directory.is_dir() or directory.is_symlink():
            raise ValueError('Falta directorio de fuentes: ' + folder)
        paths.extend(p for p in directory.rglob('*') if p.is_file())
    paths.extend(root / name for name in (*RAIZ_PUBLICA, *SEGUIMIENTO))
    data = {}
    for p in sorted(paths):
        relative = p.relative_to(root).as_posix()
        if not _admitido(relative):
            continue
        if not p.is_file():
            raise ValueError('Falta recurso de distribución: ' + relative)
        data[relative] = _leer(root, p)
    catalog = json.loads(data['seguimiento/hitos.json'])
    for milestone in catalog['milestones']:
        for criterion in milestone['criteria']:
            for name in criterion.get('check_files', []):
                if name not in data:
                    raise ValueError('Recurso requerido fuera del paquete: ' + name)
    return data


def capturar_wheels(carpeta: Path | None, lock: bytes):
    if carpeta is None:
        return {}
    directory = carpeta.resolve(strict=True)
    expected = set(re.findall(rb'--hash=sha256:([a-f0-9]{64})', lock))
    if not expected:
        raise ValueError('El lock no declara hashes de dependencias.')
    data = {}
    observed = set()
    for path in sorted(directory.glob('*.whl')):
        raw = _leer(directory, path)
        digest = sha(raw).encode()
        if digest not in expected or digest in observed:
            raise ValueError('Wheel ajeno o duplicado respecto del lock: ' + path.name)
        observed.add(digest)
        data['wheels/' + path.name] = raw
    if observed != expected:
        raise ValueError('Faltan wheels requeridos por el lock.')
    return data


def crear(raiz: Path, salida: Path, wheels: Path | None = None):
    root = raiz.resolve(strict=True)
    target = salida.resolve()
    if target.exists() or target == root or any(target.is_relative_to(root / folder) for folder in CARPETAS):
        raise ValueError('El destino debe ser nuevo y no pertenecer a las fuentes.')
    data = capturar(root)
    data.update(capturar_wheels(wheels, data['requirements-win-py310.lock']))
    hashes = {name: sha(raw) for name, raw in sorted(data.items())}
    fingerprint = sha(json.dumps(hashes, sort_keys=True, separators=(',', ':')).encode())
    target.mkdir(parents=True, exist_ok=False)
    try:
        archive = target / 'Draft2Model.zip'
        with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as z:
            for name, raw in sorted(data.items()):
                info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                z.writestr(info, raw)
        # No entregar una mezcla de archivos capturados durante ediciones concurrentes.
        updated = capturar(root)
        updated.update(capturar_wheels(wheels, updated['requirements-win-py310.lock']))
        current = {name: sha(raw) for name, raw in updated.items()}
        if hashes != current:
            raise ValueError('Las fuentes cambiaron durante el empaquetado; validar una versión estable.')
        with zipfile.ZipFile(archive) as z:
            if set(z.namelist()) != set(hashes) or any(sha(z.read(name)) != digest for name, digest in hashes.items()):
                raise ValueError('El ZIP no corresponde al inventario capturado.')
        report = {'tipo': 'paquete_fuentes', 'archivos': hashes, 'huella_fuentes': fingerprint,
                  'zip': archive.name, 'zip_sha256': sha(archive.read_bytes()),
                  'validacion_funcional': 'requiere_informe_independiente_ligado_a_esta_huella',
                  'incluye_credenciales': False, 'incluye_datos_privados': False,
                  'incluye_historial_temporal': False, 'incluye_resultados_caso_real': False}
        report['dependencias_offline'] = sorted(name for name in hashes if name.startswith('wheels/'))
        (target / 'MANIFIESTO.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        (target / 'LEEME_AECODE.md').write_text(
            '# Fuentes Draft2Model para AECODE\n\n'
            'Descomprimir Draft2Model.zip en una carpeta nueva. README.md contiene instalación y arranque.\n\n'
            'Este paquete no contiene claves, expedientes privados, entornos instalados ni tmp histórico. '
            'ETABS y las claves de visión se configuran localmente según la guía.\n\n'
            'Consultar docs/ENTREGA_AECODE.md. Si el manifiesto incluye wheels/, permite instalar '
            'sin red usando el lock; de lo contrario hay que aportar esas dependencias.\n\n'
            'MANIFIESTO.json permite comprobar cada archivo y la huella de fuentes. Crear el ZIP no demuestra '
            'que funcione el flujo completo: la aceptación requiere el informe de validación correspondiente '
            'a esta huella, con instalación, recorrido real, resultados, limitaciones y evidencias. '
            'Los resultados del caso real deben entregarse por separado, tras revisarlos.\n', encoding='utf-8')
        return report
    except Exception as exc:
        (target / 'ERROR_EMPAQUETADO.json').write_text(json.dumps({'estado': 'fallido', 'error': str(exc)}, ensure_ascii=False)+'\n', encoding='utf-8')
        raise


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--salida', type=Path)
    ap.add_argument('--wheels', type=Path, help='Incluir los wheels locales exactos del lock, sin descargarlos.')
    ap.add_argument('--comprobar', action='store_true', help='Solo revisar selección/secretos, sin generar paquete.')
    args = ap.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    if args.comprobar:
        data = capturar(root)
        data.update(capturar_wheels(args.wheels, data['requirements-win-py310.lock']))
        print(json.dumps({'preflight': 'rutas_y_contenido', 'archivos': len(data), 'validacion_funcional': False}))
        return 0
    if args.salida is None:
        ap.error('--salida es obligatorio para crear el paquete')
    report = crear(root, args.salida, args.wheels)
    print(json.dumps({'archivos': len(report['archivos']), 'huella_fuentes': report['huella_fuentes'], 'validacion_funcional': report['validacion_funcional']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
