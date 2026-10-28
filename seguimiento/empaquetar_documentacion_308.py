"""Distribuir la documentación final con código idéntico al306 probado."""
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
from urllib.parse import unquote, urlparse
import hashlib
import json
import posixpath
import re
import shutil
import subprocess
import sys
import zipfile

root=Path(__file__).resolve().parents[1]
replacements={
 'README.md': [('La documentación307 conserva el mismo código probado en306.',
                'Esta distribución conserva el mismo código probado en306.')],
 'docs/GUIA_REPRODUCIBLE.md': [('La documentación307 conserva ese código.',
                              'Esta distribución conserva ese código.')],
 'docs/ENTREGA_AECODE.md': [('Corte307:','Corte documental24de octubre de2026:'),
                          ('una suite nueva307','una suite nueva para esta actualización documental')],
 'docs/CONTEXTO_PROYECTO.md': [
   ('documentación307 sin cambios de código','actualización documental sin cambios de código'),
   ('[desarrollo técnico](../SismoVivienda_AI_Desarrollo_Tecnico.pdf)',
    'desarrollo técnico (`SismoVivienda_AI_Desarrollo_Tecnico.pdf`, antecedente del repositorio de desarrollo)'),
   ('[entrega de avance](<../SismoVivienda_AI_Entrega_Avance 01 - 03-10-2026.pdf>)',
    'entrega de avance (`SismoVivienda_AI_Entrega_Avance 01 - 03-10-2026.pdf`, antecedente del repositorio de desarrollo)')]
}
for name, pairs in replacements.items():
    path=root/name;text=path.read_text(encoding='utf-8')
    for old,new in pairs:
        assert old in text,(name,old)
        text=text.replace(old,new)
    path.write_text(text,encoding='utf-8')

out=root/'entregas/AECODE_ENTREGA_308'
subprocess.run([sys.executable,'scripts/crear_paquete_aecode.py','--salida',str(out),
    '--wheels','tmp/validacion_distribucion_306/fuentes/wheels'],cwd=root,check=True)
manifest=json.loads((out/'MANIFIESTO.json').read_text(encoding='utf-8'))
baseline=json.loads((root/'entregas/AECODE_RC_306/MANIFIESTO.json').read_text(encoding='utf-8'))
assert set(manifest['archivos'])==set(baseline['archivos'])
changed=[n for n,h in manifest['archivos'].items() if h!=baseline['archivos'][n]]
assert changed and all(n=='README.md' or n.startswith('docs/') for n in changed)
selected=('README.md','docs/GUIA_REPRODUCIBLE.md','docs/ENTREGA_AECODE.md',
          'docs/CONTEXTO_PROYECTO.md','docs/NORMATIVA_APLICADA.md',
          'docs/EVALUACION_VISION.md','docs/MATRIZ_REQUISITOS_REFERENCIA.md')
links=0;missing=[]
with zipfile.ZipFile(out/'Draft2Model.zip') as archive:
    assert len(archive.namelist())==len(set(archive.namelist()))==len(manifest['archivos'])
    assert set(archive.namelist())==set(manifest['archivos'])
    for name,h in manifest['archivos'].items():
        assert hashlib.sha256(archive.read(name)).hexdigest()==h
    for name in selected:
        for target in re.findall(r'\]\((<[^>]+>|[^)\n]+)\)',archive.read(name).decode('utf-8')):
            target=target.strip('<>');url=urlparse(target)
            if url.scheme or target.startswith('#'):continue
            resolved=posixpath.normpath(str(PurePosixPath(name).parent/unquote(url.path)))
            links+=1
            if resolved not in manifest['archivos']:missing.append([name,target])
assert not missing,missing
shutil.copytree(root/'entregas/AECODE_RC_306/EVIDENCIAS',out/'EVIDENCIAS')
shutil.copyfile(root/'entregas/AECODE_RC_306/REFERENCIA_DATOS_Y_NORMATIVA.md',out/'REFERENCIA_DATOS_Y_NORMATIVA.md')
args=[str(root/'tmp/validacion_distribucion_303/.venv/Scripts/python.exe'),
      str(root/'tmp/validacion_distribucion_306/fuentes/scripts/verificar_entrega_aecode.py'),
      '--fuentes',str(out),'--complemento',str(root/'entregas/COMPLEMENTO_CORREGIDO_303'),
      '--huella-esperada',manifest['huella_fuentes']]
checked=subprocess.run(args,cwd=root,capture_output=True,text=True,encoding='utf-8',check=True)
integrity=json.loads(checked.stdout)
summary={'fecha_utc':datetime.now(timezone.utc).isoformat(),'huella_fuentes':manifest['huella_fuentes'],
    'archivos':len(manifest['archivos']),'diferencias_con306_solo_documentales':changed,
    'codigo_pruebas_dependencias_recursos_identicos_a306':True,
    'suite_nueva308_ejecutada':False,'suite306':'EVIDENCIAS/verificacion_global.json',
    'resultado_suite306':{'python':1424,'interfaz':36,'omisiones':[],'fuentes_estables':True},
    'instalacion':'Offline303 comprobada; entorno reutilizado306 con lock/wheels idénticos. No nueva instalación308.',
    'enlaces_locales_documentacion_actual':links,'enlaces_faltantes':missing,
    'integridad_conjunto':integrity,'qa':'QA_DESCARGA_Y_306_307.json; apertura306 observada, descargaChrome303 asistida y hash real comprobado',
    'aceptacion_global':False,'motivo':'Benchmark humano incompleto; no soporte universal validado. Ver auditoría P01-P14 y límites del piloto.',
    'aprueba_ingenieria':False,'goal_completo':False}
(out/'VALIDACION.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(root/'seguimiento/REVISION_DOCUMENTACION_ENTREGA_308.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'huella':manifest['huella_fuentes'],'solo_documentos':changed,'enlaces':links,'integridad':integrity['estado']},ensure_ascii=False))
