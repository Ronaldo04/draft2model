'use strict';
(()=>{
 const sourceIDs={corpus:'ctxCorpus',reglas:'ctxReglas',sitio:'ctxSitio'},derivedIDs={recuperacion:'ctxDerivadoRecuperacion',evaluacion:'ctxDerivadoEvaluacion',sitio:'ctxDerivadoSitio'};
 let ticket=0,listSeq=0,selection=0,resultEpoch=0,result=null,versions={},derived={},reads={},published;
 const fresh=(own,caso,fp)=>own===ticket&&docs?.caso===caso&&docs.expediente_sha256===fp;
 const base=()=>({caso:docs.caso,expediente_sha256:docs.expediente_sha256});
 const query=extra=>new URLSearchParams({...base(),...extra});
 function publish(){const value=docs?{...base(),resultado:result,derivados:{recuperacion:derived.recuperacion||null,evaluacion:derived.evaluacion||null,sitio:derived.sitio||null}}:null;
  const key=JSON.stringify(value);if(key===published)return;published=key;window.dispatchEvent(new CustomEvent('d2m-context',{detail:value}));
 }
 function render(){$('ctxDatos').textContent=JSON.stringify({contexto:versions,derivados:derived},null,2);window.contextControls();}
 function source(tipo){return versions[tipo]&&versions[tipo].id===$(sourceIDs[tipo]).value?versions[tipo]:null;}
 window.contextControls=()=>{
  for(const id of ['ctxTipo','ctxJson','ctxActualizar','ctxConsulta','ctxLimite','ctxLongitud','ctxLatitud',...Object.values(sourceIDs),...Object.values(derivedIDs)])$(id).disabled=busy||!docs;
  $('ctxArchivos').disabled=busy||!docs||$('ctxTipo').value!=='corpus';$('ctxConfirmar').disabled=busy||!docs;
  $('ctxRegistrar').disabled=busy||!docs||!['corpus','sitio','reglas'].includes($('ctxTipo').value)||!$('ctxJson').value.trim()||!$('ctxConfirmar').checked;
  $('ctxVincular').disabled=busy||!result;
  $('ctxRecuperar').disabled=busy||!source('corpus')||!$('ctxConsulta').value.trim()||!$('ctxLimite').value||($('ctxVincular').checked&&!result);
  $('ctxConsultarSitio').disabled=busy||!source('sitio')||!$('ctxLongitud').value.trim()||!$('ctxLatitud').value.trim()||($('ctxVincular').checked&&!result);
  $('ctxEvaluar').disabled=busy||!source('reglas')||!result;
 };
 function fail(error){$('ctxEstado').textContent=error.message;message(error.message,true);}
 async function act(fn){const own=ticket,chosen=selection,epoch=resultEpoch,caso=docs?.caso,fp=docs?.expediente_sha256;try{await fn(own,caso,fp);}catch(error){if(fresh(own,caso,fp)&&chosen===selection&&epoch===resultEpoch)fail(error);}}
 function clear(){ticket++;listSeq++;selection++;resultEpoch++;result=null;versions={};derived={};reads={};for(const id of Object.values({...sourceIDs,...Object.fromEntries(Object.entries(derivedIDs).map(([k,v])=>['d'+k,v]))}))options($(id),[['','Sin selección']]);
  for(const id of ['ctxTipo','ctxJson','ctxArchivos','ctxConsulta','ctxLimite','ctxLongitud','ctxLatitud'])$(id).value='';$('ctxVincular').checked=false;$('ctxConfirmar').checked=false;$('ctxEstado').textContent='Contexto declarado: selecciona versiones y consulta explícitamente.';$('ctxResultado').textContent='Sin resultado seleccionado.';render();publish();
 }
 function check(value,caso,fp,id){if(value.id!==id||value.caso!==caso||value.expediente_sha256!==fp||value.aprueba_resultados!==false||value.aprueba_informe!==false)throw Error('Contexto ajeno o contrato no verificable.');}
 async function openSource(tipo){const own=ticket,caso=docs?.caso,fp=docs?.expediente_sha256,id=$(sourceIDs[tipo]).value,seq=reads[tipo]=(reads[tipo]||0)+1;delete versions[tipo];render();if(!id||!caso)return;
  try{const res=await api('/api/contexto/version?'+query({tipo,version:id})),value=await res.json();if(!fresh(own,caso,fp)||reads[tipo]!==seq||$(sourceIDs[tipo]).value!==id)return;
   check(value,caso,fp,id);if(value.tipo!==tipo||value.utilizable!==true||!/^[0-9a-f]{64}$/.test(value.huella||'')||value.verificacion_profesional!==false||value.identidad_revisor!=='declarada_no_verificada')throw Error('Versión de contexto sin verificación declarada.');versions[tipo]=value;$('ctxEstado').textContent='Contexto comprobado · revisión declarada, no autenticada.';render();
  }catch(error){if(fresh(own,caso,fp)&&reads[tipo]===seq)fail(error);}
 }
 async function openDerived(tipo,clearSelection=true){const own=ticket,caso=docs?.caso,fp=docs?.expediente_sha256,id=$(derivedIDs[tipo]).value,key='d'+tipo,seq=reads[key]=(reads[key]||0)+1,epoch=resultEpoch;if(clearSelection||!id){delete derived[tipo];publish();render();}if(!id||!caso)return;
  try{const res=await api('/api/contexto/derivado?'+query({version:id})),value=await res.json();if(!fresh(own,caso,fp)||reads[key]!==seq||$(derivedIDs[tipo]).value!==id||epoch!==resultEpoch)return;
   check(value,caso,fp,id);if(value.tipo!==tipo||value.vigente!==true||value.reproducido!==true||!/^[0-9a-f]{64}$/.test(value.sha256_salida||'')||value.conformidad_normativa!=='no_evaluada')throw Error('Consulta sin vigencia reproducible.');
   const linked=value.fuentes?.resultado;if(linked&&(!result||linked.id!==result.id||linked.huella!==result.huella))throw Error('El derivado corresponde a otros resultados o huella.');if(tipo==='evaluacion'&&!linked)throw Error('Evaluación sin resultado vinculado.');
   derived[tipo]=value;const siteNote=tipo==='sitio'?{limite:' · FRANJA INCIERTA: no confirma pertenencia ni asigna zona',ambiguo:' · varias zonas: sin asignación',sin_cobertura:' · fuera de cobertura: sin zona por cercanía',dentro:' · pertenencia puntual sin frontera próxima; no es certeza territorial ni geotecnia'}[value.salida?.estado]||'':'';
   $('ctxEstado').textContent='Consulta '+id+' reproducida · '+tipo+' · '+(value.datos_sinteticos?'DATOS SINTÉTICOS':'procedencia declarada')+siteNote+' · sin conformidad normativa.';render();publish();
  }catch(error){if(fresh(own,caso,fp)&&reads[key]===seq&&epoch===resultEpoch){delete derived[tipo];render();publish();fail(error);}}
 }
 async function listing(preferred){const own=ticket,caso=docs?.caso,fp=docs?.expediente_sha256,seq=++listSeq,chosen=selection;if(!caso)return;
  try{const res=await api('/api/contexto/historial?'+query({})),value=await res.json();if(!fresh(own,caso,fp)||seq!==listSeq||chosen!==selection)return;
   if(value.caso!==caso||value.expediente_sha256!==fp)throw Error('Historial de otro expediente.');
   for(const [tipo,id]of Object.entries(sourceIDs)){const selected=preferred?.tipo===tipo?preferred.id:$(id).value,rows=value[tipo];options($(id),[['','Selecciona '+tipo],...rows.map(v=>[v.id,v.id+(v.vigente?' · vigente':' · sin vigencia')])]);if(rows.some(v=>v.id===selected&&v.vigente))$(id).value=selected;else delete versions[tipo];}
   for(const [tipo,id]of Object.entries(derivedIDs)){const selected=preferred?.derivado===tipo?preferred.id:$(id).value,rows=value.derivados.filter(v=>v.tipo===tipo||v.vigente===false);options($(id),[['','Sin selección explícita'],...rows.map(v=>[v.id,v.id+(v.vigente?' · '+tipo:' · sin vigencia')])]);if(rows.some(v=>v.id===selected&&v.vigente))$(id).value=selected;else delete derived[tipo];}
   publish();render();await Promise.all([...Object.keys(sourceIDs).map(openSource),...Object.keys(derivedIDs).map(tipo=>openDerived(tipo,false))]);
  }catch(error){if(fresh(own,caso,fp)&&seq===listSeq&&chosen===selection){versions={};derived={};render();publish();fail(error);}}
 }
 // 293: sin consulta automática al cambiar de expediente; Actualizar consulta y verifica (clear() invalida respuestas previas).
 window.addEventListener('d2m-case',()=>{clear();if(docs)$('ctxEstado').textContent='Historial sin consultar: seleccionar el expediente no lo comprueba. Pulsa Actualizar para consultarlo y verificarlo.';});
 window.addEventListener('d2m-result',event=>{const detail=event.detail,value=detail?.record,next=value&&value.caso===docs?.caso&&value.expediente_sha256===docs.expediente_sha256&&value.vigente!==false?{id:detail.version,huella:value.huella}:null;
  if(JSON.stringify(next)===JSON.stringify(result))return;result=next;resultEpoch++;derived={};for(const id of Object.values(derivedIDs))$(id).value='';$('ctxVincular').checked=false;$('ctxResultado').textContent=result?'Resultado '+result.id+' · huella '+result.huella:'Sin resultado seleccionado.';render();publish();
 });
 for(const tipo of Object.keys(sourceIDs))$(sourceIDs[tipo]).onchange=()=>{selection++;return openSource(tipo);};
 for(const tipo of Object.keys(derivedIDs))$(derivedIDs[tipo]).onchange=()=>{selection++;return openDerived(tipo);};
 for(const id of ['ctxTipo','ctxJson','ctxArchivos'])$(id).addEventListener('input',()=>{$('ctxConfirmar').checked=false;window.contextControls();});
 for(const id of ['ctxConfirmar','ctxVincular','ctxConsulta','ctxLimite','ctxLongitud','ctxLatitud'])$(id).addEventListener('input',window.contextControls);
 $('ctxActualizar').onclick=()=>action(async()=>{const own=ticket,caso=docs?.caso,fp=docs?.expediente_sha256;await listing();if(fresh(own,caso,fp)){if($('ctxEstado').textContent==='Historial sin consultar: seleccionar el expediente no lo comprueba. Pulsa Actualizar para consultarlo y verificarlo.')$('ctxEstado').textContent='Historial consultado y comprobado.';message('Historial de contexto actualizado.',false);}});
 $('ctxRegistrar').onclick=()=>action(()=>act(async(own,caso,fp)=>{
  const tipo=$('ctxTipo').value,raw=$('ctxJson').value,chosen=selection;if(!docs||!['corpus','sitio','reglas'].includes(tipo)||!$('ctxConfirmar').checked)throw Error('Selecciona el contrato y confirma su declaración explícita.');if(new Blob([raw]).size>1024*1024)throw Error('Contrato JSON de hasta 1 MiB.');JSON.parse(raw);const body={caso,expediente_sha256:fp};
  if(tipo==='corpus'){const files=Array.from($('ctxArchivos').files);if(!files.length||files.length>20||files.some(f=>f.size>4*1024*1024)||files.reduce((n,f)=>n+f.size,0)>16*1024*1024)throw Error('Corpus: 1–20 archivos, 4 MiB cada uno y 16 MiB total.');const names=new Set();for(const file of files){if(!/^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$/.test(file.name)||file.name.includes('..')||['version.json','corpus.json','capa.json','reglas.json','salida.json'].includes(file.name)||names.has(file.name))throw Error('Nombres de corpus simples, únicos y no reservados.');names.add(file.name);}
   body.manifiesto_json=raw;body.archivos=[];for(const file of files){const bytes=new Uint8Array(await file.arrayBuffer());if(bytes.length!==file.size)throw Error('El documento cambió de tamaño al leerlo.');let binary='';for(let i=0;i<bytes.length;i+=32768)binary+=String.fromCharCode(...bytes.subarray(i,i+32768));body.archivos.push({nombre:file.name,contenido_base64:btoa(binary)});}
  }else body[tipo==='sitio'?'capa_json':'reglas_json']=raw;
  if(!fresh(own,caso,fp)||selection!==chosen||$('ctxJson').value!==raw||$('ctxTipo').value!==tipo)return;$('ctxConfirmar').checked=false;window.contextControls();const res=await api('/api/contexto/'+tipo+'/registrar',body),value=await res.json();if(fresh(own,caso,fp)&&selection===chosen){await listing({tipo,id:value.id});message('Contexto ('+tipo+') registrado correctamente: '+value.id,false);}
 }));
 async function derive(tipo){return act(async(own,caso,fp)=>{const epoch=resultEpoch,chosen=selection,body={caso,expediente_sha256:fp};let route;
  if(tipo==='evaluacion'){const rule=source('reglas');if(!rule||!result)throw Error('Selecciona reglas y resultados comprobados.');Object.assign(body,{resultado:result.id,reglas:rule.id,huella_resultados:result.huella,huella_reglas:rule.huella});route='evaluar';}
  else{if($('ctxVincular').checked&&!result)throw Error('Selecciona el resultado a vincular.');body.resultado=$('ctxVincular').checked?result.id:null;
   if(tipo==='recuperacion'){const corpus=source('corpus'),consulta=$('ctxConsulta').value,limite=Number($('ctxLimite').value);if(!corpus||!consulta.trim()||consulta.length>500||!Number.isInteger(limite)||limite<1||limite>20)throw Error('Selecciona corpus, consulta y límite explícitos.');Object.assign(body,{corpus:corpus.id,consulta,limite});route='recuperar';}
   else{const layer=source('sitio'),lon=$('ctxLongitud').value,lat=$('ctxLatitud').value;if(!layer||!lon.trim()||!lat.trim()||!Number.isFinite(Number(lon))||!Number.isFinite(Number(lat)))throw Error('Selecciona sitio y coordenadas explícitas.');Object.assign(body,{sitio:layer.id,longitud:Number(lon),latitud:Number(lat)});route='consultar-sitio';}}
  const res=await api('/api/contexto/'+route,body),value=await res.json();if(fresh(own,caso,fp)&&epoch===resultEpoch&&chosen===selection){await listing({derivado:tipo,id:value.id});message('Derivación de contexto completada: '+value.id,false);}
 });}
 $('ctxRecuperar').onclick=()=>action(()=>derive('recuperacion'));$('ctxConsultarSitio').onclick=()=>action(()=>derive('sitio'));$('ctxEvaluar').onclick=()=>action(()=>derive('evaluacion'));clear();
})();
