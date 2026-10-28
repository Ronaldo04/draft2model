"""Instalar y comprobar el ZIP303 exacto; sin red, ETABS ni proveedores."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'entregas/AECODE_RC_303'
WORK = ROOT / 'tmp/validacion_distribucion_303'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    manifest = json.loads((PACKAGE / 'MANIFIESTO.json').read_text(encoding='utf-8'))
    if (PACKAGE / 'ERROR_EMPAQUETADO.json').exists():
        raise ValueError('Paquete con error registrado.')
    archive = PACKAGE / 'Draft2Model.zip'
    assert sha(archive.read_bytes()) == manifest['zip_sha256']
    WORK.mkdir(parents=True, exist_ok=False)
    source = WORK / 'fuentes'
    source.mkdir()
    report = {'fecha_utc': datetime.now(timezone.utc).isoformat(), 'pid_coordinador': os.getpid(),
              'huella_fuentes': manifest['huella_fuentes'], 'paquete': str(PACKAGE),
              'estado': 'preparando', 'pasos': [], 'sin_red': True, 'etabs_ejecutado': False,
              'goal_completo': False}

    def save():
        (WORK / 'estado.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONNOUSERSITE='1', TEMP=str(WORK), TMP=str(WORK))
    for name in ('PYTHONPATH', 'PYTHONHOME'):
        env.pop(name, None)

    def run(name, args, timeout):
        log = WORK / (name + '.log')
        report['estado'] = name
        with log.open('w', encoding='utf-8') as output:
            process = subprocess.Popen([str(a) for a in args], cwd=source, env=env,
                                       stdout=output, stderr=subprocess.STDOUT)
            report['proceso_actual'] = {'pid': process.pid, 'paso': name,
                                       'argv': [str(a) for a in args], 'inicio_utc': datetime.now(timezone.utc).isoformat()}
            save()
            code = process.wait(timeout=timeout)
        report['pasos'].append({'nombre': name, 'codigo': code, 'log': str(log)})
        report.pop('proceso_actual', None)
        save()
        if code:
            raise RuntimeError('Falló ' + name + '; consultar su log.')

    try:
        save()
        with zipfile.ZipFile(archive) as z:
            assert len(z.namelist()) == len(set(z.namelist()))
            assert set(z.namelist()) == set(manifest['archivos'])
            for name in z.namelist():
                path = PurePosixPath(name)
                assert not path.is_absolute() and '..' not in path.parts and ':' not in name and '\\' not in name
                raw = z.read(name)
                assert sha(raw) == manifest['archivos'][name]
                target = source / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
        assert not (source / 'data/private').exists() and not (source / 'tmp').exists()
        python = WORK / '.venv/Scripts/python.exe'
        run('crear_entorno', [sys.executable, '-m', 'venv', WORK / '.venv'], 120)
        run('instalar_offline', [python, '-m', 'pip', 'install', '--no-index', '--find-links', source / 'wheels',
                                '--require-hashes', '-r', source / 'requirements-win-py310.lock'], 180)
        run('verificacion_global', [python, 'scripts/verificar_proyecto.py', '--salida', WORK / 'verificacion.json',
                                   '--temporales', WORK / 't'], 3700)
        validation = json.loads((WORK / 'verificacion.json').read_text(encoding='utf-8'))
        assert validation['validacion_local_completa'] is True
        assert all(sha((source / name).read_bytes()) == digest for name, digest in manifest['archivos'].items())
        run('integridad_conjunto', [python, 'scripts/verificar_entrega_aecode.py', '--fuentes', PACKAGE,
                                   '--complemento', ROOT / 'entregas/COMPLEMENTO_CORREGIDO_303',
                                   '--huella-esperada', manifest['huella_fuentes']], 90)
        report.update(estado='validacion_local_completa', fuentes_del_zip_intactas=True,
                      verificacion=str(WORK / 'verificacion.json'), acepta_piloto=False,
                      nota='Instalación/pruebas/integridad; QA real301 y aceptación global mantienen evidencia separada.')
        save()
    except Exception as exc:
        report.update(estado='fallido_o_interrumpido', error=str(exc))
        save()
        raise
    print(json.dumps({'estado': report['estado'], 'huella_fuentes': manifest['huella_fuentes']}))


if __name__ == '__main__':
    main()
