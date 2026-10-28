"""Contraste de etiquetas de la referencia IA fijada; sin cambiarla ni leer APIs."""
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw
import pymupdf
from draft2model.localizacion_literal_pdf import localizar_literal_pdf

root = Path(__file__).resolve().parents[1]
ref = root / 'seguimiento/revision_antigravity_328/referencia_asistida_328.json'
before = ref.read_bytes()
data = json.loads(before)
out = root / 'seguimiento/localizacion_331'
out.mkdir(exist_ok=True)
records, tiles = [], []
for obs in data['observaciones']:
    if not isinstance(obs['valor'], str) or obs['legibilidad'] != 'legible':
        continue  # no inventar formato decimal a partir de un número
    ev = obs['evidencia'][0]
    source = root / 'data/private/provisional-001/originales' / (ev['archivo_id'].replace('L', 'lamina-') + '.pdf')
    raw = source.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ev['original_sha256']
    result = localizar_literal_pdf(raw, ev['pagina'], obs['valor'])
    records.append({'observacion': obs['id'], 'literal_referencia_ia': obs['valor'], **result})
    if result['estado'] == 'unica' and len(tiles) < 6:
        bbox = result['regiones'][0]['bbox_normalizada']
        with pymupdf.open(stream=raw, filetype='pdf') as doc:
            page = doc[ev['pagina']-1]
            rect = pymupdf.Rect(bbox[0]*page.rect.width, bbox[1]*page.rect.height,
                                bbox[2]*page.rect.width, bbox[3]*page.rect.height)
            clip = (rect + (-8, -8, 8, 8)) & page.rect
            pix = page.get_pixmap(matrix=pymupdf.Matrix(3, 3), clip=clip, alpha=False)
            image = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
            tile = Image.new('RGB', (760, 180), 'white')
            draw = ImageDraw.Draw(tile)
            draw.text((10, 5), obs['id'] + ' | ' + obs['valor'], fill='black')
            image.thumbnail((740, 140))
            tile.paste(image, (10, 32))
            tiles.append(tile)
assert ref.read_bytes() == before
from collections import Counter
report = {'referencia': 'IA asistida 328; no humana ni precisión global',
          'sha256_referencia_intacto': hashlib.sha256(before).hexdigest(), 'api_calls': 0,
          'resumen': dict(Counter(r['estado'] for r in records)), 'etiquetas': records,
          'limite': 'No se infiere el formato de cotas numéricas ni se elige entre duplicados; propuestas no aplicadas.'}
(out / 'contraste.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
if tiles:
    sheet = Image.new('RGB', (760, 180*len(tiles)), 'white')
    for index, tile in enumerate(tiles):
        sheet.paste(tile, (0, 180*index))
    sheet.save(out / 'regiones_unicas.png')
print(json.dumps(report['resumen'], ensure_ascii=False))
