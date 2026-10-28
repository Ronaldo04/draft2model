"""Verificación independiente sobre copia estable de un módulo, no aceptación de entrega en edición."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
source = ROOT/'draft2model/normativa_e030.py'
content = source.read_bytes()
outdir = ROOT/'tmp/revision_normativa_codex_240'
outdir.mkdir(exist_ok=True)
frozen = outdir/'normativa_e030.py'
if frozen.exists() and frozen.read_bytes() != content:
    raise SystemExit('La copia240 ya existe con otros bytes; crear otra revisión, no reemplazar evidencia.')
frozen.write_bytes(content)
assert source.read_bytes() == content, 'Fuente cambió durante la captura; no evaluar captura inconsistente.'
spec = importlib.util.spec_from_file_location('normativa_capturada_240', frozen)
n = importlib.util.module_from_spec(spec)
spec.loader.exec_module(n)
checks=[]
common=dict(Z=.45,U=1,S=1,R=8,TP=.4,TL=2.5,P_kN=1000)
for T, c in [(0,2.5),(.08,2.5),(.4,2.5),(1,1),(2.5,.4),(5,.1),(10,.025)]:
    r=n.cortante_basal_estatico(T=T,**common)
    raw=.45*c/8*1000
    applied=max(raw,49.5)
    checks.append(dict(prueba='V_T_'+str(T), pasa=math.isclose(r['V_kN'],applied,abs_tol=1e-10)
        and math.isclose(r['V_bruto_kN'],raw,abs_tol=1e-10), esperado=applied, observado=r['V_kN']))
for key, bad in [('TL',.2),('TP',0),('R',0),('R',-1),('Z',0),('U',0),('S',0),('P_kN',0),('T',-1),('T',float('nan'))]:
    kwargs=dict(common,T=.1)
    kwargs[key]=bad
    rejected=False
    try:
        n.cortante_basal_estatico(**kwargs)
    except ValueError:
        rejected=True
    checks.append(dict(prueba='rechazo_'+key+'_'+str(bad),pasa=rejected))
# El espectro y el estático son reglas distintas en T=0: no uniformarlos al corregir mínimo.
checks.append(dict(prueba='distincion_espectro_estatico_en_T0',
    pasa=n.factor_c(0,.4,2.5)['C']==1 and n.cortante_basal_estatico(T=0,**common)['C']==2.5))
record=dict(estado='correcto' if all(c['pasa'] for c in checks) else 'fallos',
    modulo_sha256=hashlib.sha256(content).hexdigest(), comprobaciones=checks,
    alcance='Captura aislada de función corregida. No aceptación de entrega09 ni aplicación al piloto; interpolación e integración siguen pendientes.',
    api_llamadas=0, producto_modificado=False)
(ROOT/'seguimiento/REVISION_MINIMO_ESTATICO_240.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(estado=record['estado'],pruebas=len(checks),fallos=[c for c in checks if not c['pasa']],sha256=record['modulo_sha256']),ensure_ascii=True))
raise SystemExit(0 if all(c['pasa'] for c in checks) else 1)
