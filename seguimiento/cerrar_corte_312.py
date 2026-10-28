"""Consolidar evidencias únicamente después de terminar la validación312."""
from pathlib import Path
from datetime import datetime, timezone
import json
import re
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
out = root/'entregas/AECODE_ENTREGA_312'
work = root/'tmp/validacion_distribucion_312'
state = json.loads((work/'estado.json').read_text(encoding='utf-8'))
assert state['estado'] == 'terminado' and state['codigo'] == 0 and state['fuentes_intactas'] is True
validation = json.loads((work/'verificacion.json').read_text(encoding='utf-8'))
assert validation['comprobaciones'] and all(c['codigo'] == 0 and not c['omisiones'] for c in validation['comprobaciones'])
ev = out/'EVIDENCIAS'
ev.mkdir(exist_ok=True)
shutil.copyfile(work/'verificacion.json', ev/'verificacion_global.json')
counts = {}
for check in validation['comprobaciones']:
    log = work/'fuentes'/check['registro']
    raw = log.read_text(encoding='utf-8')
    shutil.copyfile(log, ev/(check['nombre']+'.log'))
    if check['nombre'] == 'suite':
        match = re.search(r'Ran (\d+) tests in', raw)
        assert match and '\nOK\n' in raw
        counts['python'] = int(match[1])
    if check['nombre'] == 'interfaz':
        counts['interfaz'] = int(re.search(r'# tests (\d+)', raw)[1])
        assert all(int(re.search(r'# '+key+r' (\d+)',raw)[1]) == 0 for key in ('fail','cancelled','skipped','todo'))
assert counts == {'python':1425,'interfaz':36}, counts
manifest = json.loads((out/'MANIFIESTO.json').read_text(encoding='utf-8'))
cmd = [sys.executable, 'scripts/verificar_entrega_aecode.py', '--fuentes', str(out), '--complemento',
       str(root/'entregas/COMPLEMENTO_CORREGIDO_303'), '--huella-esperada',manifest['huella_fuentes']]
checked = subprocess.run(cmd,cwd=root,capture_output=True,text=True,encoding='utf-8',check=True)
integrity = json.loads(checked.stdout)
summary = {'fecha_utc':datetime.now(timezone.utc).isoformat(), 'huella_fuentes':manifest['huella_fuentes'],
           'archivos':len(manifest['archivos']), 'global':counts, 'omisiones':[],
           'fuentes_estables':True, 'integridad_conjunto':integrity,
           'entorno':'Instalación offline303 reutilizada; lock y wheels idénticos. No nueva instalación312.',
           'pdf':'Pie incrustado.67pruebas focales e igualdad de texto/píxeles de ocho páginas en MuPDF. Contraste adicional309/310 archivado.',
           'no_repetido':['ETABS','llamadas API','descarga UI','instalación'],
           'limites':['Referencia humana y correspondencias pendientes; no hay precisión empírica acreditada',
                      'Masa del piloto no_coherente y diez comparaciones no satisfactorias conservadas',
                      'No se demuestra automatización de cualquier construcción ni aprobación profesional'],
           'goal_completo':False}
(out/'VALIDACION.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(root/'seguimiento/VALIDACION_DISTRIBUCION_312.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
for name in ('REFERENCIA_DATOS_Y_NORMATIVA.md',):
    shutil.copyfile(root/'entregas/AECODE_ENTREGA_308'/name,out/name)
guide = (root/'entregas/AECODE_ENTREGA_308/LEER_PRIMERO.md').read_text(encoding='utf-8')
start = guide.index('La instalación offline303')
end = guide.index('## Instalar', start)
guide = guide[:start] + ('La distribución312 pasó **1.425 pruebas Python y 36 de interfaz**, sin omisiones y con las600fuentes estables. '
    'Se reutilizó la instalación offline303 comprobada, con el mismo lock y wheels. El informe VALIDACION.json identifica la huella exacta. '
    'La fuente del pie PDF queda incrustada; no se cambiaron datos ni resultados estructurales. Las comprobaciones de descarga real y apertura UI pertenecen respectivamente a303 y306; no se repitieron en312.\n\n') + guide[end:]
guide = guide.replace('599 archivos','600 archivos').replace(
    'Permanecen pendientes el benchmark humano y la resolución o delimitación definitiva de las diferencias de visualización del PDF técnico.',
    'Permanece pendiente el benchmark humano. La supuesta pérdida de prefijos del PDF se descartó con ampliación y contraste; se corrigieron los avisos de fuente del pie para las nuevas exportaciones.')
guide = guide.replace('Persisten diferencias de renderizado en algunas páginas del PDF técnico; el HTML conserva el contenido.',
    'El complemento conserva el PDF técnico original y sus hashes. Las exportaciones nuevas incrustan la fuente del pie; no se atribuye compatibilidad universal entre visores.')
(out/'LEER_PRIMERO.md').write_text(guide,encoding='utf-8')
audit = json.loads((root/'seguimiento/AUDITORIA_P01_P14_308.json').read_text(encoding='utf-8'))
audit['fecha_utc'] = summary['fecha_utc']
audit['fuentes_evidencia'] += ['seguimiento/VALIDACION_DISTRIBUCION_312.json','seguimiento/REVISION_PDF_312.json',
                              'seguimiento/QA_PDF_INTEGRADO_312.json','seguimiento/REVISION_BENCHMARK_312.json']
for row in audit['criterios']:
    if row['id'] == 'P05': row['evidencia_y_limite'] = '1425pruebas Python y36de interfaz en312, sin omisiones. No equivale a aprobación profesional de las entradas.'
    if row['id'] == 'P12':
        row['estado'] = 'contenido contrastado y fuente del pie corregida'
        row['evidencia_y_limite'] = '309/310 descartaron pérdida de prefijos.312 conserva texto y píxeles MuPDF de8páginas e incrusta fuente del pie;67pruebas de informes correctas. No se afirma compatibilidad universal ni nueva descargaUI312.'
    if row['id'] == 'P14': row['evidencia_y_limite'] = 'Cadena real planos/revisión/modelo/análisis/13indicadores/informe conservada y distribución312 comprobada. P04 continúa pendiente; no demuestra automatización de cualquier construcción ni otra estación nativa.'
(out/'AUDITORIA_P01_P14.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
lines = ['# Auditoría P01–P14', '', 'La aceptación global permanece abierta; no se calcula un porcentaje de terminación.', '',
         '| Criterio | Estado | Evidencia y límite |','|---|---|---|']
lines += [f"| {r['id']} · {r['criterio']} | {r['estado']} | {r['evidencia_y_limite']} |" for r in audit['criterios']]
(out/'AUDITORIA_P01_P14.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({'estado':'distribucion_software_validada',**counts,'goal_completo':False},ensure_ascii=False))
