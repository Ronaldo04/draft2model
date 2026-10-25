'use strict';
(()=>{
 let ticket=0,read=0,imageUrl=null,packet=null;
 const fields=['visualRevision','visualArchivo','visualPagina','visualX0','visualY0','visualX1','visualY1','visualDpi','visualEtiqueta','visualRecortes','visualPaquete'];
 window.visualControls=()=>{
  for(const id of [...fields,'visualRevisar','visualRecortar','visualActualizar','visualMostrar'])$(id).disabled=busy||!docs;
  $('visualPreparar').disabled=busy||!docs||!$('visualRevision').value||!Array.from($('visualRecortes').selectedOptions).length;
 };
 function fresh(own,caso){return own===ticket&&caso===docs?.caso;}
 function query(extra={}){return new URLSearchParams({caso:docs.caso,expediente_sha256:docs.expediente_sha256,...extra});}
 function base(){return {caso:docs.caso,expediente_sha256:docs.expediente_sha256};}
 function clearImage(){if(imageUrl)URL.revokeObjectURL(imageUrl);imageUrl=null;$('visualImagen').removeAttribute('src');$('visualImagen').hidden=true;}
 function showPacket(value){packet=value;$('visualDetalle').textContent=value?JSON.stringify(value,null,2):'';window.dispatchEvent(new CustomEvent('d2m-visual-package',{detail:value}));}
 function clear(){ticket++;read++;clearImage();showPacket(null);for(const id of ['visualRevision','visualArchivo','visualRecortes','visualPaquete'])options($(id),[['','Sin selección']]);$('visualEstado').textContent='Selecciona un expediente para preparar sus evidencias.';window.visualControls();}
 function error(err){$('visualEstado').textContent=err.message;message(err.message,true);}
 async function listing(preferred={}){
  const own=ticket,caso=docs?.caso;if(!caso)return;
  const res=await api('/api/visual/historial?'+query()),data=await res.json();if(!fresh(own,caso))return;
  const revision=preferred.revision||$('visualRevision').value,crops=preferred.recorte?[preferred.recorte]:Array.from($('visualRecortes').selectedOptions).map(v=>v.value),version=preferred.paquete||$('visualPaquete').value;
  options($('visualRevision'),[['','Selecciona revisión documental'],...data.revisiones.map(v=>[v.id,v.id+(v.vigente?' · '+v.datos.resumen.paginas_renderizadas+' página(s) preparada(s)':' · sin vigencia')])]);
  if(data.revisiones.some(v=>v.id===revision&&v.vigente))$('visualRevision').value=revision;
  options($('visualRecortes'),data.recortes.map(v=>[v.id,v.vigente?v.datos.archivo_id+' · pág. '+v.datos.pagina+' · '+v.datos.etiqueta+' · '+v.id:v.id+' · sin vigencia']));
  for(const option of $('visualRecortes').options){option.disabled=!data.recortes.find(v=>v.id===option.value)?.vigente;option.selected=crops.includes(option.value)&&!option.disabled;}
  options($('visualPaquete'),[['','Selecciona paquete local'],...data.paquetes.map(v=>[v.id,v.id+(v.vigente?' · sin envío':' · sin vigencia')])]);
  for(const option of $('visualRevision').options)if(option.value)option.disabled=!data.revisiones.find(v=>v.id===option.value)?.vigente;
  if(data.paquetes.some(v=>v.id===version&&v.vigente)){$('visualPaquete').value=version;await openPacket();}else showPacket(null);
  window.visualControls();
 }
 async function openPacket(){
  const seq=++read,own=ticket,caso=docs?.caso,id=$('visualPaquete').value;showPacket(null);if(!caso||!id)return;
  try{const res=await api('/api/visual/paquete?'+query({version:id})),value=await res.json();
   if(fresh(own,caso)&&read===seq&&$('visualPaquete').value===id){showPacket(value);$('visualEstado').textContent='Paquete '+value.id+' comprobado · '+value.imagenes.length+' imágenes · sin envío a proveedor · revisión de ingeniería pendiente.';}
  }catch(err){if(fresh(own,caso)&&read===seq)error(err);}
 }
 async function act(fn){const own=ticket,caso=docs?.caso;try{await fn(own,caso);}catch(err){if(fresh(own,caso))error(err);}}
 window.addEventListener('d2m-case',()=>{
  clear();if(!docs)return;options($('visualArchivo'),[['','Selecciona original'],...docs.documentos.map(d=>[d.id,d.id+' · '+d.nombre])]);
  act(()=>listing());window.visualControls();
 });
 window.addEventListener('d2m-visual-crop',event=>{
  const value=event.detail,crop=value?.recorte;
  if(!docs||value?.caso!==docs.caso||value.expediente_sha256!==docs.expediente_sha256||
      crop?.caso!==docs.caso||crop.expediente_sha256!==docs.expediente_sha256||
      !/^[a-f0-9]{32}$/.test(crop.id||''))return;
  const own=ticket,caso=docs.caso,fp=docs.expediente_sha256;
  act(async()=>{await listing();if(!fresh(own,caso)||docs.expediente_sha256!==fp)return;
   for(const option of $('visualRecortes').options)if(option.value===crop.id&&!option.disabled)option.selected=true;
   window.visualControls();
  });
 });
 $('visualRevisar').onclick=()=>action(()=>act(async(own,caso)=>{if(!docs)return;const res=await api('/api/visual/revisar',base()),value=await res.json();if(fresh(own,caso)){await listing({revision:value.id});if(!fresh(own,caso))return;$('visualEstado').textContent='Revisión documental conservada · '+value.resumen.archivos_con_error+' archivo(s) con error · legibilidad pendiente de revisión humana.';}}));
 $('visualRecorteForm').onsubmit=event=>{event.preventDefault();action(()=>act(async(own,caso)=>{
  if(!docs||!$('visualRecorteForm').reportValidity())return;
  const body={...base(),archivo:$('visualArchivo').value,pagina:Number($('visualPagina').value),bbox:['visualX0','visualY0','visualX1','visualY1'].map(id=>Number($(id).value)),dpi:Number($('visualDpi').value),etiqueta:$('visualEtiqueta').value.trim()};
  const res=await api('/api/visual/recortar',body),value=await res.json();if(!fresh(own,caso))return;
  const image=await api('/api/visual/imagen?'+query({version:value.id})),blob=await image.blob();if(!fresh(own,caso))return;
  clearImage();imageUrl=URL.createObjectURL(blob);$('visualImagen').src=imageUrl;$('visualImagen').hidden=false;
  await listing({recorte:value.id});if(fresh(own,caso))$('visualEstado').textContent='Recorte '+value.id+' conservado · sin escala métrica · revisa la imagen y selecciona los recortes del paquete.';
 }));};
 $('visualMostrar').onclick=()=>action(()=>act(async()=>{
  const id=$('visualArchivo').value;if(!docs||!id)return;$('documento').value=id;await changeDocument();$('pagina').value=$('visualPagina').value;await openPage();
 }));
 $('visualPreparar').onclick=()=>action(()=>act(async(own,caso)=>{
  if(!docs)return;const recortes=Array.from($('visualRecortes').selectedOptions).map(v=>v.value);
  if(!$('visualRevision').value||!recortes.length)throw Error('Selecciona revisión documental y al menos un recorte.');
  const res=await api('/api/visual/preparar',{...base(),revision:$('visualRevision').value,recortes}),value=await res.json();if(fresh(own,caso))await listing({paquete:value.id});
 }));
 $('visualActualizar').onclick=()=>action(()=>act(()=>listing()));$('visualPaquete').onchange=openPacket;
 for(const id of ['visualRevision','visualRecortes'])$(id).addEventListener('change',window.visualControls);
 clear();
})();
