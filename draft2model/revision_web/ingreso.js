'use strict';
(()=>{
 let key=null;
 const fields=['ingresoCaso','ingresoArchivos','ingresoAutorizado','ingresoReferencia'];
 window.intakeControls=()=>{for(const id of [...fields,'ingresoRegistrar'])$(id).disabled=busy;};
 for(const id of fields)$(id).addEventListener('input',()=>{key=null;});

 function sanitizeCaseId(text){
  return (text||'')
   .trim()
   .normalize('NFD').replace(/[\u0300-\u036f]/g,'')
   .replace(/\s+/g,'-')
   .replace(/[^A-Za-z0-9_-]/g,'')
   .replace(/-+/g,'-')
   .slice(0,64);
 }

 function encode(file){return new Promise((resolve,reject)=>{
  const reader=new FileReader();reader.onerror=()=>reject(Error('No se pudo leer el archivo seleccionado.'));
  reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.readAsDataURL(file);
 });}

 // Browser UI enhancements (safe when running in real DOM, ignored in headless node vm)
 if(typeof document!=='undefined'){
  const dropZone=document.getElementById('intakeDropZone');
  const fileInput=document.getElementById('ingresoArchivos');
  const listCont=document.getElementById('intakeFileList');
  const ulList=document.getElementById('intakeFilesUl');
  const countSpan=document.getElementById('intakeFileCount');
  const resetBtn=document.getElementById('intakeResetFiles');
  const casoInput=document.getElementById('ingresoCaso');

  if(casoInput){
   casoInput.addEventListener('blur',()=>{
    const clean=sanitizeCaseId(casoInput.value);
    if(clean)casoInput.value=clean;
   });
  }

  function updateFilesUI(){
   const files=Array.from(fileInput?.files||[]);
   if(!listCont||!ulList)return;
   if(!files.length){
    listCont.hidden=true;
    ulList.innerHTML='';
    return;
   }
   listCont.hidden=false;
   if(countSpan)countSpan.textContent=files.length+(files.length===1?' lámina seleccionada':' láminas seleccionadas');
   ulList.innerHTML='';
   files.forEach(f=>{
    const isPdf=f.name.toLowerCase().endsWith('.pdf');
    const li=document.createElement('li');
    li.className='file-item-card';
    const mb=(f.size/(1024*1024)).toFixed(2);
    li.innerHTML=`<div class="file-card-type ${isPdf?'pdf':'img'}">${isPdf?'PDF':'IMG'}</div><div class="file-card-info"><strong class="file-card-name" title="${f.name}">${f.name}</strong><small class="file-card-size">${mb} MB</small></div><span class="file-card-badge">Listo</span>`;
    ulList.append(li);
   });
  }

  if(dropZone&&fileInput){
   ['dragenter','dragover'].forEach(n=>{
    dropZone.addEventListener(n,e=>{e.preventDefault();dropZone.classList.add('drag-active');});
   });
   ['dragleave','drop'].forEach(n=>{
    dropZone.addEventListener(n,e=>{e.preventDefault();dropZone.classList.remove('drag-active');});
   });
   dropZone.addEventListener('drop',e=>{
    if(e.dataTransfer?.files?.length){
     fileInput.files=e.dataTransfer.files;
     key=null;
     updateFilesUI();
    }
   });
   fileInput.addEventListener('change',()=>{key=null;updateFilesUI();});
  }

  if(resetBtn&&fileInput){
   resetBtn.addEventListener('click',()=>{
    fileInput.value='';
    key=null;
    updateFilesUI();
    if(typeof message==='function')message('Selección de láminas restablecida.');
   });
  }
 }

 $('ingresoForm').onsubmit=event=>{event.preventDefault();action(async()=>{
  const rawCaso=$('ingresoCaso').value.trim();
  const caso=sanitizeCaseId(rawCaso);
  if(!caso)throw Error('Ingresa un nombre o código válido para el proyecto (por ejemplo: proyecto-01).');
  $('ingresoCaso').value=caso;

  if(!$('ingresoForm').reportValidity()||!$('ingresoAutorizado').checked)throw Error('Declara el uso autorizado de los originales.');
  const files=Array.from($('ingresoArchivos').files||[]);
  if(!files.length||files.length>20||files.some(f=>!f.size||f.size>16*1024*1024)||files.reduce((s,f)=>s+f.size,0)>48*1024*1024)throw Error('Selecciona de 1 a 20 archivos, hasta 16 MiB por archivo y 48 MiB en total.');
  key??=crypto.randomUUID().replaceAll('-','');
  
  const statusBox=typeof document!=='undefined'?document.getElementById('intakeStatusBox'):null;
  const spinner=typeof document!=='undefined'?document.getElementById('intakeSpinner'):null;
  if(statusBox){statusBox.className='intake-status-card processing';statusBox.hidden=false;}
  if(spinner)spinner.hidden=false;

  $('ingresoEstado').textContent='Procesando láminas y generando vistas previas en alta resolución…';
  
  try{
   const archivos=[];for(const file of files)archivos.push({nombre:file.name,contenido_base64:await encode(file)});
   const res=await api('/api/ingreso/registrar',{caso,clave_solicitud:key,uso_autorizado:true,provisional_fuera_alcance:$('ingresoReferencia').checked,archivos});
   const result=await res.json();
   if(spinner)spinner.hidden=true;
   if(statusBox)statusBox.className='intake-status-card success';
   $('ingresoEstado').textContent='Proyecto '+result.caso+' registrado · '+result.resumen.paginas_renderizadas+' lámina(s) preparada(s) en alta resolución · '+result.resumen.archivos_con_error+' archivo(s) con error documental · revisión humana pendiente para interpretación estructural.';
   const list=await api('/api/casos'),data=await list.json();options($('caso'),[['','Selecciona un expediente'],...data.casos.map(c=>[c.id,c.id])]);
   $('caso').value=result.caso;await openCase();
   if(typeof message==='function')message('Proyecto '+result.caso+' registrado correctamente con '+result.resumen.paginas_renderizadas+' lámina(s).');
  }catch(err){
   if(spinner)spinner.hidden=true;
   if(statusBox){
    statusBox.className='intake-status-card error';
    statusBox.hidden=false;
   }
   $('ingresoEstado').textContent=err?.message||'No se pudo registrar el proyecto. Verifica los archivos seleccionados.';
   throw err;
  }
 });};
 window.intakeControls();
})();
