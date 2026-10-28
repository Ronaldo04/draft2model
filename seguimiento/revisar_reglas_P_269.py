"""Ejercita SOLO reglas del runner en destinos propios, con lecturas archivadas; sin ETABS."""
from pathlib import Path
import hashlib
import json
import types
from datetime import datetime,timezone

root=Path(__file__).resolve().parents[1]
source=root/'seguimiento/claude_ruta/resultados_09.py'
raw=source.read_bytes()
module=types.ModuleType('runner_reglas_revisado_269');module.__file__=str(source)
exec(compile(raw,str(source),'exec'),module.__dict__)
original=root/'tmp/recorrido_09d1'
target=root/'tmp/revision_reglas_P_269';target.mkdir(exist_ok=False)
results=[]
for scenario in ('lectura_aceptada','sin_lectura_por_piso'):
    work=target/scenario;work.mkdir();(work/'resultados').mkdir()
    for name in ('registro.json','configuracion.json','masa_pisos_diagnostico.json'):
        (work/name).write_bytes((original/name).read_bytes())
    if scenario=='sin_lectura_por_piso':
        diag=json.loads((work/'masa_pisos_diagnostico.json').read_text(encoding='utf-8'))
        diag['lectura']='0'*32
        (work/'masa_pisos_diagnostico.json').write_text(json.dumps(diag),encoding='utf-8')
    reg=json.loads((original/'registro_resultados.json').read_text(encoding='utf-8'))
    reg.pop('cortante_estatico',None)
    module.etapa_reglas(work,reg)
    rules=json.loads((work/'resultados/reglas_e030.json').read_text(encoding='utf-8'))
    vmin=[r for r in rules['reglas'] if r['id'].startswith('VMIN-')]
    if scenario=='lectura_aceptada':
        assert abs(reg['cortante_estatico']['P_kN']-4792.877604375)<1e-8
        assert len(vmin)==2 and not reg['reglas']['abstenciones']
    else:
        assert len(vmin)==0 and reg['reglas']['abstenciones']
        assert 'cortante_estatico' not in reg
    results.append({'caso':scenario,'correcto':True,'reglas_cortante':len(vmin),
                    'P_kN':reg.get('cortante_estatico',{}).get('P_kN'),
                    'abstenciones':len(reg['reglas']['abstenciones']),
                    'sha256_reglas':hashlib.sha256((work/'resultados/reglas_e030.json').read_bytes()).hexdigest()})
report={'fecha_utc':datetime.now(timezone.utc).isoformat(),'pruebas':results,
        'sha256_runner':hashlib.sha256(raw).hexdigest(),'fuente_estable':source.read_bytes()==raw,
        'alcance':'Ejecución de etapa_reglas en destinos propios, con fuente nativa archivada y sin lectura disponible. No altera corrida activa ni demuestra validez profesional de las hipótesis.',
        'etabs_ejecutado':False,'api_remota':False,'goal_completo':False}
assert report['fuente_estable']
(root/'seguimiento/REVISION_REGLAS_P_269.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
