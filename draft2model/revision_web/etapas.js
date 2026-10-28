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

   labels:['Verificación de Parámetros Normativos de Entrada','Configuración estructural','Contexto técnico declarado']},

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

 const roadmap=document.createElement('section');

 roadmap.className='engineering-roadmap';

 roadmap.setAttribute('aria-label','Flujograma general del proyecto');

 roadmap.innerHTML=`

  <div class="roadmap-header">

   <div class="roadmap-badge">MAPA DE RUTA DEL MODELADO ESTRUCTURAL</div>

   <span class="roadmap-subtitle">Proceso de 7 fases: del plano al modelo analizado en ETABS</span>

  </div>

  <div class="roadmap-track">

   <button type="button" class="roadmap-step active" data-step="ingreso">

    <span class="step-num">1</span>

    <span class="step-code">DOCS</span>

    <strong class="step-title">Proyecto y Planos</strong>

    <small class="step-desc">Carga de láminas</small>

   </button>

   <div class="step-arrow">→</div>

   <button type="button" class="roadmap-step" data-step="lectura">

    <span class="step-num">2</span>

    <span class="step-code">VISION</span>

    <strong class="step-title">Lectura IA</strong>

    <small class="step-desc">Ejes, cotas, columnas</small>

   </button>

   <div class="step-arrow">→</div>

   <button type="button" class="roadmap-step" data-step="geometria">

    <span class="step-num">3</span>

    <span class="step-code">GEOM</span>

    <strong class="step-title">Geometría 3D</strong>

    <small class="step-desc">Pórticos y muros</small>

   </button>

   <div class="step-arrow">→</div>

   <button type="button" class="roadmap-step" data-step="ingenieria">

    <span class="step-num">4</span>

    <span class="step-code">NORMA</span>

    <strong class="step-title">Norma E.030</strong>

    <small class="step-desc">Z, U, S, R, f'c</small>

   </button>

   <div class="step-arrow">→</div>

   <button type="button" class="roadmap-step" data-step="etabs">

    <span class="step-num">5</span>

    <span class="step-code">ETABS</span>

    <strong class="step-title">ETABS</strong>

    <small class="step-desc">Modelo .EDB</small>

   </button>

   <div class="step-arrow">→</div>

   <button type="button" class="roadmap-step" data-step="analisis">

    <span class="step-num">6</span>

    <span class="step-code">CALC</span>

    <strong class="step-title">Análisis</strong>

    <small class="step-desc">Derivas y esfuerzos</small>

   </button>

   <div class="step-arrow">→</div>

   <button type="button" class="roadmap-step" data-step="informe">

    <span class="step-num">7</span>

    <span class="step-code">MEMORIA</span>

    <strong class="step-title">Informe</strong>

    <small class="step-desc">Memoria técnica</small>

   </button>

  </div>

 `;

 roadmap.querySelectorAll('.roadmap-step').forEach(btn=>{

  btn.addEventListener('click',()=>show(btn.dataset.step,true));

 });



 const layout=document.createElement('div');layout.className='stage-layout';

 const nav=document.createElement('nav');nav.className='stage-nav';nav.setAttribute('aria-label','Etapas del proyecto');

 const content=document.createElement('div');content.className='stage-content';

 layout.append(nav,content);
 if(intro && intro.parentNode === main){
  intro.after(roadmap);
  roadmap.after(layout);
 } else {
  main.append(roadmap, layout);
 }

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

 let footerNode = null;
 const lecturaLabels = ['Preparación visual local', 'Preparación explícita de fotografías', 'Proveedor visual deliberado', 'Respuestas visuales locales', 'Contingencia JSON de extracción'];
 const geoLabels = ['Conversión explícita de lecturas revisadas', 'Contingencia tabular supervisada', 'Contraste espacial de geometría y plano'];

 original.forEach(node=>{
  if(node.tagName==='FOOTER'){
   footerNode = node;
   return;
  }
  if(node.classList.contains('scope')||node.id==='mensaje'){main.insertBefore(node,layout);return;}
  const ariaLabel = node.getAttribute('aria-label');
  if(lecturaLabels.includes(ariaLabel) || geoLabels.includes(ariaLabel)){
   return;
  }
  let stage=node.classList.contains('workspace')||node.classList.contains('versionbar')?'lectura':
   stages.find(s=>s.labels.includes(ariaLabel))?.id;
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
  roadmap.querySelectorAll('.roadmap-step').forEach(b=>{b.classList.toggle('active',b.dataset.step===id);});
  if(focus)containers.get(id).querySelector('h2').focus();
  window.dispatchEvent(new CustomEvent('d2m-stage',{detail:id}));
 }
 back.addEventListener('click',()=>show(stages[current-1].id,true));next.addEventListener('click',()=>show(stages[current+1].id,true));

 const toolGuides = {
  'Preparación visual local': {
   title: '1. Recortes locales y evidencias visuales',
   desc: 'Herramienta para seleccionar un cuadrante o región específica de un plano con alta densidad gráfica para inspección focalizada.'
  },
  'Preparación explícita de fotografías': {
   title: '2. Calibración de escaneos y fotografías',
   desc: 'Ajusta resolución en DPI y orientación para planos que provienen de escaneos o imágenes no vectoriales.'
  },
  'Proveedor visual deliberado': {
   title: '3. Inspección técnica de paquetes y tokens',
   desc: 'Comprueba el paquete crudo de imágenes, la estimación de tokens y los costos en USD antes de la transmisión.'
  },
  'Respuestas visuales locales': {
   title: '4. Respuestas crudas del proveedor (JSON)',
   desc: 'Inspecciona las respuestas crudas devueltas por el modelo antes de su estructuración como contrato.'
  },
  'Contingencia JSON de extracción': {
   title: '5. Contingencia JSON de extracción',
   desc: 'Permite importar un archivo JSON de extracción previamente validado en caso de contingencia.'
  }
 };

 // Grupo unificado para Fase 2: Lectura de planos
 const lecturaUnified = document.createElement('details');
 lecturaUnified.className = 'advanced-tools-unified';
 lecturaUnified.id = 'lecturaAdvancedGroup';
 const lecturaSum = document.createElement('summary');
 lecturaSum.className = 'advanced-tools-unified-summary';
 lecturaSum.innerHTML = `
   <div class="summary-left">
     <span class="advanced-badge">Herramientas Técnicas Opcionales</span>
     <strong class="summary-title">Auditoría, Contingencia y Procedencia de la Lectura</strong>
   </div>
   <small class="summary-subtitle">Recortes manuales, calibración de imágenes, inspección de tokens y firmas criptográficas</small>
 `;
 lecturaUnified.append(lecturaSum);

 const lecturaNotice = document.createElement('div');
 lecturaNotice.className = 'advanced-tools-notice';
 lecturaNotice.innerHTML = `
   <p><strong>Nota técnica para el ingeniero:</strong> Las funciones principales de lectura e interpretación de planos se gestionan arriba con el motor de IA y el visor de contraste. Las opciones agrupadas en este bloque son secundarias, diseñadas para inspección técnica profunda, recortes específicos o verificación criptográfica de procedencia.</p>
 `;
 lecturaUnified.append(lecturaNotice);

 for (const label of lecturaLabels) {
  const panel = Array.from(document.querySelectorAll('section[aria-label]')).find(s => s.getAttribute('aria-label') === label);
  if (!panel) continue;
  const guide = toolGuides[label] || { title: label, desc: 'Herramienta técnica adicional.' };
  const card = document.createElement('div');
  card.className = 'advanced-subtool-card';
  const header = document.createElement('div');
  header.className = 'advanced-subtool-header';
  header.innerHTML = `<h4 class="subtool-title">${guide.title}</h4><p class="subtool-desc">${guide.desc}</p>`;
  card.append(header, panel);
  lecturaUnified.append(card);
 }

 if (footerNode) {
  const footerCard = document.createElement('div');
  footerCard.className = 'advanced-subtool-card';
  const header = document.createElement('div');
  header.className = 'advanced-subtool-header';
  header.innerHTML = `<h4 class="subtool-title">6. Trazabilidad y firmas criptográficas del expediente</h4><p class="subtool-desc">Verifica las huellas SHA-256 de las láminas originales y de la versión de lectura para asegurar su inmutabilidad.</p>`;
  footerCard.append(header, footerNode);
  lecturaUnified.append(footerCard);
 }
 containers.get('lectura').append(lecturaUnified);

 // Grupo unificado para Fase 3: Geometría
 const geoUnified = document.createElement('details');
 geoUnified.className = 'advanced-tools-unified';
 geoUnified.id = 'geometriaAdvancedGroup';
 const geoSum = document.createElement('summary');
 geoSum.className = 'advanced-tools-unified-summary';
 geoSum.innerHTML = `
   <div class="summary-left">
     <span class="advanced-badge">Herramientas Técnicas Opcionales</span>
     <strong class="summary-title">Auditoría, Calibración Manual y Contingencia de Geometría</strong>
   </div>
   <small class="summary-subtitle">Contrato JSON de geometría, calibración manual de puntos, superposición UV y contingencia tabular</small>
 `;
 geoUnified.append(geoSum);
 const geoNotice = document.createElement('div');
 geoNotice.className = 'advanced-tools-notice';
 geoNotice.innerHTML = `
   <p><strong>Nota técnica para el ingeniero:</strong> La visualización 3D principal y la aprobación formal de la geometría se realizan arriba. Las opciones agrupadas en este bloque son herramientas secundarias de auditoría técnica, digitalización punto a punto o contingencia tabular.</p>
 `;
 geoUnified.append(geoNotice);

 const geoGuides = {
  'Conversión explícita de lecturas revisadas': {
   title: '1. Conversión explícita de lecturas',
   desc: 'Permite convertir manualmente candidatos aprobados a nodos y elementos de geometría.'
  },
  'Contingencia tabular supervisada': {
   title: '2. Contingencia tabular supervisada',
   desc: 'Editor tabular auxiliar para ajustes locales de geometría en CSV o XLSX sin emplear el modelo 3D.'
  },
  'Contraste espacial de geometría y plano': {
   title: '3. Superposición y contraste espacial plano-3D',
   desc: 'Herramienta para definir anclas y contrastar la geometría sobre la cuadrícula del plano original.'
  }
 };

 for (const label of geoLabels) {
  const panel = Array.from(document.querySelectorAll('section[aria-label]')).find(s => s.getAttribute('aria-label') === label);
  if (!panel) continue;
  const guide = geoGuides[label] || { title: label, desc: 'Herramienta de contingencia.' };
  const card = document.createElement('div');
  card.className = 'advanced-subtool-card';
  const header = document.createElement('div');
  header.className = 'advanced-subtool-header';
  header.innerHTML = `<h4 class="subtool-title">${guide.title}</h4><p class="subtool-desc">${guide.desc}</p>`;
  card.append(header, panel);
  geoUnified.append(card);
 }
 containers.get('geometria').append(geoUnified);

 function organizeStage3() {
  const geoContainer = containers.get('geometria');
  if (!geoContainer) return;
  const geoGroup = document.getElementById('geometriaAdvancedGroup');
  if (!geoGroup) return;

  const digPanel = geoContainer.querySelector('section[aria-label="Digitización calibrada local en borrador"]');
  if (digPanel && !geoGroup.contains(digPanel)) {
   const card = document.createElement('div');
   card.className = 'advanced-subtool-card';
   const header = document.createElement('div');
   header.className = 'advanced-subtool-header';
   header.innerHTML = '<h4 class="subtool-title">4. Calibración y digitalización manual de puntos</h4><p class="subtool-desc">Herramienta de contingencia para calibrar ubicaciones normalizadas locales y ajustar puntos de contorno manualmente sin coordenadas métricas.</p>';
   card.append(header, digPanel);
   geoGroup.append(card);
  }

  const guide = geoContainer.querySelector('.stage-guide');
  const viewer = geoContainer.querySelector('.viewer-3d');
  const geoCard = geoContainer.querySelector('section[aria-label="Geometría versionada"]');
  const cntPanel = geoContainer.querySelector('#cntPanel');

  if (guide && viewer && guide.nextElementSibling !== viewer) {
   guide.after(viewer);
  }
  if (viewer && geoCard && viewer.nextElementSibling !== geoCard) {
   viewer.after(geoCard);
  }
  if (geoCard && cntPanel && geoCard.nextElementSibling !== cntPanel) {
   geoCard.after(cntPanel);
  }
  if (geoGroup && geoContainer.lastElementChild !== geoGroup) {
   geoContainer.append(geoGroup);
  }
 }
 if (typeof window !== 'undefined') {
  window.addEventListener('load', organizeStage3);
  if (typeof setTimeout === 'function') {
   setTimeout(organizeStage3, 50);
   setTimeout(organizeStage3, 250);
  }
  window.addEventListener('d2m-stage', e => { if (e.detail === 'geometria') organizeStage3(); });
 }

 // Grupo unificado para Fase 4: Ingenieria (Malla 0.4, Politicas y Contexto)
 const ingUnified = document.createElement('details');
 ingUnified.className = 'advanced-tools-unified';
 ingUnified.id = 'ingenieriaAdvancedGroup';
 const ingSum = document.createElement('summary');
 ingSum.className = 'advanced-tools-unified-summary';
 ingSum.innerHTML = `
   <div class="summary-left">
     <span class="advanced-badge">Herramientas Técnicas Opcionales</span>
     <strong class="summary-title">Auditoría de Malla 0.4, Contexto Territorial y Contingencias Técnicas</strong>
   </div>
   <small class="summary-subtitle">Preparación reproducible de malla 0.4, políticas explícitas de nodos, contexto territorial y reglas</small>
 `;
 ingUnified.append(ingSum);
 const ingNotice = document.createElement('div');
 ingNotice.className = 'advanced-tools-notice';
 ingNotice.innerHTML = `
   <p><strong>Nota técnica para el ingeniero:</strong> La verificación de hipótesis normativas (E.030, E.060, E.020), la definición de propiedades físicas y la aprobación formal de la configuración se realizan arriba. Las opciones agrupadas en este bloque son herramientas secundarias para la subdivisión avanzada de malla 0.4 o la vinculación de cartografía y contexto territorial.</p>
 `;
 ingUnified.append(ingNotice);
 containers.get('ingenieria').append(ingUnified);

 function organizeStage4() {
  const ingContainer = containers.get('ingenieria');
  if (!ingContainer) return;
  const ingGroup = document.getElementById('ingenieriaAdvancedGroup');
  if (!ingGroup) return;

  // 1. Malla 0.4 fieldset
  const mallaPanel = document.getElementById('mallaPanel');
  if (mallaPanel && !ingGroup.contains(mallaPanel)) {
   const card = document.createElement('div');
   card.className = 'advanced-subtool-card';
   const header = document.createElement('div');
   header.className = 'advanced-subtool-header';
   header.innerHTML = '<h4 class="subtool-title">1. Preparación reproducible de malla 0.4</h4><p class="subtool-desc">Partición, compatibilidad y cortes Z declarados para contratos 0.4. Herramienta de contingencia para análisis de elementos finitos.</p>';
   card.append(header, mallaPanel);
   ingGroup.append(card);
  }

  // 2. Politicas explicitas de malla
  const pmPanel = ingContainer.querySelector('section[aria-label="Políticas explícitas de malla"]');
  if (pmPanel && !ingGroup.contains(pmPanel)) {
   const card = document.createElement('div');
   card.className = 'advanced-subtool-card';
   const header = document.createElement('div');
   header.className = 'advanced-subtool-header';
   header.innerHTML = '<h4 class="subtool-title">2. Políticas explícitas de nodos de malla</h4><p class="subtool-desc">Reglas para restricciones en planos Z y diafragmas de nodos calculados por mallado.</p>';
   card.append(header, pmPanel);
   ingGroup.append(card);
  }

  // 3. Contexto tecnico declarado
  const ctxPanel = ingContainer.querySelector('section[aria-label="Contexto técnico declarado"]');
  if (ctxPanel && !ingGroup.contains(ctxPanel)) {
   const card = document.createElement('div');
   card.className = 'advanced-subtool-card';
   const header = document.createElement('div');
   header.className = 'advanced-subtool-header';
   header.innerHTML = '<h4 class="subtool-title">3. Contexto técnico, sitio y reglas reproducibles</h4><p class="subtool-desc">Corpus documental complementario y consultas de coordenadas territoriales EPSG:4326.</p>';
   card.append(header, ctxPanel);
   ingGroup.append(card);
  }

  // Estilizar panel de lectura de parametros con IA
  const parPanel = ingContainer.querySelector('section[aria-label="Lectura dirigida de ingeniería"]');
  if (parPanel && !parPanel.classList.contains('ai-reader-card')) {
   parPanel.classList.add('ai-reader-card');
  }

  // Ordenar visualmente el contenedor
  const guide = ingContainer.querySelector('.stage-guide');
  const normCard = document.getElementById('normParamPanel');
  const configCard = ingContainer.querySelector('section[aria-label="Configuración estructural"]');
  const preConfigPanel = ingContainer.querySelector('section[aria-label="Preparación de configuración de ingeniería"]');

  if (guide && normCard && guide.nextElementSibling !== normCard) {
   guide.after(normCard);
  }
  if (normCard && configCard && normCard.nextElementSibling !== configCard) {
   normCard.after(configCard);
  }
  if (configCard && preConfigPanel && configCard.nextElementSibling !== preConfigPanel) {
   configCard.after(preConfigPanel);
  }
  if (preConfigPanel && parPanel && preConfigPanel.nextElementSibling !== parPanel) {
   preConfigPanel.after(parPanel);
  }
  if (ingGroup && ingContainer.lastElementChild !== ingGroup) {
   ingContainer.append(ingGroup);
  }
 }

 if (typeof window !== 'undefined') {
  window.addEventListener('load', organizeStage4);
  if (typeof setTimeout === 'function') {
   setTimeout(organizeStage4, 50);
   setTimeout(organizeStage4, 250);
  }
  window.addEventListener('d2m-stage', e => { if (e.detail === 'ingenieria') organizeStage4(); });
 }

 // Grupo unificado para Fase 5: Construccion en ETABS (Relectura de auditoria y resultados previos)
 const etabsUnified = document.createElement('details');
 etabsUnified.className = 'advanced-tools-unified';
 etabsUnified.id = 'etabsAdvancedGroup';
 const etabsSum = document.createElement('summary');
 etabsSum.className = 'advanced-tools-unified-summary';
 etabsSum.innerHTML = `
   <div class="summary-left">
     <span class="advanced-badge">Herramientas Técnicas Opcionales</span>
     <strong class="summary-title">Herramientas de Relectura Independiente y Auditoría del Motor</strong>
   </div>
   <small class="summary-subtitle">Relectura técnica de 13 magnitudes numéricas, comprobación de rigidez y contingencia pre-cálculo</small>
 `;
 etabsUnified.append(etabsSum);
 const etabsNotice = document.createElement('div');
 etabsNotice.className = 'advanced-tools-notice';
 etabsNotice.innerHTML = `
   <p><strong>Nota técnica para el ingeniero:</strong> La generación del modelo en ETABS y la lista de chequeo de ingeniería se encuentran arriba. Las herramientas en este bloque son de contingencia y auditoría independiente (lectura de rigideces numéricas en copia privada y verificación de indicadores previos).</p>
 `;
 etabsUnified.append(etabsNotice);
 containers.get('etabs').append(etabsUnified);

 function organizeStage5() {
  const etabsContainer = containers.get('etabs');
  if (!etabsContainer) return;
  const etabsGroup = document.getElementById('etabsAdvancedGroup');
  if (!etabsGroup) return;

  // 1. Relectura independiente fieldset
  const vmFieldset = etabsContainer.querySelector('fieldset[aria-label="Relectura del modelo guardado"]');
  if (vmFieldset && !etabsGroup.contains(vmFieldset)) {
   const card = document.createElement('div');
   card.className = 'advanced-subtool-card';
   const header = document.createElement('div');
   header.className = 'advanced-subtool-header';
   header.innerHTML = '<h4 class="subtool-title">1. Relectura independiente de 13 magnitudes numéricas</h4><p class="subtool-desc">Abre una copia privada temporal en ETABS para medir y verificar matrices de rigidez y conectividad sin alterar el modelo.</p>';
   card.append(header, vmFieldset);
   etabsGroup.append(card);
  }

  // 2. Previsualizacion de resultados previos
  const resTable = etabsContainer.querySelector('.results-scroll');
  const resVersionBar = Array.from(etabsContainer.querySelectorAll('.versionbar')).find(vb => vb.querySelector('#resultadoVersion'));
  if (resTable && !etabsGroup.contains(resTable)) {
   const card = document.createElement('div');
   card.className = 'advanced-subtool-card';
   const header = document.createElement('div');
   header.className = 'advanced-subtool-header';
   header.innerHTML = '<h4 class="subtool-title">2. Indicadores y tablas de resultados pre-cálculo</h4><p class="subtool-desc">Visualizador de tablas de resultados previos asociados al expediente.</p>';
   card.append(header);
   if (resVersionBar) card.append(resVersionBar);
   card.append(resTable);
   const resAvisos = document.getElementById('resultadoAvisos');
   if (resAvisos) card.append(resAvisos);
   etabsGroup.append(card);
  }

  // Ordenar visualmente el contenedor
  const guide = etabsContainer.querySelector('.stage-guide');
  const buildCard = etabsContainer.querySelector('section[aria-label="Construcción del modelo ETABS"]');
  const modelCard = etabsContainer.querySelector('section[aria-label="Modelos y resultados conservados"]');

  if (guide && buildCard && guide.nextElementSibling !== buildCard) {
   guide.after(buildCard);
  }
  if (buildCard && modelCard && buildCard.nextElementSibling !== modelCard) {
   buildCard.after(modelCard);
  }
  if (etabsGroup && etabsContainer.lastElementChild !== etabsGroup) {
   etabsContainer.append(etabsGroup);
  }
 }

 if (typeof window !== 'undefined') {
  window.addEventListener('load', organizeStage5);
  if (typeof setTimeout === 'function') {
   setTimeout(organizeStage5, 50);
   setTimeout(organizeStage5, 250);
  }
  window.addEventListener('d2m-stage', e => { if (e.detail === 'etabs') organizeStage5(); });
 }

 // Grupo unificado para Fase 6: Análisis y Comprobaciones (Tablas, Mapeos y Contingencias)
 const analisisUnified = document.createElement('details');
 analisisUnified.className = 'advanced-tools-unified';
 analisisUnified.id = 'analisisAdvancedGroup';
 const analisisSum = document.createElement('summary');
 analisisSum.className = 'advanced-tools-unified-summary';
 analisisSum.innerHTML = `
   <div class="summary-left">
     <span class="advanced-badge">Herramientas Técnicas Opcionales</span>
     <strong class="summary-title">Herramientas de Lectura de Tablas, Mapeo y Normalización de Resultados</strong>
   </div>
   <small class="summary-subtitle">Lectura deliberada de tablas crudas de ETABS, correspondencias de indicadores y recuperación de normalizaciones interrumpidas</small>
 `;
 analisisUnified.append(analisisSum);
 const analisisNotice = document.createElement('div');
 analisisNotice.className = 'advanced-tools-notice';
 analisisNotice.innerHTML = `
   <p><strong>Nota técnica para el ingeniero:</strong> La ejecución de la solución matricial en ETABS, la verificación de controles normativos (masa modal, equilibrio, avisos de solver) y la aprobación declarada de resultados se realizan en las tarjetas superiores. Las herramientas en este bloque son de contingencia técnica para la inspección y lectura directa de tablas de base de datos de ETABS, la configuración manual de correspondencias y la resolución de normalizaciones interrumpidas.</p>
 `;
 analisisUnified.append(analisisNotice);
 containers.get('analisis').append(analisisUnified);

 function organizeStage6() {
  const analisisContainer = containers.get('analisis');
  if (!analisisContainer) return;
  const analisisGroup = document.getElementById('analisisAdvancedGroup');
  if (!analisisGroup) return;

  // 1. Lectura deliberada de tablas
  const lectPanel = analisisContainer.querySelector('section[aria-label="Lectura deliberada de tablas"]');
  if (lectPanel && !analisisGroup.contains(lectPanel)) {
   const card = document.createElement('div');
   card.className = 'advanced-subtool-card';
   const header = document.createElement('div');
   header.className = 'advanced-subtool-header';
   header.innerHTML = '<h4 class="subtool-title">1. Lectura deliberada de tablas crudas de ETABS</h4><p class="subtool-desc">Permite solicitar y extraer tablas de salida específicas (desplazamientos, derivas, participación modal) en una instancia privada de ETABS.</p>';
   card.append(header, lectPanel);
   analisisGroup.append(card);
  }

  // 2. Correspondencias de tablas y normalización
  const mapPanel = analisisContainer.querySelector('section[aria-label="Correspondencias de tablas y normalización"]');
  if (mapPanel && !analisisGroup.contains(mapPanel)) {
   const card = document.createElement('div');
   card.className = 'advanced-subtool-card';
   const header = document.createElement('div');
   header.className = 'advanced-subtool-header';
   header.innerHTML = '<h4 class="subtool-title">2. Correspondencias de tablas y normalización</h4><p class="subtool-desc">Relaciona cada indicador numérico con una fila y columna de las tablas de salida para la publicación de resultados normalizados.</p>';
   card.append(header, mapPanel);
   analisisGroup.append(card);
  }

  // 3. Recuperación de normalizaciones
  const recPanel = analisisContainer.querySelector('section[aria-label="Recuperación de normalizaciones"]');
  if (recPanel && !analisisGroup.contains(recPanel)) {
   const card = document.createElement('div');
   card.className = 'advanced-subtool-card';
   const header = document.createElement('div');
   header.className = 'advanced-subtool-header';
   header.innerHTML = '<h4 class="subtool-title">3. Recuperación de normalizaciones interrumpidas</h4><p class="subtool-desc">Herramienta de contingencia para desbloquear, comprobar o cancelar operaciones de normalización que hayan quedado pendientes.</p>';
   card.append(header, recPanel);
   analisisGroup.append(card);
  }

  // Alerta contextual en Fase 6 para normalizaciones interrumpidas pendientes
  let alerta = analisisContainer.querySelector('#alertaNormalizacionInterrumpida');
  if (!alerta) {
   alerta = document.createElement('div');
   alerta.id = 'alertaNormalizacionInterrumpida';
   alerta.className = 'alerta-contingencia-box';
   alerta.hidden = true;
   alerta.innerHTML = `
     <div class="alerta-contingencia-text">
       <span class="alerta-contingencia-badge">AVISO OPERATIVO</span>
       <strong>Normalización interrumpida pendiente:</strong>
       <span>Se detectó una publicación incompleta en este caso que bloquea nuevos intentos. Puede comprobar el candidato conservado o cancelar el intento fallido.</span>
     </div>
     <button type="button" id="btnAbrirContingenciaNormalizacion" class="btn-alerta-contingencia">Resolver contingencia</button>
   `;
   const guide = analisisContainer.querySelector('.stage-guide');
   if (guide) guide.after(alerta); else analisisContainer.prepend(alerta);

   alerta.querySelector('#btnAbrirContingenciaNormalizacion')?.addEventListener('click', () => {
     if (analisisGroup) {
       analisisGroup.open = true;
       recPanel?.scrollIntoView({ behavior: 'smooth', block: 'center' });
       const sel = document.getElementById('recuperacionOperacion');
       if (sel) sel.focus();
     }
   });
  }

  // Ordenar visualmente el contenedor en orden lógico de ingeniería:
  // guide -> alerta -> execCard -> controlsCard -> resultsCard -> analisisGroup
  const guide = analisisContainer.querySelector('.stage-guide');
  const execCard = analisisContainer.querySelector('section[aria-label="Análisis deliberado del modelo revisado"]');
  const controlsCard = analisisContainer.querySelector('section[aria-label="Controles internos posteriores al análisis"]');
  const resultsCard = analisisContainer.querySelector('section[aria-label="Revisión propia declarada de resultados"]');

  if (guide && alerta && guide.nextElementSibling !== alerta) {
   guide.after(alerta);
  }
  const prevToExec = alerta || guide;
  if (prevToExec && execCard && prevToExec.nextElementSibling !== execCard) {
   prevToExec.after(execCard);
  }
  if (execCard && controlsCard && execCard.nextElementSibling !== controlsCard) {
   execCard.after(controlsCard);
  }
  if (controlsCard && resultsCard && controlsCard.nextElementSibling !== resultsCard) {
   controlsCard.after(resultsCard);
  }
  if (analisisGroup && analisisContainer.lastElementChild !== analisisGroup) {
   analisisContainer.append(analisisGroup);
  }
 }

 if (typeof window !== 'undefined') {
  window.addEventListener('load', organizeStage6);
  if (typeof setTimeout === 'function') {
   setTimeout(organizeStage6, 50);
   setTimeout(organizeStage6, 250);
  }
  window.addEventListener('d2m-stage', e => { if (e.detail === 'analisis') organizeStage6(); });
 }

 // Grupo unificado para Fase 7: Informe y Entrega (Explicaciones y Contingencias)
 const infUnified = document.createElement('details');
 infUnified.className = 'advanced-tools-unified';
 infUnified.id = 'informeAdvancedGroup';
 const infSum = document.createElement('summary');
 infSum.className = 'advanced-tools-unified-summary';
 infSum.innerHTML = `
   <div class="summary-left">
     <span class="advanced-badge">Herramientas Técnicas Opcionales</span>
     <strong class="summary-title">Auditoría de Explicaciones Determinísticas y Contingencias de Entrega</strong>
   </div>
   <small class="summary-subtitle">Generación local determinística sin consumo de APIs externas y resolución de incertidumbres</small>
 `;
 infUnified.append(infSum);
 const infNotice = document.createElement('div');
 infNotice.className = 'advanced-tools-notice';
 infNotice.innerHTML = `
   <p><strong>Nota técnica para el ingeniero:</strong> La memoria descriptiva oficial y el panel interactivo de resultados se generan y aprueban en las tarjetas superiores. Las herramientas en este bloque son de contingencia técnica local (explicaciones determinísticas sin llamada a proveedores externos y resolución de estados inciertos).</p>
 `;
 infUnified.append(infNotice);
 containers.get('informe').append(infUnified);

 function organizeStage7() {
  const infContainer = containers.get('informe');
  if (!infContainer) return;
  const infGroup = document.getElementById('informeAdvancedGroup');
  if (!infGroup) return;

  // 1. Explicaciones sustentadas pendientes
  const expPanel = infContainer.querySelector('section[aria-label="Explicaciones sustentadas pendientes"]');
  if (expPanel && !infGroup.contains(expPanel)) {
   const card = document.createElement('div');
   card.className = 'advanced-subtool-card';
   const header = document.createElement('div');
   header.className = 'advanced-subtool-header';
   header.innerHTML = '<h4 class="subtool-title">1. Explicación sustentada y contingencia determinística</h4><p class="subtool-desc">Generación de resúmenes locales determinísticos sin llamadas a APIs externas de IA.</p>';
   card.append(header, expPanel);
   infGroup.append(card);
  }

  // Ordenar visualmente el contenedor:
  // guide -> reportCard -> panelCard -> infGroup
  const guide = infContainer.querySelector('.stage-guide');
  const reportCard = infContainer.querySelector('section[aria-label="Informes del resultado seleccionado"]');
  const panelCard = infContainer.querySelector('section[aria-label="Paneles del resultado seleccionado"]');

  if (guide && reportCard && guide.nextElementSibling !== reportCard) {
   guide.after(reportCard);
  }
  if (reportCard && panelCard && reportCard.nextElementSibling !== panelCard) {
   reportCard.after(panelCard);
  }
  if (infGroup && infContainer.lastElementChild !== infGroup) {
   infContainer.append(infGroup);
  }
 }

 if (typeof window !== 'undefined') {
  window.addEventListener('load', organizeStage7);
  if (typeof setTimeout === 'function') {
   setTimeout(organizeStage7, 50);
   setTimeout(organizeStage7, 250);
  }
  window.addEventListener('d2m-stage', e => { if (e.detail === 'informe') organizeStage7(); });
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

