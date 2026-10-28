"""Renderizar el informe nuevo para inspección, sin modificar el PDF ni recalcular."""
from pathlib import Path
import argparse,hashlib,json, shutil, subprocess
import fitz
from PIL import Image,ImageOps,ImageDraw

root=Path(__file__).resolve().parents[1]
s=json.loads((root/'seguimiento/FLUJO_AUTO_322.json').read_bytes())
args=argparse.ArgumentParser();args.add_argument('--borrador',type=Path);args=args.parse_args()
folder=(root/'data/private/pueblo-libre-002/informes'/s['informe']) if s.get('informe') else args.borrador
assert folder, 'Esperar a que el servicio publique el informe o indicar borrador solo para QA.'
meta=json.loads((folder/'paquete.json').read_bytes())
raw=(folder/'informe.pdf').read_bytes()
dest=root/'tmp/pdfs/auto_322';dest.mkdir(parents=True,exist_ok=True)
pdf=dest/'informe_qa.pdf';pdf.write_bytes(raw)
doc=fitz.open(pdf)
pages=[]
for i,p in enumerate(doc):
    text=p.get_text()
    if 'peso efectivo' in text or 'Descuento' in text or 'descuento' in text:
        pages.append(i+1)
assert pages, 'No se encontró la sección nueva en el PDF.'
exe=shutil.which('pdftoppm');assert exe, 'Poppler no disponible.'
subprocess.run([exe,'-png','-scale-to','950',str(pdf),str(dest/'pagina')],check=True,capture_output=True)
images=[]
for p in sorted(dest.glob('pagina-*.png')):
    with Image.open(p) as im:
        thumbnail=ImageOps.contain(im.convert('RGB'),(380,540))
        tile=Image.new('RGB',(400,570),'#dddddd');tile.paste(thumbnail,((400-thumbnail.width)//2,25))
        ImageDraw.Draw(tile).text((12,8),p.stem,fill='black');images.append(tile)
grid=Image.new('RGB',(400*3,570*((len(images)+2)//3)),'white')
for i,im in enumerate(images):grid.paste(im,((i%3)*400,(i//3)*570))
grid.save(dest/'contacto.png')
result={'informe':meta['id'],'publicado':bool(s.get('informe')),'sha256_pdf':hashlib.sha256(raw).hexdigest(),
        'paginas':len(doc),'paginas_seccion_auto':pages,
        'renderizado_poppler':True,'inspeccion_visual':'pendiente','contacto':str((dest/'contacto.png').relative_to(root)),
        'pdf_modificado':False}
(root/'seguimiento/QA_PDF_AUTO_322.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
