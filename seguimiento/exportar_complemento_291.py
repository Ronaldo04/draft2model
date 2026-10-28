"""Complemento de un caso y sus artefactos externos; integridad, no aceptación."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
import zipfile

if __package__:
    from . import exportar_caso_268 as caso_export
else:
    import exportar_caso_268 as caso_export

LEEME = '''Complemento archivado de un único caso Draft2Model.
Descomprimir Complemento.zip en una carpeta nueva. caso_archivado/Caso.zip conserva
el expediente y sus originales; resultados/ y evidencias/ conservan las salidas
del trabajo seleccionado, sin reescribir rutas o recibos históricos.
Usar junto a una distribución de fuentes validada y su guía. Los hashes prueban
integridad, no calidad de extracción, ingeniería, cumplimiento ni portabilidad
de nuevas ejecuciones. La revisión humana y las hipótesis siguen vigentes.
No incluye credenciales, otros expedientes, Python o ETABS.
'''


def _json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def _dentro(path, base):
    """Rechaza escape y enlaces en cada componente; no sigue junctions."""
    path, base = Path(path).absolute(), Path(base).absolute()
    relative = path.relative_to(base)
    caso_export.safe(base)
    current = base
    for component in relative.parts:
        current /= component
        caso_export.safe(current)
    if path.resolve() != path or not path.is_file():
        raise ValueError('Fuente no regular o enlazada.')
    return path


def _seleccion(work, case_id):
    registry = _json(_dentro(work / 'registro_resultados.json', work))
    if registry.get('caso') != case_id:
        raise ValueError('El trabajo no corresponde al caso seleccionado.')
    report = registry['informe']
    report_dir = Path(report['carpeta']).absolute()
    selected = {}
    for name in ('registro.json', 'configuracion.json', 'masa_pisos_diagnostico.json',
                 'registro_resultados.json'):
        p = work / name
        if p.exists() or name == 'registro_resultados.json':
            selected['evidencias/' + name] = _dentro(p, work)
    for name in ('libro_masa.json', 'reglas_e030.json', 'contexto.json'):
        p = work / 'resultados' / name
        if p.exists():
            selected['resultados/' + name] = _dentro(p, work)
    for name in ('informe.json', 'informe.html', 'informe.pdf'):
        p = _dentro(report_dir / name, work)
        if caso_export.stream(p)['sha256'] != report[name]:
            raise ValueError('Informe distinto del registro: ' + name)
        selected['resultados/informe/' + name] = p
    panel = _dentro(Path(registry['panel']['archivo']), work)
    if caso_export.stream(panel)['sha256'] != registry['panel']['sha256']:
        raise ValueError('Panel distinto del registro.')
    selected['resultados/panel.html'] = panel
    document = _json(selected['resultados/informe/informe.json'])
    if document['caso_id'] != case_id:
        raise ValueError('Informe de otro caso.')
    evidence = document['evidencia_analisis']
    if evidence['resultado']['id'] != registry['resultados']['id']:
        raise ValueError('Resultado del informe distinto del registro.')
    ids = {'caso': case_id, 'resultado': registry['resultados']['id'],
           'analisis': evidence['analisis']['corrida_id'],
           'modelo': evidence['modelo']['modelo_id']}
    return selected, ids


def _referencias_publicas(directory):
    """Corpus elegido explícitamente; comprueba los bytes del manifiesto original."""
    directory = Path(directory).absolute()
    manifest = _json(_dentro(directory / 'fuentes_manifest.json', directory))
    for item in manifest['fuentes']:
        name = item['archivo']
        if Path(name).name != name:
            raise ValueError('Referencia pública con ruta no simple.')
        if caso_export.stream(_dentro(directory / name, directory)) != {
                'sha256': item['sha256'], 'bytes': item['bytes']}:
            raise ValueError('Referencia pública distinta de su manifiesto.')
    files = {}
    for p in sorted(directory.iterdir()):
        if p.suffix.lower() not in ('.pdf', '.txt', '.html', '.json'):
            continue  # No duplicar renders de páginas.
        if any(word in p.name.lower() for word in ('credencial', 'credential', '.local.', 'api_key')):
            raise ValueError('Nombre reservado en referencias públicas.')
        files[f'seguimiento/{directory.name}/{p.name}'] = _dentro(p, directory)
    return files


def create(root, case_id, work, output, *, referencias_publicas=None):
    root, work, output = (Path(p).absolute() for p in (root, work, output))
    if output.resolve().is_relative_to(work.resolve()) or output.resolve().is_relative_to((root / case_id).resolve()):
        raise ValueError('Destino dentro de las fuentes.')
    selected, ids = _seleccion(work, case_id)
    origins = {n: str(p.relative_to(work)) for n, p in selected.items()}
    references = _referencias_publicas(referencias_publicas) if referencias_publicas else {}
    selected.update(references)
    before = {name: caso_export.stream(p) for name, p in selected.items()}
    output.mkdir(parents=True, exist_ok=False)
    try:
        snapshot = caso_export.create(root, case_id, output / 'caso_archivado')
        for name, source in selected.items():
            destination = output / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open('xb') as sink:
                if caso_export.stream(source, sink) != before[name]:
                    raise ValueError('Fuente modificada durante la copia.')
        (output / 'LEEME.txt').write_text(LEEME, encoding='utf-8')
        # Cierre transitivo del conjunto copiado: también detectar altas/bajas en el caso.
        actual = {case_id + '/' + name: caso_export.stream(p)
                  for name, p in caso_export.entries(root / case_id)}
        expected = {n: h for n, h in snapshot['archivos'].items() if n.startswith(case_id + '/')}
        if actual != expected or before != {n: caso_export.stream(p) for n, p in selected.items()}:
            raise ValueError('Las fuentes cambiaron durante el complemento.')
        files = {p.relative_to(output).as_posix(): caso_export.stream(p)
                 for p in output.rglob('*') if p.is_file()}
        archive = output / 'Complemento.zip'
        with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as z:
            for name in sorted(files):
                z.write(output / name, name)
        manifest = {'contrato': 'draft2model.complemento_archivado', 'version': '0.1.0',
                    'fecha_utc': datetime.now(timezone.utc).isoformat(),
                    'ids_declarados': ids, 'archivo': archive.name,
                    'sha256_zip': caso_export.stream(archive)['sha256'], 'archivos': files,
                    'origenes_trabajo': origins,
                    'referencias_publicas_incluidas': sorted(references),
                    'estado': 'integridad_no_aceptacion', 'aprueba_ingenieria': False,
                    'portabilidad_nueva_ejecucion_verificada': False}
        (output / 'MANIFIESTO_COMPLEMENTO.json').write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        verify(output)
        return manifest
    except Exception as exc:
        (output / 'FALLO.json').write_text(json.dumps({'estado': 'no_publicable', 'error': str(exc)},
                                                    ensure_ascii=False), encoding='utf-8')
        raise


def verify(output):
    output = Path(output).absolute()
    if (output / 'FALLO.json').exists():
        raise ValueError('Complemento con fallo registrado.')
    manifest = _json(_dentro(output / 'MANIFIESTO_COMPLEMENTO.json', output))
    if manifest.get('contrato') != 'draft2model.complemento_archivado' or manifest.get('archivo') != 'Complemento.zip':
        raise ValueError('Manifiesto inválido.')
    archive = _dentro(output / 'Complemento.zip', output)
    if caso_export.stream(archive)['sha256'] != manifest['sha256_zip']:
        raise ValueError('ZIP alterado.')
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or set(names) != set(manifest['archivos']):
            raise ValueError('Inventario ZIP distinto.')
        for name in names:
            rel = PurePosixPath(name)
            if rel.is_absolute() or '..' in rel.parts or ':' in name or '\\' in name:
                raise ValueError('Ruta ZIP no segura.')
            raw = z.read(name)
            expected = manifest['archivos'][name]
            if {'sha256': caso_export.digest(raw), 'bytes': len(raw)} != expected:
                raise ValueError('Miembro ZIP alterado.')
            if caso_export.stream(_dentro(output / name, output)) != expected:
                raise ValueError('Archivo extraído distinto del manifiesto.')
    caso_export.verify(output / 'caso_archivado')
    return {'estado': 'integridad_verificada_no_aceptacion', 'archivos': len(names)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raiz', type=Path, default=Path('data/private'))
    p.add_argument('--caso')
    p.add_argument('--trabajo', type=Path)
    p.add_argument('--salida', type=Path, required=True)
    p.add_argument('--verificar', action='store_true')
    p.add_argument('--referencias-publicas', type=Path,
                   help='Corpus público elegido explícitamente con fuentes_manifest.json; conserva su ruta seguimiento/<carpeta>.')
    a = p.parse_args()
    if a.verificar:
        result = verify(a.salida)
    else:
        if not a.caso or a.trabajo is None:
            p.error('--caso y --trabajo son obligatorios al crear')
        m = create(a.raiz, a.caso, a.trabajo, a.salida, referencias_publicas=a.referencias_publicas)
        result = {'estado': m['estado'], 'sha256_zip': m['sha256_zip'], 'archivos': len(m['archivos'])}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
