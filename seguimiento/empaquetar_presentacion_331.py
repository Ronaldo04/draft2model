"""Publicación local posterior a comprobación exacta; no envía nada a AECODE."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile
from datetime import datetime, timezone
from urllib.parse import unquote, urlsplit

from scripts.verificar_entrega_aecode import verificar
from scripts.crear_entrega_ruta import _contiene_secreto

root = Path(__file__).resolve().parents[1]
base = root/'tmp/validacion_distribucion_331'
source = base/'fuentes'
state = json.loads((base/'estado.json').read_text(encoding='utf-8'))
assert state['estado'] == 'terminado' and state['codigo'] == 0, 'Esperar validación exacta331.'
validation = json.loads((base/'verificacion.json').read_text(encoding='utf-8'))
assert validation['validacion_local_completa'] and validation['archivos_estables_durante_ejecucion']
assert not validation['bloqueos_entorno']
assert all(c['codigo'] == 0 and not c['omisiones'] for c in validation['comprobaciones'])
assert all(hashlib.sha256((source/n).read_bytes()).hexdigest() == h for n,h in state['cambios'].items())
suite = next(c for c in validation['comprobaciones'] if c['nombre'] == 'suite')
suite_text = (source/suite['registro']).read_text(encoding='utf-8')
python_tests = int(re.search(r'Ran (\d+) tests', suite_text).group(1))
assert python_tests >= 1493

previous = root/'entregas/AECODE_PRESENTACION_328'
out = root/'entregas/AECODE_PRESENTACION_331'
archive_path = root/'entregas/AECODE_PRESENTACION_331_FINAL.zip'
assert not out.exists() and not archive_path.exists(), 'No sobrescribir entregas.'
shutil.copytree(previous, out)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

manifest = json.loads((previous/'software/MANIFIESTO.json').read_text(encoding='utf-8'))
names = sorted(set(manifest['archivos']) | set(state['cambios']))
inventory = {}
with zipfile.ZipFile(out/'software/Draft2Model.zip', 'w', compression=zipfile.ZIP_DEFLATED) as z:
    for name in names:
        path = source/name
        assert path.resolve().is_relative_to(source.resolve()) and not path.is_symlink()
        raw = path.read_bytes()
        assert not _contiene_secreto(raw), 'Patrón de secreto; no publicar.'
        inventory[name] = sha(raw)
        info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, raw)
fingerprint = sha(json.dumps(inventory, sort_keys=True, separators=(',', ':')).encode())
manifest.update(archivos=inventory, huella_fuentes=fingerprint,
                zip_sha256=sha((out/'software/Draft2Model.zip').read_bytes()))
write(out/'software/MANIFIESTO.json', manifest)
write(out/'software/VALIDACION.json', {
    'fecha_utc': datetime.now(timezone.utc).isoformat(), 'huella_fuentes': fingerprint,
    'archivos': len(inventory), 'global': {'python': python_tests, 'interfaz': 36},
    'omisiones': [], 'fuentes_estables': True, 'cambios_frente325': list(state['cambios']),
    'entorno': 'Offline303 reutilizado; mismo lock y wheels; no instalación nueva331.',
    'evidencia_nativa': 'Caso322 conservado; no nueva corrida ETABS331.',
    'limites': 'Piloto supervisado, referencia IA parcial, sin EMS, RNE parcial, sin generalización acreditada.',
    'goal_completo': False})
for check in validation['comprobaciones']:
    shutil.copyfile(source/check['registro'], out/'evidencias_software'/('331_'+check['nombre']+'.log'))
shutil.copyfile(base/'verificacion.json', out/'evidencias_software/VALIDACION_EXACTA_331.json')
for name in ('COHERENCIA_COTAS_329.json', 'INTEGRACION_ALERTAS_330.json'):
    shutil.copyfile(root/'seguimiento'/name, out/'evidencias_software'/name)
shutil.copytree(root/'seguimiento/localizacion_331', out/'localizacion_331',
                ignore=shutil.ignore_patterns('lamina_1_ocr.png', 'lamina_1_ocr.tsv'))

report = (out/'REPORTE_ESTADO.md').read_text(encoding='utf-8')
old = '- Software325:1471pruebas Python y36de interfaz, cinco comprobaciones correctas, sin omisiones y609fuentes estables.'
assert old in report
report = report.replace(old, f'- Software331: {python_tests} pruebas Python y 36 de interfaz, cinco comprobaciones correctas, sin omisiones y {len(inventory)} archivos de distribución con hashes.')
report = report.replace('No nueva ejecución nativa325', 'No nueva ejecución nativa331')
report = report.replace('El código325y el EDB siguen intactos.',
                        'El EDB permanece intacto; los cambios de software331 se verifican por separado.')
report += '''

## Mejoras de entrada incorporadas en331

Los avisos de coherencia entre cota/unidad y texto declarado se muestran junto a
la lectura. La búsqueda local de palabras del PDF propone regiones y conserva
las alternativas cuando hay duplicados. No guarda ni aprueba automáticamente.
En 19 etiquetas del piloto se obtuvo una coincidencia única, dos búsquedas
ambiguas y 16 sin coincidencias: la capa de texto no cubre todo lo visible.
El ensayo separado de OCR local no está integrado como función operativa.

Estos cambios no recalcularon ni corrigieron el modelo ETABS. Los informes
archivados y sus observaciones técnicas se conservan. Las mejoras no acreditan
el modelado automático de cualquier construcción.
'''
(out/'REPORTE_ESTADO.md').write_text(report, encoding='utf-8')
first = (out/'LEER_PRIMERO.md').read_text(encoding='utf-8')
first = first.replace('**Software325 verificado + caso real + benchmark asistido328.**',
                      f'**Software331: {python_tests} pruebas Python y 36 de interfaz + caso real + benchmark asistido328.**')
first = first.replace('Las pruebas globales y logs corresponden al ZIP325exacto; no se repitieron por añadir este anexo de datos.',
                      'Las pruebas globales y logs de331 corresponden a la copia congelada usada para producir este ZIP; no se hizo una nueva corrida nativa ETABS.')
first = first.replace('el modelo, los informes anteriores y el código no se modificaron.',
                      'el modelo y los informes anteriores permanecen intactos; las mejoras de código331 están identificadas en su validación.')
(out/'LEER_PRIMERO.md').write_text('''# Entrega académica331

Esta carpeta contiene software actualizado y validado, el caso real archivado y
sus informes. Leer [estado y límites](REPORTE_ESTADO.md). La extracción del caso
sigue siendo supervisada. No se necesitan claves para consultar los resultados.
El OCR local es un ensayo separado, no una función del producto publicado.

## Guía de consulta conservada

''' + first, encoding='utf-8')
talk_path = out/'PRESENTACION_5_MINUTOS.md'
talk = talk_path.read_text(encoding='utf-8')
talk = talk.replace('1471pruebas Python y36de interfaz de la versión325',
                    f'{python_tests} pruebas Python y 36 de interfaz de la versión331')
talk_path.write_text(talk, encoding='utf-8')
# Las auditorías325 son antecedentes; no dejar su espera del anotador como estado actual.
for ext in ('md', 'json'):
    file = out/f'software/AUDITORIA_P01_P14.{ext}'
    file.rename(out/f'software/AUDITORIA_P01_P14_HISTORICA_325.{ext}')
audit = '''# Auditoría de entrega331

P01–P02 y P05–P06: infraestructura y revisión local verificadas por la suite331;
instalación offline303 y conexión/caso nativo anteriores conservados. P03:
transformaciones probadas, cobertura real parcial. P04: benchmark asistido328
completado por autorización, sin referencia humana independiente; el usuario
no queda pendiente de completar el anotador. P07: escenarios sin EMS. P08:
modelo nativo con observaciones y contraste bruto de masa no coherente. P09:
comparación manual aplazada. P10–P11: reglas y fuentes documentadas, sin RNE
integral. P12: informes conservados y verificaciones previas de PDF. P13:
recuperación y fallos cubiertos por pruebas, sin exhaustividad universal. P14:
flujo del primer piloto supervisado, aceptación global abierta.

La auditoría325 se conserva como antecedente, no como lista vigente de tareas
del usuario. Consultar REPORTE_ESTADO.md y software/VALIDACION.json para331.
'''
(out/'software/AUDITORIA_P01_P14.md').write_text(audit, encoding='utf-8')
write(out/'software/AUDITORIA_P01_P14.json', {'corte': 331, 'goal_completo': False,
    'estado': 'operativo_supervisado_con_limitaciones', 'detalle': 'AUDITORIA_P01_P14.md',
    'benchmark': 'asistido_ia_completado_no_humano', 'usuario_pendiente_de_anotador': False})
integrity = verificar(out/'software', out/'caso', fingerprint)
link_count = 0
for file in [out/'LEER_PRIMERO.md', out/'REPORTE_ESTADO.md', out/'PRESENTACION_5_MINUTOS.md',
             source/'docs/GUIA_REPRODUCIBLE.md', source/'docs/COHERENCIA_LITERAL_DE_COTAS.md',
             source/'docs/LOCALIZACION_LITERAL_PDF.md']:
    for angle, plain in re.findall(r'\[[^\]]*\]\((?:<([^>]+)>|([^\s)]+))\)', file.read_text(encoding='utf-8')):
        target = angle or plain
        if urlsplit(target).scheme or target.startswith('#'):
            continue
        relative = unquote(target.split('#', 1)[0])
        if relative:
            assert (file.parent/relative).exists(), f'Enlace roto: {file.name}: {relative}'
            link_count += 1
write(out/'VALIDACION_PAQUETE.json', {'integridad': integrity, 'pruebas_python': python_tests,
    'pruebas_interfaz': 36, 'omisiones': [], 'sin_nueva_api': True, 'sin_nueva_corrida_etabs': True,
    'enlaces_de_entrada_y_guias_comprobados': link_count, 'enlaces_rotos': [], 'aceptacion_global': False})
files = {p.relative_to(out).as_posix(): {'sha256': sha(p.read_bytes()), 'bytes': p.stat().st_size}
         for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'MANIFIESTO_ENTREGA.json'}
write(out/'MANIFIESTO_ENTREGA.json', {'corte': 331, 'archivos': files, 'huella_fuentes': fingerprint,
    'estado': 'operativo_supervisado_con_limitaciones', 'goal_completo': False})
with zipfile.ZipFile(archive_path, 'x', compression=zipfile.ZIP_DEFLATED) as z:
    for path in sorted(out.rglob('*')):
        if path.is_file():
            z.write(path, (Path(out.name)/path.relative_to(out)).as_posix())
with zipfile.ZipFile(archive_path) as z:
    for name, info in files.items():
        assert sha(z.read(out.name+'/'+name)) == info['sha256']
result = {'archivo': str(archive_path.relative_to(root)), 'sha256': sha(archive_path.read_bytes()),
          'bytes': archive_path.stat().st_size, 'huella_fuentes': fingerprint,
          'pruebas_python': python_tests, 'pruebas_interfaz': 36, 'goal_completo': False}
write(root/'seguimiento/ENTREGA_ACADEMICA_331_FINAL.json', result)
print(json.dumps(result, ensure_ascii=False))
