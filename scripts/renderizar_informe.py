"""Rasterizar un informe para su inspección visual local, sin alterar el PDF."""
import argparse
from pathlib import Path
import pymupdf
from PIL import Image, ImageOps, ImageDraw

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--pdf',type=Path,required=True);p.add_argument('--salida',type=Path,required=True)
args=p.parse_args()
args.salida.mkdir()
with pymupdf.open(args.pdf) as doc:
    if len(doc)>50: raise ValueError('Inspeccionar por lotes: máximo 50 páginas.')
    thumbs=[]
    for n,page in enumerate(doc):
        pix=page.get_pixmap(matrix=pymupdf.Matrix(1.3,1.3),alpha=False)
        target=args.salida/f'pagina-{n+1:02}.png';pix.save(target)
        with Image.open(target) as image:
            thumb=ImageOps.contain(image,(380,540)).copy()
        thumbs.append(thumb)
    rows=(len(thumbs)+2)//3
    sheet=Image.new('RGB',(1200,rows*580),'#dce4e7');draw=ImageDraw.Draw(sheet)
    for n,thumb in enumerate(thumbs):
        x=(n%3)*400+10;y=(n//3)*580+25;sheet.paste(thumb,(x,y));draw.text((x,y-18),f'Página {n+1}',fill='black')
    sheet.save(args.salida/'contacto.png')
print(args.salida/'contacto.png')
