'use strict';
(()=>{
 if(!$('fotoPanel'))return;
 let generation=0,read=0,original=null,opened=null,imageUrl=null;
 const coordinateIds=['fotoX0','fotoY0','fotoX1','fotoY1','fotoX2','fotoY2','fotoX3','fotoY3'];
 const fieldIds=['fotoArchivo','fotoConsultar','fotoRotacion','fotoContraste','fotoPerspectiva','fotoRevisor','fotoMotivo','fotoRegistrar','fotoVersion','fotoCargar','fotoEtiqueta','fotoRecortar','fotoBX0','fotoBY0','fotoBX1','fotoBY1'];
 function snapshot(){return {generation,caso:docs?.caso,fp:docs?.expediente_sha256,archivo:$('fotoArchivo').value};}
 function fresh(s){return s.generation===generation&&s.caso===docs?.caso&&s.fp===docs?.expediente_sha256&&s.archivo===$('fotoArchivo').value;}
 function query(s,extra={}){return new URLSearchParams({caso:s.caso,expediente_sha256:s.fp,...extra});}
 function base(s){return {caso:s.caso,expediente_sha256:s.fp};}
 function clearImage(){if(imageUrl)URL.revokeObjectURL(imageUrl);imageUrl=null;$('fotoPreview').removeAttribute('src');$('fotoPreview').hidden=true;}
 function clearVersion(){read++;opened=null;clearImage();$('fotoDetalle').textContent='';}
 function controls(){
  for(const id of fieldIds)$(id).disabled=busy||!docs;
  for(const id of ['fotoRotacion','fotoContraste','fotoPerspectiva','fotoRevisor','fotoMotivo','fotoRegistrar'])$(id).disabled=busy||!original;
  for(const id of [...coordinateIds,'fotoAncho','fotoAlto']){$(id).disabled=busy||!original||!$('fotoPerspectiva').checked;$(id).required=$('fotoPerspectiva').checked;}
  $('fotoEsquinas').hidden=!$('fotoPerspectiva').checked;
  $('fotoConsultar').disabled=busy||!docs||!$('fotoArchivo').value;
  $('fotoCargar').disabled=busy||!docs||!$('fotoVersion').value;
  $('fotoRecortar').disabled=busy||!opened||opened.id!==$('fotoVersion').value;
 }
 window.preprocessControls=controls;
 function report(err,s){if(fresh(s)){$('fotoEstado').textContent=err.message;message(err.message,true);}}
 function validVersion(value,s){
  if(!value||!/^[a-f0-9]{64}$/.test(value.id)||value.caso!==s.caso||value.expediente_sha256!==s.fp||value.archivo_id!==s.archivo)throw Error('Versión de preprocesamiento de otro original o expediente.');
  return value;
 }
 async function history(s,preferred=''){
  const response=await api('/api/visual/preprocesamientos?'+query(s,{archivo:s.archivo})),data=await response.json();
  if(!fresh(s))return;
  if(data.caso!==s.caso||data.expediente_sha256!==s.fp||data.archivo_id!==s.archivo||!Array.isArray(data.versiones))throw Error('Historial de preprocesamiento incompatible.');
  const current=preferred||$('fotoVersion').value;
  for(const version of data.versiones)validVersion(version,s);
  options($('fotoVersion'),[['','Selecciona derivado verificado'],...data.versiones.map(v=>[v.id,v.id+' · '+v.registro.creado_utc])]);
  if(data.versiones.some(v=>v.id===current))$('fotoVersion').value=current;
  controls();
 }
 async function inspect(){
  generation++;const s=snapshot();original=null;clearVersion();options($('fotoVersion'),[['','Sin selección']]);$('fotoOriginalInfo').textContent='';controls();
  if(!docs||!s.archivo)return;
  try{
   const res=await api('/api/visual/original-raster?'+query(s,{archivo:s.archivo})),data=await res.json();
   if(!fresh(s))return;
   if(data.caso!==s.caso||data.archivo_id!==s.archivo||data.expediente_sha256!==s.fp)throw Error('Metadatos de otro original.');
   original=data;$('fotoOriginalInfo').textContent=JSON.stringify(data,null,2);
   $('fotoEstado').textContent='Esquinas en píxeles del original almacenado, antes de EXIF. Rotación y contraste explícitos; sin metros ni mejora de precisión acreditada.';
   await history(s);if(fresh(s))controls();
  }catch(err){report(err,s);}
 }
 async function openVersion(){
  const s=snapshot(),seq=++read,id=$('fotoVersion').value;opened=null;clearImage();$('fotoDetalle').textContent='';controls();
  if(!docs||!id)return;
  try{
   const res=await api('/api/visual/preprocesamiento?'+query(s,{version:id})),data=await res.json();
   if(!fresh(s)||seq!==read||$('fotoVersion').value!==id)return;
   validVersion(data,s);if(data.id!==id)throw Error('Respuesta de otra versión de preprocesamiento.');
   const img=await api('/api/visual/preprocesado-imagen?'+query(s,{version:id})),blob=await img.blob();
   if(!fresh(s)||seq!==read||$('fotoVersion').value!==id)return;
   opened=data;imageUrl=URL.createObjectURL(blob);$('fotoPreview').src=imageUrl;$('fotoPreview').hidden=false;
   $('fotoDetalle').textContent=JSON.stringify(data,null,2);$('fotoEstado').textContent='Derivado '+id+' verificado. El bbox de recorte se expresa sobre esta imagen; la evidencia vuelve al original.';controls();
  }catch(err){if(seq===read)report(err,s);}
 }
 function number(id,integer=false){const raw=$(id).value.trim(),value=Number(raw);if(!raw||!Number.isFinite(value)||(integer&&!Number.isInteger(value)))throw Error('Completa valores numéricos finitos explícitos.');return value;}
 function config(){return {rotacion_grados:number('fotoRotacion',true),contraste:number('fotoContraste'),
  perspectiva:$('fotoPerspectiva').checked?{esquinas_px:[0,1,2,3].map(i=>[number('fotoX'+i),number('fotoY'+i)]),
    dimensiones_salida_px:[number('fotoAncho',true),number('fotoAlto',true)]}:null};}
 $('fotoTransformarForm').onsubmit=event=>{event.preventDefault();return action(async()=>{
  const s=snapshot();try{
   if(!original||!$('fotoTransformarForm').reportValidity())return;
   const body={...base(s),archivo:s.archivo,config:config(),revisor_declarado:$('fotoRevisor').value.trim(),motivo:$('fotoMotivo').value.trim()};
   if(!body.revisor_declarado||!body.motivo)throw Error('Declara revisor y motivo de la transformación.');
   const res=await api('/api/visual/preprocesar',body),data=await res.json();if(!fresh(s))return;validVersion(data,s);
   await history(s,data.id);if(fresh(s))await openVersion();
  }catch(err){report(err,s);}
 });};
 $('fotoRecorteForm').onsubmit=event=>{event.preventDefault();return action(async()=>{
  const s=snapshot(),version=opened?.id;try{
   if(!opened||version!==$('fotoVersion').value||!$('fotoRecorteForm').reportValidity())return;
   const bbox=['fotoBX0','fotoBY0','fotoBX1','fotoBY1'].map(id=>number(id));
   if(!(0<=bbox[0]&&bbox[0]<bbox[2]&&bbox[2]<=1&&0<=bbox[1]&&bbox[1]<bbox[3]&&bbox[3]<=1))throw Error('El bbox debe tener área positiva dentro del derivado.');
   const body={...base(s),archivo:s.archivo,pagina:1,bbox,dpi:150,etiqueta:$('fotoEtiqueta').value.trim(),preprocesamiento:version};
   if(!body.etiqueta)throw Error('Declara una etiqueta para el recorte.');
   const res=await api('/api/visual/recortar',body),data=await res.json();
   if(!fresh(s)||opened?.id!==version||$('fotoVersion').value!==version)return;
   if(data.caso!==s.caso||data.expediente_sha256!==s.fp||!/^[a-f0-9]{32}$/.test(data.id)||data.preprocesamiento_id!==version)throw Error('Recorte de otra versión u original.');
   window.dispatchEvent(new CustomEvent('d2m-visual-crop',{detail:{...base(s),recorte:data}}));
   $('fotoEstado').textContent='Recorte '+data.id+' conservado sobre el derivado. Selección disponible para el paquete visual local; sin envío.';
  }catch(err){report(err,s);}
 });};
 $('fotoArchivo').onchange=inspect;$('fotoConsultar').onclick=inspect;
 $('fotoVersion').onchange=openVersion;$('fotoCargar').onclick=openVersion;
 $('fotoPerspectiva').onchange=controls;
 window.addEventListener('d2m-case',()=>{
  generation++;original=null;clearVersion();$('fotoOriginalInfo').textContent='';options($('fotoVersion'),[['','Sin selección']]);
  const raster=(docs?.documentos||[]).filter(d=>!d.error&&/\.(?:png|jpe?g)$/i.test(d.nombre||''));
  options($('fotoArchivo'),[['','Selecciona original PNG/JPEG'],...raster.map(d=>[d.id,d.id+' · '+d.nombre])]);
  $('fotoEstado').textContent='Selecciona un original raster y consulta sus dimensiones/orientación antes de declarar cambios.';controls();
 });
 controls();
})();
