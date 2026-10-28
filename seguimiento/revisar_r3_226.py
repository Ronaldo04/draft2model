"""Contraste independiente de evidencia r3 existente: sin producto, API ni ETABS."""
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'tmp/r3'


def cargar(p):
    return json.loads(p.read_text(encoding='utf-8'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    plan = cargar(BASE / 'plan.json')
    cfg = cargar(BASE / 'configuracion.json')
    origen = plan['origen']['geometria']
    gp = BASE / ('fuentes/private/sintetico-001/geometrias/' + origen['version_id'] + '/geometria.json')
    assert sha(gp) == origen['sha256_geometria']
    geom = cargar(gp)
    assert len(geom['niveles']) == 5 and geom['unidad_longitud'] == 'm'
    assert [n['cota'] for n in geom['niveles']] == [0, 2.6, 5.2, 7.8, 10.4]
    superficie = next(s for s in geom['superficies'] if s['id'] == 'PLACA1')
    vertices = {v['id']: v for v in geom['vertices']}
    xyz = [tuple(F(str(vertices[i][k])) for k in ('x', 'y', 'z')) for i in superficie['vertices']]
    assert set(xyz) == {(F(0),F(0),F(0)), (F(0),F(3),F(0)),
                        (F(0),F(3),F('2.6')), (F(0),F(0),F('2.6'))}
    assert not geom['aberturas']
    declaracion = cfg['liquidos']['declaraciones']
    assert len(declaracion) == 1 and declaracion[0]['patron'] == 'HIDRO'
    agua = declaracion[0]['declaracion']
    assert agua['superficies'] == [{'superficie':'PLACA1','sentido_normal':1,'fuentes':['F1']}]
    assert agua['origen_momentos_m'] == [0,0,0]
    h, gamma = F(str(agua['nivel_libre_z_m'])), F(str(agua['peso_especifico_kn_m3']))
    assert h == F('1.2') and gamma == 10
    assert next(p for p in cfg['patrones'] if p['id']=='HIDRO')['multiplicador_peso_propio'] == 0
    assert next(c for c in cfg['casos'] if c['id']=='CHIDRO')['parametros']['patrones'] == [{'patron':'HIDRO','factor':1}]
    assert not any(c['patron']=='HIDRO' for c in cfg['cargas'])
    # Integración exacta de p(z)=gamma*(h-z), rectángulo y=0..3, z=0..h,
    # normal +X. My=integral(z*p), Mz=-integral(y*p), origen global0.
    fx = 3*gamma*h*h/2
    my = 3*gamma*h*h*h/6
    mz = -fx*F(3,2)
    esperado = [fx,F(0),F(0),F(0),my,mz]
    l = BASE / 'fuentes/private/sintetico-001/lecturas_analisis/a7598bc374ae48308a35371ef3d98169'
    a = BASE / 'fuentes/private/sintetico-001/analisis_etabs/d9fd87ed277241a89677eaa2bbcf48c0'
    recibo = cargar(l/'aceptacion_lectura.json')
    assert recibo['modo']=='real' and recibo['aceptada']
    assert sha(l/'respuesta.json') == recibo['sha256_respuesta']
    assert sha(l/'solicitud.json') == recibo['sha256_solicitud']
    assert sha(a/'aceptacion_analisis.json') == recibo['sha256_aceptacion_analisis']
    aceptacion = cargar(a/'aceptacion_analisis.json')
    assert sha(a/'analizado.EDB') == recibo['sha256_edb'] == aceptacion['guardado']['sha256']
    assert aceptacion['estados_casos'] == {'CHIDRO':4,'EST':4}
    ar = cargar(a/'respuesta.json')
    assert ar['modo_ejecucion']=='real' and ar['datos']['analisis_ejecutado']
    assert ar['datos']['sha256_entrada'] == sha(BASE/'modelo.EDB')
    lectura = cargar(l/'respuesta.json')
    assert lectura['modo_ejecucion']=='real'
    datos = lectura['datos']
    assert datos['instancia_cerrada'] and datos['sha256_modelo_verificado']==recibo['sha256_edb']
    assert datos['estado_casos']=={'CHIDRO':4} and datos['casos']==['CHIDRO']
    react = datos['resultados_api']['BaseReact']
    assert react['unidades']=='kN_m_C' and react['punto_reaccion']==['0','0','0']
    assert react['casos_seleccionados']==['CHIDRO'] and len(react['filas'])==1
    fila = react['filas'][0]
    assert fila['LoadCase']=='CHIDRO' and float(fila['StepNum'])==0
    valores = [float(fila[k]) for k in ('FX','FY','FZ','MX','MY','MZ')]
    residuos = [float(e)+v for e,v in zip(esperado,valores)]
    limites = [1e-7*max(1,abs(float(e))) for e in esperado]
    assert all(abs(r)<=t for r,t in zip(residuos,limites))
    relectura = BASE/'lectura/f975dc0c30774136b065e2cb9f78a38f'
    rv = cargar(relectura/'resultado_verificacion.json')
    assert rv['sha256_respuesta']==sha(relectura/'respuesta.json')
    assert rv['sha256_edb']==sha(BASE/'modelo.EDB')
    assert rv['estado']=='verificado' and not rv['discrepancias'] and not rv['incompletos']
    assert rv['cobertura']['malla']==rv['cobertura']['cargas_liquidos']=='completa'
    evidencia = {'estado':'equilibrio_estricto_contrastado','datos_sinteticos':True,
                 'fuerza_y_momento_analiticos':[float(e) for e in esperado],
                 'reacciones_api':valores,'residuos':residuos,'limites':limites,
                 'metodo':'Integración racional independiente de presión en rectángulo3x2.6, nivel1.2; sin importar calculadores del producto.',
                 'hash_geometria':sha(gp),'hash_edb_analizado':sha(a/'analizado.EDB'),
                 'hash_respuesta_lectura':sha(l/'respuesta.json'),
                 'niveles':[n['cota'] for n in geom['niveles']],
                 'relectura':'Recibo y hash vinculados;0discrepancias,0incompletos; malla y líquidos completos según comparador conservado.',
                 'limites':['No recalcula el modelo ni verifica todos los casos.',
                            'Relectura general contrastada por integridad, sin segundo comparador independiente de toda operación.',
                            'No acredita referencia real ni cumplimiento normativo ni revisión de ingeniería.']}
    (ROOT/'seguimiento/EQUILIBRIO_R3_226.json').write_text(json.dumps(evidencia,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'estado':evidencia['estado'],'residuo_maximo':max(map(abs,residuos))}))


if __name__=='__main__':
    main()
