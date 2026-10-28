'use strict';
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const assert=require('node:assert/strict');

const flush=()=>new Promise(r=>setImmediate(r));
async function settle(){for(let i=0;i<10;i++)await flush();}
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}

const FP_A='a'.repeat(64),FP_B='b'.repeat(64);
const GEO_1='1'.repeat(32),GEO_2='2'.repeat(32);
const H_GEO_1='c'.repeat(64),S_GEO_1='d'.repeat(64);
const H_GEO_2='e'.repeat(64),S_GEO_2='f'.repeat(64);
const PREP_ID='9'.repeat(32),CALC_ID='8'.repeat(32);
const SHA_PDF='7'.repeat(64),H_PREP='6'.repeat(64),H_CALC='5'.repeat(64),H_MOD='4'.repeat(64);

function makeGeoRecord(versionId=GEO_1,huella=H_GEO_1,sha=S_GEO_1,sintetico=true){
 const proc={tipo:sintetico?'sintetico':'plano',descripcion:'Geometría 0.3 sintética'};
 return {
  datos:{
   contrato:'draft2model.geometria',
   version_contrato:'0.3.0',
   id:'CASO_A',
   unidad_longitud:'m',
   procedencia:proc,
   niveles:[],
   nodos:[],
   muros:[],
   vertices:[
    {id:'VA',x:1,y:1,z:0,procedencia:proc},
    {id:'VB',x:9,y:1,z:0,procedencia:proc},
    {id:'VC',x:9,y:7,z:0,procedencia:proc},
    {id:'VT1',x:1,y:1,z:2.8,procedencia:proc}
   ],
   superficies:[],
   aberturas:[],
   faltantes:[],
   revision:{estado:'borrador',aprobacion:null}
  },
  huella,
  sha256_geometria:sha,
  comprobacion:{
   correcta:true,
   validacion:{consistente:true,datos_sinteticos:sintetico,faltantes:[],disponible_para_modelado:false}
  }
 };
}

function makePreparedResponse(caso='CASO_A',fp=FP_A,geoId=GEO_1,huellaGeo=H_GEO_1,shaGeo=S_GEO_1,prepId=PREP_ID,huellaPrep=H_PREP){
 return {
  id:prepId,
  etapa:'preparada',
  caso,
  expediente_sha256:fp,
  huella_version:huellaPrep,
  datos_sinteticos:true,
  geometria_origen:{version_id:geoId,huella_contenido:huellaGeo,sha256_geometria:shaGeo,unidad_longitud:'m'},
  fuente_vigente:{original_id:'L0001',sha256:SHA_PDF,pagina:1,dibujo_id:'PLANTA_N0',bbox_pagina:[0,0,1,1]},
  plano:{id:'PLANO_Z_0',ejes:['x','y'],eje_constante:'z',valor_constante:0,unidad_longitud:'m'},
  catalogo_referencias:[
   {id:'VA',coordenadas:[1,1],unidad_longitud:'m',tiene_referencia_documental:false,utilizable_en_fuente:true},
   {id:'VB',coordenadas:[9,1],unidad_longitud:'m',tiene_referencia_documental:false,utilizable_en_fuente:true},
   {id:'VC',coordenadas:[9,7],unidad_longitud:'m',tiene_referencia_documental:false,utilizable_en_fuente:true}
  ],
  pendientes:[
   {codigo:'carencia_vinculo_documental_puntos',puntos:['VA','VB','VC'],mensaje:'Sin referencias documentales al dibujo.'}
  ],
  resumen:{
   etapa:'preparada',
   calculo_posible:false,
   referencias_suficientes_para_ajuste:true,
   contraste_en_controles:false,
   carencia_vinculo_documental:true,
   exactitud_documental_acreditada:false
  },
  revision:{estado:'borrador',aprobacion:null},
  aprueba_ingenieria:false,
  disponible_para_modelado:false
 };
}

function makeCalculatedResponse(body,calcId=CALC_ID,huellaCalc=H_CALC){
 const geoId=body.geometria||GEO_1;
 const huellaGeo=body.huella_geometria||H_GEO_1;
 const shaGeo=body.sha256_geometria||S_GEO_1;
 return {
  id:calcId,
  etapa:'calculada',
  caso:body.caso,
  expediente_sha256:body.expediente_sha256,
  huella_version:huellaCalc,
  datos_sinteticos:true,
  geometria_origen:{version_id:geoId,huella_contenido:huellaGeo,sha256_geometria:shaGeo,unidad_longitud:'m'},
  fuente_vigente:body.fuente,
  plano:body.plano,
  propuesta:{
   id:body.propuesta_id,
   fuente:body.fuente,
   plano:body.plano,
   limites:body.limites,
   anclas:body.anclas,
   controles:body.controles,
   puntos:body.puntos
  },
  hashes_entradas:{huella_entrada_modulo:H_MOD},
  pendientes:[
   {codigo:'carencia_vinculo_documental_puntos',puntos:['VA','VB','VC'],mensaje:'Sin referencias documentales hacia el dibujo.'},
   {codigo:'ajuste_exacto_tres_anclas_sin_verificacion',mensaje:'Tres anclas con residuo nulo NO constituyen verificación independiente.'},
   {codigo:'puntos_fuera_casco_anclas',puntos:['PN1'],mensaje:'Punto propuesto en extrapolación.'}
  ],
  resumen:{
   etapa:'calculada',
   calculo_posible:true,
   referencias_suficientes_para_ajuste:true,
   contraste_en_controles:false,
   ajuste_tres_anclas_sin_verificacion:true,
   carencia_vinculo_documental:true,
   exactitud_documental_acreditada:false
  },
  resultado:{
   residuo_ajuste_max_m:0,
   error_control_max_m:null,
   transformacion:{condicion_diseno:1.25,escalas_singulares_m_por_uv:[8.0,10.0]},
   anclas:[
    {id:'A1',punto_resuelto:'VA',uv_local:[0.1,0.875],residuo_m:0,referencias:['descriptor_geometrico:'+geoId]},
    {id:'A2',punto_resuelto:'VB',uv_local:[0.9,0.875],residuo_m:0,referencias:['descriptor_geometrico:'+geoId]},
    {id:'A3',punto_resuelto:'VC',uv_local:[0.9,0.125],residuo_m:0,referencias:['descriptor_geometrico:'+geoId]}
   ],
   controles:[],
   puntos:[
    {
     id:'PN1',
     uv_local:body.puntos[0].uv_local,
     uv_pagina:body.puntos[0].uv_local,
     coordenadas_m:{x:5.2,y:4.0,z:0.0},
     extrapolacion:true,
     incertidumbre:{indicador_m:0.0412,dentro_limite:true}
    }
   ]
  },
  revision:{estado:'borrador',aprobacion:null},
  aprueba_ingenieria:false,
  disponible_para_modelado:false
 };
}

function createHarness(){
 const allElements=[];
 const byIdMap=new Map();
 const winListeners={};
 const calls=[];
 const messages=[];
 let customHandler=null;
 let historyRows=[];

 class Element{
  constructor(tag){
   this.tagName=tag;
   this._id='';
   this.className='';
   this.textContent='';
   this.children=[];
   this.parent=null;
   this.attrs={};
   this.events={};
   this._value=undefined;
   this.disabled=false;
   this.hidden=false;
   this.maxLength=0;
   this.placeholder='';
   this.type='';
   allElements.push(this);
  }
  get id(){return this._id;}
  set id(v){this._id=String(v);if(v)byIdMap.set(String(v),this);}
  get value(){
   if(this._value!==undefined)return this._value;
   if(this.tagName==='select')return this.children[0]?.value??'';
   return '';
  }
  set value(v){this._value=String(v);}
  append(...nodes){
   for(const n of nodes){
    if(n&&typeof n==='object'){n.parent=this;}
    this.children.push(n);
   }
  }
  replaceChildren(...nodes){
   this.children=[];
   this.append(...nodes);
   if(this.tagName==='select'&&!this.children.some(c=>String(c.value)===String(this._value))){
    this._value=this.children[0]?.value??'';
   }
  }
  after(node){
   if(!this.parent)return;
   const idx=this.parent.children.indexOf(this);
   node.parent=this.parent;
   this.parent.children.splice(idx+1,0,node);
  }
  remove(){
   if(!this.parent)return;
   const idx=this.parent.children.indexOf(this);
   if(idx>=0)this.parent.children.splice(idx,1);
   this.parent=null;
  }
  setAttribute(k,v){this.attrs[k]=String(v);}
  querySelector(sel){
   if(sel==='.stage-guide')return this.children.find(c=>c.className==='stage-guide')||null;
   return null;
  }
  addEventListener(type,fn){(this.events[type]??=[]).push(fn);}
  async emit(type,ev={}){
   for(const fn of this.events[type]||[])await fn({preventDefault(){},...ev});
  }
 }

 const stageGeo=new Element('div');
 const guide=new Element('p');guide.className='stage-guide';
 stageGeo.append(guide);
 const geoVersionSelect=new Element('select');
 geoVersionSelect.id='geoVersion';
 geoVersionSelect.value=GEO_1;

 const windowObj={
  D2MEtapas:{containers:new Map([['geometria',stageGeo]])},
  addEventListener(type,fn){(winListeners[type]??=[]).push(fn);},
  dispatchEvent(ev){for(const fn of winListeners[ev.type]||[])fn(ev);}
 };

 const ctx={
  window:windowObj,
  document:{
   createElement:t=>new Element(t),
   getElementById:id=>byIdMap.get(id)||null
  },
  docs:{
   caso:'CASO_A',
   expediente_sha256:FP_A,
   documentos:[
    {id:'L0001',nombre:'planta_sintetica.pdf',paginas:2,error:null},
    {id:'L0002',nombre:'corrupto.pdf',paginas:0,error:'PDF inválido'}
   ],
   geometrias:[GEO_1,GEO_2]
  },
  geoRecord:makeGeoRecord(),
  $:id=>byIdMap.get(id)||null,
  message:(txt,err)=>messages.push({txt,err:Boolean(err)}),
  URLSearchParams,
  CustomEvent:class{constructor(t,o){this.type=t;this.detail=o?.detail;}},
  Event:class{constructor(t){this.type=t;}},
  api:async(url,body)=>{
   calls.push({url,body:body?JSON.parse(JSON.stringify(body)):undefined});
   if(customHandler){
    const custom=customHandler(url,body);
    if(custom!==undefined)return custom;
   }
   if(url.startsWith('/api/digitizacion/historial?')){
    return {json:async()=>({registros:historyRows,versiones:historyRows,seleccion_automatica:false})};
   }
   if(url==='/api/digitizacion/preparar'){
    const rec=makePreparedResponse(body.caso,body.expediente_sha256,body.geometria,body.huella_geometria,body.sha256_geometria);
    historyRows=[{id:rec.id,vigente:true,etapa:'preparada',dibujo_id:body.fuente.dibujo_id,pendientes:1}];
    return {json:async()=>rec};
   }
   if(url==='/api/digitizacion/calcular'){
    const rec=makeCalculatedResponse(body);
    historyRows.push({id:rec.id,vigente:true,etapa:'calculada',dibujo_id:body.fuente.dibujo_id,pendientes:3});
    return {json:async()=>rec};
   }
   if(url.startsWith('/api/digitizacion/registro?')){
    const calc=makeCalculatedResponse({
     caso:'CASO_A',
     expediente_sha256:FP_A,
     propuesta_id:'PROP_GUARDADA',
     fuente:{original_id:'L0001',sha256:SHA_PDF,pagina:1,dibujo_id:'PLANTA_N0',bbox_pagina:[0,0,1,1]},
     plano:{id:'PLANO_Z_0',ejes:['x','y'],eje_constante:'z',valor_constante:0,unidad_longitud:'m'},
     limites:{residuo_ajuste_max_m:0.02,error_control_max_m:0.03,incertidumbre_max_m:0.1,localizacion_uv:0.005,referencia_m:0.005,condicion_max:30,escala_min_m_por_uv:1,escala_max_m_por_uv:100,coordenada_abs_max_m:500},
     anclas:[
      {id:'A1',punto_resuelto:'VA',uv_local:[0.1,0.875]},
      {id:'A2',punto_resuelto:'VB',uv_local:[0.9,0.875]},
      {id:'A3',punto_resuelto:'VC',uv_local:[0.9,0.125]}
     ],
     controles:[],
     puntos:[{id:'PN1',uv_local:[0.5,0.5],relacionados:['VA','VB']}]
    });
    return {json:async()=>calc};
   }
   throw new Error('Ruta inesperada en prueba frontend: '+url);
  }
 };

 const srcPath=path.join(__dirname,'../draft2model/revision_web/digitizacion.js');
 const src=fs.readFileSync(srcPath,'utf8');
 vm.createContext(ctx);
 vm.runInContext(src,ctx,{filename:'digitizacion.js'});

 function collectText(node){
  if(!node||typeof node!=='object')return String(node||'');
  return [node.textContent||'',...(node.children||[]).map(collectText)].join(' ');
 }

 return {
  src,
  ctx,
  stageGeo,
  allElements,
  byId:id=>byIdMap.get(id),
  calls,
  messages,
  collectText,
  setHandler:fn=>{customHandler=fn;},
  setHistory:rows=>{historyRows=rows;},
  emitWindow:async(ev)=>{
   for(const fn of winListeners[ev.type]||[])await fn(ev);
   await settle();
  }
 };
}

(async()=>{
 // 1. Montaje en etapa 3, separación de paneles, sin coordenadas métricas ni JSON externo ni innerHTML/eval
 const h=createHarness();
 assert.ok(!/innerHTML|eval\(|new Function/.test(h.src),'Sin innerHTML, eval ni new Function');
 assert.ok(h.byId('digPanel'),'Panel montado en etapa 3 geometría');
 assert.ok(h.byId('digPanelPropuesta')&&h.byId('digPanelRevision')&&h.byId('digPanelResultados'),'Subpaneles separados');
 assert.equal(h.allElements.some(e=>e.tagName==='textarea'||e.type==='file'),false,'Sin JSON externo ni carga de archivos');
 assert.match(h.byId('digAvisoLimites').textContent,/Tres anclas con residuo 0.*NO constituyen verificación independiente/);

 await h.emitWindow(new h.ctx.Event('d2m-case'));
 assert.equal(h.byId('digOriginal').children.length,1,'Filtra documentos con error');
 assert.equal(h.byId('digOriginal').value,'L0001');

 // 2. Rechazo de evento automático con coordenadas métricas o de otro expediente
 await h.emitWindow(new h.ctx.CustomEvent('d2m-digitizacion-propuesta',{detail:{
  caso:'OTRO_CASO',expediente_sha256:FP_A,propuesta_id:'P_MAL'
 }}));
 assert.match(h.byId('digEstado').textContent,/no corresponde al expediente abierto/);

 await h.emitWindow(new h.ctx.CustomEvent('d2m-digitizacion-propuesta',{detail:{
  caso:'CASO_A',expediente_sha256:FP_A,propuesta_id:'P_METRICA',
  anclas:[{id:'A1',punto_resuelto:'VA',uv_local:[0.1,0.8],coordenadas:[1,1]}]
 }}));
 assert.match(h.byId('digEstado').textContent,/RECHAZADA.*coordenadas métricas físicas prohibidas/);

 // 3. Carga automática válida por d2m-digitizacion-propuesta, corrección en pantalla, preparar y calcular
 await h.emitWindow(new h.ctx.CustomEvent('d2m-digitizacion-propuesta',{detail:{
  caso:'CASO_A',
  expediente_sha256:FP_A,
  geometria:GEO_1,
  huella_geometria:H_GEO_1,
  referencia_origen:'IA_PROP_SINT_1',
  propuesta_id:'PROP_IA_1',
  fuente:{original_id:'L0001',pagina:1,dibujo_id:'PLANTA_N0',bbox_pagina:[0,0,1,1]},
  plano:{id:'PLANO_Z_0',ejes:['x','y'],eje_constante:'z',valor_constante:0,unidad_longitud:'m'},
  limites:{
   residuo_ajuste_max_m:0.02,error_control_max_m:0.03,incertidumbre_max_m:0.12,
   localizacion_uv:0.004,referencia_m:0.003,condicion_max:30,
   escala_min_m_por_uv:1,escala_max_m_por_uv:80,coordenada_abs_max_m:500
  },
  anclas:[
   {id:'A1',punto_resuelto:'VA',uv_local:[0.1,0.875]},
   {id:'A2',punto_resuelto:'VB',uv_local:[0.9,0.875]},
   {id:'A3',punto_resuelto:'VC',uv_local:[0.9,0.125]}
  ],
  controles:[],
  puntos:[{id:'PN1',uv_local:[0.5,0.5],relacionados:['VA','VB','VC']}]
 }}));
 assert.match(h.byId('digPropuestaAviso').textContent,/SIN APROBAR/);
 assert.equal(h.calls.some(c=>c.url.endsWith('/preparar')||c.url.endsWith('/calcular')),false,'No ejecuta automáticamente');
 assert.equal(h.byId('digCalcular').disabled,true,'Exige preparar antes de calcular');

 // Corrección humana en pantalla de coordenada normalizada u del punto nuevo
 h.byId('digPuntoU1').value='0.52';
 await h.byId('digPuntoU1').emit('input');
 assert.match(h.byId('digPropuestaAviso').textContent,/CORREGIDA en pantalla/);

 await h.byId('digPreparar').emit('click');
 await settle();
 const prepCall=h.calls.find(c=>c.url==='/api/digitizacion/preparar');
 assert.ok(prepCall);
 assert.equal(prepCall.body.origen_propuesta.modo,'propuesta_estructurada_revisada');
 assert.equal(prepCall.body.origen_propuesta.editada_en_pantalla,true);
 assert.equal(h.byId('digCalcular').disabled,false);

 await h.byId('digCalcular').emit('click');
 await settle();
 const calcCall=h.calls.find(c=>c.url==='/api/digitizacion/calcular');
 assert.ok(calcCall);
 assert.equal(calcCall.body.fuente.sha256,SHA_PDF);
 assert.deepEqual(calcCall.body.puntos[0].uv_local,[0.52,0.5]);
 assert.equal('coordenadas' in calcCall.body,false);

 const resumenTxt=h.collectText(h.byId('digResultadoResumen'));
 assert.match(resumenTxt,/BORRADOR/);
 assert.match(resumenTxt,/DATOS SINTÉTICOS CONSERVADOS/);
 assert.match(resumenTxt,/AVISO DE NO VERIFICACIÓN: Ajuste con 3 anclas/);
 assert.match(resumenTxt,/VÍNCULO DOCUMENTAL NO ACREDITADO/);
 assert.match(h.collectText(h.byId('digTablaPuntos')),/incertidumbre indicativa ±0\.0412 m/);
 assert.match(h.byId('digHuellaActiva').textContent,new RegExp(H_CALC));

 // 4. Invalidación de cálculo/huella al editar datos o cambiar de geometría
 h.byId('digAnclaU1').value='0.12';
 await h.byId('digAnclaU1').emit('input');
 assert.match(h.byId('digHuellaActiva').textContent,/Huella anterior INVALIDADA/);

 h.byId('digDibujoId').value='OTRO_DETALLE';
 await h.byId('digDibujoId').emit('input');
 assert.equal(h.byId('digCalcular').disabled,true,'Cambiar fuente invalida preparación y deshabilita calcular');

 // Abrir un registro conservado desde historial
 h.byId('digHistorial').value=CALC_ID;
 await h.byId('digHistorial').emit('change');
 await h.byId('digAbrirRegistro').emit('click');
 await settle();
 assert.match(h.byId('digHuellaActiva').textContent,new RegExp(H_CALC));

 // Cambiar geometría abierta invalida cálculo y preparación
 h.byId('geoVersion').value=GEO_2;
 h.ctx.geoRecord=makeGeoRecord(GEO_2,H_GEO_2,S_GEO_2,true);
 await h.emitWindow(new h.ctx.Event('d2m-geometry-opened'));
 assert.equal(h.byId('digCalcular').disabled,true);
 assert.match(h.byId('digHuellaActiva').textContent,/Geometría cambiada/);

 // 5. Cambio de caso borra selección y bloquea respuestas tardías del caso anterior
 const slowPrep=deferred();
 h.setHandler(url=>url==='/api/digitizacion/preparar'?slowPrep.promise:undefined);
 const pendingPrep=h.byId('digPreparar').emit('click');
 await flush();
 h.ctx.docs={caso:'CASO_B',expediente_sha256:FP_B,documentos:[{id:'L9001',nombre:'otro.pdf',paginas:1,error:null}],geometrias:[]};
 h.ctx.geoRecord=null;
 h.setHandler(null);
 h.setHistory([]);
 await h.emitWindow(new h.ctx.Event('d2m-case'));

 // Resuelve respuesta tardía del CASO_A después de haber cambiado a CASO_B
 slowPrep.resolve({json:async()=>makePreparedResponse('CASO_A',FP_A)});
 await pendingPrep;
 await settle();
 assert.equal(h.byId('digHuellaActiva').textContent,'Sin huella activa de cálculo vigente.');
 assert.equal(h.byId('digCalcular').disabled,true);
 assert.equal(h.byId('digOriginal').value,'L9001');
 assert.equal(h.calls.some(c=>c.url.includes('/etabs')),false);

 // 6. Regresión 355-02: concurrencia por geometría (G1 -> G2 en el mismo caso) en preparar, calcular, abrir e historial
 const h2=createHarness();
 await h2.emitWindow(new h2.ctx.Event('d2m-case'));
 // 6a) Reproducción exacta 355-02: preparar G1 diferido, cambiar a G2 con d2m-geometry-opened, resolver G1 tarde
 const slowPrepG1=deferred();
 h2.setHandler(url=>url==='/api/digitizacion/preparar'?slowPrepG1.promise:undefined);
 const pendingPrepG1=h2.byId('digPreparar').emit('click');
 await flush();
 h2.byId('geoVersion').value=GEO_2;
 h2.ctx.geoRecord=makeGeoRecord(GEO_2,H_GEO_2,S_GEO_2,true);
 await h2.emitWindow(new h2.ctx.Event('d2m-geometry-opened'));
 const beforeG2=h2.byId('digHuellaActiva').textContent;
 assert.match(beforeG2,/Geometría cambiada/);
 assert.equal(h2.byId('digPreparar').disabled,false,'Cambiar a G2 libera botón preparar para G2');
 assert.equal(h2.byId('digCalcular').disabled,true);

 slowPrepG1.resolve({json:async()=>makePreparedResponse('CASO_A',FP_A,GEO_1,H_GEO_1,S_GEO_1)});
 await pendingPrepG1;
 await settle();
 assert.equal(h2.byId('digHuellaActiva').textContent,beforeG2,'No restaura preparación ni huella de G1 sobre G2');
 assert.equal(h2.byId('digCalcular').disabled,true,'No habilita digCalcular bajo G2 con respuesta antigua de G1');
 assert.equal(h2.byId('geoVersion').value,GEO_2);

 // Preparar ahora G2 limpiamente y rellenar entradas válidas
 h2.setHandler(null);
 const PREP_G2='3'.repeat(32),H_PREP_G2='2'.repeat(64);
 h2.setHandler((url,body)=>{
  if(url==='/api/digitizacion/preparar'){
   return Promise.resolve({json:async()=>makePreparedResponse(body.caso,body.expediente_sha256,GEO_2,H_GEO_2,S_GEO_2,PREP_G2,H_PREP_G2)});
  }
  return undefined;
 });
 await h2.byId('digPreparar').emit('click');
 await settle();
 assert.match(h2.byId('digHuellaActiva').textContent,new RegExp(H_PREP_G2));
 assert.equal(h2.byId('digCalcular').disabled,false);

 h2.byId('digAnclaPunto1').value='VA';h2.byId('digAnclaU1').value='0.1';h2.byId('digAnclaV1').value='0.875';
 h2.byId('digAnclaPunto2').value='VB';h2.byId('digAnclaU2').value='0.9';h2.byId('digAnclaV2').value='0.875';
 h2.byId('digAnclaPunto3').value='VC';h2.byId('digAnclaU3').value='0.9';h2.byId('digAnclaV3').value='0.125';
 h2.byId('digPuntoU1').value='0.5';h2.byId('digPuntoV1').value='0.5';h2.byId('digPuntoRel1').value='VA,VB,VC';

 // 6b) Calcular diferido en G2, cambiar a G1 antes de resolver -> respuesta de cálculo G2 descartada
 const slowCalcG2=deferred();
 let capturedCalcG2Body=null;
 h2.setHandler((url,body)=>{
  if(url==='/api/digitizacion/calcular'){capturedCalcG2Body=body;return slowCalcG2.promise;}
  return undefined;
 });
 const pendingCalcG2=h2.byId('digCalcular').emit('click');
 await flush();
 h2.byId('geoVersion').value=GEO_1;
 h2.ctx.geoRecord=makeGeoRecord(GEO_1,H_GEO_1,S_GEO_1,true);
 await h2.emitWindow(new h2.ctx.Event('d2m-geometry-opened'));
 slowCalcG2.resolve({json:async()=>makeCalculatedResponse(capturedCalcG2Body)});
 await pendingCalcG2;
 await settle();
 assert.match(h2.byId('digHuellaActiva').textContent,/Geometría cambiada/);
 assert.equal(h2.collectText(h2.byId('digTablaPuntos')).trim(),'','No muestra puntos de G2 bajo G1');
 assert.equal(h2.byId('digCalcular').disabled,true);

 // 6c) Abrir registro diferido de G1 y cambiar a G2 en vuelo; además rechazar abrir registro de G1 estando en G2
 h2.setHandler(null);
 h2.setHistory([{id:CALC_ID,vigente:true,etapa:'calculada',dibujo_id:'PLANTA_N0',pendientes:3}]);
 await h2.byId('digRefrescarHistorial').emit('click');
 await settle();
 h2.byId('digHistorial').value=CALC_ID;
 await h2.byId('digHistorial').emit('change');

 const slowOpenG1=deferred();
 h2.setHandler(url=>url.startsWith('/api/digitizacion/registro?')?slowOpenG1.promise:undefined);
 const pendingOpenG1=h2.byId('digAbrirRegistro').emit('click');
 await flush();
 h2.byId('geoVersion').value=GEO_2;
 h2.ctx.geoRecord=makeGeoRecord(GEO_2,H_GEO_2,S_GEO_2,true);
 await h2.emitWindow(new h2.ctx.Event('d2m-geometry-opened'));
 slowOpenG1.resolve({json:async()=>makeCalculatedResponse({
  caso:'CASO_A',expediente_sha256:FP_A,geometria:GEO_1,huella_geometria:H_GEO_1,sha256_geometria:S_GEO_1,
  propuesta_id:'PROP_G1',fuente:{original_id:'L0001',sha256:SHA_PDF,pagina:1,dibujo_id:'PLANTA_N0',bbox_pagina:[0,0,1,1]},
  plano:{id:'PLANO_Z_0',ejes:['x','y'],eje_constante:'z',valor_constante:0,unidad_longitud:'m'},
  limites:{residuo_ajuste_max_m:0.02,error_control_max_m:0.03,incertidumbre_max_m:0.1,localizacion_uv:0.005,referencia_m:0.005,condicion_max:30,escala_min_m_por_uv:1,escala_max_m_por_uv:100,coordenada_abs_max_m:500},
  anclas:[{id:'A1',punto_resuelto:'VA',uv_local:[0.1,0.875]},{id:'A2',punto_resuelto:'VB',uv_local:[0.9,0.875]},{id:'A3',punto_resuelto:'VC',uv_local:[0.9,0.125]}],
  controles:[],puntos:[{id:'PN1',uv_local:[0.5,0.5],relacionados:['VA']}]
 })});
 await pendingOpenG1;
 await settle();
 assert.match(h2.byId('digHuellaActiva').textContent,/Geometría cambiada/);
 assert.equal(h2.byId('digCalcular').disabled,true);

 // Intento síncrono de abrir registro de G1 mientras G2 sigue abierta -> rechazado sin restaurar G1
 h2.setHandler(null);
 await h2.byId('digAbrirRegistro').emit('click');
 await settle();
 assert.doesNotMatch(h2.byId('digHuellaActiva').textContent,new RegExp(H_CALC));
 assert.match(h2.byId('digEstado').textContent,/otra versión o huella de geometría/);
 assert.equal(h2.byId('digCalcular').disabled,true);

 // 6d) Historial diferido iniciado tras preparar G1 no sobreescribe selección al cambiar a G2
 h2.byId('geoVersion').value=GEO_1;
 h2.ctx.geoRecord=makeGeoRecord(GEO_1,H_GEO_1,S_GEO_1,true);
 await h2.emitWindow(new h2.ctx.Event('d2m-geometry-opened'));
 const slowHist=deferred();
 h2.setHandler(url=>url.startsWith('/api/digitizacion/historial?')?slowHist.promise:undefined);
 const pendingPrepHist=h2.byId('digPreparar').emit('click');
 await flush();
 await flush();
 h2.byId('geoVersion').value=GEO_2;
 h2.ctx.geoRecord=makeGeoRecord(GEO_2,H_GEO_2,S_GEO_2,true);
 await h2.emitWindow(new h2.ctx.Event('d2m-geometry-opened'));
 slowHist.resolve({json:async()=>({registros:[{id:PREP_ID,vigente:true,etapa:'preparada',dibujo_id:'PLANTA_N0',pendientes:1}],versiones:[],seleccion_automatica:false})});
 await pendingPrepHist;
 await settle();
 assert.notEqual(h2.byId('digHistorial').value,PREP_ID,'Historial antiguo de G1 no autoselecciona su versión bajo G2');

 // 7. Concurrencia por edición de fuente, plano, tolerancias y entradas [u, v] durante solicitudes en vuelo
 const h3=createHarness();
 await h3.emitWindow(new h3.ctx.Event('d2m-case'));

 // 7a) Editar plano/fuente mientras preparar está en vuelo descarta la preparación antigua
 const slowPrepEdit=deferred();
 h3.setHandler(url=>url==='/api/digitizacion/preparar'?slowPrepEdit.promise:undefined);
 const pendingPrepEdit=h3.byId('digPreparar').emit('click');
 await flush();
 h3.byId('digDibujoId').value='DETALLE_EDITADO';
 await h3.byId('digDibujoId').emit('input');
 assert.equal(h3.byId('digPreparar').disabled,false,'Edición durante preparar desbloquea nueva preparación');
 slowPrepEdit.resolve({json:async()=>makePreparedResponse('CASO_A',FP_A,GEO_1,H_GEO_1,S_GEO_1)});
 await pendingPrepEdit;
 await settle();
 assert.match(h3.byId('digHuellaActiva').textContent,/Huella anterior INVALIDADA/);
 assert.equal(h3.byId('digCalcular').disabled,true);

 // 7b) Preparar limpiamente y editar tolerancia o coordenada [u, v] mientras calcular está en vuelo
 h3.setHandler(null);
 await h3.byId('digPreparar').emit('click');
 await settle();
 h3.byId('digAnclaPunto1').value='VA';h3.byId('digAnclaU1').value='0.1';h3.byId('digAnclaV1').value='0.875';
 h3.byId('digAnclaPunto2').value='VB';h3.byId('digAnclaU2').value='0.9';h3.byId('digAnclaV2').value='0.875';
 h3.byId('digAnclaPunto3').value='VC';h3.byId('digAnclaU3').value='0.9';h3.byId('digAnclaV3').value='0.125';
 h3.byId('digPuntoU1').value='0.5';h3.byId('digPuntoV1').value='0.5';h3.byId('digPuntoRel1').value='VA,VB,VC';
 assert.equal(h3.byId('digCalcular').disabled,false);

 const slowCalcTol=deferred();
 let bodyTol=null;
 h3.setHandler((url,body)=>{
  if(url==='/api/digitizacion/calcular'){bodyTol=body;return slowCalcTol.promise;}
  return undefined;
 });
 const pendingCalcTol=h3.byId('digCalcular').emit('click');
 await flush();
 h3.byId('digLimResiduo').value='0.015';
 await h3.byId('digLimResiduo').emit('input');
 slowCalcTol.resolve({json:async()=>makeCalculatedResponse(bodyTol)});
 await pendingCalcTol;
 await settle();
 assert.match(h3.byId('digHuellaActiva').textContent,/Huella anterior INVALIDADA.*límite o tolerancia/);
 assert.equal(h3.collectText(h3.byId('digTablaPuntos')).trim(),'','No restaura resultado calculado con tolerancia anterior');
 assert.equal(h3.byId('digCalcular').disabled,false,'Mantiene preparación vigente de G1 para recalcular con nueva tolerancia');

 // 7c) Editar coordenada normalizada u de ancla mientras calcular está en vuelo descarta respuesta antigua
 const slowCalcUv=deferred();
 let bodyUv=null;
 h3.setHandler((url,body)=>{
  if(url==='/api/digitizacion/calcular'){bodyUv=body;return slowCalcUv.promise;}
  return undefined;
 });
 const pendingCalcUv=h3.byId('digCalcular').emit('click');
 await flush();
 h3.byId('digAnclaU1').value='0.11';
 await h3.byId('digAnclaU1').emit('input');
 slowCalcUv.resolve({json:async()=>makeCalculatedResponse(bodyUv)});
 await pendingCalcUv;
 await settle();
 assert.match(h3.byId('digHuellaActiva').textContent,/Huella anterior INVALIDADA/);
 assert.equal(h3.collectText(h3.byId('digTablaPuntos')).trim(),'');

 console.log('Digitización 353/356 frontend: recepción estructurada, edición normalizada, no-verificación 3 anclas, invalidación, cambio de caso y concurrencia G1/G2/formulario: OK (7 bloques)');
})().catch(err=>{
 console.error(err);
 process.exitCode=1;
});
