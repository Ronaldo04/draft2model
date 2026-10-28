/* Componente sin montaje automático. Las dependencias conservan sesión/origen del host. */
(function(root,factory){
 const exported=factory();
 if(typeof module==='object'&&module.exports)module.exports=exported;
 else root.D2MRevisionResultados=exported;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const CONTROLES=Object.freeze(['unidades','casos','filtros','omisiones','consistencia_modelo','revision_tecnica']);
 const CAMPOS=Object.freeze(['rrRevisor','rrFecha','rrAlcance','rrMotivo','rrObservaciones','rrCriticos']);
 const uuid=value=>typeof value==='string'&&/^[0-9a-f]{32}$/.test(value);
 const hash=value=>typeof value==='string'&&/^[0-9a-f]{64}$/.test(value);
 const canonical=value=>JSON.stringify(value&&typeof value==='object'&&!Array.isArray(value)?Object.fromEntries(Object.keys(value).sort().map(k=>[k,JSON.parse(canonical(value[k]))])):Array.isArray(value)?value.map(v=>JSON.parse(canonical(v))):value);

 function crearRevisionResultados(deps){
  const {get,api,options,getContext,isBusy=()=>false,action=fn=>fn(),message=()=>{},emit,events,cargarAnalisis}=deps||{};
  for(const value of [get,api,options,getContext,emit])if(typeof value!=='function')throw Error('Dependencias de revisión de resultados incompletas.');
  let epoch=0,sourceSeq=0,versionSeq=0,listSeq=0,result=null,source=null,current=null,writePending=false,sourcePending=false,disposed=false,published,history=[];
  const listeners=[];
  const el=id=>{const value=get(id);if(!value)throw Error('Falta control de revisión de resultados: '+id);return value;};
  const active=()=>!disposed&&result&&getContext()?.caso===result.caso&&getContext()?.expediente_sha256===result.expediente_sha256;
  const identity=()=>result?JSON.stringify(result):'null';
  const fresh=(own,key)=>own===epoch&&key===identity()&&active();
  const analysis=()=>el('rrAnalisis').value;
  const query=extra=>new URLSearchParams({caso:result.caso,resultado:result.resultado,expediente_sha256:result.expediente_sha256,...extra});
  const proof=value=>value?canonical({huella_resultados:value.huella_resultados,huella_evidencia:value.huella_evidencia,analisis:value.analisis,archivos_resultado:value.archivos_resultado}):'null';
  function publish(value){const key=value?JSON.stringify([value.caso,value.resultado,value.analisis,value.expediente_sha256,value.id,value.sha256_revision]):'null';if(key===published)return;published=key;emit('d2m-result-review',value);}
  function resetChecks(){for(const control of CONTROLES)el('rrControl_'+control).checked=false;el('rrConfirmar').checked=false;}
  function resetCurrent(){versionSeq++;current=null;el('rrVersion').value='';el('rrRevisionDatos').textContent='';publish(null);}
  function resetSources(){sourceSeq++;source=null;sourcePending=false;el('rrFuenteDatos').textContent='';resetChecks();resetCurrent();}
  function invalidate(){epoch++;listSeq++;resetSources();for(const field of CAMPOS)el(field).value='';}
  function fail(error){el('rrEstado').textContent=error.message;message(error.message,true);}
  function validSource(value){return value&&active()&&value.caso===result.caso&&value.resultado===result.resultado&&value.analisis===analysis()&&value.expediente_sha256===result.expediente_sha256&&value.huella_resultados===result.huella_resultados&&hash(value.huella_evidencia)&&value.aprueba_resultados===false&&value.aprueba_informe===false&&value.revision_resultados==='pendiente'&&value.conformidad_normativa==='no_evaluada'&&Array.isArray(value.advertencias)&&Array.isArray(value.omisiones)&&Array.isArray(value.indicadores)&&value.indicadores.length>0&&Array.isArray(value.filas_omitidas)&&Array.isArray(value.controles_requeridos)&&canonical([...value.controles_requeridos].sort())===canonical([...CONTROLES].sort());}
  function textList(field){const value=JSON.parse(el(field).value);if(!Array.isArray(value)||value.length>100||value.some(v=>typeof v!=='string'||!v.trim()||v.length>2000))throw Error('Declara observaciones y faltantes críticos como listas JSON explícitas.');return value;}
  function declaration(){
   const revisor=el('rrRevisor').value,fecha=el('rrFecha').value,alcance=el('rrAlcance').value,motivo=el('rrMotivo').value,date=new Date(fecha+'T00:00:00Z');
   if(!revisor.trim()||revisor.length>150||!alcance.trim()||alcance.length>4000||!motivo.trim()||motivo.length>4000||!/^\d{4}-\d{2}-\d{2}$/.test(fecha)||Number.isNaN(date.getTime())||date.toISOString().slice(0,10)!==fecha)throw Error('Completa revisor, fecha válida, alcance y motivo declarados.');
   const observaciones=textList('rrObservaciones'),faltantes_criticos=textList('rrCriticos');if(faltantes_criticos.length)throw Error('Resuelve los faltantes críticos declarados antes de registrar la revisión.');
   const controles=Object.fromEntries(CONTROLES.map(k=>[k,el('rrControl_'+k).checked===true]));if(CONTROLES.some(k=>controles[k]!==true))throw Error('Declara individualmente los seis controles; el software no los infiere.');
   return {revisor_declarado:revisor,fecha,alcance,motivo,observaciones,faltantes_criticos,controles};
  }
  function ready(){if(!active()||!validSource(source)||sourcePending||writePending)return false;try{declaration();return true;}catch(_){return false;}}
  function controles(){
   if(disposed)return;const blocked=isBusy()||writePending,enabled=active();
   for(const id of ['rrAnalisis','rrActualizar','rrVersion'])el(id).disabled=blocked||!enabled;
   el('rrFuentes').disabled=blocked||!enabled||!uuid(analysis());
   for(const id of [...CAMPOS,...CONTROLES.map(k=>'rrControl_'+k)])el(id).disabled=blocked||sourcePending||!validSource(source);
   el('rrConfirmar').disabled=blocked||!ready();el('rrRegistrar').disabled=blocked||!ready()||!el('rrConfirmar').checked;
   el('rrNativo').textContent='Estado nativo del resultado: pendiente. La revisión declarada no cambia el paquete ni certifica seguridad o normativa.';
  }
  async function consultarFuentes(){
   if(!active()||!uuid(analysis()))return;const own=epoch,key=identity(),id=analysis(),seq=++sourceSeq;sourcePending=true;controles();
   try{const res=await api('/api/revision-resultados/fuentes?'+query({analisis:id})),value=await res.json();if(!fresh(own,key)||sourceSeq!==seq||analysis()!==id)return;
    if(!validSource(value))throw Error('Fuentes ajenas, incompletas o sin huellas vigentes.');
    const changed=proof(source)!==proof(value);if(changed){resetChecks();resetCurrent();}source=value;el('rrFuenteDatos').textContent=JSON.stringify(value,null,2);el('rrEstado').textContent=(value.datos_sinteticos?'DATOS SINTÉTICOS · ':'')+'Fuentes comprobadas. Revisa todas las advertencias, omisiones y filas null antes de declarar controles.';
   }catch(error){if(fresh(own,key)&&sourceSeq===seq&&analysis()===id){resetSources();fail(error);}}
   finally{if(fresh(own,key)&&sourceSeq===seq){sourcePending=false;controles();}}
  }
  function validVersion(value,id){return value&&value.id===id&&uuid(id)&&hash(value.sha256_revision)&&active()&&validSource(source)&&value.caso===result.caso&&value.resultado===result.resultado&&value.analisis===analysis()&&value.expediente_sha256===result.expediente_sha256&&value.huella_resultados===source.huella_resultados&&value.huella_evidencia===source.huella_evidencia&&proof(value.fuentes)===proof(source)&&value.vigente===true&&value.estado==='revision_declarada_vigente'&&value.revision_resultados==='revisados_declarados'&&value.aprueba_resultados===false&&value.aprueba_informe===false&&value.aprueba_ingenieria===false&&value.conformidad_normativa==='no_evaluada'&&value.identidad_revisor==='declarada_no_verificada'&&value.verificacion_profesional===false&&Array.isArray(value.declaracion?.faltantes_criticos)&&value.declaracion.faltantes_criticos.length===0&&CONTROLES.every(k=>value.declaracion?.controles?.[k]===true);}
  async function consultarRevision(conservar=false){
   const id=el('rrVersion').value,own=epoch,key=identity(),idAnalysis=analysis(),selectedProof=proof(source),seq=++versionSeq;if(!conservar){current=null;el('rrRevisionDatos').textContent='';publish(null);}controles();if(!active()||!id)return;
   if(!validSource(source)){fail(Error('Selecciona análisis y consulta sus fuentes antes de abrir una revisión.'));return;}
   if(!history.some(v=>v.id===id&&v.vigente===true)){fail(Error('Selecciona una revisión vigente del historial.'));return;}
   try{const res=await api('/api/revision-resultados/version?'+new URLSearchParams({caso:result.caso,revision:id,expediente_sha256:result.expediente_sha256})),value=await res.json();
    if(!fresh(own,key)||seq!==versionSeq||el('rrVersion').value!==id||analysis()!==idAnalysis||proof(source)!==selectedProof)return;
    if(!validVersion(value,id))throw Error('La revisión no corresponde a estas fuentes exactas o no está vigente.');
    current=value;el('rrRevisionDatos').textContent=JSON.stringify(value,null,2);el('rrEstado').textContent='Revisión '+id+' · revisados_declarados · SHA256 '+value.sha256_revision+' · identidad declarada no autenticada · sin aprobación de informe/normativa.';publish(value);
   }catch(error){if(fresh(own,key)&&seq===versionSeq&&el('rrVersion').value===id){resetCurrent();fail(error);}}
   finally{controles();}
  }
  async function actualizar(){
   if(!active())return;const own=epoch,key=identity(),seq=++listSeq,selectedVersion=el('rrVersion').value;
   try{const [a,b]=await Promise.all([cargarAnalisis?cargarAnalisis({...result}):api('/api/analisis?'+query({modo:'inventario'})).then(res=>res.json()),api('/api/revision-resultados/historial?'+query()).then(res=>res.json())]);
    if(!fresh(own,key)||seq!==listSeq||el('rrVersion').value!==selectedVersion)return;
    if(!Array.isArray(a.versiones)||!Array.isArray(b.versiones)||b.caso!==result.caso||b.resultado!==result.resultado||b.expediente_sha256!==result.expediente_sha256)throw Error('Historial ajeno o no verificable.');
    const previous=analysis();history=b.versiones;// 301: inventario (vigente:null) se rotula «sin comprobar»; «Consultar fuentes» ejecuta la comprobación completa en el servidor.
    options(el('rrAnalisis'),[['','Selecciona análisis explícito'],...a.versiones.map(v=>[v.id,v.id+(v.vigente===true?' · vínculo comprobado':v.vigente===false?' · sin vigencia':' · sin comprobar (Consultar fuentes lo comprueba)')])]);
    for(const option of el('rrAnalisis').options)if(option.value&&!a.versiones.some(v=>v.id===option.value&&v.vigente!==false))option.disabled=true;
    if(a.versiones.some(v=>v.id===previous&&v.vigente!==false))el('rrAnalisis').value=previous;else{resetSources();}
    options(el('rrVersion'),[['','Selecciona revisión manualmente'],...history.map(v=>[v.id,v.id+(v.vigente?' · revisión declarada':' · sin vigencia')])]);
    for(const option of el('rrVersion').options)if(option.value&&!history.some(v=>v.id===option.value&&v.vigente===true))option.disabled=true;
    if(history.some(v=>v.id===selectedVersion&&v.vigente===true))el('rrVersion').value=selectedVersion;else resetCurrent();
    if(source&&analysis()){await consultarFuentes();if(fresh(own,key)&&seq===listSeq&&el('rrVersion').value===selectedVersion&&current)await consultarRevision(true);}
    controles();
   }catch(error){if(fresh(own,key)&&seq===listSeq){resetSources();fail(error);controles();}}
  }
  async function registrar(){
   if(writePending)return;const own=epoch,key=identity(),snapshot=source,analysisID=analysis(),selectedRead=versionSeq;let body;
   try{if(!ready()||el('rrConfirmar').checked!==true)throw Error('Comprueba las fuentes y declara controles, observaciones, faltantes y confirmación explícita.');body={caso:result.caso,resultado:result.resultado,analisis:analysisID,expediente_sha256:result.expediente_sha256,huella_resultados:snapshot.huella_resultados,huella_evidencia:snapshot.huella_evidencia,...declaration(),confirmacion_explicita:true};}
   catch(error){fail(error);return;}
   writePending=true;el('rrConfirmar').checked=false;controles();
   try{const res=await api('/api/revision-resultados/registrar',body),value=await res.json();if(!fresh(own,key)||source!==snapshot||analysis()!==analysisID||selectedRead!==versionSeq)return;
    if(!uuid(value.id)||!validVersion(value,value.id))throw Error('Registro recibido sin fuentes o SHA verificables.');
    resetChecks();resetCurrent();await actualizar();if(fresh(own,key))el('rrEstado').textContent='Declaración '+value.id+' registrada. Selecciónala manualmente en el historial para revalidarla; no se elige la última automáticamente.';
   }catch(error){if(fresh(own,key)&&selectedRead===versionSeq){resetSources();fail(Error('Registro no confirmado: '+error.message+' Consulta el historial antes de otra declaración; no se reintenta automáticamente.'));}}
   finally{writePending=false;controles();}
  }
  function seleccionarResultado(detail){
   const record=detail?.record,ctx=getContext(),next=record&&ctx&&record.caso===ctx.caso&&record.expediente_sha256===ctx.expediente_sha256&&uuid(detail.version)&&hash(record.huella)&&record.vigente!==false&&record.aprueba_resultados===false?{caso:ctx.caso,expediente_sha256:ctx.expediente_sha256,resultado:detail.version,huella_resultados:record.huella}:null;
   if(JSON.stringify(next)===identity())return Promise.resolve();invalidate();result=next;history=[];options(el('rrAnalisis'),[['','Selecciona análisis explícito']]);options(el('rrVersion'),[['','Sin revisión seleccionada']]);el('rrResultado').textContent=result?'Resultado '+result.resultado+' · huella '+result.huella_resultados:'Abre un resultado normalizado vigente.';el('rrEstado').textContent='Controles sin declarar; revisión nativa pendiente.';controles();return result?actualizar():Promise.resolve();
  }
  function cambiarCaso(){invalidate();result=null;history=[];options(el('rrAnalisis'),[['','Selecciona análisis explícito']]);options(el('rrVersion'),[['','Sin selección']]);el('rrResultado').textContent='Abre un resultado normalizado vigente.';el('rrEstado').textContent='Selecciona resultado y análisis explícitos.';controles();}
  function on(target,type,fn){target.addEventListener(type,fn);listeners.push(()=>target.removeEventListener(type,fn));}
  function launch(fn){return action(fn);}
  on(el('rrAnalisis'),'change',()=>{invalidate();el('rrEstado').textContent='Consulta las fuentes del análisis seleccionado; no se declaran controles automáticamente.';controles();});
  on(el('rrVersion'),'change',()=>{listSeq++;return launch(consultarRevision);});
  on(el('rrFuentes'),'click',()=>launch(consultarFuentes));on(el('rrActualizar'),'click',()=>launch(actualizar));on(el('rrRegistrar'),'click',()=>launch(registrar));
  for(const id of [...CAMPOS,...CONTROLES.map(k=>'rrControl_'+k)])on(el(id),'input',()=>{el('rrConfirmar').checked=false;controles();});on(el('rrConfirmar'),'input',controles);
  if(events){on(events,'d2m-case',cambiarCaso);on(events,'d2m-result',event=>seleccionarResultado(event.detail));}
  cambiarCaso();
  return Object.freeze({actualizar,consultarFuentes,consultarRevision,registrar,seleccionarResultado,cambiarCaso,controles,
   dispose(){if(disposed)return;for(const off of listeners)off();epoch++;sourceSeq++;versionSeq++;listSeq++;current=null;publish(null);disposed=true;}});
 }
 return Object.freeze({crearRevisionResultados,CONTROLES});
});
