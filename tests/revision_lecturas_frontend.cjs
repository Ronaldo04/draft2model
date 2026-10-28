const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/lecturas.js'),'utf8');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
const response=data=>({json:async()=>data});
const A='a'.repeat(32),B='b'.repeat(32),FP='f'.repeat(64);
function record(id='1'.repeat(32),extra={}){return {id,caso:'A',analisis:A,expediente_sha256:FP,
 huella_preparacion:'c'.repeat(64),estado:'preparado',vigente:true,tablas:['Story Drifts'],casos:['EST'],
 lectura_verificada:false,modo_ejecucion:'doble',...extra};}
function harness(){
 const elements={},events={},calls=[],state={records:{},emitted:[],errors:[]};let serial=0;
 const get=id=>elements[id]??={value:'',textContent:'',checked:false,disabled:false,events:{},
  addEventListener(name,fn){this.events[name]=fn;}};
 const context={busy:false,docs:{caso:'A',expediente_sha256:FP},$:get,URLSearchParams,
  crypto:{randomUUID(){return (++serial).toString().padStart(32,'0');}},
  setTimeout(){return 1;},clearTimeout(){},
  CustomEvent:class{constructor(type,options){this.type=type;this.detail=options.detail;}},
  window:{addEventListener(name,fn){events[name]=fn;},dispatchEvent(event){state.emitted.push(event);}},
  options(select,rows){select.options=rows.map(([value,textContent])=>({value,textContent}));select.value=rows[0][0];},
  message(text){state.errors.push(text);},
  action:async fn=>{try{return await fn();}catch(error){state.errors.push(error.message);}},
  api(url,body){
   calls.push({url,body});const parsed=new URL(url,'http://127.0.0.1');
   const custom=state.handler?.(parsed,body);if(custom!==undefined)return custom;
   if(parsed.pathname==='/api/lectura/preparar'){
    const created=record(undefined,{caso:body.caso,analisis:body.analisis,expediente_sha256:body.expediente_sha256,
     tablas:body.tablas,casos:body.casos});state.records[created.id]=created;return Promise.resolve(response(created));
   }
   if(parsed.pathname==='/api/lectura/ejecutar'){
    const current=state.records[body.trabajo];state.records[current.id]={...current,estado:'en_ejecucion'};
    return Promise.resolve(response(state.records[current.id]));
   }
   if(parsed.pathname==='/api/lectura/trabajos')return Promise.resolve(response({trabajos:Object.values(state.records)}));
   if(parsed.pathname==='/api/lectura/trabajo')return Promise.resolve(response(state.records[parsed.searchParams.get('trabajo')]));
   throw Error('Ruta inesperada '+parsed.pathname);
  }};
 vm.runInNewContext(code,context);
 function select({analisis=A,tablas='Story Drifts',casos='EST'}={}){
  get('lecturaAnalisis').value=analisis;get('lecturaTablas').value=tablas;get('lecturaCasos').value=casos;
  for(const id of ['lecturaAnalisis','lecturaTablas','lecturaCasos'])get(id).events.input();
 }
 async function open(value){state.records[value.id]=value;get('lecturaVersion').value=value.id;await get('lecturaVersion').onchange();}
 function changeCase(){context.docs={caso:'B',expediente_sha256:'e'.repeat(64)};events['d2m-case']();}
 return {get,events,calls,state,context,select,open,changeCase};
}
const tests=[];function test(name,fn){tests.push({name,fn});}

test('selección exacta y confirmación explícita antes de ejecutar',async()=>{
 const h=harness();assert.equal(h.get('lecturaPreparar').disabled,true);
 await h.get('lecturaPreparar').onclick();assert.equal(h.calls.length,0);
 h.select();await h.get('lecturaPreparar').onclick();
 const prep=h.calls.filter(c=>c.url==='/api/lectura/preparar');assert.equal(prep.length,1);
 assert.deepEqual(JSON.parse(JSON.stringify(prep[0].body)),{caso:'A',analisis:A,tablas:['Story Drifts'],casos:['EST'],expediente_sha256:FP,clave_solicitud:'1'.padStart(32,'0')});
 assert.equal(h.calls.filter(c=>c.url==='/api/lectura/ejecutar').length,0);
 assert.equal(h.get('lecturaEjecutar').disabled,true);
 await h.get('lecturaEjecutar').onclick();assert.equal(h.calls.filter(c=>c.url==='/api/lectura/ejecutar').length,0);
 h.get('lecturaConfirmar').checked=true;h.get('lecturaConfirmar').events.input();assert.equal(h.get('lecturaEjecutar').disabled,false);
 h.get('lecturaCasos').value='AJENO';h.get('lecturaCasos').events.input();assert.equal(h.get('lecturaEjecutar').disabled,true);assert.equal(h.get('lecturaConfirmar').checked,false);
 h.select();h.get('lecturaConfirmar').checked=true;h.get('lecturaConfirmar').events.input();await h.get('lecturaEjecutar').onclick();
 const execution=h.calls.filter(c=>c.url==='/api/lectura/ejecutar');assert.equal(execution.length,1);assert.equal(execution[0].body.confirmacion_explicita,true);
 assert.equal(h.get('lecturaConfirmar').checked,false);
});

test('cambiar análisis, orden de tablas, caso o huella impide ejecutar',async()=>{
 for(const changes of [{analisis:B},{tablas:['Otra','Story Drifts']},{caso:'B'},{expediente_sha256:'e'.repeat(64)}]){
  const h=harness();h.select();await h.open(record(undefined,changes));h.get('lecturaConfirmar').checked=true;h.context.window.readingControls();
  assert.equal(h.get('lecturaEjecutar').disabled,true,JSON.stringify(changes));await h.get('lecturaEjecutar').onclick();
  assert.equal(h.calls.filter(c=>c.url==='/api/lectura/ejecutar').length,0);
 }
});

test('misma clave de preparación tras fallo de red, nueva clave al editar',async()=>{
 const h=harness();h.select();let failed=false;
 h.state.handler=(url)=>{if(url.pathname==='/api/lectura/preparar'&&!failed){failed=true;return Promise.reject(Error('Red interrumpida'));}};
 await h.get('lecturaPreparar').onclick();await h.get('lecturaPreparar').onclick();
 let preparations=h.calls.filter(c=>c.url==='/api/lectura/preparar');assert.equal(preparations.length,2);
 assert.equal(preparations[0].body.clave_solicitud,preparations[1].body.clave_solicitud);
 h.get('lecturaTablas').value='Modal Periods And Frequencies';h.get('lecturaTablas').events.input();await h.get('lecturaPreparar').onclick();
 preparations=h.calls.filter(c=>c.url==='/api/lectura/preparar');assert.notEqual(preparations[2].body.clave_solicitud,preparations[0].body.clave_solicitud);
});

test('consultar historial preparado, en ejecución o aceptado nunca relanza',async()=>{
 for(const estado of ['preparado','en_ejecucion','aceptado']){
  const h=harness();h.select();h.get('lecturaConfirmar').checked=true;await h.open(record(undefined,{estado,lectura_verificada:estado==='aceptado'}));
  assert.equal(h.get('lecturaConfirmar').checked,false);
  assert.equal(h.calls.some(c=>c.body),false);assert.equal(h.state.emitted.length,0);
 }
});

for(const change of ['version','caso'])for(const rejected of [false,true]){
 test('descarta '+(rejected?'error':'respuesta')+' de consulta obsoleta por '+change,async()=>{
  const h=harness(),pending=deferred(),old=record('2'.repeat(32)),current=record('3'.repeat(32));h.select();
  h.state.handler=url=>url.pathname==='/api/lectura/trabajo'&&url.searchParams.get('trabajo')===old.id?pending.promise:undefined;
  const opened=h.open(old);
  if(change==='version')await h.open(current);else{h.changeCase();await flush();}
  const before=h.get('lecturaDetalle').textContent,errors=h.state.errors.length;
  if(rejected)pending.reject(Error('ERROR OBSOLETO'));else pending.resolve(response(old));
  await opened;await flush();assert.equal(h.get('lecturaDetalle').textContent,before);assert.equal(h.state.errors.length,errors);
 });
}

test('descarta éxito de preparar después de cambiar caso',async()=>{
 const h=harness(),pending=deferred();h.select();h.state.handler=url=>url.pathname==='/api/lectura/preparar'?pending.promise:undefined;
 const request=h.get('lecturaPreparar').onclick();h.changeCase();await flush();
 const before=h.get('lecturaDetalle').textContent;pending.resolve(response(record()));await request;await flush();
 assert.equal(h.get('lecturaDetalle').textContent,before);assert.equal(h.get('lecturaVersion').value,'');
});

for(const operation of ['preparar','ejecutar','trabajos']){
 test('descarta error obsoleto de '+operation+' después de cambiar caso',async()=>{
  const h=harness(),pending=deferred();h.select();if(operation==='ejecutar')await h.open(record());
  h.state.handler=url=>url.pathname==='/api/lectura/'+operation?pending.promise:undefined;
  if(operation==='ejecutar')h.get('lecturaConfirmar').checked=true;
  const request=h.get(operation==='preparar'?'lecturaPreparar':operation==='ejecutar'?'lecturaEjecutar':'lecturaActualizar').onclick();
  // El listado del nuevo caso no pertenece a la solicitud suspendida.
  h.state.handler=undefined;h.changeCase();await flush();const errors=h.state.errors.length;
  pending.reject(Error('ERROR OBSOLETO '+operation));await request;await flush();assert.equal(h.state.errors.length,errors);
 });
}

test('descarta error obsoleto de ejecutar después de seleccionar otra versión',async()=>{
 const h=harness(),pending=deferred();h.select();await h.open(record());
 h.state.handler=url=>url.pathname==='/api/lectura/ejecutar'?pending.promise:undefined;
 h.get('lecturaConfirmar').checked=true;const request=h.get('lecturaEjecutar').onclick();
 await h.open(record('4'.repeat(32)));const errors=h.state.errors.length;
 pending.reject(Error('ERROR DE EJECUCIÓN ANTERIOR'));await request;await flush();
 assert.equal(h.state.errors.length,errors);
});

test('d2m-reading solo sale para aceptado vigente verificado del caso y huella actuales',async()=>{
 for(const extra of [{},{estado:'preparado'},{vigente:false},{lectura_verificada:false},{caso:'B'},{expediente_sha256:'e'.repeat(64)}]){
  const h=harness();await h.open(record(undefined,{estado:'aceptado',lectura_verificada:true,...extra}));h.get('lecturaMapear').onclick();
  const allowed=Object.keys(extra).length===0;
  assert.equal(h.state.emitted.length,allowed?1:0,JSON.stringify(extra));
  if(allowed){assert.equal(h.state.emitted[0].type,'d2m-reading');assert.equal(h.state.emitted[0].detail.id,'1'.repeat(32));}
 }
});

(async()=>{let failures=0;for(const {name,fn} of tests){try{await fn();console.log('OK '+name);}catch(error){failures++;console.error('FAIL '+name+'\n'+error.stack);}}
 console.log(`${tests.length-failures}/${tests.length} comprobaciones de lecturas correctas`);if(failures)process.exitCode=1;
})().catch(error=>{console.error(error);process.exitCode=1;});
