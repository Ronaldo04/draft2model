'use strict';
(()=>{
 const container=window.D2MEtapas?.containers.get('geometria');
 if(!container)return;

 const CRITERIOS_PREDETERMINADOS=Object.freeze({
  residuo_ajuste_max_m:0.02,
  error_control_max_m:0.03,
  incertidumbre_max_m:0.08,
  localizacion_uv:0.005,
  referencia_m:0.005,
  condicion_max:50,
  escala_min_m_por_uv:0.1,
  escala_max_m_por_uv:500,
  coordenada_abs_max_m:1000
 });

 const ESPECIFICACION_CRITERIOS=[
  ['residuo_ajuste_max_m','cntCritResiduo','Residuo máximo de ajuste en anclas (m)','0.02'],
  ['error_control_max_m','cntCritControl','Error máximo en puntos de control (m)','0.03'],
  ['incertidumbre_max_m','cntCritIncertidumbre','Incertidumbre indicativa máxima por punto (m)','0.08'],
  ['localizacion_uv','cntCritLocalizacion','Sensibilidad de ubicación en el dibujo (0 a 1)','0.005'],
  ['referencia_m','cntCritReferencia','Incertidumbre base de referencias existentes (m)','0.005'],
  ['condicion_max','cntCritCondicion','Número de condición máximo del ajuste (mínimo 1)','50'],
  ['escala_min_m_por_uv','cntCritEscalaMin','Escala mínima admisible (m por unidad del dibujo)','0.1'],
  ['escala_max_m_por_uv','cntCritEscalaMax','Escala máxima admisible (m por unidad del dibujo)','500'],
  ['coordenada_abs_max_m','cntCritCoordMax','Magnitud máxima de coordenada resuelta (m)','1000']
 ];

 const MODELOS_SUGERIDOS_OPENAI=['gpt-6.1-sol','gpt-6-astra','gpt-5.4'];
 const MODELO_PREDETERMINADO={openai:'gpt-6.1-sol',gemini:'gemini-3.8-flash'};
 const NUM_RE=/^(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$/;
 const INT_RE=/^(?:0|[1-9]\d*)$/;
 const HEX32_RE=/^[0-9a-f]{32}$/;

 const el=(tag,text,id,cls)=>{
  const n=document.createElement(tag);
  if(text!==undefined)n.textContent=text;
  if(id)n.id=id;
  if(cls)n.className=cls;
  return n;
 };

 const deepClone=val=>val===undefined?undefined:JSON.parse(JSON.stringify(val));

 function nuevoIdSolicitud(){
  const c=window.crypto||globalThis.crypto;
  if(c&&typeof c.randomUUID==='function')return c.randomUUID().replace(/-/g,'').toLowerCase();
  if(c&&typeof c.getRandomValues==='function'){
   const bytes=new Uint8Array(16);
   c.getRandomValues(bytes);
   return Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');
  }
  let out='';
  for(let i=0;i<32;i++)out+=Math.floor(Math.random()*16).toString(16);
  return out;
 }

 function setSelectOptions(sel,items,preferred){
  sel.replaceChildren();
  for(const [val,txt] of items){
   const opt=el('option',txt);
   opt.value=val;
   sel.append(opt);
  }
  if(preferred!==undefined&&items.some(([v])=>v===preferred))sel.value=preferred;
 }

 function textoLimpio(raw){
  if(typeof raw!=='string')return 'Observación pendiente de revisión técnica.';
  return raw
   .replace(/draft2model\.[a-z0-9_.-]+/gi,'registro del sistema')
   .replace(/\bd2m-[a-z0-9-]+\b/gi,'notificación interna')
   .replace(/\bfallido_no_reintentar\b/gi,'detenido sin reintento')
   .replace(/\bcontornos_borrador\b/gi,'borrador conservado')
   .replace(/\ben_ejecucion\b/gi,'en curso')
   .trim()||'Observación pendiente de revisión técnica.';
 }

 // --- Construcción del DOM (etapa 3: geometría) ---
 const panel=el('section',undefined,'cntPanel','geometry ai-reader-card');
 panel.setAttribute('aria-label','Recorrido automático de contornos');

 const heading=el('h2','Detección e Incorporación de Contornos Faltantes con IA');
 const intro=el(
  'p',
  'El programa lee correspondencias y contornos propuestos sobre los planos originales, calibra localmente cada dibujo con las referencias de la geometría abierta y conserva una versión derivada en borrador junto con su preparación de ingeniería. Toda salida es parcial: no sustituye la revisión profesional ni ejecuta ETABS.'
 );

 // Bloque 1: Vínculo con geometría abierta y preparación de ingeniería
 const vinculoBox=el('fieldset',undefined,'cntVinculoBox');
 vinculoBox.append(el('legend','1. Vínculo con la geometría abierta y su preparación'));
 const vinculoEstado=el('p','Abre una versión geométrica comprobada y su preparación de ingeniería para comenzar.','cntVinculoEstado');
 vinculoEstado.setAttribute('role','status');
 vinculoEstado.setAttribute('aria-live','polite');

 const ramasWrap=el('div',undefined,'cntRamasWrap','versionbar');
 ramasWrap.hidden=true;
 const ramasLabel=el('label','Ramas de preparación disponibles para esta geometría');
 ramasLabel.htmlFor='cntRamaPreparacion';
 const ramasSelect=el('select',undefined,'cntRamaPreparacion');
 setSelectOptions(ramasSelect,[['','Selecciona una preparación']]);
 const ramasDiv=el('div');
 ramasDiv.append(ramasLabel,ramasSelect);
 const ramasAbrirBtn=el('button','Usar preparación seleccionada','cntAbrirRama');
 ramasAbrirBtn.type='button';
 ramasWrap.append(ramasDiv,ramasAbrirBtn);
 vinculoBox.append(vinculoEstado,ramasWrap);

 // Bloque 2: Formulario de lectura y criterios de calibración
 const form=el('form',undefined,'cntForm');
 form.setAttribute('aria-label','Configurar lectura automática de contornos');

 const rowProv=el('div',undefined,undefined,'two');
 const colProv=el('div'),colMod=el('div');
 const lblProv=el('label','Proveedor de lectura visual');
 lblProv.htmlFor='cntProveedor';
 const selProv=el('select',undefined,'cntProveedor');
 setSelectOptions(selProv,[['openai','OpenAI'],['gemini','Google Gemini']],'openai');
 colProv.append(lblProv,selProv);

 const lblMod=el('label','Modelo seleccionado');
 lblMod.htmlFor='cntModelo';
 const inpMod=el('input',undefined,'cntModelo');
 inpMod.type='text';
 inpMod.value='gpt-6.1-sol';
 inpMod.maxLength=128;
 inpMod.required=true;
 inpMod.setAttribute('list','cntModelosSugeridos');
 const datalist=el('datalist',undefined,'cntModelosSugeridos');
 for(const m of MODELOS_SUGERIDOS_OPENAI){
  const opt=el('option');
  opt.value=m;
  datalist.append(opt);
 }
 colMod.append(lblMod,inpMod,datalist);
 rowProv.append(colProv,colMod);

 const lblTokens=el('label','Límite máximo de respuesta (256 a 65536)');
 lblTokens.htmlFor='cntTokens';
 const inpTokens=el('input',undefined,'cntTokens');
 inpTokens.type='number';
 inpTokens.min='256';
 inpTokens.max='65536';
 inpTokens.step='1';
 inpTokens.value='32768';
 inpTokens.required=true;

 const cuotaInfo=el('p','Comprobando disponibilidad de solicitudes autorizadas…','cntCuota','hint');

 // Details avanzado de 9 criterios numéricos de calibración
 const detailsCriterios=el('details',undefined,'cntCriteriosDetalle');
 const summaryCriterios=el('summary','Criterios numéricos de calibración (opciones avanzadas · no normativos)');
 const hintCriterios=el(
  'p',
  'Estos nueve parámetros acotan el cálculo algebraico local de cada dibujo. Son criterios de cálculo del programa: no representan límites normativos, verificación independiente ni aprobación de ingeniería.',
  undefined,
  'hint'
 );
 const gridCriterios=el('div',undefined,'cntCriteriosGrid');
 const inputsCriterios={};
 for(const [key,inputId,labelText,defVal] of ESPECIFICACION_CRITERIOS){
  const wrap=el('div');
  const lbl=el('label',labelText);
  lbl.htmlFor=inputId;
  const inp=el('input',undefined,inputId);
  inp.type='number';
  inp.step='any';
  inp.min='0.000001';
  inp.value=defVal;
  inp.required=true;
  inputsCriterios[key]=inp;
  wrap.append(lbl,inp);
  gridCriterios.append(wrap);
 }
 const btnResetCriterios=el('button','Restablecer valores predeterminados','cntResetCriterios');
 btnResetCriterios.type='button';
 detailsCriterios.append(summaryCriterios,hintCriterios,gridCriterios,btnResetCriterios);

 const chkCriterios=el('input',undefined,'cntConfirmarCriterios');
 chkCriterios.type='checkbox';
 const lblConfirmarCriterios=el('label',undefined,undefined,'confirmation');
 lblConfirmarCriterios.append(
  chkCriterios,
  document.createTextNode(' Confirmo emplear estos criterios numéricos de calibración para el cálculo en borrador; entiendo que no son normativos ni equivalen a revisión o aprobación de ingeniería.')
 );

 const btnPreparar=el('button','Preparar lectura local sin envío','cntPreparar');
 btnPreparar.type='submit';

 form.append(rowProv,lblTokens,inpTokens,cuotaInfo,detailsCriterios,lblConfirmarCriterios,btnPreparar);

 // Bloque 3: Autorización de 1 envío, progreso claro por etapas e historial/recuperación
 const envioBox=el('fieldset',undefined,'cntEnvioBox');
 envioBox.append(el('legend','2. Envío único autorizado y avance por etapas'));

 const chkEnvio=el('input',undefined,'cntConfirmarEnvio');
 chkEnvio.type='checkbox';
 chkEnvio.disabled=true;
 const lblEnvio=el('label',undefined,undefined,'confirmation');
 lblEnvio.append(
  chkEnvio,
  document.createTextNode(' Autorizo realizar una única solicitud de lectura al proveedor seleccionado. Puede consumir cuota; si falla no se reintentará automáticamente ni se cambiará de proveedor.')
 );

 const btnEjecutar=el('button','Ejecutar recorrido de contornos (1 envío)','cntEjecutar','primary');
 btnEjecutar.type='button';
 btnEjecutar.disabled=true;

 const estadoGeneral=el('p','Selecciona un expediente y abre una geometría para iniciar.','cntEstado');
 estadoGeneral.setAttribute('role','status');
 estadoGeneral.setAttribute('aria-live','polite');

 const etapasLista=el('ol',undefined,'cntEtapas');
 etapasLista.setAttribute('aria-label','Etapas del recorrido de contornos');
 const DEFINICION_ETAPAS=[
  ['leyendo','Leyendo planos y correspondencias'],
  ['calibrando','Calibrando dibujos con referencias locales'],
  ['comprobando','Comprobando geometría y topología'],
  ['guardando','Guardando geometría y preparación en borrador']
 ];
 const nodosEtapas=new Map();
 for(const [clave,titulo] of DEFINICION_ETAPAS){
  const li=el('li');
  li.dataset.etapa=clave;
  const strong=el('strong',titulo);
  const sep=document.createTextNode(' · ');
  const span=el('span','Pendiente');
  li.append(strong,sep,span);
  etapasLista.append(li);
  nodosEtapas.set(clave,{li,span});
 }

 const avisoDisponible=el('p',undefined,'cntAvisoDisponible','hint');
 avisoDisponible.hidden=true;
 const btnAbrirDerivado=el('button','Abrir versión derivada en borrador','cntAbrirDerivado');
 btnAbrirDerivado.type='button';
 btnAbrirDerivado.hidden=true;

 envioBox.append(lblEnvio,btnEjecutar,estadoGeneral,etapasLista,avisoDisponible,btnAbrirDerivado);

 // Historial y reevaluación sin API
 const historialBar=el('div',undefined,'cntHistorialBar','versionbar');
 const histCol=el('div');
 const lblHist=el('label','Recorridos de contornos conservados');
 lblHist.htmlFor='cntHistorial';
 const selHist=el('select',undefined,'cntHistorial');
 setSelectOptions(selHist,[['','Sin recorridos conservados']]);
 selHist.disabled=true;
 histCol.append(lblHist,selHist);
 const btnConsultar=el('button','Consultar recorrido conservado','cntConsultar');
 btnConsultar.type='button';
 btnConsultar.disabled=true;
 const btnRecuperar=el('button','Reevaluar respuesta conservada sin proveedor','cntRecuperar');
 btnRecuperar.type='button';
 btnRecuperar.disabled=true;
 historialBar.append(histCol,btnConsultar,btnRecuperar);

 // Bloque 4: Resumen y observaciones agrupadas (elemento / dibujo / causa)
 const resultadoBox=el('section',undefined,'cntResultadoBox');
 resultadoBox.setAttribute('aria-label','Resumen y observaciones del recorrido');
 const resumenLinea=el('p',undefined,'cntResumen');
 resumenLinea.hidden=true;
 const observacionesContenedor=el('div',undefined,'cntObservaciones');
 observacionesContenedor.setAttribute('aria-label','Observaciones agrupadas por categoría');
 resultadoBox.append(resumenLinea,observacionesContenedor);

 // Bloque 5: Puente de revisión hacia el panel de calibración manual (Hito 4)
 const puenteBox=el('fieldset',undefined,'cntPuenteBox');
 puenteBox.append(el('legend','3. Revisar o corregir ubicaciones en el panel de calibración manual'));
 const puenteAvisoFijo=el(
  'p',
  'Importante: enviar un dibujo al panel de calibración manual permite inspeccionar o ajustar sus puntos como borrador local independiente. Ese cálculo local no sustituye ni actualiza automáticamente este recorrido de contornos, y por sí solo no acredita controles independientes ni aprobación de ingeniería.',
  'cntPuenteAviso',
  'hint'
 );
 const puenteBar=el('div',undefined,undefined,'versionbar');
 const dibCol=el('div');
 const lblDibujo=el('label','Dibujo propuesto conservado en la lectura');
 lblDibujo.htmlFor='cntDibujoSelect';
 const selDibujo=el('select',undefined,'cntDibujoSelect');
 setSelectOptions(selDibujo,[['','Sin dibujos propuestos cargados']]);
 selDibujo.disabled=true;
 dibCol.append(lblDibujo,selDibujo);
 const btnEnviarDibujo=el('button','Cargar dibujo en calibración manual','cntEnviarDibujo');
 btnEnviarDibujo.type='button';
 btnEnviarDibujo.disabled=true;
 puenteBar.append(dibCol,btnEnviarDibujo);
 const puenteEstado=el('p','Consulta o completa un recorrido con dibujos propuestos para habilitar su revisión individual.','cntPuenteEstado','hint');
 puenteEstado.setAttribute('role','status');
 puenteBox.append(puenteAvisoFijo,puenteBar,puenteEstado);

 panel.append(heading,intro,vinculoBox,form,envioBox,historialBar,resultadoBox,puenteBox);

 const anchorNode=
  container.querySelector('[aria-label="Vista interactiva del modelo 3D"]')||
  container.querySelector('[aria-label="Reconstrucción automática del proyecto"]')||
  container.querySelector('.stage-guide');
 if(anchorNode&&typeof anchorNode.after==='function')anchorNode.after(panel);
 else container.append(panel);

 // --- Estado interno y control de concurrencia ---
 let caseEpoch=0;
 let geoEpoch=0;
 let preconfigEpoch=0;
 let formEpoch=0;
 let jobSeq=0;
 let pollSeq=0;
 let preconfigLookupSeq=0;
 let historySeq=0;
 let quotaSeq=0;

 let activePreconfig=null;
 let availableBranches=[];
 let crearRequerido=false;
 let unlinkedReason='';
 let panelPreconfigDirty=false;
 const dirtyPreconfigIds=new Set();

 let limitsQuota=null;
 let currentJob=null;
 let requestKey=null;
 let busy=false;
 let busyPhase='';
 let running=false;
 let pollTimer=null;
 let pendingDerived=null;
 const publishedChildren=new Set();

 function getDocsObj(){
  return typeof docs!=='undefined'&&docs&&docs.caso&&docs.expediente_sha256?docs:null;
 }

 function currentIdentity(){
  const d=getDocsObj();
  return d?{caso:d.caso,expediente_sha256:d.expediente_sha256}:null;
 }

 function sameCase(id){
  const cur=currentIdentity();
  return Boolean(cur&&id&&cur.caso===id.caso&&cur.expediente_sha256===id.expediente_sha256);
 }

 function getEl(id){
  return typeof $==='function'?$(id):document.getElementById(id);
 }

 function currentGeoInfo(){
  const sel=getEl('geoVersion');
  const ver=sel?.value||'';
  if(!ver||typeof geoRecord==='undefined'||!geoRecord||geoRecord.comprobacion?.correcta!==true)return null;
  const comp=geoRecord.comprobacion||{};
  return {
   version_id:ver,
   huella_contenido:geoRecord.huella||comp.huella_contenido||'',
   sha256_geometria:geoRecord.sha256_geometria||comp.sha256_geometria||'',
   unidad_longitud:geoRecord.datos?.unidad_longitud||''
  };
 }

 function geoSig(g=currentGeoInfo()){
  return g?`${g.version_id}|${g.huella_contenido}|${g.sha256_geometria}`:'';
 }

 function isGeoDirty(){
  const gJson=getEl('geoJson');
  if(!gJson||typeof geoRecord==='undefined'||!geoRecord?.datos)return false;
  if(typeof gJson.value!=='string'||!gJson.value)return false;
  return gJson.value!==JSON.stringify(geoRecord.datos,null,2);
 }

 function isPreconfigDirty(){
  if(panelPreconfigDirty)return true;
  if(activePreconfig&&dirtyPreconfigIds.has(activePreconfig.id))return true;
  return false;
 }

 function isAnyDirty(){
  return isPreconfigDirty()||isGeoDirty();
 }

 function preconfigMatchesGeo(prep,geo=currentGeoInfo()){
  if(!prep||!geo||!prep.id||!prep.sha256_configuracion)return false;
  if(!sameCase({caso:prep.caso,expediente_sha256:prep.expediente_sha256}))return false;
  const orig=prep.datos?.geometria_origen||prep.registro?.geometria_origen;
  if(!orig||orig.version_id!==geo.version_id)return false;
  if(geo.huella_contenido&&orig.huella_contenido&&orig.huella_contenido!==geo.huella_contenido)return false;
  if(geo.sha256_geometria&&orig.sha256_geometria&&orig.sha256_geometria!==geo.sha256_geometria)return false;
  return true;
 }

 function preconfigSig(p=activePreconfig){
  return p&&preconfigMatchesGeo(p)?`${p.id}|${p.sha256_configuracion}`:'';
 }

 function captureSnap(){
  const id=currentIdentity();
  return {
   id:id?{...id}:null,
   caseEpoch,
   geoEpoch,
   geoSig:geoSig(),
   preconfigEpoch,
   preconfigSig:preconfigSig(),
   formEpoch,
   jobSeq,
   pollSeq
  };
 }

 function parseCriterios(){
  const result={};
  for(const [key,,labelText] of ESPECIFICACION_CRITERIOS){
   const raw=String(inputsCriterios[key].value??'').trim();
   if(!NUM_RE.test(raw))return {ok:false,error:`Revisa "${labelText}": escribe un número positivo válido.`};
   const val=Number(raw);
   if(!Number.isFinite(val)||val<=0)return {ok:false,error:`"${labelText}" debe ser mayor que cero.`};
   result[key]=val;
  }
  if(result.condicion_max<1)return {ok:false,error:'El número de condición máximo debe ser al menos 1.'};
  if(result.localizacion_uv>1)return {ok:false,error:'La sensibilidad de ubicación en el dibujo no puede superar 1.'};
  if(result.escala_min_m_por_uv>=result.escala_max_m_por_uv){
   return {ok:false,error:'La escala mínima debe ser estrictamente menor que la escala máxima.'};
  }
  return {ok:true,criterios:result};
 }

 function parseMaxTokens(){
  const raw=String(inpTokens.value??'').trim();
  if(!INT_RE.test(raw))return {ok:false,error:'El límite máximo de respuesta debe ser un número entero entre 256 y 65536.'};
  const val=Number(raw);
  if(!Number.isInteger(val)||val<256||val>65536){
   return {ok:false,error:'El límite máximo de respuesta debe situarse entre 256 y 65536.'};
  }
  return {ok:true,valor:val};
 }

 function cancelInFlightForContextChange(){
  clearTimeout(pollTimer);
  pollTimer=null;
  pollSeq++;
  jobSeq++;
  busy=false;
  busyPhase='';
  running=false;
 }

 function invalidatePreparedJob(reason){
  requestKey=null;
  chkEnvio.checked=false;
  if(currentJob&&currentJob.estado==='preparado'){
   currentJob=null;
   if(reason)estadoGeneral.textContent=reason;
   actualizarIndicadorEtapas(null);
  }
 }

 // --- Indicador visual de etapas ---
 function fijarEtapas(estadosPorClave){
  for(const [clave] of DEFINICION_ETAPAS){
   const nodo=nodosEtapas.get(clave);
   const txt=estadosPorClave[clave]||'Pendiente';
   nodo.span.textContent=txt;
   nodo.li.dataset.estadoEtapa=txt.toLowerCase();
  }
 }

 function actualizarIndicadorEtapas(job){
  if(busyPhase==='preparando'){
   fijarEtapas({
    leyendo:'Preparando paquete local (sin envío)',
    calibrando:'Pendiente',
    comprobando:'Pendiente',
    guardando:'Pendiente'
   });
   return;
  }
  if(busyPhase==='enviando'){
   fijarEtapas({
    leyendo:'En curso (enviando solicitud única)',
    calibrando:'Pendiente',
    comprobando:'Pendiente',
    guardando:'Pendiente'
   });
   return;
  }
  if(busyPhase==='recuperando'){
   fijarEtapas({
    leyendo:'Respuesta conservada (sin nueva llamada)',
    calibrando:'En curso (recalculando localmente)',
    comprobando:'En curso',
    guardando:'Pendiente'
   });
   return;
  }
  if(!job){
   fijarEtapas({});
   return;
  }
  const st=job.estado;
  const paso=String(job.paso||'').toLowerCase();
  if(st==='preparado'){
   fijarEtapas({
    leyendo:'Listo localmente (esperando autorización de envío)',
    calibrando:'Pendiente',
    comprobando:'Pendiente',
    guardando:'Pendiente'
   });
   return;
  }
  if(st==='en_ejecucion'){
   if(paso.includes('conservando')||paso.includes('registrando')||paso.includes('guardando')){
    fijarEtapas({
     leyendo:'Completada',
     calibrando:'Completada',
     comprobando:'Completada',
     guardando:'En curso (guardando borrador)'
    });
   }else if(paso.includes('comprobando conexiones')||paso.includes('resolviendo')||paso.includes('topología')||paso.includes('incorpor')){
    fijarEtapas({
     leyendo:'Completada',
     calibrando:'Completada',
     comprobando:'En curso (comprobando geometría)',
     guardando:'Pendiente'
    });
   }else if(paso.includes('calibrando')){
    fijarEtapas({
     leyendo:'Completada',
     calibrando:'En curso (calibrando dibujos)',
     comprobando:'Pendiente',
     guardando:'Pendiente'
    });
   }else{
    fijarEtapas({
     leyendo:'En curso (leyendo planos)',
     calibrando:'Pendiente',
     comprobando:'Pendiente',
     guardando:'Pendiente'
    });
   }
   return;
  }
  if(st==='contornos_borrador'){
   const publicoHijo=Boolean(job.resultado?.geometria_version&&job.resultado?.configuracion_preparacion);
   fijarEtapas({
    leyendo:'Completada',
    calibrando:'Completada',
    comprobando:'Completada',
    guardando:publicoHijo
     ?'Completada (nueva versión en borrador conservada)'
     :'Sin publicación de nueva geometría (revisa las observaciones; se conservó la base)'
   });
   return;
  }
  if(st==='fallido_no_reintentar'||st==='incierto'){
   fijarEtapas({
    leyendo:'Detenida sin reintento automático',
    calibrando:'No aplicada',
    comprobando:'No aplicada',
    guardando:'Sin cambios publicados'
   });
   return;
  }
  fijarEtapas({});
 }

 // --- Vínculo de preparación y selector de ramas ---
 function renderVinculo(){
  const id=currentIdentity();
  const geo=currentGeoInfo();
  if(!id){
   ramasWrap.hidden=true;
   vinculoEstado.textContent='Selecciona un expediente para consultar sus geometrías y preparaciones.';
   return;
  }
  if(!geo){
   ramasWrap.hidden=true;
   vinculoEstado.textContent='Abre una versión geométrica comprobada en esta etapa para vincular su preparación de ingeniería.';
   return;
  }
  if(isGeoDirty()){
   ramasWrap.hidden=availableBranches.length<=1;
   vinculoEstado.textContent='La geometría abierta tiene cambios sin guardar en pantalla. Guarda o descarta esos cambios antes de preparar o ejecutar contornos.';
   return;
  }
  if(isPreconfigDirty()){
   ramasWrap.hidden=availableBranches.length<=1;
   vinculoEstado.textContent='La preparación de ingeniería tiene ediciones sin guardar. Guarda el borrador de preparación o vuelve a abrir una versión conservada para continuar.';
   return;
  }
  if(activePreconfig&&preconfigMatchesGeo(activePreconfig,geo)){
   ramasWrap.hidden=availableBranches.length<=1;
   vinculoEstado.textContent=`Preparación vinculada lista (${activePreconfig.id.slice(0,8)}…) para la geometría abierta (${geo.version_id.slice(0,8)}…).`;
   return;
  }
  if(availableBranches.length>1){
   ramasWrap.hidden=false;
   vinculoEstado.textContent=`Esta geometría cuenta con ${availableBranches.length} ramas de preparación conservadas. Elige explícitamente cuál emplear y pulsa «Usar preparación seleccionada».`;
   return;
  }
  ramasWrap.hidden=true;
  if(crearRequerido){
   vinculoEstado.textContent='Esta geometría aún no tiene una preparación de ingeniería conservada. Créala primero en el panel de preparación de ingeniería (etapa 4) y regresa aquí.';
   return;
  }
  if(unlinkedReason){
   vinculoEstado.textContent=unlinkedReason;
   return;
  }
  vinculoEstado.textContent='Consultando preparaciones conservadas para la geometría abierta…';
 }

 // --- Cuota ---
 function renderCuota(){
  const prov=selProv.value;
  const provNombre=prov==='gemini'?'Google Gemini':'OpenAI';
  const q=limitsQuota?.[prov];
  if(!q){
   cuotaInfo.textContent='La cuota autorizada se comparte con las demás lecturas asistidas del proyecto.';
   return;
  }
  if(q.configurada===false){
   cuotaInfo.textContent=`Sin cuota de envío configurada para ${provNombre}. La preparación local y la consulta de recorridos conservados siguen disponibles.`;
   return;
  }
  const disp=`${q.restantes} de ${q.limite} solicitudes autorizadas disponibles para ${provNombre} (${q.usadas} utilizadas).`;
  const cred=q.credencial_configurada
   ?'Credencial configurada en el entorno local.'
   :'Falta configurar la credencial en el entorno local.';
  const agotada=q.restantes===0?' Límite agotado: el envío está bloqueado y no se cambiará de proveedor automáticamente.':'';
  cuotaInfo.textContent=`${disp} ${cred}${agotada}`;
 }

 // --- Agrupación y deduplicación de observaciones (elemento / dibujo / causa) ---
 function construirMapaEntidades(lecturaDatos){
  const porId=new Map();
  if(!lecturaDatos)return porId;
  const nombresTipo={
   muro:'Muro',
   losa:'Losa',
   superficie_generica:'Superficie',
   columna:'Columna',
   viga:'Viga'
  };
  for(const elem of lecturaDatos.elementos||[]){
   if(elem?.id){
    porId.set(elem.id,{
     etiqueta:`${nombresTipo[elem.tipo]||'Elemento'} ${elem.id}`,
     dibujos:Array.isArray(elem.dibujos)?elem.dibujos:[]
    });
   }
  }
  for(const ab of lecturaDatos.aberturas||[]){
   if(ab?.id){
    porId.set(ab.id,{
     etiqueta:`Abertura ${ab.id}`+(ab.host?` (en ${ab.host})`:''),
     dibujos:Array.isArray(ab.dibujos)?ab.dibujos:[]
    });
   }
  }
  for(const dib of lecturaDatos.dibujos||[]){
   if(dib?.id){
    for(const pt of dib.puntos||[]){
     if(pt?.id&&!porId.has(pt.id)){
      porId.set(pt.id,{etiqueta:`Punto propuesto ${pt.id}`,dibujos:[dib.id]});
     }
    }
   }
  }
  return porId;
 }

 function parsearAvisoTexto(texto){
  const limpio=textoLimpio(texto);
  const mDib=/^Dibujo\s+([A-Za-z0-9_.-]+)\s*:\s*(.+)$/i.exec(limpio);
  if(mDib)return {grupo:'calibracion',elemento:'Ajuste del dibujo',dibujo:mDib[1],causa:mDib[2]};
  const mRef=/^Referencia\s+([A-Za-z0-9_.-]+)\s*:\s*(.+)$/i.exec(limpio);
  if(mRef)return {grupo:'calibracion',elemento:`Referencia ${mRef[1]}`,dibujo:'Según plano del dibujo',causa:mRef[2]};
  const mCol=/^Colisi[oó]n de punto propuesto\s*:\s*([A-Za-z0-9_.-]+)$/i.exec(limpio);
  if(mCol){
   return {
    grupo:'lectura',
    elemento:`Punto ${mCol[1]}`,
    dibujo:'Varios dibujos o base',
    causa:'El identificador propuesto coincide con otro punto ya existente o repetido.'
   };
  }
  return {grupo:'lectura',elemento:'Lectura general',dibujo:'General',causa:limpio};
 }

 function renderObservaciones(resultado){
  observacionesContenedor.replaceChildren();
  if(!resultado)return;

  const lectura=resultado.lectura||{};
  const datos=lectura.datos||{};
  const incorp=resultado.incorporacion||{};
  const mapaEntidades=construirMapaEntidades(datos);
  const dibujosIds=new Set((datos.dibujos||[]).map(d=>d.id).filter(Boolean));

  const grupos={
   calibracion:{titulo:'Calibración local por dibujo',items:[]},
   incorporacion:{titulo:'Comprobación geométrica e incorporación',items:[]},
   lectura:{titulo:'Advertencias de lectura en planos',items:[]},
   edificio:{titulo:'Datos faltantes y pendientes del edificio',items:[]}
  };

  const clavesVistas=new Set();
  const causasEspecificas=new Set();
  const dibujosConErrorDirecto=new Set();

  function agregarItem(claveGrupo,elemento,dibujo,causa,esEspecifica=true){
   const elemTxt=String(elemento||'Edificio / general').trim();
   const dibTxt=String(dibujo||'General').trim();
   const causaTxt=textoLimpio(String(causa||''));
   if(!causaTxt)return;
   const normCausa=causaTxt.toLowerCase();
   const dedupKey=`${claveGrupo}|${elemTxt.toLowerCase()}|${dibTxt.toLowerCase()}|${normCausa}`;
   if(clavesVistas.has(dedupKey))return;
   clavesVistas.add(dedupKey);
   if(esEspecifica)causasEspecificas.add(normCausa);
   grupos[claveGrupo].items.push({elemento:elemTxt,dibujo:dibTxt,causa:causaTxt});
  }

  // 1. Errores directos de calibración por dibujo
  for(const err of resultado.errores_digitizacion||[]){
   if(!err)continue;
   const dib=err.dibujo||'General';
   dibujosConErrorDirecto.add(dib);
   agregarItem('calibracion','Calibración del dibujo',dib,err.motivo||'No se pudo calibrar el dibujo con los criterios indicados.');
  }

  // 2. Conflictos de incorporación
  for(const conf of incorp.conflictos||[]){
   if(!conf)continue;
   if(typeof conf==='string'){
    agregarItem('incorporacion','Incorporación geométrica','General',conf);
    continue;
   }
   const rawMotivo=conf.motivo||'Conflicto geométrico detectado.';
   if(conf.motivo)causasEspecificas.add(textoLimpio(conf.motivo).toLowerCase());
   if(conf.tipo==='digitizacion_invalida'){
    agregarItem('calibracion','Registro de calibración',conf.id||'General',rawMotivo);
   }else if(conf.tipo==='geometria_propuesta_invalida'){
    const detalles=Array.isArray(conf.errores)&&conf.errores.length
     ?conf.errores.map(e=>e?.mensaje||e?.descripcion||e?.ruta).filter(Boolean).join('; ')
     :'';
    const texto=detalles?`${rawMotivo} (${detalles})`:rawMotivo;
    agregarItem('incorporacion','Validación del modelo geométrico','Conjunto propuesto',texto);
   }else{
    const info=conf.id?mapaEntidades.get(conf.id):null;
    const elemLabel=info?info.etiqueta:(conf.id?`Elemento ${conf.id}`:'Incorporación geométrica');
    const dibLabel=info?.dibujos?.length?info.dibujos.join(', '):(dibujosIds.has(conf.id)?conf.id:'General');
    agregarItem('incorporacion',elemLabel,dibLabel,rawMotivo);
   }
  }

  // 3. Pendientes de incorporación
  for(const pend of incorp.pendientes||[]){
   if(!pend)continue;
   if(typeof pend==='string'){
    agregarItem('incorporacion','Pendiente geométrico','General',pend);
    continue;
   }
   const rawMotivo=pend.motivo||'Elemento pendiente de métricas comprobadas.';
   if(pend.motivo)causasEspecificas.add(textoLimpio(pend.motivo).toLowerCase());
   if(pend.tipo==='digitizacion_ausente'&&pend.id&&dibujosConErrorDirecto.has(pend.id)){
    // Ya se mostró la causa exacta del fallo de calibración de este dibujo arriba; no duplicar como línea huérfana.
    continue;
   }
   if(pend.tipo==='digitizacion_ausente'){
    agregarItem('calibracion','Calibración pendiente',pend.id||'General',rawMotivo);
   }else if(pend.tipo==='sin_nuevos_contornos'){
    agregarItem('incorporacion','Conjunto leído','Todos los dibujos',rawMotivo);
   }else{
    const info=pend.id?mapaEntidades.get(pend.id):null;
    const elemLabel=info?info.etiqueta:(pend.id?`Entidad ${pend.id}`:'Contorno propuesto');
    const dibLabel=info?.dibujos?.length?info.dibujos.join(', '):'Sin dibujo calibrado';
    agregarItem('incorporacion',elemLabel,dibLabel,rawMotivo);
   }
  }

  // 4. Advertencias de lectura y calibración (evitando duplicados entre lectura e incorporación)
  const avisosUnicos=[...(lectura.advertencias||[]),...(incorp.advertencias||[])];
  for(const aviso of avisosUnicos){
   if(typeof aviso!=='string'||!aviso.trim())continue;
   causasEspecificas.add(textoLimpio(aviso).toLowerCase());
   const parsed=parsearAvisoTexto(aviso);
   agregarItem(parsed.grupo,parsed.elemento,parsed.dibujo,parsed.causa);
  }

  // 5. Faltantes del edificio (filtrando causas ya detalladas en los grupos anteriores)
  const fuentesFaltantes=[
   ...(datos.faltantes||[]),
   ...(lectura.faltantes||[]),
   ...(incorp.faltantes||[]),
   ...(resultado.faltantes||[])
  ];
  for(const item of fuentesFaltantes){
   if(!item)continue;
   let texto='';
   let elem='Edificio / general';
   let dib='General';
   if(typeof item==='string'){
    texto=item;
   }else if(typeof item==='object'){
    texto=item.descripcion||item.motivo||item.mensaje||'';
    if(item.elemento||item.id)elem=String(item.elemento||item.id);
    else if(item.ruta)elem=textoLimpio(String(item.ruta));
    if(item.dibujo)dib=String(item.dibujo);
   }
   const limpio=textoLimpio(texto);
   if(!limpio||causasEspecificas.has(limpio.toLowerCase()))continue;
   agregarItem('edificio',elem,dib,limpio,false);
  }

  let totalMostradas=0;
  for(const grupo of Object.values(grupos)){
   if(!grupo.items.length)continue;
   totalMostradas+=grupo.items.length;
   const sec=el('div',undefined,undefined,'obs-grupo');
   sec.append(el('h4',`${grupo.titulo} (${grupo.items.length})`));
   const ul=el('ul');
   for(const it of grupo.items){
    const li=el('li');
    const bElem=el('strong',`Elemento: ${it.elemento}`);
    const sep1=document.createTextNode(` · Dibujo: ${it.dibujo} · Causa: `);
    const spanCausa=el('span',it.causa);
    li.append(bElem,sep1,spanCausa);
    ul.append(li);
   }
   sec.append(ul);
   observacionesContenedor.append(sec);
  }

  if(!totalMostradas){
   observacionesContenedor.append(el('p','Sin observaciones adicionales registradas en este recorrido.',undefined,'hint'));
  }
 }

 // --- Puente hacia digitización manual (Hito 4) ---
 function originalGeoDeTrabajo(job=currentJob){
  return job?.resultado?.lectura?.contexto?.geometria||null;
 }

 function coincideConGeometriaOriginal(job=currentJob){
  const orig=originalGeoDeTrabajo(job);
  const cur=currentGeoInfo();
  if(!orig||!cur)return false;
  if(cur.version_id!==orig.version_id)return false;
  if(orig.huella_contenido&&cur.huella_contenido&&cur.huella_contenido!==orig.huella_contenido)return false;
  if(orig.sha256_geometria&&cur.sha256_geometria&&cur.sha256_geometria!==orig.sha256_geometria)return false;
  return true;
 }

 function poblarSelectorDibujos(job=currentJob){
  const dibujos=job?.resultado?.lectura?.datos?.dibujos||[];
  if(!dibujos.length){
   setSelectOptions(selDibujo,[['','Sin dibujos propuestos en este recorrido']]);
   return;
  }
  const prev=selDibujo.value;
  const opciones=dibujos.map(d=>{
   const planoTxt=d.plano?`${d.plano.eje_constante.toUpperCase()}=${d.plano.valor_constante} ${d.plano.unidad_longitud}`:d.plano_id;
   const estadoDig=job.resultado?.digitizaciones?.[d.id]?'calibrado':'con observaciones';
   return [d.id,`${d.id} · original ${d.archivo_id} pág. ${d.pagina} · plano ${planoTxt} (${estadoDig})`];
  });
  setSelectOptions(selDibujo,opciones,prev||dibujos[0].id);
 }

 function renderPuenteEstado(){
  const dibujos=currentJob?.resultado?.lectura?.datos?.dibujos||[];
  if(!dibujos.length){
   puenteEstado.textContent='Consulta o completa un recorrido con dibujos propuestos para habilitar su envío al panel de calibración manual.';
   return;
  }
  const orig=originalGeoDeTrabajo(currentJob);
  const cur=currentGeoInfo();
  if(!orig){
   puenteEstado.textContent='Este recorrido no incluye metadatos de geometría de origen.';
   return;
  }
  if(!coincideConGeometriaOriginal(currentJob)){
   const esDerivada=cur&&currentJob?.resultado?.geometria_version&&cur.version_id===currentJob.resultado.geometria_version;
   puenteEstado.textContent=esDerivada
    ?`Actualmente está abierta la geometría derivada (${cur.version_id.slice(0,8)}…). Las correspondencias del dibujo pertenecen a la geometría original (${orig.version_id.slice(0,8)}…): ábrela primero desde el selector «Versión geométrica» para revisar ubicaciones sin cambiarla por sorpresa.`
    :`Para revisar ubicaciones en el panel de calibración manual, abre primero la geometría original del cálculo (${orig.version_id.slice(0,8)}…) mediante el selector «Versión geométrica».`;
   return;
  }
  puenteEstado.textContent=`Geometría original activa (${orig.version_id.slice(0,8)}…). Puedes cargar el dibujo seleccionado en el panel de calibración manual para inspeccionar o corregir sus puntos.`;
 }

 // --- Publicación idempotente de hijos derivados respetando rama y edición (Hito 3) ---
 function clavePublicacion(job){
  const r=job?.resultado;
  if(!r?.geometria_version||!r?.configuracion_preparacion||!r?.sha256_configuracion)return '';
  return `${job.caso}|${job.expediente_sha256}|${job.id}|${r.geometria_version}|${r.configuracion_preparacion}|${r.sha256_configuracion}`;
 }

 function estaEnRamaOrigenLimpia(job){
  if(!job||!sameCase(job)||isAnyDirty())return false;
  if(!coincideConGeometriaOriginal(job))return false;
  if(!activePreconfig||!preconfigMatchesGeo(activePreconfig))return false;
  if(activePreconfig.id!==job.origen_preparacion)return false;
  if(activePreconfig.sha256_configuracion!==job.origen_sha256_configuracion)return false;
  return true;
 }

 function emitirEventosHijo(job,forzarManual=false){
  if(!job||!sameCase(job))return false;
  const r=job.resultado;
  if(!r?.geometria_version||!r?.configuracion_preparacion||!r?.sha256_configuracion)return false;
  const pubKey=clavePublicacion(job);
  if(!forzarManual&&publishedChildren.has(pubKey))return false;
  if(isAnyDirty()){
   estadoGeneral.textContent='Guarda o descarta primero las ediciones pendientes antes de cambiar a la versión derivada.';
   return false;
  }
  publishedChildren.add(pubKey);
  pendingDerived=null;
  avisoDisponible.hidden=true;
  btnAbrirDerivado.hidden=true;

  window.dispatchEvent(new CustomEvent('d2m-proposed-frames',{
   detail:{
    geometria:r.geometria_version,
    frames:Array.isArray(r.frames_propuestos)?deepClone(r.frames_propuestos):[]
   }
  }));
  window.dispatchEvent(new CustomEvent('d2m-preconfig-created',{
   detail:{
    caso:job.caso,
    expediente_sha256:job.expediente_sha256,
    configuracion_preparacion:r.configuracion_preparacion,
    sha256_configuracion:r.sha256_configuracion,
    preparacion_origen:job.origen_preparacion
   }
  }));
  window.dispatchEvent(new CustomEvent('d2m-geometry-created',{
   detail:{
    caso:job.caso,
    expediente_sha256:job.expediente_sha256,
    geometria:r.geometria_version,
    estado:'borrador',
    aprobacion:null
   }
  }));
  return true;
 }

 function gestionarPublicacionHijo(job,permitirAutoNavegacion){
  const r=job?.resultado;
  if(!r?.geometria_version||!r?.configuracion_preparacion||!r?.sha256_configuracion){
   pendingDerived=null;
   avisoDisponible.hidden=true;
   btnAbrirDerivado.hidden=true;
   return;
  }
  const pubKey=clavePublicacion(job);
  if(publishedChildren.has(pubKey)){
   const cur=currentGeoInfo();
   if(cur&&cur.version_id===r.geometria_version){
    pendingDerived=null;
    avisoDisponible.hidden=true;
    btnAbrirDerivado.hidden=true;
   }else{
    pendingDerived=job;
    avisoDisponible.textContent=`Este recorrido generó la geometría en borrador ${r.geometria_version.slice(0,8)}… y la preparación ${r.configuracion_preparacion.slice(0,8)}…. Mantuvimos tu selección actual sin cambios.`;
    avisoDisponible.hidden=false;
    btnAbrirDerivado.hidden=false;
   }
   return;
  }
  if(permitirAutoNavegacion&&estaEnRamaOrigenLimpia(job)){
   emitirEventosHijo(job,false);
   return;
  }
  pendingDerived=job;
  const razon=isAnyDirty()
   ?'Tienes ediciones sin guardar; no se cambió de versión ni se borraron tus datos.'
   :'Se conservó tu selección actual de geometría y preparación sin cambiar de rama.';
  avisoDisponible.textContent=`Nuevo resultado derivado disponible en borrador (geometría ${r.geometria_version.slice(0,8)}… · preparación ${r.configuracion_preparacion.slice(0,8)}…). ${razon}`;
  avisoDisponible.hidden=false;
  btnAbrirDerivado.hidden=false;
 }

 // --- Renderizado principal de un trabajo ---
 function renderTrabajo(job,{permitirAutoNavegacion=false}={}){
  if(!job||!sameCase(job))return;
  currentJob=deepClone(job);
  running=job.estado==='en_ejecucion';

  let msgPaso=textoLimpio(job.paso||'Estado del recorrido actualizado.');
  if(job.estado==='fallido_no_reintentar'){
   msgPaso=`Ejecución detenida sin reintento automático: ${msgPaso}`;
  }
  if(job.simulado){
   msgPaso+=' · PRUEBA SINTÉTICA: no acredita lectura real de planos.';
  }
  estadoGeneral.textContent=msgPaso;
  actualizarIndicadorEtapas(currentJob);

  const res=currentJob.resultado;
  if(res?.lectura?.datos){
   const d=res.lectura.datos;
   const inc=res.incorporacion;
   const nDib=d.dibujos?.length||0;
   const nElem=d.elementos?.length||0;
   const nAb=d.aberturas?.length||0;
   if(inc){
    const ag=inc.agregados||{};
    const estadoInc=inc.aplicado
     ?`Incorporación aplicada en borrador: +${ag.vertices?.length||0} vértices, +${ag.superficies?.length||0} superficies, +${ag.aberturas?.length||0} aberturas y +${ag.frames?.length||0} barras propuestas.`
     :'Incorporación retenida: la geometría base se mantuvo intacta hasta resolver las observaciones indicadas.';
    resumenLinea.textContent=`Lectura: ${nDib} dibujo(s), ${nElem} contorno(s) y ${nAb} abertura(s). ${estadoInc} No aprueba ingeniería ni habilita ETABS.`;
   }else{
    resumenLinea.textContent=`Lectura conservada: ${nDib} dibujo(s), ${nElem} contorno(s) y ${nAb} abertura(s). Sin incorporación geométrica aplicada.`;
   }
   resumenLinea.hidden=false;
   renderObservaciones(res);
  }else{
   resumenLinea.textContent='';
   resumenLinea.hidden=true;
   observacionesContenedor.replaceChildren();
  }

  poblarSelectorDibujos(currentJob);
  renderPuenteEstado();
  gestionarPublicacionHijo(currentJob,permitirAutoNavegacion);
  if(selHist.options.length&&Array.from(selHist.options).some(o=>o.value===currentJob.id)){
   selHist.value=currentJob.id;
  }
  updateControls();
 }

 // --- Habilitación de controles ---
 function updateControls(){
  const id=currentIdentity();
  const geo=currentGeoInfo();
  const preconfigOk=Boolean(activePreconfig&&preconfigMatchesGeo(activePreconfig,geo));
  const dirty=isAnyDirty();
  const critOk=parseCriterios().ok;
  const tokOk=parseMaxTokens().ok;
  const modOk=Boolean(inpMod.value.trim());

  const bloqueadoRed=busy;
  selProv.disabled=bloqueadoRed||!id;
  inpMod.disabled=bloqueadoRed||!id;
  inpTokens.disabled=bloqueadoRed||!id;
  for(const inp of Object.values(inputsCriterios))inp.disabled=bloqueadoRed||!id;
  btnResetCriterios.disabled=bloqueadoRed||!id;
  chkCriterios.disabled=bloqueadoRed||!id;

  ramasSelect.disabled=bloqueadoRed||!id||!geo||availableBranches.length<=1;
  ramasAbrirBtn.disabled=bloqueadoRed||!id||!geo||dirty||!ramasSelect.value;

  const bloqueadoOp=busy||running;
  btnPreparar.disabled=bloqueadoOp||!id||!geo||!preconfigOk||dirty||!critOk||!tokOk||!modOk||!chkCriterios.checked;

  const prepVigente=Boolean(
   currentJob&&
   currentJob.estado==='preparado'&&
   preconfigOk&&
   !dirty&&
   currentJob.origen_preparacion===activePreconfig.id&&
   currentJob.origen_sha256_configuracion===activePreconfig.sha256_configuracion
  );
  const cuotaRestante=limitsQuota?.[selProv.value]?.restantes;
  const cuotaConfigurada=limitsQuota?.[selProv.value]?.configurada;
  const sinCuota=cuotaRestante===0||cuotaConfigurada===false;

  chkEnvio.disabled=bloqueadoOp||!prepVigente||sinCuota;
  if(!prepVigente||sinCuota)chkEnvio.checked=false;
  btnEjecutar.disabled=bloqueadoOp||!prepVigente||!chkEnvio.checked||sinCuota;

  selHist.disabled=busy||!id||selHist.options.length<=1;
  btnConsultar.disabled=busy||!id||!selHist.value;

  const puedeRecuperar=Boolean(
   id&&
   !bloqueadoOp&&
   currentJob&&
   currentJob.tiene_respuesta_conservada===true&&
   currentJob.estado!=='en_ejecucion'
  );
  btnRecuperar.disabled=!puedeRecuperar;

  btnAbrirDerivado.disabled=bloqueadoOp||dirty||!pendingDerived;

  const dibujos=currentJob?.resultado?.lectura?.datos?.dibujos||[];
  selDibujo.disabled=bloqueadoOp||!dibujos.length;
  btnEnviarDibujo.disabled=bloqueadoOp||!dibujos.length||!selDibujo.value;
  btnEnviarDibujo.setAttribute('aria-disabled',(!coincideConGeometriaOriginal(currentJob)||btnEnviarDibujo.disabled)?'true':'false');

  renderVinculo();
  renderCuota();
  renderPuenteEstado();
 }

 // --- Consultas auxiliares de cuota, historial y preparaciones ---
 async function refrescarCuota(snap){
  const ticket=++quotaSeq;
  try{
   const res=await api('/api/reconstruccion/cuota');
   const val=await res.json();
   if(ticket!==quotaSeq||snap.caseEpoch!==caseEpoch||!sameCase(snap.id))return;
   limitsQuota=val;
   updateControls();
  }catch(err){
   if(ticket===quotaSeq&&snap.caseEpoch===caseEpoch&&sameCase(snap.id)){
    cuotaInfo.textContent=textoLimpio(err.message||'No se pudo consultar la cuota local.');
   }
  }
 }

 async function cargarHistorial(snap,seleccionPreferida){
  if(!snap.id)return;
  const ticket=++historySeq;
  try{
   const res=await api('/api/contornos/historial?'+new URLSearchParams(snap.id));
   const val=await res.json();
   if(ticket!==historySeq||snap.caseEpoch!==caseEpoch||!sameCase(snap.id))return;
   const trabajos=Array.isArray(val?.trabajos)?val.trabajos:(Array.isArray(val)?val:[]);
   const items=[['','Selecciona un recorrido'],...trabajos.map((t,idx)=>[t,`Recorrido ${idx+1} · ${String(t).slice(0,8)}`])];
   setSelectOptions(selHist,items,seleccionPreferida||currentJob?.id||selHist.value);
   updateControls();
  }catch(err){
   if(ticket===historySeq&&snap.caseEpoch===caseEpoch&&sameCase(snap.id)){
    estadoGeneral.textContent=textoLimpio(err.message||'No se pudo consultar el historial de contornos.');
   }
  }
 }

 async function cargarPreparacionPorVersion(versionId,snap){
  if(!snap.id||!HEX32_RE.test(versionId))return;
  const res=await api('/api/configuracion/preparacion?'+new URLSearchParams({...snap.id,version:versionId}));
  const record=await res.json();
  if(
   snap.caseEpoch!==caseEpoch||
   snap.geoEpoch!==geoEpoch||
   geoSig()!==snap.geoSig||
   !sameCase(snap.id)
  )return;
  if(!preconfigMatchesGeo(record)){
   activePreconfig=null;
   unlinkedReason='La preparación consultada pertenece a otra geometría o perdió vigencia.';
   updateControls();
   return;
  }
  adoptarPreparacionValida(record);
 }

 function adoptarPreparacionValida(record,desdeEvento=false){
  const prevSig=preconfigSig();
  activePreconfig=deepClone(record);
  if(desdeEvento){
   panelPreconfigDirty=false;
   dirtyPreconfigIds.clear();
  }
  unlinkedReason='';
  crearRequerido=false;
  if(availableBranches.includes(record.id))ramasSelect.value=record.id;
  if(preconfigSig()!==prevSig){
   preconfigEpoch++;
   running=false;
   invalidatePreparedJob('Se actualizó la preparación de ingeniería vinculada; prepara nuevamente la lectura si deseas enviar.');
  }
  updateControls();
 }

 async function consultarPreparacionesDeGeometria(){
  const id=currentIdentity();
  const geo=currentGeoInfo();
  const myLookup=++preconfigLookupSeq;
  availableBranches=[];
  crearRequerido=false;
  if(!id||!geo){
   activePreconfig=null;
   updateControls();
   return;
  }
  const snap=captureSnap();
  updateControls();
  try{
   const res=await api('/api/configuracion/preparacion/para-geometria?'+new URLSearchParams({...id,geometria:geo.version_id}));
   const val=await res.json();
   if(
    myLookup!==preconfigLookupSeq||
    snap.caseEpoch!==caseEpoch||
    snap.geoEpoch!==geoEpoch||
    geoSig()!==snap.geoSig||
    !sameCase(id)
   )return;

   const versiones=Array.isArray(val?.versiones)?val.versiones:[];
   availableBranches=versiones;
   crearRequerido=Boolean(val?.crear)||versiones.length===0;

   // Si durante la consulta ya llegó por evento una preparación válida de esta misma geometría, respetarla.
   if(activePreconfig&&preconfigMatchesGeo(activePreconfig,geo)){
    if(versiones.length>1){
     setSelectOptions(
      ramasSelect,
      [['','Selecciona una preparación'],...versiones.map((v,i)=>[v,`Rama ${i+1} · ${v.slice(0,8)}`])],
      activePreconfig.id
     );
    }
    updateControls();
    return;
   }

   if(val?.reutilizable&&versiones.length===1){
    const snapLoad=captureSnap();
    await cargarPreparacionPorVersion(val.reutilizable,snapLoad);
    return;
   }
   if(versiones.length>1){
    activePreconfig=null;
    setSelectOptions(
     ramasSelect,
     [['','Selecciona una preparación'],...versiones.map((v,i)=>[v,`Rama ${i+1} · ${v.slice(0,8)}`])]
    );
    updateControls();
    return;
   }
   activePreconfig=null;
   updateControls();
  }catch(err){
   if(myLookup===preconfigLookupSeq&&snap.caseEpoch===caseEpoch&&snap.geoEpoch===geoEpoch&&sameCase(id)){
    unlinkedReason=textoLimpio(err.message||'No se pudieron consultar las preparaciones de esta geometría.');
    updateControls();
   }
  }
 }

 // --- Sondeo local de 2 segundos ---
 async function sondearEstado(snap,trabajoId,permitirAutoNavegacion){
  const myPoll=++pollSeq;
  clearTimeout(pollTimer);
  pollTimer=null;
  if(!snap.id||snap.caseEpoch!==caseEpoch||!sameCase(snap.id))return;
  try{
   const res=await api('/api/contornos/estado?'+new URLSearchParams({...snap.id,trabajo:trabajoId}));
   const val=await res.json();
   if(snap.caseEpoch!==caseEpoch||!sameCase(snap.id))return;

   const contextoCambio=
    snap.geoEpoch!==geoEpoch||
    geoSig()!==snap.geoSig||
    snap.preconfigEpoch!==preconfigEpoch||
    preconfigSig()!==snap.preconfigSig||
    snap.formEpoch!==formEpoch||
    isAnyDirty();

   if(contextoCambio){
    running=false;
    if(val?.estado==='contornos_borrador'&&val?.resultado?.geometria_version&&val?.resultado?.configuracion_preparacion){
     pendingDerived=deepClone(val);
     avisoDisponible.textContent=`Un recorrido anterior finalizó en borrador (geometría ${val.resultado.geometria_version.slice(0,8)}… · preparación ${val.resultado.configuracion_preparacion.slice(0,8)}…). Mantuvimos tu rama y cambios actuales sin alterar la selección.`;
     avisoDisponible.hidden=false;
     btnAbrirDerivado.hidden=false;
     cargarHistorial(captureSnap()).catch(()=>{});
    }
    updateControls();
    return;
   }

   if(myPoll!==pollSeq||snap.jobSeq!==jobSeq)return;

   const veniaEjecutando=running||val.estado==='en_ejecucion';
   renderTrabajo(val,{permitirAutoNavegacion:permitirAutoNavegacion||veniaEjecutando});
   if(val.estado==='en_ejecucion'){
    pollTimer=setTimeout(()=>{
     if(myPoll===pollSeq)sondearEstado(snap,trabajoId,true);
    },2000);
   }else{
    await refrescarCuota(snap);
   }
  }catch(err){
   if(myPoll===pollSeq&&snap.caseEpoch===caseEpoch&&sameCase(snap.id)&&snap.jobSeq===jobSeq){
    running=false;
    estadoGeneral.textContent=textoLimpio(err.message||'No se pudo consultar el estado del recorrido.');
    updateControls();
   }
  }
 }

 // --- Manejadores de eventos de usuario ---
 ramasAbrirBtn.addEventListener('click',async()=>{
  const id=currentIdentity();
  const ver=ramasSelect.value;
  if(!id||!ver||busy||running)return;
  const snap=captureSnap();
  const myOp=++jobSeq;
  busy=true;
  busyPhase='';
  vinculoEstado.textContent='Abriendo la rama de preparación seleccionada…';
  updateControls();
  try{
   await cargarPreparacionPorVersion(ver,snap);
  }catch(err){
   if(myOp===jobSeq&&snap.caseEpoch===caseEpoch&&snap.geoEpoch===geoEpoch&&sameCase(id)){
    unlinkedReason=textoLimpio(err.message||'No se pudo abrir la preparación seleccionada.');
   }
  }finally{
   if(myOp===jobSeq&&snap.caseEpoch===caseEpoch){
    busy=false;
    busyPhase='';
    updateControls();
   }
  }
 });

 selProv.addEventListener('change',()=>{
  const nuevo=selProv.value;
  const actual=inpMod.value.trim();
  if(!actual||actual===MODELO_PREDETERMINADO.openai||actual===MODELO_PREDETERMINADO.gemini){
   inpMod.value=MODELO_PREDETERMINADO[nuevo]||'gpt-6.1-sol';
  }
  formEpoch++;
  running=false;
  if(busy&&busyPhase==='preparando')cancelInFlightForContextChange();
  invalidatePreparedJob('Cambiaste el proveedor; vuelve a preparar la lectura localmente antes de autorizar un envío.');
  updateControls();
 });

 for(const ctrl of [inpMod,inpTokens]){
  ctrl.addEventListener('input',()=>{
   formEpoch++;
   running=false;
   if(busy&&busyPhase==='preparando')cancelInFlightForContextChange();
   invalidatePreparedJob('Se modificaron los parámetros de lectura; prepara nuevamente antes de enviar.');
   updateControls();
  });
 }

 for(const inp of Object.values(inputsCriterios)){
  const onEditCriterio=()=>{
   formEpoch++;
   running=false;
   chkCriterios.checked=false;
   if(busy&&busyPhase==='preparando')cancelInFlightForContextChange();
   invalidatePreparedJob('Se modificaron los criterios de calibración; confirma su uso y vuelve a preparar la lectura.');
   updateControls();
  };
  inp.addEventListener('input',onEditCriterio);
  inp.addEventListener('change',onEditCriterio);
 }

 btnResetCriterios.addEventListener('click',()=>{
  for(const [key,,,defVal] of ESPECIFICACION_CRITERIOS){
   inputsCriterios[key].value=defVal;
  }
  formEpoch++;
  chkCriterios.checked=false;
  if(busy&&busyPhase==='preparando')cancelInFlightForContextChange();
  invalidatePreparedJob('Criterios restablecidos a sus valores predeterminados; confirma su uso antes de preparar.');
  updateControls();
 });

 chkCriterios.addEventListener('change',()=>{
  if(!chkCriterios.checked){
   formEpoch++;
   invalidatePreparedJob('Confirma el uso de los criterios numéricos de calibración para habilitar la preparación.');
  }
  updateControls();
 });

 chkEnvio.addEventListener('change',updateControls);

 form.addEventListener('submit',async e=>{
  e.preventDefault();
  const id=currentIdentity();
  const geo=currentGeoInfo();
  if(!id||!geo||busy||running||isAnyDirty())return;
  if(!activePreconfig||!preconfigMatchesGeo(activePreconfig,geo))return;
  if(!chkCriterios.checked){
   estadoGeneral.textContent='Confirma expresamente el uso de los criterios de calibración antes de preparar la lectura.';
   updateControls();
   return;
  }
  const parsedCrit=parseCriterios();
  if(!parsedCrit.ok){
   estadoGeneral.textContent=parsedCrit.error;
   updateControls();
   return;
  }
  const parsedTok=parseMaxTokens();
  if(!parsedTok.ok){
   estadoGeneral.textContent=parsedTok.error;
   updateControls();
   return;
  }
  const modelo=inpMod.value.trim();
  if(!modelo){
   estadoGeneral.textContent='Indica el identificador del modelo antes de preparar.';
   updateControls();
   return;
  }

  const myOp=++jobSeq;
  clearTimeout(pollTimer);
  pollSeq++;
  const snap={...captureSnap(),jobSeq:myOp};
  busy=true;
  busyPhase='preparando';
  chkEnvio.checked=false;
  estadoGeneral.textContent='Preparando paquete local de planos y comprobando referencias geométricas (sin envío al proveedor)…';
  actualizarIndicadorEtapas(null);
  updateControls();

  try{
   const clave=requestKey||nuevoIdSolicitud();
   requestKey=clave;
   const body={
    caso:id.caso,
    expediente_sha256:id.expediente_sha256,
    proveedor:selProv.value,
    modelo,
    max_tokens:parsedTok.valor,
    clave_solicitud:clave,
    configuracion_preparacion:activePreconfig.id,
    sha256_configuracion:activePreconfig.sha256_configuracion,
    limites_digitizacion:parsedCrit.criterios
   };
   const res=await api('/api/contornos/preparar',body);
   const val=await res.json();
   if(
    myOp!==jobSeq||
    snap.caseEpoch!==caseEpoch||
    snap.geoEpoch!==geoEpoch||
    geoSig()!==snap.geoSig||
    snap.preconfigEpoch!==preconfigEpoch||
    preconfigSig()!==snap.preconfigSig||
    snap.formEpoch!==formEpoch||
    isAnyDirty()||
    !sameCase(id)
   )return;

   busy=false;
   busyPhase='';
   chkEnvio.checked=false;
   renderTrabajo(val,{permitirAutoNavegacion:false});
   await cargarHistorial(snap,val.id);if(typeof message==='function')message('Plan de lectura de contornos preparado: '+val.id,false);
  }catch(err){
   if(myOp===jobSeq&&snap.caseEpoch===caseEpoch&&sameCase(id)){
    requestKey=null;
    busy=false;
    busyPhase='';
    estadoGeneral.textContent=textoLimpio(err.message||'No se pudo preparar la lectura local.');
    actualizarIndicadorEtapas(currentJob);
    updateControls();
   }
  }finally{
   if(myOp===jobSeq&&busy){
    busy=false;
    busyPhase='';
    updateControls();
   }
  }
 });

 btnEjecutar.addEventListener('click',async()=>{
  const id=currentIdentity();
  const geo=currentGeoInfo();
  if(!id||!geo||busy||running||isAnyDirty())return;
  if(!currentJob||currentJob.estado!=='preparado'||!chkEnvio.checked)return;
  if(!activePreconfig||!preconfigMatchesGeo(activePreconfig,geo))return;
  if(
   currentJob.origen_preparacion!==activePreconfig.id||
   currentJob.origen_sha256_configuracion!==activePreconfig.sha256_configuracion
  )return;
  if(limitsQuota?.[selProv.value]?.restantes===0||limitsQuota?.[selProv.value]?.configurada===false){
   estadoGeneral.textContent='No quedan solicitudes autorizadas disponibles para este proveedor.';
   updateControls();
   return;
  }

  const trabajoId=currentJob.id;
  chkEnvio.checked=false;
  requestKey=null;
  const myOp=++jobSeq;
  const snap={...captureSnap(),jobSeq:myOp};
  busy=true;
  busyPhase='enviando';
  estadoGeneral.textContent='Enviando solicitud única autorizada al proveedor e iniciando lectura de contornos (sin reintentos automáticos)…';
  actualizarIndicadorEtapas(null);
  updateControls();

  try{
   const res=await api('/api/contornos/ejecutar',{
    caso:id.caso,
    expediente_sha256:id.expediente_sha256,
    trabajo:trabajoId,
    confirmacion_explicita:true
   });
   const val=await res.json();
   if(myOp!==jobSeq||snap.caseEpoch!==caseEpoch||!sameCase(id))return;
   busy=false;
   busyPhase='';
   running=val.estado==='en_ejecucion';
   estadoGeneral.textContent='Etapa actual: leyendo planos y correspondencias en el proveedor…';
   actualizarIndicadorEtapas(val);
   updateControls();
   await sondearEstado(snap,trabajoId,true);
  }catch(err){
   if(myOp===jobSeq&&snap.caseEpoch===caseEpoch&&sameCase(id)){
    busy=false;
    busyPhase='';
    running=false;
    if(currentJob&&currentJob.id===trabajoId){
     currentJob={...currentJob,estado:'fallido_no_reintentar',paso:err.message||'El envío no pudo completarse.'};
    }
    estadoGeneral.textContent=`Envío detenido sin reintento automático: ${textoLimpio(err.message||'Error durante el envío.')}`;
    actualizarIndicadorEtapas(currentJob);
    updateControls();
    await refrescarCuota(snap);
   }
  }
 });

 btnConsultar.addEventListener('click',async()=>{
  const id=currentIdentity();
  const trabajoId=selHist.value;
  if(!id||!trabajoId||busy)return;
  const myOp=++jobSeq;
  clearTimeout(pollTimer);
  pollSeq++;
  const snap={...captureSnap(),jobSeq:myOp};
  busy=true;
  busyPhase='';
  estadoGeneral.textContent='Consultando recorrido conservado localmente (sin envío al proveedor)…';
  updateControls();
  try{
   const res=await api('/api/contornos/estado?'+new URLSearchParams({...id,trabajo:trabajoId}));
   const val=await res.json();
   if(myOp!==jobSeq||snap.caseEpoch!==caseEpoch||!sameCase(id))return;
   busy=false;
   // Consultar el historial muestra el resultado sin cambiar la rama ni borrar ediciones.
   renderTrabajo(val,{permitirAutoNavegacion:false});
   if(val.estado==='en_ejecucion'){
    await sondearEstado(snap,trabajoId,true);
   }
  }catch(err){
   if(myOp===jobSeq&&snap.caseEpoch===caseEpoch&&sameCase(id)){
    busy=false;
    estadoGeneral.textContent=textoLimpio(err.message||'No se pudo abrir el recorrido seleccionado.');
    updateControls();
   }
  }
 });

 btnRecuperar.addEventListener('click',async()=>{
  const id=currentIdentity();
  if(!id||busy||running||!currentJob||!currentJob.tiene_respuesta_conservada||currentJob.estado==='en_ejecucion')return;
  const trabajoId=currentJob.id;
  const myOp=++jobSeq;
  const snap={...captureSnap(),jobSeq:myOp};
  busy=true;
  busyPhase='recuperando';
  estadoGeneral.textContent='Reevaluando localmente la respuesta conservada y calibrando dibujos (sin llamar al proveedor)…';
  actualizarIndicadorEtapas(null);
  updateControls();
  try{
   const res=await api('/api/contornos/recuperar',{
    caso:id.caso,
    expediente_sha256:id.expediente_sha256,
    trabajo:trabajoId
   });
   const val=await res.json();
   if(myOp!==jobSeq||snap.caseEpoch!==caseEpoch||!sameCase(id))return;
   busy=false;
   busyPhase='';
   const mismoContexto=
    snap.geoEpoch===geoEpoch&&
    geoSig()===snap.geoSig&&
    snap.preconfigEpoch===preconfigEpoch&&
    preconfigSig()===snap.preconfigSig&&
    !isAnyDirty();
   renderTrabajo(val,{permitirAutoNavegacion:mismoContexto});
   await cargarHistorial(snap,val.id);
  }catch(err){
   if(myOp===jobSeq&&snap.caseEpoch===caseEpoch&&sameCase(id)){
    busy=false;
    busyPhase='';
    estadoGeneral.textContent=textoLimpio(err.message||'No se pudo reevaluar la respuesta conservada.');
    actualizarIndicadorEtapas(currentJob);
    updateControls();
   }
  }
 });

 btnAbrirDerivado.addEventListener('click',()=>{
  if(!pendingDerived||busy||running||isAnyDirty())return;
  emitirEventosHijo(pendingDerived,true);
  updateControls();
 });

 ramasSelect.addEventListener('change',updateControls);
 selHist.addEventListener('change',updateControls);
 selDibujo.addEventListener('change',updateControls);

 btnEnviarDibujo.addEventListener('click',()=>{
  const id=currentIdentity();
  if(!id||busy||running||!currentJob?.resultado?.lectura?.datos?.dibujos)return;
  const origGeo=originalGeoDeTrabajo(currentJob);
  if(!origGeo)return;

  if(!coincideConGeometriaOriginal(currentJob)){
   const cur=currentGeoInfo();
   const notaActual=cur?`Actualmente está abierta la versión ${cur.version_id.slice(0,8)}…. `:'No está abierta la versión original. ';
   const msg=`${notaActual}Abre primero la versión geométrica original (${origGeo.version_id.slice(0,8)}…) desde el selector «Versión geométrica» para revisar este dibujo en calibración manual; no se cambia automáticamente.`;
   puenteEstado.textContent=msg;
   estadoGeneral.textContent=msg;
   return;
  }

  const dibujo=(currentJob.resultado.lectura.datos.dibujos||[]).find(d=>d.id===selDibujo.value);
  if(!dibujo||!dibujo.fuente||!dibujo.plano)return;

  const limpiarEvidencias=items=>(items||[]).map(item=>{
   const copia={};
   for(const [k,v] of Object.entries(item)){
    if(k!=='evidencias')copia[k]=deepClone(v);
   }
   return copia;
  });

  const criterios=currentJob.criterios_calculo
   ?deepClone(currentJob.criterios_calculo)
   :deepClone(CRITERIOS_PREDETERMINADOS);

  const fuenteLimpia={
   original_id:dibujo.fuente.original_id,
   pagina:dibujo.fuente.pagina,
   dibujo_id:dibujo.fuente.dibujo_id,
   bbox_pagina:[...dibujo.fuente.bbox_pagina]
  };
  if(dibujo.fuente.sha256)fuenteLimpia.sha256=dibujo.fuente.sha256;

  const planoLimpio={
   id:dibujo.plano.id,
   ejes:[...dibujo.plano.ejes],
   eje_constante:dibujo.plano.eje_constante,
   valor_constante:dibujo.plano.valor_constante,
   unidad_longitud:dibujo.plano.unidad_longitud
  };

  const detail={
   caso:id.caso,
   expediente_sha256:id.expediente_sha256,
   geometria:origGeo.version_id,
   huella_geometria:origGeo.huella_contenido,
   sha256_geometria:origGeo.sha256_geometria,
   referencia_origen:currentJob.id,
   propuesta_id:dibujo.id,
   fuente:fuenteLimpia,
   plano:planoLimpio,
   limites:criterios,
   anclas:limpiarEvidencias(dibujo.anclas),
   controles:limpiarEvidencias(dibujo.controles),
   puntos:limpiarEvidencias(dibujo.puntos)
  };

  window.dispatchEvent(new CustomEvent('d2m-digitizacion-propuesta',{detail}));
  puenteEstado.textContent=`Dibujo ${dibujo.id} cargado en el panel de calibración manual sobre la geometría original (${origGeo.version_id.slice(0,8)}…). Recuerda que cualquier cálculo allí es un borrador local independiente y no sustituye este recorrido automáticamente.`;
 });

 // --- Suscripción a eventos globales del espacio de trabajo ---
 window.addEventListener('d2m-preconfig-opened',event=>{
  const rec=event.detail;
  const id=currentIdentity();
  if(!id||!rec||rec.caso!==id.caso||rec.expediente_sha256!==id.expediente_sha256)return;
  panelPreconfigDirty=false;
  if(rec.id)dirtyPreconfigIds.delete(rec.id);

  const geo=currentGeoInfo();
  if(geo&&preconfigMatchesGeo(rec,geo)){
   preconfigLookupSeq++;
   if(busy&&busyPhase==='preparando')cancelInFlightForContextChange();
   adoptarPreparacionValida(rec,true);
   if(!currentJob){
    estadoGeneral.textContent='Preparación de ingeniería vinculada con la geometría abierta. Confirma los criterios para preparar una lectura o consulta un recorrido conservado.';
   }
  }else{
   panelPreconfigDirty=false;
   dirtyPreconfigIds.clear();
   if(activePreconfig){
    activePreconfig=null;
    preconfigEpoch++;
    running=false;
    if(busy&&busyPhase==='preparando')cancelInFlightForContextChange();
    invalidatePreparedJob('La preparación abierta en ingeniería corresponde a otra geometría; selecciona o abre una preparación de la geometría actual.');
   }
   unlinkedReason=geo
    ?'La preparación abierta recientemente pertenece a otra versión geométrica. Selecciona o abre una preparación correspondiente a la geometría abierta.'
    :'Abre una versión geométrica en esta etapa para vincular su preparación.';
   updateControls();
  }
 });

 window.addEventListener('d2m-preconfig-edited',event=>{
  const det=event.detail;
  const id=currentIdentity();
  if(det?.caso&&id&&det.caso!==id.caso)return;
  if(det?.sin_guardar===false)return;
  panelPreconfigDirty=true;
  if(det?.id)dirtyPreconfigIds.add(det.id);
  else if(activePreconfig?.id)dirtyPreconfigIds.add(activePreconfig.id);
  preconfigEpoch++;
  if(busy&&busyPhase==='preparando')cancelInFlightForContextChange();
  chkEnvio.checked=false;
  updateControls();
 });

 const onGeoJsonEdit=()=>{
  if(isGeoDirty()){
   if(busy&&busyPhase==='preparando')cancelInFlightForContextChange();
   chkEnvio.checked=false;
  }
  updateControls();
 };
 getEl('geoJson')?.addEventListener('input',onGeoJsonEdit);
 window.addEventListener('d2m-geometry-edit',onGeoJsonEdit);

 window.addEventListener('d2m-geometry-opened',()=>{
  geoEpoch++;
  cancelInFlightForContextChange();
  const geo=currentGeoInfo();
  if(!geo||!preconfigMatchesGeo(activePreconfig,geo)){
   activePreconfig=null;
   preconfigEpoch++;
   unlinkedReason='';
   invalidatePreparedJob('Cambiaste de versión geométrica; vincula su preparación y prepara nuevamente la lectura si deseas enviarla.');
   consultarPreparacionesDeGeometria();
  }else{
   // Refrescar posibles ramas adicionales sin invalidar la preparación ya vinculada.
   consultarPreparacionesDeGeometria();
  }
  updateControls();
 });

 window.addEventListener('d2m-case',()=>{
  caseEpoch++;
  geoEpoch++;
  preconfigEpoch++;
  formEpoch++;
  preconfigLookupSeq++;
  historySeq++;
  quotaSeq++;
  cancelInFlightForContextChange();

  activePreconfig=null;
  availableBranches=[];
  crearRequerido=false;
  unlinkedReason='';
  panelPreconfigDirty=false;
  dirtyPreconfigIds.clear();
  limitsQuota=null;
  currentJob=null;
  requestKey=null;
  pendingDerived=null;
  publishedChildren.clear();

  chkEnvio.checked=false;
  chkCriterios.checked=false;
  avisoDisponible.hidden=true;
  btnAbrirDerivado.hidden=true;
  resumenLinea.textContent='';
  resumenLinea.hidden=true;
  observacionesContenedor.replaceChildren();
  setSelectOptions(selHist,[['','Sin recorridos conservados']]);
  setSelectOptions(selDibujo,[['','Sin dibujos propuestos cargados']]);
  setSelectOptions(ramasSelect,[['','Selecciona una preparación']]);
  ramasWrap.hidden=true;
  actualizarIndicadorEtapas(null);

  const id=currentIdentity();
  estadoGeneral.textContent=id
   ?'Expediente abierto. Abre una versión geométrica comprobada para vincular su preparación o consulta un recorrido conservado.'
   :'Selecciona un expediente para iniciar.';
  updateControls();

  if(id){
   const snap=captureSnap();
   cargarHistorial(snap);
   refrescarCuota(snap);
   if(currentGeoInfo())consultarPreparacionesDeGeometria();
  }
 });

 // Inicialización si ya hubiera contexto cargado
 actualizarIndicadorEtapas(null);
 updateControls();
 if(currentIdentity()){
  const snap=captureSnap();
  cargarHistorial(snap);
  refrescarCuota(snap);
  if(currentGeoInfo())consultarPreparacionesDeGeometria();
 }
})();
