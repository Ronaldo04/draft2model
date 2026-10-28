'use strict';
(()=>{
 let model=null,job=null,ticket=0,read=0,timer=null,requestKey=null,published=null,publishedKey;
 function publish(record){
  const key=record?JSON.stringify(['caso','expediente_sha256','id','corrida_id','modelo','aprobacion','huella_preparacion','huella_modelo','sha256_aprobacion','estado','vigente','calculo_verificado'].map(k=>record[k]??null)):'null';
  if(key===publishedKey)return;published=record;publishedKey=key;
  window.dispatchEvent(new CustomEvent('d2m-analysis',{detail:record}));
 }
 const approval=()=>$('analisisAprobacion').value;
 function selected(){return model&&model.caso===docs?.caso&&model.aprobaciones.some(a=>a.id===approval());}
 function executable(){return selected()&&job?.estado==='preparado'&&job.vigente&&job.modelo===model.modelo&&job.aprobacion===approval()&&job.expediente_sha256===docs.expediente_sha256;}
 window.analysisControls=()=>{
  $('analisisAprobacion').disabled=busy||!model;
  $('analisisPreparar').disabled=busy||!selected();
  for(const id of ['analisisVersion','analisisActualizar'])$(id).disabled=busy||!docs;
  $('analisisConfirmar').disabled=busy||!executable();$('analisisEjecutar').disabled=busy||!executable()||!$('analisisConfirmar').checked;
 };
 function resetJob(){read++;if(timer!==null)clearTimeout(timer);timer=null;job=null;$('analisisConfirmar').checked=false;$('analisisDetalle').textContent='';window.analysisControls();}
 function fresh(own,caso){return own===ticket&&caso===docs?.caso;}
 function clear(){ticket++;model=null;requestKey=null;resetJob();publish(null);options($('analisisAprobacion'),[['','Selecciona aprobación']]);options($('analisisVersion'),[['','Sin trabajos']]);$('analisisModelo').textContent='Abre un modelo y consulta su revisión propia.';$('analisisEstado').textContent=docs?'Selecciona o prepara un trabajo.':'Selecciona un expediente.';window.analysisControls();}
 function show(record){job=record;$('analisisConfirmar').checked=false;$('analisisDetalle').textContent=JSON.stringify(record,null,2);$('analisisEstado').textContent='Trabajo '+record.id+' · '+record.estado+(record.vigente?' · fuentes vigentes':' · fuentes sin vigencia')+(record.calculo_verificado?' · cálculo verificado':'')+' · resultados sin normalizar ni revisar.';window.analysisControls();publish(record);}
 function showError(error){$('analisisEstado').textContent=error.message;message(error.message,true);}
 async function open(){
  const own=ticket,caso=docs?.caso,id=$('analisisVersion').value;
  if(!published||published.id!==id||published.caso!==caso||published.expediente_sha256!==docs?.expediente_sha256)publish(null);
  resetJob();const seq=read;if(!caso||!id)return;
  try{const res=await api('/api/analisis/trabajo?'+new URLSearchParams({caso,trabajo:id})),data=await res.json();
   if(!fresh(own,caso)||read!==seq||$('analisisVersion').value!==id)return;
   show(data);if(data.estado==='en_ejecucion')timer=setTimeout(()=>{timer=null;open();},4000);
  }catch(error){if(fresh(own,caso)&&read===seq&&$('analisisVersion').value===id)showError(error);}
 }
 async function listing(preferred){
  const own=ticket,caso=docs?.caso;if(!caso)return;
  const res=await api('/api/analisis/trabajos?'+new URLSearchParams({caso})),data=await res.json();if(!fresh(own,caso))return;
  const id=preferred||$('analisisVersion').value;
  options($('analisisVersion'),[['',data.trabajos.length?'Selecciona trabajo':'Sin trabajos'],...data.trabajos.map(v=>[v.id,v.id+' · '+v.estado])]);
  if(id&&data.trabajos.some(v=>v.id===id)){$('analisisVersion').value=id;await open();}else{resetJob();publish(null);}window.analysisControls();
 }
 // 293: sin consulta automática al cambiar de expediente; Actualizar consulta y verifica (clear() invalida respuestas previas).
 window.addEventListener('d2m-case',()=>{clear();if(docs)$('analisisEstado').textContent='Historial sin consultar: seleccionar el expediente no lo comprueba. Pulsa Actualizar para consultarlo y verificarlo.';});
 window.addEventListener('d2m-model-review',event=>{
  model=event.detail;requestKey=null;$('analisisConfirmar').checked=false;
  options($('analisisAprobacion'),[['','Selecciona aprobación'],...(model?.aprobaciones||[]).map(a=>[a.id,a.id+' · '+a.fecha+' · '+a.revisor_declarado])]);
  $('analisisModelo').textContent=model?'Modelo '+model.modelo+' · '+model.aprobaciones.length+' aprobación(es) comprobada(s).':'Abre un modelo y consulta su revisión propia.';
  window.analysisControls();
 });
 $('analisisAprobacion').onchange=()=>{requestKey=null;$('analisisConfirmar').checked=false;window.analysisControls();};
 $('analisisConfirmar').addEventListener('input',window.analysisControls);
 $('analisisPreparar').onclick=()=>action(async()=>{
  if(!selected())throw Error('Selecciona una aprobación propia vigente del modelo.');
  const own=ticket,caso=docs.caso;requestKey??=crypto.randomUUID().replaceAll('-','');
  const res=await api('/api/analisis/preparar',{caso,modelo:model.modelo,aprobacion:approval(),expediente_sha256:docs.expediente_sha256,clave_solicitud:requestKey});
  const created=await res.json();if(fresh(own,caso)){await listing(created.id);message('Preparación de análisis estructural registrada: '+created.id,false);}
 });
 $('analisisEjecutar').onclick=()=>action(async()=>{
  if(!executable()||!$('analisisConfirmar').checked)throw Error('Comprueba modelo, aprobación y trabajo y confirma la ejecución.');
  const own=ticket,caso=docs.caso,current=job;$('analisisConfirmar').checked=false;
  const res=await api('/api/analisis/ejecutar',{caso,trabajo:current.id,huella_preparacion:current.huella_preparacion,expediente_sha256:current.expediente_sha256,confirmacion_explicita:true});
  const data=await res.json();if(fresh(own,caso)&&$('analisisVersion').value===current.id){show(data);await open();message('Análisis estructural ejecutado con éxito.',false);}
 });
 $('analisisVersion').onchange=open;$('analisisActualizar').onclick=()=>action(async()=>{const own=ticket,caso=docs?.caso;try{await listing();if(fresh(own,caso)&&$('analisisEstado').textContent==='Historial sin consultar: seleccionar el expediente no lo comprueba. Pulsa Actualizar para consultarlo y verificarlo.')$('analisisEstado').textContent='Historial consultado y comprobado. Abrir o usar una versión vuelve a comprobarla.';}catch(error){if(fresh(own,caso))throw error;}});clear();
})();
