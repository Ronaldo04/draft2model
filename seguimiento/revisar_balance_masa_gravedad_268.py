"""Contraste independiente de masa ensamblada frente a reacciones estáticas archivadas."""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime, timezone
import json
import hashlib

root=Path(__file__).resolve().parents[1]
paths={
    'reacciones':'data/private/pueblo-libre-002/lecturas_analisis/74d78008b7804616abcbf5dbd23a08b7/respuesta.json',
    'masa':'data/private/pueblo-libre-002/lecturas_analisis/9b1080d1f35d4007aef5fd92f527cea0/respuesta.json',
    'libro':'tmp/recorrido_09d1/resultados/libro_masa.json',
    'registro':'tmp/recorrido_09d1/registro_resultados.json'}
raw={k:(root/p).read_bytes() for k,p in paths.items()}
reac,mass,book,reg=(json.loads(raw[k].decode('utf-8-sig')) for k in paths)
tables={t['clave']:t for t in reac['datos']['tablas']}
rows={r['OutputCase']:r for r in tables['Base Reactions']['filas'] if r['OutputCase'] in ('CM','CV','CAGUA')}
assert len(rows)==3
g=D(str(book['gravedad_m_s2'])); c=book['contribuciones']
native_weight=D(rows['CM']['FZ'])+D('0.25')*D(rows['CV']['FZ'])+D(rows['CAGUA']['FZ'])
native_mass=D(str(reg['masa']['masa_observada_U1']))
book_cm=D(str(c['peso_propio_por_patrones']['peso_kn']))+D(str(c['cargas_D']['peso_kn']))
report={
    'fecha_utc':datetime.now(timezone.utc).isoformat(),
    'alcance':'Aritmética de respuestas archivadas; no revalidación completa ni nuevas llamadas ETABS.',
    'hipotesis_balance':'CM = peso propio + D; CV = L; CAGUA = líquidos; factores1/0.25/1 del libro actual.',
    'peso_estatico_nativo_equivalente_kn':str(native_weight),
    'masa_nativa_por_gravedad_kn':str(native_mass*g),
    'diferencia_estatica_masa_kn':str(native_weight-native_mass*g),
    'masa_por_reacciones':str(native_weight/g),
    'masa_ensamblada_U1':str(native_mass),
    'CM_libro_kn':str(book_cm),'CM_ETABS_kn':rows['CM']['FZ'],
    'diferencia_CM_libro_menos_ETABS_kn':str(book_cm-D(rows['CM']['FZ'])),
    'diferencia_CV_libro_menos_ETABS_kn':str(D(str(c['cargas_L']['peso_kn']))-D(rows['CV']['FZ'])),
    'conclusion':'El desfase del libro se concentra en peso propio+D de CM: ~6,868kN. Masa ensamblada*g y CM+0,25CV+CAGUA nativos difieren0,001673kN, una diferencia mucho menor que el desfase del libro, sin declarar igualdad exacta. Esto orienta a contrastar geometría/peso/cargas D del libro con su transporte; no justifica aumentar tolerancia ni confirma por sí solo la causa.',
    'fuentes_sha256':{paths[k]:hashlib.sha256(v).hexdigest() for k,v in raw.items()},
    'fuentes_estables':all((root/paths[k]).read_bytes()==v for k,v in raw.items()),
    'producto_modificado':False,'aprueba_ingenieria':False,'goal_completo':False}
assert native_weight.is_finite() and native_mass.is_finite()
assert report['fuentes_estables']
(root/'seguimiento/BALANCE_MASA_GRAVEDAD_268.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ('peso_estatico_nativo_equivalente_kn','masa_nativa_por_gravedad_kn','diferencia_estatica_masa_kn','diferencia_CM_libro_menos_ETABS_kn')}))
