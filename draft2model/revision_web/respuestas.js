'use strict';
(()=>{
 let ticket=0,reading=0,listing=0,fileRead=0,packet=null,current=null;
 const same=(own,caso,fp)=>own===ticket&&docs?.caso===caso&&docs.expediente_sha256===fp;
 const query=extra=>new URLSearchParams({caso:docs.caso,expediente_sha256:docs.expediente_sha256,...extra});
 const cuarentenaTexto=v=>{const q=v.candidatos_en_cuarentena||0,cob=(v.cobertura||[]).filter(c=>c.efectiva);return (q?' · '+q+' candidato(s) en cuarentena, sin corregir':'')+(cob.length?' · Cobertura efectiva: '+cob.map(c=>c.recorte_id.slice(0,8)+' '+c.efectiva.recuperados+'/'+c.efectiva.candidatos_declarados+' ('+c.efectiva.estado+'; declarada '+c.estado+')').join('; '):'');};
 const declared=()=>['prueba','expediente'].includes($('respuestaModo').value)&&$('respuestaProveedor').value.trim()&&$('respuestaModelo').value.trim()&&$('respuestaJson').value.trim();
 window.responseControls=()=>{
  for(const id of ['respuestaArchivo','respuestaJson','respuestaProveedor','respuestaModelo','respuestaModo','respuestaCuarentena'])$(id).disabled=busy||!packet;
  for(const id of ['respuestaVersion','respuestaActualizar'])$(id).disabled=busy||!docs;
  $('respuestaRegistrar').disabled=busy||!packet||!declared();
  $('respuestaConfirmar').disabled=busy||!current?.traslado_permitido;
  $('respuestaImportar').disabled=busy||!current?.traslado_permitido||!$('respuestaConfirmar').checked;
 };
 function reset(){current=null;$('respuestaConfirmar').checked=false;$('respuestaDetalle').textContent='';$('respuestaEstado').textContent='Sin respuesta seleccionada.';window.responseControls();}
 function fail(error){$('respuestaEstado').textContent=error.message;message(error.message,true);}
 function clear(){ticket++;reading++;listing++;fileRead++;packet=null;reset();for(const id of ['respuestaJson','respuestaProveedor','respuestaModelo','respuestaModo','respuestaArchivo'])$(id).value='';$('respuestaCuarentena').checked=false;$('respuestaPaquete').textContent='Sin paquete seleccionado.';options($('respuestaVersion'),[['','Selecciona respuesta']]);window.responseControls();}
 async function act(fn){const own=ticket,caso=docs?.caso,fp=docs?.expediente_sha256;try{await fn(own,caso,fp);}catch(error){if(same(own,caso,fp))fail(error);}}
 async function open(){const seq=++reading,own=ticket,caso=docs?.caso,fp=docs?.expediente_sha256,id=$('respuestaVersion').value;reset();if(!caso||!id)return;
  try{const res=await api('/api/respuesta?'+query({version:id})),value=await res.json();
   if(!same(own,caso,fp)||seq!==reading||$('respuestaVersion').value!==id)return;
   const origin=value.origen==='respuesta_local_declarada'?value.transmision_externa===false&&value.llamada_real_acreditada!==true:
    value.origen==='proveedor_verificado'&&/^[0-9a-f]{32}$/.test(value.trabajo_proveedor||'')&&typeof value.llamada_real_acreditada==='boolean'&&value.transmision_externa===value.llamada_real_acreditada&&(!value.modo_prueba||!value.llamada_real_acreditada);
   if(value.id!==id||value.caso!==caso||value.expediente_sha256!==fp||value.estado!=='pendiente_revision'||value.aprueba_ingenieria!==false||typeof value.modo_prueba!=='boolean'||!origin)throw Error('Respuesta ajena o sin comprobación de origen.');
   current=value;$('respuestaDetalle').textContent=JSON.stringify(value,null,2);
   $('respuestaEstado').textContent=(value.modo_prueba?'PRUEBA SINTÉTICA · sin traslado. ':value.origen==='proveedor_verificado'?'Proveedor verificado · trabajo '+value.trabajo_proveedor+'. ':'Respuesta local declarada del expediente. ')+value.proveedor_declarado+' / '+value.modelo_declarado+' · extracción pendiente, sin aprobación · '+(value.llamada_real_acreditada?'transmisión real acreditada por evidencia local.':'sin transmisión real acreditada.')+cuarentenaTexto(value);window.responseControls();
  }catch(error){if(same(own,caso,fp)&&seq===reading)fail(error);}
 }
 async function list(preferred){const seq=++listing,opened=reading,own=ticket,caso=docs?.caso,fp=docs?.expediente_sha256;if(!caso)return;
  const res=await api('/api/respuestas?'+query({})),value=await res.json();if(!same(own,caso,fp)||seq!==listing||opened!==reading)return;
  const id=preferred||$('respuestaVersion').value;options($('respuestaVersion'),[['','Selecciona respuesta'],...value.versiones.map(v=>[v.id,v.id+(v.vigente?' · pendiente':' · sin vigencia')])]);
  if(value.versiones.some(v=>v.id===id&&v.vigente)){$('respuestaVersion').value=id;if(preferred)await open();}
  else{reading++;reset();}window.responseControls();
 }
 window.addEventListener('d2m-case',()=>{clear();if(docs)act(()=>list());});
 window.addEventListener('d2m-response-created',event=>{const value=event.detail;if(value?.caso===docs?.caso&&value.expediente_sha256===docs?.expediente_sha256&&value.origen==='proveedor_verificado'&&value.estado==='pendiente_revision'&&value.aprueba_ingenieria===false)act(()=>list(value.id));});
 window.addEventListener('d2m-visual-package',event=>{
  const value=event.detail,valid=value&&value.caso===docs?.caso&&value.expediente_sha256===docs?.expediente_sha256&&value.estado==='preparado_sin_envio'&&value.transmision_externa===false&&value.aprueba_ingenieria===false;
  const next=valid?value:null;if(packet?.id!==next?.id||packet?.sha256_solicitud!==next?.sha256_solicitud){ticket++;fileRead++;$('respuestaJson').value='';$('respuestaArchivo').value='';$('respuestaConfirmar').checked=false;}
  packet=next;$('respuestaPaquete').textContent=packet?'Paquete '+packet.id+' · solicitud '+packet.solicitud_id+' · SHA256 '+packet.sha256_solicitud:'Sin paquete seleccionado.';window.responseControls();
 });
 $('respuestaVersion').onchange=open;$('respuestaActualizar').onclick=()=>action(()=>act(()=>list()));
 for(const id of ['respuestaJson','respuestaProveedor','respuestaModelo','respuestaModo'])$(id).addEventListener('input',()=>{$('respuestaConfirmar').checked=false;window.responseControls();});
 $('respuestaConfirmar').addEventListener('input',window.responseControls);
 $('respuestaArchivo').onchange=()=>act(async(own,caso,fp)=>{const seq=++fileRead,selected=packet,file=$('respuestaArchivo').files[0];if(!file||!selected)return;if(file.size>1536*1024)throw Error('El JSON admite hasta 1.5 MiB.');const raw=await file.text();if(!same(own,caso,fp)||seq!==fileRead||packet!==selected)return;JSON.parse(raw);$('respuestaJson').value=raw;$('respuestaConfirmar').checked=false;window.responseControls();});
 $('respuestaRegistrar').onclick=()=>action(()=>act(async(own,caso,fp)=>{
  const selected=packet;if(!selected||!declared())throw Error('Selecciona paquete vigente, JSON, proveedor, modelo y procedencia explícitos.');
  const raw=$('respuestaJson').value;if(new Blob([raw]).size>1536*1024)throw Error('El JSON admite hasta 1.5 MiB.');JSON.parse(raw);
  const body={caso,expediente_sha256:fp,paquete:selected.id,respuesta_json:raw,proveedor_declarado:$('respuestaProveedor').value,modelo_declarado:$('respuestaModelo').value,modo_prueba:$('respuestaModo').value==='prueba'};if($('respuestaCuarentena').checked)body.cuarentena=true;
  const res=await api('/api/respuesta/registrar',body),value=await res.json();if(same(own,caso,fp)&&packet===selected)await list(value.id);
 }));
 $('respuestaImportar').onclick=()=>action(()=>act(async(own,caso,fp)=>{
  const selected=current;if(!selected?.traslado_permitido||!$('respuestaConfirmar').checked)throw Error('Selecciona una extracción trasladable y confirma su huella exacta.');
  $('respuestaConfirmar').checked=false;window.responseControls();const res=await api('/api/respuesta/importar',{caso,expediente_sha256:fp,respuesta:selected.id,sha256_extraccion:selected.sha256_extraccion,confirmacion_explicita:true}),value=await res.json();
  if(!same(own,caso,fp)||current!==selected)return;if(value.caso!==caso||value.estado!=='pendiente_revision'||value.aprueba_ingenieria!==false)throw Error('Importación sin comprobación de estado pendiente.');
  $('respuestaEstado').textContent='Extracción '+value.extraccion+' importada para revisión, sin aprobación.';window.dispatchEvent(new CustomEvent('d2m-extraction-created',{detail:{...value,expediente_sha256:fp}}));
 }));clear();
})();
