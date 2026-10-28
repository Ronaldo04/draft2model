"""Inventario ciego de texto PDF original para una referencia asistida; NO es revisión humana."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
import fitz

root=Path(__file__).resolve().parents[1]
kit=json.loads((root/'seguimiento/referencia_humana_308/fuentes.json').read_bytes())
dest=root/'seguimiento/referencia_codex_326';dest.mkdir(exist_ok=True)
target=dest/'texto_originales.json';assert not target.exists(), 'No sobrescribir el inventario ciego.'
pages=[]
for i,meta in enumerate(kit['paginas'],1):
    path=root/'data/private/provisional-001/originales'/f'lamina-{i:04d}.pdf'
    assert hashlib.sha256(path.read_bytes()).hexdigest()==meta['original_sha256']
    doc=fitz.open(path);page=doc[0];words=[]
    for x0,y0,x1,y1,text,*_ in page.get_text('words'):
        box=fitz.Rect(x0,y0,x1,y1)*page.rotation_matrix
        rect=page.rect
        words.append({'texto':text,'bbox_normalizada':[box.x0/rect.width,box.y0/rect.height,box.x1/rect.width,box.y1/rect.height]})
    pages.append({**meta,'rotacion_pdf':page.rotation,'palabras_fuente':words})
out={'contrato':'seguimiento.referencia_codex_preparacion','fecha_utc':datetime.now(timezone.utc).isoformat(),
     'caso':kit['caso'],'anotador':'Codex (IA)','autorizacion':'Usuario: aún no lo termino y por esta vez complétalo tú.',
     'revision_humana_realizada':False,'respuestas_previas_sistema_consultadas':False,
     'estado':'inventario_textual_pendiente_de_revision_visual','observaciones_referencia_completadas':0,
     'paginas':pages,'advertencia':'Texto extraído directamente del PDF. Puede no coincidir con su apariencia visible; no prueba legibilidad ni es verdad humana. No puntuar desde este inventario.'}
target.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'archivo':str(target.relative_to(root)),'palabras_por_lamina':{p['archivo_id']:len(p['palabras_fuente']) for p in pages},'revision_humana':False,'llamadas_api':0}))
