"""Contrasta bytes y relectura nativa conservada; NO inicia ETABS ni solver."""
import copy
import hashlib
import json
import math
from fractions import Fraction as F
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
SOURCE=ROOT/'tmp/columna_l_246b/registro.json'
raw=SOURCE.read_bytes()
d=json.loads(raw.decode('utf-8-sig'))
checks=[]
def check(name, passed, **evidence):
    checks.append({'caso':name,'pasa':bool(passed),**evidence})
def equal(a,b):
    if isinstance(a,dict):
        return isinstance(b,dict) and a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
    if isinstance(a,list):
        return isinstance(b,list) and len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    if isinstance(a,(int,float)) and not isinstance(a,bool):
        return math.isfinite(a) and math.isfinite(b) and math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-14)
    return a==b
check('ensayo_sintetico_sin_error', d['datos_sinteticos'] is True and d['error'] is None)
check('dos_cierres_API_declarados',len(d['cierres'])==2 and all(c['confirmado'] is True for c in d['cierres']))
edb=ROOT/'tmp/columna_l_246b/columna_l.EDB'
sha=hashlib.sha256(edb.read_bytes()).hexdigest()
check('bytes_EDB_no_alterados_reapertura',sha==d['sha256_final']==d['sha256_antes_reapertura'])
fases=d['fases']
check('fases_esperadas',[f['fase'] for f in fases]==['construccion','reapertura'])
length={'kN_m_C':1.,'N_mm_C':.001}
norm=[]
for fase in fases:
    escala=length[fase['unidades']]
    source=copy.deepcopy(fase)
    for s in source['secciones'].values():
        for k in ('T3','T2','Tf','TwC','TwT'): s[k]*=escala
        for k,v in s['props'].items():
            power=2 if k in ('Area','As2','As3') else 4 if k in ('Torsion','I22','I33') else 3 if k in ('S22','S33','Z22','Z33') else 1
            s['props'][k]=v*escala**power
    for frame in source['frames'].values():
        for k in ('offset_i','offset_j'): frame[k]=[v*escala for v in frame[k]]
    norm.append(source)
check('cuatro_secciones_releidas',len(norm[0]['secciones'])==len(norm[1]['secciones'])==4)
for ident,s in norm[0]['secciones'].items():
    check(f'seccion_persiste_{ident}',equal(s,norm[1]['secciones'][ident]))
    check(f'area_analitica_L_{ident}',math.isclose(s['props']['Area'],float(F('.4')**2-F('.25')**2),rel_tol=1e-12))
for ident,frame in norm[0]['frames'].items():
    check(f'insercion_persiste_{ident}',equal(frame,norm[1]['frames'][ident]))

# Control independiente que distingue ensayo observado y flexión asimétrica.
s=norm[0]['secciones']['L_M20_M30']['props']
u=d['resultados_tope']['L_M20_M30_C10']['FX']
E=d['carga']['E_kN_m2'];H=d['carga']['H_m'];P=d['carga']['FX_kN']
nu=.2  # script ensayo SetMPIsotropic; no se atribuye al concreto del caso real
G=E/(2*(1+nu))
ux_desacoplado=P*H**3/(3*E*s['I22'])+P*H/(G*s['As2'])
check('C10_reproduce_flexion_diagonal_mas_cortante',math.isclose(u[0],ux_desacoplado,rel_tol=1e-12) and abs(u[1])<1e-14,observado=u[:2],ux_diagonal=ux_desacoplado)
# Integral independiente de dos rectángulos menos solape.
a,b=F('.4'),F('.15')
area=2*a*b-b*b
c=(a*b*a/2+a*b*b/2-b*b*b/2)/area
I=(b*a**3+a*b**3-b**4)/3-area*c*c
Ixy=(a*a*b*b+a*a*b*b-b**4)/4-area*c*c
for ident, sec in norm[0]['secciones'].items():
    check(f'inercias_diagonales_analiticas_{ident}',
          all(math.isclose(sec['props'][key],float(I),rel_tol=1e-12) for key in ('I22','I33')))
ux_acoplado=P*H**3/(3*E)*float(I/(I*I-Ixy*Ixy))
uy_acoplado=P*H**3/(3*E)*float(Ixy/(I*I-Ixy*Ixy))
check('acoplamiento_no_acreditado_por_ensayo',abs(uy_acoplado)>1e-3 and abs(u[1])<1e-14,ux_Euler_Bernoulli_acoplado=ux_acoplado,uy_Euler_Bernoulli_acoplado=uy_acoplado,I=float(I),Ixy=float(Ixy))
capture=ROOT/'tmp/revision_c1_codex_249'
capture.mkdir(exist_ok=True)
(capture/'registro.json').write_bytes(raw)
result={'estado':'correcto_con_limites' if all(x['pasa'] for x in checks) else 'fallo',
        'recibo_sha256':hashlib.sha256(raw).hexdigest(),'EDB_sha256':sha,'comprobaciones':checks,
        'limites':'Ensayo sintetico conservado, no piloto. Area/dimensiones/espejos/inserciones y relectura persistentes. No acredita acoplamiento flector asimetrico; no se infiere limite general del programa. Cierres sustentados por retornoAPI registrado, no auditoria actual de procesos ajenos.'}
(ROOT/'seguimiento/REVISION_C1_NATIVA_CODEX_249.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'estado':result['estado'],'comprobaciones':len(checks),'fallos':[x for x in checks if not x['pasa']]},ensure_ascii=False))
assert result['estado']=='correcto_con_limites'
