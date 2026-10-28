"""Contraste independiente de las lecturas conservadas; no inicia motor ni red."""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timezone
from decimal import Decimal
import hashlib
import json
import math
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from draft2model.lectura_analisis import LectorAnalisis

CASE='pueblo-libre-002';RUN='7203c79a3ece4438b36d267ba80f3c4b'
IDS={'reacciones':'74d78008b7804616abcbf5dbd23a08b7','modal':'ddcf711b19e74f5a8043f9c1271d5ffa','derivas':'376b4c1c72a349ef98b7e6677c9de772'}
seen={}
def read(p):
    p=Path(p);raw=p.read_bytes();seen[str(p.relative_to(ROOT))]=hashlib.sha256(raw).hexdigest();return raw
def load(p):return json.loads(read(p))
def sha(raw):return hashlib.sha256(raw).hexdigest()

folder=ROOT/'data/private'/CASE
analysis=load(folder/'analisis_etabs'/RUN/'aceptacion_analisis.json')
analysis_sha=seen[str((folder/'analisis_etabs'/RUN/'aceptacion_analisis.json').relative_to(ROOT))]
tables={};checks=[]
for name,ident in IDS.items():
    p=folder/'lecturas_analisis'/ident
    request=load(p/'solicitud.json');response=load(p/'respuesta.json');receipt=load(p/'aceptacion_lectura.json')
    assert receipt['aceptada'] is True and receipt['modo']=='real'
    assert receipt['lectura_id']==ident and receipt['corrida_analisis_id']==RUN
    assert receipt['sha256_edb']==analysis['guardado']['sha256']
    assert receipt['sha256_aceptacion_analisis']==analysis_sha
    assert receipt['sha256_solicitud']==seen[str((p/'solicitud.json').relative_to(ROOT))]
    assert receipt['sha256_respuesta']==seen[str((p/'respuesta.json').relative_to(ROOT))]
    assert receipt['instancia_nueva_cerrada'] is True and receipt['analisis_ejecutado'] is False
    assert response['id_solicitud']==ident and response['modo_ejecucion']=='real' and response['estado']=='ok'
    assert response['operacion']=='leer_tablas' and request['id']==ident
    assert request['sha256_edb']==analysis['guardado']['sha256'] and request['corrida_analisis_id']==RUN
    assert request['sha256_aceptacion_analisis']==analysis_sha
    LectorAnalisis._comprobar_datos(SimpleNamespace(contenido=request),response['datos'])
    assert load(ROOT/'tmp/recorrido_09d1'/('lectura_'+name+'.json'))==response['datos']
    for table in response['datos']['tablas']:tables[table['clave']]=table
    checks.append({'lectura':ident,'tipo':name,'aceptada_real_con_fuentes_coincidentes':True})

# La referencia analítica264 corresponde a la misma configuración operativa:
# solo cambió revisión, que se conserva y no se hace pasar por idénticos bytes.
ref=load(ROOT/'seguimiento/CONTRASTE_PRESIONES_264.json')
oldpath=ROOT/'tmp/ruta201/configuracion09dt.json';old=load(oldpath)
assert sha(oldpath.read_bytes())==ref['configuracion_sha256']
cfg=load(folder/'modelos_construidos'/analysis['modelo_id']/'configuracion.json')
assert {k:v for k,v in cfg.items() if k!='revision'}=={k:v for k,v in old.items() if k!='revision'}
assert cfg['geometria_origen']['version_id']==ref['version_geometria']
water=[r for r in tables['Base Reactions']['filas'] if r['OutputCase']=='CAGUA'];assert len(water)==1
water=water[0]
force=[-sum(c['fuerza_referencia_kn'][i] for c in ref['contrastes']) for i in range(3)]
moment=[-sum(c['momento_referencia_kn_m'][i] for c in ref['contrastes']) for i in range(3)]
comparison=[]
for field,expected in zip(('FX','FY','FZ','MX','MY','MZ'),force+moment):
    observed=float(water[field]);assert math.isfinite(observed)
    # Semiancho de una unidad de la última cifra textual publicada por ETABS.
    rounding=float(Decimal(10)**Decimal(Decimal(water[field]).as_tuple().exponent)/2)
    error=abs(observed-expected);assert error<=rounding+1e-8
    comparison.append({'campo':field,'reaccion_esperada':expected,'reaccion_observada':observed,
                       'error_absoluto':error,'semiancho_redondeo_textual':rounding,'coincide':True})

modal=tables['Modal Periods And Frequencies']['filas'];mass=tables['Modal Participating Mass Ratios']['filas']
assert len(modal)==12 and {int(r['Mode']) for r in modal}==set(range(1,13))
periods=[float(r['Period']) for r in sorted(modal,key=lambda r:int(r['Mode']))]
assert all(math.isfinite(t) and t>0 for t in periods)
assert all(a>=b for a,b in zip(periods,periods[1:]))
last=max(mass,key=lambda r:int(r['Mode']))
drifts=tables['Story Drifts']['filas'];summary={}
for case,direction in (('SX','X'),('SY','Y')):
    selected=[r for r in drifts if r['OutputCase']==case and r['Direction']==direction and r['Story'] in ('N1','N2','N3','N4')]
    assert len(selected)==4 and {r['Story'] for r in selected}=={'N1','N2','N3','N4'}
    assert all(math.isfinite(float(r['Drift'])) for r in selected)
    top=max(selected,key=lambda r:abs(float(r['Drift'])))
    summary[case]={'direccion':direction,'maximo_elastico':float(top['Drift']),'piso':top['Story']}
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in seen.items())
output={'fecha_utc':datetime.now(timezone.utc).isoformat(),'caso':CASE,'analisis':RUN,'modo':'real',
        'lecturas':checks,'equilibrio_agua':comparison,'periodos_primeros3_s':periods[:3],
        'participacion_modal_acumulada_modo12':{k:float(last[k]) for k in ('SumUX','SumUY','SumRZ')},
        'derivas_elasticas':summary,'fuentes_sha256':seen,'fuentes_estables':True,
        'limites':['Contraste del escenario y entradas declaradas; no confirma hipótesis de los planos ni ingeniería.',
                   'Equilibrio estático global del agua no acredita masa ensamblada, distribución dinámica ni hidrodinámica.',
                   'Derivas son crudas elásticas; evaluación normativa e informe final se verifican por separado.',
                   'No se ejecutó ETABS, solver ni API remota.'],'goal_completo':False}
target=ROOT/'seguimiento/REVISION_LECTURAS_09D1_267.json'
if target.exists():raise RuntimeError('No sobrescribir evidencia.')
target.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'lecturas':len(checks),'agua_global':'coincide6/6','periodos':periods[:3],'derivas_elasticas':summary},ensure_ascii=False))
