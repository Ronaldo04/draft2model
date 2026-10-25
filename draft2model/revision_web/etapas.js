'use strict';
(()=>{
 const stages=[
  {id:'ingreso',name:'Proyecto y planos',title:'1. Registrar el proyecto',
   auto:'Conservar los originales y comprobar qué documentos se pueden procesar.',
   human:'Adjunta las láminas del mismo proyecto y confirma que tienes autorización para utilizarlas.',
   output:'Un expediente con sus planos originales y su revisión documental.',
   labels:['Ingreso local de planos']},
  {id:'lectura',name:'Lectura de planos',title:'2. Leer y contrastar los planos',
   auto:'Leer las evidencias con el proveedor seleccionado y conservar los datos obtenidos junto a su ubicación en el plano.',
   human:'Revisa los datos señalados como dudosos. Una lectura confirmada solo acredita lo que se leyó; la revisión estructural se hace después.',
   output:'Datos del plano con evidencia. La cantidad de lecturas no acredita que la estructura esté completa.',
   labels:['Preparación visual local','Preparación explícita de fotografías','Proveedor visual deliberado','Respuestas visuales locales']},
  {id:'geometria',name:'Geometría y modelo 3D',title:'3. Reconstruir y comprobar la geometría',
   auto:'Relacionar medidas, niveles y conexiones para generar la forma del edificio. El paso automático todavía está en desarrollo.',
   human:'Contrasta posiciones, encuentros, vanos y niveles con el plano. Corrige el borrador en el editor de esta pantalla y conserva una nueva versión.',
   output:'Una geometría trazable. No avanzar a ETABS con plantas incompletas o conexiones sin resolver.',
   labels:['Conversión explícita de lecturas revisadas','Contingencia tabular supervisada','Geometría versionada','Contraste espacial de geometría y plano']},
  {id:'ingenieria',name:'Revisión de ingeniería',title:'4. Definir y revisar las hipótesis de ingeniería',
   auto:'Comprobar la coherencia entre geometría, materiales, secciones, cargas y configuración del análisis.',
   human:'Aporta los datos que los planos no contienen: condiciones del terreno, hipótesis de modelado y decisiones técnicas justificadas. Revisa la representación estructural antes de aprobarla.',
   output:'Configuración vinculada a una geometría concreta, con fuentes y faltantes explícitos.',
   labels:['Configuración estructural','Contexto técnico declarado']},
  {id:'etabs',name:'Construcción en ETABS',title:'5. Construir y releer el modelo en ETABS',
   auto:'Enviar al motor la geometría y configuración revisadas, conservar el archivo y comparar lo construido con lo solicitado.',
   human:'Revisa que ETABS recibió los elementos, materiales, cargas y apoyos previstos. La aprobación corresponde a esa versión del modelo.',
   output:'Archivo de ETABS y evidencia de relectura. Abrir el programa por sí solo no acredita un modelo correcto.',
   labels:['Construcción del modelo ETABS','Modelos y resultados conservados']},
  {id:'analisis',name:'Análisis y comprobaciones',title:'6. Calcular y comprobar los resultados',
   auto:'Ejecutar los casos definidos, recuperar las tablas y aplicar los controles implementados.',
   human:'Evalúa advertencias, comportamiento estructural y límites de las hipótesis. Un cálculo terminado no equivale a conformidad normativa.',
   output:'Resultados vinculados al análisis y sus controles; observaciones visibles antes del informe.',
   labels:['Análisis deliberado del modelo revisado','Lectura deliberada de tablas','Correspondencias de tablas y normalización','Recuperación de normalizaciones','Controles internos posteriores al análisis','Revisión propia declarada de resultados']},
  {id:'informe',name:'Informe y entrega',title:'7. Preparar la entrega técnica',
   auto:'Reunir resultados, fuentes, hipótesis, comprobaciones y pendientes en un informe reproducible.',
   human:'Revisa el alcance y las conclusiones que vas a presentar. Conserva las limitaciones que afectan a la interpretación.',
   output:'Informe descargable y panel de resultados de la versión seleccionada.',
   labels:['Explicaciones sustentadas pendientes','Informes del resultado seleccionado','Paneles del resultado seleccionado']}
 ];
 const main=document.querySelector('main'),intro=main.querySelector('.intro');
 intro.querySelector('h1').textContent='Del plano al modelo, paso a paso';
 intro.querySelector('.eyebrow').textContent='ESPACIO DE TRABAJO DE INGENIERÍA';
 const desc=intro.querySelector('p:not(.eyebrow)');if(desc)desc.textContent='Consulta el avance, revisa las decisiones técnicas y conserva cada versión dentro del sistema.';
 const original=Array.from(main.children).filter(n=>n!==intro);
 const layout=document.createElement('div');layout.className='stage-layout';
 const nav=document.createElement('nav');nav.className='stage-nav';nav.setAttribute('aria-label','Etapas del proyecto');
 const content=document.createElement('div');content.className='stage-content';
 layout.append(nav,content);main.append(layout);
 const containers=new Map(),buttons=new Map();
 stages.forEach((stage,index)=>{
  const button=document.createElement('button');button.type='button';button.dataset.stage=stage.id;
  button.innerHTML='<span class="stage-number">'+(index+1)+'</span><span>'+stage.name+'<small class="stage-badge">Por consultar</small></span>';
  nav.append(button);buttons.set(stage.id,button);
  const box=document.createElement('div');box.className='stage-pane';box.dataset.stage=stage.id;box.hidden=true;
  const header=document.createElement('section');header.className='stage-guide';
  const title=document.createElement('h2');title.tabIndex=-1;title.textContent=stage.title;header.append(title);
  const cards=document.createElement('div');cards.className='stage-guide-grid';
  [['Procesamiento del programa',stage.auto],['Intervención del ingeniero',stage.human],['Resultado de la etapa',stage.output]].forEach(([name,text])=>{
   const card=document.createElement('div'),strong=document.createElement('h3'),p=document.createElement('p');strong.textContent=name;p.textContent=text;card.append(strong,p);cards.append(card);
  });header.append(cards);box.append(header);containers.set(stage.id,box);content.append(box);
  button.addEventListener('click',()=>show(stage.id,true));
 });
 original.forEach(node=>{
  if(node.tagName==='FOOTER'){
   const details=document.createElement('details'),summary=document.createElement('summary');
   details.className='advanced-panel';summary.textContent='Historial y procedencia de la extracción';details.append(summary,node);containers.get('lectura').append(details);return;
  }
  if(node.classList.contains('scope')||node.id==='mensaje'){main.insertBefore(node,layout);return;}
  let stage=node.classList.contains('workspace')||node.classList.contains('versionbar')?'lectura':
   stages.find(s=>s.labels.includes(node.getAttribute('aria-label')))?.id;
  if(stage)containers.get(stage).append(node);else containers.get('ingenieria').append(node);
 });
 const actions=document.createElement('div');actions.className='stage-actions';
 const back=document.createElement('button'),next=document.createElement('button');back.type=next.type='button';
 back.textContent='← Etapa anterior';next.textContent='Siguiente etapa →';actions.append(back,next);content.append(actions);
 let current=0;
 function show(id,focus=false){
  const selected=stages.findIndex(s=>s.id===id);if(selected<0)return;current=selected;
  for(const s of stages){const active=s.id===id;containers.get(s.id).hidden=!active;buttons.get(s.id).setAttribute('aria-current',active?'step':'false');}
  back.disabled=current===0;next.disabled=current===stages.length-1;
  // Cambiar de etapa no ejecuta trabajos ni marca pasos como completados.
  if(focus)containers.get(id).querySelector('h2').focus();
  window.dispatchEvent(new CustomEvent('d2m-stage',{detail:id}));
 }
 back.addEventListener('click',()=>show(stages[current-1].id,true));next.addEventListener('click',()=>show(stages[current+1].id,true));
 const advancedLabels=['Preparación visual local','Preparación explícita de fotografías','Respuestas visuales locales',
  'Conversión explícita de lecturas revisadas','Contingencia tabular supervisada','Recuperación de normalizaciones'];
 for(const label of advancedLabels){
  const panel=Array.from(document.querySelectorAll('section[aria-label]')).find(s=>s.getAttribute('aria-label')===label);
  if(!panel)continue;
  const details=document.createElement('details');details.className='advanced-panel';const summary=document.createElement('summary');
  summary.textContent=label+' · herramientas adicionales';panel.before(details);details.append(summary,panel);
 }
 function badge(id,text){buttons.get(id).querySelector('small').textContent=text;}
 function update(){
  badge('ingreso',docs?docs.documentos?.length+' documentos':'Sin proyecto');
  badge('lectura',record?(record.datos?.candidatos?.length||0)+' lecturas · revisar':'Sin extracción abierta');
  badge('geometria',geoRecord?'Geometría '+geoRecord.datos.revision.estado:'Sin geometría abierta');
 }
 window.addEventListener('d2m-case',()=>{update();if(!docs){badge('ingenieria','Por consultar');badge('etabs','Por consultar');badge('analisis','Por consultar');badge('informe','Por consultar');}});
 window.addEventListener('d2m-geometry-opened',update);
 window.addEventListener('d2m-readings-opened',update);
 window.addEventListener('d2m-config',e=>badge('ingenieria',e.detail?'Configuración abierta':'Sin configuración abierta'));
 window.addEventListener('d2m-model',e=>badge('etabs',e.detail?'Modelo conservado abierto':'Sin modelo abierto'));
 window.addEventListener('d2m-result',e=>badge('analisis',e.detail?'Resultados abiertos':'Sin resultados abiertos'));
 window.D2MEtapas={show,update,containers};show('ingreso');update();
})();
