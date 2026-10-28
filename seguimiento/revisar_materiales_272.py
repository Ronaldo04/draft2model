"""Contrasta cantidades de lectura nativa archivada y ledger geométrico independiente."""
from pathlib import Path
from decimal import Decimal as D
from types import SimpleNamespace
from datetime import datetime,timezone
import json,hashlib,sys
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from draft2model.lectura_analisis import LectorAnalisis
case=root/'data/private/pueblo-libre-002'
folder=case/'lecturas_analisis/461c751056c74acaa6d738b29f4df633'
raw={n:(folder/n).read_bytes() for n in ('solicitud.json','respuesta.json','aceptacion_lectura.json')}
request,response,receipt=(json.loads(raw[n].decode('utf-8-sig')) for n in raw)
sha=lambda b:hashlib.sha256(b).hexdigest()
assert receipt['aceptada'] is True and receipt['modo']=='real' and receipt['instancia_nueva_cerrada'] is True
assert receipt['sha256_solicitud']==sha(raw['solicitud.json']) and receipt['sha256_respuesta']==sha(raw['respuesta.json'])
assert receipt['corrida_analisis_id']=='7203c79a3ece4438b36d267ba80f3c4b'
edb=case/'analisis_etabs'/receipt['corrida_analisis_id']/'analizado.edb'
assert sha(edb.read_bytes())==receipt['sha256_edb']=='42371308a03d4f1bac8f5ed3aa5daf0421cdf3de27ff823f8f582c13ad2af394'
LectorAnalisis._comprobar_datos(SimpleNamespace(contenido=request),response['datos'])
tab=next(t for t in response['datos']['tablas'] if t['clave']=='Material List by Section Property')
assert response['datos']['unidades']=='kN_m_C'
geom_path=root/'seguimiento/DIAGNOSTICO_PESO_RELECTURA_268.json'
geom_raw=geom_path.read_bytes();geom=json.loads(geom_raw)
expected={**geom['peso_shells_por_seccion_kn'],**geom['peso_frames_por_seccion_kn']}
observed={}
for row in tab['filas']:
    observed[row['Section']]=observed.get(row['Section'],D(0))+D(row['Weight'])
assert not (set(observed)-set(expected))
assert all(D(str(expected[n]))==0 for n in set(expected)-set(observed))
comparison=[]
for name in sorted(expected):
    book=D(str(expected[name]));native=observed.get(name,D(0))
    comparison.append({'seccion':name,'inventario_geometrico_kn':str(book),'tabla_nativa_kn':str(native),'diferencia_kn':str(book-native)})
beam=next(c for c in comparison if c['seccion']=='VS-15X30')
known=D(beam['diferencia_kn']);total=D('6.8681120841357')
assert D('6.86')<known<D('6.87')
assert all(abs(D(c['diferencia_kn']))<D('0.001') for c in comparison if c['seccion']!='VS-15X30')
report={'fecha_utc':datetime.now(timezone.utc).isoformat(),'lectura':folder.name,
        'fuentes_sha256':{str((folder/n).relative_to(root)):sha(b) for n,b in raw.items()},
        'sha256_diagnostico_geometrico':sha(geom_raw),'sha256_edb':receipt['sha256_edb'],
        'comparacion_por_seccion':comparison,'diferencia_localizada_VS_kn':str(known),
        'desfase_CM_kn':str(total),'residuo_CM_no_atribuido_kn':str(total-known),
        'componente_localizada':True,'mecanismo_exacto_demostrado':False,
        'fuentes_estables':all((folder/n).read_bytes()==b for n,b in raw.items()) and geom_path.read_bytes()==geom_raw,
        'interpretacion':'La tabla confirma localización en VS-15X30. Longitud equivalente calculada desde su peso no prueba por sí sola una regla de offsets, descuento de paredes o una opción de peso propio seleccionada. No ajustar el ledger al peso observado.',
        'fuente_CSI':'https://installs.csiamerica.com/software/ETABS/2013/ReleaseNotesETABS2013v1320.pdf',
        'nota_CSI':'Incidente69133 documenta un control para incluir/excluir peso de las zonas de offset. Es antecedente oficial, no prueba de la selección efectiva en el EDB21.1 del piloto.',
        'SDK_instalado_inspeccionado':'cFrameObj expone GetEndLengthOffset(Name,ref bool,ref double,ref double,ref double) y SetEndLengthOffset(Name,bool,double,double,double,eItemType); no se encontró método SelfWeight. Solo reflexión, sin crear ETABS.',
        'alcance':'Integridad del paquete de lectura y contraste por sección; no nueva relectura, análisis, cierre de proceso observado en host ni aprobación de ingeniería.',
        'api_remota':False,'etabs_ejecutado':False,'goal_completo':False}
assert report['fuentes_estables']
(root/'seguimiento/REVISION_MATERIALES_272.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ('componente_localizada','mecanismo_exacto_demostrado','diferencia_localizada_VS_kn','residuo_CM_no_atribuido_kn','fuentes_estables')}))
