"""Contraste independiente de extremos reales y cantidades de vigas del piloto."""
from pathlib import Path
from types import SimpleNamespace
from decimal import Decimal as D
from datetime import datetime, timezone
import hashlib
import json
import math
import sys

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from draft2model.lectura_analisis import LectorAnalisis
case=root/'data/private/pueblo-libre-002'
tracked={}
def read(p):
    tracked[p]=p.read_bytes()
    return json.loads(tracked[p])
def sha(b): return hashlib.sha256(b).hexdigest()

folder=case/'lecturas_analisis/6da62ea363484498a3e13315c99b328a'
req=read(folder/'solicitud.json');res=read(folder/'respuesta.json');receipt=read(folder/'aceptacion_lectura.json')
assert receipt['aceptada'] is True and receipt['instancia_nueva_cerrada'] is True and receipt['modo']=='real'
assert receipt['sha256_solicitud']==sha(tracked[folder/'solicitud.json'])
assert receipt['sha256_respuesta']==sha(tracked[folder/'respuesta.json'])
assert receipt['corrida_analisis_id']=='7203c79a3ece4438b36d267ba80f3c4b'
edb=case/'analisis_etabs'/receipt['corrida_analisis_id']/'analizado.edb'
assert sha(edb.read_bytes())==receipt['sha256_edb']=='42371308a03d4f1bac8f5ed3aa5daf0421cdf3de27ff823f8f582c13ad2af394'
LectorAnalisis._comprobar_datos(SimpleNamespace(contenido=req),res['datos'])
assert res['datos']['unidades']=='kN_m_C'
rows=next(t['filas'] for t in res['datos']['tablas'] if t['clave']=='Frame Assignments - End Length Offsets')
geo=root/'tmp/recorrido_09d1/lectura/2eca39b2592c4c1d8a0cdb800eb06ddf/respuesta.json'
g=read(geo)['datos']['lecturas'];assert g['unidades']=='N_mm_C'
assert len(rows)==len({r['UniqueName'] for r in rows})==len(g['frames']['nombres'])==128
assert {r['UniqueName'] for r in rows}==set(g['frames']['nombres'])
beam=[]
for row in rows:
    name=row['UniqueName'];section=g['frames']['secciones'][name]
    if section!='VS-15X30': continue
    prop=g['propiedades_frame']['rectangulos'][section]
    gamma=D(str(g['materiales']['detalle'][prop['material']]['W']))*D(10)**6
    area=D(str(prop['t3']))*D(str(prop['t2']))/D(10)**6
    a,b=(g['puntos']['coordenadas'][p] for p in g['frames']['puntos'][name])
    length=D(str(math.dist(a,b)))/1000
    offsets=D(row['OffsetI'])+D(row['OffsetJ'])
    assert 0<=offsets<=length
    assert row['OffsetOpt']==row['SelfWtOpt']=='Auto' and D(row['RigidFact'])==0
    beam.append({'nombre':name,'longitud_m':str(length),'extremos_m':str(offsets),'peso_bruto_kn':str(length*area*gamma),'peso_extremos_kn':str(offsets*area*gamma)})
assert len(beam)==45
total=lambda key:sum((D(b[key]) for b in beam),D(0))
matfolder=case/'lecturas_analisis/461c751056c74acaa6d738b29f4df633'
mat=read(matfolder/'respuesta.json')
native=sum((D(r['Weight']) for t in mat['datos']['tablas'] if t['clave']=='Material List by Section Property' for r in t['filas'] if r['Section']=='VS-15X30'),D(0))
gross=total('peso_bruto_kn');excluded=total('peso_extremos_kn');net=gross-excluded
assert abs(net-native)<D('0.0001')
stable=all(p.read_bytes()==b for p,b in tracked.items());assert stable
report={'fecha_utc':datetime.now(timezone.utc).isoformat(),'lectura':folder.name,'analisis':receipt['corrida_analisis_id'],
        'sha256_edb':receipt['sha256_edb'],'fuentes_sha256':{str(p.relative_to(root)):sha(b) for p,b in tracked.items()},
        'cobertura_frames':len(rows),'vigas':beam,'totales':{'longitud_m':str(total('longitud_m')),'extremos_m':str(total('extremos_m')),'peso_bruto_kn':str(gross),'peso_extremos_kn':str(excluded),'peso_neto_calculado_kn':str(net),'peso_tabla_materiales_kn':str(native),'diferencia_redondeo_kn':str(net-native)},
        'opciones_observadas':{'OffsetOpt':sorted({r['OffsetOpt'] for r in rows}),'SelfWtOpt':sorted({r['SelfWtOpt'] for r in rows}),'RigidFact':sorted({r['RigidFact'] for r in rows})},
        'fuentes_estables':stable,'alcance':'Recibo nativo de extremos del mismo análisis y aritmética por45vigas a partir de relectura geométrica archivada. Explica diferencia por sección para este EDB, no prueba universal de la regla Auto ni validación profesional.',
        'limites':['La conciliación usa offsets observados: no es predicción independiente de esos offsets.','El libro independiente original y el contraste global fallido se conservan; no cambiar tolerancia para pasar.','Residuo CM global distinto de la diferencia por sección sigue sin atribución exacta.'],
        'etabs_ejecutado':False,'api_remota':False,'goal_completo':False}
(root/'seguimiento/REVISION_EXTREMOS_278.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'fuentes_estables':stable,'vigas':len(beam),'totales':report['totales']},ensure_ascii=False))
