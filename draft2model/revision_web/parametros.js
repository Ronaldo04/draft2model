'use strict';
(()=>{
 const target=window.D2MEtapas?.containers.get('ingenieria');if(!target)return;
 const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
 const panel=el('section');panel.className='geometry';panel.setAttribute('aria-label','Lectura dirigida de ingeniería');
 panel.append(el('h2','Leer cuadros de materiales, secciones y cargas'),el('p','El programa lee estos datos y sus asignaciones desde los planos originales y conserva una preparación nueva. Los datos incompletos siguen pendientes. No reconstruye otra geometría, no supone apoyos ni ejecuta ETABS. Puedes reaplicar una lectura conservada después de completar condiciones de ingeniería, sin volver al proveedor.'));
 const form=el('form');form.setAttribute('aria-label','Preparar lectura de ingeniería');
 const field=(id,text,type)=>{const n=el(type==='select'?'select':'input');n.id=id;if(type!=='select')n.type=type;const label=el('label',text);label.htmlFor=id;form.append(label,n);return n;};
 const provider=field('parProveedor','Proveedor de visión','select');for(const [id,name] of [['openai','OpenAI'],['gemini','Google Gemini']]){const o=el('option',name);o.value=id;provider.append(o);}
 const model=field('parModelo','Identificador exacto del modelo','text');model.value='gpt-6.1-sol';model.required=true;
 const tokens=field('parTokens','Límite de salida de esta lectura','number');tokens.min='256';tokens.max='65536';tokens.value='16384';tokens.required=true;
 const prepare=el('button','Preparar lectura de cuadros');prepare.type='submit';form.append(prepare);
 const quota=el('p','La cuota se comparte con las demás lecturas de planos.');
 const consent=el('input');consent.type='checkbox';consent.id='parConfirmar';const consentLabel=el('label','Autorizo una solicitud de lectura de estos planos al proveedor. No se reintentará automáticamente.');consentLabel.htmlFor=consent.id;
 const run=el('button','Leer cuadros e incorporar datos');run.type='button';
 const status=el('p','Abre o genera una preparación de ingeniería para continuar.');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
 const history=el('select');history.id='parHistorial';const historyLabel=el('label','Lecturas de ingeniería conservadas');historyLabel.htmlFor=history.id;
 const open=el('button','Consultar lectura de ingeniería');open.type='button';
 const recover=el('button','Reevaluar respuesta conservada sin API');recover.type='button';
 const apply=el('button','Actualizar preparación abierta con estos datos sin API');apply.type='button';
 const summary=el('p'),details=el('details'),detailTitle=el('summary','Materiales, secciones y cargas detectados'),rows=el('ul'),issues=el('ul');details.append(detailTitle,rows);
 issues.setAttribute('aria-label','Datos de ingeniería aún pendientes');
 panel.append(form,quota,consent,consentLabel,run,status,historyLabel,history,open,recover,apply,summary,details,issues);
 const preparation=target.querySelector('[aria-label="Preparación de configuración de ingeniería"]');if(preparation)preparation.querySelector('p').after(panel);else target.append(panel);
 let generation=0,preconfig=null,dirty=false,current=null,busy=false,running=false,timer=null,limits=null,lastPublished='',lastExtraction='',polling=0,requestKey=null;
 const identity=()=>docs?{caso:docs.caso,expediente_sha256:docs.expediente_sha256}:null;
 const same=(own,id)=>own===generation&&id?.caso===docs?.caso&&id.expediente_sha256===docs?.expediente_sha256;
 const linked=()=>preconfig?.caso===docs?.caso&&preconfig?.expediente_sha256===docs?.expediente_sha256;
 function controls(){prepare.disabled=busy||running||!linked()||dirty;provider.disabled=model.disabled=tokens.disabled=busy||running;
  consent.disabled=busy||running||current?.estado!=='preparado';
  run.disabled=busy||running||!linked()||dirty||current?.estado!=='preparado'||!consent.checked||!model.value.trim()||
   current.origen_preparacion!==preconfig.id||current.origen_sha256_configuracion!==preconfig.sha256_configuracion||limits?.[provider.value]?.restantes===0;
  open.disabled=busy||!docs;recover.disabled=busy||running||!current?.tiene_respuesta_conservada;
  apply.disabled=busy||running||!linked()||dirty||!current?.tiene_respuesta_conservada;}
 function showQuota(){const q=limits?.[provider.value];quota.textContent=q?(q.restantes+' de '+q.limite+' solicitudes autorizadas disponibles. '+(q.credencial_configurada?'Credencial local configurada.':'Falta la credencial local.')):'La cuota se comparte con las demás lecturas de planos.';}
 async function refreshQuota(own,id){const res=await api('/api/reconstruccion/cuota'),value=await res.json();if(same(own,id)){limits=value;showQuota();controls();}}
 async function listing(own,id){const res=await api('/api/parametros/historial?'+new URLSearchParams(id)),value=await res.json();if(!same(own,id))return;
  history.replaceChildren();const empty=el('option','Selecciona una lectura');empty.value='';history.append(empty);
  for(const [index,job] of value.trabajos.entries()){const option=el('option','Lectura '+(index+1)+' · '+job.slice(0,8));option.value=job;history.append(option);}if(current)history.value=current.id;}
 function publish(child,origin,sha){if(!child||child===lastPublished)return;lastPublished=child;
  window.dispatchEvent(new CustomEvent('d2m-preconfig-created',{detail:{...identity(),configuracion_preparacion:child,preparacion_origen:origin,sha256_configuracion:sha}}));}
 function showIssues(value){issues.replaceChildren();const groups=new Map();
  for(const row of value||[]){if(typeof row==='string'){issues.append(el('li',row));continue;}
   const reason=row.motivo||row.descripcion||row.mensaje||'Dato pendiente de revisión.',key=(row.coleccion||'')+'|'+reason;
   if(!groups.has(key))groups.set(key,{reason,collection:row.coleccion,rows:[]});groups.get(key).rows.push(row);}
  const names={materiales:'materiales',secciones:'secciones',asignaciones:'asignaciones',cargas:'cargas',lectura:'observaciones del plano'};
  for(const group of groups.values()){const item=el('li'),box=el('details'),list=el('ul');
   box.append(el('summary',group.rows.length+' '+(names[group.collection]||'datos')+': '+group.reason));
   for(const row of group.rows)list.append(el('li',(row.dato?.nombre||row.id||'Dato por revisar')+(row.id&&row.dato?.nombre?' ['+row.id+']':'')));
   box.append(list);item.append(box);issues.append(item);}}
 function render(value){current=value;running=value.estado==='en_ejecucion';status.textContent=value.paso;rows.replaceChildren();summary.textContent='';
  const result=value.resultado,read=result?.lectura?.datos;if(read){summary.textContent=read.materiales.length+' materiales · '+read.secciones.length+' secciones · '+read.cargas.length+' cargas propuestas. La preparación sigue en borrador.';
   for(const row of read.materiales)rows.append(el('li','Material '+row.nombre+' ['+row.id+']: '+row.propiedades.map(q=>q.nombre+'='+q.valor+' '+q.unidad).join('; ')));
   for(const row of read.secciones)rows.append(el('li','Sección '+row.nombre+' ['+row.id+'] · '+row.tipo+': '+row.parametros.map(q=>q.nombre+'='+q.valor+' '+q.unidad).join('; ')));
   for(const row of read.cargas)rows.append(el('li','Carga '+row.nombre+': '+row.valor+' '+row.unidad+' · '+row.alcance));
   showIssues([...(result.faltantes||[]),...(result.lectura.advertencias||[]),...(result.faltantes_adaptacion_lecturas||[])]);
   publish(result.configuracion_preparacion,value.origen_preparacion,result.sha256_configuracion);
   if(result.extraccion&&result.extraccion!==lastExtraction){lastExtraction=result.extraccion;window.dispatchEvent(new CustomEvent('d2m-extraction-created',{detail:{...identity(),extraccion:result.extraccion,estado:'pendiente_revision',aprueba_ingenieria:false}}));
    window.dispatchEvent(new CustomEvent('d2m-parameter-readings-created',{detail:{...identity(),extraccion:result.extraccion,materiales_para_revision:result.materiales_para_revision||[]}}));}
  }else showIssues([]);if(value.simulado)status.textContent+=' PRUEBA SINTÉTICA: no acredita lectura real.';controls();}
 async function action(callback){const own=generation,id=identity();if(!id||busy)return;busy=true;status.textContent='Procesando la operación… El resultado y los datos pendientes aparecerán aquí.';controls();try{await callback(own,id);}
  catch(error){if(same(own,id))status.textContent=error.message;}finally{if(same(own,id)){busy=false;controls();}}}
 async function poll(own,id,job){const ticket=++polling;clearTimeout(timer);if(!same(own,id))return;
  try{const res=await api('/api/parametros/estado?'+new URLSearchParams({...id,trabajo:job})),value=await res.json();if(!same(own,id)||ticket!==polling)return;
   render(value);if(running)timer=setTimeout(()=>{if(ticket===polling)poll(own,id,job);},2000);else await refreshQuota(own,id);
  }catch(error){if(same(own,id)&&ticket===polling){running=false;status.textContent=error.message;controls();}}}
 form.addEventListener('submit',event=>{event.preventDefault();action(async(own,id)=>{if(!linked()||dirty)return;
  requestKey=crypto.randomUUID().replaceAll('-','');const res=await api('/api/parametros/preparar',{...id,proveedor:provider.value,modelo:model.value.trim(),max_tokens:Number(tokens.value),
   clave_solicitud:requestKey,configuracion_preparacion:preconfig.id,sha256_configuracion:preconfig.sha256_configuracion}),value=await res.json();
  if(!same(own,id))return;consent.checked=false;render(value);await listing(own,id);});});
 run.addEventListener('click',()=>action(async(own,id)=>{if(!current||!consent.checked)return;const job=current.id;consent.checked=false;
  const res=await api('/api/parametros/ejecutar',{...id,trabajo:job,confirmacion_explicita:true}),value=await res.json();if(!same(own,id))return;render(value);await poll(own,id,job);}));
 open.addEventListener('click',()=>action(async(own,id)=>{if(!history.value)return;await poll(own,id,history.value);}));
 recover.addEventListener('click',()=>action(async(own,id)=>{if(!current)return;const res=await api('/api/parametros/recuperar',{...id,trabajo:current.id}),value=await res.json();if(same(own,id))render(value);}));
 apply.addEventListener('click',()=>action(async(own,id)=>{if(!current||!linked()||dirty)return;const origin=preconfig.id,res=await api('/api/parametros/aplicar',{...id,trabajo:current.id,
   configuracion_preparacion:origin,sha256_configuracion:preconfig.sha256_configuracion,clave_aplicacion:crypto.randomUUID().replaceAll('-','')}),value=await res.json();
  if(!same(own,id))return;showIssues(value.aplicacion.faltantes);publish(value.configuracion_preparacion,origin,value.sha256_configuracion);status.textContent='Datos conservados reaplicados a la preparación. No se llamó al proveedor ni se aprobó ingeniería.';}));
 consent.addEventListener('change',controls);provider.addEventListener('change',()=>{current=null;consent.checked=false;model.value=provider.value==='openai'?'gpt-6.1-sol':'';showQuota();controls();});
 for(const input of [model,tokens])input.addEventListener('input',()=>{if(current?.estado==='preparado'){current=null;consent.checked=false;}controls();});
 window.addEventListener('d2m-preconfig-opened',event=>{const value=event.detail,id=identity();if(!id||value?.caso!==id.caso||value.expediente_sha256!==id.expediente_sha256)return;preconfig=value;dirty=false;
  if(!current)status.textContent='Preparación de ingeniería abierta. Puedes preparar una lectura nueva o consultar una conservada.';controls();});
 window.addEventListener('d2m-preconfig-edited',event=>{if(event.detail?.id===preconfig?.id){dirty=true;consent.checked=false;controls();}});
 window.addEventListener('d2m-case',()=>{const own=++generation;clearTimeout(timer);preconfig=null;current=null;dirty=false;running=false;busy=false;limits=null;lastPublished='';lastExtraction='';polling++;requestKey=null;consent.checked=false;
  history.replaceChildren();rows.replaceChildren();issues.replaceChildren();summary.textContent='';status.textContent='Abre o genera una preparación de ingeniería para continuar.';controls();showQuota();
  const id=identity();if(id){listing(own,id).catch(error=>{if(same(own,id))status.textContent=error.message;});refreshQuota(own,id).catch(error=>{if(same(own,id))quota.textContent=error.message;});}});controls();
})();
