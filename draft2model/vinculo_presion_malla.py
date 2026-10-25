"""Presión revisada → piezas CSI del plan regenerado; sin mutación ni ingeniería.

La integral sobre triángulos se contrasta con la integral independiente del
contorno fuente menos sus huecos. No basta comparar sumas de coeficientes.
"""
import hashlib
import json
import math
from pathlib import Path

from .acciones_liquidos import calcular_acciones_liquidos
from .cargas_liquidos_etabs import preparar_cargas_no_uniformes, evaluar_componente, CAMPOS, TABLA, ErrorCargaLiquido
from . import gestion_geometria as gg, malla_preparacion as mp, operaciones_etabs as op


def _canon(x):
    return json.dumps(x,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf-8')


def _sha(x):
    return hashlib.sha256(_canon(x)).hexdigest()


def _cruz(a,b):
    return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]


def _integrar(xyz, componentes, origen):
    area = math.hypot(*_cruz([xyz[1][k]-xyz[0][k] for k in range(3)],
                             [xyz[2][k]-xyz[0][k] for k in range(3)]))/2
    if not math.isfinite(area) or area <= 0:
        raise ErrorCargaLiquido('Triángulo degenerado o no representable.')
    r = [[p[k]-origen[k] for k in range(3)] for p in xyz]
    fuerza, momentos = [0.,0.,0.], []
    for comp in componentes:
        q = [evaluar_componente(comp,p) for p in xyz]
        total = math.fsum(q)
        eje,signo = {'Global-X':(0,1),'Global-Y':(1,1),'Gravity':(2,-1)}[comp['Dir']]
        fuerza[eje] += signo*area*total/3
        # Integral de r*q, producto de dos campos lineales: momentos de grado2.
        primero = [area/12*(math.fsum(p[k] for p in r)*total+
                            math.fsum(p[k]*v for p,v in zip(r,q))) for k in range(3)]
        normal = [0.,0.,0.];normal[eje] = signo
        momentos.append(_cruz(primero,normal))
    return area,fuerza,[math.fsum(m[k] for m in momentos) for k in range(3)]


def preparar_tabla_liquidos(raiz, configuracion, plan, declarada, fuentes, *, patron):
    """Vincula únicamente un patrón dedicado del plan0.4 aprobado, sin peso propio.

    No añade operaciones a un plan aprobado. La propuesta debe ser parte de un
    contrato nuevo y regenerable antes de habilitar su aplicación productiva.
    """
    try:
        if configuracion.get('version_contrato') != '0.4.0' or plan.get('version_contrato') != '0.4.0':
            raise ErrorCargaLiquido('Se requiere configuración y plan de malla0.4; no se reinterpreta el legado.')
        regenerado = op.generar_plan_por_version(Path(raiz),configuracion,**plan['opciones']).datos
        if _canon(regenerado) != _canon(plan):
            raise ErrorCargaLiquido('El plan no coincide con su regeneración completa.')
        patrones = {p['id']:p for p in configuracion['patrones']}
        if patron not in patrones or patrones[patron]['multiplicador_peso_propio'] != 0:
            raise ErrorCargaLiquido('Patrón explícito existente y sin peso propio requerido.')
        if any(c['patron']==patron for c in configuracion['cargas']):
            raise ErrorCargaLiquido('El patrón debe estar dedicado: ya contiene otras cargas declaradas.')
        consulta = gg.consultar_version(Path(raiz),configuracion['caso'],configuracion['geometria_origen']['version_id'])
        geo = consulta.geometria
        presion = preparar_cargas_no_uniformes(geo,declarada,fuentes)
        integral = calcular_acciones_liquidos(geo,declarada,fuentes)
        prep = mp.preparar_malla(geo,configuracion)
        if prep['huella_preparacion'] != plan['malla']['huella_preparacion']:
            raise ErrorCargaLiquido('La malla no corresponde al plan vigente.')
        niveles = (prep['cortes_nivel'] or {}).get('niveles_z_m', [])
        nodos = {n['csi']:n['xyz_m'] for n in prep['nodos']}
        triangulos = {t['csi']:t for t in prep['triangulos']}
        esperadas = {s['superficie']:s for s in integral['superficies']}
        filas,hosts = [],[]
        origen = integral['origen_momentos_m']
        h = declarada['declaracion']['nivel_libre_z_m']
        for host in presion['superficies']:
            nombre = host['superficie']
            if nombre not in prep['hosts']:
                raise ErrorCargaLiquido('Superficie de líquido sin asignación completa en la malla: '+nombre)
            if any(z not in niveles for z in host['cortes_obligatorios_z_m']):
                raise ErrorCargaLiquido('Falta corte explícito por nivel libre en '+nombre)
            piezas = prep['hosts'][nombre]['triangulos']
            if not piezas or set(piezas) != {t for t,x in triangulos.items() if x['host']==nombre}:
                raise ErrorCargaLiquido('Cobertura de piezas incompleta.')
            medidas=[];fuerzas=[];momentos=[]
            for pieza in piezas:
                xyz=[nodos[n] for n in triangulos[pieza]['nodos']]
                zs=[p[2] for p in xyz]
                if min(zs)<h<max(zs):
                    raise ErrorCargaLiquido('Una pieza cruza el nivel libre; no se aproxima la presión.')
                area,fuerza,momento=_integrar(xyz,host['componentes'],origen)
                medidas.append(area);fuerzas.append(fuerza);momentos.append(momento)
                for comp in host['componentes']:
                    filas.append({'UniqueName':pieza,'LoadPattern':patron,
                                  **{k:comp[k] for k in ('Dir','A','B','C','D','Restriction')}})
            f=[math.fsum(v[k] for v in fuerzas) for k in range(3)]
            m=[math.fsum(v[k] for v in momentos) for k in range(3)]
            esperado=esperadas[nombre]
            for a,b in zip(f+m,esperado['fuerza_kn']+esperado['momento_kn_m']):
                if not math.isfinite(a) or abs(a-b)>1e-9*max(1.,abs(a),abs(b)):
                    raise ErrorCargaLiquido('La presión sobre piezas no conserva fuerza y momento del contorno neto.')
            hosts.append({'superficie':nombre,'triangulos':list(piezas),'area_material_m2':math.fsum(medidas),
                          'fuerza_kn':f,'momento_kn_m':m,'fuerza_fuente_kn':esperado['fuerza_kn'],
                          'momento_fuente_kn_m':esperado['momento_kn_m'],'aberturas_ids':host['aberturas_ids']})
        filas.sort(key=lambda row:(row['UniqueName'],row['LoadPattern'],row['Dir']))
        resultado={'contrato':'draft2model.tabla_liquidos_malla','version_contrato':'0.1.0',
                   'tabla':TABLA,'version_tabla':1,'campos':list(CAMPOS),'unidades':'kN_m_C','filas':filas,
                   'patron':patron,'hosts':hosts,'origen_momentos_m':origen,
                   'origen':{'huella_plan':plan['huella_plan'],'sha256_plan_canonico':_sha(plan),
                             'huella_configuracion':plan['origen']['huella_configuracion'],
                             'huella_declaracion':declarada['huella_declaracion'],
                             'huella_preparacion_malla':prep['huella_preparacion'],
                             'sha256_geometria_canonica':_sha(geo)},
                   'criterio_conservacion':'|a-b| <= 1e-9*max(1,|a|,|b|), computacional; no tolerancia de ingeniería',
                   'estado':'propuesta_vinculada_no_aplicada','ejecutable':False,'aplicado':False,'aprueba_ingenieria':False}
        resultado=json.loads(_canon(resultado))
        resultado['huella_tabla']=_sha(resultado)
        return resultado
    except ErrorCargaLiquido:
        raise
    except (ValueError,KeyError,TypeError,OSError,OverflowError) as exc:
        raise ErrorCargaLiquido('No se puede vincular la presión al plan vigente: '+str(exc)) from exc
