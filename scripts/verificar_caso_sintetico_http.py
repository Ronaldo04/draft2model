import urllib.request
import re
import json

url_base = 'http://127.0.0.1:8766'
caso = 'vivienda-sintetica-albanileria-2p'

# 1. Obtener token de sesion desde index
req = urllib.request.Request(url_base)
with urllib.request.urlopen(req) as resp:
    html = resp.read().decode()
token = re.search(r'name="revision-session" content="([^"]+)"', html).group(1)

def get(path):
    req = urllib.request.Request(f'{url_base}{path}', headers={'X-Revision-Session': token})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

print("1. Casos en servidor:", get('/api/casos'))
doc = get(f'/api/documentos?caso={caso}')
fp = doc['expediente_sha256']
print("2. Documentos registrados:", [d['nombre'] for d in doc['documentos']])
print("3. Geometrias registradas:", get(f'/api/geometrias?caso={caso}'))
print("4. Configuraciones registradas:", get(f'/api/configuraciones?caso={caso}'))
print("5. Modelos ETABS registrados:", get(f'/api/modelos?caso={caso}'))
res = get(f'/api/resultados?caso={caso}')
print("6. Resultados Estructurales:", res)

res_id = res['versiones'][0]['id']
print("7. Analisis vinculado:", get(f'/api/analisis?caso={caso}&resultado={res_id}&expediente_sha256={fp}'))
print("8. Revisiones de Resultados:", get(f'/api/revision-resultados/historial?caso={caso}&resultado={res_id}&expediente_sha256={fp}'))
print("9. Informes Tecnicos:", get(f'/api/informes?caso={caso}&resultado={res_id}&expediente_sha256={fp}'))
print("10. Paneles Tecnicos:", get(f'/api/paneles?caso={caso}&resultado={res_id}&expediente_sha256={fp}'))

print("\n>>> VERIFICACION HTTP TOTALMENTE EXITOSA EN EL SERVIDOR LOCAL: TODAS LAS 7 ETAPAS ACTIVAS Y DISPONIBLES <<<")
