'use strict';
(()=>{
 let source=null,current=null,responseText=null,ticket=0,normalizationKey=null,reading=null,analysisKey=null;
 const declaration=['mapeoRevisor','mapeoFecha','mapeoMotivo','mapeoAlcance'];
 // 293: la etapa no tenía botón de consulta (listaba al cambiar de expediente); se añade uno explícito junto al historial.
 if(!$('mapeoActualizar')){const b=document.createElement('button');b.id='mapeoActualizar';b.type='button';b.disabled=true;b.textContent='Consultar mapeos conservados';$('mapeoGuardar').before(b);}
 function pristine(){return current&&$('mapeoJson').value===JSON.stringify(current.mapeo,null,2);}
 function draft(){return pristine()&&current.mapeo.revision.estado==='borrador';}
 function approved(){return pristine()&&current.mapeo.revision.estado==='aprobado';}
 function approvalReady(){return draft()&&declaration.every(id=>$(id).value.trim()&&$(id).checkValidity())&&$('mapeoConfirmar').checked;}
 window.mappingControls=()=>{
  for(const id of ['mapeoAnalisis','mapeoFuente','mapeoVersion','mapeoActualizar'])$(id).disabled=busy||!docs;
  $('mapeoRespuesta').disabled=busy||!source;$('mapeoJson').disabled=busy||(!source&&!current);
  $('mapeoImportar').disabled=busy||!source||(responseText===null&&!reading);
  $('mapeoGuardar').disabled=busy||!current;
  for(const id of [...declaration,'mapeoConfirmar'])$(id).disabled=busy||!draft();
  $('mapeoAprobar').disabled=busy||!approvalReady();
  $('mapeoNormalizarConfirmar').disabled=busy||!approved();$('mapeoNormalizar').disabled=busy||!approved()||!$('mapeoNormalizarConfirmar').checked;
 };
 function clearRecord(){current=null;normalizationKey=null;$('mapeoHuella').value='';$('mapeoPreview').textContent='';$('mapeoConfirmar').checked=false;$('mapeoNormalizarConfirmar').checked=false;}
 function clear(){ticket++;analysisKey=null;source=null;responseText=null;reading=null;clearRecord();$('mapeoAnalisis').value='';$('mapeoRespuesta').value='';$('mapeoJson').value='';$('mapeoTablas').textContent='';options($('mapeoVersion'),[['','Sin mapeos']]);$('mapeoEstado').textContent='Selecciona o comprueba un análisis aceptado.';window.mappingControls();}
 function fresh(own,caso){return own===ticket&&caso===docs?.caso;}
 function query(extra={}){return new URLSearchParams({caso:docs.caso,expediente_sha256:docs.expediente_sha256,...extra});}
 function base(){if(!current||!docs)throw Error('Abre un mapeo comprobado.');return {caso:docs.caso,version:current.id,expediente_sha256:current.expediente_sha256,huella_mapeo:current.huella_mapeo};}
 function show(record){clearRecord();current=record;source=record.analisis_verificado;responseText=null;$('mapeoRespuesta').value='';$('mapeoAnalisis').value=record.analisis;$('mapeoJson').value=JSON.stringify(record.mapeo,null,2);$('mapeoHuella').value=record.huella_mapeo;$('mapeoPreview').textContent=JSON.stringify(record.previsualizacion,null,2);$('mapeoEstado').textContent='Mapeo '+record.id+' · '+record.mapeo.revision.estado+' · previsualización sin publicación · resultados sin aprobar.';window.mappingControls();}
 async function open(){
  const own=++ticket,caso=docs?.caso,id=$('mapeoVersion').value;source=null;responseText=null;reading=null;clearRecord();$('mapeoJson').value='';$('mapeoTablas').textContent='';window.mappingControls();if(!caso||!id)return;
  try{const res=await api('/api/mapeo?'+query({version:id})),data=await res.json();if(fresh(own,caso)&&$('mapeoVersion').value===id)show(data);}
  catch(error){if(fresh(own,caso)){$('mapeoEstado').textContent=error.message;message(error.message,true);}}
 }
 async function listing(preferred){
  const own=ticket,caso=docs?.caso;if(!caso)return;
  const res=await api('/api/mapeos?'+query()),data=await res.json();if(!fresh(own,caso))return;
  const selected=preferred||$('mapeoVersion').value;
  options($('mapeoVersion'),[['',data.versiones.length?'Selecciona mapeo':'Sin mapeos'],...data.versiones.map(v=>[v.id,v.id+' · '+(v.vigente?v.estado:'sin vigencia')])]);
  if(selected&&data.versiones.some(v=>v.id===selected)){$('mapeoVersion').value=selected;await open();}window.mappingControls();
 }
 async function loadSource(){
  const own=++ticket,caso=docs?.caso,id=$('mapeoAnalisis').value.trim();source=null;responseText=null;reading=null;clearRecord();$('mapeoJson').value='';$('mapeoRespuesta').value='';window.mappingControls();
  if(!caso||!/^[0-9a-f]{32}$/.test(id))throw Error('Selecciona un identificador válido de análisis aceptado.');
  const res=await api('/api/mapeo/fuente?'+query({analisis:id})),data=await res.json();if(!fresh(own,caso)||$('mapeoAnalisis').value.trim()!==id)return;
  source=data;$('mapeoEstado').textContent='Análisis '+id+' comprobado. Selecciona una respuesta conservada y declara sus correspondencias.';window.mappingControls();
 }
 // 293: sin consulta automática al cambiar de expediente; Actualizar consulta y verifica (clear() invalida respuestas previas).
 window.addEventListener('d2m-case',()=>{clear();if(docs)$('mapeoEstado').textContent='Historial sin consultar: seleccionar el expediente no lo comprueba. Pulsa Actualizar para consultarlo y verificarlo.';});
 window.addEventListener('d2m-analysis',event=>{
  const record=event.detail;if(record&&(record.caso!==docs?.caso||record.expediente_sha256!==docs?.expediente_sha256))return;
  const identity=record?JSON.stringify(['caso','expediente_sha256','id','corrida_id','modelo','aprobacion','huella_preparacion','huella_modelo','sha256_aprobacion','estado','vigente','calculo_verificado'].map(k=>record[k]??null)):null;
  if(identity===analysisKey)return;analysisKey=identity;source=null;responseText=null;reading=null;clearRecord();ticket++;
  $('mapeoAnalisis').value='';$('mapeoJson').value='';$('mapeoTablas').textContent='';window.mappingControls();
  if(record?.estado==='aceptado'&&record.vigente===true&&record.calculo_verificado===true&&docs){$('mapeoAnalisis').value=record.corrida_id;const task=loadSource(),own=ticket,caso=docs.caso;task.catch(error=>{if(fresh(own,caso))message(error.message,true);});}
 });
 window.addEventListener('d2m-reading',event=>{
  const record=event.detail;if(!docs||!record?.lectura_verificada||!record.vigente||record.caso!==docs.caso||record.expediente_sha256!==docs.expediente_sha256)return;
  const own=++ticket,caso=docs.caso;source=null;responseText=null;reading=null;clearRecord();$('mapeoJson').value='';$('mapeoAnalisis').value=record.analisis;window.mappingControls();
  (async()=>{
   const res=await api('/api/mapeo/fuente?'+query({analisis:record.analisis})),proof=await res.json();if(!fresh(own,caso))return;
   source=proof;reading=record;const data=record.datos_tablas;
   $('mapeoJson').value=JSON.stringify({contrato:'draft2model.mapeo_resultados_etabs',version:'0.1.0',caso,
    datos_sinteticos:proof.datos_sinteticos,huella_configuracion:proof.configuracion.huella,sha256_respuesta:record.sha256_respuesta,
    modelo:{archivo:'analisis_etabs/'+proof.corrida_id+'/analizado.edb',sha256:proof.sha256_edb_analizado},
    unidades_api_esperadas:data.unidades,version_etabs_esperada:proof.version_etabs,selectores:[],revision:{estado:'borrador',aprobacion:null}},null,2);
   $('mapeoTablas').textContent=JSON.stringify(data.tablas,null,2);$('mapeoEstado').textContent='Lectura comprobada '+record.id+' · '+record.modo_ejecucion+'. Declara selectores y guarda el nuevo borrador; la respuesta se transferirá dentro del servidor.';window.mappingControls();
  })().catch(error=>{if(fresh(own,caso))message(error.message,true);});
 });
 $('mapeoAnalisis').addEventListener('input',()=>{ticket++;source=null;responseText=null;reading=null;clearRecord();$('mapeoJson').value='';$('mapeoTablas').textContent='';window.mappingControls();});
 $('mapeoActualizar').onclick=()=>action(async()=>{const own=ticket,caso=docs?.caso;try{await listing();if(fresh(own,caso)&&$('mapeoEstado').textContent==='Historial sin consultar: seleccionar el expediente no lo comprueba. Pulsa Actualizar para consultarlo y verificarlo.')$('mapeoEstado').textContent='Historial consultado y comprobado. Abrir o usar una versión vuelve a comprobarla.';}catch(error){if(fresh(own,caso))throw error;}});
 $('mapeoFuente').onclick=()=>action(loadSource);$('mapeoVersion').onchange=open;
 $('mapeoRespuesta').onchange=()=>action(async()=>{
  const file=$('mapeoRespuesta').files[0];if(!file||!source)return;if(file.size>1.5*1024*1024)throw Error('Respuesta de hasta 1.5 MiB para esta importación.');
  const own=ticket,caso=docs.caso,proof=source,text=await file.text(),raw=JSON.parse(text);
  const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text));if(!fresh(own,caso)||source!==proof)return;
  const hash=Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join('');
  clearRecord();reading=null;responseText=text;$('mapeoJson').value=JSON.stringify({contrato:'draft2model.mapeo_resultados_etabs',version:'0.1.0',caso,
   datos_sinteticos:proof.datos_sinteticos,huella_configuracion:proof.configuracion.huella,sha256_respuesta:hash,
   modelo:{archivo:'analisis_etabs/'+proof.corrida_id+'/analizado.edb',sha256:proof.sha256_edb_analizado},
   unidades_api_esperadas:raw.datos?.unidades,version_etabs_esperada:proof.version_etabs,selectores:[],revision:{estado:'borrador',aprobacion:null}},null,2);
  $('mapeoTablas').textContent=JSON.stringify((raw.datos?.tablas||[]).map(t=>({tabla:t.clave,campos:t.campos,filas:t.filas})),null,2);
  $('mapeoEstado').textContent='Declara selectores: id, variable, caso, dirección, ubicación, tabla, filtros, campo_valor y unidad_origen. Cero filas produce ausencia; varias filas se rechazan.';window.mappingControls();
 });
 $('mapeoImportar').onclick=()=>action(async()=>{if(!source||(responseText===null&&!reading))return;const own=ticket,caso=docs.caso;const body={caso,expediente_sha256:docs.expediente_sha256,mapeo_json:$('mapeoJson').value};const res=reading?await api('/api/mapeo/importar-lectura',{...body,trabajo_lectura:reading.id}):await api('/api/mapeo/importar',{...body,analisis:source.corrida_id,respuesta_json:responseText});const data=await res.json();if(fresh(own,caso))await listing(data.id);});
 $('mapeoGuardar').onclick=()=>action(async()=>{const own=ticket,caso=docs.caso,mapping=JSON.parse($('mapeoJson').value);mapping.revision={estado:'borrador',aprobacion:null};const res=await api('/api/mapeo/revisar',{...base(),mapeo_json:JSON.stringify(mapping)});const data=await res.json();if(fresh(own,caso))await listing(data.id);});
 for(const id of [...declaration,'mapeoConfirmar','mapeoNormalizarConfirmar'])$(id).addEventListener('input',window.mappingControls);
 $('mapeoJson').addEventListener('input',()=>{$('mapeoConfirmar').checked=false;$('mapeoNormalizarConfirmar').checked=false;window.mappingControls();});
 $('mapeoFecha').value=new Date().toLocaleDateString('sv-SE');
 $('mapeoAprobacionForm').onsubmit=event=>{event.preventDefault();action(async()=>{if(!approvalReady()||!$('mapeoAprobacionForm').reportValidity())return;const own=ticket,caso=docs.caso;const res=await api('/api/mapeo/aprobar',{...base(),revisor:$('mapeoRevisor').value,fecha:$('mapeoFecha').value,motivo:$('mapeoMotivo').value,alcance:$('mapeoAlcance').value,confirmacion_explicita:$('mapeoConfirmar').checked});const data=await res.json();if(fresh(own,caso))await listing(data.id);});};
 $('mapeoNormalizar').onclick=()=>action(async()=>{if(!approved()||!$('mapeoNormalizarConfirmar').checked)throw Error('Confirma el mapeo aprobado y sin cambios antes de normalizar.');const own=ticket,caso=docs.caso;normalizationKey??=crypto.randomUUID().replaceAll('-','');const res=await api('/api/mapeo/normalizar',{...base(),clave_solicitud:normalizationKey,confirmacion_explicita:true});const data=await res.json();if(fresh(own,caso)){$('mapeoNormalizarConfirmar').checked=false;$('mapeoEstado').textContent='Resultado '+data.resultado+' publicado y ligado al análisis · revisión de resultados pendiente.';window.dispatchEvent(new CustomEvent('d2m-result-created',{detail:{caso,resultado:data.resultado}}));window.mappingControls();}});
 clear();
})();
