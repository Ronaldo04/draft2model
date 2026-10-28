"""Integra geometría/propiedades/cargas de la relectura archivada N_mm_C; sin ETABS."""
from pathlib import Path
import json
import math
import hashlib
from datetime import datetime,timezone

root=Path(__file__).resolve().parents[1]
source=root/'tmp/recorrido_09d1/lectura/2eca39b2592c4c1d8a0cdb800eb06ddf/respuesta.json'
raw=source.read_bytes(); response=json.loads(raw.decode('utf-8-sig'))
l=response['datos']['lecturas'];assert l['unidades']=='N_mm_C'
points={k:[float(v)/1000 for v in xyz] for k,xyz in l['puntos']['coordenadas'].items()}
materials={k:float(v['W'])*1e6 for k,v in l['materiales']['detalle'].items()}
sections={**l['propiedades_area']['losas'],**l['propiedades_area']['muros']}
def triangle(a,b,c):
    u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
    cross=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
    return math.sqrt(sum(x*x for x in cross))/2
area={}
weights={}
for name,vertices in l['areas']['puntos'].items():
    assert len(vertices)==3, 'El diagnóstico exige malla triangular explícita.'
    assert not l['areas']['aberturas'][name]
    area[name]=triangle(*(points[p] for p in vertices))
    prop=sections[l['areas']['propiedades'][name]]
    weight=area[name]*(float(prop['espesor'])/1000)*materials[prop['material']]
    key=l['areas']['propiedades'][name]
    weights[key]=weights.get(key,0)+weight
frame_weights={}
for name,pair in l['frames']['puntos'].items():
    assert len(pair)==2
    section=l['frames']['secciones'][name]
    if section in l['propiedades_frame']['rectangulos']:
        prop=l['propiedades_frame']['rectangulos'][section]
        a=float(prop['t3'])*float(prop['t2'])/1e6
    else:
        prop=l['propiedades_frame']['secciones_l'][section]
        assert prop['twc']==prop['twt'], 'Ala trapezoidal no cubierta.'
        a=(float(prop['t2'])*float(prop['tf'])+(float(prop['t3'])-float(prop['tf']))*float(prop['twc']))/1e6
    length=math.dist(*(points[p] for p in pair))
    weight=length*a*materials[prop['material']]
    frame_weights[section]=frame_weights.get(section,0)+weight
loads={}
for name,items in l['cargas_area'].items():
    for item in items:
        assert item['csys']=='Global' and item['dir']==10
        loads[item['patron']]=loads.get(item['patron'],0)+area[name]*float(item['valor'])*1000
assert not any(l['cargas_frame'].values()) and not any(l['cargas_punto'].values())
bookpath=root/'tmp/recorrido_09d1/resultados/libro_masa.json';bookraw=bookpath.read_bytes();book=json.loads(bookraw)
selfweight=math.fsum(weights.values())+math.fsum(frame_weights.values())
cm=selfweight+loads['D']
report={'fecha_utc':datetime.now(timezone.utc).isoformat(),
        'fuente':str(source.relative_to(root)),'sha256':hashlib.sha256(raw).hexdigest(),
        'edb_leido_sha256':response['datos']['sha256_antes'],
        'unidades_originales':l['unidades'],'peso_shells_por_seccion_kn':weights,'peso_frames_por_seccion_kn':frame_weights,
        'peso_shells_kn':math.fsum(weights.values()),'peso_frames_kn':math.fsum(frame_weights.values()),
        'cargas_por_patron_kn':loads,'CM_geometria_releida_kn':cm,
        'delta_shells_con_libro_kn':math.fsum(weights.values())-book['contribuciones']['peso_propio_por_patrones']['detalle']['shells_kn'],
        'delta_frames_con_libro_kn':math.fsum(frame_weights.values())-book['contribuciones']['peso_propio_por_patrones']['detalle']['frames_kn'],
        'delta_D_con_libro_kn':loads['D']-book['contribuciones']['cargas_D']['peso_kn'],
        'limites':'Integral geométrica de objetos/peso específico re-leídos del EDB construido previo al análisis. No descuenta offsets/intersecciones ni prueba cómo el solver calcula peso efectivo; gravedad dirección10 tratada como carga por área real. No nueva llamada ni prueba de modelo final.',
        'fuentes_estables':source.read_bytes()==raw and bookpath.read_bytes()==bookraw,
        'aprueba_ingenieria':False,'goal_completo':False}
assert report['fuentes_estables']
(root/'seguimiento/DIAGNOSTICO_PESO_RELECTURA_268.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ('peso_shells_kn','peso_frames_kn','cargas_por_patron_kn','CM_geometria_releida_kn','delta_shells_con_libro_kn','delta_frames_con_libro_kn','delta_D_con_libro_kn')}))
