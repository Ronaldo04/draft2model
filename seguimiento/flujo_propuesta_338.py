"""Flujo sintético con registro, revisión de cotas, CLI nueva e importación geométrica."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
work=root/'tmp/desarrollo_geometria_337'
sys.path.insert(0,str(work))
import pymupdf
from tests.test_propuesta_trazos import fixture
from draft2model.ingreso import registrar_expediente
from draft2model.revision_documental import revisar_expediente
from draft2model.revision_visual import RevisionLocal
from draft2model.gestion_geometria import importar_geometria,consultar_version

base=root/'tmp/g338c';assert not base.exists(),'Conservar evidencia previa.'
base.mkdir()
raw,_,cfg=fixture()
with pymupdf.open(stream=raw,filetype='pdf') as doc:
    for index,(ident,value) in enumerate((('C1',4),('C2',2),('C3',4),('C4',2))):
        doc[0].insert_text((5,72+index*6),f'{ident} {value:.2f} m',fontsize=5)
    raw=doc.tobytes()
source=base/'plano.pdf';source.write_bytes(raw)
manifest=registrar_expediente('demo-propuesta',[source],base/'casos',uso_autorizado=True,
                             provisional_fuera_alcance=True)
revisar_expediente(manifest,max_lado=256)
m=json.loads(manifest.read_text(encoding='utf-8'))
fingerprint=hashlib.sha256(manifest.read_bytes()).hexdigest()
candidates=[]
with pymupdf.open(stream=raw,filetype='pdf') as doc:
    page=doc[0]
    for ident,value in (('C1',4),('C2',2),('C3',4),('C4',2)):
        rect=page.search_for(f'{ident} {value:.2f} m')[0]
        candidates.append({'id':ident,'tipo':'cota','valor_propuesto':value,'unidad':'m',
             'texto_fuente':f'{ident} {value:.2f} m','metodo':{'tipo':'sintetico'},
             'evidencia':[{'archivo_id':'L0001','pagina':1,'original_sha256':hashlib.sha256(raw).hexdigest(),
             'bbox_normalizada':[rect.x0/page.rect.width,rect.y0/page.rect.height,
                                  rect.x1/page.rect.width,rect.y1/page.rect.height]}]})
extraction={'contrato':'draft2model.extraccion_preliminar','version_contrato':'0.1.0','caso':m['id'],
            'procedencia':{'tipo':'expediente','descripcion':'Expediente de prueba con PDF y lecturas SINTÉTICOS; no es un proyecto real.'},
            'alcance':m['alcance'],'sistema_coordenadas':'pagina_visible_normalizada','candidatos':candidates}
app=RevisionLocal(base/'casos')
saved=app.actuar('importar',{'caso':m['id'],'expediente_sha256':fingerprint,'extraccion_json':json.dumps(extraction)})
version=saved['id']
for candidate in candidates:
    record=app.version(m['id'],version)
    corrected=app.actuar('corregir',{'caso':m['id'],'expediente_sha256':fingerprint,'version':version,
         'huella':record['huella'],'candidato':candidate['id'],'estado':'revisado',
         'valor_revisado':candidate['valor_propuesto'],'unidad_revisada':'m',
         'fecha':'2026-10-24','revisor_declarado':'Revisor SINTÉTICO de pruebas',
         'motivo':'Revisión fabricada para probar software, no evaluación humana real.'})
    version=corrected['id']
config=base/'config.json';config.write_text(json.dumps(cfg),encoding='utf-8')
args=[sys.executable,'-X','utf8','-m','draft2model.propuesta_trazos','--raiz',str(base/'casos'),
      '--caso',m['id'],'--extraccion',version,'--archivo','L0001','--pagina','1',
      '--config',str(config),'--salida',str(base/'salida')]
run=subprocess.run(args,cwd=work,capture_output=True,encoding='utf-8',errors='replace',timeout=60)
(base/'cli.log').write_text(run.stdout+run.stderr,encoding='utf-8')
assert run.returncode==0,run.stderr[-1200:]
proposal=json.loads((base/'salida/propuesta.json').read_text(encoding='utf-8'))
assert len(proposal['geometria']['muros'])==4 and len(proposal['geometria']['nodos'])==4
pending=json.loads((base/'salida/manifiesto_pendiente.json').read_text(encoding='utf-8'))
blocked=False
try:
    app.conversion.crear({'caso':m['id'],'expediente_sha256':fingerprint,'extraccion':version,
                         'manifiesto_json':json.dumps(pending)})
except ValueError:
    blocked=True
assert blocked,'La plantilla sin declaración no debe convertirse.'
pending['operador_declarado']='Operador SINTÉTICO: declaración fabricada solo para pruebas.'
converted=app.conversion.crear({'caso':m['id'],'expediente_sha256':fingerprint,'extraccion':version,
                              'manifiesto_json':json.dumps(pending)})
imported=app.conversion.importar_geometria({'caso':m['id'],'expediente_sha256':fingerprint,
                 'version':converted['id'],'huella_conversion':converted['huella_conversion'],'confirmacion_explicita':True})
geo_id=imported['geometria']
consult=consultar_version(base/'casos',m['id'],geo_id)
assert consult.comprobacion.correcta
geometry=json.loads((manifest.parent/'geometrias'/geo_id/'geometria.json').read_text(encoding='utf-8'))
assert geometry['revision']=={'estado':'borrador','aprobacion':None}
assert imported['disponible_para_modelado'] is False and geometry['procedencia']['tipo']=='sintetico'
source_extraction=manifest.parent/'extracciones'/version/'extraccion.json'
extraction_bytes=source_extraction.read_bytes()
detected=False
try:
    source_extraction.write_bytes(extraction_bytes+b' ')
    try:app.conversion.consultar(m['id'],converted['id'],expediente_sha256=fingerprint)
    except ValueError:detected=True
finally:
    source_extraction.write_bytes(extraction_bytes)  # restauración exacta de fixture; no se reparan hashes
assert detected
receipt=json.loads((root/'seguimiento/ENTREGA_ACADEMICA_331_FINAL.json').read_text(encoding='utf-8'))
assert hashlib.sha256((root/receipt['archivo']).read_bytes()).hexdigest()==receipt['sha256']
result={'datos_sinteticos':True,'revision_sintetica':True,'api_calls':0,'etabs_nativo':False,
        'pasos':['registrar_pdf','revisar_documento','importar_cotas','revisar4cotas','cli_proponer','bloquear_plantilla_sin_operador',
                 'declaracion_sintetica','conversion_versionada','importar_borrador','consultar_version','detectar_cambio_fuente'],
        'cotas_de_calibracion':4,'coordenadas_de_nodos_declaradas_manualmente':0,'nodos_propuestos':4,'muros_propuestos':4,
        'estado_geometria':'borrador_sin_aprobacion','version_geometria':geo_id,
        'conversion':converted['id'],'fuente_alterada_detectada':detected,'fixture_restaurada_sin_reparar_huellas':True,
        'fuente_sha256':hashlib.sha256(raw).hexdigest(),'entrega331_intacta':True,
        'limitacion':'Prueba de software; no prueba de geometría automática del piloto real ni de cualquier construcción.'}
(root/'seguimiento/FLUJO_PROPUESTA_338.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
