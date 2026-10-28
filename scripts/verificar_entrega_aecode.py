"""Comprobar integridad de fuentes y complemento sin extraer ni ejecutar su contenido.

No acredita aceptación funcional, procedencia auténtica ni revisión de ingeniería.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import zipfile


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _leer_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Clave duplicada en JSON.')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique)


def _ruta(name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name:
        raise ValueError('Ruta no admitida en inventario.')
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or path.as_posix() != name:
        raise ValueError('Ruta no canónica en inventario.')


def _verificar_zip(archive, inventory):
    if not isinstance(inventory, dict) or not inventory:
        raise ValueError('Inventario vacío o inválido.')
    infos = archive.infolist()
    names = [item.filename for item in infos]
    if len(names) != len(set(names)) or set(names) != set(inventory):
        raise ValueError('Inventario distinto del ZIP o miembros duplicados.')
    folded = set()
    for item in infos:
        name = item.filename
        _ruta(name)
        if name.casefold() in folded:
            raise ValueError('Rutas ambiguas en Windows.')
        folded.add(name.casefold())
        if item.flag_bits & 1 or item.is_dir() or ((item.external_attr >> 16) & 0o170000) == 0o120000:
            raise ValueError('Miembro cifrado, directorio o enlace no admitido.')
        expected = inventory[name]
        digest = expected if isinstance(expected, str) else expected.get('sha256')
        if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Hash inválido en inventario.')
        if isinstance(expected, dict) and expected.get('bytes') != item.file_size:
            raise ValueError('Tamaño distinto del inventario.')
        h = hashlib.sha256()
        with archive.open(item) as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                h.update(chunk)
        if h.hexdigest() != digest:
            raise ValueError('Contenido distinto del inventario.')


def verificar(fuentes: Path, complemento: Path, huella_esperada: str):
    fuentes, complemento = fuentes.resolve(strict=True), complemento.resolve(strict=True)
    for folder, error in ((fuentes, 'ERROR_EMPAQUETADO.json'), (complemento, 'FALLO.json')):
        if (folder / error).exists():
            raise ValueError('Paquete con fallo registrado.')
    source = _leer_json((fuentes / 'MANIFIESTO.json').read_bytes())
    extra = _leer_json((complemento / 'MANIFIESTO_COMPLEMENTO.json').read_bytes())
    if source.get('tipo') != 'paquete_fuentes' or source.get('zip') != 'Draft2Model.zip':
        raise ValueError('Contrato de fuentes inválido.')
    if extra.get('contrato') != 'draft2model.complemento_archivado' or extra.get('archivo') != 'Complemento.zip':
        raise ValueError('Contrato de complemento inválido.')
    fingerprint = _sha(json.dumps(source['archivos'], sort_keys=True, separators=(',', ':')).encode())
    if fingerprint != source.get('huella_fuentes') or fingerprint != huella_esperada:
        raise ValueError('Huella de fuentes distinta de la esperada.')
    for folder, manifest, filename, key in (
        (fuentes, source, 'Draft2Model.zip', 'zip_sha256'),
        (complemento, extra, 'Complemento.zip', 'sha256_zip'),
    ):
        path = folder / filename
        h = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                h.update(chunk)
        if h.hexdigest() != manifest.get(key):
            raise ValueError('Hash del ZIP distinto del manifiesto.')
        with zipfile.ZipFile(path) as z:
            _verificar_zip(z, manifest['archivos'])
    with zipfile.ZipFile(complemento / 'Complemento.zip') as z:
        case = _leer_json(z.read('caso_archivado/MANIFIESTO.json'))
        raw = z.read('caso_archivado/Caso.zip')
        if case.get('contrato') != 'draft2model.anexo_archivado' or case.get('archivo') != 'Caso.zip':
            raise ValueError('Contrato del caso inválido.')
        if _sha(raw) != case.get('sha256_zip'):
            raise ValueError('Hash del caso distinto del manifiesto.')
        case_id = extra['ids_declarados']['caso']
        if not isinstance(case_id, str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,127}', case_id):
            raise ValueError('Identificador del caso inválido.')
        if case.get('caso') != case_id:
            raise ValueError('Casos distintos entre manifiestos.')
        with zipfile.ZipFile(io.BytesIO(raw)) as nested:
            _verificar_zip(nested, case['archivos'])
            if any(name != 'LEEME_ANEXO.txt' and not name.startswith(case_id + '/') for name in nested.namelist()):
                raise ValueError('El anexo contiene otro expediente.')
        for name in ('resultados/informe/informe.json', 'resultados/informe/informe.html',
                     'resultados/informe/informe.pdf', 'resultados/panel.html'):
            if name not in extra['archivos']:
                raise ValueError('Falta una salida obligatoria del caso.')
        report = _leer_json(z.read('resultados/informe/informe.json'))
        if report.get('caso_id') != case_id:
            raise ValueError('Informe de otro expediente.')
        evidence = report.get('evidencia_analisis', {})
        ids = extra['ids_declarados']
        if (evidence.get('caso_id') != case_id
                or evidence.get('resultado', {}).get('id') != ids.get('resultado')
                or evidence.get('analisis', {}).get('corrida_id') != ids.get('analisis')
                or evidence.get('modelo', {}).get('modelo_id') != ids.get('modelo')
                or not all(ids.get(key) for key in ('resultado', 'analisis', 'modelo'))):
            raise ValueError('Informe y complemento enlazan versiones distintas.')
        analysis_id = ids['analisis']
        if not isinstance(analysis_id, str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,127}', analysis_id):
            raise ValueError('Identificador del análisis inválido.')
        edb = case['archivos'].get(case_id + '/analisis_etabs/' + analysis_id + '/analizado.EDB', {})
        if (not edb or edb.get('sha256') != evidence['analisis'].get('sha256_edb_analizado')
                or edb.get('sha256') != evidence['resultado'].get('sha256_edb_leido')):
            raise ValueError('EDB archivado distinto del analizado o del leído.')
    return {'estado': 'integridad_verificada_no_aceptacion_funcional',
            'huella_fuentes': fingerprint, 'caso': case_id,
            'archivos_fuentes': len(source['archivos']), 'archivos_complemento': len(extra['archivos']),
            'aprueba_ingenieria': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fuentes', type=Path, required=True)
    parser.add_argument('--complemento', type=Path, required=True)
    parser.add_argument('--huella-esperada', required=True,
                        help='Huella de la distribución que debe acompañar a la evidencia funcional.')
    args = parser.parse_args()
    try:
        result = verificar(args.fuentes, args.complemento, args.huella_esperada)
    except (ValueError, KeyError, TypeError, OSError, zipfile.BadZipFile) as exc:
        print(json.dumps({'estado': 'fallido', 'error': str(exc)}, ensure_ascii=True))
        return 1
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
