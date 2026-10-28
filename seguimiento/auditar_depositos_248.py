"""Localiza detalles de depósitos y conserva coordenadas de fuente; no modifica PDF."""
import hashlib
import json
from pathlib import Path
import pymupdf

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'tmp/auditoria_depositos_248'
OUT.mkdir(exist_ok=True)
items=[]
for path in sorted((ROOT/'planos_muestra/proyecto_pueblo_libre').glob('*.pdf')):
    with pymupdf.open(path) as doc:
        page=doc[0]
        hits=[]
        for line in page.get_text('dict')['blocks']:
            for row in line.get('lines',[]):
                text=''.join(s['text'] for s in row['spans'])
                if any(w in text.upper() for w in ('CISTERN','TANQUE','AGUA','NIVEL LIBRE','CUBA')):
                    hits.append({'texto':text,'bbox_pt_sin_rotar':list(row['bbox']), 'bbox_pt_vista':list(pymupdf.Rect(row['bbox'])*page.rotation_matrix)})
        (OUT/(path.stem+'.txt')).write_text(page.get_text(),encoding='utf-8')
        if hits:
            page.get_pixmap(matrix=pymupdf.Matrix(.65,.65),alpha=False).save(OUT/(path.stem+'.png'))
        items.append({'archivo':str(path.relative_to(ROOT)), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'pagina':1,'tamano_pt':list(page.rect),'rotacion_grados':page.rotation,'matriz_rotacion':list(page.rotation_matrix),'rotulos':hits})
(OUT/'indice.json').write_text(json.dumps(items,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for item in items:
    print(json.dumps({'archivo':item['archivo'],'rotulos':item['rotulos']},ensure_ascii=False))
