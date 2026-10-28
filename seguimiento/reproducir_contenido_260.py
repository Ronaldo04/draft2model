"""Contraste focal de entradas JSON inválidas en integración de contenido; sin ETABS/red."""
from datetime import datetime, timezone
import json
import argparse
import tempfile
from pathlib import Path

from tests.test_contenido_liquidos_258 import ContenidoTests

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--verificacion261', action='store_true')
args = parser.parse_args()
output = root/'seguimiento'/('REVISION_CONTENIDO_261.json' if args.verificacion261 else 'REPRODUCCION_CONTENIDO_260.json')
if output.exists():
    raise ValueError('El registro ya existe; no sobrescribir evidencia histórica: ' + output.name)
records = []
temp_root = root/'tmp/pruebas_contenido_260'
temp_root.mkdir(exist_ok=True,parents=True)
tempfile.tempdir = str(temp_root)
case = ContenidoTests()
try:
    case.setUp()
    for value in ([], {}, True, None):
        data = case.montar_contenido()
        data['liquidos']['contenido'][0]['deposito'] = value
        try:
            result = case.validar(case.aprobar_local(data))
            records.append({'tipo_deposito':type(value).__name__, 'excepcion':None,
                            'consistente':result.consistente,'errores':result.errores})
        except Exception as error:
            records.append({'tipo_deposito':type(value).__name__,'excepcion':type(error).__name__,
                            'detalle':str(error)})
finally:
    case.tearDown()
    case.doCleanups()
report = {'fecha_utc':datetime.now(timezone.utc).isoformat(),'comando':'.venv/Scripts/python.exe -B -m seguimiento.reproducir_contenido_260',
          'casos':records,'apis_remotas':0,'etabs':False,'aceptacion_global':False}
with output.open('x',encoding='utf-8') as stream:
    stream.write(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'casos':len(records),'excepciones':sum(x['excepcion'] is not None for x in records)}))
