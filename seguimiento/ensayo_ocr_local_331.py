"""Ensayo local acotado: una lámina, sin red, sin editar expediente ni referencia."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import pymupdf

root = Path(__file__).resolve().parents[1]
out = root / 'seguimiento/localizacion_331'
out.mkdir(exist_ok=True)
source = root / 'data/private/provisional-001/originales/lamina-0001.pdf'
raw = source.read_bytes()
exe = Path('C:/Program Files/Tesseract-OCR/tesseract.exe')
assert exe.is_file()
target = out / 'lamina_1_ocr.tsv'
assert not target.exists(), 'Conservar el ensayo existente.'
with pymupdf.open(stream=raw, filetype='pdf') as doc:
    page = doc[0]
    scale = 4096 / max(page.rect.width, page.rect.height)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
    image = out / 'lamina_1_ocr.png'
    pix.save(image)
result = subprocess.run([str(exe), str(image), str(out/'lamina_1_ocr'), '-l', 'spa+eng', '--psm', '11', 'tsv'],
                        capture_output=True, encoding='utf-8', errors='replace', timeout=90)
assert result.returncode == 0, result.stderr[-500:]
with target.open(encoding='utf-8-sig', newline='') as stream:
    rows = [r for r in csv.DictReader(stream, delimiter='\t') if r.get('level') == '5' and r.get('text', '').strip()]
known = {t: [{'texto': r['text'], 'confianza': r['conf'], 'bbox_px': [r['left'], r['top'], r['width'], r['height']]}
             for r in rows if r['text'].casefold() == t.casefold()] for t in ('C-1', 'C-2', 'C-6', 'PL-1', 'PL-10')}
assert source.read_bytes() == raw
report = {'metodo': 'Tesseract local 5.4.0, spa+eng, PSM11', 'dimensiones': [pix.width, pix.height],
          'original_sha256': hashlib.sha256(raw).hexdigest(), 'palabras_ocr': len(rows),
          'coincidencias_exactas': known, 'no_aplica_cambios': True, 'api_calls': 0,
          'advertencia': 'Salida OCR experimental; confianza no demuestra corrección visual.'}
(out/'ENSAYO_OCR.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'palabras': len(rows), 'coincidencias': {k: len(v) for k,v in known.items()}}))
