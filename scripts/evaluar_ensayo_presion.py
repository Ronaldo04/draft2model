"""Equilibrio del ensayo sintético185/186, no certificación ni control del proyecto real."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def evaluar(record):
    if (record.get('datos_sinteticos') is not True or record.get('error') is not None
            or record.get('solver_ejecutado') is not True or record.get('cierre_confirmado') is not True
            or record.get('unidades_reacciones')!='kN_m_C'
            or record.get('sha256_original')!=record.get('sha256_original_posterior')):
        raise ValueError('Ensayo no completado, unidades distintas u original alterado.')
    imp=record['importacion']
    if any(imp[k]!=0 for k in ('errores','fatales','avisos')):raise ValueError('Importación no aceptada.')
    table=record['tabla'];fields=table['campos'];data=table['datos'];count=table['registros']
    if count<=0 or len(data)!=count*len(fields):raise ValueError('Tabla no uniforme vacía o truncada.')
    names=[]
    for i in range(count):
        row=dict(zip(fields,data[i*len(fields):(i+1)*len(fields)]));names.append(row['UniqueName'])
        if row['LoadPattern']!='HIDRO' or row['Dir']!='Global-Y' or row['Restriction']!='Zero Positive Values':raise ValueError('Patrón/dirección/restricción ajenos al ensayo.')
        if [float(row[k]) for k in ('A','B','C','D')]!=[0,0,10,-15]:raise ValueError('Coeficientes ajenos al ensayo.')
    if len(set(names))!=count:raise ValueError('Carga duplicada sobre una pieza.')
    reactions=record['reacciones']
    if not reactions:raise ValueError('Sin reacciones observadas.')
    def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
    for row in reactions:
        if row['caso']!='HIDRO' or any(not isinstance(row[k],list) or len(row[k])!=3 or any(type(x) not in (int,float) or not math.isfinite(x) for x in row[k]) for k in ('xyz_m','fuerza','momento')):raise ValueError('Reacción no representable o de otro caso.')
    forces=[math.fsum(x['fuerza'][k] for x in reactions) for k in range(3)]
    moments=[math.fsum(x['momento'][k]+cross(x['xyz_m'],x['fuerza'])[k] for x in reactions) for k in range(3)]
    # Integrales cerradas: F=45−1.25; Mx=−(22.5−35/24); Mz=90−1.875.
    expected_force=[0,175/4,0];expected_moment=[-505/24,0,705/8]
    residual_force=[x-y for x,y in zip(forces,expected_force)]
    residual_moment=[x-y for x,y in zip(moments,expected_moment)]
    numerical=1e-7 # umbral computacional explícito del ensayo en kN y kN·m, no criterio de diseño
    return {'ensayo':'muro4x3_hueco1x1_gamma10_nivel1.5','datos_sinteticos':True,
            'piezas_cargadas':count,'reacciones':len(reactions),'fuerza_reaccion_kn':forces,'momento_reaccion_origen_kn_m':moments,
            'esperado_fuerza_kn':expected_force,'esperado_momento_kn_m':expected_moment,
            'residuo_fuerza_kn':residual_force,'residuo_momento_kn_m':residual_moment,'umbral_computacional':numerical,
            'equilibrio_ensayo_sintetico':all(abs(x)<=numerical for x in residual_force+residual_moment),
            'aprueba_modelo':False,'aprueba_ingenieria':False,
            'limites':['Solo balance estático del ensayo sintético; no prueba tensiones/deformaciones/convergencia ni proyecto real.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('registro',type=Path);parser.add_argument('--salida',type=Path,required=True)
    args=parser.parse_args();raw=args.registro.read_bytes();out=evaluar(json.loads(raw.decode('utf-8-sig')))
    out['sha256_registro']=hashlib.sha256(raw).hexdigest()
    with args.salida.open('x',encoding='utf-8') as stream:json.dump(out,stream,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({k:out[k] for k in ('equilibrio_ensayo_sintetico','fuerza_reaccion_kn','momento_reaccion_origen_kn_m','residuo_fuerza_kn','residuo_momento_kn_m')},ensure_ascii=False))


if __name__=='__main__':main()
