"""Preparar fixture modal/espectral inventada; no conecta con ETABS."""
import argparse
import copy
import json
from pathlib import Path
from draft2model.modelo_estructural import huella_configuracion
from draft2model.operaciones_etabs import generar_plan


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raiz',type=Path,required=True)
    p.add_argument('--configuracion-base',type=Path,required=True)
    p.add_argument('--salida',type=Path,required=True)
    args=p.parse_args(argv)
    config=json.loads(args.configuracion_base.read_bytes())
    if config.get('datos_sinteticos') is not True:raise ValueError('Solo datos sintéticos.')
    folder=args.salida.resolve()
    if folder.exists():raise ValueError('La salida debe ser nueva.')
    source=json.loads((Path(__file__).parent/'modelo_estructural_sintetico.json').read_bytes())
    for name in ('casos','espectros','combinaciones','analisis'):config[name]=copy.deepcopy(source[name])
    config['id']='ensayo-dinamico-sintetico'
    config['revision']={'estado':'aprobado','aprobacion':{
        'revisor_declarado':'Operador SINTÉTICO de fixture, sin revisión de ingeniería',
        'fecha':'2026-10-17','huella_configuracion':huella_configuracion(config),
        'alcance':'Parámetros inventados del ejemplo para probar construcción dinámica; no edificio real.',
        'identidad_revisor':'declarada_no_verificada'}}
    options={'destino_guardado':str(folder/'modelo.edb'),'tipo_shell_muro':'ShellThin',
        'gravedad_programa_m_s2':config['masa']['gravedad_m_s2'],
        'parametros_modales':{'MOD':{'frecuencia_desplazamiento_hz':0.0,'frecuencia_corte_hz':0.0,
                                    'tolerancia':1e-9,'desplazamiento_automatico':True}},
        'amortiguamiento_funciones':{'ESP-PRUEBA':0.05},'excentricidad_espectral':{'EX':0.0},
        'respuesta_rigida_espectral':{'EX':False}}
    plan=generar_plan(args.raiz,config,**options)
    folder.mkdir(parents=True,exist_ok=False)
    for name,value in [('configuracion.json',config),('plan.json',plan.datos)]:
        with (folder/name).open('x',encoding='utf-8') as file:json.dump(value,file,ensure_ascii=False,indent=2)
    print(json.dumps({'plan':plan.huella,'operaciones':len(plan.operaciones),'datos_sinteticos':True,'ejecuto_etabs':False}))


if __name__=='__main__':main()
