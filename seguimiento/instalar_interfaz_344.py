"""Porta solo UI344 a fuentes principales; no porta OCR ni reconstrucción experimental."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil

root=Path(__file__).resolve().parents[1]
dev=root/'tmp/desarrollo_geometria_337'
frozen=root/'tmp/validacion_distribucion_331/fuentes'
backup=root/'seguimiento/respaldo_interfaz_344'
receipt=root/'seguimiento/INTEGRACION_INTERFAZ_344.json'
if receipt.exists():raise SystemExit('Integración ya registrada: no repetir sobre fuentes cambiadas.')
core=['draft2model/revision_visual.py','draft2model/revision_web/index.html','draft2model/revision_web/app.js']
for name in core:
    assert (root/name).read_bytes()==(frozen/name).read_bytes(),f'Cambios previos sin revisar: {name}'
for name in core:
    target=backup/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/name,target)
def replace(name,old,new):
    path=root/name;text=path.read_text(encoding='utf-8');assert text.count(old)==1,(name,text.count(old))
    path.write_text(text.replace(old,new),encoding='utf-8')
assets=['etapas.js','etapas.css','editor_ingenieria.js','modelo_3d.js']
for name in assets:shutil.copy2(dev/'draft2model/revision_web'/name,root/'draft2model/revision_web'/name)
replace(core[0],"'verificacion_modelo.js','app.js'", "'etapas.js','etapas.css','editor_ingenieria.js','modelo_3d.js','verificacion_modelo.js','app.js'")
replace(core[1],'<link rel="stylesheet" href="/style.css">','<link rel="stylesheet" href="/style.css"><link rel="stylesheet" href="/etapas.css">')
replace(core[1],'</body></html>','<script src="/etapas.js"></script><script src="/editor_ingenieria.js"></script><script src="/modelo_3d.js"></script></body></html>')
replace(core[1],'Draft2Model · Revisar lecturas','Draft2Model · Proyecto estructural')
replace(core[1],'REVISIÓN DE PLANOS','FLUJO DE MODELADO')
replace(core[2],"geoControls();}\nasync function refreshGeo", "geoControls();window.dispatchEvent(new Event('d2m-geometry-opened'));}\nasync function refreshGeo")
replace(core[2],"geoControls();}\nasync function openGeo", "geoControls();window.dispatchEvent(new Event('d2m-geometry-opened'));}\nasync function openGeo")
replace(core[2],"renderReadings();controls();await openPage();", "renderReadings();controls();window.dispatchEvent(new Event('d2m-readings-opened'));await openPage();")
replace(core[2],"controls();}\nasync function openCase", "controls();window.dispatchEvent(new Event('d2m-readings-opened'));}\nasync function openCase")
for name in ['revision_editor_344_frontend.cjs','revision_modelo3d_344_frontend.cjs']:
    shutil.copy2(dev/'tests'/name,root/'tests'/name)
names=core+['draft2model/revision_web/'+a for a in assets]
receipt.write_text(json.dumps({'fecha_utc':datetime.now(timezone.utc).isoformat(),'version':'interfaz344',
    'respaldo':str(backup.relative_to(root)),'archivos':{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in names},
    'no_integra':['OCR335','anclajes342-343','reconstrucción automática experimental'],
    'entrega331_conservada':True,'goal_completo':False},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('UI344 integrada en fuentes principales; copia331 y expediente intactos.')
