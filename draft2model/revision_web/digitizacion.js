'use strict';
(()=>{
 const target=window.D2MEtapas?.containers?.get('geometria');
 if(!target)return;

 const getDocs=()=>(typeof docs!=='undefined'&&docs)||window.docs||null;
 const getGeo=()=>(typeof geoRecord!=='undefined'&&geoRecord)||window.geoRecord||null;
 const getApi=()=>(typeof api==='function'?api:window.api);
 const notify=(txt,err=false)=>{if(typeof message==='function')message(txt,err);else if(typeof window.message==='function')window.message(txt,err);};
 const byId=id=>(typeof $==='function'?$(id):document.getElementById?.(id))||null;

 const FORBIDDEN_METRIC_KEYS=new Set(['puntos_resueltos','coordenadas','coordenadas_m','xy','xy_m','xyz','x','y','z','metros']);
 const ID_RE=/^[A-Za-z0-9_.:-]{1,128}$/;

 const el=(tag,text,id)=>{
  const n=document.createElement(tag);
  if(text!==undefined)n.textContent=text;
  if(id)n.id=id;
  return n;
 };
 const setOptions=(sel,pairs,keep)=>{
  const prev=keep!==undefined?keep:sel.value;
  sel.replaceChildren();
  for(const [val,txt] of pairs){
   const o=el('option',txt);
   o.value=String(val);
   sel.append(o);
  }
  if(pairs.some(([v])=>String(v)===String(prev)))sel.value=String(prev);
  else sel.value=pairs.length?String(pairs[0][0]):'';
 };
 const hasForbiddenMetricKey=obj=>{
  if(!obj||typeof obj!=='object')return false;
  if(Array.isArray(obj))return obj.some(hasForbiddenMetricKey);
  for(const k of Object.keys(obj)){
   if(FORBIDDEN_METRIC_KEYS.has(k))return true;
   if(hasForbiddenMetricKey(obj[k]))return true;
  }
  return false;
 };
 const parseFinite=(raw,positive=false)=>{
  const s=String(raw??'').trim();
  if(!/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(s))return null;
  const n=Number(s);
  if(!Number.isFinite(n)||(positive&&n<=0))return null;
  return n;
 };
 const parseUv=(uRaw,vRaw)=>{
  const u=parseFinite(uRaw,false),v=parseFinite(vRaw,false);
  if(u===null||v===null||u<0||u>1||v<0||v>1)return null;
  return [u,v];
 };

 let caseEpoch=0;
 let geoEpoch=0;
 let sourceEpoch=0;
 let formEpoch=0;
 let opSeq=0;
 let activeOpId=0;
 let activeOpKind='';
 let historySeq=0;
 let prepared=null;
 let calculated=null;
 let invalidationNotice='';
 let proposalMeta=null;
 let suppressingInvalidation=false;

 const anchorRows=[];
 const controlRows=[];
 const pointRows=[];

 const panel=el('section',undefined,'digPanel');
 panel.className='geometry digitizacion-calibrada';
 panel.setAttribute('aria-label','Digitización calibrada local en borrador');

 const title=el('h2','Digitización calibrada de contornos en borrador (sin coordenadas métricas manuales)');
 const intro=el('p',
  'Calibra ubicaciones normalizadas locales [u, v] en [0, 1]² contra vértices ya resueltos de una geometría 0.3.0 vigente del mismo expediente. '
  +'Nunca solicita coordenadas físicas ni JSON externo, no incorpora puntos automáticamente al modelo y no aprueba ingeniería ni habilita ETABS.'
 );

 // Panel 1: Recepción de propuesta automática / estructurada
 const proposalBox=el('div',undefined,'digPanelPropuesta');
 proposalBox.className='dig-subpanel dig-propuesta-auto';
 const proposalTitle=el('h3','1. Propuesta estructurada / automática recibida (sin aprobación)');
 const proposalIntro=el('p',
  'Este panel muestra si se recibió una propuesta automática mediante el evento d2m-digitizacion-propuesta. '
  +'Sus valores solo rellenan ubicaciones normalizadas [u, v], IDs resueltos, plano y criterios para revisión y corrección humana en pantalla.'
 );
 const proposalStatus=el('p','Sin propuesta automática cargada. Puedes revisar o completar el formulario del ingeniero abajo.','digPropuestaAviso');
 const proposalOrigin=el('p','','digPropuestaOrigen');
 proposalOrigin.hidden=true;
 proposalBox.append(proposalTitle,proposalIntro,proposalStatus,proposalOrigin);

 // Panel 2: Revisión y criterios declarados del ingeniero
 const reviewBox=el('div',undefined,'digPanelRevision');
 reviewBox.className='dig-subpanel dig-revision-ingeniero';
 const reviewTitle=el('h3','2. Revisión y criterios declarados del ingeniero');
 const limitsWarning=el('p',
  'ADVERTENCIA TÉCNICA: Tres anclas con residuo 0 solo resuelven exactamente los 6 parámetros afines y NO constituyen verificación independiente. '
  +'La bandera de contraste en controles exige al menos 3 controles independientes bien condicionados con referencias documentales separadas del ajuste, '
  +'y aun así solo contrasta esos controles en BORRADOR. La incertidumbre mostrada es un indicador conservador local (no estadístico ni normativo).',
  'digAvisoLimites'
 );

 const geoInfo=el('p','Abre una geometría 0.3.0 vigente en esta etapa para habilitar referencias resueltas.','digGeometriaInfo');

 const sourceFieldset=el('fieldset',undefined,'digFuenteFieldset');
 sourceFieldset.append(el('legend','Original, página, región del dibujo y plano geométrico'));

 const selOriginal=el('select',undefined,'digOriginal');
 const selPagina=el('select',undefined,'digPagina');
 const inpDibujo=el('input',undefined,'digDibujoId');
 inpDibujo.value='DIBUJO_1';inpDibujo.maxLength=128;
 const inpX0=el('input',undefined,'digBboxX0');inpX0.value='0';
 const inpY0=el('input',undefined,'digBboxY0');inpY0.value='0';
 const inpX1=el('input',undefined,'digBboxX1');inpX1.value='1';
 const inpY1=el('input',undefined,'digBboxY1');inpY1.value='1';

 const selPlanoSugerido=el('select',undefined,'digPlanoSugerido');
 const inpPlanoId=el('input',undefined,'digPlanoId');
 inpPlanoId.value='PLANO_Z_0';inpPlanoId.maxLength=128;
 const selPlanoEjes=el('select',undefined,'digPlanoEjes');
 setOptions(selPlanoEjes,[
  ['x,y','Planta X-Y (cota Z constante)'],
  ['x,z','Alzado X-Z (cota Y constante)'],
  ['y,z','Alzado Y-Z (cota X constante)']
 ],'x,y');
 const inpPlanoCota=el('input',undefined,'digPlanoCota');inpPlanoCota.value='0';
 const spanPlanoUnidad=el('span','m','digPlanoUnidad');

 for(const [lbl,ctrl] of [
  ['Documento original del expediente',selOriginal],
  ['Página del original (desde 1)',selPagina],
  ['Identificador del dibujo en la página',inpDibujo],
  ['Región normalizada x0 [0,1)',inpX0],
  ['Región normalizada y0 [0,1)',inpY0],
  ['Región normalizada x1 (x0,1]',inpX1],
  ['Región normalizada y1 (y0,1]',inpY1],
  ['Cotas existentes en la geometría abierta',selPlanoSugerido],
  ['Identificador del plano',inpPlanoId],
  ['Ejes del plano',selPlanoEjes],
  ['Valor constante del tercer eje (cota existente en geometría)',inpPlanoCota]
 ]){
  const l=el('label',lbl);
  if(ctrl.id)l.htmlFor=ctrl.id;
  sourceFieldset.append(l,ctrl);
 }
 const unitLine=el('p','Unidad física tomada de la geometría abierta (no editable): ');
 unitLine.append(spanPlanoUnidad);
 const btnPreparar=el('button','Preparar contexto y referencias resueltas','digPreparar');
 btnPreparar.type='button';
 sourceFieldset.append(unitLine,btnPreparar);

 // Criterios / tolerancias declaradas (9 límites obligatorios)
 const limFieldset=el('fieldset',undefined,'digLimitesFieldset');
 limFieldset.append(el('legend','Criterios y tolerancias declaradas para este cálculo (no normativos)'));
 const LIMIT_SPECS=[
  ['residuo_ajuste_max_m','digLimResiduo','Residuo máximo admisible en anclas (m)','0.02'],
  ['error_control_max_m','digLimControl','Error máximo admisible en controles independientes (m)','0.03'],
  ['incertidumbre_max_m','digLimIncertidumbre','Umbral indicativo de incertidumbre por punto (m)','0.08'],
  ['localizacion_uv','digLimLocUv','Incertidumbre declarada de localización normalizada uv (<= 1)','0.005'],
  ['referencia_m','digLimRefM','Incertidumbre declarada de referencia resuelta (m)','0.005'],
  ['condicion_max','digLimCondicion','Número de condición máximo admisible (>= 1)','50'],
  ['escala_min_m_por_uv','digLimEscalaMin','Escala singular mínima admisible (m por unidad uv)','0.1'],
  ['escala_max_m_por_uv','digLimEscalaMax','Escala singular máxima admisible (m por unidad uv)','500'],
  ['coordenada_abs_max_m','digLimCoordMax','Valor absoluto máximo de coordenada física (m)','1000']
 ];
 const limitInputs={};
 for(const [key,id,lbl,defVal] of LIMIT_SPECS){
  const inp=el('input',undefined,id);
  inp.value=defVal;
  limitInputs[key]=inp;
  const l=el('label',lbl);l.htmlFor=id;
  limFieldset.append(l,inp);
 }

 // Correspondencias normalizadas: Anclas, Controles, Puntos nuevos
 const corrFieldset=el('fieldset',undefined,'digCorrespondenciasFieldset');
 corrFieldset.append(el('legend','Correspondencias en coordenadas locales normalizadas [u, v] en [0, 1]² (nunca metros)'));
 const inpPropuestaId=el('input',undefined,'digPropuestaId');
 inpPropuestaId.value='PROP_DIG_1';inpPropuestaId.maxLength=128;
 const lblPropId=el('label','Identificador de la propuesta');lblPropId.htmlFor=inpPropuestaId.id;

 const anchorsTitle=el('h4','Anclas de ajuste (mínimo 3 IDs resueltos no colineales; propuesta de correspondencia)');
 const anchorsBox=el('div',undefined,'digAnclasLista');
 const btnAddAnchor=el('button','Añadir ancla','digAgregarAncla');btnAddAnchor.type='button';

 const controlsTitle=el('h4','Controles independientes excluidos del ajuste (0 o más; se exigen >= 3 independientes para contraste)');
 const controlsBox=el('div',undefined,'digControlesLista');
 const btnAddControl=el('button','Añadir control independiente','digAgregarControl');btnAddControl.type='button';

 const pointsTitle=el('h4','Puntos nuevos propuestos en borrador (solo [u, v] normalizados e IDs resueltos relacionados)');
 const pointsBox=el('div',undefined,'digPuntosLista');
 const btnAddPoint=el('button','Añadir punto nuevo','digAgregarPunto');btnAddPoint.type='button';

 const btnCalcular=el('button','Calcular digitización en borrador','digCalcular');
 btnCalcular.type='button';

 corrFieldset.append(
  lblPropId,inpPropuestaId,
  anchorsTitle,anchorsBox,btnAddAnchor,
  controlsTitle,controlsBox,btnAddControl,
  pointsTitle,pointsBox,btnAddPoint,
  btnCalcular
 );

 reviewBox.append(reviewTitle,limitsWarning,geoInfo,sourceFieldset,limFieldset,corrFieldset);

 // Panel 3: Historial y resultado en borrador
 const resultBox=el('div',undefined,'digPanelResultados');
 resultBox.className='dig-subpanel dig-resultados-borrador';
 const resultTitle=el('h3','3. Versiones conservadas y resultado en borrador');
 const selHistorial=el('select',undefined,'digHistorial');
 setOptions(selHistorial,[['','Sin registros consultados']]);
 const lblHist=el('label','Registros conservados en el expediente');lblHist.htmlFor=selHistorial.id;
 const btnAbrir=el('button','Abrir registro seleccionado','digAbrirRegistro');btnAbrir.type='button';
 const btnRefrescar=el('button','Actualizar historial','digRefrescarHistorial');btnRefrescar.type='button';

 const statusLine=el('p','Selecciona un expediente y abre una geometría 0.3.0 para iniciar.','digEstado');
 statusLine.setAttribute('role','status');
 statusLine.setAttribute('aria-live','polite');

 const hashLine=el('p','Sin huella activa de cálculo vigente.','digHuellaActiva');
 const summaryBox=el('div',undefined,'digResultadoResumen');
 const pendingsList=el('ul',undefined,'digPendientes');
 const pointsOutput=el('div',undefined,'digTablaPuntos');

 resultBox.append(resultTitle,lblHist,selHistorial,btnAbrir,btnRefrescar,statusLine,hashLine,summaryBox,pendingsList,pointsOutput);
 panel.append(title,intro,proposalBox,reviewBox,resultBox);

 const guide=target.querySelector?.('.stage-guide');
 if(guide&&typeof guide.after==='function')guide.after(panel);
 else target.append(panel);

 function currentIdentity(){
  const d=getDocs();
  return d&&d.caso&&d.expediente_sha256?{caso:d.caso,expediente_sha256:d.expediente_sha256}:null;
 }
 function currentGeoMeta(){
  const g=getGeo();
  const verInput=byId('geoVersion');
  const versionId=verInput?.value||g?.id||'';
  if(!g||g.comprobacion?.correcta!==true||!g.datos||g.datos.version_contrato!=='0.3.0'||!versionId)return null;
  return {
   version_id:versionId,
   huella:g.huella,
   sha256_geometria:g.sha256_geometria,
   unidad_longitud:g.datos.unidad_longitud,
   datos_sinteticos:Boolean(g.comprobacion?.validacion?.datos_sinteticos||g.datos.procedencia?.tipo==='sintetico'),
   datos:g.datos
  };
 }
  function currentGeoSig(gm=currentGeoMeta()){
   if(!gm)return null;
   return {
    version_id:gm.version_id,
    huella:gm.huella,
    sha256_geometria:gm.sha256_geometria
   };
  }
  function sameCaseId(id){
   const cur=currentIdentity();
   return Boolean(cur&&id)&&cur.caso===id.caso&&cur.expediente_sha256===id.expediente_sha256;
  }
  function sameGeoSig(a,b){
   return Boolean(a&&b)
    &&a.version_id===b.version_id
    &&a.huella===b.huella
    &&a.sha256_geometria===b.sha256_geometria;
  }
  function recordMatchesGeoSig(rec,sig){
   const go=rec?.geometria_origen;
   return Boolean(go&&sig)
    &&go.version_id===sig.version_id
    &&go.huella_contenido===sig.huella
    &&go.sha256_geometria===sig.sha256_geometria;
  }
  function isRunning(){
   return activeOpId!==0;
  }
  function cancelPendingRequests(bumpHistory=true){
   activeOpId=0;
   activeOpKind='';
   if(bumpHistory)historySeq++;
  }
  function beginOperation(kind,extra={}){
   const id=currentIdentity();
   const gm=currentGeoMeta();
   const opId=++opSeq;
   activeOpId=opId;
   activeOpKind=kind;
   return {
    opId,
    kind,
    caseEpoch,
    geoEpoch,
    sourceEpoch,
    formEpoch,
    id:id?{...id}:null,
    geoSig:currentGeoSig(gm),
    selectedHistoryId:selHistorial.value,
    ...extra
   };
  }
  function isOperationCurrent(snap,{requireGeo=true,checkHistorySelection=false}={}){
   if(!snap||snap.opId!==activeOpId||snap.kind!==activeOpKind)return false;
   if(snap.caseEpoch!==caseEpoch||!sameCaseId(snap.id))return false;
   if(snap.geoEpoch!==geoEpoch||snap.sourceEpoch!==sourceEpoch||snap.formEpoch!==formEpoch)return false;
   if(checkHistorySelection&&selHistorial.value!==snap.selectedHistoryId)return false;
   const curSig=currentGeoSig();
   if(requireGeo){
    if(!snap.geoSig||!curSig||!sameGeoSig(snap.geoSig,curSig))return false;
   }else if((snap.geoSig||curSig)&&!sameGeoSig(snap.geoSig,curSig)){
    return false;
   }
   return true;
  }
  function releaseIfActive(opId){
   if(activeOpId===opId){
    activeOpId=0;
    activeOpKind='';
    updateControlsState();
   }
  }
  function planeAxesSpec(){
   const parts=(selPlanoEjes.value||'x,y').split(',');
   const ejes=parts.length===2?parts:['x','y'];
   const eje_constante=['x','y','z'].find(a=>!ejes.includes(a))||'z';
   return {ejes,eje_constante};
  }
  function availableResolvedCatalog(){
   const curSig=currentGeoSig();
   if(prepared?.etapa==='preparada'&&prepared?.catalogo_referencias&&curSig&&recordMatchesGeoSig(prepared,curSig)){
    return prepared.catalogo_referencias.filter(r=>r.utilizable_en_fuente!==false);
   }
   const gm=currentGeoMeta();
   if(!gm)return [];
   const {eje_constante}=planeAxesSpec();
   const cota=parseFinite(inpPlanoCota.value,false);
   if(cota===null)return [];
   return (gm.datos.vertices||[])
    .filter(v=>Number(v[eje_constante])===cota)
    .map(v=>({
     id:v.id,
     coordenadas:[v[planeAxesSpec().ejes[0]],v[planeAxesSpec().ejes[1]]],
     unidad_longitud:gm.unidad_longitud,
     tiene_referencia_documental:Array.isArray(v.procedencia?.referencias)&&v.procedencia.referencias.length>0,
     utilizable_en_fuente:true
    }));
  }
  function resolvedOptionsPairs(){
   const cat=availableResolvedCatalog();
   if(!cat.length)return [['','(Prepara o elige plano con referencias)']];
   return [
    ['','Selecciona ID resuelto'],
    ...cat.map(r=>[
     r.id,
     `${r.id} (${r.coordenadas[0]}, ${r.coordenadas[1]} ${r.unidad_longitud} · ${r.tiene_referencia_documental?'con ref. doc.':'solo descriptor geom.'})`
    ])
   ];
  }
  function refreshReferenceSelects(){
   const pairs=resolvedOptionsPairs();
   for(const row of [...anchorRows,...controlRows]){
    setOptions(row.punto,pairs,row.punto.value);
   }
  }

  function markEditedIfProposal(){
   if(proposalMeta&&!suppressingInvalidation){
    proposalMeta.editada_en_pantalla=true;
    proposalStatus.textContent='Propuesta automática cargada y CORREGIDA en pantalla por el ingeniero (sin aprobar; pendiente de recalcular).';
   }
  }
  function invalidateCalculation(reason,alsoPreparation=false){
   if(suppressingInvalidation)return;
   markEditedIfProposal();
   formEpoch++;
   if(alsoPreparation)sourceEpoch++;
   const hadPendingOp=isRunning();
   const pendingKind=activeOpKind;
   if(hadPendingOp)cancelPendingRequests(true);
   const hadState=Boolean(calculated||(alsoPreparation&&prepared)||hadPendingOp);
   if(alsoPreparation||pendingKind==='preparar')prepared=null;
   calculated=null;
   if(hadState){
    invalidationNotice=reason||'Se modificaron entradas: el cálculo y la huella anteriores quedaron invalidados.';
    hashLine.textContent='Huella anterior INVALIDADA: '+invalidationNotice;
    summaryBox.replaceChildren(el('p','Resultado previo invalidado por cambio de datos. Prepara/calcula nuevamente para obtener una huella vigente.'));
    pendingsList.replaceChildren();
    pointsOutput.replaceChildren();
    if(hadPendingOp){
     statusLine.textContent='Solicitud pendiente descartada por edición en pantalla: '+invalidationNotice;
    }
   }
   if(alsoPreparation||pendingKind==='preparar')refreshReferenceSelects();
   updateControlsState();
  }

 function createRefRow(collection,box,prefix,idx,initial){
  const wrap=el('div');wrap.className='dig-row';
  const idInput=el('input',undefined,`${prefix}Id${idx}`);
  idInput.value=initial?.id||`${prefix==='digAncla'?'A':'C'}${idx}`;
  const puntoSelect=el('select',undefined,`${prefix}Punto${idx}`);
  setOptions(puntoSelect,resolvedOptionsPairs(),initial?.punto_resuelto||'');
  if(initial?.punto_resuelto&&puntoSelect.value!==initial.punto_resuelto){
   const opt=el('option',`${initial.punto_resuelto} (por validar al preparar)`);
   opt.value=initial.punto_resuelto;
   puntoSelect.append(opt);
   puntoSelect.value=initial.punto_resuelto;
  }
  const uInput=el('input',undefined,`${prefix}U${idx}`);
  uInput.value=initial?.uv_local?.[0]!==undefined?String(initial.uv_local[0]):'';
  uInput.placeholder='u [0..1]';
  const vInput=el('input',undefined,`${prefix}V${idx}`);
  vInput.value=initial?.uv_local?.[1]!==undefined?String(initial.uv_local[1]):'';
  vInput.placeholder='v [0..1]';
  const btnRemove=el('button','Quitar',`${prefix}Quitar${idx}`);btnRemove.type='button';

  const rowObj={wrap,id:idInput,punto:puntoSelect,u:uInput,v:vInput,remove:btnRemove};
  for(const ctrl of [idInput,puntoSelect,uInput,vInput]){
   const evName=ctrl.tagName?.toLowerCase()==='select'?'change':'input';
   ctrl.addEventListener(evName,()=>invalidateCalculation('Se editó una referencia o coordenada normalizada [u, v].',false));
   if(evName!=='change')ctrl.addEventListener('change',()=>invalidateCalculation('Se editó una referencia o coordenada normalizada [u, v].',false));
  }
  btnRemove.addEventListener('click',()=>{
   const pos=collection.indexOf(rowObj);
   if(pos>=0)collection.splice(pos,1);
   if(typeof wrap.remove==='function')wrap.remove();
   else box.replaceChildren(...collection.map(r=>r.wrap));
   invalidateCalculation('Se eliminó una fila de referencia.',false);
  });
  wrap.append(
   el('label','ID '),idInput,
   el('label',' Punto resuelto '),puntoSelect,
   el('label',' u local [0,1] '),uInput,
   el('label',' v local [0,1] '),vInput,
   btnRemove
  );
  collection.push(rowObj);
  box.append(wrap);
  return rowObj;
 }

 function createPointRow(idx,initial){
  const wrap=el('div');wrap.className='dig-row dig-point-row';
  const idInput=el('input',undefined,`digPuntoId${idx}`);
  idInput.value=initial?.id||`PN${idx}`;
  const uInput=el('input',undefined,`digPuntoU${idx}`);
  uInput.value=initial?.uv_local?.[0]!==undefined?String(initial.uv_local[0]):'';
  uInput.placeholder='u [0..1]';
  const vInput=el('input',undefined,`digPuntoV${idx}`);
  vInput.value=initial?.uv_local?.[1]!==undefined?String(initial.uv_local[1]):'';
  vInput.placeholder='v [0..1]';
  const relInput=el('input',undefined,`digPuntoRel${idx}`);
  relInput.value=Array.isArray(initial?.relacionados)?initial.relacionados.join(','):'';
  relInput.placeholder='IDs resueltos separados por coma (ej. V1,V2,V3)';
  const btnUsarAnclas=el('button','Usar IDs de anclas',`digPuntoUsarAnclas${idx}`);btnUsarAnclas.type='button';
  const btnRemove=el('button','Quitar',`digPuntoQuitar${idx}`);btnRemove.type='button';

  const rowObj={wrap,id:idInput,u:uInput,v:vInput,rel:relInput,useAnchors:btnUsarAnclas,remove:btnRemove};
  btnUsarAnclas.addEventListener('click',()=>{
   const used=[...new Set(anchorRows.map(r=>r.punto.value).filter(Boolean))];
   relInput.value=used.join(',');
   invalidateCalculation('Se actualizaron los IDs resueltos relacionados del punto.',false);
  });
  for(const ctrl of [idInput,uInput,vInput,relInput]){
   ctrl.addEventListener('input',()=>invalidateCalculation('Se editó un punto propuesto normalizado.',false));
   ctrl.addEventListener('change',()=>invalidateCalculation('Se editó un punto propuesto normalizado.',false));
  }
  btnRemove.addEventListener('click',()=>{
   const pos=pointRows.indexOf(rowObj);
   if(pos>=0)pointRows.splice(pos,1);
   if(typeof wrap.remove==='function')wrap.remove();
   else pointsBox.replaceChildren(...pointRows.map(r=>r.wrap));
   invalidateCalculation('Se eliminó un punto propuesto.',false);
  });
  wrap.append(
   el('label','ID nuevo '),idInput,
   el('label',' u local [0,1] '),uInput,
   el('label',' v local [0,1] '),vInput,
   el('label',' IDs resueltos relacionados '),relInput,
   btnUsarAnclas,
   btnRemove
  );
  pointRows.push(rowObj);
  pointsBox.append(wrap);
  return rowObj;
 }

 function resetDefaultRows(){
  anchorRows.length=0;anchorsBox.replaceChildren();
  controlRows.length=0;controlsBox.replaceChildren();
  pointRows.length=0;pointsBox.replaceChildren();
  for(let i=1;i<=3;i++)createRefRow(anchorRows,anchorsBox,'digAncla',i);
  createPointRow(1);
 }

 function populateDocumentsAndPages(){
  const d=getDocs();
  const validDocs=(d?.documentos||[]).filter(doc=>!doc.error&&doc.paginas>=1);
  if(!validDocs.length){
   setOptions(selOriginal,[['','Sin originales disponibles']]);
   setOptions(selPagina,[['','Sin páginas']]);
   return;
  }
  setOptions(selOriginal,validDocs.map(doc=>[doc.id,`${doc.id} · ${doc.nombre||doc.id}`]),selOriginal.value);
  updatePagesForSelectedDoc();
 }
 function updatePagesForSelectedDoc(keepPage){
  const d=getDocs();
  const doc=(d?.documentos||[]).find(item=>item.id===selOriginal.value&&!item.error);
  if(!doc||doc.paginas<1){
   setOptions(selPagina,[['','Sin páginas']]);
   return;
  }
  const pages=Array.from({length:doc.paginas},(_,i)=>[String(i+1),`Página ${i+1}`]);
  setOptions(selPagina,pages,keepPage!==undefined?String(keepPage):selPagina.value);
 }

 function refreshSuggestedPlanes(){
  const gm=currentGeoMeta();
  if(!gm){
   spanPlanoUnidad.textContent='—';
   geoInfo.textContent='Abre y comprueba una geometría 0.3.0 vigente para habilitar la digitización calibrada.';
   setOptions(selPlanoSugerido,[['','Sin geometría 0.3.0 abierta']]);
   return;
  }
  spanPlanoUnidad.textContent=gm.unidad_longitud;
  geoInfo.textContent=`Geometría 0.3.0 activa: ${gm.version_id} · huella ${gm.huella.slice(0,12)}… · unidad ${gm.unidad_longitud} · `
   +(gm.datos_sinteticos?'DATOS SINTÉTICOS (solo prueba de software)':'Procedencia declarada en borrador');
  const {eje_constante}=planeAxesSpec();
  const counts=new Map();
  for(const v of gm.datos.vertices||[]){
   const val=Number(v[eje_constante]);
   if(Number.isFinite(val))counts.set(val,(counts.get(val)||0)+1);
  }
  if(eje_constante==='z'){
   for(const n of gm.datos.niveles||[]){
    const val=Number(n.cota);
    if(n.cota!==null&&Number.isFinite(val)&&!counts.has(val))counts.set(val,0);
   }
  }
  const sorted=[...counts.entries()].sort((a,b)=>a[0]-b[0]);
  if(!sorted.length){
   setOptions(selPlanoSugerido,[['','Sin cotas disponibles en este eje']]);
   return;
  }
  setOptions(
   selPlanoSugerido,
   sorted.map(([val,cnt])=>[String(val),`${eje_constante} = ${val} ${gm.unidad_longitud} (${cnt} vértices coplanares)`]),
   inpPlanoCota.value
  );
  if(!counts.has(Number(inpPlanoCota.value))){
   inpPlanoCota.value=String(sorted[0][0]);
   selPlanoSugerido.value=String(sorted[0][0]);
   inpPlanoId.value=`PLANO_${eje_constante.toUpperCase()}_${String(sorted[0][0]).replace(/[^A-Za-z0-9_.-]/g,'_')}`;
  }
 }

 function buildFuenteRequest(requireSha){
  const original_id=selOriginal.value.trim();
  const pagina=Number(selPagina.value);
  const dibujo_id=inpDibujo.value.trim();
  const x0=parseFinite(inpX0.value),y0=parseFinite(inpY0.value),x1=parseFinite(inpX1.value),y1=parseFinite(inpY1.value);
  if(!ID_RE.test(original_id))throw Error('Selecciona un documento original válido del expediente.');
  if(!Number.isInteger(pagina)||pagina<1)throw Error('Selecciona un número de página entero desde 1.');
  if(!ID_RE.test(dibujo_id))throw Error('Indica un identificador válido para el dibujo.');
  if(x0===null||y0===null||x1===null||y1===null||!(0<=x0&&x0<x1&&x1<=1&&0<=y0&&y0<y1&&y1<=1)){
   throw Error('La región normalizada bbox_pagina debe cumplir 0 <= x0 < x1 <= 1 y 0 <= y0 < y1 <= 1.');
  }
  const f={original_id,pagina,dibujo_id,bbox_pagina:[x0,y0,x1,y1]};
  if(requireSha){
   const sha=prepared?.fuente_vigente?.sha256;
   if(!sha)throw Error('Prepara primero el contexto para verificar los bytes y el SHA-256 real del original.');
   f.sha256=sha;
  }
  return f;
 }

 function buildPlanoRequest(gm){
  const id=inpPlanoId.value.trim();
  if(!ID_RE.test(id))throw Error('Identificador de plano inválido.');
  const {ejes,eje_constante}=planeAxesSpec();
  const valor_constante=parseFinite(inpPlanoCota.value);
  if(valor_constante===null)throw Error('Indica un valor constante numérico finito para el plano.');
  return {id,ejes,eje_constante,valor_constante,unidad_longitud:gm.unidad_longitud};
 }

 function buildLimitesRequest(){
  const out={};
  for(const [key,,lbl] of LIMIT_SPECS){
   const val=parseFinite(limitInputs[key].value,true);
   if(val===null)throw Error(`Criterio inválido en «${lbl}»: ingresa un número finito positivo.`);
   out[key]=val;
  }
  if(out.condicion_max<1)throw Error('El número de condición máximo debe ser >= 1.');
  if(!(out.escala_min_m_por_uv<out.escala_max_m_por_uv))throw Error('La escala mínima debe ser estrictamente menor que la escala máxima.');
  if(out.localizacion_uv>1)throw Error('La incertidumbre de localización normalizada uv debe ser <= 1.');
  return out;
 }

 function buildOrigenPropuesta(){
  if(!proposalMeta)return {modo:'interfaz_revision_ingenieria',referencia_origen:null,editada_en_pantalla:false};
  return {
   modo:'propuesta_estructurada_revisada',
   referencia_origen:proposalMeta.referencia||null,
   editada_en_pantalla:Boolean(proposalMeta.editada_en_pantalla)
  };
 }

 function renderRecord(rec){
  summaryBox.replaceChildren();
  pendingsList.replaceChildren();
  pointsOutput.replaceChildren();
  invalidationNotice='';

  const res=rec.resumen||{};
  hashLine.textContent=`Versión ${rec.id} · etapa ${rec.etapa} · huella ${rec.huella_version}`
   +(rec.hashes_entradas?.huella_entrada_modulo?` · huella cálculo ${rec.hashes_entradas.huella_entrada_modulo}`:'');

  if(rec.datos_sinteticos){
   const syn=el('p','DATOS SINTÉTICOS CONSERVADOS: este registro proviene de una geometría sintética de prueba y no representa un proyecto real.');
   syn.className='dig-badge-sintetico';
   summaryBox.append(syn);
  }

  const draftBadge=el('p',
   `Estado: BORRADOR (${rec.revision?.estado||'borrador'}) · disponible_para_modelado: false · aprueba_ingenieria: false · `
   +`cálculo posible: ${res.calculo_posible?'sí':'no'} · `
   +`contraste numérico en >=3 controles independientes: ${res.contraste_en_controles?'SÍ (solo controles declarados)':'NO'} · `
   +`exactitud documental en dibujo: ${res.exactitud_documental_acreditada?'acreditada':'NO ACREDITADA'}.`
  );
  summaryBox.append(draftBadge);

  if(res.ajuste_tres_anclas_sin_verificacion||(rec.resultado&&rec.resultado.anclas?.length===3&&!res.contraste_en_controles)){
   const warn3=el('p',
    'AVISO DE NO VERIFICACIÓN: Ajuste con 3 anclas (residuo 0 m). Tres anclas determinan exactamente la transformación afín y NO prueban exactitud independiente.'
   );
   warn3.className='dig-warn-tres-anclas';
   summaryBox.append(warn3);
  }

  if(res.carencia_vinculo_documental||!res.exactitud_documental_acreditada){
   const warnDoc=el('p',
    'VÍNCULO DOCUMENTAL NO ACREDITADO: La geometría o lectura carece de evidencia documental de ubicación en el dibujo; la ausencia de vínculo nunca equivale a exactitud comprobada.'
   );
   warnDoc.className='dig-warn-documental';
   summaryBox.append(warnDoc);
  }

  for(const p of rec.pendientes||[]){
   const extra=Array.isArray(p.puntos)&&p.puntos.length?` [puntos: ${p.puntos.join(', ')}]`:'';
   pendingsList.append(el('li',`[${p.codigo}] ${p.mensaje}${extra}`));
  }

  if(rec.resultado){
   const r=rec.resultado;
   const fitLine=el('p',
    `Ajuste afín: residuo máx. anclas = ${r.residuo_ajuste_max_m.toFixed(6)} m · `
    +`error máx. controles = ${r.error_control_max_m===null?'sin controles (no verificado)':r.error_control_max_m.toFixed(6)+' m'} · `
    +`condición = ${r.transformacion.condicion_diseno.toFixed(3)} · `
    +`escalas singulares = [${r.transformacion.escalas_singulares_m_por_uv[0].toFixed(4)}, ${r.transformacion.escalas_singulares_m_por_uv[1].toFixed(4)}] m/uv.`
   );
   summaryBox.append(fitLine);

   for(const a of r.anclas||[]){
    pointsOutput.append(el('p',
     `Ancla ${a.id} -> resuelto ${a.punto_resuelto} · uv_local [${a.uv_local[0]}, ${a.uv_local[1]}] · residuo ${a.residuo_m.toFixed(6)} m · refs: ${a.referencias.join(', ')}`
    ));
   }
   for(const c of r.controles||[]){
    pointsOutput.append(el('p',
     `Control ${c.id} -> resuelto ${c.punto_resuelto} · uv_local [${c.uv_local[0]}, ${c.uv_local[1]}] · error ${c.residuo_m.toFixed(6)} m · refs: ${c.referencias.join(', ')}`
    ));
   }
   for(const pt of r.puntos||[]){
    const c=pt.coordenadas_m;
    const inc=pt.incertidumbre;
    pointsOutput.append(el('p',
     `Punto borrador ${pt.id}: uv_local [${pt.uv_local[0]}, ${pt.uv_local[1]}] · uv_pagina [${pt.uv_pagina[0].toFixed(4)}, ${pt.uv_pagina[1].toFixed(4)}] · `
     +`borrador (m) x=${c.x.toFixed(4)}, y=${c.y.toFixed(4)}, z=${c.z.toFixed(4)} · `
     +`${pt.extrapolacion?'EXTRAPOLADO (fuera casco anclas)':'dentro casco anclas'} · `
     +`incertidumbre indicativa ±${inc.indicador_m.toFixed(4)} m (${inc.dentro_limite?'dentro de límite declarado':'EXCEDE límite declarado'})`
    ));
   }
  }
 }

 function populateFormFromRecord(rec){
  suppressingInvalidation=true;
  try{
   if(rec.fuente_vigente){
    updatePagesForSelectedDoc(rec.fuente_vigente.pagina);
    selOriginal.value=rec.fuente_vigente.original_id;
    updatePagesForSelectedDoc(rec.fuente_vigente.pagina);
    selPagina.value=String(rec.fuente_vigente.pagina);
    inpDibujo.value=rec.fuente_vigente.dibujo_id;
    const [x0,y0,x1,y1]=rec.fuente_vigente.bbox_pagina;
    inpX0.value=String(x0);inpY0.value=String(y0);inpX1.value=String(x1);inpY1.value=String(y1);
   }
   if(rec.plano){
    inpPlanoId.value=rec.plano.id;
    selPlanoEjes.value=rec.plano.ejes.join(',');
    inpPlanoCota.value=String(rec.plano.valor_constante);
    spanPlanoUnidad.textContent=rec.plano.unidad_longitud;
   }
   refreshReferenceSelects();
   if(rec.propuesta){
    inpPropuestaId.value=rec.propuesta.id;
    for(const [k] of LIMIT_SPECS){
     if(rec.propuesta.limites?.[k]!==undefined)limitInputs[k].value=String(rec.propuesta.limites[k]);
    }
    anchorRows.length=0;anchorsBox.replaceChildren();
    (rec.propuesta.anclas||[]).forEach((a,i)=>createRefRow(anchorRows,anchorsBox,'digAncla',i+1,a));
    controlRows.length=0;controlsBox.replaceChildren();
    (rec.propuesta.controles||[]).forEach((c,i)=>createRefRow(controlRows,controlsBox,'digControl',i+1,c));
    pointRows.length=0;pointsBox.replaceChildren();
    (rec.propuesta.puntos||[]).forEach((p,i)=>createPointRow(i+1,p));
   }
  }finally{
   suppressingInvalidation=false;
  }
 }

 async function loadHistory(ctxSnap,selectedId){
  const callApi=getApi();
  const id=ctxSnap?.id||currentIdentity();
  const ownCaseEpoch=ctxSnap?.caseEpoch??caseEpoch;
  const ownGeoEpoch=ctxSnap?.geoEpoch??geoEpoch;
  const ownSourceEpoch=ctxSnap?.sourceEpoch??sourceEpoch;
  const ownFormEpoch=ctxSnap?.formEpoch??formEpoch;
  const ownGeoSig=ctxSnap&&'geoSig' in ctxSnap?ctxSnap.geoSig:currentGeoSig();
  if(!callApi||!id||ownCaseEpoch!==caseEpoch||!sameCaseId(id))return;
  const hSeq=++historySeq;
  const res=await callApi('/api/digitizacion/historial?'+new URLSearchParams(id));
  const data=await res.json();
  if(hSeq!==historySeq||ownCaseEpoch!==caseEpoch||!sameCaseId(id))return;
  const curSig=currentGeoSig();
  const sameSubContext=ownGeoEpoch===geoEpoch
   &&ownSourceEpoch===sourceEpoch
   &&ownFormEpoch===formEpoch
   &&((!ownGeoSig&&!curSig)||sameGeoSig(ownGeoSig,curSig));
  if(selectedId&&!sameSubContext)return;
  const rows=Array.isArray(data)?data:(data.registros||data.versiones||[]);
  const pairs=[
   ['','Selecciona un registro conservado'],
   ...rows.map(r=>typeof r==='string'
    ?[r,r]
    :[r.id,`${r.id.slice(0,10)}… · ${r.etapa||'registro'} · ${r.vigente===false?'NO VIGENTE':(r.dibujo_id||'')+' · pend:'+r.pendientes}`])
  ];
  setOptions(selHistorial,pairs,sameSubContext&&selectedId?selectedId:selHistorial.value);
  updateControlsState();
 }

 function updateControlsState(){
  const id=currentIdentity();
  const gm=currentGeoMeta();
  const sig=currentGeoSig(gm);
  const busy=isRunning();
  const canPrep=!busy&&Boolean(id)&&Boolean(gm)&&Boolean(selOriginal.value);
  const prepValid=Boolean(prepared)&&prepared.etapa==='preparada'&&Boolean(sig)&&recordMatchesGeoSig(prepared,sig);
  btnPreparar.disabled=!canPrep;
  btnCalcular.disabled=!canPrep||!prepValid||anchorRows.length<3||pointRows.length<1;
  btnAbrir.disabled=busy||!id||!selHistorial.value;
  btnRefrescar.disabled=busy||!id;
  btnAddAnchor.disabled=busy||!id;
  btnAddControl.disabled=busy||!id;
  btnAddPoint.disabled=busy||!id;
 }

 btnAddAnchor.addEventListener('click',()=>{
  createRefRow(anchorRows,anchorsBox,'digAncla',anchorRows.length+1);
  invalidateCalculation('Se añadió un ancla por completar.',false);
 });
 btnAddControl.addEventListener('click',()=>{
  createRefRow(controlRows,controlsBox,'digControl',controlRows.length+1);
  invalidateCalculation('Se añadió un control independiente por completar.',false);
 });
 btnAddPoint.addEventListener('click',()=>{
  createPointRow(pointRows.length+1);
  invalidateCalculation('Se añadió un punto propuesto por completar.',false);
 });

 selOriginal.addEventListener('change',()=>{
  updatePagesForSelectedDoc();
  invalidateCalculation('Cambió el documento original seleccionado.',true);
 });
 for(const ctrl of [selPagina,inpDibujo,inpX0,inpY0,inpX1,inpY1,inpPlanoId,inpPlanoCota]){
  const evName=ctrl.tagName?.toLowerCase()==='select'?'change':'input';
  ctrl.addEventListener(evName,()=>invalidateCalculation('Cambió la fuente, región o plano; vuelve a preparar y calcular.',true));
  if(evName!=='change')ctrl.addEventListener('change',()=>invalidateCalculation('Cambió la fuente, región o plano; vuelve a preparar y calcular.',true));
 }
 selPlanoEjes.addEventListener('change',()=>{
  refreshSuggestedPlanes();
  invalidateCalculation('Cambiaron los ejes del plano declarado.',true);
 });
 selPlanoSugerido.addEventListener('change',()=>{
  if(selPlanoSugerido.value!==''){
   inpPlanoCota.value=selPlanoSugerido.value;
   const {eje_constante}=planeAxesSpec();
   inpPlanoId.value=`PLANO_${eje_constante.toUpperCase()}_${selPlanoSugerido.value.replace(/[^A-Za-z0-9_.-]/g,'_')}`;
   invalidateCalculation('Cambió la cota seleccionada del plano.',true);
  }
 });
 inpPropuestaId.addEventListener('input',()=>invalidateCalculation('Cambió el identificador de propuesta.',false));
 for(const [,inp] of Object.entries(limitInputs)){
  inp.addEventListener('input',()=>invalidateCalculation('Se modificó un límite o tolerancia declarada.',false));
  inp.addEventListener('change',()=>invalidateCalculation('Se modificó un límite o tolerancia declarada.',false));
 }
 selHistorial.addEventListener('change',()=>{
  if(activeOpKind==='abrir')cancelPendingRequests(false);
  updateControlsState();
 });

 btnPreparar.addEventListener('click',async()=>{
  const id=currentIdentity(),gm=currentGeoMeta(),callApi=getApi();
  if(!id||!gm||!callApi||isRunning())return;
  let fuente,plano,origen_propuesta;
  try{
   fuente=buildFuenteRequest(false);
   plano=buildPlanoRequest(gm);
   origen_propuesta=buildOrigenPropuesta();
  }catch(err){
   statusLine.textContent=err.message||'No se pudo preparar la digitización.';
   notify(statusLine.textContent,true);
   updateControlsState();
   return;
  }
  const snap=beginOperation('preparar');
  updateControlsState();
  statusLine.textContent='Verificando bytes originales, página y geometría 0.3.0 vigente…';
  try{
   const res=await callApi('/api/digitizacion/preparar',{
    ...id,
    geometria:gm.version_id,
    huella_geometria:gm.huella,
    sha256_geometria:gm.sha256_geometria,
    fuente,
    plano,
    origen_propuesta
   });
   const rec=await res.json();
   if(!isOperationCurrent(snap,{requireGeo:true})){
    releaseIfActive(snap.opId);
    return;
   }
   if(rec?.caso!==snap.id.caso||rec?.expediente_sha256!==snap.id.expediente_sha256||rec?.etapa!=='preparada'||!recordMatchesGeoSig(rec,snap.geoSig)){
    releaseIfActive(snap.opId);
    statusLine.textContent='Respuesta de preparación descartada: no coincide con la geometría o expediente activos.';
    notify(statusLine.textContent,true);
    return;
   }
   activeOpId=0;
   activeOpKind='';
   prepared=rec;
   calculated=null;
   refreshReferenceSelects();
   renderRecord(rec);
   statusLine.textContent=rec.resumen?.referencias_suficientes_para_ajuste
    ?'Contexto y referencias resueltas verificados. Revisa ubicaciones normalizadas [u, v] y ejecuta el cálculo en borrador.'
    :'Preparación registrada con PENDIENTES: faltan referencias coplanares suficientes en la geometría.';
   updateControlsState();
   await loadHistory(snap,rec.id);
  }catch(err){
   if(isOperationCurrent(snap,{requireGeo:true})){
    releaseIfActive(snap.opId);
    statusLine.textContent=err.message||'No se pudo preparar la digitización.';
    notify(statusLine.textContent,true);
   }else{
    releaseIfActive(snap.opId);
   }
  }
 });

 btnCalcular.addEventListener('click',async()=>{
  const id=currentIdentity(),gm=currentGeoMeta(),callApi=getApi();
  if(!id||!gm||!prepared||!callApi||isRunning())return;
  const sig=currentGeoSig(gm);
  if(prepared.etapa!=='preparada'||!recordMatchesGeoSig(prepared,sig)){
   prepared=null;
   updateControlsState();
   statusLine.textContent='La preparación activa no corresponde a la geometría abierta; prepara nuevamente.';
   notify(statusLine.textContent,true);
   return;
  }
  let propId,fuente,plano,limites,anclas,controles,puntos,origen_propuesta;
  try{
   propId=inpPropuestaId.value.trim();
   if(!ID_RE.test(propId))throw Error('Identificador de propuesta inválido.');
   fuente=buildFuenteRequest(true);
   plano=buildPlanoRequest(gm);
   limites=buildLimitesRequest();
   if(anchorRows.length<3)throw Error('Declara al menos 3 anclas con IDs ya resueltos.');
   anclas=anchorRows.map((r,idx)=>{
    const aid=r.id.value.trim(),pid=r.punto.value.trim(),uv=parseUv(r.u.value,r.v.value);
    if(!ID_RE.test(aid)||!ID_RE.test(pid)||!uv)throw Error(`Ancla ${idx+1}: completa ID, punto resuelto y coordenadas uv_local en [0, 1].`);
    return {id:aid,punto_resuelto:pid,uv_local:uv};
   });
   controles=controlRows.map((r,idx)=>{
    const cid=r.id.value.trim(),pid=r.punto.value.trim(),uv=parseUv(r.u.value,r.v.value);
    if(!ID_RE.test(cid)||!ID_RE.test(pid)||!uv)throw Error(`Control ${idx+1}: completa ID, punto resuelto y coordenadas uv_local en [0, 1].`);
    return {id:cid,punto_resuelto:pid,uv_local:uv};
   });
   if(pointRows.length<1)throw Error('Declara al menos 1 punto nuevo propuesto en coordenadas normalizadas.');
   puntos=pointRows.map((r,idx)=>{
    const pid=r.id.value.trim(),uv=parseUv(r.u.value,r.v.value);
    const relacionados=r.rel.value.split(',').map(s=>s.trim()).filter(Boolean);
    if(!ID_RE.test(pid)||!uv||!relacionados.length||relacionados.some(x=>!ID_RE.test(x))){
     throw Error(`Punto nuevo ${idx+1}: indica ID, uv_local en [0, 1] y al menos un ID resuelto relacionado.`);
    }
    return {id:pid,uv_local:uv,relacionados};
   });
   origen_propuesta=buildOrigenPropuesta();
  }catch(err){
   statusLine.textContent=err.message||'El cálculo de digitización fue rechazado.';
   notify(statusLine.textContent,true);
   updateControlsState();
   return;
  }

  const prepId=prepared.id,prepHuella=prepared.huella_version;
  const snap=beginOperation('calcular',{prepId,prepHuella});
  updateControlsState();
  statusLine.textContent='Calculando transformación afín e incertidumbre indicativa en borrador…';
  try{
   const res=await callApi('/api/digitizacion/calcular',{
    ...id,
    geometria:gm.version_id,
    huella_geometria:gm.huella,
    sha256_geometria:gm.sha256_geometria,
    preparacion_id:prepId,
    huella_preparacion:prepHuella,
    propuesta_id:propId,
    fuente,
    plano,
    limites,
    anclas,
    controles,
    puntos,
    origen_propuesta
   });
   const rec=await res.json();
   if(!isOperationCurrent(snap,{requireGeo:true})||prepared?.id!==snap.prepId||prepared?.huella_version!==snap.prepHuella){
    releaseIfActive(snap.opId);
    return;
   }
   if(rec?.caso!==snap.id.caso||rec?.expediente_sha256!==snap.id.expediente_sha256||!recordMatchesGeoSig(rec,snap.geoSig)){
    releaseIfActive(snap.opId);
    statusLine.textContent='Respuesta de cálculo descartada: no coincide con la geometría o expediente activos.';
    notify(statusLine.textContent,true);
    return;
   }
   activeOpId=0;
   activeOpKind='';
   calculated=rec;
   renderRecord(rec);
   statusLine.textContent=rec.resumen?.calculo_posible
    ?'Digitización calculada y conservada en BORRADOR (no incorporada al modelo ni aprobada).'
    :'Registro conservado con pendientes por falta de referencias suficientes.';
   updateControlsState();
   await loadHistory(snap,rec.id);
  }catch(err){
   if(isOperationCurrent(snap,{requireGeo:true})){
    releaseIfActive(snap.opId);
    statusLine.textContent=err.message||'El cálculo de digitización fue rechazado.';
    notify(statusLine.textContent,true);
   }else{
    releaseIfActive(snap.opId);
   }
  }
 });

 btnAbrir.addEventListener('click',async()=>{
  const id=currentIdentity(),regId=selHistorial.value,callApi=getApi();
  if(!id||!regId||!callApi||isRunning())return;
  const snap=beginOperation('abrir',{selectedHistoryId:regId});
  updateControlsState();
  statusLine.textContent='Consultando y revalidando registro conservado…';
  try{
   const res=await callApi('/api/digitizacion/registro?'+new URLSearchParams({...id,id:regId}));
   const rec=await res.json();
   if(!isOperationCurrent(snap,{requireGeo:false,checkHistorySelection:true})){
    releaseIfActive(snap.opId);
    return;
   }
   const curSig=currentGeoSig();
   if(rec?.id!==regId||rec?.caso!==snap.id.caso||rec?.expediente_sha256!==snap.id.expediente_sha256||!curSig||!recordMatchesGeoSig(rec,curSig)){
    releaseIfActive(snap.opId);
    statusLine.textContent=!curSig
     ?'Abre primero la geometría 0.3.0 correspondiente antes de restaurar un registro conservado.'
     :'El registro seleccionado pertenece a otra versión o huella de geometría; no se restaura sobre la geometría abierta.';
    notify(statusLine.textContent,true);
    return;
   }
   activeOpId=0;
   activeOpKind='';
   if(rec.etapa==='preparada'){
    prepared=rec;
    calculated=null;
   }else{
    calculated=rec;
    if(
     prepared&&(
      prepared.etapa!=='preparada'
      ||!recordMatchesGeoSig(prepared,curSig)
      ||JSON.stringify(prepared.fuente_vigente)!==JSON.stringify(rec.fuente_vigente)
      ||JSON.stringify(prepared.plano)!==JSON.stringify(rec.plano)
     )
    ){
     prepared=null;
    }
   }
   populateFormFromRecord(rec);
   renderRecord(rec);
   statusLine.textContent=`Registro ${rec.id} abierto y comprobado en BORRADOR.`;
   updateControlsState();
  }catch(err){
   if(isOperationCurrent(snap,{requireGeo:false,checkHistorySelection:true})){
    releaseIfActive(snap.opId);
    statusLine.textContent=err.message||'El registro perdió vigencia o no pudo abrirse.';
    notify(statusLine.textContent,true);
   }else{
    releaseIfActive(snap.opId);
   }
  }
 });

 btnRefrescar.addEventListener('click',()=>{
  const id=currentIdentity();
  if(!id||isRunning())return;
  const snap={id:{...id},caseEpoch,geoEpoch,sourceEpoch,formEpoch,geoSig:currentGeoSig()};
  loadHistory(snap).catch(err=>{
   if(snap.caseEpoch===caseEpoch&&sameCaseId(snap.id)){
    statusLine.textContent=err.message||'No se pudo consultar el historial de digitización.';
   }
  });
 });

 // Evento estructurado d2m-digitizacion-propuesta (sin coordenadas físicas ni autoaprobación)
 window.addEventListener('d2m-digitizacion-propuesta',ev=>{
  const detail=ev?.detail;
  const id=currentIdentity();
  if(!id){
   statusLine.textContent='Abre primero un expediente antes de recibir una propuesta de digitización.';
   return;
  }
  if(!detail||typeof detail!=='object'||detail.caso!==id.caso||detail.expediente_sha256!==id.expediente_sha256){
   statusLine.textContent='Propuesta automática descartada: no corresponde al expediente abierto.';
   return;
  }
  if(hasForbiddenMetricKey(detail)){
   statusLine.textContent='Propuesta automática RECHAZADA: contiene coordenadas métricas físicas prohibidas.';
   notify(statusLine.textContent,true);
   return;
  }
  const gm=currentGeoMeta();
  if(
   gm&&(
    (detail.geometria&&detail.geometria!==gm.version_id)
    ||(detail.huella_geometria&&detail.huella_geometria!==gm.huella)
    ||(detail.sha256_geometria&&detail.sha256_geometria!==gm.sha256_geometria)
   )
  ){
   statusLine.textContent='Propuesta automática descartada: apunta a otra versión o huella de geometría.';
   return;
  }
  if(gm&&detail.plano?.unidad_longitud&&detail.plano.unidad_longitud!==gm.unidad_longitud){
   statusLine.textContent='Propuesta automática rechazada: la unidad del plano no coincide con la geometría abierta.';
   return;
  }

  sourceEpoch++;
  formEpoch++;
  cancelPendingRequests(true);
  suppressingInvalidation=true;
  try{
   prepared=null;
   calculated=null;
   if(detail.propuesta_id&&ID_RE.test(detail.propuesta_id))inpPropuestaId.value=detail.propuesta_id;
   if(detail.fuente){
    if(detail.fuente.original_id){
     selOriginal.value=detail.fuente.original_id;
     updatePagesForSelectedDoc(detail.fuente.pagina);
    }
    if(detail.fuente.pagina!==undefined)selPagina.value=String(detail.fuente.pagina);
    if(detail.fuente.dibujo_id)inpDibujo.value=detail.fuente.dibujo_id;
    if(Array.isArray(detail.fuente.bbox_pagina)&&detail.fuente.bbox_pagina.length===4){
     inpX0.value=String(detail.fuente.bbox_pagina[0]);
     inpY0.value=String(detail.fuente.bbox_pagina[1]);
     inpX1.value=String(detail.fuente.bbox_pagina[2]);
     inpY1.value=String(detail.fuente.bbox_pagina[3]);
    }
   }
   if(detail.plano){
    if(detail.plano.id)inpPlanoId.value=detail.plano.id;
    if(Array.isArray(detail.plano.ejes)&&detail.plano.ejes.length===2)selPlanoEjes.value=detail.plano.ejes.join(',');
    if(detail.plano.valor_constante!==undefined)inpPlanoCota.value=String(detail.plano.valor_constante);
   }
   if(detail.limites){
    for(const [k] of LIMIT_SPECS){
     if(detail.limites[k]!==undefined)limitInputs[k].value=String(detail.limites[k]);
    }
   }
   refreshSuggestedPlanes();
   refreshReferenceSelects();
   if(Array.isArray(detail.anclas)){
    anchorRows.length=0;anchorsBox.replaceChildren();
    detail.anclas.forEach((a,i)=>createRefRow(anchorRows,anchorsBox,'digAncla',i+1,a));
   }
   if(Array.isArray(detail.controles)){
    controlRows.length=0;controlsBox.replaceChildren();
    detail.controles.forEach((c,i)=>createRefRow(controlRows,controlsBox,'digControl',i+1,c));
   }
   if(Array.isArray(detail.puntos)){
    pointRows.length=0;pointsBox.replaceChildren();
    detail.puntos.forEach((p,i)=>createPointRow(i+1,p));
   }
  }finally{
   suppressingInvalidation=false;
  }

  const refOrigen=typeof detail.referencia_origen==='string'&&ID_RE.test(detail.referencia_origen)?detail.referencia_origen:null;
  proposalMeta={referencia:refOrigen,editada_en_pantalla:false};
  proposalStatus.textContent='Propuesta estructurada cargada en pantalla SIN APROBAR. Revisa/corrige ubicaciones normalizadas [u, v], prepara referencias y calcula el borrador.';
  proposalOrigin.textContent=`Origen estructurado: ${refOrigen||'sin referencia declarada'} · anclas propuestas: ${anchorRows.length} · controles: ${controlRows.length} · puntos nuevos: ${pointRows.length}.`;
  proposalOrigin.hidden=false;
  hashLine.textContent='Propuesta cargada sin calcular: prepara el contexto y pulsa «Calcular digitización en borrador».';
  summaryBox.replaceChildren();
  pendingsList.replaceChildren();
  pointsOutput.replaceChildren();
  statusLine.textContent='Propuesta automática rellenada para revisión del ingeniero; no se ejecutó ni aprobó automáticamente.';
  updateControlsState();
 });

 window.addEventListener('d2m-geometry-opened',()=>{
  geoEpoch++;
  const gm=currentGeoMeta();
  const sig=currentGeoSig(gm);
  const hadPending=isRunning();
  if(hadPending)cancelPendingRequests(true);
  const activeRec=calculated||prepared;
  const changed=hadPending||!activeRec||!sig||!recordMatchesGeoSig(activeRec,sig);
  if(changed){
   sourceEpoch++;
   formEpoch++;
   historySeq++;
   prepared=null;
   calculated=null;
   hashLine.textContent=gm
    ?'Geometría cambiada: prepara nuevamente el contexto antes de calcular.'
    :'Abre una geometría 0.3.0 vigente para preparar referencias.';
   summaryBox.replaceChildren();
   pendingsList.replaceChildren();
   pointsOutput.replaceChildren();
   if(hadPending){
    statusLine.textContent=gm
     ?'Solicitud pendiente descartada al cambiar de geometría. Prepara el contexto de la geometría actual.'
     :'Solicitud pendiente descartada: abre una geometría 0.3.0 vigente.';
   }
  }
  refreshSuggestedPlanes();
  refreshReferenceSelects();
  updateControlsState();
 });

 window.addEventListener('d2m-case',async()=>{
  caseEpoch++;
  geoEpoch++;
  sourceEpoch++;
  formEpoch++;
  cancelPendingRequests(true);
  prepared=null;
  calculated=null;
  proposalMeta=null;
  invalidationNotice='';
  proposalStatus.textContent='Sin propuesta automática cargada. Puedes revisar o completar el formulario del ingeniero abajo.';
  proposalOrigin.textContent='';
  proposalOrigin.hidden=true;
  hashLine.textContent='Sin huella activa de cálculo vigente.';
  summaryBox.replaceChildren();
  pendingsList.replaceChildren();
  pointsOutput.replaceChildren();
  setOptions(selHistorial,[['','Sin registros consultados']]);
  populateDocumentsAndPages();
  refreshSuggestedPlanes();
  resetDefaultRows();
  const id=currentIdentity();
  statusLine.textContent=id
   ?'Expediente abierto. Abre una geometría 0.3.0 vigente o consulta registros conservados.'
   :'Selecciona un expediente para iniciar.';
  updateControlsState();
  if(!id)return;
  const snap={id:{...id},caseEpoch,geoEpoch,sourceEpoch,formEpoch,geoSig:currentGeoSig()};
  try{
   await loadHistory(snap);
  }catch(err){
   if(snap.caseEpoch===caseEpoch&&sameCaseId(snap.id)){
    statusLine.textContent=err.message||'No se pudo consultar el historial de digitización.';
   }
  }
 });

 populateDocumentsAndPages();
 refreshSuggestedPlanes();
 resetDefaultRows();
 updateControlsState();
})();
