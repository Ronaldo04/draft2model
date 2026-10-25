"""Coeficientes hidrostáticos para la tabla CSI no uniforme; propuesta sin envío al motor."""
import hashlib
import json
import math
from .acciones_liquidos import calcular_acciones_liquidos,ErrorAccionesLiquidos

TABLA='Area Load Assignments - Non-uniform'
CAMPOS=('UniqueName','LoadPattern','Dir','A','B','C','D','Restriction')


class ErrorCargaLiquido(ValueError):
    pass


def preparar_cargas_no_uniformes(geometria,declarada,fuentes):
    """p=gamma*max(0,h-z); componente normal global y restricción ANTES de análisis.

    No resuelve IDs CSI, patrón, ni mapeo de piezas: corresponden al plan revisado.
    No sustituye presiones por fuerzas puntuales ni por intensidad uniforme.
    """
    try:
        calculo=calcular_acciones_liquidos(geometria,declarada,fuentes)
        gamma=declarada['declaracion']['peso_especifico_kn_m3'];h=declarada['declaracion']['nivel_libre_z_m']
        hosts=[]
        for item in calculo['superficies']:
            n=item['normal_carga'];loads=[]
            h=item.get('nivel_efectivo_z_m',declarada['declaracion']['nivel_libre_z_m'])   # cara física declarada (R253)
            for direction,factor in (('Global-X',n[0]),('Global-Y',n[1]),('Gravity',-n[2])):
                if factor==0:continue
                c=-gamma*factor;d=gamma*h*factor
                if not all(math.isfinite(x) for x in (c,d)):
                    raise ErrorCargaLiquido('Coeficientes globales no representables; no se aproxima la presión.')
                loads.append({'Dir':direction,'A':0.0,'B':0.0,'C':c,'D':d,
                              'Restriction':'Zero Negative Values' if factor>0 else 'Zero Positive Values',
                              'factor_normal':factor})
            z=[p['xyz_m'][2] for p in item['contornos'][0]['vertices_declarados']]
            hosts.append({'superficie':item['superficie'],'normal_carga':n,'componentes':loads,
                          **({'nivel_efectivo_z_m':h,'desplazamiento_cara_m':item['desplazamiento_cara_m']} if 'nivel_efectivo_z_m' in item else {}),
                          'cortes_obligatorios_z_m':[h] if min(z)<h<max(z) else [],
                          'aberturas_ids':item['aberturas_ids'],'fuentes':item['fuentes']})
        result={'contrato':'draft2model.cargas_liquidos_no_uniformes','version_contrato':'0.1.0',
                'tabla':TABLA,'version_tabla':1,'campos_importacion':list(CAMPOS),'unidades':'kN_m_C',
                'unidad_ABC':'kN/m3','unidad_D':'kN/m2','huella_declaracion':declarada['huella_declaracion'],
                'geometria_origen':declarada['geometria_origen'],'superficies':hosts,
                'estado':'propuesta_no_aplicada','ejecutable':False,'aplicado':False,'aprueba_ingenieria':False,
                'pendientes':['Patrón de carga revisado y sin duplicación de masa/peso propio',
                              'Cortar malla en cada nivel libre interior: restricción de signo sola no reproduce la carga parcial (ensayo185)',
                              'Mapeo completo de superficies a piezas del plan CSI vigente',
                              'Esquema/importación/relectura/equilibrio de estas cargas sobre modelo registrado']}
        canonical=json.dumps(result,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))
        # Copia sin alias mutables hacia geometría/declaración/fuentes del llamador.
        result=json.loads(canonical)
        result['huella_preparacion']=hashlib.sha256(canonical.encode()).hexdigest()
        return result
    except ErrorCargaLiquido:
        raise
    except (ErrorAccionesLiquidos,KeyError,TypeError,ValueError,OverflowError) as exc:
        raise ErrorCargaLiquido('No se puede preparar presión sin geometría y declaración vigentes: '+str(exc)) from exc


def evaluar_componente(componente,xyz_m):
    """Evaluador local de la ecuación de la tabla; no consulta ni escribe ETABS."""
    if (not isinstance(xyz_m,(list,tuple)) or len(xyz_m)!=3
            or any(type(x) not in (int,float) or not math.isfinite(x) for x in xyz_m)):
        raise ErrorCargaLiquido('Coordenadas XYZ finitas en metros requeridas.')
    try:
        value=math.fsum(componente[k]*x for k,x in zip(('A','B','C','D'),(*xyz_m,1)))
        if not math.isfinite(value):raise ValueError('Presión no finita.')
        restriction=componente['Restriction']
        if restriction=='Zero Negative Values':return max(0.0,value)
        if restriction=='Zero Positive Values':return min(0.0,value)
        raise ErrorCargaLiquido('Restricción hidrostática desconocida; no se admite presión de signo libre.')
    except (KeyError,TypeError,ValueError,OverflowError) as exc:
        raise ErrorCargaLiquido('Componente de presión inválida.') from exc
