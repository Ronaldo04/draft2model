'use strict';
(()=>{
 let packet=null,job=null,ticket=0,read=0,listRead=0,timer=null,polls=0,requestKey=null,payloadKey=null;
 const fresh=(own,caso,fp)=>own===ticket&&caso===docs?.caso&&fp===docs.expediente_sha256;
 const fields=['proveedorTipo','proveedorModelo','proveedorTokens','proveedorDetalle','proveedorTimeout'];
 const linkHint='Vincular conserva la procedencia del trabajo. Importar su extracción al historial requiere otra acción en el panel de respuestas.';
 function inputs(){const proveedor=$('proveedorTipo').value||'openai';if(!/^[a-z][a-z0-9_]{0,63}$/.test(proveedor))return null;const modelo=$('proveedorModelo').value, max_tokens=Number($('proveedorTokens').value),timeout_s=Number($('proveedorTimeout').value),detalle=$('proveedorDetalle').value;
  if(!/^[A-Za-z0-9_.:/-]{1,128}$/.test(modelo)||!Number.isInteger(max_tokens)||max_tokens<256||max_tokens>16384||!Number.isInteger(timeout_s)||timeout_s<1||timeout_s>180||!['low','high','auto'].includes(detalle))return null;
  if($('proveedorTipo').selectedOptions?.[0]?.dataset?.detalleAuto==='true'&&detalle!=='auto')return null;return {modelo,opciones:{max_tokens,detalle,timeout_s},...(proveedor==='openai'?{}:{proveedor})};
 }
 function matches(){const value=inputs();return value&&packet&&job?.vigente===true&&job.expediente_sha256===docs?.expediente_sha256&&job.paquete===packet.id&&job.sha256_solicitud===packet.sha256_solicitud&&job.modelo_declarado===value.modelo&&(job.proveedor||'openai')===(value.proveedor||'openai')&&Object.keys(value.opciones).every(k=>job.opciones?.[k]===value.opciones[k]);}
 const canRun=()=>job?.estado==='preparado'&&matches();
 const canRecover=()=>job?.estado==='incierto'&&job.requiere_recuperacion===true&&job.caso===docs?.caso&&job.expediente_sha256===docs.expediente_sha256;
 const canLink=()=>job?.estado==='completado_verificado'&&job.vigente===true&&job.caso===docs?.caso&&job.expediente_sha256===docs.expediente_sha256&&/^[0-9a-f]{32}$/.test(job.respuesta_visual?.id||'');
 window.providerControls=()=>{
  for(const id of fields)$(id).disabled=busy||!packet;
  for(const id of ['proveedorVersion','proveedorActualizar'])$(id).disabled=busy||!docs;
  $('proveedorPreparar').disabled=busy||!packet||!inputs();
  $('proveedorConfirmar').disabled=busy||!canRun();$('proveedorEjecutar').disabled=busy||!canRun()||!$('proveedorConfirmar').checked;
  $('proveedorConfirmarRecuperar').disabled=busy||!canRecover();$('proveedorRecuperar').disabled=busy||!canRecover()||!$('proveedorConfirmarRecuperar').checked;
  $('proveedorConfirmarVincular').disabled=busy||!canLink();$('proveedorImportar').disabled=busy||!canLink()||!$('proveedorConfirmarVincular').checked;
 };
 function stop(){if(timer!==null)clearTimeout(timer);timer=null;}
 function unconfirm(){$('proveedorConfirmar').checked=false;$('proveedorConfirmarRecuperar').checked=false;$('proveedorConfirmarVincular').checked=false;}
 function reset(){read++;stop();job=null;unconfirm();$('proveedorDatos').textContent='';$('proveedorTraslado').textContent=linkHint;$('proveedorEstado').textContent='Sin trabajo seleccionado.';window.providerControls();}
 function clear(){ticket++;listRead++;reset();packet=null;polls=0;requestKey=null;payloadKey=null;for(const id of fields)$(id).value='';$('proveedorTipo').value='openai';options($('proveedorVersion'),[['','Selecciona trabajo']]);$('proveedorPaquete').textContent='Selecciona un paquete visual comprobado arriba.';window.providerControls();}
 function fail(error){$('proveedorEstado').textContent=error.message;message(error.message,true);}
 async function act(fn){const own=ticket,seq=read,caso=docs?.caso,fp=docs?.expediente_sha256;try{await fn(own,caso,fp);}catch(error){if(fresh(own,caso,fp)&&seq===read)fail(error);}}
 function show(value){
  if(value.id!==$('proveedorVersion').value||value.caso!==docs?.caso||value.expediente_sha256!==docs?.expediente_sha256||value.aprueba_ingenieria!==false||value.aprueba_resultados!==false)throw Error('Trabajo ajeno a la selección o contrato no verificable.');
  const identity=job&&JSON.stringify([job.id,job.huella_preparacion,job.estado,job.vigente]),next=JSON.stringify([value.id,value.huella_preparacion,value.estado,value.vigente]);
  if(identity!==next){unconfirm();$('proveedorTraslado').textContent=linkHint;}job=value;$('proveedorDatos').textContent=JSON.stringify(value,null,2);
  const mode=value.modo==='transporte_prueba_python'?'PRUEBA SINTÉTICA · sin llamada real':value.llamada_real_acreditada===true?'REAL · llamada acreditada por evidencia local':value.modo==='real'?'REAL · transmisión posible; resultado aún no acreditado':'PLAN LOCAL · sin envío';
  $('proveedorEstado').textContent='Trabajo '+value.id+' · '+(value.proveedor||'openai')+' · '+(value.endpoint_declarado||'destino del plan')+' · '+value.estado+' · '+mode+' · '+(value.vigente?'fuentes vigentes':'sin vigencia')+' · costo estimado no disponible · sin aprobación.';
  window.providerControls();
 }
 function schedule(){stop();if(job?.estado==='en_ejecucion'&&polls<30){timer=setTimeout(()=>{timer=null;polls++;open(false);},4000);}else if(job?.estado==='en_ejecucion')$('proveedorEstado').textContent+=' Sondeo detenido tras 30 consultas; actualiza el historial para continuar consultando.';}
 async function open(manual=true){const own=ticket,seq=++read,caso=docs?.caso,fp=docs?.expediente_sha256,id=$('proveedorVersion').value;stop();if(manual)polls=0;
  if(!caso||!id){reset();return;}if(job?.id!==id){job=null;unconfirm();$('proveedorDatos').textContent='';window.providerControls();}
  try{const res=await api('/api/proveedor/trabajo?'+new URLSearchParams({caso,trabajo:id})),value=await res.json();
   if(!fresh(own,caso,fp)||seq!==read||$('proveedorVersion').value!==id)return;show(value);schedule();
  }catch(error){if(fresh(own,caso,fp)&&seq===read&&$('proveedorVersion').value===id){job=null;unconfirm();$('proveedorDatos').textContent='';window.providerControls();fail(error);}}
 }
 async function listing(preferred){const own=ticket,seq=++listRead,selected=$('proveedorVersion').value,caso=docs?.caso,fp=docs?.expediente_sha256;if(!caso)return;
  try{const res=await api('/api/proveedor/trabajos?'+new URLSearchParams({caso})),value=await res.json();if(!fresh(own,caso,fp)||seq!==listRead||(!preferred&&$('proveedorVersion').value!==selected))return;
   const id=preferred||selected;options($('proveedorVersion'),[['','Selecciona trabajo'],...value.trabajos.map(v=>[v.id,v.id+' · '+v.estado])]);
   if(value.trabajos.some(v=>v.id===id)){$('proveedorVersion').value=id;await open();}else reset();
  }catch(error){if(fresh(own,caso,fp)&&seq===listRead&&$('proveedorVersion').value===selected)fail(error);}
 }
 window.addEventListener('d2m-case',()=>{clear();if(docs)listing();});
 window.addEventListener('d2m-visual-package',event=>{const value=event.detail,valid=value&&value.caso===docs?.caso&&value.expediente_sha256===docs.expediente_sha256&&value.estado==='preparado_sin_envio'&&value.transmision_externa===false&&value.aprueba_ingenieria===false;
  const next=valid?value:null;if(packet?.id!==next?.id||packet?.sha256_solicitud!==next?.sha256_solicitud){ticket++;read++;listRead++;stop();unconfirm();requestKey=null;payloadKey=null;}
  packet=next;$('proveedorPaquete').textContent=packet?'Paquete '+packet.id+' · solicitud '+packet.solicitud_id+' · SHA256 '+packet.sha256_solicitud:'Selecciona un paquete visual comprobado arriba.';window.providerControls();
 });
 for(const id of fields)$(id).addEventListener('input',()=>{unconfirm();window.providerControls();});
 for(const id of ['proveedorConfirmar','proveedorConfirmarRecuperar','proveedorConfirmarVincular'])$(id).addEventListener('input',window.providerControls);
 $('proveedorVersion').onchange=()=>{listRead++;open();};$('proveedorActualizar').onclick=()=>action(()=>listing());
 $('proveedorPreparar').onclick=()=>action(()=>act(async(own,caso,fp)=>{
  const selected=packet,value=inputs();if(!selected||!value)throw Error('Selecciona paquete, modelo, tokens, detalle y espera explícitos.');
  const body={caso,expediente_sha256:fp,paquete:selected.id,...value},key=JSON.stringify(body),seq=read;
  if(payloadKey!==key){requestKey=crypto.randomUUID().replaceAll('-','');payloadKey=key;}
  const res=await api('/api/proveedor/preparar',{...body,clave_solicitud:requestKey}),created=await res.json();
  if(fresh(own,caso,fp)&&read===seq&&packet===selected&&JSON.stringify(inputs())===JSON.stringify(value))await listing(created.id);
 }));
 $('proveedorEjecutar').onclick=()=>action(()=>act(async(own,caso,fp)=>{
  const selected=job,seq=read;if(!canRun()||!$('proveedorConfirmar').checked)throw Error('Comprueba el paquete, opciones y huella; confirma transmisión externa y posibles costos.');unconfirm();window.providerControls();
  const res=await api('/api/proveedor/ejecutar',{caso,trabajo:selected.id,huella_preparacion:selected.huella_preparacion,expediente_sha256:fp,confirmacion_explicita:true}),value=await res.json();
  if(fresh(own,caso,fp)&&seq===read&&job===selected){show(value);polls=0;schedule();}
 }));
 $('proveedorRecuperar').onclick=()=>action(()=>act(async(own,caso,fp)=>{
  const selected=job,seq=read;if(!canRecover()||!$('proveedorConfirmarRecuperar').checked)throw Error('Selecciona el trabajo incierto y confirma resolver sin reenviar.');unconfirm();window.providerControls();
  const res=await api('/api/proveedor/recuperar',{caso,trabajo:selected.id,huella_preparacion:selected.huella_preparacion,confirmacion_explicita:true,resolucion:'cerrar_sin_reintento'}),value=await res.json();
  if(fresh(own,caso,fp)&&seq===read&&job===selected){show(value);schedule();}
 }));
 $('proveedorImportar').onclick=()=>action(()=>act(async(own,caso,fp)=>{
  const selected=job,seq=read;if(!canLink()||!$('proveedorConfirmarVincular').checked)throw Error('Comprueba el trabajo completado vigente y confirma vincular su respuesta sin aprobar.');unconfirm();window.providerControls();
  const res=await api('/api/respuestas/vincular-proveedor',{caso,expediente_sha256:fp,trabajo:selected.id,huella_preparacion:selected.huella_preparacion,confirmacion_explicita:true}),value=await res.json();
  if(!fresh(own,caso,fp)||seq!==read||job!==selected)return;
  if(value.id!==selected.respuesta_visual.id||value.caso!==caso||value.expediente_sha256!==fp||value.trabajo_proveedor!==selected.id||value.origen!=='proveedor_verificado'||value.estado!=='pendiente_revision'||value.aprueba_ingenieria!==false||value.modo_prueba!==(selected.modo==='transporte_prueba_python')||value.llamada_real_acreditada!==selected.llamada_real_acreditada||value.transmision_externa!==selected.llamada_real_acreditada)throw Error('Vínculo de respuesta no verificable.');
  $('proveedorTraslado').textContent='Respuesta '+value.id+' vinculada; revisa su extracción pendiente en el panel de respuestas. Importarla al historial exige otra confirmación.';
  window.dispatchEvent(new CustomEvent('d2m-response-created',{detail:value}));
 }));clear();
})();
