'use strict';
(()=>{
 let selected=null,review=null,ticket=0;
 const controls={modeloControlGeometria:'geometria_conectividad',modeloControlMateriales:'materiales_secciones',modeloControlCargas:'cargas_masa',modeloControlApoyos:'apoyos_diafragmas',modeloControlCasos:'casos_combinaciones'};
 const fields=['modeloRevisor','modeloFecha','modeloAlcance'];
 function ready(){return review&&fields.every(id=>$(id).value.trim()&&$(id).checkValidity())&&Object.keys(controls).every(id=>$(id).checked)&&$('modeloRevisionConfirmar').checked;}
 window.modelReviewControls=()=>{
  for(const id of [...fields,...Object.keys(controls),'modeloRevisionConfirmar'])$(id).disabled=busy||!review;
  $('modeloAprobar').disabled=busy||!ready();
 };
 function unchecked(){for(const id of [...Object.keys(controls),'modeloRevisionConfirmar'])$(id).checked=false;}
 function clear(){ticket++;selected=null;review=null;unchecked();$('modeloRevisionHuella').value='';$('modeloAprobaciones').textContent='';$('modeloRevisionEstado').textContent='Abre y comprueba un modelo construido.';window.modelReviewControls();window.dispatchEvent(new CustomEvent('d2m-model-review',{detail:null}));}
 function fresh(own){return own===ticket&&selected?.caso===docs?.caso;}
 function show(data){
  review=data;unchecked();$('modeloRevisionHuella').value=data.huella_modelo;$('modeloAprobaciones').textContent=JSON.stringify(data.aprobaciones,null,2);
  $('modeloRevisionEstado').textContent='Revisión propia '+data.estado+' · '+data.aprobaciones.length+' aprobación(es) comprobada(s) · análisis separado · resultados sin aprobar.';
  window.modelReviewControls();window.dispatchEvent(new CustomEvent('d2m-model-review',{detail:data}));
 }
 window.addEventListener('d2m-case',clear);
 window.addEventListener('d2m-model',async event=>{
  clear();if(!event.detail||!docs)return;
  selected={caso:docs.caso,modelo:event.detail.version,fingerprint:event.detail.record.expediente_sha256};const own=ticket;
  try{const res=await api('/api/modelo/revision?'+new URLSearchParams({caso:selected.caso,modelo:selected.modelo,expediente_sha256:selected.fingerprint}));const data=await res.json();if(fresh(own))show(data);}
  catch(error){if(fresh(own)){$('modeloRevisionEstado').textContent=error.message;message(error.message,true);}}
 });
 for(const id of [...fields,...Object.keys(controls),'modeloRevisionConfirmar'])$(id).addEventListener('input',window.modelReviewControls);
 $('modeloFecha').value=new Date().toLocaleDateString('sv-SE');
 $('modeloRevisionForm').onsubmit=event=>{event.preventDefault();action(async()=>{
  if(!selected||!ready()||!$('modeloRevisionForm').reportValidity())return;
  const own=ticket,res=await api('/api/modelo/aprobar',{caso:selected.caso,modelo:selected.modelo,expediente_sha256:selected.fingerprint,
   huella_modelo:review.huella_modelo,revisor:$('modeloRevisor').value.trim(),fecha:$('modeloFecha').value,alcance:$('modeloAlcance').value.trim(),
   controles:Object.fromEntries(Object.entries(controls).map(([id,key])=>[key,$(id).checked])),confirmacion_explicita:$('modeloRevisionConfirmar').checked});
  const data=await res.json();if(fresh(own))show(data);
 });};
 clear();
})();
