"""Preparar imágenes y anotador vacío; no crea verdad humana ni llama a IA."""
from pathlib import Path
import hashlib
import json
import shutil

root=Path(__file__).resolve().parents[1]
case=root/'data/private/provisional-001'
record=json.loads((case/'expediente.json').read_text(encoding='utf-8'))
review=json.loads((case/'revision_documental/bed45cd9875c4e9d8cf46fafd58711d1/revision.json').read_text(encoding='utf-8'))
out=root/'seguimiento/referencia_humana_308';out.mkdir(exist_ok=False)
(out/'imagenes').mkdir()
pages=[]
for document in review['documentos']:
    original=next(x for x in record['archivos'] if x['id']==document['id'])
    raw=(case/original['archivo']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==original['sha256']
    for p in document['paginas']:
        source=case/p['vista_previa'];image=source.read_bytes()
        target=out/'imagenes'/source.name;target.write_bytes(image)
        pages.append({'archivo_id':original['id'],'nombre':original['nombre_original'],
            'pagina':p['numero'],'original_sha256':original['sha256'],
            'imagen_sha256':hashlib.sha256(image).hexdigest(),'imagen':'imagenes/'+target.name})
data={'caso':record['id'],'alcance':record['alcance'],
      'procedencia':{'tipo':'expediente','descripcion':'Referencia humana de los originales de Pueblo Libre; no contiene respuestas de IA.'},
      'paginas':pages,'observaciones_anotadas':0,'revision_humana_realizada':False}
template=(root/'seguimiento/anotador_referencia_308.html').read_text(encoding='utf-8')
assert template.count('__DATA__')==1
(out/'Anotar_referencia.html').write_text(template.replace('__DATA__',json.dumps(data,ensure_ascii=False).replace('<','\\u003c')),encoding='utf-8')
(out/'fuentes.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copyfile(root/'examples/referencia_vision.csv',out/'referencia_vision_vacia.csv')
print(json.dumps({'carpeta':str(out),'paginas':len(pages),'observaciones':0,'no_es_referencia_revisada':True}))
