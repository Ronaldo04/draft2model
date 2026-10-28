"""Aclarar atribución de resultados del modelo, conservando el ZIP previo recuperable."""
from pathlib import Path
import hashlib,json,os,shutil,zipfile
root=Path(__file__).resolve().parents[1];out=root/'entregas/AECODE_PRESENTACION_328';archive=root/'entregas/AECODE_PRESENTACION_328_FINAL.zip'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(archive)=='735d6abda2d30f99dfdee949380fce775f70ed9856997641aa0d879b78c0e842'
backup=root/'tmp/entrega328_revisiones';backup.mkdir(exist_ok=True)
shutil.copyfile(archive,backup/'anterior_a_aclaracion_modelo.zip')
p=out/'REPORTE_ESTADO.md';text=p.read_text(encoding='utf-8')
text=text.replace('Mostrar fallos del edificio no es un fallo del software; no se alteraron para obtener aprobación.',
 'Una comparación no satisfactoria no demuestra por sí sola un fallo del software ni inseguridad del edificio: depende del modelo y sus hipótesis. No se alteraron resultados para obtener aprobación.')
text=text.replace('Hoy sigue siendo necesaria revisión supervisada de planos y configuración.',
 'Hoy sigue siendo necesaria revisión supervisada de planos y configuración. No está acreditado pasar de un proyecto nuevo a geometría/configuración correctas sin intervención técnica.')
text=text.replace('Los resultados no constituyen diseño ejecutivo aprobado.',
 'Los resultados no constituyen diseño ejecutivo aprobado. El motor cubre las reglas y parámetros documentados, no una comprobación integral de todo el RNE.')
p.write_text(text,encoding='utf-8')
manifest_path=out/'MANIFIESTO_ENTREGA.json';m=json.loads(manifest_path.read_bytes())
m['archivos']={p.relative_to(out).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(out.rglob('*')) if p.is_file() and p!=manifest_path}
manifest_path.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
temp=backup/'presentacion_actualizada.zip';assert not temp.exists()
with zipfile.ZipFile(temp,'x',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(out.rglob('*')):
  if p.is_file():z.write(p,'AECODE_PRESENTACION_328/'+p.relative_to(out).as_posix())
with zipfile.ZipFile(temp) as z:
 for n,item in m['archivos'].items():assert hashlib.sha256(z.read('AECODE_PRESENTACION_328/'+n)).hexdigest()==item['sha256']
os.replace(temp,archive)
summary_path=root/'seguimiento/ENTREGA_ACADEMICA_328_FINAL.json';summary=json.loads(summary_path.read_bytes())
summary.update(sha256=sha(archive),bytes=archive.stat().st_size,aclaracion_modelo='Resultados condicionados a modelo/hipótesis; no juicio de seguridad del edificio ni RNE integral.')
summary_path.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'paquete_final':str(archive.relative_to(root)),'sha256':summary['sha256'],'integridad':'verificada','programa325_sin_cambios':True}))
