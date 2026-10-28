'use strict';
(()=>{
 const target=window.D2MEtapas?.containers.get('lectura')||window.D2MEtapas?.containers.get('geometria');if(!target)return;
 const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
 const panel=el('section');panel.className='geometry ai-reader-card';panel.setAttribute('aria-label','Reconstrucción automática del proyecto');
 const badge=el('span','FASE 2 · LECTURA ESTRUCTURAL CON IA');badge.className='stage-tag';
 const title=el('h2','Lectura e interpretación de planos con IA');
 const intro=el('p','Selecciona el modelo de IA para procesar automáticamente los planos cargados. El sistema identificará cotas, ejes de replanteo, columnas, vigas, placas y niveles para estructurar el modelo del edificio.');
 intro.className='ai-reader-desc';
 const nextStageBtn=el('button','Consolidar Geometría 3D →');nextStageBtn.type='button';nextStageBtn.className='primary btn-next-stage';nextStageBtn.hidden=true;
 nextStageBtn.onclick=()=>{if(window.D2MEtapas)window.D2MEtapas.show('geometria',true);};
 const form=el('form'),provider=el('select'),model=el('input'),tokens=el('input');provider.id='reconProveedor';model.id='reconModelo';tokens.id='reconTokens';
 [['openai','OpenAI'],['gemini','Google Gemini']].forEach(([v,t])=>{const o=el('option',t);o.value=v;provider.append(o);});
 const modelList=el('datalist');modelList.id='reconModelosSugeridos';
 ['gpt-6.1-sol','gpt-6-astra','gpt-4o','gpt-5.4'].forEach(m=>{const o=el('option');o.value=m;modelList.append(o);});
 model.value='gpt-6.1-sol';model.required=true;model.maxLength=128;model.setAttribute('list',modelList.id);
 tokens.type='number';tokens.min=256;tokens.max=65536;tokens.value=49152;tokens.required=true;
 form.append(modelList);
 for(const [name,input]of [['Proveedor para leer los planos',provider],['Identificador exacto del modelo',model],['Límite de salida de esta lectura',tokens]]){const label=el('label',name);label.htmlFor=input.id;form.append(label,input);}
 const quota=el('p'),prepare=el('button','Preparar automáticamente las páginas');prepare.type='submit';
 const confirm=el('input');confirm.type='checkbox';confirm.id='reconConfirmar';
 const confirmLabel=el('label','Autorizo una solicitud de lectura de estos planos al proveedor elegido. No se reintentará automáticamente.');confirmLabel.className='confirmation';confirmLabel.prepend(confirm);
 const run=el('button','Leer planos y generar geometría');run.type='button';
 const status=el('p','Selecciona un expediente para comenzar.');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
 const summary=el('p','');summary.id='reconResumen';summary.hidden=true;
 const list=el('ul'),history=el('select');history.id='reconHistorial';const historyLabel=el('label','Ejecuciones conservadas');historyLabel.htmlFor=history.id;
 const open=el('button','Consultar ejecución seleccionada');open.type='button';
 const recover=el('button','Reevaluar lectura conservada (sin envío API)');recover.type='button';recover.id='reconRecuperar';
 const unitBox=el('div');unitBox.id='reconUnidadBox';unitBox.hidden=true;
 const unitTitle=el('h3','Declarar unidad faltante del plano (revisión de ingeniería)');
 const unitNote=el('p','Úsalo solo cuando el plano omita una nota literal de unidades pero las cotas permitan identificarla. No aprueba la geometría ni consume solicitudes API.');
 const unitSelect=el('select'),unitReviewer=el('input'),unitReason=el('input'),unitApply=el('button','Declarar unidad y reevaluar localmente');
 unitSelect.id='reconUnidadValor';unitReviewer.id='reconUnidadRevisor';unitReason.id='reconUnidadMotivo';unitApply.type='button';unitApply.id='reconAplicarUnidad';
 [['','Selecciona unidad'],['m','Metros (m)'],['cm','Centímetros (cm)'],['mm','Milímetros (mm)']].forEach(([v,t])=>{const o=el('option',t);o.value=v;unitSelect.append(o);});
 unitReviewer.maxLength=120;unitReason.maxLength=500;
 for(const [name,input]of [['Unidad verificada en planos',unitSelect],['Ingeniero revisor',unitReviewer],['Sustento en cotas o niveles',unitReason]]){const l=el('label',name);l.htmlFor=input.id;unitBox.append(l,input);}
 unitBox.prepend(unitTitle,unitNote);unitBox.append(unitApply);
 form.append(quota,prepare,confirmLabel,run);panel.append(badge,title,intro,form,status,summary,list,unitBox,historyLabel,history,open,recover,nextStageBtn);
 target.querySelector('.stage-guide').after(panel);
 let epochRecon=0,current=null,timer=null,running=false,limits=null,key=null;
 const identity=()=>docs?{caso:docs.caso,expediente_sha256:docs.expediente_sha256}:null;
 const same=(own,id)=>own===epochRecon&&id?.caso===docs?.caso&&id.expediente_sha256===docs?.expediente_sha256;
 function controls(){prepare.disabled=running||!docs;run.disabled=running||!current||current.estado!=='preparado'||!confirm.checked||limits?.[provider.value]?.restantes===0;
  const saved=Boolean(current?.tiene_respuesta_conservada)&&current?.estado!=='en_ejecucion';
  recover.disabled=running||!saved;
  unitApply.disabled=running||!saved||!unitSelect.value||!unitReviewer.value.trim()||!unitReason.value.trim();
  for(const c of [provider,model,tokens])c.disabled=running;}
 function quotaText(){const q=limits?.[provider.value];quota.textContent=q?(q.configurada?q.restantes+' de '+q.limite+' solicitudes autorizadas disponibles. '+(q.credencial_configurada?'Credencial local configurada.':'Falta configurar la credencial local.'):'No hay una cuota de envío configurada.'):'Comprobando cuota local…';}
 function render(value){current=value;status.textContent=value.paso;list.replaceChildren();
  prepare.textContent=['preparado','en_ejecucion'].includes(value.estado)?'Preparar automáticamente las páginas':'Preparar otra lectura';
  const r=value.resultado?.resumen_lectura;
  if(r){
   const u=r.unidad_efectiva?(r.unidad_efectiva+(value.resultado?.unidad_declarada_ingenieria?' (declarada por revisión)':' (literal en plano)')):'sin respaldo literal';
   const conflictsCount=(value.resultado?.conflictos||[]).length;
   summary.textContent=`Lectura: ${r.niveles} niveles · ${r.puntos} puntos · ${r.medidas} medidas · ${r.alineaciones} alineaciones · ${r.elementos_validos}/${r.elementos_totales} elementos válidos · ${conflictsCount} conflictos · unidad: ${u}.`;
   summary.hidden=false;
  }else{summary.textContent='';summary.hidden=true;}
  const decl=value.resultado?.unidad_declarada_ingenieria||value.intervenciones?.unidad_revisada;
  const needsUnit=Boolean(value.tiene_respuesta_conservada)&&(Boolean(decl)||r?.unidad_efectiva===null||(value.resultado?.faltantes||[]).some(t=>/unidad/i.test(t)));
  unitBox.hidden=!needsUnit;
  if(decl){unitSelect.value=decl.unidad;unitReviewer.value=decl.revisor;unitReason.value=decl.motivo;}
  for(const text of value.resultado?.faltantes||[])list.append(el('li',text));
  if(value.simulado)list.prepend(el('li','PRUEBA SINTÉTICA: esta ejecución no acredita una lectura real.'));
  nextStageBtn.hidden=!Boolean(value.resultado?.geometria_version);
   if(value.resultado?.geometria_version){window.dispatchEvent(new CustomEvent('d2m-proposed-frames',{detail:{
    geometria:value.resultado.geometria_version,frames:value.resultado.frames_propuestos||[]}}));
   window.dispatchEvent(new CustomEvent('d2m-geometry-created',{detail:{
    caso:value.caso,expediente_sha256:value.expediente_sha256,geometria:value.resultado.geometria_version,estado:'borrador',aprobacion:null}}));}
  controls();
 }
 async function historyList(own,id){
  const res=await api('/api/reconstruccion/historial?'+new URLSearchParams(id)),value=await res.json();if(!same(own,id))return;
  const selected=current?.id;history.replaceChildren();const empty=el('option','Selecciona una ejecución');empty.value='';history.append(empty);
  for(const item of value.trabajos){const o=el('option',item);o.value=item;history.append(o);}if(selected)history.value=selected;
 }
 async function poll(own,id,job){
  clearTimeout(timer);if(!same(own,id))return;
  try{const res=await api('/api/reconstruccion/estado?'+new URLSearchParams({...id,trabajo:job})),value=await res.json();if(!same(own,id))return;
   running=value.estado==='en_ejecucion';render(value);
   if(running)timer=setTimeout(()=>poll(own,id,job),2000);
   else{const q=await api('/api/reconstruccion/cuota');limits=await q.json();if(same(own,id))quotaText();if(typeof message==='function'){if(value.resultado?.geometria_version)message('Lectura estructural completada exitosamente.');else if(value.resultado)message('Lectura completada. Revisa los datos en pantalla.');}}
  }catch(error){if(same(own,id)){running=false;status.textContent=error.message;controls();}}
 }
 form.addEventListener('submit',async e=>{e.preventDefault();const own=epochRecon,id=identity();if(!id)return;
  running=true;controls();status.textContent='Preparando documentos e imágenes localmente; aún no se envía al proveedor.';
  try{if(current&&!['preparado','en_ejecucion'].includes(current.estado))key=null;key=key||crypto.randomUUID().replaceAll('-','');const res=await api('/api/reconstruccion/preparar',{...id,proveedor:provider.value,modelo:model.value.trim(),max_tokens:Number(tokens.value),clave_solicitud:key});
   const value=await res.json();if(!same(own,id))return;running=false;confirm.checked=false;render(value);await historyList(own,id);if(typeof message==='function')message('Páginas preparadas localmente para la lectura con IA.');
  }catch(error){if(same(own,id)){running=false;status.textContent=error.message;controls();}}
 });
 run.addEventListener('click',async()=>{const own=epochRecon,id=identity(),job=current?.id;if(!id||!job||!confirm.checked)return;
  running=true;controls();try{await api('/api/reconstruccion/ejecutar',{...id,trabajo:job,confirmacion_explicita:true});confirm.checked=false;await poll(own,id,job);
  }catch(error){if(same(own,id)){running=false;status.textContent=error.message;controls();}}
 });
 open.addEventListener('click',()=>{const id=identity();if(id&&history.value)poll(epochRecon,id,history.value);});
 async function runRecover(extra){
  const own=epochRecon,id=identity(),job=current?.id;if(!id||!job||!current?.tiene_respuesta_conservada)return;
  running=true;controls();status.textContent='Reevaluando localmente la respuesta conservada (sin llamadas API)…';
  try{const res=await api('/api/reconstruccion/recuperar',{...id,trabajo:job,...extra});const value=await res.json();
   if(!same(own,id))return;running=false;render(value);if(typeof message==='function')message('Lectura reevaluada localmente con éxito.');
  }catch(error){if(same(own,id)){running=false;status.textContent=error.message;controls();}}
 }
 recover.addEventListener('click',()=>runRecover({}));
 unitApply.addEventListener('click',()=>{if(unitSelect.value&&unitReviewer.value.trim()&&unitReason.value.trim())
  runRecover({unidad_revisada:{unidad:unitSelect.value,revisor:unitReviewer.value.trim(),motivo:unitReason.value.trim()}});});
 for(const input of [unitSelect,unitReviewer,unitReason]){input.addEventListener('change',controls);input.addEventListener('input',controls);}
 confirm.addEventListener('change',controls);
 for(const input of [provider,model,tokens])input.addEventListener('change',()=>{current=null;key=null;confirm.checked=false;quotaText();controls();});
 provider.addEventListener('change',()=>{model.value=provider.value==='gemini'?'gemini-3.8-flash':'gpt-6.1-sol';});
 window.addEventListener('d2m-case',async()=>{const own=++epochRecon;clearTimeout(timer);current=null;key=null;running=false;confirm.checked=false;
  summary.textContent='';summary.hidden=true;unitBox.hidden=true;unitSelect.value='';unitReviewer.value='';unitReason.value='';list.replaceChildren();controls();
  const id=identity();status.textContent=id?'Prepara una lectura nueva o consulta una ejecución conservada.':'Selecciona un expediente.';
  if(!id)return;
  try{const res=await api('/api/reconstruccion/cuota');const value=await res.json();if(!same(own,id))return;limits=value;quotaText();await historyList(own,id);}
  catch(error){if(same(own,id))status.textContent=error.message;}
 });controls();
})();
