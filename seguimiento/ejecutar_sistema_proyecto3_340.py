"""Ejecuta componentes331, sin interpretar planos ni fabricar revisiones/geometría."""
import argparse
import copy
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'tmp/validacion_distribucion_331/fuentes'
sys.path.insert(0,str(SOURCE))
from draft2model.ingreso import registrar_expediente
from draft2model.revision_documental import revisar_expediente
from draft2model.recortes import generar_recorte
from draft2model.entrada_vision import preparar_paquete
from draft2model import proveedor_openai as api
from draft2model.credenciales_locales import cargar
from draft2model.revision_visual import RevisionLocal
from draft2model.gestion_extraccion import exportar_version

CASE='vivienda-unifamiliar-003'
STATE=ROOT/'seguimiento/EJECUCION_PROYECTO3_340.json'
LEDGER=ROOT/'seguimiento/CONSUMO_API_211.json'

def save(data):
    STATE.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enviar',action='store_true')
    args=parser.parse_args()
    if not args.enviar:
        assert not STATE.exists(),'Conservar ejecución existente; no preparar duplicados.'
        source=ROOT/'planos_muestra/proyecto_3_vivienda_unifamiliar'
        paths=sorted(source.glob('*.pdf'))
        assert len(paths)==4
        manifest=registrar_expediente(CASE,paths,ROOT/'data/private',uso_autorizado=True,
                                     provisional_fuera_alcance=False)
        revision=revisar_expediente(manifest,max_lado=1600)
        record=json.loads(revision.read_text(encoding='utf-8'))
        crops=[]
        for document in record['documentos']:
            assert not document.get('error'), 'Documento no procesable por el sistema.'
            for page in document['paginas']:
                number=page['numero']
                crops.append(generar_recorte(manifest,document['id'],number,[0,0,1,1],dpi=150,
                                             etiqueta='pagina_completa_automatica'))
        request=preparar_paquete(manifest,revision,crops)
        plan=api.preparar_plan(manifest,request,modelo='gpt-5.4',max_tokens=16384,detalle='high')
        payload,summary=api.preparar_peticion(manifest,request,modelo='gpt-5.4',max_tokens=16384,detalle='high')
        without_images=copy.deepcopy(payload);n=0
        for message in without_images['input']:
            for part in message['content']:
                if part['type']=='input_image':part['image_url']='';n+=1
        tokens_bound=len(json.dumps(without_images,ensure_ascii=False).encode('utf-8'))+1000+n*3000
        # Regla interna de la autorización211; estimación, no factura ni tarifa actual acreditada.
        internal_bound=tokens_bound*2.5/1_000_000+16384*15/1_000_000
        assert tokens_bound<272000 and internal_bound<=1
        state={'fecha_utc':datetime.now(timezone.utc).isoformat(),'caso':CASE,'etapa':'preparado_sin_envio',
               'codigo_sistema':'software331 exacto, sin modificaciones','fuentes':str(SOURCE.relative_to(ROOT)),
               'manifest':str(manifest.relative_to(ROOT)),'revision':str(revision.relative_to(ROOT)),
               'solicitud':str(request.relative_to(ROOT)),'plan':str(plan.relative_to(ROOT)),
               'imagenes':n,'recortes':'Páginas completas, misma regla para todos los PDF; sin selección semántica manual.',
               'peticion_sha256':summary['peticion_sha256'],'reserva_usd':1,
               'estimacion_interna_usd':internal_bound,'datos_aportados_usuario':{
                 'ubicacion':'San Juan de Miraflores, Lima','cisterna_incluida':True,'estudio_suelos':'no aportado'},
               'datos_modelo_completados_por_codex':False,'revisiones_fabricadas':False,
               'modelo_generado':False,'analisis_etabs':False,'goal_completo':False}
        save(state)
        print(json.dumps({k:state[k] for k in ('caso','etapa','imagenes','plan')}))
        return
    state=json.loads(STATE.read_text(encoding='utf-8'))
    assert state['etapa']=='preparado_sin_envio','No reenviar; revisar resultado conservado.'
    manifest=ROOT/state['manifest'];plan=ROOT/state['plan']
    values=cargar(ROOT/'data/private/credenciales.local.md')
    key=values.get('OPENAI_API_KEY')
    if not key:raise ValueError('Credencial OpenAI no disponible.')
    lock=ROOT/'seguimiento/CONSUMO_API_211.lock'
    with lock.open('x',encoding='utf-8') as stream:stream.write('Reserva proyecto3; no repetir ante interrupción.\n')
    try:
        ledger=json.loads(LEDGER.read_text(encoding='utf-8'))
        assert len(ledger['openai'])<5 and sum(x['reserva_usd'] for x in ledger['openai'])+1<=5
        assert all(x.get('peticion_sha256')!=state['peticion_sha256'] for x in ledger['openai'])
        entry={'numero':len(ledger['openai'])+1,'modelo':'gpt-5.4','caso':CASE,'reserva_usd':1,
               'estado':'reservado_no_reintentar','fecha_utc':datetime.now(timezone.utc).isoformat(),
               'plan':state['plan'],'plan_sha256':hashlib.sha256(plan.read_bytes()).hexdigest(),
               'peticion_sha256':state['peticion_sha256'],'finalidad':'revision_extraccion_planos'}
        ledger['openai'].append(entry)
        LEDGER.write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        state.update(etapa='peticion_reservada_no_reintentar',peticion_openai_numero=entry['numero'])
        save(state)
        os.environ['OPENAI_API_KEY']=key
        result_path=api.ejecutar_plan(manifest,plan,autorizar_envio=True,timeout=180,importar_automaticamente=True)
        result=json.loads(result_path.read_text(encoding='utf-8'))
        entry.update(estado=result['estado'],resultado=str(result_path.relative_to(ROOT)),uso=result.get('usage'))
        LEDGER.write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        state.update(etapa=result['estado'],resultado=entry['resultado'],uso=entry['uso'],
                     duracion_api_segundos=result.get('duracion_api_segundos'),
                     version_importada=result.get('version_importada'))
        save(state)
        if state['version_importada']:
            app=RevisionLocal(ROOT/'data/private')
            opened=app.version(CASE,state['version_importada'])
            candidates=opened['datos']['candidatos']
            exported=exportar_version(ROOT/'data/private',CASE,state['version_importada'])
            state.update(candidatos=len(candidates),
              pendientes=sum(c.get('revision',{}).get('estado','pendiente')=='pendiente' for c in candidates),
              candidatos_exportados_revisados=len(exported.datos['candidatos']),
              comprobacion=opened['comprobacion'],
              geometrias_generadas=app.documentos(CASE).get('geometrias',[]),
              limite_observado='Conversión requiere lecturas revisadas y manifiesto; no se proporcionaron manualmente.',
              etapa='lecturas_importadas_pendientes_sin_geometria')
            save(state)
        print(json.dumps({k:state.get(k) for k in ('caso','etapa','version_importada','candidatos','pendientes',
                         'candidatos_exportados_revisados','geometrias_generadas','resultado')},ensure_ascii=False))
    finally:
        os.environ.pop('OPENAI_API_KEY',None)
        lock.unlink()

if __name__=='__main__':
    try:main()
    except Exception as error:
        # No publicar secretos, imágenes, texto del proveedor ni excepciones de terceros.
        print(json.dumps({'estado':'detenido_sin_reintento','tipo':type(error).__name__}))
        raise SystemExit(2)
