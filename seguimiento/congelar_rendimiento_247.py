"""Captura producto reservado estable sobre base íntegra anterior."""
import hashlib
import json
import shutil
from pathlib import Path
root = Path(__file__).resolve().parent.parent
dest = root/'tmp/revision_rendimiento_codex_247'
if dest.exists():
    raise SystemExit('Destino existente: no sobrescribir captura')
shutil.copytree(root/'tmp/revision_codex_246', dest)
files = ['draft2model/malla_preparacion.py', 'draft2model/particion_superficies.py', 'draft2model/compatibilidad_particiones.py', 'draft2model/triangulacion_particiones.py', 'tests/test_malla_rendimiento_246.py']
hashes = {}
for name in files:
    source = root/name
    content = source.read_bytes()
    (dest/name).write_bytes(content)
    assert source.read_bytes() == content
    hashes[name] = hashlib.sha256(content).hexdigest()
(root/'seguimiento/CAPTURA_RENDIMIENTO_247.json').write_text(json.dumps({'snapshot': str(dest.relative_to(root)), 'sha256':hashes}, indent=2)+'\n', encoding='utf-8')
print(json.dumps(hashes))
