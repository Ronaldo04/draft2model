'use strict';
(()=>{
 const tipos=['recuperacion','evaluacion','sitio'],fields=['expProveedor','expModelo','expTokens','expTimeout'];
 let ticket=0,read=0,listRead=0,timer=null,polls=0,result=null,derivados={recuperacion:null,evaluacion:null,sitio:null},job=null,key=null,keyPayload=null,published;
 const fresh=(own,caso,fp)=>own===ticket&&docs?.caso===caso&&docs.expediente_sha256===fp;
 const ids=()=>Object.fromEntries(tipos.map(t=>[t,derivados[t]?.id||null]));
 function inputs(){const proveedor=$('expProveedor').value||'openai';if(!/^[a-z][a-z0-9_]{0,63}$/.test(proveedor))return null;const modelo=$('expModelo').value,max_tokens=Number($('expTokens').value),timeout_s=Number($('expTimeout').value);return /^[A-Za-z0-9_.:/-]{1,128}$/.test(modelo)&&Number.isInteger(max_tokens)&&max_tokens>=256&&max_tokens<=16384&&Number.isInteger(timeout_s)&&timeout_s>=1&&timeout_s<=180?{modelo,opciones:{max_tokens,timeout_s},...(proveedor==='openai'?{}:{proveedor})}:null;}
 function matches(){const value=inputs();return result&&value&&job?.vigente===true&&job.resultado===result.id&&job.huella_resultados===result.huella&&job.expediente_sha256===docs?.expediente_sha256&&job.modelo_declarado===value.modelo&&(job.proveedor||'openai')===(value.proveedor||'openai')&&Object.keys(value.opciones).every(k=>job.opciones?.[k]===value.opciones[k])&&tipos.every(t=>(job.derivados?.[t]||null)===(derivados[t]?.id||null));}
 const executable=()=>job?.estado==='preparado'&&matches(),recoverable=()=>job?.estado==='incierto'&&job.requiere_recuperacion===true&&job.expediente_sha256===docs?.expediente_sha256;
 window.explanationControls=()=>{for(const id of fields)$(id).disabled=busy||!result;for(const id of ['expVersion','expActualizar'])$(id).disabled=busy||!docs;$('expPreparar').disabled=busy||!result||!inputs();$('expConfirmar').disabled=busy||!executable();$('expEjecutar').disabled=busy||!executable()||!$('expConfirmar').checked;$('expConfirmarRecuperar').disabled=busy||!recoverable();$('expRecuperar').disabled=busy||!recoverable()||!$('expConfirmarRecuperar').checked;};
 function publish(value){const serialized=JSON.stringify(value);if(serialized===published)return;published=serialized;window.dispatchEvent(new CustomEvent('d2m-explanation',{detail:value}));}
 function stop(){if(timer!==null)clearTimeout(timer);timer=null;}
 function unconfirm(){$('expConfirmar').checked=false;$('expConfirmarRecuperar').checked=false;}
 function reset(){read++;stop();job=null;unconfirm();$('expDatos').textContent='';$('expEstado').textContent='Sin trabajo seleccionado.';publish(null);window.explanationControls();}
 function sources(){$('expFuentes').textContent=JSON.stringify({resultado:result,derivados:ids()},null,2);window.explanationControls();}
 function clear(){ticket++;listRead++;result=null;derivados={recuperacion:null,evaluacion:null,sitio:null};key=null;keyPayload=null;reset();for(const id of fields)$(id).value='';$('expProveedor').value='openai';options($('expVersion'),[['','Sin selección']]);sources();}
 function fail(error){$('expEstado').textContent=error.message;message(error.message,true);}
 async function act(fn){const own=ticket,seq=read,caso=docs?.caso,fp=docs?.expediente_sha256;try{await fn(own,caso,fp,seq);}catch(error){if(fresh(own,caso,fp)&&seq===read)fail(error);}}
 function show(value){if(value.id!==$('expVersion').value||value.caso!==docs?.caso||value.expediente_sha256!==docs.expediente_sha256||value.aprueba_resultados!==false||value.aprueba_informe!==false||value.conformidad_normativa!=='no_evaluada')throw Error('Explicación ajena o contrato no verificable.');
  const old=job&&JSON.stringify([job.id,job.huella_preparacion,job.estado,job.vigente]),next=JSON.stringify([value.id,value.huella_preparacion,value.estado,value.vigente]);if(old!==next)unconfirm();job=value;
  const salida=value.vigente?value.salida:null;if(salida&&(salida.aprueba_resultados!==false||salida.aprueba_informe!==false||salida.conformidad_normativa!=='no_evaluada'||salida.estado_revision!=='propuesta_pendiente_revision_humana'))throw Error('Salida sin límites de revisión humana.');
  $('expDatos').textContent=JSON.stringify({...value,salida},null,2);const mode=!salida?'sin salida aceptada':salida.modo==='contingencia_deterministica'?'CONTINGENCIA DETERMINÍSTICA · SIN LLM REAL':salida.generacion_llm_real?'LLM REAL · propuesta pendiente de revisión humana':'PRUEBA / SIMULACIÓN · SIN LLM REAL';
  $('expEstado').textContent='Trabajo '+value.id+' · '+(value.proveedor||'openai')+' · '+(value.endpoint_declarado||'destino del plan')+' · '+value.estado+' · '+mode+' · '+(value.vigente?'fuentes vigentes':'sin vigencia')+' · sin aprobación ni conformidad normativa.';window.explanationControls();
  publish(salida&&result&&value.resultado===result.id&&value.huella_resultados===result.huella?value:null);
 }
 function schedule(){stop();if(job?.estado==='en_ejecucion'&&polls<30)timer=setTimeout(()=>{timer=null;polls++;open(false);},4000);else if(job?.estado==='en_ejecucion')$('expEstado').textContent+=' Sondeo detenido tras 30 consultas; consulta el historial para continuar.';}
 async function open(manual=true){const own=ticket,seq=++read,caso=docs?.caso,fp=docs?.expediente_sha256,id=$('expVersion').value;stop();if(manual)polls=0;if(!caso||!id){reset();return;}if(job?.id!==id){job=null;unconfirm();$('expDatos').textContent='';publish(null);window.explanationControls();}
  try{const res=await api('/api/explicaciones/trabajo?'+new URLSearchParams({caso,trabajo:id})),value=await res.json();if(!fresh(own,caso,fp)||seq!==read||$('expVersion').value!==id)return;show(value);schedule();}
  catch(error){if(fresh(own,caso,fp)&&seq===read){reset();fail(error);}}
 }
 async function listing(preferred){const own=ticket,caso=docs?.caso,fp=docs?.expediente_sha256,seq=++listRead,opened=read,id=preferred||$('expVersion').value;if(!caso)return;
  try{const res=await api('/api/explicaciones/trabajos?'+new URLSearchParams({caso})),value=await res.json();if(!fresh(own,caso,fp)||seq!==listRead||opened!==read)return;
   options($('expVersion'),[['','Selecciona trabajo'],...value.trabajos.map(v=>[v.id,v.id+' · '+v.estado+(v.vigente?'':' · sin vigencia')])]);if(value.trabajos.some(v=>v.id===id)){$('expVersion').value=id;await open();}else reset();
  }catch(error){if(fresh(own,caso,fp)&&seq===listRead&&opened===read)fail(error);}
 }
 // 293: sin consulta automática al cambiar de expediente; Actualizar consulta y verifica (clear() invalida respuestas previas).
 window.addEventListener('d2m-case',()=>{clear();if(docs)$('expEstado').textContent='Historial sin consultar: seleccionar el expediente no lo comprueba. Pulsa Actualizar para consultarlo y verificarlo.';});
 window.addEventListener('d2m-result',event=>{const d=event.detail,r=d?.record,next=r&&r.caso===docs?.caso&&r.expediente_sha256===docs.expediente_sha256&&r.vigente!==false?{id:d.version,huella:r.huella}:null;if(JSON.stringify(result)===JSON.stringify(next))return;ticket++;listRead++;result=next;reset();sources();});
 window.addEventListener('d2m-context',event=>{const d=event.detail;if(d&&(d.caso!==docs?.caso||d.expediente_sha256!==docs.expediente_sha256))return;
  const next=Object.fromEntries(tipos.map(t=>{const v=d?.derivados?.[t];return [t,v&&v.tipo===t&&v.vigente===true&&v.reproducido===true?v:null];})),identity=values=>JSON.stringify(tipos.map(t=>[values[t]?.id||null,values[t]?.sha256_salida||null]));
  if(identity(next)!==identity(derivados)){ticket++;listRead++;derivados=next;reset();sources();}
 });
 for(const id of fields)$(id).addEventListener('input',()=>{unconfirm();window.explanationControls();});for(const id of ['expConfirmar','expConfirmarRecuperar'])$(id).addEventListener('input',window.explanationControls);
 $('expVersion').onchange=()=>{listRead++;return open();};$('expActualizar').onclick=()=>action(async()=>{const own=ticket,caso=docs?.caso,fp=docs?.expediente_sha256;await listing();if(fresh(own,caso,fp)&&$('expEstado').textContent==='Historial sin consultar: seleccionar el expediente no lo comprueba. Pulsa Actualizar para consultarlo y verificarlo.')$('expEstado').textContent='Historial consultado y comprobado. Abrir o usar una versión vuelve a comprobarla.';});
 $('expPreparar').onclick=()=>action(()=>act(async(own,caso,fp,seq)=>{const value=inputs();if(!result||!value)throw Error('Selecciona resultado comprobado y declara modelo, tokens y espera.');const body={caso,expediente_sha256:fp,resultado:result.id,huella_resultados:result.huella,derivados:ids(),...value},signature=JSON.stringify(body);if(signature!==keyPayload){key=crypto.randomUUID().replaceAll('-','');keyPayload=signature;}
  const res=await api('/api/explicaciones/preparar',{...body,clave_solicitud:key}),created=await res.json();if(fresh(own,caso,fp)&&seq===read&&JSON.stringify(inputs())===JSON.stringify(value))await listing(created.id);
 }));
 $('expEjecutar').onclick=()=>action(()=>act(async(own,caso,fp,seq)=>{if(!executable()||!$('expConfirmar').checked)throw Error('Comprueba fuentes, modelo, opciones y huella; confirma transmisión y contingencia.');const current=job;unconfirm();window.explanationControls();const res=await api('/api/explicaciones/ejecutar',{caso,trabajo:current.id,expediente_sha256:fp,huella_preparacion:current.huella_preparacion,confirmacion_explicita:true}),value=await res.json();if(fresh(own,caso,fp)&&seq===read&&job===current){show(value);polls=0;schedule();}}));
 $('expRecuperar').onclick=()=>action(()=>act(async(own,caso,fp,seq)=>{if(!recoverable()||!$('expConfirmarRecuperar').checked)throw Error('Selecciona trabajo incierto y confirma cerrar sin reenviar.');const current=job;unconfirm();window.explanationControls();const res=await api('/api/explicaciones/recuperar',{caso,trabajo:current.id,huella_preparacion:current.huella_preparacion,confirmacion_explicita:true,resolucion:'cerrar_sin_reintento'}),value=await res.json();if(fresh(own,caso,fp)&&seq===read&&job===current){show(value);schedule();}}));clear();
})();
