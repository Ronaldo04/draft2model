'use strict';
(()=>{
 // Esquema por nivel y superposición con tres anclas DECLARADAS; nunca se alinea sin correspondencia registrada.
 const SVG='http://www.w3.org/2000/svg',ANCLAS=[1,2,3];
 let ticket=0,schemaSeq=0,versionSeq=0,listSeq=0,imageSeq=0,schema=null,overlay=null,imageUrl=null;
 const same=(own,caso,fp)=>own===ticket&&caso===docs?.caso&&fp===docs?.expediente_sha256;
 const query=extra=>new URLSearchParams({caso:docs.caso,expediente_sha256:docs.expediente_sha256,...extra});
 const level=()=>schema?.niveles.find(n=>n.id===$('supNivel').value)||null;
 const plane3dMode=()=>$('supTipo')?.value==='superficies_plano3d';
 const surfaceMode=()=>plane3dMode()||$('supTipo')?.value==='superficies_horizontal';
 const baseFields=['supOrigen3d','supEjeU3d','supEjeV3d'];
 function vector(id){const raw=$(id)?.value;if(typeof raw!=='string')return null;const partes=raw.split(',');return partes.length===3&&partes.every(v=>v.trim()!==''&&Number.isFinite(Number(v)))?partes.map(Number):null;}
 const dot=(a,b)=>a.reduce((s,x,i)=>s+x*b[i],0);
 function base3d(){const [o,u,v]=baseFields.map(vector);if(!o||!u||!v||Math.abs(Math.hypot(...u)-1)>1e-12||Math.abs(Math.hypot(...v)-1)>1e-12||Math.abs(dot(u,v))>1e-12)return null;return {tipo:'base_ortonormal_3d',origen_m:o,eje_u:u,eje_v:v};}
 const planeKey=p=>p?JSON.stringify([p.tipo,p.origen_m,p.eje_u,p.eje_v]):'';
 function ulp(x){const b=new DataView(new ArrayBuffer(8));b.setFloat64(0,Math.abs(x));const exp=(b.getUint32(0)>>>20)&2047;return exp===0?Number.MIN_VALUE:2**(exp-1023-52);}
 function projected(s,p){const {origen_m:o,eje_u:u,eje_v:v}=p,n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]],pts=s.vertices_m;
  const scale=Math.max(...pts.flatMap(q=>q.map((x,k)=>Math.abs(x-pts[0][k])))),mag=Math.max(...pts.flat().map(Math.abs),...o.map(Math.abs));
  const tol=Math.max(1e-12*scale,64*ulp(mag));if(!Number.isFinite(tol)||scale<=0||tol/scale>1e-6)return null;
  const deltas=pts.map(q=>q.map((x,k)=>x-o[k]));if(deltas.some(q=>!q.every(Number.isFinite)||Math.abs(dot(q,n))>tol))return null;
  const uv=deltas.map(q=>[dot(q,u),dot(q,v)]);if(!uv.every(q=>q.every(Number.isFinite)))return null;
  if(s.aberturas){const aberturas=s.aberturas.map(a=>projected(a,p));if(aberturas.some(a=>!a))return null;return {...s,vertices_plano_m:uv,aberturas};}
  return {...s,vertices_plano_m:uv};
 }
 const planeZ=()=>$('supCota')?.value?.trim()!==''&&Number.isFinite(Number($('supCota')?.value))?Number($('supCota').value):null;
 const planeSurfaces=()=>plane3dMode()?(base3d()?(schema?.superficies||[]).map(s=>projected(s,base3d())).filter(Boolean):[]):(planeZ()===null?[]:(schema?.superficies||[]).filter(s=>s.vertices_m.every(p=>p[2]===planeZ())&&(!s.aberturas||s.aberturas.every(a=>a.vertices_m.every(p=>p[2]===planeZ())))));
 const planeTitle=()=>plane3dMode()?'base 3D ortonormal DECLARADA (U×V fija sentido)':'plano horizontal DECLARADO Z='+planeZ()+' m';
 const surface=()=>planeSurfaces().find(s=>s.id===$('supElemento').value)||null;
 const fmt=v=>typeof v==='number'?String(Math.round(v*1e6)/1e6):String(v);
 const declaracion=['supRevisor','supFecha','supMotivo'];
 function anchorsReady(){return ANCLAS.every(i=>{const u=$('supU'+i).value,v=$('supV'+i).value;return $('supNodo'+i).value&&u!==''&&v!==''&&Number.isFinite(Number(u))&&Number.isFinite(Number(v));});}
 function ready(){return schema&&!(schema.version_geometria==='0.3.0'&&!surfaceMode())&&(surfaceMode()?surface():level()?.muros.length)&&$('supDocumento').value&&$('supPagina').value&&anchorsReady()
  &&declaracion.every(id=>$(id).value.trim()&&$(id).checkValidity());}
 window.overlayControls=()=>{
  for(const id of ['supGeometria','supDocumento','supPagina','supEsquema','supVersion','supActualizar'])$(id).disabled=busy||!docs;
  for(const id of ['supNivel','supElemento',...ANCLAS.flatMap(i=>['supNodo'+i,'supU'+i,'supV'+i]),...declaracion])$(id).disabled=busy||!schema;
  if($('supTipo'))$('supTipo').disabled=busy||!schema;
  if($('supCota'))$('supCota').disabled=busy||!schema||!surfaceMode()||plane3dMode();
  for(const id of baseFields)if($(id))$(id).disabled=busy||!schema||!plane3dMode();
  $('supNivel').disabled=busy||!schema||surfaceMode();
  $('supConfirmar').disabled=busy||!ready();$('supRegistrar').disabled=busy||!ready()||!$('supConfirmar').checked;
 };
 function revokeImage(){imageSeq++;if(imageUrl)URL.revokeObjectURL(imageUrl);imageUrl=null;}
 function clearOverlay(){overlay=null;versionSeq++;revokeImage();$('supFuera').textContent='';$('supConfirmar').checked=false;}
 function clearSchema(){schemaSeq++;schema=null;clearOverlay();options($('supNivel'),[['','Sin esquema']]);options($('supElemento'),[['','Sin elemento']]);
  if($('supTipo'))$('supTipo').value='muros_nivel';if($('supCota'))$('supCota').value='';
  for(const id of baseFields)if($(id))$(id).value='';
  for(const i of ANCLAS){options($('supNodo'+i),[['','Nodo']]);$('supU'+i).value='';$('supV'+i).value='';}
  $('supElementoDetalle').textContent='';$('supLienzo').replaceChildren();$('supAviso').textContent='Sin esquema cargado.';}
 function pages(){const doc=docs?.documentos.find(d=>d.id===$('supDocumento').value);options($('supPagina'),doc?Array.from({length:doc.paginas},(_,i)=>[String(i+1),String(i+1)]):[['','Sin página']]);$('supPagina').value=doc?'1':'';}
 function clear(){ticket++;listSeq++;clearSchema();
  options($('supGeometria'),[['','Selecciona geometría'],...(docs?.geometrias||[]).map(v=>[v,v])]);
  options($('supDocumento'),[['','Selecciona original'],...(docs?.documentos||[]).filter(d=>!d.error&&d.paginas>0).map(d=>[d.id,d.id+' · '+d.nombre])]);pages();
  options($('supVersion'),[['','Sin superposición seleccionada']]);
  $('supEstado').textContent=docs?'Selecciona geometría y nivel. Sin anclas declaradas solo se muestra el esquema métrico.':'Selecciona un expediente.';window.overlayControls();}
 function error(err){$('supEstado').textContent=err.message;message(err.message,true);}
 function el(tag,attrs){const n=document.createElementNS(SVG,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,String(v));return n;}
 function shapeWithHoles(s,coordinates,stroke,width){
  const loops=[s,...s.aberturas],d=loops.map(a=>coordinates(a).map((p,i)=>(i?'L':'M')+p[0]+','+p[1]).join(' ')+' Z').join(' ');
  return el('path',{d,fill:stroke,'fill-opacity':.12,'fill-rule':'evenodd',stroke,'stroke-width':width,'data-superficie':s.id,'data-aberturas':s.aberturas.map(a=>a.id).join(',')});
 }
 function drawSurfaces(svg){
  const chosen=$('supElemento').value,items=planeSurfaces();
  const expected=schema?.version_geometria==='0.3.0'?'0.4.0':(plane3dMode()?'0.3.0':'0.2.0');
  const matching=overlay?.version_contrato===expected&&(plane3dMode()?planeKey(overlay.plano)===planeKey(base3d()):overlay.plano.tipo==='horizontal'&&overlay.plano.cota_m===planeZ());
  if(matching&&imageUrl){
   const [w,h]=overlay.fuente.preview_px;svg.setAttribute('viewBox','0 0 '+w+' '+h);svg.setAttribute('aria-label','Contornos declarados en '+planeTitle()+' sobre página '+overlay.fuente.pagina);
   svg.append(el('image',{href:imageUrl,x:0,y:0,width:w,height:h}));
   for(const s of overlay.superficies)svg.append(s.aberturas?shapeWithHoles(s,a=>a.proyeccion.map(p=>[p.u*w,p.v*h]),s.id===chosen?'#c0392b':'#1f6feb',s.id===chosen?6:3):el('polygon',{points:s.proyeccion.map(p=>p.u*w+','+p.v*h).join(' '),fill:'none',stroke:s.id===chosen?'#c0392b':'#1f6feb','stroke-width':s.id===chosen?6:3}));
   for(const a of overlay.anclas)svg.append(el('circle',{cx:a.punto[0]*w,cy:a.punto[1]*h,r:8,fill:'none',stroke:'#e67e22','stroke-width':3}));
   $('supFuera').textContent=overlay.fuera_imagen.length?'Fuera de imagen (sin recortar): '+overlay.fuera_imagen.map(f=>f.superficie+'/'+(f.abertura?f.abertura+'/':'')+f.vertice+' ('+fmt(f.u)+', '+fmt(f.v)+')').join('; '):'Todos los vértices proyectados están dentro de la página.';
   $('supAviso').textContent=overlay.aviso||'Contornos horizontales y correspondencia DECLARADOS; sin aprobación de ingeniería.';return;
  }
  const pts=items.flatMap(s=>s.vertices_plano_m||s.vertices_m);
  if(!pts.length){$('supAviso').textContent=plane3dMode()?'Declara origen físico XYZ y dos ejes unitarios/ortogonales (ternas separadas por comas). Solo se muestran superficies coplanares con esa base; no son ejes locales ETABS.':'Declara una cota física Z en metros. Solo se muestran contornos horizontales en esa cota.';return;}
  const xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]),x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys),span=Math.max(x1-x0,y1-y0)||1,pad=span*.08;
  svg.setAttribute('viewBox',[x0-pad,-y1-pad,x1-x0+2*pad,y1-y0+2*pad].join(' '));svg.setAttribute('aria-label','Contornos métricos en '+planeTitle());
  for(const s of items)svg.append(s.aberturas?shapeWithHoles(s,a=>(a.vertices_plano_m||a.vertices_m).map(p=>[p[0],-p[1]]),s.id===chosen?'#c0392b':'#243447',span*(s.id===chosen?0.02:0.01)):el('polygon',{points:(s.vertices_plano_m||s.vertices_m).map(p=>p[0]+','+(-p[1])).join(' '),fill:'none',stroke:s.id===chosen?'#c0392b':'#243447','stroke-width':span*(s.id===chosen?0.02:0.01)}));
  $('supAviso').textContent='Contornos en metros en '+planeTitle()+'. Sin correspondencia: NO están alineados con el plano. No son una malla, sección estructural ni ejes locales ETABS.';
 }
 function draw(){
  const lvl=level(),svg=el('svg',{width:'100%',role:'img'});$('supLienzo').replaceChildren(svg);$('supFuera').textContent='';
  if(surfaceMode()){drawSurfaces(svg);return;}
  if(schema?.version_geometria==='0.3.0'){$('supAviso').textContent='Geometría con aberturas: selecciona una vista de superficies para conservar los huecos; el formato histórico de muros no es compatible.';return;}
  if(!lvl)return;
  const selected=$('supElemento').value;
  if(overlay&&overlay.nivel===lvl.id&&imageUrl){
   const [w,h]=overlay.fuente.preview_px;svg.setAttribute('viewBox','0 0 '+w+' '+h);svg.setAttribute('aria-label','Superposición declarada sobre la página '+overlay.fuente.pagina);
   svg.append(el('image',{href:imageUrl,x:0,y:0,width:w,height:h}));
   for(const m of overlay.muros){const [a,b]=m.proyeccion;svg.append(el('line',{x1:a.u*w,y1:a.v*h,x2:b.u*w,y2:b.v*h,'stroke-width':m.id===selected?6:3,stroke:m.id===selected?'#c0392b':'#1f6feb'}));}
   for(const a of overlay.anclas)svg.append(el('circle',{cx:a.punto[0]*w,cy:a.punto[1]*h,r:8,fill:'none',stroke:'#e67e22','stroke-width':3}));
   $('supFuera').textContent=overlay.fuera_imagen.length?'Fuera de la imagen (sin recortar): '+overlay.fuera_imagen.map(f=>f.muro+'/'+f.nodo+' ('+fmt(f.u)+', '+fmt(f.v)+')').join('; '):'Todos los extremos proyectados están dentro de la página.';
   $('supAviso').textContent='Superposición con correspondencia DECLARADA (tres anclas, '+overlay.declaracion.revisor_declarado+'). No es detección automática ni prueba que el elemento esté documentado.';
   return;
  }
  const {x:[x0,x1],y:[y0,y1]}=schema.extension,span=Math.max(x1-x0,y1-y0)||1,pad=span*0.08;
  svg.setAttribute('viewBox',[x0-pad,-(y1+pad),x1-x0+2*pad,y1-y0+2*pad].join(' '));svg.setAttribute('aria-label','Esquema métrico del nivel '+lvl.id);
  for(const m of lvl.muros)svg.append(el('line',{x1:m.inicio.x,y1:-m.inicio.y,x2:m.fin.x,y2:-m.fin.y,'stroke-width':span*(m.id===selected?0.02:0.01),stroke:m.id===selected?'#c0392b':'#243447'}));
  $('supAviso').textContent='Esquema métrico en '+schema.unidad_longitud+' sin correspondencia: NO está alineado con ningún plano. Declara tres anclas para superponer.';
 }
 function showElement(){
  if(surfaceMode()){
   const s=surface();$('supElementoDetalle').textContent=s?'Superficie '+s.id+' · área geométrica '+fmt(s.area_m2)+' m² · papel declarado: '+s.papel_geometrico+' · vértices XYZ (m): '+s.vertices.map((id,i)=>id+' ('+s.vertices_m[i].map(fmt).join(', ')+')').join(' → ')+' · procedencia: '+JSON.stringify(s.procedencia)+(s.aberturas?' · área bruta '+fmt(s.area_bruta_m2)+' m² · huecos '+fmt(s.area_aberturas_m2)+' m² · área neta '+fmt(s.area_neta_m2)+' m² · aberturas: '+s.aberturas.map(a=>a.id+' de '+s.id+' ('+fmt(a.area_m2)+' m²), procedencia: '+JSON.stringify(a.procedencia)).join('; '):'')+' · geometría '+schema.geometria+' ('+schema.estado_revision+')':'';
   draw();return;
  }
  const lvl=level(),m=lvl?.muros.find(x=>x.id===$('supElemento').value);
  if(!m){$('supElementoDetalle').textContent='';draw();return;}
  const u=schema.unidad_longitud,p=overlay&&overlay.nivel===lvl.id?overlay.muros.find(x=>x.id===m.id)?.proyeccion:null;
  $('supElementoDetalle').textContent='Muro '+m.id+' · '+m.inicio.id+' ('+fmt(m.inicio.x)+', '+fmt(m.inicio.y)+') → '+m.fin.id+' ('+fmt(m.fin.x)+', '+fmt(m.fin.y)+') '+u
   +' · longitud '+fmt(m.longitud)+' '+u+' · espesor '+(m.espesor===null?'faltante declarado':fmt(m.espesor)+' '+u)+' · niveles '+m.nivel_inferior+'→'+m.nivel_superior
   +' · geometría '+schema.geometria+' ('+schema.estado_revision+')'
   +(p?' · proyección: '+p.map(e=>e.nodo+' ('+fmt(e.u)+', '+fmt(e.v)+')'+(e.dentro_imagen?'':' FUERA')).join(' → ')+' · fuente '+overlay.fuente.archivo+' p.'+overlay.fuente.pagina:' · sin proyección: no hay correspondencia consultada');
  draw();
 }
 function levelChanged(){
  if(surfaceMode()){
   options($('supElemento'),[['','Selecciona superficie'],...planeSurfaces().map(s=>[s.id,s.id])]);
   for(const i of ANCLAS){options($('supNodo'+i),[['','Vértice 3D']]);$('supU'+i).value='';$('supV'+i).value='';}
   $('supConfirmar').checked=false;showElement();window.overlayControls();return;
  }
  const lvl=level();options($('supElemento'),[['','Selecciona elemento'],...(lvl?.muros||[]).map(m=>[m.id,m.id])]);
  const nodes=[...new Set((lvl?.muros||[]).flatMap(m=>[m.inicio.id,m.fin.id]))];
  for(const i of ANCLAS){options($('supNodo'+i),[['','Nodo'],...nodes.map(n=>[n,n])]);$('supU'+i).value='';$('supV'+i).value='';}
  $('supConfirmar').checked=false;showElement();window.overlayControls();
 }
 async function loadSchema(version=$('supGeometria').value){
  const seq=++schemaSeq,own=ticket,caso=docs?.caso,fp=docs?.expediente_sha256;clearSchema();schemaSeq=seq;window.overlayControls();if(!caso||!version)return null;
  const res=await api('/api/superposicion/esquema?'+query({version})),value=await res.json();
  if(!same(own,caso,fp)||schemaSeq!==seq||$('supGeometria').value!==version)return null;
  if(value.geometria!==version||value.caso!==caso)throw Error('Esquema ajeno a la selección.');
  schema=value;options($('supNivel'),value.niveles.map(n=>[n.id,n.id+(n.nombre?' · '+n.nombre:'')+' · '+n.muros.length+' muro(s)']));$('supNivel').value=value.niveles[0]?.id||'';
  if(!value.niveles.length&&['0.2.0','0.3.0'].includes(value.version_geometria)&&$('supTipo'))$('supTipo').value='superficies_horizontal';levelChanged();
  $('supEstado').textContent='Geometría '+version+' · '+value.estado_revision+' · unidad '+value.unidad_longitud+(value.disponible_para_modelado?'':' · sin disponibilidad para modelado')+'. Una correspondencia previa no se hereda.';
  window.overlayControls();return value;
 }
 async function background(item){
  const seq=++imageSeq,own=ticket,caso=docs?.caso,fp=docs?.expediente_sha256;
  const res=await api('/api/pagina?'+new URLSearchParams({caso,archivo:item.fuente.archivo,pagina:String(item.fuente.pagina),expediente_sha256:fp})),blob=await res.blob();
  if(!same(own,caso,fp)||seq!==imageSeq||overlay!==item)return;
  imageUrl=URL.createObjectURL(blob);showElement();
 }
 async function openVersion(){
  const id=$('supVersion').value,seq=++versionSeq,own=ticket,caso=docs?.caso,fp=docs?.expediente_sha256;
  overlay=null;revokeImage();if(!caso||!id){showElement();return;}
  const res=await api('/api/superposicion/version?'+query({version:id})),item=await res.json();
  if(!same(own,caso,fp)||versionSeq!==seq||$('supVersion').value!==id)return;
  if(item.id!==id||item.caso!==caso||item.expediente_sha256!==fp||item.vigente!==true||item.aprueba_ingenieria!==false)throw Error('Superposición sin vigencia o ajena.');
  if(!schema||schema.geometria!==item.geometria.id||schema.huella_geometria!==item.geometria.huella){
   $('supGeometria').value=item.geometria.id;const loaded=await loadSchema(item.geometria.id);
   if(!loaded||!same(own,caso,fp)||$('supVersion').value!==id)return;versionSeq=seq;
   if(loaded.huella_geometria!==item.geometria.huella)throw Error('La geometría cambió; registra una correspondencia nueva.');
  }
  if(['0.2.0','0.3.0','0.4.0'].includes(item.version_contrato)){
   const tridimensional=item.version_contrato==='0.3.0'||(item.version_contrato==='0.4.0'&&item.plano.tipo==='base_ortonormal_3d');
   $('supTipo').value=tridimensional?'superficies_plano3d':'superficies_horizontal';
   if(tridimensional){for(const [i,key] of ['origen_m','eje_u','eje_v'].entries())$(baseFields[i]).value=item.plano[key].join(',');}
   else $('supCota').value=String(item.plano.cota_m);levelChanged();
   $('supElemento').value=item.superficies[0]?.id||'';surfaceAnchors();
  }else{$('supTipo').value='muros_nivel';$('supNivel').value=item.nivel;levelChanged();}
  $('supDocumento').value=item.fuente.archivo;pages();$('supPagina').value=String(item.fuente.pagina);
  overlay=item;$('supEstado').textContent='Superposición '+id+' comprobada · '+item.naturaleza+' · sin aprobación de ingeniería.';
  showElement();await background(item);
 }
 async function listing(preferred){
  const seq=++listSeq,own=ticket,caso=docs?.caso,fp=docs?.expediente_sha256;if(!caso)return;
  const res=await api('/api/superposicion/historial?'+query({})),value=await res.json();if(!same(own,caso,fp)||listSeq!==seq)return;
  options($('supVersion'),[['',value.versiones.length?'Selecciona superposición':'Sin superposiciones'],
   ...value.versiones.map(v=>[v.id,v.id+(v.vigente?' · '+(v.plano?(v.plano.tipo==='horizontal'?'Z='+v.plano.cota_m+' m':'base 3D declarada'):v.nivel)+' · geometría '+v.geometria:' · sin vigencia')])]);
  if(preferred&&value.versiones.some(v=>v.id===preferred&&v.vigente)){$('supVersion').value=preferred;await openVersion();}
  window.overlayControls();
 }
 async function act(fn){const own=ticket,caso=docs?.caso,fp=docs?.expediente_sha256;try{await fn(own,caso,fp);}catch(err){if(same(own,caso,fp))error(err);}}
 window.addEventListener('d2m-case',()=>{clear();if(docs)act(()=>listing());});
 window.addEventListener('d2m-geometry-created',()=>{if(docs)act(async(own,caso,fp)=>{const res=await api('/api/geometrias?'+new URLSearchParams({caso})),data=await res.json();
  if(!same(own,caso,fp))return;const keep=$('supGeometria').value;options($('supGeometria'),[['','Selecciona geometría'],...data.versiones.map(v=>[v,v])]);$('supGeometria').value=keep;});});
 // Hook localizado: al abrir otra versión en el panel geométrico se recarga el esquema y se exige correspondencia nueva.
 $('geoVersion').addEventListener('change',()=>{const id=$('geoVersion').value;if(!docs||!id||id===$('supGeometria').value)return;
  $('supGeometria').value=id;$('supVersion').value='';act(()=>loadSchema(id));});
 $('supGeometria').onchange=()=>{$('supVersion').value='';act(()=>loadSchema());};
 $('supEsquema').onclick=()=>action(()=>act(()=>loadSchema()));
 $('supNivel').onchange=()=>{clearOverlay();$('supVersion').value='';levelChanged();};
 function surfaceAnchors(){for(const i of ANCLAS){options($('supNodo'+i),[['','Vértice 3D'],...(surface()?.vertices||[]).map(id=>[id,id])]);$('supU'+i).value='';$('supV'+i).value='';}}
 $('supElemento').onchange=()=>{if(surfaceMode()){clearOverlay();$('supVersion').value='';surfaceAnchors();}showElement();window.overlayControls();};
 if($('supTipo'))$('supTipo').onchange=()=>{clearOverlay();$('supVersion').value='';levelChanged();};
 if($('supCota'))$('supCota').addEventListener('input',()=>{clearOverlay();$('supVersion').value='';levelChanged();});
 for(const id of baseFields)if($(id))$(id).addEventListener('input',()=>{clearOverlay();$('supVersion').value='';levelChanged();});
 $('supDocumento').onchange=()=>{pages();clearOverlay();$('supVersion').value='';showElement();window.overlayControls();};
 $('supPagina').onchange=()=>{clearOverlay();$('supVersion').value='';showElement();window.overlayControls();};
 for(const id of [...ANCLAS.flatMap(i=>['supNodo'+i,'supU'+i,'supV'+i]),...declaracion])$(id).addEventListener('input',()=>{$('supConfirmar').checked=false;window.overlayControls();});
 $('supConfirmar').addEventListener('input',window.overlayControls);
 $('supVersion').onchange=()=>act(()=>openVersion());$('supActualizar').onclick=()=>action(()=>act(()=>listing()));
 $('supFecha').value=new Date().toLocaleDateString('sv-SE');
 $('supRegistrar').onclick=()=>action(()=>act(async(own,caso,fp)=>{
  if(!ready()||!$('supConfirmar').checked)throw Error('Completa tres anclas, la declaración y confirma la correspondencia.');
  const current=schema;$('supConfirmar').checked=false;window.overlayControls();
  const body={caso,expediente_sha256:fp,geometria:current.geometria,huella_geometria:current.huella_geometria,sha256_geometria:current.sha256_geometria,
   archivo:$('supDocumento').value,pagina:Number($('supPagina').value),nivel:$('supNivel').value,
   anclas:ANCLAS.map(i=>({nodo:$('supNodo'+i).value,punto:[Number($('supU'+i).value),Number($('supV'+i).value)]})),
   revisor_declarado:$('supRevisor').value.trim(),fecha:$('supFecha').value,motivo:$('supMotivo').value.trim(),confirmacion_explicita:true};
  if(surfaceMode()){
   delete body.nivel;body.version_contrato='0.2.0';body.plano={tipo:'horizontal',cota_m:planeZ()};body.superficies=[surface().id];
   body.anclas=body.anclas.map(a=>({vertice:a.nodo,punto:a.punto}));
   if(plane3dMode()){body.version_contrato='0.3.0';body.plano=base3d();}
   if(current.version_geometria==='0.3.0')body.version_contrato='0.4.0';
  }
  const res=await api('/api/superposicion/crear',body),item=await res.json();
  if(!same(own,caso,fp)||schema!==current)return;
  if(item.aprueba_ingenieria!==false||item.geometria.id!==current.geometria)throw Error('Registro sin comprobación.');
  await listing(item.id);
 }));clear();
})();
