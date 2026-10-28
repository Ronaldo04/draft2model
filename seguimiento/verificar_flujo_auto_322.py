"""Recorrido real de lectura web + informe opcional, sin recalcular el edificio ni llamar LLM."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
from uuid import uuid4
from draft2model.revision_visual import RevisionLocal

root=Path(__file__).resolve().parents[1]
state_path=root/'seguimiento/FLUJO_AUTO_322.json'
assert not state_path.exists(), 'No repetir un recorrido ya iniciado; consultar su estado.'
case='pueblo-libre-002';analysis='7203c79a3ece4438b36d267ba80f3c4b';result='697bb37e9ce64f90ba1ef3e25733c8cc'
edb=root/'data/private'/case/'analisis_etabs'/analysis/'analizado.EDB'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
state={'inicio_utc':datetime.now(timezone.utc).isoformat(),'estado':'preparando',
       'sha_edb_antes':sha(edb),'goal_completo':False,'llamadas_remotas':0,'recalculo':False}
def save():state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
save()
app=RevisionLocal(root/'data/private')
fp=app.expediente(case)[2]
try:
    job=app.lecturas.preparar({'caso':case,'analisis':analysis,'expediente_sha256':fp,'clave_solicitud':uuid4().hex,
        'tablas':['Modal Periods And Frequencies'],'casos':['MODAL-E030'],
        'resultados_api':['AssembledJointMass','ConfiguracionAuto']})
    state.update(estado='lectura',trabajo=job['id'],huella_preparacion=job['huella_preparacion']);save()
    app.lecturas.ejecutar({'caso':case,'trabajo':job['id'],'huella_preparacion':job['huella_preparacion'],
        'expediente_sha256':fp,'confirmacion_explicita':True})
    thread=app.lecturas._threads.get(job['id'])
    if thread is not None:thread.join()
    job=app.lecturas.consultar(case,job['id'])
    state.update(estado_lectura=job['estado'],lectura_id=job.get('lectura_id'));save()
    assert job['estado']=='aceptado' and job['lectura_verificada'] and job['vigente'], job['estado']
    state.update(estado='informe');save()
    report=app.entregables.crear({'caso':case,'resultado':result,'expediente_sha256':fp,'analisis':analysis,
        'contexto':{'titulo':'QA de integración de estimación independiente de masa',
          'hipotesis':['Validación del recorrido software sobre análisis existente; no nuevo cálculo ETABS.',
            'Se conservan las hipótesis del piloto y el contraste del libro bruto.'],
          'faltantes':['Sin EMS ni aprobación profesional. Este borrador de QA no sustituye el informe técnico con18evaluaciones.'], 'sitio':None},
        'contenido_masa':True,'masa_nativa':{'trabajo':job['id'],'lectura_id':job['lectura_id'],
          'sha256_respuesta':job['sha256_respuesta'],'estimar_auto':True}})
    state['informe']=report['id'];save()
    checked=app.entregables.consultar(case,report['id'],expediente_sha256=fp)
    mass=checked['masa_nativa'];auto=mass['estimacion_auto']
    assert mass['contraste']['estado']=='no_coherente'
    assert auto['estado']=='estimado' and auto['contraste_estimado']['estado']=='coherente'
    assert checked['masa_nativa_seleccionada']['estimar_auto'] is True
    state.update(estado='terminado',bruto=mass['libro']['masa_total_kn_s2_m'],
        estimado=auto['masa_estimada_kn_s2_m'],observado=mass['contraste']['masa_observada_U1'],
        descuento_kn=auto['descuento_peso_kn'],sha_edb_despues=sha(edb))
    assert state['sha_edb_antes']==state['sha_edb_despues']
except Exception as error:
    state.update(estado='fallo',error=str(error));save();raise
state['fin_utc']=datetime.now(timezone.utc).isoformat();save()
print(json.dumps(state,ensure_ascii=False))
