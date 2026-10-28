"""Integra navegación guiada y editores en la copia de desarrollo; conserva331."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'tmp/desarrollo_geometria_337/draft2model'
def replace(path,old,new):
    text=path.read_text(encoding='utf-8')
    if new in text:return
    assert text.count(old)==1,(path.name,old,text.count(old))
    path.write_text(text.replace(old,new),encoding='utf-8')
replace(root/'revision_web/index.html','<link rel="stylesheet" href="/style.css">',
        '<link rel="stylesheet" href="/style.css"><link rel="stylesheet" href="/etapas.css">')
replace(root/'revision_web/index.html','</body></html>',
        '<script src="/etapas.js"></script><script src="/editor_ingenieria.js"></script><script src="/modelo_3d.js"></script></body></html>')
replace(root/'revision_visual.py',"'verificacion_modelo.js','app.js'",
        "'etapas.js','etapas.css','editor_ingenieria.js','modelo_3d.js','verificacion_modelo.js','app.js'")
app=root/'revision_web/app.js'
replace(app,"geoControls();}\nasync function refreshGeo", "geoControls();window.dispatchEvent(new Event('d2m-geometry-opened'));}\nasync function refreshGeo")
replace(app,"geoControls();}\nasync function openGeo", "geoControls();window.dispatchEvent(new Event('d2m-geometry-opened'));}\nasync function openGeo")
replace(app,"renderReadings();controls();await openPage();", "renderReadings();controls();window.dispatchEvent(new Event('d2m-readings-opened'));await openPage();")
print('Interfaz344 integrada únicamente en desarrollo337.')
