"""Estimación independiente opcional de peso efectivo; conserva el libro y contraste brutos."""
from __future__ import annotations

import math
import re
from .estimacion_extremos_auto import estimar_desde_plan, validar_captura_configuracion
from .libro_masa import contrastar_masa_nativa


def crear(plan, configuracion, libro, captura_config, captura_masa, *, lectura, fuente, tolerancia):
    cfg = validar_captura_configuracion(captura_config, 'kN_m_C', captura_config.get('version_etabs'))
    pred = estimar_desde_plan(plan, cfg)
    out = {'contrato':'draft2model.estimacion_masa_auto','version':'0.1.0','estado':'no_estimable',
           'huella_plan':plan['huella_plan'],'configuracion_capturada':dict(captura_config),
           'prediccion':pred,'masa_bruta_kn_s2_m':libro['masa_total_kn_s2_m'],
           'masa_estimada_kn_s2_m':None,'descuento_peso_kn':None,'factor_peso_propio':None,
           'gravedad_m_s2':libro['gravedad_m_s2'],'contraste_estimado':None,
           'motivos':[],'aprueba_ingenieria':False}
    if pred.get('estado') != 'estimacion' or pred.get('totales') is None or pred.get('problemas_plan'):
        out['motivos'].append('El perfil no cubre completamente las vigas del plan.')
    if pred.get('perfil_peso',{}).get('salvedades'):
        out['motivos'].extend(pred['perfil_peso']['salvedades'])
    if configuracion['masa']['incluir_masa_propia']:
        out['motivos'].append('El perfil no cubre masa propia directa además de la fuente por patrones.')
    if out['motivos']:
        return out
    g = libro['gravedad_m_s2']
    factor = libro['contribuciones']['peso_propio_por_patrones']['factor_efectivo']
    descuento = pred['totales']['descuento_kN']
    if any(type(x) not in (int,float) or not math.isfinite(x) or x < 0 for x in (g,factor,descuento)) or g <= 0:
        raise ValueError('Factores de estimación inválidos.')
    neto = libro['masa_total_kn_s2_m'] - descuento * factor / g
    if any(type(x) not in (int,float) or not math.isfinite(x) for x in (g,factor,descuento,neto)) or g <= 0 or factor < 0 or descuento < 0 or neto < 0:
        raise ValueError('Estimación de masa no finita o negativa.')
    # El contraste usa la captura completa: no convierte en éxito errores de ejes, fuente o distribución.
    contraste = contrastar_masa_nativa(captura_masa, {'masa_total_kn_s2_m':neto},
        capture_id=lectura,fuente_esperada=fuente,tolerancia_relativa=tolerancia)
    out.update(estado='estimado',masa_estimada_kn_s2_m=neto,descuento_peso_kn=descuento,
               factor_peso_propio=factor,contraste_estimado=contraste)
    return out


def validar(value, libro_resumen, contraste_bruto):
    keys={'contrato','version','estado','huella_plan','configuracion_capturada','prediccion',
          'masa_bruta_kn_s2_m','masa_estimada_kn_s2_m','descuento_peso_kn','factor_peso_propio',
          'gravedad_m_s2','contraste_estimado','motivos','aprueba_ingenieria'}
    if (not isinstance(value,dict) or set(value)!=keys or value['contrato']!='draft2model.estimacion_masa_auto'
            or value['version']!='0.1.0' or value['aprueba_ingenieria'] is not False
            or value['masa_bruta_kn_s2_m']!=libro_resumen['masa_total_kn_s2_m']
            or not isinstance(value['huella_plan'],str) or re.fullmatch('[0-9a-f]{64}',value['huella_plan']) is None
            or not isinstance(value['motivos'],list) or any(not isinstance(x,str) for x in value['motivos'])):
        raise ValueError('Estimación Auto del informe inválida.')
    c=value['configuracion_capturada']
    if not isinstance(c,dict):raise ValueError('Configuración capturada inválida.')
    validar_captura_configuracion(c,'kN_m_C',c.get('version_etabs'))
    if value['estado']=='no_estimable':
        if not value['motivos'] or any(value[k] is not None for k in ('masa_estimada_kn_s2_m','descuento_peso_kn','factor_peso_propio','contraste_estimado')):
            raise ValueError('Una abstención no puede contener masa estimada.')
        return
    if value['estado']!='estimado' or value['motivos']:
        raise ValueError('Estado de estimación inválido.')
    p=value['prediccion']
    if not isinstance(p,dict):raise ValueError('Predicción inválida.')
    total=p.get('totales'); rows=p.get('vigas')
    if (p.get('estado')!='estimacion' or p.get('problemas_plan') or not isinstance(total,dict)
            or p.get('plan_validado',{}).get('huella_plan')!=value['huella_plan'] or not isinstance(rows,list) or not rows
            or any(x.get('abstencion') or not x.get('descuento_peso') for x in rows)):
        raise ValueError('Cobertura de la estimación incompleta.')
    numbers=[value[k] for k in ('gravedad_m_s2','descuento_peso_kn','factor_peso_propio','masa_estimada_kn_s2_m')]
    numbers += [x['descuento_peso']['kN'] for x in rows]
    if any(type(x) not in (int,float) or not math.isfinite(x) or x < 0 for x in numbers) or value['gravedad_m_s2']<=0:
        raise ValueError('Valores de estimación inválidos.')
    descuento=math.fsum(x['descuento_peso']['kN'] for x in rows)
    neto=value['masa_bruta_kn_s2_m']-descuento*value['factor_peso_propio']/value['gravedad_m_s2']
    if (abs(descuento-value['descuento_peso_kn'])>1e-9 or abs(neto-value['masa_estimada_kn_s2_m'])>1e-9
            or total['vigas']!=len(rows) or abs(total['descuento_kN']-descuento)>1e-9):
        raise ValueError('Total estimado alterado.')
    contraste=value['contraste_estimado']
    if (not isinstance(contraste,dict) or contraste.get('masa_libro_kn_s2_m')!=value['masa_estimada_kn_s2_m']
            or contraste.get('estado') not in ('coherente','no_coherente')
            or contraste.get('aprueba_ingenieria') is not False
            or any(contraste.get(k)!=contraste_bruto.get(k) for k in
                   ('capture_id','fuente_esperada','tolerancia_relativa','masa_observada_U1','masa_observada_U2'))):
        raise ValueError('Contraste estimado de otra captura o criterio.')
