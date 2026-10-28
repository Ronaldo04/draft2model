"""GET locales acotados al servidor de revisión; no muta datos ni llama proveedores."""
import json
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
URL='http://127.0.0.1:18226'
observado=[]


def pedir(ruta, token=None):
    t=time.monotonic()
    try:
        with urlopen(Request(URL+ruta, headers={'X-Revision-Session':token} if token else {}), timeout=45) as res:
            contenido=res.read(32*1024*1024+1)
            observado.append({'ruta':ruta.split('?')[0],'estado_http':res.status,
                              'bytes':len(contenido),'tipo':res.headers.get('Content-Type'),
                              'segundos':round(time.monotonic()-t,3)})
            if len(contenido)>32*1024*1024:raise ValueError('Excede cota local.')
            return contenido
    except Exception as exc:
        observado.append({'ruta':ruta.split('?')[0],'error_tipo':type(exc).__name__,
                          'segundos':round(time.monotonic()-t,3)})
        raise


try:
    html=pedir('/').decode('utf-8')
    token=re.search(r'<meta name="revision-session" content="([^"]+)"',html).group(1)
    version=json.loads(pedir('/api/version?caso=provisional-001&version=1cde498b56c34b03866d0583a0e8ad3d',token))
    assert len(version['datos']['candidatos'])==32
    pedir('/api/pagina?caso=provisional-001&archivo=L0001&pagina=1&expediente_sha256='+version['expediente_sha256'],token)
finally:
    (ROOT/'seguimiento/SONDA_HTTP_227.json').write_text(json.dumps(observado,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(observado))
