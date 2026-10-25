'use strict';
(()=>{
 let selected=null,panel=null,ticket=0,analysisRows=[],analysisCheck=0;
 window.panelControls=()=>{
  for(const id of ['panelAnalisis','panelCrear','panelVersion'])$(id).disabled=busy||!selected;
  $('panelCrear').disabled=busy||!selected||analysisPending();   // 301
  $('panelDescargar').disabled=busy||!selected||!panel;
 };
 function clear(){
  ticket++;analysisCheck++;selected=null;panel=null;analysisRows=[];analysisInfo('');
  options($('panelAnalisis'),[['','Sin evidencia vinculada']]);options($('panelVersion'),[['','Sin paneles']]);
  $('panelEstado').textContent='Abre una versión de resultados comprobada.';window.panelControls();
 }
 function query(extra={}){return new URLSearchParams({caso:selected.caso,resultado:selected.version,expediente_sha256:selected.fingerprint,...extra});}
 function fresh(own){return own===ticket&&selected?.caso===docs?.caso;}
 function showError(error){$('panelEstado').textContent=error.message;message(error.message,true);window.panelControls();}
 // 301: el listado es inventario (vigente:null, verificacion:pendiente; no acredita vínculo). Al seleccionar se comprueba SOLO ese
 // análisis en el servidor; nada dependiente se habilita hasta su respuesta vigente para esta misma selección/caso/resultado.
 // Sin caché: cada selección o actualización vuelve a pendiente y se comprueba de nuevo.
 function pendientes(rows){return rows.map(v=>({id:v.id,vigente:null,verificacion:'pendiente'}));}
 function analysisInfo(text){const info=$('panelAnalisisEstado');if(info)info.textContent=text;}
 async function checkAnalysis(){const id=$('panelAnalisis').value,sel=selected,seq=++analysisCheck;analysisRows=pendientes(analysisRows);
  if(!sel||!/^[0-9a-f]{32}$/.test(id)){analysisInfo(id?'':'Sin evidencia de análisis seleccionada.');return;}
  analysisInfo('Comprobando en el servidor el vínculo del análisis '+id+' con este resultado…');
  const same=()=>selected===sel&&seq===analysisCheck&&$('panelAnalisis').value===id;
  try{const res=await api('/api/analisis/comprobar?'+query({analisis:id})),value=await res.json();if(!same())return;
   if(!value||value.id!==id||value.vigente!==true||value.verificacion!=='completa'||(value.caso!==undefined&&value.caso!==sel.caso)||(value.resultado!==undefined&&value.resultado!==sel.version)||(value.expediente_sha256!==undefined&&value.expediente_sha256!==sel.fingerprint))throw Error('Comprobación de análisis ajena, incompleta o sin vigencia.');
   analysisRows=analysisRows.map(v=>v.id===id?{id,vigente:true,verificacion:'completa',estados:value.estados,casos:value.casos}:v);
   analysisInfo('Análisis '+id+' comprobado en el servidor para este resultado (vínculo y fuentes). Crear o descargar vuelve a validarlo.');
  }catch(error){if(same()){analysisRows=analysisRows.map(v=>v.id===id?{...v,verificacion:'fallida'}:v);analysisInfo('Comprobación fallida: '+error.message);message(error.message,true);}}
 }
 function analysisPending(){const id=$('panelAnalisis').value;return Boolean(id)&&!analysisRows.some(v=>v.id===id&&v.vigente===true);}
 if(!$('panelAnalisisEstado')){const p=document.createElement('p');p.id='panelAnalisisEstado';p.setAttribute('role','status');$('panelAnalisis').after(p);}
 function checkPanel(){return checkAnalysis().finally(()=>window.panelControls());}
 async function openPanel(){
  const own=ticket,id=$('panelVersion').value;panel=null;window.panelControls();if(!selected||!id)return;
  try{
   const res=await api('/api/panel?'+query({version:id})),record=await res.json();
   if(!fresh(own)||$('panelVersion').value!==id)return;
   panel=record;$('panelEstado').textContent='Panel '+record.id+' · '+(record.evidencia_analisis?'cálculo vinculado y comprobado':'sin vínculo de análisis')+' · revisión de resultados pendiente · conformidad no evaluada.';window.panelControls();
  }catch(error){if(fresh(own)&&$('panelVersion').value===id)showError(error);}
 }
 async function lists(own,preferred){
  const responses=await Promise.all([api('/api/analisis?'+query({modo:'inventario'})),api('/api/paneles?'+query())]);
  const [analyses,panels]=await Promise.all(responses.map(r=>r.json()));if(!fresh(own))return;
  const previous=$('panelAnalisis').value;
  if(!Array.isArray(analyses.versiones))throw Error('Inventario de análisis no verificable.');
  analysisRows=pendientes(analyses.versiones);   // 301: nunca se toma vigencia del listado
  options($('panelAnalisis'),[['','Sin evidencia vinculada'],...analysisRows.map(v=>[v.id,v.id+' · sin comprobar (se comprueba al seleccionarlo)'])]);
  if(analysisRows.some(v=>v.id===previous))$('panelAnalisis').value=previous;
  if($('panelAnalisis').value)checkPanel();else analysisInfo('Inventario: '+analysisRows.length+' análisis sin comprobar. Selecciona uno para comprobar su vínculo.');
  options($('panelVersion'),[['',panels.versiones.length?'Selecciona panel':'Sin paneles'],...panels.versiones.map(v=>[v.id,v.id+(v.vigente?' · comprobado':' · sin vigencia')])]);
  if(preferred){$('panelVersion').value=preferred;await openPanel();}window.panelControls();
 }
 window.addEventListener('d2m-case',clear);
 window.addEventListener('d2m-result',event=>{
  clear();if(!event.detail||!docs)return;
  selected={caso:docs.caso,version:event.detail.version,fingerprint:event.detail.record.expediente_sha256};
  const own=ticket;window.panelControls();lists(own).catch(error=>{if(fresh(own))showError(error);});
 });
 $('panelCrear').onclick=()=>action(async()=>{
  if(!selected)return;const own=ticket;
  try{
   if(analysisPending())throw Error('Comprueba el análisis seleccionado antes de crear el panel.');
   const res=await api('/api/panel/crear',{caso:selected.caso,resultado:selected.version,expediente_sha256:selected.fingerprint,analisis:$('panelAnalisis').value||null});
   const created=await res.json();if(fresh(own))await lists(own,created.id);
  }catch(error){if(fresh(own))showError(error);}
 });
 $('panelVersion').onchange=openPanel;
 $('panelAnalisis').addEventListener?.('change',()=>{checkPanel();window.panelControls();});
 $('panelDescargar').onclick=()=>action(async()=>{
  if(!panel||!selected)return;const own=ticket,id=panel.id;
  try{
   const res=await api('/api/panel/archivo?'+query({version:id})),blob=await res.blob();
   if(!fresh(own)||panel?.id!==id)return;
   const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='panel-'+id+'.html';link.click();URL.revokeObjectURL(url);
  }catch(error){if(fresh(own)&&panel?.id===id)showError(error);}
 });
 clear();
})();
