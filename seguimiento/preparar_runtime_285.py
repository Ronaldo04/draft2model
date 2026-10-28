"""Congela fuentes estables para QA, sin credenciales ni expediente privado."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from scripts.crear_paquete_aecode import capturar

destination = root / 'tmp/runtime_qa_285'
assert not destination.exists(), 'Destino ya existente: no sobrescribir.'
first = capturar(root)
assert first == capturar(root), 'Fuentes cambiaron durante captura; no congelar.'
destination.mkdir()
for name, content in first.items():
    target = destination / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
digests = {name: hashlib.sha256(content).hexdigest() for name, content in first.items()}
assert all(hashlib.sha256((destination/name).read_bytes()).hexdigest() == digest for name,digest in digests.items())
report = {'fecha_utc':datetime.now(timezone.utc).isoformat(), 'tipo':'runtime fijo para QA, no entrega final',
          'archivos':digests, 'huella_fuentes':hashlib.sha256(json.dumps(digests,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
          'captura_doble_identica':True, 'copia_verificada':True, 'goal_completo':False}
(destination/'RUNTIME_MANIFIESTO.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'destino':str(destination),'archivos':len(digests),'huella':report['huella_fuentes']}))
