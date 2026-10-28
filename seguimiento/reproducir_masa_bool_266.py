"""Contraste de tipo numérico inválido en adaptador de captura; no ETABS ni modelo real."""
from copy import deepcopy
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from draft2model import libro_masa as lb
from draft2model import lectura_analisis as la

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--revision267',action='store_true')
args=parser.parse_args()
target=root/'seguimiento'/('REVISION_MASA_BOOL_267.json' if args.revision267 else 'REPRODUCCION_MASA_BOOL_266.json')
if target.exists():raise ValueError('No sobrescribir evidencia existente: '+target.name)
base={'unidades':'kN_m_C','retorno':0,'numero_resultados':1,
      'point_elements':['P1'],'mass_sources':['MsSrc1'],
      'U1':['1'],'U2':['1'],'U3':['0'],'R1':['0'],'R2':['0'],'R3':['0'],
      'observaciones':[{'point_element':'P1','mass_source':'MsSrc1','global_xyz':['0','0','0'],
                       'point_axes_deg':['0','0','0'],'U1':'1','U2':'1','U3':'0','R1':'0','R2':'0','R3':'0'}]}
rows=[]
cases=('numerico_texto','booleano_no_es_masa','solo_array_bool','solo_observacion_bool','coordenada_bool','eje_bool') if args.revision267 else ('numerico_texto','booleano_no_es_masa')
for name in cases:
    capture=deepcopy(base)
    if name=='booleano_no_es_masa':
        for k in ('U1','U2'):
            capture[k][0]=True
            capture['observaciones'][0][k]=True
    if name=='solo_array_bool':capture['U1'][0]=True
    if name=='solo_observacion_bool':capture['observaciones'][0]['U1']=True
    if name=='coordenada_bool':capture['observaciones'][0]['global_xyz'][0]=True
    if name=='eje_bool':capture['observaciones'][0]['point_axes_deg'][0]=False
    try:
        la._validar_masa_api(capture,'kN_m_C')
        shape='aceptada'
    except Exception as error:shape=type(error).__name__
    try:
        contrast=lb.contrastar_masa_nativa(capture,{'masa_total_kn_s2_m':1.},capture_id='captura-sintetica266',
                                          fuente_esperada='MsSrc1',tolerancia_relativa=1e-6)
        result=contrast['estado']
    except Exception as error:result=type(error).__name__
    rows.append({'caso':name,'forma_lector':shape,'contraste':result,
                 'correcto':(shape=='aceptada' and result=='coherente') if name=='numerico_texto' else (shape!='aceptada' and result!='coherente')})
record={'fecha_utc':datetime.now(timezone.utc).isoformat(),'casos':rows,'etabs':False,'apis_remotas':0,
        'alcance':'Tipado y conversión del adaptador con un JSON sintético de una fila, no evidencia de ejecución nativa',
        'hallazgo':'float(True) convierte booleano a masa1 antes de llegar al validador estricto; no debe aceptarse como masa tipada',
        'fuentes':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in
                   ('draft2model/libro_masa.py','draft2model/lectura_analisis.py')}}
record['revision_corregida']=args.revision267
record['correcto']=all(row['correcto'] for row in rows)
with target.open('x',encoding='utf-8') as stream:
    json.dump(record,stream,ensure_ascii=False,indent=2)
print(json.dumps(rows))
if args.revision267:raise SystemExit(int(not record['correcto']))
