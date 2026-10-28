'use strict';
(()=>{
 let job=null,ticket=0,read=0,timer=null,key=null,analysisKey=null,massPublished=false;
 const massOptIn=()=>$('lecturaMasaApi');
 const autoOptIn=()=>$('lecturaConfigAuto');
 const requestedAuto=record=>Array.isArray(record?.resultados_api)&&record.resultados_api.includes('ConfiguracionAuto');
 const requestedMass=record=>Array.isArray(record?.resultados_api)&&record.resultados_api.includes('AssembledJointMass');
 function publishMass(record){
  const allowed=record?.estado==='aceptado'&&record.lectura_verificada===true&&record.vigente===true&&record.caso===docs?.caso&&record.expediente_sha256===docs?.expediente_sha256&&record.analisis===$('lecturaAnalisis').value.trim()&&requestedMass(record);
  if(!allowed&&!massPublished)return;
  massPublished=Boolean(allowed);
  const detail=allowed?Object.fromEntries(['caso','expediente_sha256','analisis','lectura_id','sha256_respuesta','sha256_edb','modo_ejecucion','datos_sinteticos'].map(k=>[k,record[k]]).concat([['trabajo',record.id]],requestedAuto(record)?[['configuracion_auto_disponible',true]]:[])):null;
  window.dispatchEvent(new CustomEvent('d2m-mass-reading',{detail}));
 }
 const lines=id=>$(id).value.split(/\r?\n/).map(v=>v.trim()).filter(Boolean);
 function selected(){return docs&&/^[0-9a-f]{32}$/.test($('lecturaAnalisis').value.trim())&&lines('lecturaTablas').length&&lines('lecturaCasos').length;}
 function executable(){return selected()&&job?.estado==='preparado'&&job.vigente&&job.caso===docs.caso&&job.expediente_sha256===docs.expediente_sha256&&job.analisis===$('lecturaAnalisis').value.trim()&&JSON.stringify(job.tablas)===JSON.stringify(lines('lecturaTablas'))&&JSON.stringify(job.casos)===JSON.stringify(lines('lecturaCasos'))&&requestedMass(job)===(massOptIn()?.checked===true)&&requestedAuto(job)===(autoOptIn()?.checked===true);}
 window.readingControls=()=>{
  for(const id of ['lecturaAnalisis','lecturaTablas','lecturaCasos','lecturaVersion','lecturaActualizar'])$(id).disabled=busy||!docs;
  if(massOptIn())massOptIn().disabled=busy||!docs;
  if(autoOptIn()){if(!massOptIn()?.checked)autoOptIn().checked=false;autoOptIn().disabled=busy||!docs||!massOptIn()?.checked;}
  $('lecturaPreparar').disabled=busy||!selected();$('lecturaConfirmar').disabled=busy||!executable();
  $('lecturaEjecutar').disabled=busy||!executable()||!$('lecturaConfirmar').checked;
  $('lecturaMapear').disabled=busy||job?.estado!=='aceptado'||!job?.lectura_verificada||!job.vigente||job.caso!==docs?.caso||job.expediente_sha256!==docs?.expediente_sha256;
 };
 function reset(){publishMass(null);read++;if(timer!==null)clearTimeout(timer);timer=null;job=null;$('lecturaConfirmar').checked=false;$('lecturaDetalle').textContent='';window.readingControls();}
 function fresh(own,caso){return own===ticket&&caso===docs?.caso;}
 function clear(){ticket++;key=null;analysisKey=null;reset();if(massOptIn())massOptIn().checked=false;$('lecturaAnalisis').value='';$('lecturaCasos').value='';options($('lecturaVersion'),[['','Sin lecturas']]);$('lecturaEstado').textContent='Selecciona un análisis aceptado y las tablas y casos que se leerán.';window.readingControls();}
 function show(record){job=record;publishMass(record);$('lecturaConfirmar').checked=false;$('lecturaDetalle').textContent=JSON.stringify(record,null,2);$('lecturaEstado').textContent='Lectura '+record.id+' · '+record.estado+(record.lectura_verificada?' · lectura comprobada':'')+' · '+record.modo_ejecucion+' · resultados sin normalizar ni aprobar.';window.readingControls();}
 function error(err){$('lecturaEstado').textContent=err.message;message(err.message,true);}
 async function open(){
  const own=ticket,caso=docs?.caso,id=$('lecturaVersion').value;reset();const seq=read;if(!caso||!id)return;
  try{const res=await api('/api/lectura/trabajo?'+new URLSearchParams({caso,trabajo:id})),data=await res.json();
   if(!fresh(own,caso)||read!==seq||$('lecturaVersion').value!==id)return;
   show(data);if(data.estado==='en_ejecucion')timer=setTimeout(()=>{timer=null;open();},4000);
  }catch(err){if(fresh(own,caso)&&read===seq)error(err);}
 }
 async function listing(preferred){
  const own=ticket,caso=docs?.caso;if(!caso)return;
  const res=await api('/api/lectura/trabajos?'+new URLSearchParams({caso})),data=await res.json();if(!fresh(own,caso))return;
  const id=preferred||$('lecturaVersion').value;
  options($('lecturaVersion'),[['',data.trabajos.length?'Selecciona lectura':'Sin lecturas'],...data.trabajos.map(v=>[v.id,v.id+' · '+v.estado])]);
  if(id&&data.trabajos.some(v=>v.id===id)){$('lecturaVersion').value=id;await open();}window.readingControls();
 }
 // 293: sin consulta automática al cambiar de expediente; Actualizar consulta y verifica (clear() invalida respuestas previas).
 window.addEventListener('d2m-case',()=>{clear();if(docs)$('lecturaEstado').textContent='Historial sin consultar: seleccionar el expediente no lo comprueba. Pulsa Actualizar para consultarlo y verificarlo.';});
 window.addEventListener('d2m-analysis',event=>{
  const record=event.detail;if(record&&(record.caso!==docs?.caso||record.expediente_sha256!==docs?.expediente_sha256))return;
  const identity=record?JSON.stringify(['caso','expediente_sha256','id','corrida_id','modelo','aprobacion','huella_preparacion','huella_modelo','sha256_aprobacion','estado','vigente','calculo_verificado'].map(k=>record[k]??null)):null;
  if(identity===analysisKey)return;analysisKey=identity;ticket++;key=null;reset();if(massOptIn())massOptIn().checked=false;
  $('lecturaAnalisis').value=record?.estado==='aceptado'&&record.vigente===true&&record.calculo_verificado===true?record.corrida_id:'';
  $('lecturaCasos').value='';window.readingControls();
 });
 for(const id of ['lecturaAnalisis','lecturaTablas','lecturaCasos'])$(id).addEventListener('input',()=>{ticket++;read++;publishMass(null);key=null;$('lecturaConfirmar').checked=false;window.readingControls();});
 massOptIn()?.addEventListener?.('input',()=>{ticket++;read++;publishMass(null);key=null;$('lecturaConfirmar').checked=false;window.readingControls();});
 autoOptIn()?.addEventListener?.('input',()=>{ticket++;read++;publishMass(null);key=null;$('lecturaConfirmar').checked=false;window.readingControls();});
 $('lecturaConfirmar').addEventListener('input',window.readingControls);
 $('lecturaPreparar').onclick=()=>action(async()=>{
  if(!selected())throw Error('Indica análisis, tablas y casos explícitos.');const own=ticket,caso=docs.caso;key??=crypto.randomUUID().replaceAll('-','');
  try{
   const res=await api('/api/lectura/preparar',{caso,analisis:$('lecturaAnalisis').value.trim(),tablas:lines('lecturaTablas'),casos:lines('lecturaCasos'),expediente_sha256:docs.expediente_sha256,clave_solicitud:key,...(massOptIn()?.checked===true?{resultados_api:['AssembledJointMass',...(autoOptIn()?.checked?['ConfiguracionAuto']:[])]}:{})});
   const created=await res.json();if(fresh(own,caso))await listing(created.id);
  }catch(err){if(fresh(own,caso))error(err);}
 });
 $('lecturaEjecutar').onclick=()=>action(async()=>{
  if(!executable()||!$('lecturaConfirmar').checked)throw Error('Comprueba la selección preparada y confirma la lectura.');
  const own=ticket,caso=docs.caso,current=job;$('lecturaConfirmar').checked=false;
  try{
   const res=await api('/api/lectura/ejecutar',{caso,trabajo:current.id,huella_preparacion:current.huella_preparacion,expediente_sha256:current.expediente_sha256,confirmacion_explicita:true});
   const data=await res.json();if(fresh(own,caso)&&$('lecturaVersion').value===current.id){show(data);await open();}
  }catch(err){if(fresh(own,caso)&&$('lecturaVersion').value===current.id)error(err);}
 });
 $('lecturaMapear').onclick=()=>{if(job?.estado!=='aceptado'||!job.lectura_verificada||!job.vigente||job.caso!==docs?.caso||job.expediente_sha256!==docs?.expediente_sha256)return;window.dispatchEvent(new CustomEvent('d2m-reading',{detail:job}));};
 $('lecturaVersion').onchange=open;$('lecturaActualizar').onclick=()=>action(async()=>{const own=ticket,caso=docs?.caso;try{await listing();if(fresh(own,caso)&&$('lecturaEstado').textContent==='Historial sin consultar: seleccionar el expediente no lo comprueba. Pulsa Actualizar para consultarlo y verificarlo.')$('lecturaEstado').textContent='Historial consultado y comprobado. Abrir o usar una versión vuelve a comprobarla.';}catch(err){if(fresh(own,caso))error(err);}});clear();
})();
