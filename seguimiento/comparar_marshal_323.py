"""Microensayo de formatos sobre una fuente existente; no cambia algoritmos ni archivos del caso."""
from pathlib import Path
import json,marshal,time
root=Path(__file__).resolve().parents[1]
p=root/'data/private/pueblo-libre-002/geometrias/25ef94672fac4e53863701b55e32f97d/geometria.json'
d=json.loads(p.read_bytes());results={};n=100
for version in (2,4):
    start=time.perf_counter()
    for _ in range(n):raw=marshal.dumps(d,version)
    results[str(version)]={'segundos':time.perf_counter()-start,'bytes':len(raw),'repeticiones':n}
(root/'seguimiento/MARSHAL_FORMATOS_323.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(json.dumps(results))
