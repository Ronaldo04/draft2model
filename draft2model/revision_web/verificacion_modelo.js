'use strict';
(()=>{
 let selected=null,job=null,ticket=0,key=null;
 const prefix='/api/modelo/verificacion/';
 function canonical(x){return JSON.stringify(x,(_,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])):v);}
 function inputs(){return {criterios:JSON.parse($('vmCriterios').value),ejes_locales_area:$('vmEjes').value.trim()?JSON.parse($('vmEjes').value):null};}
 function matches(r){
  try{return selected&&r&&r.caso===docs?.caso&&r.modelo===selected.modelo&&r.huella_modelo===selected.huella_modelo&&r.expediente_sha256===selected.expediente_sha256&&canonical(r.criterios)===canonical(inputs().criterios)&&canonical(r.ejes_locales_area)===canonical(inputs().ejes_locales_area);}
  catch{return false;}
 }
 function controls(){
  let valid=false;try{valid=!!selected&&!!inputs().criterios;}catch{}
  $('vmPreparar').disabled=busy||!valid;
  $('vmEjecutar').disabled=busy||!matches(job)||!job.vigente||job.estado!=='preparado'||!$('vmConfirmar').checked;
  $('vmConsultar').disabled=busy||!job;
  $('vmHistorial').disabled=busy||!selected;
 }
 window.modelVerificationControls=controls;
 function publish(){window.dispatchEvent(new CustomEvent('d2m-model-verification',{detail:matches(job)&&job.lectura_comprobada===true&&job.vigente===true?job:null}));}
 function consume(){ticket++;key=null;job=null;publish();$('vmConfirmar').checked=false;$('vmHuella').value='';$('vmResultado').textContent='';controls();}
 function current(own){return own===ticket&&selected?.caso===docs?.caso;}
 async function fetchFor(own,url,body){try{const res=await api(url,body);return await res.json();}catch(e){if(current(own))throw e;return null;}}
 function show(r){job=r;publish();$('vmConfirmar').checked=false;$('vmHuella').value=r.huella_preparacion;
  const malla=r.resultado&&r.resultado.malla?' · malla 0.4: cobertura '+(r.resultado.cobertura?.malla||'sin dato')+' · '+Object.entries(r.resultado.malla.hosts||{}).map(([h,x])=>h+' '+(x.area_triangulos_leida_m2===null?'área no leída':x.triangulos_leidos+' triángulos')).join(', '):'';
  $('vmEstado').textContent=r.estado+' · '+r.modo_ejecucion+' · vigente: '+r.vigente+' · lectura comprobada: '+r.lectura_comprobada+malla+' · no aprueba ni autoriza análisis';
  $('vmResultado').textContent=JSON.stringify(r.resultado||{estado:'Sin resultado de lectura',problemas:r.problemas},null,2);controls();}
 window.addEventListener('d2m-case',()=>{selected=null;consume();options($('vmTrabajo'),[['','Selecciona trabajo']]);$('vmEstado').textContent='Selecciona un modelo construido.';});
 window.addEventListener('d2m-model',e=>{selected=e.detail&&docs?{caso:docs.caso,modelo:e.detail.version,expediente_sha256:e.detail.record.expediente_sha256,huella_modelo:e.detail.huella_modelo||e.detail.record.huella_modelo}:null;consume();options($('vmTrabajo'),[['','Selecciona trabajo']]);$('vmEstado').textContent='Declara criterios completos y prepara la lectura.';});
 for(const id of ['vmCriterios','vmEjes'])$(id).addEventListener('input',consume);
 $('vmConfirmar').addEventListener('input',controls);
 $('vmPreparar').onclick=()=>action(async()=>{
  if(!selected)return;inputs();
  key ||= crypto.randomUUID().replaceAll('-','');const own=ticket;
  const r=await fetchFor(own,prefix+'preparar',{...selected,clave_solicitud:key,...inputs()});
  if(r&&current(own))show(r);
 });
 $('vmEjecutar').onclick=()=>action(async()=>{
  if(!matches(job)||!job.vigente||job.estado!=='preparado'||!$('vmConfirmar').checked)return;
  const own=ticket,body={caso:selected.caso,trabajo:job.id,huella_preparacion:job.huella_preparacion,expediente_sha256:selected.expediente_sha256,confirmacion_explicita:true};
  $('vmConfirmar').checked=false;controls();
  const r=await fetchFor(own,prefix+'ejecutar',body);if(r&&current(own))show(r);
 });
 async function consult(id){const own=++ticket;$('vmConfirmar').checked=false;job=null;publish();controls();
  const r=await fetchFor(own,prefix+'estado?'+new URLSearchParams({caso:selected.caso,trabajo:id}));if(r&&current(own))show(r);}
 $('vmConsultar').onclick=()=>action(async()=>{if(selected&&job)await consult(job.id);});
 $('vmTrabajo').onchange=()=>action(async()=>{if(selected&&$('vmTrabajo').value)await consult($('vmTrabajo').value);});
 $('vmHistorial').onclick=()=>action(async()=>{if(!selected)return;const own=ticket;
  const r=await fetchFor(own,prefix+'historial?'+new URLSearchParams({caso:selected.caso}));
  if(r&&current(own)){options($('vmTrabajo'),[['','Selecciona trabajo'],...r.trabajos.filter(x=>x.modelo===selected.modelo&&x.huella_modelo===selected.huella_modelo).map(x=>[x.id,x.id+' · '+x.estado])]);$('vmConfirmar').checked=false;controls();}
 });
 controls();
})();
