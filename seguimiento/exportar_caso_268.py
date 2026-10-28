"""Anexo local íntegro de un solo caso. No ejecuta ETABS ni altera recibos."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

SECRET = re.compile(rb'(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,})')
EXPLANATION = '''Anexo de expediente: copia exacta de bytes, sin aprobación de ingeniería.
Puede contener versiones históricas, intentos fallidos e hipótesis; un archivo presente no es una entrega aceptada.
Las rutas absolutas originales y sus recibos se conservan: no acreditan relecturas en otra carpeta.
Separar consulta de resultados archivados, apertura del EDB y reconstrucción con nuevas corridas.
No incluye claves ni instala Python, ETABS o el sistema. Se entrega junto al paquete de fuentes verificado.
La integridad del manifiesto no prueba calidad, cierre transitivo ni validez del modelo.
'''

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def safe(path):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
        raise ValueError('No se admiten enlaces o junctions.')
    return info

def entries(case):
    safe(case)
    found = []
    for p in case.rglob('*'):
        info = safe(p)
        if stat.S_ISREG(info.st_mode):
            rel = p.relative_to(case).as_posix()
            if any(s in rel.lower() for s in ('credencial', 'credential', '.env', '.local.', 'api_key')):
                raise ValueError('Nombre reservado para credenciales en el expediente.')
            found.append((rel, p))
        elif not stat.S_ISDIR(info.st_mode):
            raise ValueError('Archivo especial no admitido.')
    if not found or not (case/'expediente.json').is_file():
        raise ValueError('Expediente vacío o sin índice.')
    return sorted(found)

def stream(path, sink=None):
    safe(path)
    h = hashlib.sha256(); total = 0; tail = b''
    with path.open('rb') as f:
        while True:
            data = f.read(1024*1024)
            if not data:
                break
            if SECRET.search(tail + data):
                raise ValueError('Posible credencial: anexo cancelado sin exponer contenido.')
            tail = (tail+data)[-128:]
            h.update(data); total += len(data)
            if sink is not None:
                sink.write(data)
    safe(path)
    return {'sha256': h.hexdigest(), 'bytes': total}

def create(root, case_id, output):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', case_id):
        raise ValueError('Identificador de caso inválido.')
    root = Path(root).absolute(); safe(root)
    case = root/case_id
    listing = entries(case)
    # El destino nunca puede situarse dentro del expediente ni reemplazar otro anexo.
    output = Path(output).absolute()
    if output.resolve().is_relative_to(case.resolve()):
        raise ValueError('Destino dentro del expediente.')
    output.mkdir(parents=True, exist_ok=False)
    try:
        hashes = {}
        archive = output/'Caso.zip'
        with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=4) as z:
            for relative, source in listing:
                name = case_id+'/'+relative
                with z.open(name, 'w', force_zip64=True) as sink:
                    hashes[name] = stream(source, sink)
            z.writestr('LEEME_ANEXO.txt', EXPLANATION)
            hashes['LEEME_ANEXO.txt'] = {'sha256': digest(EXPLANATION.encode()), 'bytes': len(EXPLANATION.encode())}
        if [n for n,_ in entries(case)] != [n for n,_ in listing]:
            raise ValueError('El conjunto de archivos cambió durante la copia.')
        for relative, source in listing:
            if stream(source) != hashes[case_id+'/'+relative]:
                raise ValueError('El expediente cambió durante la copia.')
        manifest = {'contrato':'draft2model.anexo_archivado', 'version':'0.1.0',
                    'fecha_utc':datetime.now(timezone.utc).isoformat(), 'caso':case_id,
                    'archivo':'Caso.zip', 'sha256_zip':stream(archive)['sha256'],
                    'archivos':hashes, 'aprueba_ingenieria':False,
                    'relectura_portable_verificada':False, 'estado':'bytes_estables_no_aceptacion_funcional'}
        (output/'MANIFIESTO.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        verify(output)
        return manifest
    except Exception as error:
        (output/'FALLO.json').write_text(json.dumps({'estado':'anexo_no_publicable','error':str(error)}, ensure_ascii=False), encoding='utf-8')
        raise

def verify(output):
    output = Path(output)
    if (output/'FALLO.json').exists():
        raise ValueError('Anexo con fallo registrado.')
    raw = json.loads((output/'MANIFIESTO.json').read_text(encoding='utf-8'))
    if raw.get('contrato') != 'draft2model.anexo_archivado' or raw.get('archivo') != 'Caso.zip':
        raise ValueError('Manifiesto inválido.')
    archive = output/'Caso.zip'
    if stream(archive)['sha256'] != raw['sha256_zip']:
        raise ValueError('ZIP alterado.')
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or set(names) != set(raw['archivos']):
            raise ValueError('Inventario ZIP distinto del manifiesto.')
        for name in names:
            p = PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or ':' in name or '\\' in name:
                raise ValueError('Ruta ZIP no segura.')
            with z.open(name) as f:
                h = hashlib.sha256(); size = 0
                while True:
                    b = f.read(1024*1024)
                    if not b: break
                    h.update(b); size += len(b)
            if {'sha256':h.hexdigest(),'bytes':size} != raw['archivos'][name]:
                raise ValueError('Miembro alterado.')
    return {'estado':'integridad_verificada','archivos':len(names),'aprueba_ingenieria':False}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raiz', type=Path, default=Path('data/private'))
    p.add_argument('--caso')
    p.add_argument('--salida', required=True, type=Path)
    p.add_argument('--verificar', action='store_true')
    a = p.parse_args()
    if a.verificar:
        result = verify(a.salida)
    else:
        if not a.caso: p.error('--caso es obligatorio al crear')
        m = create(a.raiz, a.caso, a.salida)
        result = {'estado':m['estado'],'archivos':len(m['archivos']),'sha256_zip':m['sha256_zip']}
    print(json.dumps(result, ensure_ascii=False))

if __name__ == '__main__': main()
