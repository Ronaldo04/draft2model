'use strict';
(()=>{
 let current=null, ticket=0;
 // -- Malla 0.4: preparación reproducible de solo lectura (sin escribir políticas ni inferir apoyos/diafragmas) --
 let malla=null,mallaTicket=0;
 const DESARROLLO=['0.2.0','0.3.0'],MALLA='0.4.0',LIQUIDOS='0.5.0';
 const esMalla=()=>[MALLA,LIQUIDOS].includes(current?.datos?.version_contrato);
 const num=v=>typeof v==='number'&&Number.isFinite(v)?String(v):'?';
 const xyz=p=>Array.isArray(p)?'('+p.map(num).join(', ')+')':'(?)';
 function mallaControls(){
  $('mallaConsultar').disabled=busy||!docs||!esMalla();
  $('mallaExportar').disabled=busy||!malla;
 }
 function mallaClear(texto){
  mallaTicket++;malla=null;
  for(const id of ['mallaIdentidad','mallaResumen','mallaFaltantes','mallaNodos','mallaSubdivisiones','mallaCortes'])$(id).textContent='';
  $('mallaEstado').textContent=texto||(current?(esMalla()?'Consulta la preparación de esta versión 0.4.':'Contrato '+(current.datos?.version_contrato||'0.1.0')+': sin malla 0.4; recorrido 0.1–0.3 sin cambios.'):'Abre una configuración 0.4 registrada.');
  mallaControls();
 }
 function mallaRender(){
  const p=malla.respuesta.preparacion,d=malla.datos,falt=malla.respuesta.faltantes;
  const fuentes=new Map((d.fuentes||[]).map(f=>[f.id,f]));
  const declarados=new Map((d.nodos_derivados||[]).map(n=>[n.nodo,n]));
  const subdecl=new Map((d.subdivision_frames||[]).map(s=>[s.frame,s]));
  const cortes=p.cortes_nivel;
  $('mallaIdentidad').textContent='Caso '+malla.caso+' · versión '+malla.version+' · huella '+malla.huella+' · contrato '+malla.datos.version_contrato+' · preparación '+p.huella_preparacion;
  $('mallaResumen').textContent=[
   'Hosts: '+Object.keys(p.hosts||{}).length+' · triángulos: '+(p.triangulos||[]).length+' · nodos: '+(p.nodos||[]).length,
   'Nodos derivados: '+(p.nodos_derivados||[]).length+' · frames a subdividir: '+(p.frames_subdivision_requerida||[]).length+' · cortes Z: '+(cortes?cortes.niveles_z_m.length:0),
   'Faltantes de política: '+falt.length+' · apto según contrato: '+(malla.respuesta.apto_para_adaptador?'sí (datos completos)':'no'),
   'Preparación no es ejecución ETABS. La aprobación declarada no certifica ingeniería (aprueba_ingenieria: false).'
  ].join('\n');
  $('mallaFaltantes').textContent=falt.length?falt.map(f=>f.ruta+' — '+f.motivo).join('\n'):'Sin faltantes de política de malla.';
  const xyzNodo=new Map((p.nodos||[]).map(n=>[n.csi,n.xyz_m]));
  $('mallaNodos').textContent=(p.nodos_derivados||[]).map(n=>{
   const pol=declarados.get(n),pos=xyzNodo.get(n);
   let estado='FALTA política';
   if(pol){const ok=JSON.stringify(pol.xyz_m)===JSON.stringify(pos);
    estado=(ok?'declarada':'DECLARADA EN OTRA POSICIÓN '+xyz(pol.xyz_m))+' · restricciones '+JSON.stringify(pol.restricciones)+' · '+(pol.diafragma!==null&&pol.diafragma!==undefined?'diafragma '+pol.diafragma:'sin diafragma: '+pol.motivo_sin_diafragma)+' · fuente '+pol.fuente;}
   return n+' '+xyz(pos)+' · '+estado;
  }).join('\n')||'Sin nodos derivados.';
  $('mallaSubdivisiones').textContent=(p.frames_subdivision_requerida||[]).map(r=>{
   const s=subdecl.get(r.frame),ok=s&&JSON.stringify(s.nodos)===JSON.stringify(r.nodos);
   return r.frame+': '+r.nodos.join(' → ')+' · subframes '+r.subframes.join(', ')+' · '+(ok?'declarada (fuente '+s.fuente+')':s?'DECLARADA DISTINTA':'FALTA declaración');
  }).join('\n')||'Ningún frame atraviesa nodos de malla.';
  const lineas=cortes?cortes.declaraciones.map(c=>'Z = '+num(c.z_m)+' m · motivo: '+c.motivo+' · fuente '+c.fuente+(fuentes.has(c.fuente)?' ('+fuentes.get(c.fuente).descripcion+')':'')):['Sin cortes Z declarados.'];
  if(cortes)lineas.push('Nodos de corte: '+cortes.nodos_corte.join(', '),'No crea pisos (Storys); conserva ambos lados del corte.');
  const fm=d.malla?.fuente;lineas.push('Estrategia: '+(d.malla?.estrategia||'?')+' · fuente '+fm+(fuentes.has(fm)?' ('+fuentes.get(fm).descripcion+')':''));
  lineas.push('Conexiones de borde declaradas: '+((p.conexiones||[]).map(c=>c.id).join(', ')||'ninguna'));
  $('mallaCortes').textContent=lineas.join('\n');
  $('mallaEstado').textContent=falt.length?'Preparación consultada: '+falt.length+' faltante(s); completa la política en el JSON y guarda una revisión. La aprobación sigue bloqueada.':(d.revision?.estado==='aprobado'?'Preparación consultada sin faltantes de política; configuración ya aprobada (declaración, no certifica ingeniería).':'Preparación consultada sin faltantes de política. Revisa y aprueba con la operación existente.');
 }
 async function mallaConsultar(){
  if(!docs||!current||!esMalla())throw Error('Abre una configuración 0.4 registrada.');
  const seq=++mallaTicket,caso=docs.caso,version=current.id,huella=current.huella,abierta=current;malla=null;mallaControls();
  $('mallaEstado').textContent='Reproduciendo partición, compatibilidad, triangulación y cortes de la versión '+version+'…';
  const res=await api('/api/configuracion/malla?'+new URLSearchParams({caso,version})),data=await res.json();
  // Respuesta de una selección anterior: se descarta sin mostrarla.
  if(seq!==mallaTicket||docs?.caso!==caso||current!==abierta||current?.id!==version||current?.huella!==huella)return;
  if(data.id!==version||data.expediente_sha256!==abierta.expediente_sha256||typeof data.huella_configuracion!=='string'||data.huella_configuracion!==huella)throw Error('La preparación no corresponde a la versión o expediente abiertos; vuelve a consultar.');
  malla={caso,version,huella,datos:abierta.datos,respuesta:data};mallaRender();mallaControls();
 }
 window.mallaExportacion=()=>{
  if(!malla||!current||current.id!==malla.version||current.huella!==malla.huella||docs?.caso!==malla.caso)throw Error('Consulta primero la preparación de la versión abierta.');
  const p=malla.respuesta.preparacion,declarados=new Set((malla.datos.nodos_derivados||[]).map(n=>n.nodo)),subdecl=new Set((malla.datos.subdivision_frames||[]).map(s=>s.frame));
  return {contrato:'draft2model.exportacion_preparacion_malla',version_contrato:'0.1.0',caso:malla.caso,configuracion_version:malla.version,
   huella_configuracion:malla.huella,huella_preparacion:p.huella_preparacion,apto_para_adaptador:malla.respuesta.apto_para_adaptador,aprueba_ingenieria:false,
   aviso:'Documento de revisión. No es una configuración ni una ejecución. Las plantillas tienen valores null: la política se declara a mano, con fuente, en una revisión en borrador.',
   faltantes:malla.respuesta.faltantes,
   plantilla_nodos_pendientes:(p.plantilla_nodos_derivados||[]).filter(n=>!declarados.has(n.nodo)),
   subdivisiones_pendientes:(p.frames_subdivision_requerida||[]).filter(r=>!subdecl.has(r.frame)).map(r=>({frame:r.frame,nodos:r.nodos,fuente:null})),
   cortes_nivel:p.cortes_nivel,preparacion:p};
 };
 function mallaExportar(){
  const doc=window.mallaExportacion(),blob=new Blob([JSON.stringify(doc,null,2)+'\n'],{type:'application/json'});
  const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='preparacion-malla-'+doc.configuracion_version+'.json';link.click();URL.revokeObjectURL(url);
 }
 function reason(){
  if(!docs||!current)return 'Abre una configuración con evidencia vigente.';
  const c=current.comprobacion;
  if(!c.consistente||!c.geometria_comprobada)return 'Completa las validaciones de configuración y geometría.';
  if(c.faltantes.length)return 'Resuelve los faltantes y guarda una revisión.';
  if(c.comprobacion_geometria?.validacion?.disponible_para_modelado!==true&&!([...DESARROLLO,MALLA,LIQUIDOS].includes(current.datos.version_contrato)&&c.geometria_aprobada_por_huella===true))return 'La geometría de origen requiere aprobación vigente.';
  if(current.datos.revision.estado==='aprobado')return 'Esta configuración ya está aprobada; cualquier cambio requiere una revisión en borrador.';
  if($('configJson').value!==JSON.stringify(current.datos,null,2))return 'Guarda primero los cambios del JSON como revisión en borrador.';
  if(!['configRevisor','configFecha','configMotivo','configAlcance'].every(id=>$(id).value.trim()&&$(id).checkValidity()))return 'Completa revisor, fecha, motivo y alcance.';
  if(!$('configConfirmar').checked)return 'Marca la declaración explícita de aprobación.';
  return '';
 }
 window.configControls=()=>{
  for(const id of ['configVersion','configImportar','configComprobar','configJson','configGuardar','configConfirmar'])$(id).disabled=busy||!docs||(['configComprobar','configJson','configGuardar','configConfirmar'].includes(id)&&!current);
  const why=reason();$('configAprobar').disabled=busy||Boolean(why);$('configAprobacionInfo').textContent=why||'Lista para registrar una declaración sobre la huella abierta.';
  mallaControls();
 };
 function publish(){window.dispatchEvent(new CustomEvent('d2m-config',{detail:current}));}
 function clear(){ticket++;current=null;publish();$('configJson').value='';$('configDetalle').textContent='';$('configHuella').value='';$('configConfirmar').checked=false;mallaClear();options($('configVersion'),[['','Sin configuraciones']]);$('configEstado').textContent=docs?'Selecciona una versión de configuración.':'Selecciona un expediente.';window.configControls();}
 async function listing(preferred){
  const seq=ticket,caso=docs?.caso;if(!caso)return;
  const res=await api('/api/configuraciones?'+new URLSearchParams({caso})),data=await res.json();
  if(seq!==ticket||docs?.caso!==caso)return;
  options($('configVersion'),[['','Selecciona configuración'],...data.versiones.map(v=>[v,v])]);
  if(preferred&&data.versiones.includes(preferred)){$('configVersion').value=preferred;await open();}
  else if(!preferred&&data.versiones.length){$('configVersion').value=data.versiones[data.versiones.length-1];await open();}
 }
 async function open(){
  const seq=++ticket,caso=docs?.caso,id=$('configVersion').value;current=null;mallaClear();publish();$('configConfirmar').checked=false;$('configJson').value='';$('configHuella').value='';window.configControls();
  if(!caso||!id)return;
  $('configEstado').textContent='Comprobando configuración y evidencia…';
  const res=await api('/api/configuracion?'+new URLSearchParams({caso,version:id})),data=await res.json();
  if(seq!==ticket||docs?.caso!==caso)return;
  current=data;if(typeof window!=='undefined')window.__CURRENT_CONFIG__=data.datos;$('configJson').value=JSON.stringify(data.datos,null,2);$('configHuella').value=data.huella;
  mallaClear();publish();
  $('configDetalle').textContent=JSON.stringify({metadatos:data.metadatos,comprobacion:data.comprobacion,cadena:data.cadena},null,2);
  $('configEstado').textContent='Contrato '+(data.datos.version_contrato||'0.1.0')+(data.datos.version_contrato===MALLA?' (malla)':data.datos.version_contrato===LIQUIDOS?' (malla · líquidos: '+(data.datos.liquidos?.aplicabilidad||'sin declarar')+')':DESARROLLO.includes(data.datos.version_contrato)?' (desarrollo, sin ETABS)':'')+' · '+data.datos.revision.estado+' · '+(data.datos.datos_sinteticos?'DATOS SINTÉTICOS · ':'')+data.comprobacion.faltantes.length+' faltante(s) · '+(data.comprobacion.apto_para_adaptador?'Configuración apta según contrato; modelo ETABS pendiente de comprobación.':'Sin disponibilidad para aplicar en ETABS.');window.configControls();
 }
 function base(){if(!docs||!current)throw Error('Abre una configuración.');return {caso:docs.caso,expediente_sha256:current.expediente_sha256,version:current.id,huella:current.huella,sha256_configuracion:current.sha256_configuracion,revisor_declarado:$('configRevisor').value,fecha:$('configFecha').value,motivo:$('configMotivo').value};}
 window.addEventListener('d2m-case',()=>{clear();listing().catch(e=>message(e.message,true));});
 $('configFecha').value=new Date().toLocaleDateString('sv-SE');
 for(const id of ['configRevisor','configFecha','configMotivo','configAlcance','configConfirmar'])$(id).addEventListener('input',window.configControls);
 $('configJson').addEventListener('input',()=>{$('configConfirmar').checked=false;if(malla)$('mallaEstado').textContent='El JSON editado aún no está guardado: la preparación visible corresponde a la versión registrada '+malla.version+'.';window.dispatchEvent(new CustomEvent('d2m-config',{detail:null}));window.configControls();});
 $('configVersion').onchange=()=>open().catch(e=>{$('configEstado').textContent=e.message;message(e.message,true);});
 $('mallaConsultar').onclick=()=>action(async()=>{await mallaConsultar();});
 $('mallaExportar').onclick=()=>action(async()=>{mallaExportar();message('Preparación exportada como documento de revisión; no se modificó la configuración.');});
 $('configComprobar').onclick=()=>action(async()=>{await open();message('Configuración, cadena y geometría comprobadas.');});
 $('configImportar').onchange=()=>{const file=$('configImportar').files[0];if(!file)return;action(async()=>{if(file.size>1.5*1024*1024)throw Error('Máximo 1.5 MiB para importación visual.');const res=await api('/api/configuracion/importar',{caso:docs.caso,expediente_sha256:docs.expediente_sha256,configuracion_json:await file.text()});await listing((await res.json()).id);message('Configuración importada en borrador.');}).finally(()=>{$('configImportar').value='';});};
 $('configForm').onsubmit=e=>{e.preventDefault();action(async()=>{const res=await api('/api/configuracion/revisar',{...base(),configuracion_json:$('configJson').value});await listing((await res.json()).id);message('Nueva revisión de configuración conservada en borrador.');});};
 $('configAprobar').onclick=()=>action(async()=>{const why=reason();if(why)throw Error(why);const res=await api('/api/configuracion/aprobar',{...base(),alcance:$('configAlcance').value,confirmacion_explicita:true});await listing((await res.json()).id);message('Aprobación de configuración registrada. No se ejecutó ni aprobó un modelo ETABS.');});
 window.addEventListener('d2m-config-created',event=>{
  const value=event.detail;
  if(!docs||value?.caso!==docs.caso||value.expediente_sha256!==docs.expediente_sha256||value.aprueba_ingenieria!==false||value.registrada!==true)return;
  listing(value.configuracion).catch(error=>message(error.message,true));
 });
 clear();
})();
