"""Contraste puro de procedencia del campo opcional de masa en informe, sin datos privados."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

from draft2model import informe

root=Path(__file__).resolve().parents[1]
base={'caso_id':'caso-sintetico-261','huella_plan':'a'*64,'inventario':{
    'estado':'contabilidad_declarada_coherente','escenarios':[{'deposito':'TANQUE','estado':'lleno',
        'modo':'patron_presion','volumen_m3':1.,'peso_kn':10.,'masa_kn_s2_m':1.,'fz_presion_kn':-10.,
        'patron_masa':'AGUA','fuente':'referencia-sintetica'}],
    'peso_total_kn':10.,'masa_total_kn_s2_m':1.,'aprueba_ingenieria':False,'crea_cargas':False,'ejecutable':False,
    'huella_liquidos':'b'*64,'estados':{'TANQUE':'lleno'},'masa_nativa_verificada':False,'nota':'Prueba sintética sin ETABS'}}
cases=[]
for name, change in [('declarado_sin_masa_nativa',{}),('afirma_masa_nativa_sin_evidencia',{'native':True}),
                     ('plan_no_identificado',{'plan':'plan-de-otro-modelo'})]:
    value=deepcopy(base)
    if 'native' in change:value['inventario']['masa_nativa_verificada']=change['native']
    if 'plan' in change:value['huella_plan']=change['plan']
    try:
        informe._validar_contenido_masa(value,{'caso_id':base['caso_id']})
        cases.append({'caso':name,'aceptado':True})
    except Exception as error:
        cases.append({'caso':name,'aceptado':False,'error':type(error).__name__,'detalle':str(error)})
report={'fecha_utc':datetime.now(timezone.utc).isoformat(),'casos':cases,'alcance':'Validador puro opcional del informe; no se generó informe ni llamó ETABS',
        'apis_remotas':0,'etabs':False,'requiere_correccion':any(x['aceptado'] for x in cases[1:])}
out=root/'seguimiento/REPRODUCCION_INVENTARIO_INFORME_261.json'
with out.open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
print(json.dumps(report))
