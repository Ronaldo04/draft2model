'use strict';
(()=>{
 let config=null,job=null,ticket=0,read=0,timer=null,requestKey=null,shownModel=null,edits=0,losas=[];
 const inputs=['construccionPlantilla','construccionShell','construccionGravedad','construccionOpciones'];
 const tiposLosa=['shell_losa_homogenea','shell_losa_nervada_v1','shell_losa_casetonada_v1'];
 const shells=[['','Selecciona la formulación'],['ShellThin','Shell delgado · ShellThin'],['ShellThick','Shell grueso · ShellThick'],['Membrane','Membrana · Membrane']];
 const funciones=[['','Declara la función'],['piso','Piso'],['fondo_deposito','Fondo de depósito'],['tapa_deposito','Tapa de depósito'],['otra','Otra']];
 function hasWalls(){return config?.datos?.secciones?.some(s=>s.tipo==='shell_muro')===true;}
 function changed(){edits++;requestKey=null;$('construccionConfirmar').checked=false;window.constructionControls();}
 function renderLosas(){
  losas=[];$('construccionLosas').replaceChildren();
  for(const sec of config?.datos?.secciones||[]){
   if(!tiposLosa.includes(sec.tipo))continue;
   const index=losas.length,group=node('fieldset'),legend=node('legend','Sección '+sec.id+' · '+sec.tipo),fields={seccion:sec.id};group.append(legend);
   for(const [key,title,rows] of [['funcion','Función estructural',funciones],['tipo','Formulación',shells],['justificacion','Justificación de la elección',null]]){
    const control=node(rows?'select':'textarea'),label=node('label',title);control.id='construccionLosa'+index+'_'+key;label.htmlFor=control.id;control.required=true;
    if(rows)options(control,rows);else control.rows=2;
    control.addEventListener('input',changed);fields[key]=control;group.append(label,control);
   }
   losas.push(fields);$('construccionLosas').append(group);
  }
  $('construccionLosasInfo').textContent=losas.length?'Declara función, formulación y justificación para cada sección, incluidas las aligeradas. La orientación no determina su función. Membrane no admite la presión normal de fondos o tapas de depósito.':'La configuración no declara secciones de losa.';
 }
 function opcionesLosas(){
  const entries=losas.map(row=>{
   const tipo=row.tipo.value,funcion=row.funcion.value,justificacion=row.justificacion.value.trim();
   if(!shells.some(([v])=>v&&v===tipo)||!funciones.some(([v])=>v&&v===funcion)||!justificacion)throw Error('Completa función, formulación y justificación de la losa '+row.seccion+'.');
   if(tipo==='Membrane'&&['fondo_deposito','tapa_deposito'].includes(funcion))throw Error('La losa '+row.seccion+': un fondo o tapa de depósito requiere ShellThin o ShellThick para resistir presión normal.');
   return [row.seccion,{tipo,funcion,justificacion}];
  });
  return entries.length?{tipo_shell_losa:Object.fromEntries(entries)}:{};
 }
 function approved(){return config?.comprobacion?.apto_para_adaptador===true&&config?.datos?.revision?.estado==='aprobado';}
 function executable(){return job?.estado==='preparado'&&job.vigente&&approved()&&job.configuracion_version===config.id&&job.expediente_sha256===docs?.expediente_sha256;}
 window.constructionControls=()=>{
  for(const id of [...inputs,'construccionPreparar'])$(id).disabled=busy||!approved();
  $('construccionMuros').hidden=!hasWalls();$('construccionShell').required=hasWalls();$('construccionShell').disabled=busy||!approved()||!hasWalls();
  for(const row of losas)for(const key of ['tipo','funcion','justificacion'])row[key].disabled=busy||!approved();
  for(const id of ['construccionVersion','construccionActualizar'])$(id).disabled=busy||!docs;
  $('construccionConfirmar').disabled=busy||!executable();
  $('construccionEjecutar').disabled=busy||!executable()||!$('construccionConfirmar').checked;
 };
 function stop(){if(timer!==null)clearTimeout(timer);timer=null;}
 function resetJob(){read++;stop();job=null;$('construccionConfirmar').checked=false;$('construccionDetalle').textContent='';window.constructionControls();}
 function fresh(own,caso){return own===ticket&&docs?.caso===caso;}
 function clear(){ticket++;edits++;config=null;requestKey=null;shownModel=null;resetJob();$('construccionForm').reset();renderLosas();options($('construccionVersion'),[['','Sin trabajos']]);$('construccionConfig').textContent='Abre una configuración aprobada y comprobada.';$('construccionEstado').textContent=docs?'Selecciona o prepara un trabajo.':'Selecciona un expediente.';window.constructionControls();}
 function showError(error){$('construccionEstado').textContent=error.message;message(error.message,true);}
 function show(record){
  job=record;$('construccionConfirmar').checked=false;$('construccionDetalle').textContent=JSON.stringify(record,null,2);
  $('construccionEstado').textContent='Trabajo '+record.id+' · '+record.estado+(record.vigente?' · entradas vigentes':' · entradas sin vigencia')+(record.modelo_id?' · modelo '+record.modelo_id:'')+' · análisis y revisión propia pendientes.';
  window.constructionControls();
  if(record.estado==='aceptado'&&record.vigente&&record.modelo_id&&shownModel!==record.modelo_id){shownModel=record.modelo_id;window.dispatchEvent(new CustomEvent('d2m-model-created',{detail:{caso:docs.caso,modelo:record.modelo_id}}));}
 }
 async function listing(preferred){
  const own=ticket,caso=docs?.caso,seq=read,revision=edits;if(!caso)return;
  const res=await api('/api/construccion/trabajos?'+new URLSearchParams({caso})),data=await res.json();if(!fresh(own,caso)||seq!==read||revision!==edits)return;
  const selected=preferred||$('construccionVersion').value;
  options($('construccionVersion'),[['',data.trabajos.length?'Selecciona trabajo':'Sin trabajos'],...data.trabajos.map(v=>[v.id,v.id+' · '+v.estado])]);
  if(selected&&data.trabajos.some(v=>v.id===selected)){$('construccionVersion').value=selected;await open();}
 }
 async function open(){
  const own=ticket,caso=docs?.caso,id=$('construccionVersion').value;resetJob();const seq=read;if(!caso||!id)return;
  try{
   const res=await api('/api/construccion/trabajo?'+new URLSearchParams({caso,trabajo:id})),data=await res.json();
   if(!fresh(own,caso)||read!==seq||$('construccionVersion').value!==id)return;
   show(data);
   if(data.estado==='en_ejecucion')timer=setTimeout(()=>{timer=null;open();},4000);
  }catch(error){if(fresh(own,caso)&&read===seq&&$('construccionVersion').value===id)showError(error);}
 }
 // 293: sin consulta automática al cambiar de expediente; Actualizar consulta y verifica (clear() invalida respuestas previas).
 window.addEventListener('d2m-case',()=>{clear();if(docs)$('construccionEstado').textContent='Historial sin consultar: seleccionar el expediente no lo comprueba. Pulsa Actualizar para consultarlo y verificarlo.';});
 window.addEventListener('d2m-config',event=>{
  config=event.detail;resetJob();renderLosas();changed();
  $('construccionConfig').textContent=approved()?'Configuración '+config.id+' comprobada y aprobada.':'Abre una configuración aprobada y comprobada.';
  window.constructionControls();
 });
 for(const id of inputs)$(id).addEventListener('input',changed);
 $('construccionConfirmar').addEventListener('input',window.constructionControls);
 $('construccionForm').onsubmit=event=>{event.preventDefault();action(async()=>{
  if(!approved()||!docs||!$('construccionForm').reportValidity())return;
  const own=ticket,caso=docs.caso,selectedConfig=config,revision=edits,seq=read,extra=JSON.parse($('construccionOpciones').value);
  if(extra&&Object.hasOwn(extra,'tipo_shell_losa'))throw Error('Declara tipo_shell_losa en los controles por sección; retíralo del JSON para evitar dos elecciones distintas.');
  const allowed=['parametros_modales','amortiguamiento_funciones','excentricidad_espectral','respuesta_rigida_espectral'];
  if(!extra||Array.isArray(extra)||typeof extra!=='object'||Object.keys(extra).some(k=>!allowed.includes(k)))throw Error('Las opciones adicionales deben contener solo parámetros modales o espectrales permitidos.');
  const shellMuro=$('construccionShell').value;
  if(hasWalls()&&!shells.some(([v])=>v&&v===shellMuro))throw Error('Selecciona la formulación de los muros.');
  const losasOpciones=opcionesLosas();
  const gravedad=Number($('construccionGravedad').value);if(!Number.isFinite(gravedad)||gravedad<=0)throw Error('Declara una gravedad positiva y finita.');
  requestKey??=crypto.randomUUID().replaceAll('-','');
  try{
  const res=await api('/api/construccion/preparar',{caso,configuracion_version:config.id,expediente_sha256:docs.expediente_sha256,
   plantilla_relativa:$('construccionPlantilla').value.trim(),clave_solicitud:requestKey,
   opciones:{...extra,...losasOpciones,...(hasWalls()?{tipo_shell_muro:shellMuro}:{}),gravedad_programa_m_s2:gravedad}});
  const created=await res.json();if(fresh(own,caso)&&config===selectedConfig&&edits===revision&&read===seq)await listing(created.id);
  }catch(error){if(fresh(own,caso)&&config===selectedConfig&&edits===revision&&read===seq)throw error;}
 });};
 $('construccionEjecutar').onclick=()=>action(async()=>{
  if(!executable()||!$('construccionConfirmar').checked)throw Error('Selecciona un trabajo vigente y confirma explícitamente su ejecución.');
  const own=ticket,caso=docs.caso,selected=job,selectedConfig=config,seq=read,revision=edits;$('construccionConfirmar').checked=false;
  try{
  const res=await api('/api/construccion/ejecutar',{caso,trabajo:selected.id,huella_preparacion:selected.huella_preparacion,
   expediente_sha256:selected.expediente_sha256,confirmacion_explicita:true});
  const data=await res.json();if(fresh(own,caso)&&config===selectedConfig&&read===seq&&edits===revision&&$('construccionVersion').value===selected.id){show(data);await open();}
  }catch(error){if(fresh(own,caso)&&config===selectedConfig&&read===seq&&edits===revision&&$('construccionVersion').value===selected.id)throw error;}
 });
 $('construccionVersion').onchange=open;
 $('construccionActualizar').onclick=()=>action(async()=>{const own=ticket,caso=docs?.caso;try{await listing();if(fresh(own,caso)&&$('construccionEstado').textContent==='Historial sin consultar: seleccionar el expediente no lo comprueba. Pulsa Actualizar para consultarlo y verificarlo.')$('construccionEstado').textContent='Historial consultado y comprobado. Abrir o usar una versión vuelve a comprobarla.';}catch(error){if(fresh(own,caso))throw error;}});
 clear();
})();
