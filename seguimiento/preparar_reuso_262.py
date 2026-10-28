"""Crear candidato aislado desde fuentes estables; no portar sobre archivos de Claude."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'tmp/reuso_preparacion_262'
OUT=BASE/'fuentes'
OUT.mkdir(exist_ok=False)
names=('draft2model/modelo_estructural.py','draft2model/operaciones_etabs.py')
frozen={name:(ROOT/name).read_bytes() for name in names}
for folder in ('draft2model','tests','examples'):
    shutil.copytree(ROOT/folder,OUT/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.pyo'))
for name,raw in frozen.items():
    if (ROOT/name).read_bytes()!=raw or (OUT/name).read_bytes()!=raw:
        raise ValueError('Fuentes cambiaron durante copia; no generar candidato: '+name)
shutil.copyfile(BASE/'reuso_preparacion.py',OUT/'draft2model/reuso_preparacion.py')
shutil.copyfile(BASE/'test_reuso_262.py',OUT/'test_reuso_262.py')
model=frozen[names[0]].decode('utf-8').replace('\r\n','\n')
old='            self.preparacion = mp.preparar_malla(geometria, d)'
new='''            from . import reuso_preparacion as rp
            try:
                entradas_preparacion = rp.huellas(geometria, d)
                self.preparacion = mp.preparar_malla(geometria, d)
                self.r._preparacion_malla_reutilizable = rp.sellar(geometria, d, self.preparacion, entradas_preparacion)
            except (ValueError, TypeError) as error:
                raise mp.ErrorMalla(str(error)) from error'''
if model.count(old)!=1:raise ValueError('Sitio de preparación ambiguo')
(OUT/names[0]).write_text(model.replace(old,new),encoding='utf-8')
operations=frozen[names[1]].decode('utf-8').replace('\r\n','\n')
old='        prep = me.mp.preparar_malla(consulta.geometria, config)'
new='''        from . import reuso_preparacion as rp
        prep = rp.obtener(getattr(resultado, "_preparacion_malla_reutilizable", None), consulta.geometria, config)
        if prep is None:
            prep = me.mp.preparar_malla(consulta.geometria, config)'''
if operations.count(old)!=1:raise ValueError('Sitio de compilación ambiguo')
(OUT/names[1]).write_text(operations.replace(old,new),encoding='utf-8')
manifest={'fuentes_base':{name:hashlib.sha256(raw).hexdigest() for name,raw in frozen.items()},
          'portado':False,'alcance':'Reutilización solo en resultado privado validado; entradas completas, sin globales ni persistencia'}
(BASE/'congelado.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print(json.dumps(manifest))
