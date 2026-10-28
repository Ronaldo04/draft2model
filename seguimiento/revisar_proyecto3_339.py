"""Inventario y vistas de planos del proyecto3 autorizado; no modela ni llama APIs."""
import hashlib
import json
from pathlib import Path
import re
import pymupdf
from PIL import Image,ImageDraw

root=Path(__file__).resolve().parents[1]
source=root/'planos_muestra/proyecto_3_vivienda_unifamiliar'
out=root/'seguimiento/revision_proyecto3_339';out.mkdir(exist_ok=True)
records=[];tiles=[]
for index,path in enumerate(sorted(source.glob('*.pdf')),1):
    raw=path.read_bytes();pages=[];text=[]
    with pymupdf.open(stream=raw,filetype='pdf') as doc:
        for p,page in enumerate(doc,1):
            literal=page.get_text()
            text.append(literal)
            scale=1800/max(page.rect.width,page.rect.height)
            pix=page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),alpha=False)
            name=f'{index:02d}-pagina-{p}.png';pix.save(out/name)
            im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples);im.thumbnail((900,600))
            tile=Image.new('RGB',(920,640),'white');ImageDraw.Draw(tile).text((8,8),path.name+f' | pagina {p}',fill='black')
            tile.paste(im,(10,30));tiles.append(tile)
            pages.append({'pagina':p,'puntos':[page.rect.width,page.rect.height],
                          'palabras_vectoriales':len(page.get_text('words')),'caracteres_texto':len(literal),'vista':name})
    (out/f'{index:02d}-texto.txt').write_text('\n\n'.join(text),encoding='utf-8')
    joined='\n'.join(text)
    lines=[s.strip() for s in joined.splitlines() if s.strip()]
    keywords=[s for s in lines if re.search(r'(?i)nivel|piso|techo|azotea|cisterna|tanque|f.c|f.y|suelo|alba|ladrillo|king|sismo|[0-9]+\.[0-9]+|escala|carga|losa|cimiento',s)]
    records.append({'archivo':path.name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'paginas':pages,
                    'seleccion_textual':keywords[:150]})
    print(path.name,'paginas=',len(pages),'palabras=',sum(p['palabras_vectoriales'] for p in pages))
if tiles:
    sheet=Image.new('RGB',(1840,640*((len(tiles)+1)//2)),'white')
    for i,tile in enumerate(tiles):sheet.paste(tile,((i%2)*920,(i//2)*640))
    sheet.save(out/'contacto.png')
(out/'INVENTARIO.json').write_text(json.dumps({'proyecto':'proyecto_3_vivienda_unifamiliar','api_calls':0,
  'autorizado_por_usuario':'24Oct, solicitud expresa de usar proyecto3','archivos':records},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
