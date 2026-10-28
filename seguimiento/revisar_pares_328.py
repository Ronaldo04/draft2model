from pathlib import Path
import json,fitz
from PIL import Image,ImageDraw,ImageOps
root=Path(__file__).resolve().parents[1];dest=root/'seguimiento/revision_antigravity_328'
inv=json.loads((root/'seguimiento/claude_ruta/preparacion_benchmark_311/INVENTARIO_COHORTES_311.json').read_bytes())
consumo=json.loads((root/'seguimiento/CONSUMO_API_211.json').read_bytes());exposure=[];tiles=[];info=[]
kit=json.loads((root/'seguimiento/referencia_humana_308/fuentes.json').read_bytes());hashes={p['imagen_sha256']:p['archivo_id'] for p in kit['paginas']}
for c in inv['cohortes']:
 ledger=next(x for x in consumo[c['proveedor']] if x['numero']==c['numero'])
 result=json.loads((root/ledger['resultado'].replace('\\','/')).read_bytes())
 imgs=(result.get('configuracion') or {}).get('imagenes',[])
 exposure.append({'cohorte':c['cohorte'],'contextos_completos':[hashes[x['sha256']] for x in imgs if x.get('sha256') in hashes],'imagenes':len(imgs),'estado':c['estado']})
 if not c.get('extraccion_previa_correccion'):continue
 ext=json.loads((root/c['extraccion_previa_correccion']['ruta']).read_bytes());index={x['id']:x for x in ext['candidatos']}
 proposal=json.loads((dest/(c['cohorte']+'_sugerencias.json')).read_bytes())
 for pair in proposal['sugerencias']:
  candidate=index[pair['candidato_id']];e=candidate['evidencia'][pair['indice_evidencia_candidato']]
  a,b,cc,d=e['bbox_normalizada'];i=int(e['archivo_id'][1:]);doc=fitz.open(root/'seguimiento/ANTIGRAVITY_REFERENCIA_327/entradas/originales'/f'lamina-{i:04d}.pdf');p=doc[0];r=p.rect
  rect=fitz.Rect(a*r.width,b*r.height,cc*r.width,d*r.height)
  pix=p.get_pixmap(matrix=fitz.Matrix(6,6),clip=rect,alpha=False);im=Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
  name=c['cohorte']+'_'+candidate['id']+'_'+pair['observacion_id'];im.save(dest/(name+'.png'))
  tile=Image.new('RGB',(480,190),'#dddddd');draw=ImageDraw.Draw(tile)
  draw.text((6,6),name+' = '+str(candidate['valor_propuesto']),fill='black')
  small=ImageOps.contain(im,(460,145));tile.paste(small,((480-small.width)//2,34));tiles.append(tile)
  info.append({'nombre':name,'par':pair,'valor':candidate['valor_propuesto'],'unidad':candidate['unidad']})
grid=Image.new('RGB',(1440,190*((len(tiles)+2)//3)),'white')
for j,t in enumerate(tiles):grid.paste(t,((j%3)*480,(j//3)*190))
grid.save(dest/'pares-candidatos.png')
(dest/'EXPOSICION_328.json').write_text(json.dumps(exposure,ensure_ascii=False,indent=2),encoding='utf-8')
(dest/'PARES_PARA_DECIDIR_328.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(exposure,ensure_ascii=False))
