'use strict';
(()=>{
 const container=window.D2MEtapas?.containers.get('geometria');if(!container)return;
 const panel=document.createElement('section');panel.className='viewer-3d';panel.setAttribute('aria-label','Vista interactiva del modelo 3D');
 const heading=document.createElement('h2');heading.textContent='Modelo 3D';
 const info=document.createElement('p');info.setAttribute('role','status');
 const canvas=document.createElement('canvas');canvas.setAttribute('aria-label','Modelo tridimensional: arrastra para girar, usa la rueda para acercar');canvas.tabIndex=0;
 const tools=document.createElement('div');tools.className='viewer-3d-tools';
 const note=document.createElement('p');note.textContent='Vista de la geometría del sistema. La construcción y relectura en ETABS se comprueban en la etapa 5. Las ediciones sin guardar se identifican como borrador.';
 const title=document.createElement('span');title.textContent='Arrastrar: girar · Rueda: acercar · Muros: verde · Losas/superficies: azul · Columnas/vigas: naranja';
 panel.append(heading,info,tools,canvas,title,note);(container.querySelector('[aria-label="Reconstrucción automática del proyecto"]')||container.querySelector('.stage-guide')).after(panel);
 let angle=.65,elevation=.45,zoom=1,geometry=null,config=null,proposedByGeo=new Map(),proposedFrames=[],drag=null;
 [['Vista inicial',()=>{angle=.65;elevation=.45;zoom=1;}],['Planta',()=>{elevation=Math.PI/2;angle=0;}],['Acercar',()=>{zoom=Math.min(8,zoom*1.2);}],['Alejar',()=>{zoom=Math.max(.15,zoom/1.2);}]].forEach(([name,action])=>{
  const b=document.createElement('button');b.type='button';b.textContent=name;b.addEventListener('click',()=>{action();render();});tools.append(b);
 });
 function entities(g,c){
  if(!g)return {points:new Map(),faces:[],lines:[]};
  const points=new Map((g.vertices||[]).map(v=>[v.id,[v.x,v.y,v.z]])),faces=[],lines=[];
  for(const s of g.superficies||[])faces.push({ids:s.vertices,
   holes:(g.aberturas||[]).filter(a=>a.superficie===s.id).map(a=>a.vertices),
   color:String(s.papel_geometrico).toLowerCase().includes('muro')?'#138b77':'#548fbd'});
  const levels=new Map((g.niveles||[]).map(n=>[n.id,n.cota])),nodes=new Map((g.nodos||[]).map(n=>[n.id,n]));
  for(const wall of g.muros||[]){const a=nodes.get(wall.nodo_inicio),b=nodes.get(wall.nodo_fin);if(!a||!b)continue;
   const ids=['a','b','c','d'].map(s=>wall.id+'_'+s),z0=levels.get(wall.nivel_inferior),z1=levels.get(wall.nivel_superior);
   [[a.x,a.y,z0],[b.x,b.y,z0],[b.x,b.y,z1],[a.x,a.y,z1]].forEach((p,i)=>points.set(ids[i],p));faces.push({ids,holes:[],color:'#138b77'});
  }
  if(c){
   for(const p of c.puntos||[]){if(p.vertice_geometria&&points.has(p.vertice_geometria))points.set(p.id,points.get(p.vertice_geometria));
    else if(nodes.has(p.nodo_geometria)&&levels.has(p.nivel_geometria)){const n=nodes.get(p.nodo_geometria);points.set(p.id,[n.x,n.y,levels.get(p.nivel_geometria)]);}}
   for(const f of c.frames||[])lines.push({ids:[f.inicio,f.fin],color:'#cf762f'});
  }else{
   for(const f of proposedFrames)if(Array.isArray(f.puntos)&&f.puntos.length===2)lines.push({ids:f.puntos,color:'#cf762f'});
  }
  const divisor={m:1,cm:100,mm:1000}[g.unidad_longitud];
  if(!divisor)return {points:new Map(),faces:[],lines:[]};
  for(const [id,p]of points)if(p.every(Number.isFinite))points.set(id,p.map(v=>v/divisor));else points.delete(id);
  return {points,faces,lines};
 }
 function render(){
  const rect=canvas.getBoundingClientRect();if(!rect.width||!rect.height)return;
  const ratio=window.devicePixelRatio||1;canvas.width=Math.round(rect.width*ratio);canvas.height=Math.round(rect.height*ratio);
  const ctx=canvas.getContext('2d');if(!ctx)return;ctx.scale(ratio,ratio);const w=rect.width,h=rect.height;
  const scene=entities(geometry,config),pts=[...scene.points.values()];
  if(!pts.length){ctx.fillStyle='#53696d';ctx.font='14px system-ui';ctx.textAlign='center';ctx.fillText('Aún no hay geometría para mostrar en este expediente.',w/2,h/2);return;}
  const min=[0,1,2].map(i=>Math.min(...pts.map(p=>p[i]))),max=[0,1,2].map(i=>Math.max(...pts.map(p=>p[i]))),mid=min.map((v,i)=>(v+max[i])/2);
  const scale=.62*Math.min(w,h)/Math.max(1,...max.map((v,i)=>v-min[i]))*zoom;
  const project=p=>{const [x,y,z]=p.map((v,i)=>v-mid[i]),u=x*Math.cos(angle)-y*Math.sin(angle),v=x*Math.sin(angle)+y*Math.cos(angle);
   return [w/2+u*scale,h/2+(v*Math.sin(elevation)-z*Math.cos(elevation))*scale,v*Math.cos(elevation)+z*Math.sin(elevation)];};
  const polygons=scene.faces.filter(f=>f.ids.every(id=>scene.points.has(id))).map(f=>({...f,p:f.ids.map(id=>project(scene.points.get(id))),
    holes:f.holes.filter(ids=>ids.every(id=>scene.points.has(id))).map(ids=>ids.map(id=>project(scene.points.get(id))))}));
  polygons.sort((a,b)=>a.p.reduce((s,p)=>s+p[2],0)/a.p.length-b.p.reduce((s,p)=>s+p[2],0)/b.p.length);
  for(const f of polygons){ctx.beginPath();for(const ring of [f.p,...f.holes]){ring.forEach((p,i)=>i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]));ctx.closePath();}ctx.fillStyle=f.color+'55';ctx.fill('evenodd');ctx.lineWidth=1.3;ctx.strokeStyle=f.color;ctx.stroke();}
  for(const line of scene.lines){const ps=line.ids.map(id=>scene.points.get(id));if(ps.some(p=>!p))continue;const [a,b]=ps.map(project);ctx.beginPath();ctx.moveTo(a[0],a[1]);ctx.lineTo(b[0],b[1]);ctx.strokeStyle=line.color;ctx.lineWidth=3;ctx.stroke();}
  ctx.fillStyle='#526b75';ctx.font='11px system-ui';ctx.fillText('Coordenadas en m · '+pts.length+' puntos · '+polygons.length+' superficies',12,h-12);
 }
 function load(){
  geometry=geoRecord?.comprobacion?.correcta===true?geoRecord.datos:null;
  const ver=$('geoVersion')?.value||'';
  if(config?.geometria_origen?.version_id!==ver)config=null;
  proposedFrames=proposedByGeo.get(ver)||[];
  info.textContent=geometry?'Geometría registrada · '+geometry.revision.estado+' · versión '+ver:'Selecciona una versión geométrica. Un expediente con lecturas aún no es un modelo.';
  render();
 }
 window.addEventListener('d2m-proposed-frames',e=>{if(e.detail?.geometria){proposedByGeo.set(e.detail.geometria,e.detail.frames||[]);if($('geoVersion')?.value===e.detail.geometria){proposedFrames=e.detail.frames||[];render();}}});
 window.addEventListener('d2m-geometry-opened',load);
 window.addEventListener('d2m-case',()=>{geometry=null;config=null;info.textContent='Selecciona una geometría de este expediente para mostrarla.';render();});
 window.addEventListener('d2m-config',e=>{const candidate=e.detail?.datos;config=candidate?.geometria_origen?.version_id===$('geoVersion').value?candidate:null;render();});
 window.addEventListener('d2m-geometry-edit',()=>{try{geometry=JSON.parse($('geoJson').value);info.textContent='BORRADOR EDITADO SIN GUARDAR · no es la versión conservada ni el modelo de ETABS.';render();}catch{}});
 window.addEventListener('d2m-stage',render);window.addEventListener('resize',render);
 canvas.addEventListener('pointerdown',e=>{drag=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId);});
 canvas.addEventListener('pointermove',e=>{if(!drag)return;angle+=(e.clientX-drag[0])*.008;elevation=Math.max(-1.5,Math.min(1.57,elevation+(e.clientY-drag[1])*.008));drag=[e.clientX,e.clientY];render();});
 canvas.addEventListener('pointerup',()=>drag=null);canvas.addEventListener('pointercancel',()=>drag=null);
 canvas.addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(.15,Math.min(8,zoom*(e.deltaY<0?1.1:1/1.1)));render();},{passive:false});
 canvas.addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();angle+=e.key==='ArrowLeft'?-.1:e.key==='ArrowRight'?.1:0;elevation+=e.key==='ArrowUp'?.1:e.key==='ArrowDown'?-.1:0;render();}});
 window.D2MModelo3D={entities};load();
})();
