"""Verificación focal de la forma y afirmaciones del inventario corregido; no procedencia nativa."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

from draft2model import informe

root=Path(__file__).resolve().parents[1]
base={'caso_id':'sintetico-262','modelo_id':'c'*32,'huella_plan':'a'*64,'inventario':{
    'estado':'contabilidad_declarada_coherente','escenarios':[{'deposito':'TANQUE','estado':'lleno','fuente':'F-SINTETICA',
        'declaracion':'AGUA-TAN','modo':'patron_presion','patron_masa':'AGUA','volumen_m3':1.,'peso_kn':10.,
        'masa_kn_s2_m':10/9.80665,'factor_contenido':1,'fz_presion_kn':-10.}],
    'peso_total_kn':10.,'masa_total_kn_s2_m':10/9.80665,'aprueba_ingenieria':False,'crea_cargas':False,'ejecutable':False,
    'huella_liquidos':'b'*64,'estados':{'TANQUE':'lleno'},'masa_nativa_verificada':False,'nota':'Solo contrato sintético'}}
result={'caso_id':base['caso_id']}
evidence={'modelo':{'modelo_id':base['modelo_id']}}
cases=[]
for name in ('declarado_valido','nativo_sin_captura','plan_no_sha','sin_evidencia','modelo_ajeno','peso_nan'):
    value=deepcopy(base)
    ev=evidence
    if name=='nativo_sin_captura':value['inventario']['masa_nativa_verificada']=True
    if name=='plan_no_sha':value['huella_plan']='plan-de-otro-modelo'
    if name=='sin_evidencia':ev=None
    if name=='modelo_ajeno':value['modelo_id']='d'*32
    if name=='peso_nan':value['inventario']['peso_total_kn']=float('nan')
    try:
        informe._validar_contenido_masa(value,result,ev)
        accepted=True
    except ValueError:
        accepted=False
    cases.append({'caso':name,'aceptado':accepted,'correcto':accepted==(name=='declarado_valido')})
report={'fecha_utc':datetime.now(timezone.utc).isoformat(),'comprobaciones':cases,
    'correcto':all(c['correcto'] for c in cases),'alcance':'Forma/guardas del validador; no prueba fuente registrada, captura nativa ni informe real',
    'apis_remotas':0,'etabs':False}
with (root/'seguimiento/REVISION_INVENTARIO_INFORME_262.json').open('x',encoding='utf-8') as stream:
    json.dump(report,stream,ensure_ascii=False,indent=2)
print(json.dumps({'correcto':report['correcto'],'casos':len(cases),'masa_nativa_verificada':False}))
raise SystemExit(int(not report['correcto']))
