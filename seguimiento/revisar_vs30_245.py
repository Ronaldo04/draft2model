"""Referencias independientes de Tablas3/4/5 oficiales229; captura módulo, no entrega global."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
source=ROOT/'draft2model/normativa_e030.py'
payload=source.read_bytes()
target=ROOT/'tmp/revision_vs30_codex_245'
target.mkdir(exist_ok=False)
(target/'normativa_e030.py').write_bytes(payload)
assert source.read_bytes()==payload
spec=importlib.util.spec_from_file_location('normativa245',target/'normativa_e030.py')
n=importlib.util.module_from_spec(spec)
spec.loader.exec_module(n)
checks=[]
# Cada fila: zona, perfil, Vs30 intermedio, S/TP/TL esperados por tablas públicas.
references=[(4,'S2',450,1.05,.5,2.25),(3,'S2',450,1.075,.5,2.25),
 (2,'S2',450,1.15,.5,2.25),(1,'S2',450,1.15,.5,2.25),
 (4,'S3',275,1.15,.75,1.8),(3,'S3',275,1.175,.75,1.8),
 (2,'S3',275,1.35,.75,1.8),(1,'S3',275,1.45,.75,1.8)]
for zona,perfil,vs,s,tp,tl in references:
    observed=n.parametros_sitio(zona,perfil,vs30=vs)
    checks.append(dict(caso=f'{zona}/{perfil}/{vs}',pasa=all(math.isclose(observed[k],v,abs_tol=1e-12)
        for k,v in zip(('S','TP','TL'),(s,tp,tl))),esperado=[s,tp,tl],observado=[observed[k] for k in ('S','TP','TL')]))
for zona in (1,2,3,4):
    for perfil,lower,upper in [('S2',350,550),('S3',200,350)]:
        a=n.parametros_sitio(zona,perfil,vs30=lower)
        b=n.parametros_sitio(zona,perfil)
        checks.append(dict(caso=f'{zona}/{perfil}/extremo_blando_y_nota',pasa=all(a[k]==b[k] for k in ('S','TP','TL'))))
        for vs in (lower-1,upper):
            rejected=False
            try:
                n.parametros_sitio(zona,perfil,vs30=vs)
            except ValueError:
                rejected=True
            checks.append(dict(caso=f'{zona}/{perfil}/no_extrapolar_{vs}',pasa=rejected))
for perfil in ('S2','S3'):
    for bad in (float('nan'),float('inf'),True):
        rejected=False
        try:
            n.parametros_sitio(4,perfil,vs30=bad)
        except ValueError:
            rejected=True
        checks.append(dict(caso=f'{perfil}/rechazo_{bad}',pasa=rejected))
out=dict(estado='correcto' if all(x['pasa'] for x in checks) else 'fallos',
    modulo_sha256=hashlib.sha256(payload).hexdigest(),comprobaciones=checks,
    alcance='Interpolación en perfiles declarados S2/S3 y nota sinVs30; no clasifica suelo real, no sustituyeEMS ni valida integración global09B.',api_llamadas=0)
(ROOT/'seguimiento/REVISION_VS30_245.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(estado=out['estado'],comprobaciones=len(checks),fallos=[x for x in checks if not x['pasa']],sha256=out['modulo_sha256'])))
