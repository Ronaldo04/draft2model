"""Completa candidato aislado tras límite del agente; no toca el runner vivo."""
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / 'tmp/recorrido_seguro_255'


def reparar_texto(text):
    replacements = {}
    for char in 'áéíóúñÁÉÍÓÚÑ¿¡':
        for encoding in ('cp1252', 'latin1'):
            bad = char
            for _ in range(2):
                try:
                    bad = bad.encode('utf-8').decode(encoding)
                except UnicodeDecodeError:
                    break
                replacements[bad] = char
    for bad, good in sorted(replacements.items(), key=lambda item: -len(item[0])):
        text = text.replace(bad, good)
    return text


def main():
    live = ROOT / 'seguimiento/claude_ruta/recorrido_etabs_09t.py'
    live_bytes = live.read_bytes()
    frozen = DIR / 'original_256/recorrido_etabs_09t.py'
    frozen.parent.mkdir(exist_ok=True)
    if frozen.exists():
        assert frozen.read_bytes() == live_bytes, 'No sustituir un congelado distinto'
    else:
        with frozen.open('xb') as f:
            f.write(live_bytes)
    for name in ('recorrido_etabs_09t.py', 'validacion_etapas_255.py', 'test_candidato_255.py'):
        p = DIR / name
        p.write_text(reparar_texto(p.read_text(encoding='utf-8-sig')), encoding='utf-8')
    p = DIR / 'recorrido_etabs_09t.py'
    text = p.read_text(encoding='utf-8')
    # Preserve the two independent current changes made by Claude since freeze255.
    text = text.replace('"parametros_modales": {"MODAL": EIGEN}', '"parametros_modales": {"MODAL-E030": EIGEN}')
    text = text.replace('["MODAL"]),', '["MODAL-E030"]),')
    text = text.replace('review = json.loads(revision_path.read_text(encoding="utf-8"))',
                        'review_raw = revision_path.read_bytes()\n    review = json.loads(review_raw)\n    review_sha = hashlib.sha256(review_raw).hexdigest()')
    text = text.replace('"sha256": epl.sha(revision_path),', '"sha256": review_sha,')
    anchor = '    # Existing rm.aprobar contract: no new fields and no auto-generated True controls.'
    assert anchor in text
    text = text.replace(anchor, '    if revision_path.read_bytes() != review_raw:\n        raise ValueError("La revisión cambió durante la comprobación; no se aprueba el modelo.")\n' + anchor)
    # Do not attribute a real review to the user by hardcoded identity/date.
    start = text.index('REVISOR = ')
    end = text.index('\nALCANCE = ', start)
    text = text[:start] + 'REVISOR = "Operador del recorrido (revisión declarada de transporte de software; no ingeniería)"' + text[end:]
    text = text.replace('"aprobacion": "declarada SOLO de transporte de software (autorización del usuario)"',
                        '"aprobacion": "declarada SOLO de transporte de software; no aprobación de ingeniería"')
    text = text.replace('"""Recorrido ETABS propio POR ETAPAS del caso real en el ESCENARIO DE TRANSPORTE (autorización del usuario 2026-10-22).',
                        '"""Recorrido ETABS propio POR ETAPAS del caso real en el ESCENARIO DE TRANSPORTE.')
    p.write_text(text, encoding='utf-8')
    current = live_bytes.decode('utf-8-sig')
    patch = ''.join(difflib.unified_diff(current.splitlines(True), text.splitlines(True),
                                        fromfile='seguimiento/claude_ruta/recorrido_etabs_09t.py',
                                        tofile='candidato256/recorrido_etabs_09t.py'))
    (DIR / 'candidato_256.patch').write_text(patch, encoding='utf-8')
    out = {'estado': 'candidato_aislado_no_portado', 'fuente_actual_sha256': hashlib.sha256(live_bytes).hexdigest(),
           'modal_E030_preservado': '"parametros_modales": {"MODAL-E030": EIGEN}' in text and '["MODAL-E030"]),' in text,
           'runner_vivo_sin_modificar': live.read_bytes() == live_bytes,
           'motivo': 'El agente alcanzó cuota; root completa y verifica candidato. El runner vivo cambió y permanece propiedad de Claude.',
           'candidato_sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
    (ROOT / 'seguimiento/CANDIDATO_RECORRIDO_256.json').write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(out, ensure_ascii=True))


if __name__ == '__main__':
    main()
