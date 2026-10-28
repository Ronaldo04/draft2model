"""Revisión de integridad y muestras visuales regeneradas desde fuentes, sin confiar en recortes del agente."""
from pathlib import Path
from collections import Counter
import argparse,hashlib,json,math
from PIL import Image,ImageDraw,ImageOps
import fitz

root=Path(__file__).resolve().parents[1];base=root/'seguimiento/ANTIGRAVITY_REFERENCIA_327'
dest=root/'seguimiento/revision_antigravity_328';dest.mkdir(exist_ok=True)
parser=argparse.ArgumentParser();parser.add_argument('--corregida',action='store_true');args=parser.parse_args()
refpath=(dest/'propuesta_corregida_328.json') if args.corregida else (base/'salidas/referencia_propuesta_ia.json')
ref=json.loads(refpath.read_bytes())
marker=json.loads((base/'salidas/MARCADOR_FINAL.json').read_bytes())
kit=json.loads((root/'seguimiento/referencia_humana_308/fuentes.json').read_bytes())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
checks=[]
for group in ('hashes_entregables','hashes_recortes'):
    for name,digest in marker[group].items():
        p=base/name;assert p.resolve().is_relative_to(base.resolve())
        checks.append({'archivo':name,'coincide':sha(p)==digest})
pages={p['archivo_id']:p for p in kit['paginas']}
for i,p in enumerate(kit['paginas'],1):
    checks.append({'archivo':p['archivo_id']+' PDF','coincide':sha(base/'entradas/originales'/f'lamina-{i:04d}.pdf')==p['original_sha256']})
    checks.append({'archivo':p['imagen'],'coincide':sha(base/'entradas'/p['imagen'])==p['imagen_sha256']})
manifest=json.loads((root/'entregas/AECODE_ENTREGA_325/MANIFIESTO.json').read_bytes())
changed=[n for n,h in manifest['archivos'].items() if not n.startswith('wheels/') and sha(root/n)!=h]
assert not changed,changed
assert all(c['coincide'] for c in checks)
tiles=[];rows=[]
for obs in ref['observaciones']:
    e=obs['evidencia'][0];page=pages[e['archivo_id']]
    assert e['original_sha256']==page['original_sha256'] and e['imagen_sha256']==page['imagen_sha256']
    x0,y0,x1,y1=e['bbox_normalizada'];assert 0<=x0<x1<=1 and 0<=y0<y1<=1
    i=int(e['archivo_id'][1:]);doc=fitz.open(base/'entradas/originales'/f'lamina-{i:04d}.pdf');p=doc[0]
    # Región canónica con pequeño margen; render vectorial para confirmar letras diminutas.
    r=p.rect;pad=.004
    box=fitz.Rect(max(0,x0-pad)*r.width,max(0,y0-pad)*r.height,min(1,x1+pad)*r.width,min(1,y1+pad)*r.height)
    pix=p.get_pixmap(matrix=fitz.Matrix(5,5),clip=box,alpha=False)
    im=Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
    im.save(dest/(('COR-' if args.corregida else '')+obs['id']+'.png'))
    tile=Image.new('RGB',(480,180),'#eeeeee');draw=ImageDraw.Draw(tile)
    draw.text((8,7),f"{obs['id']} {e['archivo_id']} {obs['tipo']} = {obs['valor']} [{obs['unidad']}]",fill='black')
    scaled=ImageOps.contain(im,(460,140));tile.paste(scaled,((480-scaled.width)//2,32));tiles.append(tile)
    rows.append({'id':obs['id'],'tipo':obs['tipo'],'valor':obs['valor'],'unidad':obs['unidad'],'legibilidad':obs['legibilidad']})
for n in range(0,len(tiles),12):
    grid=Image.new('RGB',(480*3,180*4),'white')
    for j,im in enumerate(tiles[n:n+12]):grid.paste(im,((j%3)*480,(j//3)*180))
    grid.save(dest/f'{"corregido" if args.corregida else "contacto"}-{n//12+1}.png')
out={'integridad':checks,'fuentes_publicas325_sin_cambios':True,'observaciones':len(rows),
     'por_clase':dict(Counter(x['tipo'] for x in rows)),'propuesta_sha256':sha(base/'salidas/referencia_propuesta_ia.json'),
     'revision_visual':'pendiente','revision_humana_realizada':False,'resumen_observaciones':rows}
(dest/('REVISION_CORREGIDA_328.json' if args.corregida else 'REVISION_328.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'integridad':'OK','archivos_comprobados':len(checks),'observaciones':len(rows),'fuentes325':'intactas','contactos':3}))
