'use strict';
(()=>{
 const target=window.D2MEtapas?.containers.get('ingenieria');if(!target||!window.D2MEditorIngenieria)return;
 const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
 const panel=el('section');panel.className='geometry';panel.setAttribute('aria-label','Preparación de configuración de ingeniería');
 const title=el('h2','Preparar la configuración del modelo');
 const help=el('p','El programa incorpora la geometría y, cuando existe una lectura vinculada, sus columnas y vigas. Completa y revisa materiales, secciones, cargas y condiciones del análisis aquí. Un dato ausente queda pendiente; no se sustituye por un valor supuesto.');
 const create=el('button','Preparar desde la geometría abierta');create.type='button';
 const history=el('select');history.id='preConfigVersion';const historyLabel=el('label','Configuraciones en preparación');historyLabel.htmlFor=history.id;
 const open=el('button','Abrir preparación');open.type='button';
 const status=el('p','Abre una geometría en la etapa3 para preparar su configuración.');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
 const form=el('form'),textarea=el('textarea');textarea.id='preConfigJson';textarea.disabled=true;
 const label=el('label','Configuración de trabajo');label.htmlFor=textarea.id;
 const save=el('button','Guardar borrador de trabajo');save.type='submit';
 const register=el('button','Validar y registrar configuración');register.type='button';
 const issues=el('ul');issues.setAttribute('aria-label','Datos de ingeniería por completar');
 form.append(label,textarea,save,register);
 const continuity=el('fieldset'),legend=el('legend','Continuidad entre superficies');continuity.append(legend,
  el('p','El programa localiza bordes exteriores que coinciden o se solapan exactamente. Revisa las uniones propuestas y excluye juntas o contactos sin continuidad estructural. La selección no aprueba materiales, cargas ni el modelo completo.'));
 const propose=el('button','Calcular conexiones propuestas');propose.type='button';
 const proposedList=el('div'),limits=el('ul');proposedList.setAttribute('aria-label','Selección de conexiones propuestas');
 const selectAll=el('button','Seleccionar todas las conexiones');selectAll.type='button';
 const clearAll=el('button','Quitar todas las conexiones');clearAll.type='button';
 const review=el('form');review.setAttribute('aria-label','Declarar continuidad revisada');
 const input=(id,text,type)=>{const field=el('input');field.id=id;field.type=type;field.required=true;
  const label=el('label',text);label.htmlFor=id;review.append(label,field);return field;};
 const reviewer=input('preConfigDeclarante','Profesional que revisa','text'),date=input('preConfigFecha','Fecha de revisión','date'),scope=input('preConfigAlcance','Alcance y límites de esta decisión','text');
 const confirmation=input('preConfigConfirma','He revisado las conexiones seleccionadas y las exclusiones','checkbox');
 const declare=el('button','Guardar continuidad revisada');declare.type='submit';review.append(declare);
 continuity.append(propose,limits,selectAll,clearAll,proposedList,review);
 const material=el('fieldset');material.append(el('legend','Material de concreto desde la lectura del plano'),
  el('p','Consulta resistencias y cargas ya detectadas. Para el concreto, el programa calcula E con E.060 8.5.2 y deduce Poisson usando 8.5.4. Declara las condiciones de aplicación y el peso específico; no se infieren desde la resistencia. La lectura conserva su estado de revisión.'));
 const versions=el('select');versions.id='preConfigExtraccion';const versionsLabel=el('label','Lectura de planos conservada');versionsLabel.htmlFor=versions.id;
 const read=el('button','Consultar propiedades y cargas detectadas');read.type='button';
 const readings=el('ul'),fc=el('select');fc.id='preConfigFc';const fcLabel=el('label','Resistencia del concreto detectada');fcLabel.htmlFor=fc.id;
 const materialForm=el('form');materialForm.setAttribute('aria-label','Material desde una lectura');
 const matInput=(id,text,type)=>{const field=el('input');field.id=id;field.type=type;field.required=true;const label=el('label',text);label.htmlFor=id;materialForm.append(label,field);return field;};
 materialForm.append(fcLabel,fc);const matId=matInput('preConfigMatId','Identificador del material','text');matId.value='CONCRETO1';
 const matWeight=matInput('preConfigMatPeso','Peso específico declarado (kN/m³)','number');matWeight.min='0';matWeight.step='any';
 const matCondition=matInput('preConfigMatNormal','Declaro concreto de peso normal y ausencia de ensayos confiables de E o G que sustituyan estas fórmulas','checkbox');
 const matReviewer=matInput('preConfigMatRevisor','Declarante de las condiciones del material','text'),matDate=matInput('preConfigMatFecha','Fecha de declaración del material','date'),matScope=matInput('preConfigMatAlcance','Sustento y alcance de la decisión del material','text');
 const matConfirmation=matInput('preConfigMatConfirma','Confirmo usar esta lectura y estas condiciones en el borrador del material','checkbox');
 const matSave=el('button','Calcular material y guardar borrador');matSave.type='submit';materialForm.append(matSave);
 material.append(versionsLabel,versions,read,readings,materialForm);
 panel.append(title,help,create,historyLabel,history,open,status,issues,form,continuity,material);
 target.querySelector('.stage-guide').after(panel);
 const editor=window.D2MEditorIngenieria.mount('preConfig',window.D2MEditorIngenieria.clavesConfiguracion,'Datos de la configuración en preparación');
 let current=null,epochConfig=0,working=false,proposal=null,checks=[],technicalReadings=null,pendingTechnical=null,materialRefs=new Map(),materialRefExtraction=null;
 const identity=()=>docs?{caso:docs.caso,expediente_sha256:docs.expediente_sha256}:null;
 const same=(own,id)=>own===epochConfig&&id?.caso===docs?.caso&&id.expediente_sha256===docs?.expediente_sha256;
 function controls(){create.disabled=working||!docs||!geoRecord||geoRecord.comprobacion?.correcta!==true;
  save.disabled=working||!current;register.disabled=working||!current||textarea.value!==JSON.stringify(current.datos,null,2);
  textarea.disabled=working||!current;open.disabled=working||!docs;
  const unchanged=current&&textarea.value===JSON.stringify(current.datos,null,2);
  propose.disabled=working||!unchanged;declare.disabled=working||!unchanged||!proposal;
  for(const field of [reviewer,date,scope,confirmation,selectAll,clearAll,...checks])field.disabled=working||!proposal;
  versions.disabled=working||!docs;read.disabled=working||!docs||!versions.value;
  fc.disabled=working||!technicalReadings;matSave.disabled=working||!current||!technicalReadings||!fc.value||textarea.value!==JSON.stringify(current.datos,null,2);}
 function clearProposal(){proposal=null;checks=[];proposedList.replaceChildren();limits.replaceChildren();confirmation.checked=false;}
 function showIssues(validation){issues.replaceChildren();for(const text of validation?.errores||[])issues.append(el('li',text));
  for(const row of validation?.faltantes||[])issues.append(el('li',(row.ruta?row.ruta+': ':'')+row.motivo));}
 function render(value){clearProposal();current=value;textarea.value=JSON.stringify(value.datos,null,2);editor.load();showIssues(value.validacion);
  status.textContent='Borrador de trabajo conservado. '+(value.puede_registrar?'La estructura de datos es consistente; aún requiere revisión de ingeniería.':'Completa los datos indicados antes del registro formal.');controls();
  window.dispatchEvent(new CustomEvent('d2m-preconfig-opened',{detail:JSON.parse(JSON.stringify(value))}));}
 async function listing(own,id){const res=await api('/api/configuracion/preparaciones?'+new URLSearchParams(id)),value=await res.json();if(!same(own,id))return;
  const selected=current?.id;history.replaceChildren();const empty=el('option','Selecciona una preparación');empty.value='';history.append(empty);
  for(const version of value.versiones){const option=el('option',version);option.value=version;history.append(option);}if(selected)history.value=selected;}
 async function action(fn){const own=epochConfig,id=identity();if(!id)return;working=true;controls();
  try{await fn(own,id);}catch(error){if(same(own,id))status.textContent=error.message;}
  finally{if(same(own,id)){working=false;controls();if(pendingTechnical){pendingTechnical=null;readValues();}}}}
 create.addEventListener('click',()=>action(async(own,id)=>{const res=await api('/api/configuracion/preparacion/crear',{...id,geometria:$('geoVersion').value}),value=await res.json();
  if(!same(own,id))return;render(value);await listing(own,id);}));
 open.addEventListener('click',()=>action(async(own,id)=>{if(!history.value)return;const res=await api('/api/configuracion/preparacion?'+new URLSearchParams({...id,version:history.value})),value=await res.json();if(same(own,id))render(value);}));
 form.addEventListener('submit',e=>{e.preventDefault();action(async(own,id)=>{const res=await api('/api/configuracion/preparacion/guardar',{...id,version:current.id,
    sha256_configuracion:current.sha256_configuracion,configuracion_json:textarea.value}),value=await res.json();if(!same(own,id))return;render(value);await listing(own,id);});});
 register.addEventListener('click',()=>action(async(own,id)=>{const res=await api('/api/configuracion/preparacion/registrar',{...id,version:current.id,sha256_configuracion:current.sha256_configuracion}),value=await res.json();
  if(!same(own,id))return;if(value.registrada){status.textContent='Configuración registrada en borrador. Revisa y aprueba su versión antes de utilizarla en ETABS.';
   window.dispatchEvent(new CustomEvent('d2m-config-created',{detail:value}));}else{showIssues(value.validacion);status.textContent='La configuración sigue incompleta. Conserva sus datos en este borrador y resuelve las observaciones.';}}));
 propose.addEventListener('click',()=>action(async(own,id)=>{const res=await api('/api/configuracion/preparacion/conexiones/proponer',
  {...id,version:current.id,sha256_configuracion:current.sha256_configuracion}),value=await res.json();if(!same(own,id))return;
  clearProposal();proposal=value;for(const text of value.limites||[])limits.append(el('li',text));
  for(const row of value.conexiones){const checkbox=el('input');checkbox.type='checkbox';checkbox.value=row.id;checkbox.id='preConfigConexion'+row.id;
   const label=el('label',row.a.superficie+' ('+row.a.desde+'–'+row.a.hasta+') ↔ '+row.b.superficie+' ('+row.b.desde+'–'+row.b.hasta+')');label.htmlFor=checkbox.id;
   const line=el('div');line.append(checkbox,label);proposedList.append(line);checks.push(checkbox);checkbox.addEventListener('change',()=>{confirmation.checked=false;});}
  status.textContent=value.cantidad+' conexiones propuestas. Revisa la selección antes de guardar su continuidad; aún no se ha aplicado ninguna.';}));
 selectAll.addEventListener('click',()=>{checks.forEach(c=>c.checked=true);confirmation.checked=false;});
 clearAll.addEventListener('click',()=>{checks.forEach(c=>c.checked=false);confirmation.checked=false;});
 review.addEventListener('submit',event=>{event.preventDefault();if(!proposal||!confirmation.checked)return;
  action(async(own,id)=>{const selected=checks.filter(c=>c.checked).map(c=>c.value),res=await api('/api/configuracion/preparacion/conexiones/declarar',
   {...id,version:current.id,sha256_configuracion:current.sha256_configuracion,sha256_propuesta:proposal.sha256_propuesta,
    conexiones_seleccionadas:selected,confirmacion_explicita:true,declaracion:{declarado_por:reviewer.value,fecha:date.value,alcance:scope.value}}),value=await res.json();
   if(!same(own,id))return;render(value);status.textContent='Continuidad conservada en una nueva versión de trabajo: '+selected.length+' conexiones. No se aprobó el modelo ni se ejecutó ETABS.';await listing(own,id);});});
 textarea.addEventListener('input',()=>{clearProposal();status.textContent='Cambios preparados sin guardar.';controls();
  if(current)window.dispatchEvent(new CustomEvent('d2m-preconfig-edited',{detail:{...identity(),id:current.id,sin_guardar:true}}));});
 function clearReadings(){technicalReadings=null;readings.replaceChildren();fc.replaceChildren();matConfirmation.checked=false;}
 versions.addEventListener('change',()=>{clearReadings();controls();});
 fc.addEventListener('change',()=>{matConfirmation.checked=false;const matched=versions.value===materialRefExtraction&&materialRefs.get(fc.value);if(matched)matId.value=matched;controls();});
 const readValues=()=>action(async(own,id)=>{const version=versions.value;if(!version)return;const res=await api('/api/configuracion/preparacion/lecturas',{...id,extraccion:version}),value=await res.json();
  if(!same(own,id)||versions.value!==version)return;clearReadings();technicalReadings=value;
  const empty=el('option','Selecciona una resistencia');empty.value='';fc.append(empty);
  for(const row of value.lecturas){readings.append(el('li',row.id+' · '+row.texto+' · '+row.valor+' '+row.unidad+' · '+row.estado_lectura));
   if(row.resistencia_concreto){const option=el('option',row.id+' · '+row.valor+' '+row.unidad+' · '+row.estado_lectura);option.value=row.id;fc.append(option);}}
  status.textContent=value.lecturas.length+' propiedades y cargas detectadas. No se asignaron automáticamente a elementos ni se aprobó su lectura.';});
 read.addEventListener('click',readValues);
 materialForm.addEventListener('submit',event=>{event.preventDefault();if(!technicalReadings||!matConfirmation.checked||!matCondition.checked)return;
  action(async(own,id)=>{const res=await api('/api/configuracion/preparacion/material',{...id,version:current.id,sha256_configuracion:current.sha256_configuracion,
   extraccion:technicalReadings.extraccion,huella_lectura:technicalReadings.huella_lectura,lectura:fc.value,material_id:matId.value,
   peso_kN_m3:Number(matWeight.value),concreto_normal_sin_ensayos:matCondition.checked,confirmacion_explicita:true,
   declaracion:{declarado_por:matReviewer.value,fecha:matDate.value,alcance:matScope.value}}),value=await res.json();if(!same(own,id))return;
   render(value);matConfirmation.checked=false;status.textContent='Material calculado y conservado en un nuevo borrador. No se aprobó la lectura, el modelo ni se ejecutó ETABS.';await listing(own,id);});});
 window.addEventListener('d2m-preconfig-created',event=>{const value=event.detail,id=identity();
  if(!id||value?.caso!==id.caso||value.expediente_sha256!==id.expediente_sha256)return;
  const dirty=current&&textarea.value!==JSON.stringify(current.datos,null,2);
  if(working||dirty||(current&&current.id!==value.preparacion_origen&&current.id!==value.configuracion_preparacion)){
   status.textContent='Hay una nueva preparación conservada. Mantuvimos tus datos abiertos; puedes elegir la versión nueva en el historial.';
   listing(epochConfig,id).catch(error=>{status.textContent=error.message;});return;}
  action(async(own,identity)=>{const res=await api('/api/configuracion/preparacion?'+new URLSearchParams({...identity,version:value.configuracion_preparacion})),record=await res.json();
   if(!same(own,identity))return;render(record);await listing(own,identity);});});
 window.addEventListener('d2m-parameter-readings-created',event=>{const value=event.detail,id=identity();
  if(!id||value?.caso!==id.caso||value.expediente_sha256!==id.expediente_sha256||!value.extraccion)return;
  materialRefs=new Map((value.materiales_para_revision||[]).map(row=>[row.lectura,row.material_id]));materialRefExtraction=value.extraccion;
  if(!Array.from(versions.options).some(option=>option.value===value.extraccion)){const option=el('option','Datos de materiales y secciones · '+value.extraccion.slice(0,8));option.value=value.extraccion;versions.append(option);}
  versions.value=value.extraccion;clearReadings();controls();if(working)pendingTechnical=value.extraccion;else readValues();});
 window.addEventListener('d2m-geometry-opened',()=>{controls();if(working||current||!docs||geoRecord?.comprobacion?.correcta!==true)return;
  action(async(own,id)=>{const geometry=$('geoVersion').value,res=await api('/api/configuracion/preparacion/para-geometria?'+new URLSearchParams({...id,geometria:geometry})),value=await res.json();
   if(!same(own,id)||$('geoVersion').value!==geometry)return;
   if(value.crear){const prepared=await api('/api/configuracion/preparacion/crear',{...id,geometria:geometry}),record=await prepared.json();if(same(own,id))render(record);}
   else if(value.reutilizable){const prepared=await api('/api/configuracion/preparacion?'+new URLSearchParams({...id,version:value.reutilizable})),record=await prepared.json();if(same(own,id))render(record);}
   else status.textContent='Esta geometría tiene varias ramas de preparación. Elige la que corresponde a tu revisión en el historial.';
   if(same(own,id))await listing(own,id);});});
 window.addEventListener('d2m-case',()=>{const own=++epochConfig;current=null;working=false;textarea.value='';clearProposal();reviewer.value='';date.value='';scope.value='';issues.replaceChildren();editor.load();controls();
  clearReadings();pendingTechnical=null;materialRefs=new Map();materialRefExtraction=null;versions.replaceChildren();const empty=el('option','Selecciona una lectura');empty.value='';versions.append(empty);
  for(const version of docs?.versiones||[]){const option=el('option',version);option.value=version;versions.append(option);}
  if(docs?.versiones?.length===1)versions.value=docs.versiones[0];matReviewer.value='';matDate.value='';matScope.value='';matCondition.checked=false;matWeight.value='';controls();
  const id=identity();status.textContent='Abre una geometría de este expediente para preparar su configuración.';
  if(id)listing(own,id).catch(error=>{if(same(own,id))status.textContent=error.message;});});controls();
})();
