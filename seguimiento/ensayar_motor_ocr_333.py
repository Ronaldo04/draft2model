"""Contrasta el motor aislado con la primera lámina, sin alterar el caso ni331."""
import hashlib
import json
from pathlib import Path
import sys

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'tmp/desarrollo_ocr_333'))
from draft2model.ocr_local import reconocer_pagina_pdf,buscar_literal_ocr
import pymupdf
from PIL import Image,ImageDraw

source=root/'data/private/provisional-001/originales/lamina-0001.pdf'
raw=source.read_bytes()
result=reconocer_pagina_pdf(raw,1)
out=root/'tmp/desarrollo_ocr_333/tmp/ocr_real'
out.mkdir(parents=True,exist_ok=True)
full=out/'lectura.json'
full.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
report={'metodo':'OCR local aislado333; sin modificar entrega331',
        'original_sha256':result['original_sha256'],'render_sha256':result['render_sha256'],
        'perfil':result['perfil'],'palabras':len(result['palabras']),
        'api_calls':0,'lectura_sha256':hashlib.sha256(full.read_bytes()).hexdigest(),
        'coincidencias':{}}
with pymupdf.open(stream=raw,filetype='pdf') as doc:
 page=doc[0]
 pix=page.get_pixmap(matrix=pymupdf.Matrix(min(4,4096/max(page.rect.width,page.rect.height)),
                                         min(4,4096/max(page.rect.width,page.rect.height))),alpha=False)
 image=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
 tiles=[]
 for literal in ('C-1','C-2','C-6','PL-1','PL-10'):
  found=buscar_literal_ocr(result['palabras'],literal)
  report['coincidencias'][literal]=found
  for region in found['regiones'][:2]:
   b=region['bbox_normalizada']
   crop=image.crop((max(0,int(b[0]*pix.width)-15),max(0,int(b[1]*pix.height)-15),
                    min(pix.width,int(b[2]*pix.width)+15),min(pix.height,int(b[3]*pix.height)+15)))
   crop.thumbnail((580,110))
   tile=Image.new('RGB',(600,145),'white')
   ImageDraw.Draw(tile).text((8,5),literal+' | confianza OCR: '+str(region['confianza_ocr']),fill='black')
   tile.paste(crop,(8,28));tiles.append(tile)
 sheet=Image.new('RGB',(600,145*len(tiles)),'white')
 for index,tile in enumerate(tiles):sheet.paste(tile,(0,145*index))
 sheet.save(out/'regiones.png')
assert source.read_bytes()==raw
target=root/'seguimiento/OCR_LOCAL_333_REAL.json'
target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'palabras':report['palabras'], 'estados':{k:v['estado'] for k,v in report['coincidencias'].items()}},ensure_ascii=False))
