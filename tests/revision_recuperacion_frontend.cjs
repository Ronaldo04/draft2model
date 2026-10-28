const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/recuperacion.js'),'utf8');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
const response=value=>({json:async()=>value});
const KEY='1'.repeat(32),RESULT='2'.repeat(32),FP='f'.repeat(64);
function row(extra={}){return {clave_solicitud:KEY,mapeo_version:'3'.repeat(32),huella_mapeo:'4'.repeat(64),
 resultados_candidatos:[RESULT],puede_cancelar:false,requiere_recuperacion:true,...extra};}
function harness(){
 const elements={},events={},calls=[],state={pending:[row()],emitted:[],errors:[]};
 const get=id=>elements[id]??={value:'',textContent:'',checked:false,disabled:false,events:{},
  addEventListener(name,fn){this.events[name]=fn;}};
 const context={busy:false,docs:{caso:'A',expediente_sha256:FP},$:get,URLSearchParams,
  CustomEvent:class{constructor(type,options){this.type=type;this.detail=options.detail;}},
  window:{addEventListener(name,fn){events[name]=fn;},dispatchEvent(event){state.emitted.push(event);}},
  options(select,rows){select.options=rows.map(([value,textContent])=>({value,textContent}));select.value=rows[0]?.[0]??'';},
  message(text){state.errors.push(text);},action:async fn=>{try{return await fn();}catch(error){state.errors.push(error.message);}},
  api(url,body){calls.push({url,body});const parsed=new URL(url,'http://127.0.0.1');const custom=state.handler?.(parsed,body);if(custom!==undefined)return custom;
   if(parsed.pathname==='/api/normalizacion/estado')return Promise.resolve(response({caso:parsed.searchParams.get('caso'),expediente_sha256:FP,
    pendientes:parsed.searchParams.get('caso')==='A'?state.pending:[]}));
   if(parsed.pathname==='/api/normalizacion/recuperar'){
    state.pending=[];return Promise.resolve(response(body.resultado===null?{cancelada_sin_resultado:true,clave_solicitud:body.clave_solicitud,aprueba_resultados:false}:
     {resultado:body.resultado,aprueba_resultados:false,conformidad_normativa:'no_evaluada'}));
   }
   throw Error('Ruta inesperada '+parsed.pathname);
  }};
 vm.runInNewContext(code,context);
 async function load(){events['d2m-case']();await get('recuperacionActualizar').onclick();await flush();}   // 293: consulta explícita
 function select(choice=RESULT){get('recuperacionOperacion').value=KEY;get('recuperacionOperacion').onchange();get('recuperacionResultado').value=choice;get('recuperacionResultado').events.input();}
 function confirm(){get('recuperacionConfirmar').checked=true;get('recuperacionConfirmar').events.input();}
 function changeCase(){context.docs={caso:'B',expediente_sha256:'e'.repeat(64)};events['d2m-case']();}
 return {get,state,calls,events,context,load,select,confirm,changeCase};
}
const tests=[];function test(name,fn){tests.push({name,fn});}

test('consultar pendientes no relanza ni selecciona acción automáticamente',async()=>{
 const h=harness();await h.load();await h.get('recuperacionActualizar').onclick();
 assert.equal(h.get('recuperacionOperacion').value,'');assert.equal(h.get('recuperacionResultado').value,'');assert.equal(h.get('recuperacionEjecutar').disabled,true);
 assert.equal(h.calls.every(c=>!c.body),true);assert.equal(h.state.emitted.length,0);
});

test('aceptación exige operación, candidato y confirmación explícita',async()=>{
 const h=harness();await h.load();await h.get('recuperacionEjecutar').onclick();h.select();
 assert.equal(h.get('recuperacionEjecutar').disabled,true);await h.get('recuperacionEjecutar').onclick();assert.equal(h.calls.some(c=>c.body),false);
 h.confirm();assert.equal(h.get('recuperacionEjecutar').disabled,false);await h.get('recuperacionEjecutar').onclick();
 const post=h.calls.find(c=>c.body);assert.equal(post.url,'/api/normalizacion/recuperar');
 assert.deepEqual(JSON.parse(JSON.stringify(post.body)),{caso:'A',expediente_sha256:FP,clave_solicitud:KEY,resultado:RESULT,confirmacion_explicita:true});
 assert.equal(h.get('recuperacionConfirmar').checked,false);const event=h.state.emitted.at(-1);
 assert.equal(event.type,'d2m-result-created');assert.deepEqual(JSON.parse(JSON.stringify(event.detail)),{caso:'A',resultado:RESULT});
 assert.match(h.get('recuperacionEstado').textContent,/Revisión de resultados pendiente/);
});

test('cancelación solo aparece sin candidato y requiere declaración nueva',async()=>{
 const h=harness();h.state.pending=[row({resultados_candidatos:[],puede_cancelar:true})];await h.load();h.select('cancelar');
 assert.equal(h.get('recuperacionResultado').options.some(o=>o.value==='cancelar'),true);assert.equal(h.get('recuperacionEjecutar').disabled,true);
 h.confirm();await h.get('recuperacionEjecutar').onclick();const post=h.calls.find(c=>c.body);
 assert.equal(post.body.resultado,null);assert.equal(post.body.confirmacion_explicita,true);assert.equal(h.state.emitted.length,0);
 assert.match(h.get('recuperacionEstado').textContent,/cancelado sin publicar resultados/);
 const other=harness();await other.load();other.select();assert.equal(other.get('recuperacionResultado').options.some(o=>o.value==='cancelar'),false);
});

test('cambiar operación borra confirmación y acción anteriores',async()=>{
 const h=harness();h.state.pending.push(row({clave_solicitud:'9'.repeat(32),resultados_candidatos:[],puede_cancelar:true}));await h.load();h.select();h.confirm();
 h.get('recuperacionOperacion').value='9'.repeat(32);h.get('recuperacionOperacion').onchange();
 assert.equal(h.get('recuperacionConfirmar').checked,false);assert.equal(h.get('recuperacionResultado').value,'');assert.equal(h.get('recuperacionEjecutar').disabled,true);
});

test('cambiar acción exige renovar confirmación',async()=>{
 const h=harness();await h.load();h.select();h.confirm();h.get('recuperacionResultado').value='';h.get('recuperacionResultado').events.input();
 assert.equal(h.get('recuperacionConfirmar').checked,false);
 h.get('recuperacionResultado').value=RESULT;h.get('recuperacionResultado').events.input();assert.equal(h.get('recuperacionEjecutar').disabled,true);
});

for(const operation of ['estado','recuperar'])for(const rejected of [false,true]){
 test('descarta '+(rejected?'error':'respuesta')+' obsoleto de '+operation+' tras cambiar caso',async()=>{
  const h=harness(),pending=deferred();if(operation==='recuperar'){await h.load();h.select();h.confirm();}
  h.state.handler=url=>url.pathname==='/api/normalizacion/'+operation&&
   (operation==='recuperar'||url.searchParams.get('caso')==='A')?pending.promise:undefined;
  let request;if(operation==='estado'){h.events['d2m-case']();request=h.get('recuperacionActualizar').onclick();}else request=h.get('recuperacionEjecutar').onclick();
  h.changeCase();await flush();const before=h.get('recuperacionEstado').textContent,errors=h.state.errors.length;
  if(rejected)pending.reject(Error('ERROR OBSOLETO'));else pending.resolve(response(operation==='estado'?{pendientes:[row()]}:{resultado:RESULT}));
  await request;await flush();assert.equal(h.get('recuperacionEstado').textContent,before);assert.equal(h.state.errors.length,errors);assert.equal(h.state.emitted.length,0);
 });
}

test('última consulta del mismo caso prevalece ante respuestas fuera de orden',async()=>{
 const h=harness(),first=deferred(),second=deferred();let count=0;
 h.state.handler=url=>url.pathname==='/api/normalizacion/estado'?(++count===1?first.promise:second.promise):undefined;
 h.events['d2m-case']();h.get('recuperacionActualizar').onclick();const update=h.get('recuperacionActualizar').onclick();second.resolve(response({pendientes:[]}));await update;
 const before=h.get('recuperacionEstado').textContent;first.resolve(response({pendientes:[row()]}));await flush();
 assert.equal(h.get('recuperacionEstado').textContent,before);assert.equal(h.get('recuperacionOperacion').options.length,1);
});

test('error de recuperación actual no emite resultado y desmarca confirmación',async()=>{
 const h=harness();await h.load();h.select();h.confirm();h.state.handler=url=>url.pathname==='/api/normalizacion/recuperar'?Promise.reject(Error('Fuentes alteradas')):undefined;
 await h.get('recuperacionEjecutar').onclick();assert.equal(h.state.emitted.length,0);assert.equal(h.get('recuperacionConfirmar').checked,false);
 assert.equal(h.get('recuperacionEstado').textContent,'Fuentes alteradas');
});

(async()=>{let failures=0;for(const {name,fn} of tests){try{await fn();console.log('OK '+name);}catch(error){failures++;console.error('FAIL '+name+'\n'+error.stack);}}
 console.log(`${tests.length-failures}/${tests.length} comprobaciones de recuperación correctas`);if(failures)process.exitCode=1;
})().catch(error=>{console.error(error);process.exitCode=1;});
