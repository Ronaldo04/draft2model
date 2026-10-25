'use strict';
(()=>{
 let ticket=0,read=0,sourceRead=0,listRead=0,current=null,source=null;
 const same=(own,caso,fp)=>own===ticket&&caso===docs?.caso&&fp===docs?.expediente_sha256;
 const query=extra=>new URLSearchParams({caso:docs.caso,expediente_sha256:docs.expediente_sha256,...extra});
 const pristine=()=>current&&$('conversionManifiesto').value===JSON.stringify(current.manifiesto,null,2);
 window.conversionControls=()=>{
  for(const id of ['conversionExtraccion','conversionVersion','conversionActualizar','conversionManifiesto'])$(id).disabled=busy||!docs;
  $('conversionCrear').disabled=busy||!source||source.version!==$('conversionExtraccion').value||!$('conversionManifiesto').value.trim();
  $('conversionConfirmar').disabled=busy||!pristine();
  $('conversionImportar').disabled=busy||!pristine()||!$('conversionConfirmar').checked;
 };
 function reset(){current=null;$('conversionConfirmar').checked=false;$('conversionDetalle').textContent='';window.conversionControls();}
 function clear(){ticket++;read++;sourceRead++;listRead++;source=null;reset();$('conversionManifiesto').value='';$('conversionLecturas').textContent='';
  options($('conversionExtraccion'),[['','Selecciona extracción revisada'],...(docs?.versiones||[]).map(id=>[id,id])]);
  options($('conversionVersion'),[['','Sin conversión seleccionada']]);$('conversionEstado').textContent='Declara ejes, coordenadas físicas, unidades, espesores y referencias; no se infieren del plano.';window.conversionControls();}
 function error(err){$('conversionEstado').textContent=err.message;message(err.message,true);}
 async function sourceOpen(clearRecord=true){
  const seq=++sourceRead,own=ticket,caso=docs?.caso,fp=docs?.expediente_sha256,id=$('conversionExtraccion').value;
  source=null;if(clearRecord)reset();$('conversionLecturas').textContent='';window.conversionControls();if(!caso||!id)return;
  try{const res=await api('/api/version?'+new URLSearchParams({caso,version:id})),value=await res.json();
   if(!same(own,caso,fp)||sourceRead!==seq||$('conversionExtraccion').value!==id)return;
   if(value.expediente_sha256!==fp)throw Error('La extracción corresponde a otra huella de expediente.');
   source={version:id};$('conversionLecturas').textContent=JSON.stringify(value.datos.candidatos.filter(c=>c.revision?.estado==='revisado'),null,2);window.conversionControls();
  }catch(err){if(same(own,caso,fp)&&sourceRead===seq)error(err);}
 }
 async function open(){
  const seq=++read,own=ticket,caso=docs?.caso,fp=docs?.expediente_sha256,id=$('conversionVersion').value;reset();if(!caso||!id)return;
  try{const res=await api('/api/conversion?'+query({version:id})),value=await res.json();
   if(!same(own,caso,fp)||read!==seq||$('conversionVersion').value!==id)return;
   if(value.caso!==caso||value.expediente_sha256!==fp||value.id!==id||!value.vigente||value.estado!=='borrador'||value.aprobacion!==null)throw Error('Conversión sin vigencia o ajena a la selección.');
   current=value;$('conversionManifiesto').value=JSON.stringify(value.manifiesto,null,2);$('conversionExtraccion').value=value.extraccion;
   $('conversionDetalle').textContent=JSON.stringify({huella_conversion:value.huella_conversion,sha256_geometria:value.sha256_geometria,geometria:value.geometria,trazabilidad:value.trazabilidad},null,2);
   $('conversionEstado').textContent='Conversión '+id+' comprobada · geometría borrador sin aprobación'+(value.geometria.version_contrato==='0.3.0'?' · aberturas explícitas conservadas':'')+'. Importarla requiere otra acción explícita.';
   window.conversionControls();await sourceOpen(false);
  }catch(err){if(same(own,caso,fp)&&read===seq)error(err);}
 }
 async function listing(preferred){
  const seq=++listRead,own=ticket,caso=docs?.caso,fp=docs?.expediente_sha256;if(!caso)return;
  const res=await api('/api/conversiones?'+query({})),value=await res.json();if(!same(own,caso,fp)||listRead!==seq)return;
  const selected=preferred||$('conversionVersion').value;
  options($('conversionVersion'),[['','Selecciona conversión'],...value.versiones.map(v=>[v.id,v.id+(v.vigente?' · borrador':' · sin vigencia')])]);
  const row=value.versiones.find(v=>v.id===selected&&v.vigente);
  if(row){$('conversionVersion').value=selected;if(preferred)await open();}
  else{read++;reset();}window.conversionControls();
 }
 async function act(fn){const own=ticket,caso=docs?.caso,fp=docs?.expediente_sha256;try{await fn(own,caso,fp);}catch(err){if(same(own,caso,fp))error(err);}}
 window.addEventListener('d2m-case',()=>{clear();if(docs)act(()=>listing());});
 $('conversionExtraccion').onchange=()=>{read++;sourceOpen().catch(error);};$('conversionVersion').onchange=open;
 $('conversionActualizar').onclick=()=>action(()=>act(()=>listing()));
 $('conversionManifiesto').addEventListener('input',()=>{read++;$('conversionConfirmar').checked=false;window.conversionControls();});
 $('conversionConfirmar').addEventListener('input',window.conversionControls);
 $('conversionCrear').onclick=()=>action(()=>act(async(own,caso,fp)=>{
  const extraccion=$('conversionExtraccion').value,manifest=$('conversionManifiesto').value;
  if(!source||source.version!==extraccion||!manifest.trim())throw Error('Selecciona una extracción comprobada y declara el manifiesto completo.');
  JSON.parse(manifest);const res=await api('/api/conversion/crear',{caso,extraccion,expediente_sha256:fp,manifiesto_json:manifest}),value=await res.json();
  if(same(own,caso,fp)&&$('conversionExtraccion').value===extraccion&&$('conversionManifiesto').value===manifest)await listing(value.id);
 }));
 $('conversionImportar').onclick=()=>action(()=>act(async(own,caso,fp)=>{
  if(!pristine()||!$('conversionConfirmar').checked)throw Error('Comprueba la conversión sin cambios y confirma importar el borrador.');
  const selected=current;$('conversionConfirmar').checked=false;window.conversionControls();
  const res=await api('/api/conversion/importar-geometria',{caso,version:selected.id,expediente_sha256:fp,huella_conversion:selected.huella_conversion,confirmacion_explicita:true}),value=await res.json();
  if(!same(own,caso,fp)||current!==selected)return;
  if(value.caso!==caso||value.expediente_sha256!==fp||value.estado!=='borrador'||value.aprobacion!==null||value.disponible_para_modelado!==false)throw Error('Importación sin comprobación de borrador.');
  $('conversionEstado').textContent='Geometría '+value.geometria+' importada como borrador, sin aprobación ni disponibilidad para modelado.';
  window.dispatchEvent(new CustomEvent('d2m-geometry-created',{detail:value}));
 }));clear();
})();
