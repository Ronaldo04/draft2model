"""Registrar implementación independiente258 y disponibilidad para integración."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
files = ('scripts/crear_paquete_aecode.py', 'tests/test_paquete_aecode.py', 'docs/ENTREGA_AECODE.md')
record = {'responsable': 'Codex', 'fecha_utc': datetime.now(timezone.utc).isoformat(),
          'archivos': {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files},
          'pruebas': {'comando': '.venv/Scripts/python.exe -B -m unittest tests.test_paquete_aecode -q',
                      'resultado': '8 pruebas OK, 1.015s'},
          'paquete': 'entregas/AECODE_CANDIDATO_258',
          'huella_fuentes': '87f79d0511866223e1e51007e099474c3de9523fd7be5ec282736ba368f38fc2',
          'alcance': '564 archivos incluidos con wheels exactos del lock; no datos privados ni resultados reales',
          'validacion': 'tmp/validacion_paquete_258/verificacion.json; consultar resultado terminal',
          'aceptacion_global': False, 'acuerdo_claude_confirmado': False}
(root/'seguimiento/RESERVA_EMPAQUETADO_258.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
path = root/'seguimiento/CLAUDE_ESTADO.json'
state = json.loads(path.read_bytes())
state['reserva_nuevos_archivos_258'] = {'responsable': 'Codex', 'archivos': list(files),
    'registro': 'seguimiento/RESERVA_EMPAQUETADO_258.json',
    'alcance': 'Empaquetado independiente, sin editar implementación existente de Claude',
    'acuerdo_claude_confirmado': False}
path.write_text(json.dumps(state, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
path = root/'seguimiento/CONTINUACION_CLAUDE_253.md'
text = path.read_text(encoding='utf-8')
if 'Empaquetado258 disponible' not in text:
    text += '\n## Empaquetado258 disponible\n\nCodex implementó scripts/crear_paquete_aecode.py, tests/test_paquete_aecode.py y docs/ENTREGA_AECODE.md en archivos nuevos independientes;8 pruebas propiasOK. Paquete candidato con564archivos y wheels exactos del lock en entregas/AECODE_CANDIDATO_258, huella87f79d0511866223e1e51007e099474c3de9523fd7be5ec282736ba368f38fc2. Validación de instalación/demo/HTTP en tmp/validacion_paquete_258/verificacion.json: consultar estado terminal, no asumir éxito. No incluye credenciales/expedientes/resultados. Al estabilizar tu integración, regenerar versión nueva; no modificar este candidato ni presentarlo como aceptación global. Codex conserva esos tres archivos mientras concluye esta verificación; no necesita que dupliques su implementación. El objetivo del usuario es entrega AECODE del sistema completo hoy, con limitaciones honestas; no sustituirla por un EDB parcial.\n'
    path.write_text(text, encoding='utf-8')
print(json.dumps({'registro': 'RESERVA_EMPAQUETADO_258.json', 'archivos': len(files)}))
