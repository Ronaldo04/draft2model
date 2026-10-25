'use strict';
(()=>{
 let key=null;
 const fields=['ingresoCaso','ingresoArchivos','ingresoAutorizado','ingresoReferencia'];
 window.intakeControls=()=>{for(const id of [...fields,'ingresoRegistrar'])$(id).disabled=busy;};
 for(const id of fields)$(id).addEventListener('input',()=>{key=null;});
 function encode(file){return new Promise((resolve,reject)=>{
  const reader=new FileReader();reader.onerror=()=>reject(Error('No se pudo leer el archivo seleccionado.'));
  reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.readAsDataURL(file);
 });}
 $('ingresoForm').onsubmit=event=>{event.preventDefault();action(async()=>{
  if(!$('ingresoForm').reportValidity()||!$('ingresoAutorizado').checked)throw Error('Declara el uso autorizado de los originales.');
  const files=Array.from($('ingresoArchivos').files||[]);
  if(!files.length||files.length>20||files.some(f=>!f.size||f.size>16*1024*1024)||files.reduce((s,f)=>s+f.size,0)>48*1024*1024)throw Error('Selecciona de 1 a 20 archivos, hasta 16 MiB por archivo y 48 MiB en total.');
  const caso=$('ingresoCaso').value.trim();key??=crypto.randomUUID().replaceAll('-','');
  $('ingresoEstado').textContent='Registrando originales y preparando revisión documental local…';
  const archivos=[];for(const file of files)archivos.push({nombre:file.name,contenido_base64:await encode(file)});
  const res=await api('/api/ingreso/registrar',{caso,clave_solicitud:key,uso_autorizado:true,provisional_fuera_alcance:$('ingresoReferencia').checked,archivos});
  const result=await res.json();$('ingresoEstado').textContent='Expediente '+result.caso+' registrado · '+result.resumen.paginas_renderizadas+' página(s) preparada(s) · '+result.resumen.archivos_con_error+' archivo(s) con error documental · revisión humana pendiente.';
  const list=await api('/api/casos'),data=await list.json();options($('caso'),[['','Selecciona un expediente'],...data.casos.map(c=>[c.id,c.id])]);
  $('caso').value=result.caso;await openCase();
 });};
 window.intakeControls();
})();
