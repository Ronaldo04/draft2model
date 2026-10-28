"""Contrastar corrección263 de métricas contra recibos existentes, sin reenvíos."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
paths=('seguimiento/claude_ruta/METRICAS_EXTRACCION_09.json',
       'seguimiento/DIAGNOSTICO_GEMINI_235.json','seguimiento/REVISION_NORMATIVA_RECUPERACION_236.json',
       'seguimiento/CUARTA_EXTRACCION_REAL_221.json')
raw={name:(root/name).read_bytes() for name in paths}
metrics,diagnosis,recovery,cost=(json.loads(raw[name]) for name in paths)
vision=metrics['extraccion_vision']
attempts=vision['intentos']
row=next(x for x in attempts if x['proveedor']=='gemini' and x['numero']==2)
stages=row['etapas'];den=vision['denominadores']
checks={
    '71crudos_coinciden_con_diagnostico':stages['respuesta_cruda']['candidatos']==diagnosis['candidatos']==71,
    '59adaptables_y12cuarentena_coinciden_con_revision':
        stages['recuperacion_local']['adaptables']==recovery['recuperacion_real_en_memoria']['candidatos']==59 and
        stages['recuperacion_local']['cuarentena']==recovery['recuperacion_real_en_memoria']['cuarentena']==12,
    'no_se_inventa_persistencia':stages['recuperacion_local']['persistido'] is recovery['persistido'] is False,
    'fallo_inicial_conservado':row['estado']=='fallido' and stages['validacion_inicial']['estado']=='fallida' and
        stages['validacion_inicial']['importados']==0,
    'denominadores_por_etapa_correctos':den['peticiones']==len(attempts)==6 and
        den['respuestas_con_candidatos_crudos_contados']==5 and den['candidatos_crudos_no_deduplicados']==299 and
        den['candidatos_importados_o_registrados']==228,
    'coste_openai_sin_cambios':vision['coste_openai_usd_total']==cost['coste_acumulado_openai_usd'],
    'sin_aprobaciones_ni_precision_fabricadas':vision['lecturas_aprobadas_totales']==0 and
        vision['precision_recall'].startswith('NO VERIFICABLE'),
    'fuentes_estables':all((root/name).read_bytes()==content for name,content in raw.items())}
report={'fecha_utc':datetime.now(timezone.utc).isoformat(),'comprobaciones':checks,'correcto':all(checks.values()),
    'fuentes':{name:hashlib.sha256(content).hexdigest() for name,content in raw.items()},
    'limites':['Verifica contabilidad de recibos y estados, no exactitud de candidatos ni benchmark humano',
               '299 no es cantidad deduplicada ni datos aprobados;59+12 no es importación productiva'],
    'etabs':False,'apis_remotas':0}
with (root/'seguimiento/REVISION_METRICAS_265.json').open('x',encoding='utf-8') as stream:
    json.dump(report,stream,ensure_ascii=False,indent=2)
print(json.dumps({'correcto':report['correcto'],'comprobaciones':len(checks)}))
raise SystemExit(int(not report['correcto']))
