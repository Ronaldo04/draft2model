"""Dos consultas HTTP en memoria con Tesseract real, en expediente aislado."""
import hashlib
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from urllib.parse import urlencode

root=Path(__file__).resolve().parents[1]
work=root/'tmp/desarrollo_ocr_333'
sys.path.insert(0,str(work))
from draft2model.ingreso import registrar_expediente
from draft2model.revision_documental import revisar_expediente
from draft2model.revision_visual import RevisionLocal
from draft2model.ocr_local import CacheOCRLocal,ejecutar_tesseract
from tests import test_revision_visual as test_http

source=root/'data/private/provisional-001/originales/lamina-0001.pdf'
before=source.read_bytes()
base=work/'tmp/flujo_real_335'
assert not base.exists(),'Conservar expediente de ensayo ya registrado.'
base.mkdir(parents=True)
manifest=registrar_expediente('ocr-piloto-335',[source],base/'casos',uso_autorizado=True,
                            provisional_fuera_alcance=True)
revision=revisar_expediente(manifest,max_lado=256)
m=json.loads(manifest.read_text(encoding='utf-8'))
fingerprint=hashlib.sha256(manifest.read_bytes()).hexdigest()
app=RevisionLocal(base/'casos')
candidates=[{'id':ident,'tipo':'elemento','valor_propuesto':literal,'unidad':'no_aplica',
             'texto_fuente':literal,'metodo':{'tipo':'importado','descripcion':'Ensayo de OCR local aislado.'},
             'evidencia':[{'archivo_id':'L0001','pagina':1,'original_sha256':m['archivos'][0]['sha256'],
                           'bbox_normalizada':[0,0,1,1]}]}
            for ident,literal in (('C001','C-1'),('C002','C-2'))]
data={'contrato':'draft2model.extraccion_preliminar','version_contrato':'0.1.0','caso':m['id'],
      'procedencia':{'tipo':'expediente','descripcion':'Prueba aislada con primera lámina autorizada.'},
      'alcance':m['alcance'],'sistema_coordenadas':'pagina_visible_normalizada','candidatos':candidates}
saved=app.actuar('importar',{'caso':m['id'],'expediente_sha256':fingerprint,'extraccion_json':json.dumps(data)})
version=saved['id']
record=app.version(m['id'],version)
extraction=manifest.parent/'extracciones'/version/'extraccion.json'
original_extraction=extraction.read_bytes()
calls=[0]
def engine(png):
    calls[0]+=1
    return ejecutar_tesseract(png)
app._ocr_local=CacheOCRLocal(motor=engine)
server=SimpleNamespace(revision=app,token='token-local-de-prueba',origen='http://127.0.0.1:8766')
connection=SimpleNamespace(server=server)
responses=[]
for ident in ('C001','C002'):
    query={'caso':m['id'],'version':version,'candidato':ident,'expediente_sha256':fingerprint,
           'huella':record['huella'],'metodo':'ocr_local'}
    start=time.perf_counter()
    status,raw,_=test_http.HTTPRevisionTests.request(connection,'GET','/api/localizar-lectura?'+urlencode(query))
    elapsed=time.perf_counter()-start
    assert status==200,raw
    body=json.loads(raw)
    assert body['modifica_datos'] is False and body['metodo']=='ocr_local'
    responses.append({'candidato':ident,'pared_s':elapsed,'respuesta':body})
assert calls[0]==1,'Dos candidatos deben reutilizar la misma página OCR.'
assert source.read_bytes()==before and extraction.read_bytes()==original_extraction
assert app.documentos(m['id'])['versiones']==[version]
assert all(c.get('revision',{}).get('estado','pendiente')=='pendiente' for c in app.version(m['id'],version)['datos']['candidatos'])
receipt=json.loads((root/'seguimiento/ENTREGA_ACADEMICA_331_FINAL.json').read_text(encoding='utf-8'))
assert hashlib.sha256((root/receipt['archivo']).read_bytes()).hexdigest()==receipt['sha256']
result={'modo':'HTTP en memoria y motor Tesseract real, expediente aislado de primera lámina',
        'api_calls':0,'etabs_nativo':False,'ejecuciones_ocr':calls[0],'consultas':responses,
        'original_y_extraccion_intactos':True,'crea_versiones_por_buscar':False,
        'entrega331_intacta':True,'modelo_del_piloto_original_modificado':False,
        'limite':'Lecturas locales propuestas; no validación global de precisión ni modelado automático.'}
(root/'seguimiento/FLUJO_OCR_LOCAL_335.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'ocr':calls[0],'consultas':[{'candidato':r['candidato'],'estado':r['respuesta']['fuentes'][0]['estado'],
                 'regiones':r['respuesta']['fuentes'][0]['total'],'pared_s':r['pared_s']} for r in responses]},ensure_ascii=False))
