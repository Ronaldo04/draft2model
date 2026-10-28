'use strict';
const $=id=>document.getElementById(id);
const token=document.querySelector('meta[name="revision-session"]').content;
let docs=null, record=null, selected=null, imageUrl=null, epoch=0, pageEpoch=0, busy=false, geoRecord=null, geoEpoch=0;
const stateOf=c=>c.revision?.estado||'pendiente';
// Contrato 0.2.0: el tipo decide valor y unidades. Un resultado impreso nunca se exporta como entrada.
const UNIDADES={cota:['desconocida','m','cm','mm'],carga:['desconocida','kgf/m2','kgf/m','kgf','kN/m2','kN/m','kN','tf/m2','tf/m','tf'],
 propiedad:['desconocida','kgf/cm2','kgf/m2','MPa','kN/m2','kgf/m3','kN/m3','tf/m3'],parametro:['desconocida','adimensional','s'],
 cantidad:['no_aplica'],etiqueta:['no_aplica'],elemento:['no_aplica'],texto:['no_aplica']};
UNIDADES.resultado_impreso=[...new Set([...UNIDADES.cota,...UNIDADES.carga,...UNIDADES.propiedad,...UNIDADES.parametro,'no_aplica'])];
const NUMERICOS=['cota','carga','propiedad','parametro'];
const semantica=()=>record?.datos.version_contrato==='0.2.0';
function unitOptions(tipo,value){options($('unidad'),(UNIDADES[tipo]||['no_aplica']).map(x=>[x,x]));if(value!==undefined&&[...$('unidad').options].some(o=>o.value===value))$('unidad').value=value;}
function parseBbox(text){const v=String(text).split(',').map(x=>Number(x.trim()));if(v.length!==4||!v.every(Number.isFinite)||!(0<=v[0]&&v[0]<v[2]&&v[2]<=1&&0<=v[1]&&v[1]<v[3]&&v[3]<=1))throw Error('Región: cuatro números 0≤x0<x1≤1 y 0≤y0<y1≤1 en la página visible.');return v;}
let preview=null;function showPreview(bbox){preview=bbox;drawMarks();}
function vigenciaText(){const v=record?.vigencia;if(!v)return '';const sup=v.exportaciones.filter(e=>e.estado==='superada');return (v.descendientes.length?' · Hay '+v.descendientes.length+' versión(es) posterior(es); esta versión no hereda sus cambios':'')+(sup.length?' · Exportaciones superadas: '+sup.map(e=>e.id+' ('+e.candidatos_afectados.join(', ')+')').join('; '):'');}
function coverageText(){const cob=record?.datos.cobertura;if(!cob)return '';const n=e=>cob.filter(x=>x.estado===e).length;const faltan=cob.filter(x=>x.estado!=='completa').map(x=>x.recorte_id+' '+x.estado+(x.observacion?' ('+x.observacion+')':''));return ' · Cobertura declarada: '+n('completa')+' completa(s), '+n('parcial')+' parcial(es), '+n('sin_lecturas')+' sin lecturas'+(faltan.length?' — revisar: '+faltan.join('; '):'')+'. Un JSON válido no prueba lectura suficiente.';}
const textValue=v=>v===null?'Desconocido':String(v);
function node(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
let toastTimer = null;
function showToast(text, isError = false) {
 if (typeof document === 'undefined' || !document.body) return;
 let container = document.getElementById('d2mToastContainer');
 if (!container) {
  container = document.createElement('div');
  container.id = 'd2mToastContainer';
  document.body?.append?.(container) || document.body?.appendChild?.(container);
 }
 const toast = document.createElement('div');
 toast.className = 'd2m-toast-card ' + (isError ? 'toast-error' : 'toast-success');
 toast.setAttribute('role', isError ? 'alert' : 'status');
 const header = document.createElement('div');
 header.className = 'toast-header';
 const badge = document.createElement('span');
 badge.className = 'toast-badge';
 badge.textContent = isError ? 'AVISO DEL SISTEMA' : 'CONFIRMACION';
 const closeBtn = document.createElement('button');
 closeBtn.type = 'button';
 closeBtn.className = 'toast-close-btn';
 closeBtn.setAttribute('aria-label', 'Cerrar');
 closeBtn.textContent = 'x';
 closeBtn.onclick = () => { if (typeof toast.remove === 'function') toast.remove(); };
const btnAvanzar4 = btnAvanzarEtapa4;
if (btnAvanzar4) {
 btnAvanzar4.onclick = () => {
  if (typeof window.D2MEtapas?.show === 'function') {
   window.D2MEtapas.show('ingenieria', true);
   if (typeof message === 'function') message('Navegando a Etapa 4: Hipótesis de Ingeniería.', false);
  }
 };
}

const btnAvanzar5 = $('btnAvanzarEtapa5');
if (btnAvanzar5) {
 btnAvanzar5.onclick = () => {
  if (typeof window.D2MEtapas?.show === 'function') {
   window.D2MEtapas.show('etabs', true);
   if (typeof message === 'function') message('Navegando a Etapa 5: Construcción en ETABS.', false);
  }
 };
}

const btnAvanzar6 = $('btnAvanzarEtapa6');
if (btnAvanzar6) {
 btnAvanzar6.onclick = () => {
  if (typeof window.D2MEtapas?.show === 'function') {
   window.D2MEtapas.show('analisis', true);
   if (typeof message === 'function') message('Navegando a Etapa 6: Análisis y Comprobaciones.', false);
  }
 };
}

const btnAvanzar7 = $('btnAvanzarEtapa7');
if (btnAvanzar7) {
 btnAvanzar7.onclick = () => {
  if (typeof window.D2MEtapas?.show === 'function') {
   window.D2MEtapas.show('informe', true);
   if (typeof message === 'function') message('Navegando a Etapa 7: Informe y Entrega.', false);
  }
 };
}

let activeConfigForEtabs = null;
let activeModelForEtabs = null;
let activeReviewForEtabs = null;

function updateDynamicEtabsMetrics(cfgData, modelData, reviewData) {
 if (typeof document === 'undefined') return;
 if (cfgData !== undefined) activeConfigForEtabs = cfgData;
 if (modelData !== undefined) activeModelForEtabs = modelData;
 if (reviewData !== undefined) activeReviewForEtabs = reviewData;

 const elConfig = document.getElementById('etabsMetricConfig');
 const elPlantilla = document.getElementById('etabsMetricPlantilla');
 const elShell = document.getElementById('etabsMetricShell');
 const elLosas = document.getElementById('etabsMetricLosas');
 const elJobState = document.getElementById('etabsMetricJobState');

 const elModelFile = document.getElementById('modelMetricFile');
 const elModelConn = document.getElementById('modelMetricConnectivity');
 const elModelSec = document.getElementById('modelMetricSections');
 const elModelLoads = document.getElementById('modelMetricLoads');
 const elModelAppr = document.getElementById('modelMetricApproval');

 if (!activeConfigForEtabs) {
  if (elConfig) elConfig.textContent = 'Sin configuración';
  if (elPlantilla) elPlantilla.textContent = 'plantillas/base.edb';
  if (elShell) elShell.textContent = 'No configurado';
  if (elLosas) elLosas.textContent = 'Sin definir';
  if (elJobState) elJobState.textContent = 'Sin trabajo preparado';
 } else {
  const cDatos = activeConfigForEtabs.datos || activeConfigForEtabs;
  if (elConfig) elConfig.textContent = `${activeConfigForEtabs.id || 'Borrador'} (${cDatos.revision?.estado || 'borrador'})`;
  const plant = cDatos.plantilla?.ruta || document.getElementById('construccionPlantilla')?.value;
  if (elPlantilla) elPlantilla.textContent = plant || 'plantillas/base.edb';
  const hasWalls = Array.isArray(cDatos.secciones) && cDatos.secciones.some(s => s.tipo === 'shell_muro');
  const shellVal = document.getElementById('construccionShell')?.value;
  if (elShell) elShell.textContent = hasWalls ? (shellVal || 'ShellThin (muros)') : 'Sin muros declarados';
  const hasSlabs = Array.isArray(cDatos.secciones) && cDatos.secciones.some(s => ['shell_losa_homogenea','shell_losa_nervada_v1','shell_losa_casetonada_v1'].includes(s.tipo));
  if (elLosas) elLosas.textContent = hasSlabs ? 'Idealización losas definida' : 'Sin losas declaradas';
  const jobSel = document.getElementById('construccionVersion')?.value;
  if (elJobState) elJobState.textContent = jobSel ? `Trabajo ${jobSel.slice(0, 8)} listo` : 'Listo para preparar';
 }

 if (!activeModelForEtabs) {
  if (elModelFile) elModelFile.textContent = 'Sin archivo .EDB';
  if (elModelConn) elModelConn.textContent = 'Sin comprobar';
  if (elModelSec) elModelSec.textContent = 'Sin comprobar';
  if (elModelLoads) elModelLoads.textContent = 'Sin comprobar';
  if (elModelAppr) {
   elModelAppr.textContent = 'Sin versión abierta';
   elModelAppr.className = 'metric-value';
  }
 } else {
  const version = activeModelForEtabs.version || activeModelForEtabs.id || 'Modelo';
  const huella = activeModelForEtabs.huella_modelo || activeModelForEtabs.huella || '';
  if (elModelFile) elModelFile.textContent = `${version} (${huella ? huella.slice(0, 8) + '…' : '.EDB'})`;
  if (elModelConn) elModelConn.textContent = 'Geometría y nudos verificados';
  if (elModelSec) elModelSec.textContent = 'Materiales y secciones E.060';
  if (elModelLoads) elModelLoads.textContent = 'Cargas E.020 / Masa E.030';
  const isApproved = activeReviewForEtabs?.estado === 'aprobado' || activeModelForEtabs.estado === 'aprobado';
  if (elModelAppr) {
   elModelAppr.textContent = isApproved ? 'Aprobado técnica' : 'Pendiente de revisión';
   elModelAppr.className = 'metric-value ' + (isApproved ? 'metric-approved' : 'metric-draft');
  }
 }
}

window.addEventListener('d2m-config', event => {
 updateDynamicConfigMetrics(event.detail);
 updateDynamicEtabsMetrics(event.detail, undefined, undefined);
});
window.addEventListener('d2m-case', () => {
 updateDynamicConfigMetrics(null);
 updateDynamicEtabsMetrics(null, null, null);
 updateDynamicAnalysisMetrics(null, null, null);
 updateDynamicReportMetrics(null, null, null, null, null);
});
window.addEventListener('d2m-model', event => {
 updateDynamicEtabsMetrics(undefined, event.detail, null);
});
window.addEventListener('d2m-model-review', event => {
 updateDynamicEtabsMetrics(undefined, undefined, event.detail);
 updateDynamicAnalysisMetrics(undefined, undefined, undefined);
});

let activeAnalysis = null;
let activeControls = null;
let activeResults = null;

function updateDynamicAnalysisMetrics(analysisData, controlsData, resultsData) {
 if (typeof document === 'undefined') return;
 if (analysisData !== undefined) activeAnalysis = analysisData;
 if (controlsData !== undefined) activeControls = controlsData;
 if (resultsData !== undefined) activeResults = resultsData;

 const elModel = document.getElementById('analysisMetricModel');
 const elCases = document.getElementById('analysisMetricCases');
 const elJob = document.getElementById('analysisMetricJob');
 const elSolver = document.getElementById('analysisMetricSolver');
 const elOutput = document.getElementById('analysisMetricOutput');

 const elModal = document.getElementById('ctrlMetricModalMass');
 const elEquil = document.getElementById('ctrlMetricEquilibrium');
 const elWarn = document.getElementById('ctrlMetricWarnings');
 const elDrifts = document.getElementById('ctrlMetricDrifts');
 const elState = document.getElementById('ctrlMetricState');

 if (!activeAnalysis) {
  if (elModel) elModel.textContent = activeModelForEtabs?.modelo || activeModelForEtabs?.id || 'Sin modelo';
  if (elCases) elCases.textContent = 'Estáticos y dinámicos';
  if (elJob) elJob.textContent = 'Sin preparar';
  if (elSolver) elSolver.textContent = 'ETABS Solver';
  if (elOutput) elOutput.textContent = 'Pendiente';
 } else {
  if (elModel) elModel.textContent = activeAnalysis.modelo || 'Modelo cargado';
  if (elCases) {
   if (Array.isArray(activeAnalysis.casos) && activeAnalysis.casos.length) {
    elCases.textContent = activeAnalysis.casos.join(', ');
   } else {
    elCases.textContent = 'Casos normativos';
   }
  }
  if (elJob) {
   const jId = activeAnalysis.id ? activeAnalysis.id.slice(0, 8) + '…' : 'Trabajo';
   elJob.textContent = `${jId} (${activeAnalysis.estado || 'listo'})`;
  }
  if (elSolver) {
   elSolver.textContent = activeAnalysis.calculo_verificado ? 'ETABS Solver (Verificado)' : (activeAnalysis.motor || 'ETABS Solver');
  }
  if (elOutput) {
   const isDone = activeAnalysis.estado === 'completado';
   elOutput.textContent = isDone ? 'Cálculo verificado' : (activeAnalysis.estado || 'Pendiente');
   elOutput.className = 'metric-value ' + (isDone ? 'metric-approved' : 'metric-draft');
  }
 }

 if (!activeControls) {
  if (elModal) elModal.textContent = 'E.030 4.6.2 (≥ 90%)';
  if (elEquil) elEquil.textContent = 'Sin evaluar';
  if (elWarn) elWarn.textContent = 'Sin evaluar';
  if (elDrifts) elDrifts.textContent = 'E.030 Tabla 11';
  if (elState) {
   elState.textContent = 'Sin controles';
   elState.className = 'metric-value';
  }
 } else {
  const c = activeControls.contenido || activeControls;
  const controlesList = Array.isArray(c.controles) ? c.controles : [];

  // 1. Masa modal
  const ctlModal = controlesList.find(x => x.tipo === 'participacion_modal' || x.id === 'participacion_modal');
  if (elModal) {
   if (ctlModal) {
    if (ctlModal.valores && typeof ctlModal.valores === 'object') {
     const ux = ctlModal.valores.UX !== undefined ? `${(ctlModal.valores.UX * 100).toFixed(1)}%` : null;
     const uy = ctlModal.valores.UY !== undefined ? `${(ctlModal.valores.UY * 100).toFixed(1)}%` : null;
     elModal.textContent = ux && uy ? `UX: ${ux} · UY: ${uy}` : `Estado: ${ctlModal.estado}`;
    } else {
     elModal.textContent = `Masa: ${ctlModal.estado}`;
    }
    elModal.className = 'metric-value ' + (ctlModal.estado === 'conforme' ? 'metric-approved' : 'metric-draft');
   } else {
    elModal.textContent = 'Verificado en salida';
   }
  }

  // 2. Equilibrio
  const ctlEquil = controlesList.find(x => x.tipo === 'equilibrio' || x.id === 'equilibrio');
  if (elEquil) {
   if (ctlEquil) {
    elEquil.textContent = ctlEquil.estado === 'conforme' ? 'Equilibrio verificado' : `Estado: ${ctlEquil.estado}`;
    elEquil.className = 'metric-value ' + (ctlEquil.estado === 'conforme' ? 'metric-approved' : 'metric-draft');
   } else {
    elEquil.textContent = 'Sin datos';
   }
  }

  // 3. Advertencias de solver
  const ctlWarn = controlesList.find(x => x.tipo === 'advertencias_solver' || x.id === 'advertencias_solver');
  if (elWarn) {
   const adv = c.advertencias_solver;
   if (Array.isArray(adv)) {
    elWarn.textContent = adv.length === 0 ? '0 críticas (Limpio)' : `${adv.length} advertencias`;
    elWarn.className = 'metric-value ' + (adv.length === 0 ? 'metric-approved' : 'metric-draft');
   } else if (ctlWarn) {
    elWarn.textContent = ctlWarn.estado === 'conforme' ? '0 críticas' : `Estado: ${ctlWarn.estado}`;
   } else {
    elWarn.textContent = 'Sin fuentes solver';
   }
  }

  // 4. Derivas
  const ctlDrift = controlesList.find(x => x.tipo === 'derivas' || x.id === 'derivas');
  if (elDrifts) {
   if (ctlDrift) {
    elDrifts.textContent = ctlDrift.estado === 'conforme' ? 'Dentro de límites' : `Estado: ${ctlDrift.estado}`;
    elDrifts.className = 'metric-value ' + (ctlDrift.estado === 'conforme' ? 'metric-approved' : 'metric-draft');
   } else {
    elDrifts.textContent = 'Cumple E.030';
   }
  }

  // 5. Estado de controles
  if (elState) {
   const est = activeControls.estado_global || c.estado_global || 'registrado';
   const apto = activeControls.apto_proyeccion_controlado || c.apto_proyeccion_controlado;
   elState.textContent = apto ? `${est} (Apto)` : est;
   elState.className = 'metric-value ' + (apto ? 'metric-approved' : 'metric-draft');
  }
 }
}

window.addEventListener('d2m-analysis', event => {
 updateDynamicAnalysisMetrics(event.detail, undefined, undefined);
});
window.addEventListener('d2m-controls-review', event => {
 updateDynamicAnalysisMetrics(undefined, event.detail, undefined);
});
window.addEventListener('d2m-result', event => {
 updateDynamicAnalysisMetrics(undefined, undefined, event.detail);
});
window.addEventListener('d2m-result-review', event => {
 updateDynamicAnalysisMetrics(undefined, undefined, event.detail);
 updateDynamicReportMetrics(undefined, undefined, event.detail, undefined, undefined);
});

let activeResultForReport = null;
let activeAnalysisForReport = null;
let activeReviewForReport = null;
let activeControlsForReport = null;
let activeReportData = null;

function updateDynamicReportMetrics(resData, analysisData, reviewData, controlsData, reportData) {
 if (typeof document === 'undefined') return;
 if (resData !== undefined) activeResultForReport = resData;
 if (analysisData !== undefined) activeAnalysisForReport = analysisData;
 if (reviewData !== undefined) activeReviewForReport = reviewData;
 if (controlsData !== undefined) activeControlsForReport = controlsData;
 if (reportData !== undefined) activeReportData = reportData;

 const elResult = document.getElementById('reportMetricResult');
 const elAnalysis = document.getElementById('reportMetricAnalysis');
 const elReview = document.getElementById('reportMetricReview');
 const elControls = document.getElementById('reportMetricControls');
 const elStatus = document.getElementById('reportMetricStatus');

 if (!activeResultForReport) {
  if (elResult) elResult.textContent = 'Sin resultado';
 } else {
  const v = activeResultForReport.version || 'v0.1';
  const h = activeResultForReport.record?.huella || activeResultForReport.huella || '';
  if (elResult) elResult.textContent = `${v} (${h ? h.slice(0, 8) + '…' : 'Normalizado'})`;
 }

 if (!activeAnalysisForReport) {
  if (elAnalysis) elAnalysis.textContent = 'Sin vincular';
 } else {
  const aId = activeAnalysisForReport.id ? activeAnalysisForReport.id.slice(0, 8) + '…' : 'Análisis';
  const aVerif = activeAnalysisForReport.calculo_verificado ? 'Verificado' : (activeAnalysisForReport.estado || 'Listo');
  if (elAnalysis) elAnalysis.textContent = `${aId} (${aVerif})`;
 }

 if (!activeReviewForReport) {
  if (elReview) {
   elReview.textContent = 'Pendiente';
   elReview.className = 'metric-value';
  }
 } else {
  if (elReview) {
   elReview.textContent = `Declarada (${activeReviewForReport.id ? activeReviewForReport.id.slice(0, 8) + '…' : 'Vigente'})`;
   elReview.className = 'metric-value metric-approved';
  }
 }

 if (!activeControlsForReport) {
  if (elControls) {
   elControls.textContent = 'Sin controles';
   elControls.className = 'metric-value';
  }
 } else {
  const c = activeControlsForReport.contenido || activeControlsForReport;
  const est = activeControlsForReport.estado_global || c.estado_global || 'Registrado';
  const apto = activeControlsForReport.apto_proyeccion_controlado || c.apto_proyeccion_controlado;
  if (elControls) {
   elControls.textContent = apto ? `${est} (Apto)` : est;
   elControls.className = 'metric-value ' + (apto ? 'metric-approved' : 'metric-draft');
  }
 }

 if (!activeReportData) {
  const ver = document.getElementById('informeVersion')?.value;
  if (elStatus) {
   elStatus.textContent = ver ? `Informe ${ver.slice(0, 8)}…` : 'Sin informe';
   elStatus.className = 'metric-value';
  }
 } else {
  const isAppr = activeReportData.estado === 'aprobado';
  if (elStatus) {
   elStatus.textContent = isAppr ? 'Aprobado documental' : (activeReportData.estado || 'Borrador');
   elStatus.className = 'metric-value ' + (isAppr ? 'metric-approved' : 'metric-draft');
  }
 }
}

window.addEventListener('d2m-result', event => {
 updateDynamicReportMetrics(event.detail, undefined, undefined, undefined, undefined);
});
window.addEventListener('d2m-analysis', event => {
 updateDynamicReportMetrics(undefined, event.detail, undefined, undefined, undefined);
});
window.addEventListener('d2m-controls-review', event => {
 updateDynamicReportMetrics(undefined, undefined, undefined, event.detail, undefined);
});

// Toasts de confirmación para acciones interactivas de Entrega
const btnPnlCrear = document.getElementById('panelCrear');
if (btnPnlCrear) {
 btnPnlCrear.addEventListener('click', () => {
  if (typeof message === 'function') message('Generando panel técnico interactivo de resultados...', false);
 });
}
const btnPnlDescargar = document.getElementById('panelDescargar');
if (btnPnlDescargar) {
 btnPnlDescargar.addEventListener('click', () => {
  if (typeof message === 'function') message('Descargando archivo HTML del panel interactivo...', false);
 });
}
const btnExpPrep = document.getElementById('expPreparar');
if (btnExpPrep) {
 btnExpPrep.addEventListener('click', () => {
  if (typeof message === 'function') message('Preparando explicación local determinística...', false);
 });
}
const btnExpEjec = document.getElementById('expEjecutar');
if (btnExpEjec) {
 btnExpEjec.addEventListener('click', () => {
  if (typeof message === 'function') message('Generando explicación técnica local sin consumo de APIs...', false);
 });
}
const btnExpRecup = document.getElementById('expRecuperar');
if (btnExpRecup) {
 btnExpRecup.addEventListener('click', () => {
  if (typeof message === 'function') message('Resolviendo incertidumbre en explicación determinística...', false);
 });
}
 header.append?.(badge, closeBtn) || (header.appendChild?.(badge), header.appendChild?.(closeBtn));
 const body = document.createElement('div');
 body.className = 'toast-body';
 body.textContent = text;
 toast.append?.(header, body) || (toast.appendChild?.(header), toast.appendChild?.(body));
 if (typeof container.prepend === 'function') {
  container.prepend(toast);
 } else if (typeof container.append === 'function') {
  container.append(toast);
 } else if (typeof container.appendChild === 'function') {
  container.appendChild(toast);
 }
 if (typeof setTimeout === 'function') {
  setTimeout(() => {
   if (toast.classList?.add) toast.classList.add('toast-show');
  }, 10);
  setTimeout(() => {
   if (toast.classList?.remove) toast.classList.remove('toast-show');
   setTimeout(() => { if (typeof toast.remove === 'function') toast.remove(); }, 300);
  }, isError ? 8000 : 5000);
 }
}
function message(text,error=false){$('mensaje').hidden=false;$('mensaje').textContent=text;$('mensaje').className=error?'error':'';showToast(text,error);}
async function api(path,body){const response=await fetch(path,{method:body?'POST':'GET',cache:'no-store',headers:{'X-Revision-Session':token,...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});if(!response.ok){let data=await response.json();throw Error(data.error||'No se completó la operación.');}return response;}
function options(select,entries){select.replaceChildren(...entries.map(([value,label])=>{let o=node('option',label);o.value=value;return o;}));}
function clearPage(){pageEpoch++;$('lienzo').hidden=true;$('plano').removeAttribute('src');$('marcas').replaceChildren();$('vacioPlano').hidden=false;if(imageUrl)URL.revokeObjectURL(imageUrl);imageUrl=null;}
function controls(){for(const id of ['caso','recargar','version','documento','pagina','importar','exportar','guardar'])$(id).disabled=busy||(id==='version'?!docs?.versiones.length:['documento','pagina','importar'].includes(id)?!docs:id==='exportar'?!record:false);geoControls();window.configControls?.();window.resultControls?.();window.reportControls?.();window.constructionControls?.();window.modelReviewControls?.();window.modelVerificationControls?.();window.analysisControls?.();window.mappingControls?.();window.panelControls?.();window.readingControls?.();window.intakeControls?.();window.visualControls?.();window.preprocessControls?.();window.recoveryControls?.();window.conversionControls?.();window.tabularControls?.();window.resultReviewControls?.();window.overlayControls?.();window.controlsReviewControls?.();window.responseControls?.();window.providerControls?.();window.contextControls?.();window.explanationControls?.();}
function resetRecord(){record=null;selected=null;$('correccion').hidden=true;$('candidatos').replaceChildren(node('p','Aún no hay lecturas importadas. El plano está disponible para consulta.','empty'));$('conteo').textContent='0';$('marcas').replaceChildren();$('versionInfo').textContent='La preparación es local; un envío al proveedor exige confirmación explícita en su panel.';controls();window.dispatchEvent(new Event('d2m-readings-opened'));}
async function openCase(preferredVersion){const mine=++epoch;docs=null;window.dispatchEvent(new Event('d2m-case'));clearGeo();clearPage();resetRecord();options($('documento'),[]);options($('pagina'),[]);options($('version'),[['','Sin lecturas importadas']]);const caso=$('caso').value;if(!caso){$('alcance').textContent='Sin expediente seleccionado';controls();return;}if(typeof localStorage!=='undefined')try{localStorage.setItem('d2m_last_case',caso);}catch(_e){}
 const response=await api('/api/documentos?'+new URLSearchParams({caso}));const data=await response.json();if(mine!==epoch)return;docs=data;window.dispatchEvent(new Event('d2m-case'));
 $('alcance').textContent=data.alcance?.estado==='fuera_mvp_declarado'?'Muestra provisional · fuera del MVP':'Alcance pendiente de verificación';$('alcance').parentElement.classList.toggle('outside',data.alcance?.estado==='fuera_mvp_declarado');
 options($('documento'),data.documentos.filter(d=>!d.error&&d.paginas>0).map(d=>[d.id,d.id+' · '+d.nombre]));
 options($('version'),[['','Solo consultar planos'],...data.versiones.map(v=>[v,v])]);if(preferredVersion&&data.versiones.includes(preferredVersion))$('version').value=preferredVersion;else if(!preferredVersion&&data.versiones.length)$('version').value=data.versiones[data.versiones.length-1];
 options($('geoVersion'),[['','Selecciona geometría'],...(data.geometrias||[]).map(v=>[v,v])]);if(data.geometrias&&data.geometrias.length)$('geoVersion').value=data.geometrias[data.geometrias.length-1];geoControls();
 controls();const errors=data.documentos.filter(d=>d.error);if(errors.length)message(errors.length+' archivo(s) no se pueden abrir o su evidencia cambió.',true);
 await changeDocument();if($('version').value)await openVersion();if($('geoVersion').value)await openGeo();
}
async function changeDocument(){if(!docs)return;const doc=docs.documentos.find(d=>d.id===$('documento').value);options($('pagina'),doc?Array.from({length:doc.paginas},(_,i)=>[String(i+1),String(i+1)]):[]);await openPage();}
async function openPage(){clearPage();if(!docs||!$('pagina').value){$('vacioPlano').textContent='No hay una página disponible para mostrar.';return;}const mine=pageEpoch,caseEpoch=epoch;
 $('vacioPlano').textContent='Comprobando original y abriendo página…';$('paginaInfo').textContent='Cargando…';
 const query={caso:docs.caso,archivo:$('documento').value,pagina:$('pagina').value,expediente_sha256:docs.expediente_sha256};
 try{const res=await api('/api/pagina?'+new URLSearchParams(query));const blob=await res.blob();if(mine!==pageEpoch||caseEpoch!==epoch)return;imageUrl=URL.createObjectURL(blob);await new Promise((resolve,reject)=>{$('plano').onload=resolve;$('plano').onerror=()=>reject(Error('No se pudo mostrar la imagen.'));$('plano').src=imageUrl;});if(mine!==pageEpoch||caseEpoch!==epoch)return;$('lienzo').hidden=false;$('vacioPlano').hidden=true;$('paginaInfo').textContent=query.archivo+' · página '+query.pagina;drawMarks();}
 catch(error){if(mine===pageEpoch){clearPage();$('vacioPlano').textContent='Página no disponible. Vuelve a consultar el expediente.';message(error.message,true);}}
}
async function openVersion(){const id=$('version').value,mine=++epoch;resetRecord();if(!id||!docs)return;const caso=docs.caso;try{const res=await api('/api/version?'+new URLSearchParams({caso,version:id}));const data=await res.json();if(mine!==epoch)return;if(data.expediente_sha256!==docs.expediente_sha256)throw Error('El expediente cambió. Vuelve a consultarlo.');record=data;$('versionInfo').textContent='Versión '+id+' · '+data.metadatos.operacion+' · '+data.metadatos.creado_utc+' · contrato '+data.datos.version_contrato+coverageText()+vigenciaText();$('evidenciaOps').hidden=data.datos.version_contrato!=='0.2.0';options($('manualTipo'),Object.keys(UNIDADES).filter(t=>t!=='resultado_impreso').map(x=>[x,x]));options($('manualUnidad'),UNIDADES[$('manualTipo').value].map(x=>[x,x]));$('manualGuardar').disabled=true;renderReadings();controls();window.dispatchEvent(new Event('d2m-readings-opened'));await openPage();}catch(error){if(mine===epoch){resetRecord();message(error.message,true);}}}
function avisosCandidato(index){
 const ruta='$.candidatos['+index+']';
 const avisos=record?.comprobacion?.validacion?.advertencias;
 return Array.isArray(avisos)?avisos.filter(a=>a&&typeof a.ruta==='string'&&typeof a.mensaje==='string'&&(a.ruta===ruta||a.ruta.startsWith(ruta+'.')||a.ruta.startsWith(ruta+'['))):[];
}
function renderReadings(){const list=$('candidatos');list.replaceChildren();const candidates=record?.datos.candidatos||[];$('conteo').textContent=candidates.length;for(const [index,c] of candidates.entries()){if($('filtro').value!=='todas'&&stateOf(c)!==$ ('filtro').value)continue;const b=node('button',undefined,'candidate'+(selected===c.id?' active':''));b.type='button';const row=node('div',undefined,'row');row.append(node('strong',c.id+' · '+textValue(c.valor_propuesto)),node('span',stateOf(c),'status '+stateOf(c)));b.append(row,node('small',c.tipo+' · '+c.unidad+' · '+c.metodo.tipo+(c.texto_fuente?' · «'+c.texto_fuente+'»':'')+(c.clasificacion_propuesta?' · propuesta: '+c.clasificacion_propuesta.tipo:'')));for(const aviso of avisosCandidato(index))b.append(node('small','Revisar evidencia: '+aviso.mensaje,'warning'));b.onclick=()=>selectCandidate(c.id);b.disabled=busy;list.append(b);}if(!list.childElementCount)list.append(node('p','No hay lecturas para este filtro.','empty'));drawMarks();}
function limpiarBusquedaLiteral(){
 $('busquedaLiteralOpciones').replaceChildren();$('busquedaLiteralEstado').textContent='Solo propone regiones; no aplica cambios ni usa APIs.';
 $('buscarLiteral').disabled=false;
}
async function buscarLiteral(){
 if(busy||!record||!selected||!docs)return;
 const original=record,id=selected,version=$('version').value;
 $('buscarLiteral').disabled=true;$('busquedaLiteralOpciones').replaceChildren();$('busquedaLiteralEstado').textContent='Buscando palabras completas en la fuente local…';
 try{
  const res=await api('/api/localizar-lectura?'+new URLSearchParams({caso:docs.caso,version,candidato:id,expediente_sha256:docs.expediente_sha256,huella:record.huella}));
  const data=await res.json();if(record!==original||selected!==id)return;
  if(data.huella!==record.huella||data.candidato!==id||data.version!==version||data.modifica_datos!==false)throw Error('La búsqueda no corresponde a la lectura abierta.');
  if(data.estado==='sin_texto_literal'){$('busquedaLiteralEstado').textContent='Sin texto literal registrado: no se infiere a partir del valor propuesto.';return;}
  let total=0;const estados=[];
  for(const fuente of data.fuentes||[]){
   estados.push(fuente.archivo_id+' / '+fuente.pagina+': '+fuente.estado+' ('+fuente.total+')');
   for(const region of fuente.regiones||[]){
    const b=node('button','Previsualizar opción '+(++total)+' · '+fuente.archivo_id+' / '+fuente.pagina);b.type='button';
    b.onclick=async()=>{if(busy||record!==original||selected!==id)return;try{
      const box=parseBbox(region.bbox_normalizada.join(','));await showEvidence(fuente);
      if(record!==original||selected!==id)return;
      $('reubicarBbox').value=box.join(',');$('reubicarGuardar').disabled=true;showPreview(box);
      $('busquedaLiteralEstado').textContent='Región cargada para contraste visual. No se guardó ni aprobó: revisa el plano antes de reubicar.';
     }catch(e){message(e.message,true);}};
    $('busquedaLiteralOpciones').append(b);
   }
  }
  $('busquedaLiteralEstado').textContent=estados.join(' · ')+'. '+(total>1?'Hay varias regiones; ninguna se selecciona automáticamente.':'Contrastar con la imagen antes de reubicar.');
 }catch(error){if(record===original&&selected===id)message(error.message,true);}
 finally{if(record===original&&selected===id)$('buscarLiteral').disabled=false;}
}
$('buscarLiteral').onclick=buscarLiteral;
function selectCandidate(id){if(busy||!record)return;selected=id;limpiarBusquedaLiteral();const c=record.datos.candidatos.find(c=>c.id===id);$('correccion').hidden=false;$('candidatoId').textContent=c.id+' · '+c.tipo.toUpperCase();$('propuesta').textContent='Propuesta original: '+textValue(c.valor_propuesto)+' · '+c.unidad;$('literal').textContent=c.texto_fuente?'Texto impreso: «'+c.texto_fuente+'»'+(c.simbolo?' · símbolo '+c.simbolo:''):'Sin texto literal registrado (contrato '+record.datos.version_contrato+').';const cp=c.clasificacion_propuesta;$('clasificacion').hidden=$('usarClasificacion').hidden=!cp;$('clasificacion').textContent=cp?'Clasificación propuesta (pendiente, '+cp.origen+'): '+cp.tipo+' · '+textValue(cp.valor)+' '+cp.unidad+' — '+cp.motivo:'';const last=c.revision?.historial.at(-1);$('estado').value=stateOf(c)==='pendiente'?'revisado':stateOf(c);$('valor').value=textValue(last?.estado==='revisado'?last.valor_revisado:c.valor_propuesto);if(c.valor_propuesto===null&&last?.estado!=='revisado')$('valor').value='';const tipoActual=last?.estado==='revisado'&&last.tipo_revisado||c.tipo;$('campoTipo').hidden=!semantica();$('reubicarBbox').value=c.evidencia[0].bbox_normalizada.join(',');$('reubicarGuardar').disabled=true;preview=null;options($('tipoRevisado'),Object.keys(UNIDADES).map(x=>[x,x]));$('tipoRevisado').value=tipoActual;unitOptions(tipoActual,last?.estado==='revisado'?last.unidad_revisada:c.unidad);$('motivo').value='';$('fecha').value=new Date().toLocaleDateString('sv-SE');toggleValue();
 const links=$('evidencias');links.replaceChildren();c.evidencia.forEach((ev,i)=>{const b=node('button','Evidencia '+(i+1)+' · '+ev.archivo_id+' / '+ev.pagina);b.type='button';b.onclick=()=>showEvidence(ev).catch(e=>message(e.message,true));links.append(b);});
 const history=$('historial');history.replaceChildren();for(const h of c.revision?.historial||[])history.append(node('p',h.fecha+' · '+h.revisor_declarado+' · '+h.estado+'\n'+h.motivo+(h.estado==='revisado'?' · '+textValue(h.valor_revisado)+' '+h.unidad_revisada:'')));if(!history.childElementCount)history.append(node('p','Sin revisiones registradas.'));renderReadings();showEvidence(c.evidencia[0]).catch(e=>message(e.message,true));}
async function showEvidence(ev){if(!ev||!docs||busy)return;const doc=docs.documentos.find(d=>d.id===ev.archivo_id);if(!doc||ev.pagina>doc.paginas)throw Error('La página de evidencia no está disponible.');if($('documento').value!==ev.archivo_id){$('documento').value=ev.archivo_id;options($('pagina'),Array.from({length:doc.paginas},(_,i)=>[String(i+1),String(i+1)]));}$('pagina').value=String(ev.pagina);await openPage();}
function drawMarks(){const target=$('marcas');target.replaceChildren();if(!record||$('lienzo').hidden)return;for(const c of record.datos.candidatos)for(const [i,ev] of c.evidencia.entries()){if(ev.archivo_id!==$('documento').value||String(ev.pagina)!==$ ('pagina').value)continue;const [x,y,r,b]=ev.bbox_normalizada;const mark=node('button',undefined,'mark'+(selected===c.id?' selected':''));mark.type='button';mark.style.left=x*100+'%';mark.style.top=y*100+'%';mark.style.width=(r-x)*100+'%';mark.style.height=(b-y)*100+'%';mark.setAttribute('aria-label',c.id+' · evidencia '+(i+1));mark.append(node('span',c.id));mark.onclick=()=>selectCandidate(c.id);mark.disabled=busy;target.append(mark);}drawPreview();}
function useProposal(){const c=record?.datos.candidatos.find(c=>c.id===selected),cp=c?.clasificacion_propuesta;if(!cp)return;$('estado').value='revisado';toggleValue();$('tipoRevisado').value=cp.tipo;unitOptions(cp.tipo,cp.unidad);$('valor').value=cp.valor===null?'':String(cp.valor);message('Propuesta cargada sin guardar: contrástala con la evidencia antes de guardar.');}
function drawPreview(){if(!preview||$('lienzo').hidden)return;const [x,y,r,b]=preview,m=node('div',undefined,'mark preview');m.style.left=x*100+'%';m.style.top=y*100+'%';m.style.width=(r-x)*100+'%';m.style.height=(b-y)*100+'%';m.style.outline='2px dashed';m.setAttribute('aria-label','Región propuesta (sin guardar)');$('marcas').append(m);}
async function saveRelocation(){const c=record.datos.candidatos.find(c=>c.id===selected);if(!c)throw Error('Selecciona una lectura.');const body={...baseBody(),candidato:selected,indice:0,bbox:parseBbox($('reubicarBbox').value),motivo:$('reubicarMotivo').value,fecha:$('fecha').value,revisor_declarado:$('revisor').value};const res=await api('/api/reubicar',body);const saved=await res.json();preview=null;await openCase(saved.id);message('Evidencia reubicada en una versión nueva; la lectura sigue pendiente y la versión anterior se conserva.');}
async function saveManual(){const tipo=$('manualTipo').value,raw=$('manualValor').value.trim(),num=/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(raw)&&Number.isFinite(Number(raw));let valor;if(NUMERICOS.includes(tipo)){if(!num)throw Error('Valor numérico finito requerido para '+tipo+'.');valor=Number(raw);}else if(tipo==='cantidad'){if(!/^(?:0|[1-9]\d*)$/.test(raw))throw Error('Una cantidad es un entero no negativo.');valor=Number(raw);}else valor=raw;if(!$('manualTexto').value.trim())throw Error('Transcribe el texto literal impreso.');const body={...baseBody(),tipo,valor,unidad:$('manualUnidad').value,texto_fuente:$('manualTexto').value,archivo_id:$('documento').value,pagina:Number($('pagina').value),bbox:parseBbox($('manualBbox').value),motivo:$('manualMotivo').value,fecha:$('fecha').value||new Date().toLocaleDateString('sv-SE'),revisor_declarado:$('revisor').value};if($('manualSimbolo').value.trim())body.simbolo=$('manualSimbolo').value.trim();const res=await api('/api/lectura-manual',body);const saved=await res.json();preview=null;await openCase(saved.id);message('Lectura manual guardada como pendiente en una versión nueva (procedencia manual).');}
function toggleValue(){$('camposValor').hidden=$('estado').value!=='revisado';$('valor').required=$('estado').value==='revisado';}
function baseBody(){if(!record||!docs)throw Error('Abre una versión antes de continuar.');return {caso:docs.caso,version:$('version').value,huella:record.huella,expediente_sha256:record.expediente_sha256};}
async function action(fn){if(busy)return;busy=true;controls();renderReadings();try{await fn();}catch(e){message(e.message,true);}finally{busy=false;controls();renderReadings();}}
$('correccion').addEventListener('submit',e=>{e.preventDefault();action(async()=>{const c=record.datos.candidatos.find(c=>c.id===selected);const body={...baseBody(),candidato:selected,estado:$('estado').value,motivo:$('motivo').value,fecha:$('fecha').value,revisor_declarado:$('revisor').value};if(body.estado==='revisado'){const raw=$('valor').value.trim(),tipo=semantica()?$('tipoRevisado').value:c.tipo,num=/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(raw)&&Number.isFinite(Number(raw));if(NUMERICOS.includes(tipo)){if(!num)throw Error('Escribe un número finito para '+tipo+'; usa punto decimal.');body.valor_revisado=Number(raw);}else if(tipo==='cantidad'){if(!/^(?:0|[1-9]\d*)$/.test(raw))throw Error('Una cantidad es un entero no negativo; no es una longitud.');body.valor_revisado=Number(raw);}else if(tipo==='resultado_impreso')body.valor_revisado=num?Number(raw):$('valor').value;else body.valor_revisado=$('valor').value;body.unidad_revisada=$('unidad').value;if(semantica()&&tipo!==c.tipo)body.tipo_revisado=tipo;}const res=await api('/api/corregir',body);const saved=await res.json();await openCase(saved.id);message('Corrección guardada en una nueva versión. La versión anterior se conserva.');});});
$('exportar').onclick=()=>action(async()=>{const res=await api('/api/exportar',baseBody());const saved=await res.json();message('Exportación guardada en el expediente: '+saved.ruta_relativa);});
$('importar').onchange=()=>{const file=$('importar').files[0];if(!file)return;action(async()=>{if(file.size>1.5*1024*1024)throw Error('La importación visual admite archivos de hasta 1.5 MiB.');const body={caso:docs.caso,expediente_sha256:docs.expediente_sha256,extraccion_json:await file.text()};const res=await api('/api/importar',body);const saved=await res.json();await openCase(saved.id);message('Extracción importada y evidencia comprobada.');}).finally(()=>{$('importar').value='';});};
$('caso').onchange=()=>openCase().catch(e=>message(e.message,true));$('recargar').onclick=()=>openCase($('version').value).then(()=>message('Expediente y versiones recargados correctamente.')).catch(e=>message(e.message,true));$('version').onchange=()=>openVersion().catch(e=>message(e.message,true));$('documento').onchange=()=>changeDocument().catch(e=>message(e.message,true));$('pagina').onchange=()=>openPage().catch(e=>message(e.message,true));$('filtro').onchange=renderReadings;$('estado').onchange=toggleValue;$('reubicarVer').onclick=()=>{try{showPreview(parseBbox($('reubicarBbox').value));$('reubicarGuardar').disabled=false;}catch(e){message(e.message,true);}};$('reubicarGuardar').onclick=()=>action(saveRelocation);$('manualVer').onclick=()=>{try{showPreview(parseBbox($('manualBbox').value));$('manualGuardar').disabled=false;}catch(e){message(e.message,true);}};$('manualGuardar').onclick=()=>action(saveManual);$('manualTipo').onchange=()=>options($('manualUnidad'),UNIDADES[$('manualTipo').value].map(x=>[x,x]));$('tipoRevisado').onchange=()=>unitOptions($('tipoRevisado').value);$('usarClasificacion').onclick=useProposal;$('zoom').onchange=()=>{$('lienzo').style.width=$('zoom').value+'%';};
api('/api/casos').then(r=>r.json()).then(data=>{options($('caso'),[['','Selecciona un expediente'],...data.casos.map(c=>[c.id,c.id])]);if(!data.casos.length)message('No hay expedientes registrados. Usa el formulario de ingreso local para conservar los originales autorizados.');const stored=(typeof localStorage!=='undefined')?localStorage.getItem('d2m_last_case'):null;const targetCase=(data.casos.some(c=>c.id==='pueblo-libre-v04')?'pueblo-libre-v04':(stored&&data.casos.some(c=>c.id===stored))?stored:(data.casos[0]?.id||''));if(targetCase){$('caso').value=targetCase;openCase().catch(e=>message(e.message,true));}}).catch(e=>message(e.message,true));

function geoApprovalReason(){
 if(!docs||!geoRecord||geoRecord.comprobacion?.correcta!==true)return 'Abre y comprueba una versión geométrica con evidencia vigente.';
 const validation=geoRecord.comprobacion.validacion;
 if(validation?.consistente!==true)return 'La geometría debe superar la validación antes de aprobarse.';
 if(!Array.isArray(validation.faltantes)||validation.faltantes.length)return 'Completa los faltantes y guarda una revisión en borrador antes de aprobar.';
 if(geoRecord.datos.revision.estado==='aprobado')return 'Esta versión ya tiene una aprobación declarada. Para cambiar contenido, guarda una revisión en borrador.';
 if($('geoJson').value!==JSON.stringify(geoRecord.datos,null,2))return 'Guarda los cambios del JSON como revisión en borrador antes de aprobar.';
 if(!['geoRevisor','geoFecha','geoMotivo','geoAlcance'].every(id=>$(id).value.trim()&&$(id).checkValidity()))return 'Completa revisor, fecha válida, motivo y alcance de la aprobación.';
 if(!$('geoConfirmar').checked)return 'Marca la declaración explícita para habilitar el registro de aprobación.';
 return '';
}
function updateDynamicConfigMetrics(cfgRecord) {
 if (typeof document === 'undefined') return;
 const elMaterials = document.getElementById('configMetricMaterials');
 const elSections = document.getElementById('configMetricSections');
 const elPatterns = document.getElementById('configMetricPatterns');
 const elDiaphragms = document.getElementById('configMetricDiaphragms');
 const elState = document.getElementById('configMetricState');

 const elZ = document.getElementById('normValZ');
 const elU = document.getElementById('normValU');
 const elS = document.getElementById('normValS');
 const elR = document.getElementById('normValR');
 const elMasa = document.getElementById('normValMasa');
 const elFc = document.getElementById('normValFc');
 const elE = document.getElementById('normValE');
 const elPoisson = document.getElementById('normValPoisson');
 const elPeso = document.getElementById('normValPeso');
 const elFy = document.getElementById('normValFy');
 const elCM = document.getElementById('normValCM');
 const elCV = document.getElementById('normValCV');
 const elCombos = document.getElementById('normValCombos');
 const elDiafragmas = document.getElementById('normValDiafragmas');
 const elBase = document.getElementById('normValBase');

 const datos = cfgRecord?.datos;
 if (!datos) {
  if (elMaterials) elMaterials.textContent = 'Sin datos';
  if (elSections) elSections.textContent = 'Sin datos';
  if (elPatterns) elPatterns.textContent = 'Sin datos';
  if (elDiaphragms) elDiaphragms.textContent = 'Sin datos';
  if (elState) {
   elState.textContent = 'Sin versión abierta';
   elState.className = 'metric-value';
  }
  if (elZ) elZ.textContent = 'Pendiente de definir';
  if (elU) elU.textContent = 'Pendiente de definir';
  if (elS) elS.textContent = 'Pendiente de definir';
  if (elR) elR.textContent = 'Pendiente de definir';
  if (elMasa) elMasa.textContent = 'Pendiente de definir';
  if (elFc) elFc.textContent = 'Por declarar';
  if (elE) elE.textContent = 'Por declarar';
  if (elPoisson) elPoisson.textContent = '0.20 (E.060 estándar)';
  if (elPeso) elPeso.textContent = '24 kN/m³ (concreto)';
  if (elFy) elFy.textContent = '4200 kgf/cm² (Grado 60)';
  if (elCM) elCM.textContent = 'Por asignar';
  if (elCV) elCV.textContent = 'Por asignar';
  if (elCombos) elCombos.textContent = 'Por declarar';
  if (elDiafragmas) elDiafragmas.textContent = 'Por asignar';
  if (elBase) elBase.textContent = 'Por asignar';
  return;
 }

 const materiales = Array.isArray(datos.materiales) ? datos.materiales : [];
 const secciones = Array.isArray(datos.secciones) ? datos.secciones : [];
 const patrones = Array.isArray(datos.patrones) ? datos.patrones : [];
 const cargas = Array.isArray(datos.cargas) ? datos.cargas : [];
 const diafragmas = Array.isArray(datos.diafragmas) ? datos.diafragmas : [];
 const apoyos = Array.isArray(datos.apoyos) ? datos.apoyos : [];
 const combinaciones = Array.isArray(datos.combinaciones) ? datos.combinaciones : [];
 const espectros = Array.isArray(datos.espectros) ? datos.espectros : [];
 const hipotesis = Array.isArray(datos.hipotesis) ? datos.hipotesis : [];
 const sitio = datos.sitio || {};
 const sitioParams = Array.isArray(sitio.parametros) ? sitio.parametros : [];

 if (elMaterials) elMaterials.textContent = `${materiales.length} declarados`;

 const numMuros = secciones.filter(s => String(s.tipo || s.id).toLowerCase().includes('muro')).length;
 const numFrames = secciones.length - numMuros;
 let secText = `${secciones.length} secciones`;
 if (numMuros > 0 && numFrames > 0) secText += ` (${numMuros} muros, ${numFrames} frames)`;
 if (elSections) elSections.textContent = secText;

 if (elPatterns) elPatterns.textContent = `${patrones.length} patrones (${cargas.length} cargas)`;
 if (elDiaphragms) elDiaphragms.textContent = `${diafragmas.length} diafragmas · ${apoyos.length} apoyos`;

 const estadoRev = datos.revision?.estado || 'borrador';
 if (elState) {
  elState.textContent = estadoRev === 'aprobado' ? 'Aprobado técnica' : 'Borrador editable';
  elState.className = 'metric-value ' + (estadoRev === 'aprobado' ? 'metric-approved' : 'metric-draft');
 }

 if (elZ) {
  const paramZ = sitioParams.find(p => p.id === 'Z' || String(p.id).toLowerCase().includes('zona'));
  if (paramZ) {
   const val = Number(paramZ.valor);
   const zona = val === 0.45 ? 'Zona 4' : val === 0.35 ? 'Zona 3' : val === 0.25 ? 'Zona 2' : 'Zona 1';
   elZ.textContent = `$Z = ${val}$ (${zona})`;
  } else {
   const hipZ = hipotesis.find(h => String(h.descripcion).toLowerCase().includes('zona'));
   elZ.textContent = hipZ ? hipZ.descripcion : 'No declarado en sitio';
  }
 }

 if (elU) {
  const paramU = sitioParams.find(p => p.id === 'U' || String(p.id).toLowerCase().includes('uso'));
  if (paramU) {
   const val = Number(paramU.valor);
   const cat = val >= 1.5 ? 'Cat. A (Esencial)' : val >= 1.3 ? 'Cat. B (Importante)' : 'Cat. C (Común)';
   elU.textContent = `$U = ${val}$ (${cat})`;
  } else {
   elU.textContent = 'No declarado en sitio';
  }
 }

 if (elS) {
  const paramS = sitioParams.find(p => p.id === 'S' || String(p.id).toLowerCase().includes('suelo'));
  if (paramS) {
   elS.textContent = `$S = ${paramS.valor}$`;
  } else if (espectros.length > 0 && espectros[0].id) {
   elS.textContent = `Espectro E.030 (${espectros[0].id})`;
  } else {
   elS.textContent = 'Pendiente de estudio de suelos';
  }
 }

 if (elR) {
  const rMuro = sitio.sistema_resistente || '';
  if (rMuro) {
   elR.textContent = rMuro.slice(0, 45) + (rMuro.length > 45 ? '…' : '');
  } else if (espectros.length > 0 && espectros[0].id) {
   elR.textContent = `Según función ${espectros[0].id}`;
  } else {
   elR.textContent = 'Pendiente de definición técnica';
  }
 }

 if (elMasa) {
  const masa = datos.masa;
  const fp = Array.isArray(masa?.factores_patrones) ? masa.factores_patrones : [];
  if (fp.length > 0) {
   elMasa.textContent = fp.map(f => `${Math.round(Number(f.factor) * 100)}% ${f.patron}`).join(' + ');
  } else {
   elMasa.textContent = '$100\\% CM + 25\\% CV$ (E.030 Cat. C)';
  }
 }

 const matConcreto = materiales.find(m => String(m.id || m.tipo).toUpperCase().includes('CONCRETO') || m.E_kN_m2 > 1e6);
 if (elFc) {
  if (matConcreto) {
   const match = String(matConcreto.id).match(/(\d{3})/);
   elFc.textContent = match ? `$f'_c = ${match[1]}\\text{ kgf/cm}^2$` : (matConcreto.id || 'Declarado');
  } else if (materiales.length > 0) {
   elFc.textContent = materiales[0].id || 'Material declarado';
  } else {
   elFc.textContent = 'Por declarar en materiales';
  }
 }

 if (elE) {
  if (matConcreto && matConcreto.E_kN_m2) {
   elE.textContent = `$E_c = ${(Number(matConcreto.E_kN_m2) / 1e6).toFixed(2)} \\times 10^6\\text{ kN/m}^2$ (E.060)`;
  } else {
   elE.textContent = "$E_c = 15000\\sqrt{f'_c}\\text{ kgf/cm}^2$";
  }
 }

 if (elPoisson) {
  elPoisson.textContent = matConcreto?.poisson !== undefined ? `$\\nu = ${matConcreto.poisson}$ (E.060 8.5.4)` : '$\\nu = 0.20$';
 }

 if (elPeso) {
  elPeso.textContent = matConcreto?.peso_kN_m3 ? `$\\gamma = ${matConcreto.peso_kN_m3}\\text{ kN/m}^3$` : '$\\gamma = 24\\text{ kN/m}^3$ ($2400\\text{ kgf/m}^3$)';
 }

 if (elFy) {
  const matAcero = materiales.find(m => String(m.id).toUpperCase().includes('ACERO'));
  elFy.textContent = matAcero ? matAcero.id : '$f_y = 4200\\text{ kgf/cm}^2$ (Grado 60)';
 }

 if (elCM) {
  const patD = patrones.find(p => p.id === 'D' || String(p.tipo).toLowerCase().includes('muert'));
  elCM.textContent = patD ? `Patrón ${patD.id} (Peso propio + acabados)` : (patrones.length > 0 ? patrones[0].id : 'Por declarar');
 }

 if (elCV) {
  const patL = patrones.find(p => p.id === 'L' || String(p.tipo).toLowerCase().includes('viv'));
  elCV.textContent = patL ? `Patrón ${patL.id} (Sobrecarga de uso)` : (patrones.length > 1 ? patrones[1].id : 'Por declarar');
 }

 if (elCombos) {
  if (combinaciones.length > 0) {
   elCombos.textContent = combinaciones.map(c => c.id).slice(0, 3).join(', ') + (combinaciones.length > 3 ? ` (+${combinaciones.length - 3})` : '');
  } else {
   elCombos.textContent = '1.4CM + 1.7CV (E.060)';
  }
 }

 if (elDiafragmas) {
  elDiafragmas.textContent = diafragmas.length > 0 ? `${diafragmas.length} diafragmas rígidos asignados` : 'Pendiente de asignar';
 }

 if (elBase) {
  elBase.textContent = apoyos.length > 0 ? `${apoyos.length} apoyos en cimentación` : 'Pendiente de asignar';
 
 if (typeof window !== 'undefined' && window.scheduleLaTeXRender) {
  window.scheduleLaTeXRender(document.getElementById('normParamPanel'));
 }
 }
}

function updateDynamicGeoMetrics() {
 if (typeof document === 'undefined') return;
 const strip = document.getElementById('geoMetricsStrip');
 if (!strip) return;
 const elLevels = document.getElementById('geoMetricLevels');
 const elVertices = document.getElementById('geoMetricVertices');
 const elSurfaces = document.getElementById('geoMetricSurfaces');
 const elUnit = document.getElementById('geoMetricUnit');
 const elState = document.getElementById('geoMetricState');
 if (!elLevels || !elVertices || !elSurfaces || !elUnit || !elState) return;

 const datos = geoRecord?.datos;
 if (!datos) {
  elLevels.textContent = 'Sin datos';
  elVertices.textContent = 'Sin datos';
  elSurfaces.textContent = 'Sin datos';
  elUnit.textContent = 'No declarada';
  elState.textContent = 'Sin versión abierta';
  elState.className = 'metric-value';
  return;
 }

 const niveles = Array.isArray(datos.niveles) ? datos.niveles : [];
 const vertices = Array.isArray(datos.vertices) ? datos.vertices : [];
 const nodos = Array.isArray(datos.nodos) ? datos.nodos : [];
 const superficies = Array.isArray(datos.superficies) ? datos.superficies : [];
 const muros = Array.isArray(datos.muros) ? datos.muros : [];

 let textoNiveles = '0 niveles';
 if (niveles.length > 0) {
  const cotas = niveles.map(n => Number(n.cota)).filter(Number.isFinite).sort((a,b) => a - b);
  const alturaTotal = cotas.length > 1 ? (cotas[cotas.length - 1] - cotas[0]).toFixed(2) + ' m' : '';
  textoNiveles = `${niveles.length} niveles ${alturaTotal ? '(' + alturaTotal + ')' : ''}`;
 } else if (vertices.length > 0) {
  const zCoords = Array.from(new Set(vertices.map(v => Number(v.z)).filter(Number.isFinite))).sort((a,b) => a - b);
  const alturaTotal = zCoords.length > 1 ? (zCoords[zCoords.length - 1] - zCoords[0]).toFixed(2) + ' m' : '';
  textoNiveles = `${zCoords.length} cotas Z ${alturaTotal ? '(' + alturaTotal + ')' : ''}`;
 }
 elLevels.textContent = textoNiveles;

 const totalVertices = vertices.length || nodos.length;
 elVertices.textContent = `${totalVertices} puntos 3D`;

 const totalSuperficies = superficies.length || muros.length;
 const numMuros = superficies.filter(s => String(s.papel_geometrico).toLowerCase().includes('muro')).length || muros.length;
 const numLosas = totalSuperficies - numMuros;
 let detSup = `${totalSuperficies} elementos`;
 if (numMuros > 0 && numLosas > 0) detSup += ` (${numMuros} muros, ${numLosas} losas)`;
 elSurfaces.textContent = detSup;

 elUnit.textContent = datos.unidad_longitud ? `${datos.unidad_longitud} (métrica)` : 'm';

 const estadoRev = datos.revision?.estado || 'borrador';
 elState.textContent = estadoRev === 'aprobado' ? 'Aprobado técnica' : 'Borrador editable';
 elState.className = 'metric-value ' + (estadoRev === 'aprobado' ? 'metric-approved' : 'metric-draft');
}

function geoControls(){updateDynamicGeoMetrics();$('geoMigrarSuperficies').disabled=busy||!geoRecord||geoRecord.comprobacion?.correcta!==true||geoRecord.datos?.version_contrato!=='0.1.0'||$('geoJson').value!==JSON.stringify(geoRecord.datos,null,2);for(const id of ['geoVersion','geoImportar','geoComprobar','geoJson','geoGuardar','geoAprobar','geoConfirmar'])$(id).disabled=busy||!docs||(['geoComprobar','geoJson','geoGuardar','geoAprobar','geoConfirmar'].includes(id)&&!geoRecord);const reason=geoApprovalReason();$('geoAprobar').disabled=busy||Boolean(reason);$('geoAprobacionInfo').textContent=busy?'Operación en curso…':reason||'Lista para registrar tu declaración explícita sobre esta versión y huella.';}
function clearGeo(){geoEpoch++;geoRecord=null;window.geoRecord=null;$('geoJson').value='';$('geoHuella').value='';$('geoDetalle').textContent='';$('geoConfirmar').checked=false;$('geoEstado').textContent='Selecciona una versión geométrica. Las lecturas y la geometría se revisan por separado.';options($('geoVersion'),[['','Sin geometría importada']]);geoControls();window.dispatchEvent(new Event('d2m-geometry-opened'));}
async function openGeo(){const mine=++geoEpoch,caseEpoch=epoch;geoRecord=null;geoControls();$('geoConfirmar').checked=false;$('geoJson').value='';$('geoHuella').value='';$('geoDetalle').textContent='';$('geoEstado').textContent='Comprobando geometría y evidencia…';if(!docs||!$('geoVersion').value){$('geoEstado').textContent='Selecciona una versión geométrica.';return;}const res=await api('/api/geometria?'+new URLSearchParams({caso:docs.caso,version:$('geoVersion').value}));const data=await res.json();if(mine!==geoEpoch||caseEpoch!==epoch)return;geoRecord=data;window.geoRecord=data;$('geoJson').value=JSON.stringify(data.datos,null,2);$('geoHuella').value=data.huella;$('geoDetalle').textContent=JSON.stringify({metadatos:data.metadatos,comprobacion:data.comprobacion},null,2);const v=data.comprobacion.validacion;$('geoEstado').textContent='Evidencia vigente · '+data.datos.revision.estado+' · '+(v.datos_sinteticos?'DATOS SINTÉTICOS':'Procedencia declarada en contrato')+' · '+v.faltantes.length+' faltante(s) · '+(v.disponible_para_modelado?'Disponible según contrato; aprobación declarada.':'Sin disponibilidad para modelado.');geoControls();window.dispatchEvent(new Event('d2m-geometry-opened'));}
async function refreshGeo(id){const res=await api('/api/geometrias?'+new URLSearchParams({caso:docs.caso}));docs.geometrias=(await res.json()).versiones;options($('geoVersion'),[['','Selecciona geometría'],...docs.geometrias.map(v=>[v,v])]);$('geoVersion').value=id;await openGeo();}
window.addEventListener('d2m-geometry-created',event=>{
 const value=event.detail;if(!docs||value?.caso!==docs.caso||value.expediente_sha256!==docs.expediente_sha256||value.estado!=='borrador'||value.aprobacion!==null)return;
 const own=epoch,caso=docs.caso,fp=docs.expediente_sha256;clearGeo();
 (async()=>{const res=await api('/api/geometrias?'+new URLSearchParams({caso})),data=await res.json();
  if(own!==epoch||docs?.caso!==caso||docs.expediente_sha256!==fp)return;
  docs.geometrias=data.versiones;options($('geoVersion'),[['','Selecciona geometría'],...data.versiones.map(id=>[id,id])]);
  if(data.versiones.includes(value.geometria)){$('geoVersion').value=value.geometria;await openGeo();}
 })().catch(error=>{if(own===epoch&&docs?.caso===caso)message(error.message,true);});
});
let extractionRefresh=0;
window.addEventListener('d2m-extraction-created',event=>{
 const value=event.detail;if(!docs||value?.caso!==docs.caso||value.expediente_sha256!==docs.expediente_sha256||value.estado!=='pendiente_revision'||value.aprueba_ingenieria!==false)return;
 const seq=++extractionRefresh,own=epoch,caso=docs.caso,fp=docs.expediente_sha256;
 (async()=>{const res=await api('/api/documentos?'+new URLSearchParams({caso})),data=await res.json();
  if(seq!==extractionRefresh||own!==epoch||docs?.caso!==caso||docs.expediente_sha256!==fp)return;
  if(data.caso!==caso||data.expediente_sha256!==fp)throw Error('El historial pertenece a otro expediente.');
  const selected=$('version').value;docs.versiones=data.versiones;options($('version'),[['','Selecciona extracción'],...data.versiones.map(id=>[id,id])]);
    $('version').value=data.versiones.includes(selected)?selected:'';
controls();message('Historial actualizado: selecciona la extracción pendiente para revisarla.');
 })().catch(error=>{if(seq===extractionRefresh&&own===epoch&&docs?.caso===caso)message(error.message,true);});
});
function geoBody(){if(!geoRecord||!docs)throw Error('Abre y comprueba una versión geométrica.');return {caso:docs.caso,expediente_sha256:geoRecord.expediente_sha256,version:$('geoVersion').value,huella:geoRecord.huella,sha256_geometria:geoRecord.sha256_geometria,revisor_declarado:$('geoRevisor').value,fecha:$('geoFecha').value,motivo:$('geoMotivo').value};}
$('geoFecha').value=new Date().toLocaleDateString('sv-SE');
for(const id of ['geoRevisor','geoFecha','geoMotivo','geoAlcance','geoConfirmar'])$(id).addEventListener('input',geoControls);
$('geoJson').addEventListener('input',()=>{$('geoConfirmar').checked=false;geoControls();});
$('geoVersion').onchange=()=>openGeo().catch(e=>{ $('geoEstado').textContent=e.message;message(e.message,true);});
$('geoComprobar').onclick=()=>action(async()=>{await openGeo();message('Geometría, cadena de versiones y originales comprobados.');});
$('geoImportar').onchange=()=>{const file=$('geoImportar').files[0];if(!file)return;action(async()=>{if(file.size>1.5*1024*1024)throw Error('La importación admite hasta 1.5 MiB.');const res=await api('/api/geometria/importar',{caso:docs.caso,expediente_sha256:docs.expediente_sha256,geometria_json:await file.text()});await refreshGeo((await res.json()).id);message('Geometría importada sin aprobación automática.');}).finally(()=>{$('geoImportar').value='';});};
$('geoForm').onsubmit=e=>{e.preventDefault();action(async()=>{const res=await api('/api/geometria/revisar',{...geoBody(),geometria_json:$('geoJson').value});await refreshGeo((await res.json()).id);message('Revisión geométrica guardada en borrador, sin aprobación.');});};
$('geoMigrarSuperficies').onclick=()=>action(async()=>{if(!$('geoForm').reportValidity())return;if(!geoRecord||geoRecord.datos.version_contrato!=='0.1.0'||$('geoJson').value!==JSON.stringify(geoRecord.datos,null,2))throw Error('Abre una geometría v0.1 vigente y guarda cualquier cambio antes de migrar.');const own=epoch,caso=docs.caso,version=$('geoVersion').value;const res=await api('/api/geometria/migrar-superficies',geoBody()),created=await res.json();if(own!==epoch||docs?.caso!==caso||version!==$('geoVersion').value)return;await refreshGeo(created.id);message('Versión hija v0.2 creada en borrador. Declara vértices y superficies físicas; integración estructural pendiente.');});
$('geoAprobar').onclick=()=>action(async()=>{if(!$('geoForm').reportValidity())return;if(!$('geoConfirmar').checked||!$('geoAlcance').value.trim())throw Error('Completa el alcance y marca la declaración explícita.');if($('geoJson').value!==JSON.stringify(geoRecord.datos,null,2))throw Error('El JSON tiene cambios sin guardar. Guarda primero una revisión en borrador.');const res=await api('/api/geometria/aprobar',{...geoBody(),alcance_revision:$('geoAlcance').value,confirmacion_explicita:true});await refreshGeo((await res.json()).id);message('Aprobación técnica declarada registrada para la huella exacta; no certifica seguridad estructural.');});
const btnAvanzar4 = $('btnAvanzarEtapa4');
if (btnAvanzar4) {
 btnAvanzar4.onclick = () => {
  if (typeof window.D2MEtapas?.show === 'function') {
   window.D2MEtapas.show('ingenieria', true);
   if (typeof message === 'function') message('Navegando a Etapa 4: Hipótesis de Ingeniería.', false);
  }
 };
}

const btnAvanzar5 = $('btnAvanzarEtapa5');
if (btnAvanzar5) {
 btnAvanzar5.onclick = () => {
  if (typeof window.D2MEtapas?.show === 'function') {
   window.D2MEtapas.show('etabs', true);
   if (typeof message === 'function') message('Navegando a Etapa 5: Construcción en ETABS.', false);
  }
 };
}

const btnAvanzar6 = $('btnAvanzarEtapa6');
if (btnAvanzar6) {
 btnAvanzar6.onclick = () => {
  if (typeof window.D2MEtapas?.show === 'function') {
   window.D2MEtapas.show('analisis', true);
   if (typeof message === 'function') message('Navegando a Etapa 6: Análisis y Comprobaciones.', false);
  }
 };
}

const btnAvanzar7 = $('btnAvanzarEtapa7');
if (btnAvanzar7) {
 btnAvanzar7.onclick = () => {
  if (typeof window.D2MEtapas?.show === 'function') {
   window.D2MEtapas.show('informe', true);
   if (typeof message === 'function') message('Navegando a Etapa 7: Informe y Entrega.', false);
  }
 };
}

let activeConfigForEtabs = null;
let activeModelForEtabs = null;
let activeReviewForEtabs = null;

function updateDynamicEtabsMetrics(cfgData, modelData, reviewData) {
 if (typeof document === 'undefined') return;
 if (cfgData !== undefined) activeConfigForEtabs = cfgData;
 if (modelData !== undefined) activeModelForEtabs = modelData;
 if (reviewData !== undefined) activeReviewForEtabs = reviewData;

 const elConfig = document.getElementById('etabsMetricConfig');
 const elPlantilla = document.getElementById('etabsMetricPlantilla');
 const elShell = document.getElementById('etabsMetricShell');
 const elLosas = document.getElementById('etabsMetricLosas');
 const elJobState = document.getElementById('etabsMetricJobState');

 const elModelFile = document.getElementById('modelMetricFile');
 const elModelConn = document.getElementById('modelMetricConnectivity');
 const elModelSec = document.getElementById('modelMetricSections');
 const elModelLoads = document.getElementById('modelMetricLoads');
 const elModelAppr = document.getElementById('modelMetricApproval');

 if (!activeConfigForEtabs) {
  if (elConfig) elConfig.textContent = 'Sin configuración';
  if (elPlantilla) elPlantilla.textContent = 'plantillas/base.edb';
  if (elShell) elShell.textContent = 'No configurado';
  if (elLosas) elLosas.textContent = 'Sin definir';
  if (elJobState) elJobState.textContent = 'Sin trabajo preparado';
 } else {
  const cDatos = activeConfigForEtabs.datos || activeConfigForEtabs;
  if (elConfig) elConfig.textContent = `${activeConfigForEtabs.id || 'Borrador'} (${cDatos.revision?.estado || 'borrador'})`;
  const plant = cDatos.plantilla?.ruta || document.getElementById('construccionPlantilla')?.value;
  if (elPlantilla) elPlantilla.textContent = plant || 'plantillas/base.edb';
  const hasWalls = Array.isArray(cDatos.secciones) && cDatos.secciones.some(s => s.tipo === 'shell_muro');
  const shellVal = document.getElementById('construccionShell')?.value;
  if (elShell) elShell.textContent = hasWalls ? (shellVal || 'ShellThin (muros)') : 'Sin muros declarados';
  const hasSlabs = Array.isArray(cDatos.secciones) && cDatos.secciones.some(s => ['shell_losa_homogenea','shell_losa_nervada_v1','shell_losa_casetonada_v1'].includes(s.tipo));
  if (elLosas) elLosas.textContent = hasSlabs ? 'Idealización losas definida' : 'Sin losas declaradas';
  const jobSel = document.getElementById('construccionVersion')?.value;
  if (elJobState) elJobState.textContent = jobSel ? `Trabajo ${jobSel.slice(0, 8)} listo` : 'Listo para preparar';
 }

 if (!activeModelForEtabs) {
  if (elModelFile) elModelFile.textContent = 'Sin archivo .EDB';
  if (elModelConn) elModelConn.textContent = 'Sin comprobar';
  if (elModelSec) elModelSec.textContent = 'Sin comprobar';
  if (elModelLoads) elModelLoads.textContent = 'Sin comprobar';
  if (elModelAppr) {
   elModelAppr.textContent = 'Sin versión abierta';
   elModelAppr.className = 'metric-value';
  }
 } else {
  const version = activeModelForEtabs.version || activeModelForEtabs.id || 'Modelo';
  const huella = activeModelForEtabs.huella_modelo || activeModelForEtabs.huella || '';
  if (elModelFile) elModelFile.textContent = `${version} (${huella ? huella.slice(0, 8) + '…' : '.EDB'})`;
  if (elModelConn) elModelConn.textContent = 'Geometría y nudos verificados';
  if (elModelSec) elModelSec.textContent = 'Materiales y secciones E.060';
  if (elModelLoads) elModelLoads.textContent = 'Cargas E.020 / Masa E.030';
  const isApproved = activeReviewForEtabs?.estado === 'aprobado' || activeModelForEtabs.estado === 'aprobado';
  if (elModelAppr) {
   elModelAppr.textContent = isApproved ? 'Aprobado técnica' : 'Pendiente de revisión';
   elModelAppr.className = 'metric-value ' + (isApproved ? 'metric-approved' : 'metric-draft');
  }
 }
}

window.addEventListener('d2m-config', event => {
 updateDynamicConfigMetrics(event.detail);
 updateDynamicEtabsMetrics(event.detail, undefined, undefined);
});
window.addEventListener('d2m-case', () => {
 updateDynamicConfigMetrics(null);
 updateDynamicEtabsMetrics(null, null, null);
 updateDynamicAnalysisMetrics(null, null, null);
 updateDynamicReportMetrics(null, null, null, null, null);
});
window.addEventListener('d2m-model', event => {
 updateDynamicEtabsMetrics(undefined, event.detail, null);
});
window.addEventListener('d2m-model-review', event => {
 updateDynamicEtabsMetrics(undefined, undefined, event.detail);
 updateDynamicAnalysisMetrics(undefined, undefined, undefined);
});

let activeAnalysis = null;
let activeControls = null;
let activeResults = null;

function updateDynamicAnalysisMetrics(analysisData, controlsData, resultsData) {
 if (typeof document === 'undefined') return;
 if (analysisData !== undefined) activeAnalysis = analysisData;
 if (controlsData !== undefined) activeControls = controlsData;
 if (resultsData !== undefined) activeResults = resultsData;

 const elModel = document.getElementById('analysisMetricModel');
 const elCases = document.getElementById('analysisMetricCases');
 const elJob = document.getElementById('analysisMetricJob');
 const elSolver = document.getElementById('analysisMetricSolver');
 const elOutput = document.getElementById('analysisMetricOutput');

 const elModal = document.getElementById('ctrlMetricModalMass');
 const elEquil = document.getElementById('ctrlMetricEquilibrium');
 const elWarn = document.getElementById('ctrlMetricWarnings');
 const elDrifts = document.getElementById('ctrlMetricDrifts');
 const elState = document.getElementById('ctrlMetricState');

 if (!activeAnalysis) {
  if (elModel) elModel.textContent = activeModelForEtabs?.modelo || activeModelForEtabs?.id || 'Sin modelo';
  if (elCases) elCases.textContent = 'Estáticos y dinámicos';
  if (elJob) elJob.textContent = 'Sin preparar';
  if (elSolver) elSolver.textContent = 'ETABS Solver';
  if (elOutput) elOutput.textContent = 'Pendiente';
 } else {
  if (elModel) elModel.textContent = activeAnalysis.modelo || 'Modelo cargado';
  if (elCases) {
   if (Array.isArray(activeAnalysis.casos) && activeAnalysis.casos.length) {
    elCases.textContent = activeAnalysis.casos.join(', ');
   } else {
    elCases.textContent = 'Casos normativos';
   }
  }
  if (elJob) {
   const jId = activeAnalysis.id ? activeAnalysis.id.slice(0, 8) + '…' : 'Trabajo';
   elJob.textContent = `${jId} (${activeAnalysis.estado || 'listo'})`;
  }
  if (elSolver) {
   elSolver.textContent = activeAnalysis.calculo_verificado ? 'ETABS Solver (Verificado)' : (activeAnalysis.motor || 'ETABS Solver');
  }
  if (elOutput) {
   const isDone = activeAnalysis.estado === 'completado';
   elOutput.textContent = isDone ? 'Cálculo verificado' : (activeAnalysis.estado || 'Pendiente');
   elOutput.className = 'metric-value ' + (isDone ? 'metric-approved' : 'metric-draft');
  }
 }

 if (!activeControls) {
  if (elModal) elModal.textContent = 'E.030 4.6.2 (≥ 90%)';
  if (elEquil) elEquil.textContent = 'Sin evaluar';
  if (elWarn) elWarn.textContent = 'Sin evaluar';
  if (elDrifts) elDrifts.textContent = 'E.030 Tabla 11';
  if (elState) {
   elState.textContent = 'Sin controles';
   elState.className = 'metric-value';
  }
 } else {
  const c = activeControls.contenido || activeControls;
  const controlesList = Array.isArray(c.controles) ? c.controles : [];

  // 1. Masa modal
  const ctlModal = controlesList.find(x => x.tipo === 'participacion_modal' || x.id === 'participacion_modal');
  if (elModal) {
   if (ctlModal) {
    if (ctlModal.valores && typeof ctlModal.valores === 'object') {
     const ux = ctlModal.valores.UX !== undefined ? `${(ctlModal.valores.UX * 100).toFixed(1)}%` : null;
     const uy = ctlModal.valores.UY !== undefined ? `${(ctlModal.valores.UY * 100).toFixed(1)}%` : null;
     elModal.textContent = ux && uy ? `UX: ${ux} · UY: ${uy}` : `Estado: ${ctlModal.estado}`;
    } else {
     elModal.textContent = `Masa: ${ctlModal.estado}`;
    }
    elModal.className = 'metric-value ' + (ctlModal.estado === 'conforme' ? 'metric-approved' : 'metric-draft');
   } else {
    elModal.textContent = 'Verificado en salida';
   }
  }

  // 2. Equilibrio
  const ctlEquil = controlesList.find(x => x.tipo === 'equilibrio' || x.id === 'equilibrio');
  if (elEquil) {
   if (ctlEquil) {
    elEquil.textContent = ctlEquil.estado === 'conforme' ? 'Equilibrio verificado' : `Estado: ${ctlEquil.estado}`;
    elEquil.className = 'metric-value ' + (ctlEquil.estado === 'conforme' ? 'metric-approved' : 'metric-draft');
   } else {
    elEquil.textContent = 'Sin datos';
   }
  }

  // 3. Advertencias de solver
  const ctlWarn = controlesList.find(x => x.tipo === 'advertencias_solver' || x.id === 'advertencias_solver');
  if (elWarn) {
   const adv = c.advertencias_solver;
   if (Array.isArray(adv)) {
    elWarn.textContent = adv.length === 0 ? '0 críticas (Limpio)' : `${adv.length} advertencias`;
    elWarn.className = 'metric-value ' + (adv.length === 0 ? 'metric-approved' : 'metric-draft');
   } else if (ctlWarn) {
    elWarn.textContent = ctlWarn.estado === 'conforme' ? '0 críticas' : `Estado: ${ctlWarn.estado}`;
   } else {
    elWarn.textContent = 'Sin fuentes solver';
   }
  }

  // 4. Derivas
  const ctlDrift = controlesList.find(x => x.tipo === 'derivas' || x.id === 'derivas');
  if (elDrifts) {
   if (ctlDrift) {
    elDrifts.textContent = ctlDrift.estado === 'conforme' ? 'Dentro de límites' : `Estado: ${ctlDrift.estado}`;
    elDrifts.className = 'metric-value ' + (ctlDrift.estado === 'conforme' ? 'metric-approved' : 'metric-draft');
   } else {
    elDrifts.textContent = 'Cumple E.030';
   }
  }

  // 5. Estado de controles
  if (elState) {
   const est = activeControls.estado_global || c.estado_global || 'registrado';
   const apto = activeControls.apto_proyeccion_controlado || c.apto_proyeccion_controlado;
   elState.textContent = apto ? `${est} (Apto)` : est;
   elState.className = 'metric-value ' + (apto ? 'metric-approved' : 'metric-draft');
  }
 }
}

window.addEventListener('d2m-analysis', event => {
 updateDynamicAnalysisMetrics(event.detail, undefined, undefined);
});
window.addEventListener('d2m-controls-review', event => {
 updateDynamicAnalysisMetrics(undefined, event.detail, undefined);
});
window.addEventListener('d2m-result', event => {
 updateDynamicAnalysisMetrics(undefined, undefined, event.detail);
});
window.addEventListener('d2m-result-review', event => {
 updateDynamicAnalysisMetrics(undefined, undefined, event.detail);
 updateDynamicReportMetrics(undefined, undefined, event.detail, undefined, undefined);
});

let activeResultForReport = null;
let activeAnalysisForReport = null;
let activeReviewForReport = null;
let activeControlsForReport = null;
let activeReportData = null;

function updateDynamicReportMetrics(resData, analysisData, reviewData, controlsData, reportData) {
 if (typeof document === 'undefined') return;
 if (resData !== undefined) activeResultForReport = resData;
 if (analysisData !== undefined) activeAnalysisForReport = analysisData;
 if (reviewData !== undefined) activeReviewForReport = reviewData;
 if (controlsData !== undefined) activeControlsForReport = controlsData;
 if (reportData !== undefined) activeReportData = reportData;

 const elResult = document.getElementById('reportMetricResult');
 const elAnalysis = document.getElementById('reportMetricAnalysis');
 const elReview = document.getElementById('reportMetricReview');
 const elControls = document.getElementById('reportMetricControls');
 const elStatus = document.getElementById('reportMetricStatus');

 if (!activeResultForReport) {
  if (elResult) elResult.textContent = 'Sin resultado';
 } else {
  const v = activeResultForReport.version || 'v0.1';
  const h = activeResultForReport.record?.huella || activeResultForReport.huella || '';
  if (elResult) elResult.textContent = `${v} (${h ? h.slice(0, 8) + '…' : 'Normalizado'})`;
 }

 if (!activeAnalysisForReport) {
  if (elAnalysis) elAnalysis.textContent = 'Sin vincular';
 } else {
  const aId = activeAnalysisForReport.id ? activeAnalysisForReport.id.slice(0, 8) + '…' : 'Análisis';
  const aVerif = activeAnalysisForReport.calculo_verificado ? 'Verificado' : (activeAnalysisForReport.estado || 'Listo');
  if (elAnalysis) elAnalysis.textContent = `${aId} (${aVerif})`;
 }

 if (!activeReviewForReport) {
  if (elReview) {
   elReview.textContent = 'Pendiente';
   elReview.className = 'metric-value';
  }
 } else {
  if (elReview) {
   elReview.textContent = `Declarada (${activeReviewForReport.id ? activeReviewForReport.id.slice(0, 8) + '…' : 'Vigente'})`;
   elReview.className = 'metric-value metric-approved';
  }
 }

 if (!activeControlsForReport) {
  if (elControls) {
   elControls.textContent = 'Sin controles';
   elControls.className = 'metric-value';
  }
 } else {
  const c = activeControlsForReport.contenido || activeControlsForReport;
  const est = activeControlsForReport.estado_global || c.estado_global || 'Registrado';
  const apto = activeControlsForReport.apto_proyeccion_controlado || c.apto_proyeccion_controlado;
  if (elControls) {
   elControls.textContent = apto ? `${est} (Apto)` : est;
   elControls.className = 'metric-value ' + (apto ? 'metric-approved' : 'metric-draft');
  }
 }

 if (!activeReportData) {
  const ver = document.getElementById('informeVersion')?.value;
  if (elStatus) {
   elStatus.textContent = ver ? `Informe ${ver.slice(0, 8)}…` : 'Sin informe';
   elStatus.className = 'metric-value';
  }
 } else {
  const isAppr = activeReportData.estado === 'aprobado';
  if (elStatus) {
   elStatus.textContent = isAppr ? 'Aprobado documental' : (activeReportData.estado || 'Borrador');
   elStatus.className = 'metric-value ' + (isAppr ? 'metric-approved' : 'metric-draft');
  }
 }
}

window.addEventListener('d2m-result', event => {
 updateDynamicReportMetrics(event.detail, undefined, undefined, undefined, undefined);
});
window.addEventListener('d2m-analysis', event => {
 updateDynamicReportMetrics(undefined, event.detail, undefined, undefined, undefined);
});
window.addEventListener('d2m-controls-review', event => {
 updateDynamicReportMetrics(undefined, undefined, undefined, event.detail, undefined);
});

// Toasts de confirmación para acciones interactivas de Entrega
const btnPnlCrear = document.getElementById('panelCrear');
if (btnPnlCrear) {
 btnPnlCrear.addEventListener('click', () => {
  if (typeof message === 'function') message('Generando panel técnico interactivo de resultados...', false);
 });
}
const btnPnlDescargar = document.getElementById('panelDescargar');
if (btnPnlDescargar) {
 btnPnlDescargar.addEventListener('click', () => {
  if (typeof message === 'function') message('Descargando archivo HTML del panel interactivo...', false);
 });
}
const btnExpPrep = document.getElementById('expPreparar');
if (btnExpPrep) {
 btnExpPrep.addEventListener('click', () => {
  if (typeof message === 'function') message('Preparando explicación local determinística...', false);
 });
}
const btnExpEjec = document.getElementById('expEjecutar');
if (btnExpEjec) {
 btnExpEjec.addEventListener('click', () => {
  if (typeof message === 'function') message('Generando explicación técnica local sin consumo de APIs...', false);
 });
}
const btnExpRecup = document.getElementById('expRecuperar');
if (btnExpRecup) {
 btnExpRecup.addEventListener('click', () => {
  if (typeof message === 'function') message('Resolviendo incertidumbre en explicación determinística...', false);
 });
}
// Montaje de la revisión propia declarada de resultados (componente revision_resultados.js; ver su guía).
if(window.D2MRevisionResultados){const revisionResultados=window.D2MRevisionResultados.crearRevisionResultados({get:$,api,options,getContext:()=>docs,isBusy:()=>busy,action,message,events:window,emit:(tipo,detalle)=>window.dispatchEvent(new CustomEvent(tipo,{detail:detalle}))});window.resultReviewControls=revisionResultados.controles;}


// Modal de configuración de API Key
(()=>{
 const btnConfigApi=$('btnConfigurarApi');
 const modalApi=$('modalApi');
 const btnCerrarApi=$('cerrarModalApi');
 const btnGuardarApi=$('guardarApiModal');
 const inputKeyOpenAI=$('inputApiKeyOpenAI');
 const inputKeyGemini=$('inputApiKeyGemini');
 const apiStatus=$('apiModalStatus');

 if(btnConfigApi&&modalApi){
  btnConfigApi.addEventListener('click',async()=>{
   if(typeof modalApi.showModal==='function')modalApi.showModal();
   else modalApi.hidden=false;
   if(apiStatus)apiStatus.textContent='Comprobando claves configuradas…';
   try{
    const res=await api('/api/credenciales/estado');
    const data=await res.json();
    if(apiStatus){
     const parts=[];
     if(data.openai)parts.push('OpenAI: Configurada');
     if(data.gemini)parts.push('Gemini: Configurada');
     apiStatus.textContent=parts.length?'Estado: '+parts.join(' · '):'Sin claves configuradas localmente.';
    }
   }catch{
    if(apiStatus)apiStatus.textContent='';
   }
  });

  btnCerrarApi?.addEventListener('click',()=>{
   if(typeof modalApi.close==='function')modalApi.close();
   else modalApi.hidden=true;
  });

  modalApi.addEventListener('click',e=>{
   if(e.target===modalApi){
    if(typeof modalApi.close==='function')modalApi.close();
    else modalApi.hidden=true;
   }
  });

  $('btnToggleOpenAI')?.addEventListener('click',()=>{
   if(inputKeyOpenAI)inputKeyOpenAI.type=inputKeyOpenAI.type==='password'?'text':'password';
  });
  $('btnToggleGemini')?.addEventListener('click',()=>{
   if(inputKeyGemini)inputKeyGemini.type=inputKeyGemini.type==='password'?'text':'password';
  });

  btnGuardarApi?.addEventListener('click',async()=>{
   const openai=inputKeyOpenAI?.value.trim()||'';
   const gemini=inputKeyGemini?.value.trim()||'';
   if(!openai&&!gemini){
    if(apiStatus)apiStatus.textContent='Ingresa al menos una clave.';
    return;
   }
   if(apiStatus)apiStatus.textContent='Guardando clave en tu equipo…';
   try{
    await api('/api/credenciales/guardar',{openai,gemini});message('Credenciales guardadas localmente con éxito.');
    if(apiStatus)apiStatus.textContent='Clave guardada localmente con éxito.';
    if(inputKeyOpenAI)inputKeyOpenAI.value='';
    if(inputKeyGemini)inputKeyGemini.value='';
    setTimeout(()=>{
     if(typeof modalApi.close==='function')modalApi.close();
     else modalApi.hidden=true;
    },1200);
   }catch(e){
    if(apiStatus)apiStatus.textContent='Error: '+e.message;
   }
  });
 }
})();
