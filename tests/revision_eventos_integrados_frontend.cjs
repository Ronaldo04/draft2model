// Cuatro módulos reales, un bus compartido y transporte simulado; sin navegador ni motor.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
async function settle(){await flush();await flush();}
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
const response=value=>({json:async()=>value});
const J='1'.repeat(32),RUN='2'.repeat(32),L='3'.repeat(32),M='4'.repeat(32),R='5'.repeat(32),FP='a'.repeat(64);
function analysis(extra={}){return {id:J,caso:'A',expediente_sha256:FP,corrida_id:RUN,modelo:'6'.repeat(32),aprobacion:'7'.repeat(32),
 huella_preparacion:'b'.repeat(64),huella_modelo:'c'.repeat(64),sha256_aprobacion:'d'.repeat(64),estado:'aceptado',vigente:true,calculo_verificado:true,...extra};}
function reading(extra={}){return {id:L,caso:'A',analisis:RUN,expediente_sha256:FP,huella_preparacion:'e'.repeat(64),
 estado:'preparado',vigente:true,casos:['EST'],tablas:['Story Drifts'],modo_ejecucion:'doble',lectura_verificada:false,...extra};}
function proof(){return {corrida_id:RUN,datos_sinteticos:true,configuracion:{huella:'f'.repeat(64)},sha256_edb_analizado:'0'.repeat(64),version_etabs:'sintético'};}
function mapping(){return {id:M,caso:'A',analisis:RUN,expediente_sha256:FP,huella_mapeo:'h-mapeo',analisis_verificado:proof(),
 mapeo:{revision:{estado:'aprobado',aprobacion:{revisor_declarado:'Revisión propia sintética'}},selectores:[]},previsualizacion:{publicado:false}};}
function result(){return {id:R,caso:'A',expediente_sha256:FP,vigente:true,datos:{datos_sinteticos:true,motor:{nombre:'doble',version:'1'},
 resultados:[{id:'DX',caso:'EST',direccion:'X',ubicacion:'N1',valor:0.001,unidad:'1'}],advertencias:['Prueba sintética'],omisiones:[]}};}
function harness(){
 const elements={},listeners={},calls=[],state={analysis:analysis(),reading:reading(),mapping:mapping(),resultRows:[{id:R,vigente:true}],emitted:[],errors:[],timers:new Map(),blobs:0};let serial=0;
 function element(){return {value:'',textContent:'',checked:false,disabled:false,children:[],events:{},files:[],
  append(...nodes){this.children.push(...nodes);},replaceChildren(...nodes){this.children=nodes;},click(){},
  addEventListener(name,fn){(this.events[name]??=[]).push(fn);},checkValidity(){return true;},reportValidity(){return true;}};}
 const get=id=>elements[id]??=element();
 const window={addEventListener(name,fn){(listeners[name]??=[]).push(fn);},dispatchEvent(event){state.emitted.push(event);for(const fn of listeners[event.type]||[])fn(event);}};
 const context={docs:{caso:'A',expediente_sha256:FP},busy:false,$:get,window,URLSearchParams,Blob,TextEncoder,Uint8Array,
  document:{createElement:element},CustomEvent:class{constructor(type,options){this.type=type;this.detail=options.detail;}},
  URL:{createObjectURL(){state.blobs++;return 'blob:prueba';},revokeObjectURL(){}},
  crypto:{randomUUID(){return (++serial).toString().padStart(32,'0');},subtle:require('node:crypto').webcrypto.subtle},
  setTimeout(fn){const id=++serial;state.timers.set(id,fn);return id;},clearTimeout(id){state.timers.delete(id);},
  options(select,rows){select.options=rows.map(([value,textContent])=>({value,textContent}));select.value=rows[0]?.[0]??'';},
  message(text){state.errors.push(text);},action:async fn=>{try{return await fn();}catch(error){state.errors.push(error.message);}},
  api(url,body){calls.push({url,body});const parsed=new URL(url,'http://127.0.0.1');const custom=state.handler?.(parsed,body);if(custom!==undefined)return custom;
   const routes={
    '/api/analisis/trabajos':{trabajos:[state.analysis]},'/api/analisis/trabajo':state.analysis,
    '/api/lectura/trabajos':{trabajos:[state.reading]},'/api/lectura/trabajo':state.reading,
    '/api/lectura/ejecutar':state.reading,'/api/mapeos':{versiones:[{id:M,vigente:true,estado:'aprobado'}]},
    '/api/mapeo':state.mapping,'/api/mapeo/fuente':proof(),'/api/mapeo/normalizar':{resultado:R},
    '/api/modelos':{versiones:[]},'/api/resultados':{versiones:state.resultRows},'/api/resultado':result()};
   if(!(parsed.pathname in routes))throw Error('Ruta no prevista '+parsed.pathname);return Promise.resolve(response(routes[parsed.pathname]));
  }};
 vm.createContext(context);
 for(const name of ['analisis','lecturas','mapeos','resultados'])vm.runInContext(fs.readFileSync(path.join(__dirname,`../draft2model/revision_web/${name}.js`),'utf8'),context,{filename:name+'.js'});
 function emit(type,detail){window.dispatchEvent(new context.CustomEvent(type,{detail}));}
 window.addEventListener('d2m-result',event=>{state.panelSelection=event.detail;state.reportSelection=event.detail;});
 async function init(){emit('d2m-case');await settle();}
 async function openAnalysis(){get('analisisVersion').value=state.analysis.id;await get('analisisVersion').onchange();await settle();}
 async function openDependents(){
  get('lecturaAnalisis').value=RUN;get('lecturaTablas').value='Story Drifts';get('lecturaCasos').value='EST';
  get('lecturaVersion').value=L;await get('lecturaVersion').onchange();get('lecturaConfirmar').checked=true;window.readingControls();
  get('mapeoVersion').value=M;await get('mapeoVersion').onchange();get('mapeoNormalizarConfirmar').checked=true;window.mappingControls();
 }
 async function openResult(){get('resultadoVersion').value=R;await get('resultadoConsultar').onclick();await settle();}
 return {get,context,state,calls,emit,init,openAnalysis,openDependents,openResult};
}
const tests=[];function test(name,fn){tests.push({name,fn});}

test('actualizar el mismo análisis conserva lectura confirmada y mapeo aprobado propio',async()=>{
 const h=harness();await h.init();await h.openAnalysis();await h.openDependents();
 const detail=h.get('lecturaDetalle').textContent,map=h.get('mapeoJson').value,events=h.state.emitted.filter(e=>e.type==='d2m-analysis').length;
 assert.equal(h.get('lecturaEjecutar').disabled,false);assert.equal(h.get('mapeoNormalizar').disabled,false);
 await h.get('analisisActualizar').onclick();await settle();
 assert.equal(h.state.emitted.filter(e=>e.type==='d2m-analysis').length,events,'La reconsulta no es cambio de identidad');
 assert.equal(h.get('lecturaDetalle').textContent,detail);assert.equal(h.get('lecturaCasos').value,'EST');assert.equal(h.get('lecturaConfirmar').checked,true);
 assert.equal(h.get('lecturaEjecutar').disabled,false);assert.equal(h.get('mapeoJson').value,map);assert.equal(h.get('mapeoNormalizar').disabled,false);
});

test('eventos idénticos repetidos por el bus no descartan consumidores',async()=>{
 const h=harness();await h.init();await h.openAnalysis();await h.openDependents();
 h.emit('d2m-analysis',JSON.parse(JSON.stringify(h.state.analysis)));await settle();
 assert.equal(h.get('lecturaEjecutar').disabled,false);assert.equal(h.get('mapeoNormalizar').disabled,false);
});

test('sondeo del mismo trabajo en ejecución conserva revisión abierta deliberadamente',async()=>{
 const h=harness();h.state.analysis=analysis({estado:'en_ejecucion',calculo_verificado:false});await h.init();await h.openAnalysis();await h.openDependents();
 const timer=[...h.state.timers.entries()][0];assert.ok(timer);h.state.timers.delete(timer[0]);timer[1]();await settle();
 assert.equal(h.get('lecturaEjecutar').disabled,false);assert.equal(h.get('mapeoNormalizar').disabled,false);
});

for(const change of [{id:'8'.repeat(32),corrida_id:'9'.repeat(32)}, {huella_preparacion:'9'.repeat(64)},
 {modelo:'9'.repeat(32)}, {aprobacion:'9'.repeat(32)}, {huella_modelo:'9'.repeat(64)},
 {sha256_aprobacion:'9'.repeat(64)}, {vigente:false,calculo_verificado:false}]){
 test('cambio real de identidad/huella/vigencia invalida dependientes '+Object.keys(change).join('/'),async()=>{
  const h=harness();await h.init();await h.openAnalysis();await h.openDependents();h.state.analysis=analysis(change);await h.openAnalysis();
  assert.equal(h.get('lecturaConfirmar').checked,false);assert.equal(h.get('lecturaDetalle').textContent,'');assert.equal(h.get('lecturaEjecutar').disabled,true);
  assert.equal(h.get('mapeoGuardar').disabled,true);assert.equal(h.get('mapeoNormalizar').disabled,true);assert.equal(h.get('mapeoJson').value,'');
 });
}

test('transición de ejecución a aceptación comunica disponibilidad sin aprobar derivados',async()=>{
 const h=harness();h.state.analysis=analysis({estado:'en_ejecucion',calculo_verificado:false});await h.init();await h.openAnalysis();
 assert.equal(h.get('lecturaAnalisis').value,'');h.state.analysis=analysis();await h.get('analisisActualizar').onclick();await settle();
 assert.equal(h.get('lecturaAnalisis').value,RUN);assert.equal(h.get('lecturaEjecutar').disabled,true);
 assert.equal(h.get('mapeoAnalisis').value,RUN);assert.equal(h.get('mapeoAprobar').disabled,true);assert.equal(h.get('mapeoNormalizar').disabled,true);
});

test('fallo de red al reconsultar mismo análisis no publica cambio ficticio',async()=>{
 const h=harness();await h.init();await h.openAnalysis();await h.openDependents();
 h.state.handler=url=>url.pathname==='/api/analisis/trabajo'?Promise.reject(Error('Red interrumpida')):undefined;
 await h.get('analisisActualizar').onclick();assert.equal(h.get('lecturaEjecutar').disabled,false);assert.equal(h.get('mapeoNormalizar').disabled,false);
 assert.equal(h.state.errors.at(-1),'Red interrumpida');
});

test('cambiar caso o huella de expediente limpia selecciones y no hereda aprobación',async()=>{
 for(const docs of [{caso:'B',expediente_sha256:FP},{caso:'A',expediente_sha256:'9'.repeat(64)}]){
  const h=harness();await h.init();await h.openAnalysis();await h.openDependents();h.context.docs=docs;h.emit('d2m-case');await settle();
  assert.equal(h.get('lecturaConfirmar').checked,false);assert.equal(h.get('lecturaAnalisis').value,'');assert.equal(h.get('mapeoNormalizar').disabled,true);
  h.emit('d2m-analysis',analysis());await settle();assert.equal(h.get('lecturaAnalisis').value,'');assert.equal(h.get('mapeoNormalizar').disabled,true);
 }
});

test('lectura en vuelo recibe su respuesta tras actualizar el mismo análisis',async()=>{
 const h=harness();await h.init();await h.openAnalysis();await h.openDependents();const pending=deferred();
 h.state.handler=url=>url.pathname==='/api/lectura/ejecutar'?pending.promise:undefined;
 const request=h.get('lecturaEjecutar').onclick();await h.get('analisisActualizar').onclick();await settle();
 h.state.reading=reading({estado:'aceptado',lectura_verificada:true});pending.resolve(response(h.state.reading));await request;await settle();
 assert.equal(JSON.parse(h.get('lecturaDetalle').textContent).estado,'aceptado');assert.equal(h.get('lecturaMapear').disabled,false);
});

test('actualizar mismo análisis conserva clave idempotente de normalización',async()=>{
 const h=harness();await h.init();await h.openAnalysis();await h.openDependents();await h.get('mapeoNormalizar').onclick();await settle();
 await h.get('analisisActualizar').onclick();h.get('mapeoNormalizarConfirmar').checked=true;h.context.window.mappingControls();await h.get('mapeoNormalizar').onclick();
 const requests=h.calls.filter(c=>c.url==='/api/mapeo/normalizar');assert.equal(requests.length,2);assert.equal(requests[0].body.clave_solicitud,requests[1].body.clave_solicitud);
});

for(const rows of [[{id:R,vigente:false}],[]]){
 test('relistado limpia resultado abierto '+(rows.length?'sin vigencia':'ausente')+' y sus consumidores',async()=>{
  const h=harness();await h.init();await h.openResult();assert.equal(h.get('resultadoDescargar').disabled,false);
  h.state.resultRows=rows;h.emit('d2m-model-created',{caso:'A'});await settle();
  assert.equal(h.get('resultadoFilas').children.length,0);assert.equal(h.get('resultadoAvisos').children.length,0);assert.equal(h.get('resultadoDescargar').disabled,true);
  assert.equal(h.state.panelSelection,null);assert.equal(h.state.reportSelection,null);const blobs=h.state.blobs;h.get('resultadoDescargar').onclick();assert.equal(h.state.blobs,blobs);
 });
}

test('preferred no vigente no abre detalle y descarta el resultado previo',async()=>{
 const h=harness();await h.init();await h.openResult();const other='9'.repeat(32),before=h.calls.filter(c=>c.url.startsWith('/api/resultado?')).length;
 h.state.resultRows=[{id:R,vigente:true},{id:other,vigente:false}];h.emit('d2m-result-created',{caso:'A',resultado:other});await settle();
 assert.equal(h.get('resultadoVersion').value,other);assert.equal(h.get('resultadoDescargar').disabled,true);assert.equal(h.get('resultadoConsultar').disabled,true);
 assert.equal(h.state.panelSelection,null);assert.equal(h.calls.filter(c=>c.url.startsWith('/api/resultado?')).length,before);
});

test('detalle tardío no restaura un resultado invalidado por relistado',async()=>{
 const h=harness();await h.init();const pending=deferred();h.state.handler=url=>url.pathname==='/api/resultado'?pending.promise:undefined;
 h.get('resultadoVersion').value=R;const request=h.get('resultadoConsultar').onclick();h.state.resultRows=[{id:R,vigente:false}];h.emit('d2m-model-created',{caso:'A'});await settle();
 pending.resolve(response(result()));await request;await settle();assert.equal(h.get('resultadoDescargar').disabled,true);assert.equal(h.state.panelSelection,null);assert.equal(h.get('resultadoFilas').children.length,0);
});

(async()=>{let failures=0;for(const {name,fn} of tests){try{await fn();console.log('OK '+name);}catch(error){failures++;console.error('FAIL '+name+'\n'+error.stack);}}
 console.log(`${tests.length-failures}/${tests.length} comprobaciones de eventos integrados correctas`);if(failures)process.exitCode=1;
})().catch(error=>{console.error(error);process.exitCode=1;});
