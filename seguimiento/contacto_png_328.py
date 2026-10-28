from pathlib import Path
import json
from PIL import Image,ImageDraw,ImageOps
root=Path(__file__).resolve().parents[1];base=root/'seguimiento/ANTIGRAVITY_REFERENCIA_327';dest=root/'seguimiento/revision_antigravity_328'
ref=json.loads((base/'salidas/referencia_propuesta_ia.json').read_bytes())
kit=json.loads((base/'entradas/fuentes.json').read_bytes());pages={p['archivo_id']:p for p in kit['paginas']};tiles=[]
for obs in ref['observaciones']:
 e=obs['evidencia'][0];im=Image.open(base/'entradas'/pages[e['archivo_id']]['imagen']).convert('RGB');w,h=im.size
 a,b,c,d=e['bbox_normalizada'];crop=im.crop((int(a*w)-3,int(b*h)-3,int(c*w)+4,int(d*h)+4))
 tile=Image.new('RGB',(480,180),'#eeeeee');ImageDraw.Draw(tile).text((7,6),str(obs['id'])+' = '+str(obs['valor']),fill='black')
 scaled=ImageOps.contain(crop,(460,140),Image.Resampling.NEAREST);tile.paste(scaled,((480-scaled.width)//2,32));tiles.append(tile)
for n in range(0,len(tiles),12):
 grid=Image.new('RGB',(1440,720),'white')
 for i,im in enumerate(tiles[n:n+12]):grid.paste(im,((i%3)*480,(i//3)*180))
 grid.save(dest/f'png-{n//12+1}.png')
