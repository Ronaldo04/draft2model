'use strict';
(()=>{
 // Contingencia tabular supervisada: crear no importa; importar es otra acción confirmada sobre versión+huella exactas.
 const CSV=['niveles.csv','nodos.csv','muros.csv'],CSV02=[...CSV,'vertices.csv','superficies.csv'],CSV03=[...CSV02,'aberturas.csv'],MAX_META=256*1024,MAX_CSV=4*1024*1024,MAX_XLSX=16*1024*1024;
 let ticket=0,read=0,listRead=0,current=null;
 const same=(own,caso,fp)=>own===ticket&&caso===docs?.caso&&fp===docs?.expediente_sha256;
 const query=extra=>new URLSearchParams({caso:docs.caso,expediente_sha256:docs.expediente_sha256,...extra});
 const files=id=>Array.from($(id).files||[]);
 const importable=()=>current&&current.vigente!==false&&current.estado==='borrador'&&current.aprobacion===null&&current.importacion?.estado!=='interrumpida';
 window.tabularControls=()=>{
  for(const id of ['tabularMetadatos','tabularFormato','tabularArchivos','tabularVersion','tabularActualizar'])$(id).disabled=busy||!docs;
  $('tabularRegistrar').disabled=busy||!docs||!files('tabularMetadatos').length||!files('tabularArchivos').length;
  $('tabularConfirmar').disabled=busy||!importable();
  $('tabularImportar').disabled=busy||!importable()||!$('tabularConfirmar').checked;
 };
 function reset(){current=null;$('tabularConfirmar').checked=false;$('tabularDetalle').textContent='';window.tabularControls();}
 function clear(){ticket++;read++;listRead++;reset();options($('tabularVersion'),[['','Sin versión tabular seleccionada']]);
  $('tabularEstado').textContent=docs?'Adjunta metadatos y tablas, o selecciona una versión conservada.':'Selecciona un expediente.';window.tabularControls();}
 function error(err){$('tabularEstado').textContent=err.message;message(err.message,true);}
 function selection(){
  // Validar nombres y tamaños antes de leer contenido.
  const meta=files('tabularMetadatos'),tables=files('tabularArchivos'),formato=$('tabularFormato').value;
  if(meta.length!==1||!meta[0].name.toLowerCase().endsWith('.json')||!meta[0].size||meta[0].size>MAX_META)throw Error('Adjunta un único JSON de metadatos de hasta 256 KiB.');
  if(formato==='csv'){
   if(![CSV,CSV02,CSV03].some(names=>tables.length===names.length&&[...tables.map(f=>f.name)].sort().join()===[...names].sort().join()))throw Error('CSV requiere exactamente niveles.csv, nodos.csv y muros.csv; para 0.2 añade vertices.csv y superficies.csv; para 0.3 añade también aberturas.csv.');
   if(tables.some(f=>!f.size||f.size>MAX_CSV))throw Error('Cada CSV debe tener contenido y hasta 4 MiB.');
  }else if(formato==='xlsx'){
   if(tables.length!==1||!tables[0].name.toLowerCase().endsWith('.xlsx'))throw Error('XLSX requiere exactamente un libro .xlsx.');
   if(!tables[0].size||tables[0].size>MAX_XLSX)throw Error('El libro XLSX debe tener contenido y hasta 16 MiB.');
  }else throw Error('Formato no admitido.');
  if(tables.some(f=>!/^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$/.test(f.name)||f.name.includes('..')))throw Error('Usa nombres de archivo simples.');
  return {meta:meta[0],tables,formato};
 }
 async function base64(file){
  const bytes=new Uint8Array(await file.arrayBuffer());let text='';
  for(let i=0;i<bytes.length;i+=0x8000)text+=String.fromCharCode(...bytes.subarray(i,i+0x8000));
  return btoa(text);
 }
 function show(value){
  current=value;$('tabularConfirmar').checked=false;
  $('tabularDetalle').textContent=JSON.stringify({huella_tabular:value.huella_tabular,formato:value.formato,nombre_original:value.nombre_original,
   version_contrato:value.version_contrato,archivos:value.archivos,resumen:value.resumen,importacion:value.importacion,geometria_propuesta:value.geometria},null,2);
  const imp=value.importacion;
  $('tabularEstado').textContent='Versión tabular '+value.id+' comprobada · contingencia tabular supervisada · geometría borrador sin aprobación'
   +(imp?.estado==='importada'?' · ya importada como geometría '+imp.geometria+'.':imp?.estado==='interrumpida'?' · importación interrumpida: requiere revisión, no se repite.':'. Importarla requiere otra acción confirmada.');
  window.tabularControls();
 }
 async function open(){
  const seq=++read,own=ticket,caso=docs?.caso,fp=docs?.expediente_sha256,id=$('tabularVersion').value;reset();if(!caso||!id)return;
  try{const res=await api('/api/tabular/version?'+query({version:id})),value=await res.json();
   if(!same(own,caso,fp)||read!==seq||$('tabularVersion').value!==id)return;
   if(value.caso!==caso||value.expediente_sha256!==fp||value.id!==id||value.estado!=='borrador'||value.aprobacion!==null||value.aprueba_geometria!==false)
    throw Error('Versión tabular sin vigencia o ajena a la selección.');
   show(value);
  }catch(err){if(same(own,caso,fp)&&read===seq)error(err);}
 }
 async function listing(preferred){
  const seq=++listRead,own=ticket,caso=docs?.caso,fp=docs?.expediente_sha256;if(!caso)return;
  const res=await api('/api/tabular/historial?'+query({})),value=await res.json();if(!same(own,caso,fp)||listRead!==seq)return;
  const selected=preferred||$('tabularVersion').value;
  options($('tabularVersion'),[['',value.versiones.length?'Selecciona versión tabular':'Sin versiones tabulares'],
   ...value.versiones.map(v=>[v.id,v.id+(v.vigente?' · '+v.formato+' · borrador'+(v.importacion?.estado==='importada'?' · importada':''):' · sin vigencia')])]);
  if(value.versiones.some(v=>v.id===selected&&v.vigente)){$('tabularVersion').value=selected;await open();}
  else{read++;reset();}window.tabularControls();
 }
 async function act(fn){const own=ticket,caso=docs?.caso,fp=docs?.expediente_sha256;try{await fn(own,caso,fp);}catch(err){if(same(own,caso,fp))error(err);}}
 window.addEventListener('d2m-case',()=>{clear();if(docs)act(()=>listing());});
 for(const id of ['tabularMetadatos','tabularFormato','tabularArchivos'])$(id).addEventListener('change',window.tabularControls);
 $('tabularVersion').onchange=open;$('tabularConfirmar').addEventListener('input',window.tabularControls);
 $('tabularActualizar').onclick=()=>action(()=>act(()=>listing()));
 $('tabularRegistrar').onclick=()=>action(()=>act(async(own,caso,fp)=>{
  const {meta,tables,formato}=selection();
  const metadatos_json=await meta.text();
  let metadata;try{metadata=JSON.parse(metadatos_json);}catch{throw Error('Los metadatos no son JSON válido.');}
  const expected=metadata?.version_contrato==='0.3.0'?CSV03:(metadata?.version_contrato==='0.2.0'?CSV02:CSV);
  if(formato==='csv'&&[...tables.map(f=>f.name)].sort().join()!==[...expected].sort().join())throw Error('Las tablas no corresponden a version_contrato declarada en metadatos.');
  const archivos=[];for(const file of tables)archivos.push({nombre:file.name,contenido_base64:await base64(file)});
  if(!same(own,caso,fp))return;
  const res=await api('/api/tabular/crear',{caso,expediente_sha256:fp,metadatos_json,formato,archivos}),value=await res.json();
  if(!same(own,caso,fp))return;
  if(value.estado!=='borrador'||value.aprobacion!==null||value.importacion!==null)throw Error('Registro tabular sin comprobación de borrador.');
  $('tabularMetadatos').value='';$('tabularArchivos').value='';await listing(value.id);
 }));
 $('tabularImportar').onclick=()=>action(()=>act(async(own,caso,fp)=>{
  if(!importable()||!$('tabularConfirmar').checked)throw Error('Selecciona una versión comprobada y confirma importar el borrador.');
  const selected=current;$('tabularConfirmar').checked=false;window.tabularControls();
  const res=await api('/api/tabular/importar',{caso,expediente_sha256:fp,version:selected.id,huella_tabular:selected.huella_tabular,confirmacion_explicita:true}),value=await res.json();
  if(!same(own,caso,fp)||current!==selected)return;
  if(value.caso!==caso||value.expediente_sha256!==fp||value.tabular!==selected.id||value.estado!=='borrador'||value.aprobacion!==null
     ||value.disponible_para_modelado!==false||value.aprueba_geometria!==false)throw Error('Importación sin comprobación de borrador.');
  $('tabularEstado').textContent='Geometría '+value.geometria+' importada como borrador desde la versión tabular, sin aprobación ni disponibilidad para modelado.';
  window.dispatchEvent(new CustomEvent('d2m-geometry-created',{detail:value}));
  await listing(selected.id);
 }));clear();
})();
