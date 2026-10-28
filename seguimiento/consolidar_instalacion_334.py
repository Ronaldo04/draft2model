"""Anexo de verificación offline; conserva íntegra la entrega331 ya publicada."""
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
from datetime import datetime,timezone

root=Path(__file__).resolve().parents[1]
report=json.loads((root/'tmp/i334/verificacion.json').read_text(encoding='utf-8'))
delivery=json.loads((root/'seguimiento/ENTREGA_ACADEMICA_331_FINAL.json').read_text(encoding='utf-8'))
assert report['completa'] and report['entorno_aislado'] and report['corridas_completadas']==6
assert len(report['comprobaciones'])==6 and all(c['codigo']==0 for c in report['comprobaciones'])
install=next(c for c in report['comprobaciones'] if c['nombre']=='instalar')
assert '--no-index' in install['comando'] and '--require-hashes' in install['comando']
manifest=json.loads((root/'entregas/AECODE_PRESENTACION_331/software/MANIFIESTO.json').read_text(encoding='utf-8'))
source=root/'tmp/validacion_distribucion_331/fuentes'
assert all(hashlib.sha256((source/n).read_bytes()).hexdigest()==h for n,h in manifest['archivos'].items())
assert hashlib.sha256((root/delivery['archivo']).read_bytes()).hexdigest()==delivery['sha256']
out=root/'entregas/ANEXO_INSTALACION_OFFLINE_334'
out.mkdir(exist_ok=False)
shutil.copyfile(root/'tmp/i334/verificacion.json',out/'verificacion.json')
for check in report['comprobaciones']:
 shutil.copyfile(Path(check['registro']),out/(check['nombre']+'.log'))
text='''# Instalación offline verificada de la entrega331

Se creó un entorno Python3.10x64 nuevo, sin paquetes globales, usando los wheels
incluidos en el ZIP de software331 y el lock con hashes. Las seis comprobaciones
terminaron correctamente: crear entorno, instalar con --no-index y --require-hashes,
pip check, arranque CLI, ejecución de la demo integrada y verificación de sus seis
corridas. Los módulos nuevos331 se importaron con Pillow12.3.0 y PyMuPDF1.28.2
procedentes del entorno nuevo. Los616archivos distribuidos siguen idénticos.

Esto prueba instalación en otro entorno de la misma estación Windows; no en otro
equipo ni una licencia ETABS nueva. La demo es sintética, sin visión real ni análisis
nativo; no sustituye el caso real archivado. No se hicieron llamadas a proveedores.
No cambió el ZIP331: este anexo aporta evidencia posterior a su generación.
Los recibos conservan las rutas del equipo de prueba; no son una instalación ya
realizada en el equipo del evaluador.
'''
(out/'LEER_PRIMERO.md').write_text(text,encoding='utf-8')
evidence={'fecha_utc':datetime.now(timezone.utc).isoformat(),'entrega_verificada':delivery,
          'instalacion_completa':True,'comprobaciones':6,'corridas_demo_sintetica':6,
          'archivos_fuentes_intactos':len(manifest['archivos']),'otro_equipo':False,
          'etabs_nativo_nuevo':False,'api_calls':0,
          'archivos':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}}
(out/'EVIDENCIA.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
archive=root/'entregas/ANEXO_INSTALACION_OFFLINE_334.zip'
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
 for p in sorted(out.iterdir()):z.write(p,out.name+'/'+p.name)
with zipfile.ZipFile(archive) as z:
 for n,h in evidence['archivos'].items():assert hashlib.sha256(z.read(out.name+'/'+n)).hexdigest()==h
receipt={'archivo':str(archive.relative_to(root)),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
         'bytes':archive.stat().st_size,'entrega331_intacta':True,'resultado':'instalacion_offline_correcta'}
(root/'seguimiento/INSTALACION_334.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt,ensure_ascii=False))
