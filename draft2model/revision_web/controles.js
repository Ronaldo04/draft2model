'use strict';
(()=>{
 // Controles postsolver: lectura aceptada exacta + criterios DECLARADOS; sin tolerancias por defecto ni selección automática.
 let ticket=0,listSeq=0,readSeq=0,openSeq=0,current=null,lecturas=[];
 const same=(own,caso,fp)=>own===ticket&&caso===docs?.caso&&fp===docs?.expediente_sha256;
 const query=extra=>new URLSearchParams({caso:docs.caso,expediente_sha256:docs.expediente_sha256,...extra});
 const decl=['ctlRevisor','ctlFecha','ctlAlcance','ctlControles'];
 function ready(){return docs&&lecturas.some(l=>l.id===$('ctlLectura').value)&&decl.every(id=>$(id).value.trim()&&$(id).checkValidity());}
 window.controlsReviewControls=()=>{
  for(const id of ['ctlLectura','ctlVersion','ctlActualizar',...decl,'ctlAvisos'])$(id).disabled=busy||!docs;
  $('ctlConfirmar').disabled=busy||!ready();$('ctlRegistrar').disabled=busy||!ready()||!$('ctlConfirmar').checked;
 };
 function publish(value){window.dispatchEvent(new CustomEvent('d2m-controls-review',{detail:value}));}
 function clearRecord(){openSeq++;if(current)publish(null);current=null;$('ctlTabla').replaceChildren();$('ctlListas').replaceChildren();$('ctlDetalle').textContent='';}
 function clear(){ticket++;listSeq++;readSeq++;lecturas=[];clearRecord();$('ctlConfirmar').checked=false;
  options($('ctlLectura'),[['','Selecciona lectura aceptada']]);options($('ctlVersion'),[['','Sin controles seleccionados']]);
  $('ctlEstado').textContent=docs?'Selecciona una lectura aceptada y declara criterios explícitos. CSI 4 solo indica terminación del motor.':'Selecciona un expediente.';window.controlsReviewControls();}
 function error(err){$('ctlEstado').textContent=err.message;message(err.message,true);}
 function cell(tr,text){const td=node('td',text===null||text===undefined?'—':String(text));tr.append(td);}
 function render(item){
  const c=item.contenido,table=node('table');const head=node('tr');
  for(const h of ['Control','Tipo / caso','Estado','Base de datos','Fórmula y criterio','Valores (unidad)','Motivos'])head.append(node('th',h));table.append(head);
  const declared=Object.fromEntries(c.declaracion.controles.map(d=>[d.id,d]));
  for(const r of c.controles){const tr=node('tr');cell(tr,r.id+(declared[r.id]?.critico?' (crítico)':''));cell(tr,r.tipo+' / '+(r.caso??'toda la corrida'));
   cell(tr,r.estado);cell(tr,r.base_datos+' · '+r.verificacion);cell(tr,(r.formula||'no aplica')+' · criterio: '+(declared[r.id]?.fuente_criterio||''));
   cell(tr,r.valores===null?null:JSON.stringify(r.valores));cell(tr,r.motivos.join(' | '));table.append(tr);}
  $('ctlTabla').replaceChildren(table);
  const lists=[['Faltantes críticos',c.faltantes_criticos],['Controles solo declarados (no verificados)',c.controles_solo_declarados],
   ['Críticos declarados no aplicables',c.criticos_no_aplicables],['Avisos del LECTOR (no son el log del solver)',c.avisos_lector],
   ['Advertencias del solver declaradas',c.advertencias_solver===null?['Sin fuente solver aportada']:c.advertencias_solver.map(w=>(w.caso??'corrida')+' · '+w.codigo+' · '+w.texto)]];
  $('ctlListas').replaceChildren(...lists.flatMap(([t,v])=>[node('h3',t),v.length?(()=>{const ul=node('ul');for(const x of v)ul.append(node('li',String(x)));return ul;})():node('p','Ninguno.','empty')]));
  $('ctlDetalle').textContent=JSON.stringify({sha256_controles:item.sha256_controles,lectura:item.lectura,analisis:item.analisis,modelo:item.modelo,
   fuentes:c.fuentes,huellas_tablas:c.huellas_tablas,estado_casos_declarado:c.estado_casos_declarado,declaracion:{revisor:c.declaracion.revisor_declarado,fecha:c.declaracion.fecha,alcance:c.declaracion.alcance}},null,2);
  $('ctlEstado').textContent='Controles '+item.id+' · estado global '+c.estado_global+' · '+(c.apto_proyeccion_controlado?'apto para proyectar «controlado» según criterios DECLARADOS':'NO apto para proyectar «controlado»')
   +(item.datos_sinteticos?' · DATOS SINTÉTICOS fabricados':'')+' · '+item.estado_motor+' · sin aprobación de resultados ni conformidad normativa.';
 }
 async function lecturasList(){
  const seq=++readSeq,own=ticket,caso=docs?.caso,fp=docs?.expediente_sha256;if(!caso)return;
  const res=await api('/api/lectura/trabajos?'+new URLSearchParams({caso})),value=await res.json();if(!same(own,caso,fp)||readSeq!==seq)return;
  lecturas=value.trabajos.filter(t=>t.estado==='aceptado'&&t.vigente===true&&t.lectura_verificada===true&&t.expediente_sha256===fp);
  options($('ctlLectura'),[['',lecturas.length?'Selecciona lectura aceptada':'Sin lecturas aceptadas vigentes'],...lecturas.map(t=>[t.id,t.id+' · análisis '+t.analisis+' · casos '+t.casos.join(',')])]);
  window.controlsReviewControls();
 }
 async function open(){
  const id=$('ctlVersion').value,seq=++openSeq,own=ticket,caso=docs?.caso,fp=docs?.expediente_sha256;if(current)publish(null);current=null;
  $('ctlTabla').replaceChildren();$('ctlListas').replaceChildren();$('ctlDetalle').textContent='';if(!caso||!id)return;
  const res=await api('/api/controles/version?'+query({version:id})),item=await res.json();
  if(!same(own,caso,fp)||openSeq!==seq||$('ctlVersion').value!==id)return;
  if(item.id!==id||item.caso!==caso||item.expediente_sha256!==fp||item.vigente!==true||item.aprueba_resultados!==false||item.conformidad_normativa!=='no_evaluada')throw Error('Controles sin vigencia o ajenos.');
  current=item;render(item);
  publish({caso,expediente_sha256:fp,id:item.id,sha256_controles:item.sha256_controles,analisis:item.analisis,
   estado_global:item.contenido.estado_global,apto_proyeccion_controlado:item.contenido.apto_proyeccion_controlado});
 }
 async function listing(preferred){
  const seq=++listSeq,own=ticket,caso=docs?.caso,fp=docs?.expediente_sha256;if(!caso)return;
  const res=await api('/api/controles/historial?'+query({})),value=await res.json();if(!same(own,caso,fp)||listSeq!==seq)return;
  options($('ctlVersion'),[['',value.versiones.length?'Selecciona controles':'Sin controles registrados'],
   ...value.versiones.map(v=>[v.id,v.id+(v.vigente?' · '+v.estado_global+(v.apto_proyeccion_controlado?' · apto':' · no apto'):' · sin vigencia')])]);
  if(preferred&&value.versiones.some(v=>v.id===preferred&&v.vigente)){$('ctlVersion').value=preferred;await open();}
  window.controlsReviewControls();
 }
 async function act(fn){const own=ticket,caso=docs?.caso,fp=docs?.expediente_sha256;try{await fn(own,caso,fp);}catch(err){if(same(own,caso,fp))error(err);}}
 // 293: sin consulta automática al cambiar de expediente; Actualizar consulta y verifica (clear() invalida respuestas previas).
 window.addEventListener('d2m-case',()=>{clear();if(docs)$('ctlEstado').textContent='Historial sin consultar: seleccionar el expediente no lo comprueba. Pulsa Actualizar para consultarlo y verificarlo.';});
 $('ctlLectura').onchange=()=>{$('ctlConfirmar').checked=false;window.controlsReviewControls();};
 for(const id of [...decl,'ctlAvisos'])$(id).addEventListener('input',()=>{$('ctlConfirmar').checked=false;window.controlsReviewControls();});
 $('ctlConfirmar').addEventListener('input',window.controlsReviewControls);
 $('ctlVersion').onchange=()=>act(()=>open());$('ctlActualizar').onclick=()=>action(()=>act(async(own,caso,fp)=>{await lecturasList();await listing();if(same(own,caso,fp)&&$('ctlEstado').textContent==='Historial sin consultar: seleccionar el expediente no lo comprueba. Pulsa Actualizar para consultarlo y verificarlo.')$('ctlEstado').textContent='Historial consultado y comprobado. Abrir o usar una versión vuelve a comprobarla.';}));
 $('ctlFecha').value=new Date().toLocaleDateString('sv-SE');
 $('ctlRegistrar').onclick=()=>action(()=>act(async(own,caso,fp)=>{
  if(!ready()||!$('ctlConfirmar').checked)throw Error('Selecciona lectura, declara criterios y confirma.');
  const lectura=lecturas.find(l=>l.id===$('ctlLectura').value);let controles;
  try{controles=JSON.parse($('ctlControles').value);}catch{throw Error('Los controles declarados deben ser JSON válido.');}
  const avisos=$('ctlAvisos').value.trim();if(avisos){try{JSON.parse(avisos);}catch{throw Error('La fuente solver declarada debe ser JSON válido o quedar vacía.');}}
  $('ctlConfirmar').checked=false;window.controlsReviewControls();
  const body={caso,expediente_sha256:fp,lectura:lectura.id,sha256_respuesta:lectura.sha256_respuesta,avisos_solver_json:avisos||null,
   revisor_declarado:$('ctlRevisor').value.trim(),fecha:$('ctlFecha').value,alcance:$('ctlAlcance').value.trim(),controles,confirmacion_explicita:true};
  const res=await api('/api/controles/crear',body),item=await res.json();if(!same(own,caso,fp))return;
  if(item.lectura!==lectura.id||item.aprueba_resultados!==false)throw Error('Registro de controles sin comprobación.');
  await listing(item.id);
 }));clear();
})();
