'use strict';
(()=>{
 let rows=[],ticket=0,read=0;
 const selected=()=>rows.find(r=>r.clave_solicitud===$('recuperacionOperacion').value);
 window.recoveryControls=()=>{
  for(const id of ['recuperacionActualizar','recuperacionOperacion'])$(id).disabled=busy||!docs;
  for(const id of ['recuperacionResultado','recuperacionConfirmar'])$(id).disabled=busy||!selected();
  $('recuperacionEjecutar').disabled=busy||!selected()||!$('recuperacionResultado').value||!$('recuperacionConfirmar').checked;
 };
 function fresh(own,caso){return ticket===own&&docs?.caso===caso;}
 function choose(){
  $('recuperacionConfirmar').checked=false;const row=selected();
  options($('recuperacionResultado'),[['','Selecciona una acción explícita'],...(row?.resultados_candidatos||[]).map(id=>[id,'Comprobar y aceptar resultado existente '+id]),...(row?.puede_cancelar?[['cancelar','Cancelar intento sin resultado; conservar evidencia']]:[])]);
  $('recuperacionDetalle').textContent=row?JSON.stringify(row,null,2):'';window.recoveryControls();
  if(row?.inventario_previo_conocido===false&&!row.resultados_candidatos.length)$('recuperacionEstado').textContent='Inventario previo desconocido y sin candidato comprobable. Requiere revisar la evidencia conservada; consultar otra vez no resuelve la operación.';
 }
 function clear(){ticket++;read++;rows=[];options($('recuperacionOperacion'),[['','Sin operaciones seleccionadas']]);choose();$('recuperacionEstado').textContent='La consulta no recalcula ni recupera automáticamente.';}
 async function refresh(){
  const own=ticket,seq=++read,caso=docs?.caso;if(!caso)return;
  try{const res=await api('/api/normalizacion/estado?'+new URLSearchParams({caso,expediente_sha256:docs.expediente_sha256})),data=await res.json();if(!fresh(own,caso)||seq!==read)return;
   rows=data.pendientes;options($('recuperacionOperacion'),[['',rows.length?'Selecciona operación pendiente':'Sin operaciones pendientes'],...rows.map(r=>[r.clave_solicitud,r.clave_solicitud+' · mapeo '+r.mapeo_version])]);choose();
   $('recuperacionEstado').textContent=rows.length?'Hay normalizaciones pendientes. Las nuevas publicaciones quedan bloqueadas hasta resolverlas.':'No se encontraron normalizaciones pendientes.';
  }catch(error){if(fresh(own,caso)&&seq===read){$('recuperacionEstado').textContent=error.message;message(error.message,true);}}
 }
 // 293: sin consulta automática al cambiar de expediente; Actualizar consulta y verifica (clear() invalida respuestas previas).
 window.addEventListener('d2m-case',()=>{clear();if(docs)$('recuperacionEstado').textContent='Historial sin consultar: seleccionar el expediente no lo comprueba. Pulsa Actualizar para consultarlo y verificarlo.';});
 $('recuperacionActualizar').onclick=()=>action(refresh);$('recuperacionOperacion').onchange=choose;
 $('recuperacionResultado').addEventListener('input',()=>{$('recuperacionConfirmar').checked=false;window.recoveryControls();});
 $('recuperacionConfirmar').addEventListener('input',window.recoveryControls);
 $('recuperacionEjecutar').onclick=()=>action(async()=>{
  const row=selected(),choice=$('recuperacionResultado').value;if(!docs||!row||!choice||!$('recuperacionConfirmar').checked)throw Error('Selecciona operación, acción y confirmación.');
  const own=ticket,caso=docs.caso;$('recuperacionConfirmar').checked=false;
  try{const res=await api('/api/normalizacion/recuperar',{caso,expediente_sha256:docs.expediente_sha256,clave_solicitud:row.clave_solicitud,resultado:choice==='cancelar'?null:choice,confirmacion_explicita:true}),data=await res.json();if(!fresh(own,caso))return;
   await refresh();if(!fresh(own,caso))return;
   $('recuperacionEstado').textContent=data.cancelada_sin_resultado?'Intento cancelado sin publicar resultados; la evidencia se conserva.':'Resultado existente recuperado y comprobado. Revisión de resultados pendiente.';
   if(data.resultado)window.dispatchEvent(new CustomEvent('d2m-result-created',{detail:{caso,resultado:data.resultado}}));
  }catch(error){if(fresh(own,caso)){$('recuperacionEstado').textContent=error.message;message(error.message,true);}}
 });clear();
})();
