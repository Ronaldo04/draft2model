'use strict';
(()=>{
 let context=0, resultTicket=0, modelTicket=0, listTicket=0, current=null, invalidResults=new Set();
 window.resultControls=()=>{
  for(const id of ['modeloVersion','resultadoVersion'])$(id).disabled=busy||!docs;
  $('modeloConsultar').disabled=busy||!docs||!$('modeloVersion').value;
  $('resultadoConsultar').disabled=busy||!docs||!$('resultadoVersion').value||invalidResults.has($('resultadoVersion').value);
  $('resultadoDescargar').disabled=busy||!current;
 };
 function resetResult(){
  current=null;$('resultadoFilas').replaceChildren();$('resultadoAvisos').replaceChildren();
  window.dispatchEvent(new CustomEvent('d2m-result',{detail:null}));window.resultControls();
 }
 function clear(){
  context++;resultTicket++;modelTicket++;listTicket++;invalidResults=new Set();resetResult();
  options($('modeloVersion'),[['','Sin modelos']]);options($('resultadoVersion'),[['','Sin resultados']]);
  $('resultadoFilas').replaceChildren();$('resultadoAvisos').replaceChildren();$('modeloDetalle').textContent='';
  window.dispatchEvent(new CustomEvent('d2m-model',{detail:null}));
  for(const id of ['modeloEstado','resultadoEstado'])$(id).textContent=docs?'Selecciona una versión.':'Selecciona un expediente.';
  window.resultControls();
 }
 async function listing(preferredModel,preferredResult){
  const own=context,seq=++listTicket,caso=docs?.caso;if(!caso)return;
  const active=()=>own===context&&seq===listTicket&&docs?.caso===caso;
  async function column(prefix,endpoint,preferred){
   $(prefix+'Estado').textContent='Consultando versiones y comprobando fuentes…';
   if(!$(prefix+'Version').value)options($(prefix+'Version'),[['','Consultando versiones…']]);
   try{
    const response=await api(endpoint+'?'+new URLSearchParams({caso,modo:'inventario'}));   // IDs sin comprobar; abrir comprueba
    const list=await response.json();if(!active())return;
    const rows=list.versiones,previous=$(prefix+'Version').value;
    if(prefix==='resultado')invalidResults=new Set(rows.filter(v=>v.vigente===false).map(v=>v.id));
    options($(prefix+'Version'),[['',rows.length?'Selecciona versión':'Sin versiones'],...rows.map(r=>[r.id,r.id+(r.vigente===true?'':r.vigente===false?' · requiere revisión':' · sin comprobar (se comprueba al abrir)')])]);
    if(rows.some(r=>r.id===previous))$(prefix+'Version').value=previous;
    if(prefix==='resultado'&&previous&&!rows.some(r=>r.id===previous&&r.vigente!==false)){resultTicket++;resetResult();}
    $(prefix+'Estado').textContent=rows.length?rows.length+' versión(es) conservada(s); se comprueban al abrir.':'No hay versiones conservadas en este expediente.';
    window.resultControls();if(!active())return;
    if(preferred){
     const row=rows.find(v=>v.id===preferred);
     $(prefix+'Version').value=row?preferred:'';
     if(row&&row.vigente!==false)await (prefix==='modelo'?openModel():openResult());   // abrir ejecuta la comprobación completa
     else if(prefix==='resultado'){resultTicket++;resetResult();$('resultadoEstado').textContent='El resultado seleccionado no está vigente. Vuelve a comprobar sus fuentes.';}
    }
   }catch(error){
    if(!active())return;
    $(prefix+'Estado').textContent=error.message;
    if(prefix==='resultado'){resultTicket++;resetResult();}
    window.resultControls();message(error.message,true);
   }
  }
  await Promise.all([column('modelo','/api/modelos',preferredModel),column('resultado','/api/resultados',preferredResult)]);
 }

 function query(version){return new URLSearchParams({caso:docs.caso,version,expediente_sha256:docs.expediente_sha256});}
 async function openResult(){
  const own=++resultTicket,caseContext=context,version=$('resultadoVersion').value;
  resetResult();
  if(!docs||!version){$('resultadoEstado').textContent='Selecciona resultados.';return;}
  if(invalidResults.has(version)){$('resultadoEstado').textContent='El resultado seleccionado requiere revisión de sus fuentes.';return;}
  $('resultadoEstado').textContent='Comprobando resultados y fuentes…';
  let record;
  try{const res=await api('/api/resultado?'+query(version));record=await res.json();}
  catch(error){if(own!==resultTicket||caseContext!==context)return;throw error;}
  if(own!==resultTicket||caseContext!==context)return;
  if(record.vigente===false){$('resultadoEstado').textContent='El resultado seleccionado no está vigente.';return;}
  current=record.datos;
  window.dispatchEvent(new CustomEvent('d2m-result',{detail:{record,version}}));
  $('resultadoEstado').textContent=(current.datos_sinteticos?'DATOS SINTÉTICOS · ':'')+'Paquete verificado · motor declarado '+current.motor.nombre+' '+current.motor.version+' · revisión de resultados pendiente · evidencia de cálculo sin vincular en esta consulta.';
  for(const row of current.resultados){
   const tr=document.createElement('tr');
   for(const value of [row.id,row.caso,row.direccion+' / '+row.ubicacion,row.valor===null?'Sin dato: '+row.motivo_omision:String(row.valor),row.unidad]){
    const td=document.createElement('td');td.textContent=value;tr.append(td);
   }
   $('resultadoFilas').append(tr);
  }
  for(const text of [...current.advertencias,...current.omisiones]){const li=document.createElement('li');li.textContent=text;$('resultadoAvisos').append(li);}
  window.resultControls();
 }
 async function openModel(){
  const own=++modelTicket,caseContext=context,version=$('modeloVersion').value;
  window.dispatchEvent(new CustomEvent('d2m-model',{detail:null}));
  $('modeloDetalle').textContent='';if(!docs||!version){$('modeloEstado').textContent='Selecciona un modelo.';return;}
  $('modeloEstado').textContent='Comprobando modelo y fuentes…';
  let record;
  try{const res=await api('/api/modelo?'+query(version));record=await res.json();}
  catch(error){if(own!==modelTicket||caseContext!==context)return;throw error;}
  if(own!==modelTicket||caseContext!==context)return;
  window.dispatchEvent(new CustomEvent('d2m-model',{detail:{record,version}}));
  $('modeloEstado').textContent='Modelo construido comprobado · revisión propia pendiente de consulta · no acredita cálculo ni aprobación de resultados.';
  $('modeloDetalle').textContent=JSON.stringify(record,null,2);window.resultControls();
 }
 function showError(error){$('resultadoEstado').textContent=error.message;message(error.message,true);window.resultControls();}
 window.addEventListener('d2m-case',()=>{clear();const own=context;listing().catch(error=>{if(own===context)showError(error);});});
 window.addEventListener('d2m-model-created',event=>{if(event.detail?.caso!==docs?.caso)return;const own=context;listing(event.detail.modelo).catch(error=>{if(own===context)showError(error);});});
 window.addEventListener('d2m-result-created',event=>{if(event.detail?.caso!==docs?.caso)return;const own=context;listing(null,event.detail.resultado).catch(error=>{if(own===context)showError(error);});});
 $('resultadoVersion').onchange=()=>{openResult().catch(showError);};
 $('modeloVersion').onchange=()=>{openModel().catch(e=>{$('modeloEstado').textContent=e.message;message(e.message,true);});};
 $('resultadoConsultar').onclick=()=>action(openResult);
 $('modeloConsultar').onclick=()=>action(openModel);
 $('resultadoDescargar').onclick=()=>{
  if(!current)return;
  const url=URL.createObjectURL(new Blob([JSON.stringify(current,null,2)],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download='resultados-comprobados.json';link.click();URL.revokeObjectURL(url);
 };
 clear();
})();
