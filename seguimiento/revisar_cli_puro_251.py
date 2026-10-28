"""Contrastes de despacho CLI en snapshot; sin registro de expedientes ni ETABS."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tmp/revision_codex_251'))
from tests.test_cli_plan_etabs_247 import despacho
work=ROOT/'tmp/cli_puro_251'
work.mkdir(exist_ok=False)
mapa={'PISO':{'tipo':'Membrane','funcion':'piso','justificacion':'Control sintético de despacho'},
      'FONDO':{'tipo':'ShellThick','funcion':'fondo_deposito','justificacion':'Control sintético de flexión'}}
f=work/'losas.json';f.write_text(json.dumps(mapa),encoding='utf-8')
bad=work/'malo.json';bad.write_text('{ no json',encoding='utf-8')
checks=[]
def check(caso, ok):
    checks.append({'caso':caso,'pasa':bool(ok)})
for version in ('0.4.0','0.5.0'):
    r=despacho(version,['--tipo-shell-losa','Membrane'])
    check(version+' global',r[1]==['generar_plan_malla'] and r[2]=={'tipo_shell_losa':'Membrane'})
    r=despacho(version,['--tipo-shell-losa-json',str(f)])
    check(version+' mapaJSON',r[1]==['generar_plan_malla'] and r[2]=={'tipo_shell_losa':mapa})
r=despacho('0.5.0',[]);check('0.5 sinflag usa malla',r[1]==['generar_plan_malla'])
r=despacho('0.1.0',[]);check('legacy conserva despacho',r[1]==['generar_plan'])
r=despacho('0.5.0',['--tipo-shell-losa','Membrane','--tipo-shell-losa-json',str(f)])
check('conflicto rechazado antes generar',r[0]==2 and not r[1])
for name,path in [('JSONinvalido',bad),('ausente',work/'ausente.json')]:
    r=despacho('0.5.0',['--tipo-shell-losa-json',str(path)])
    check(name+' no genera',r[0]!=0 and not r[1])
r=despacho('0.1.0',['--tipo-shell-losa-json',str(f)])
check('legacy rechaza mapa incompatible',r[0]!=0 and not r[1])
out={'estado':'correcto' if all(c['pasa'] for c in checks) else 'fallo','comprobaciones':checks,
     'limites':'Cargador y generadores son dobles centinela. Comprueba despacho/argumentos/rechazos; no genera un plan real ni reemplaza validación de configuración. Pruebas originales3 con fixture expediente no corrieron por WinError5 del aislamiento.'}
(ROOT/'seguimiento/REVISION_CLI_PURO_251.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'estado':out['estado'],'cantidad':len(checks)}))
assert out['estado']=='correcto'
