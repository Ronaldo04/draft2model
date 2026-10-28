const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/preparacion.js'),'utf8');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
const response=value=>({json:async()=>value,blob:async()=>Buffer.from('PNG SINTETICO')});
const R='a'.repeat(32),C='b'.repeat(32),P='c'.repeat(32),Q='d'.repeat(32),FP='f'.repeat(64);
function packet(id=P,extra={}){return {id,solicitud_id:'e'.repeat(32),caso:'A',expediente_sha256:FP,
 sha256_solicitud:'1'.repeat(64),imagenes:[{id:'CTX0001',rol:'contexto',admite_evidencia:false},{id:'REC0001',rol:'recorte',admite_evidencia:true}],
 recortes:[C],transmision_externa:false,estado:'preparado_sin_envio',aprueba_ingenieria:false,...extra};}
function history(){return {revisiones:[{id:R,vigente:true,datos:{resumen:{paginas_renderizadas:1}}}],
 recortes:[{id:C,vigente:true,datos:{archivo_id:'L0001',pagina:1,etiqueta:'Sintético'}}],
 paquetes:[{id:P,vigente:true},{id:Q,vigente:true}]};}
function harness(){
 const elements={},events={},calls=[],state={emitted:[],errors:[],history:history(),packets:{[P]:packet(),[Q]:packet(Q)}};
 const get=id=>elements[id]??={value:'',checked:false,disabled:false,hidden:false,textContent:'',options:[],events:{},
  get selectedOptions(){return this.options.filter(v=>v.selected);},
  addEventListener(name,fn){this.events[name]=fn;},removeAttribute(name){delete this[name];},reportValidity(){return true;}};
 const context={busy:false,docs:{caso:'A',expediente_sha256:FP,documentos:[{id:'L0001',nombre:'Plano sintético'}]},$:get,URLSearchParams,
  URL:{createObjectURL(){return 'blob:sintetico';},revokeObjectURL(){}},
  CustomEvent:class{constructor(type,options){this.type=type;this.detail=options.detail;}},
  window:{addEventListener(name,fn){events[name]=fn;},dispatchEvent(event){state.emitted.push(event);}},
  options(select,rows){select.options=rows.map(([value,textContent])=>({value,textContent,selected:false,disabled:false}));select.value=rows[0]?.[0]??'';},
  message(text){state.errors.push(text);},action:async fn=>{try{return await fn();}catch(error){state.errors.push(error.message);}},
  changeDocument:async()=>{},openPage:async()=>{},
  api(url,body){
   calls.push({url,body});const parsed=new URL(url,'http://127.0.0.1');
   const custom=state.handler?.(parsed,body);if(custom!==undefined)return custom;
   if(parsed.pathname==='/api/visual/historial')return Promise.resolve(response(parsed.searchParams.get('caso')==='A'?state.history:{revisiones:[],recortes:[],paquetes:[]}));
   if(parsed.pathname==='/api/visual/paquete')return Promise.resolve(response(state.packets[parsed.searchParams.get('version')]));
   if(parsed.pathname==='/api/visual/revisar')return Promise.resolve(response({id:R,resumen:{archivos_con_error:0}}));
   if(parsed.pathname==='/api/visual/preparar')return Promise.resolve(response(packet()));
   if(parsed.pathname==='/api/visual/recortar')return Promise.resolve(response({id:C}));
   if(parsed.pathname==='/api/visual/imagen')return Promise.resolve(response({}));
   throw Error('Ruta inesperada '+parsed.pathname);
  }};
 vm.runInNewContext(code,context);
 async function load(){events['d2m-case']();await flush();}
 async function open(id){get('visualPaquete').value=id;await get('visualPaquete').onchange();}
 function changeCase(){context.docs={caso:'B',expediente_sha256:'9'.repeat(64),documentos:[]};events['d2m-case']();}
 function select(){get('visualRevision').value=R;for(const option of get('visualRecortes').options)option.selected=option.value===C;context.window.visualControls();}
 return {get,events,calls,state,context,load,open,changeCase,select};
}
const tests=[];function test(name,fn){tests.push({name,fn});}

test('historial exige seleccionar revisión y recortes; consultar no prepara',async()=>{
 const h=harness();await h.load();assert.equal(h.get('visualRevision').value,'');assert.equal(h.get('visualRecortes').selectedOptions.length,0);
 assert.equal(h.get('visualPaquete').value,'');assert.equal(h.get('visualPreparar').disabled,true);
 await h.get('visualPreparar').onclick();assert.equal(h.calls.some(c=>c.body),false);
 h.get('visualRevision').value=R;h.context.window.visualControls();assert.equal(h.get('visualPreparar').disabled,true);
 h.select();assert.equal(h.get('visualPreparar').disabled,false);await h.open(P);assert.equal(h.calls.some(c=>c.body),false);
});

test('preparar usa selección exacta y conserva paquete sin envío',async()=>{
 const h=harness();await h.load();h.select();await h.get('visualPreparar').onclick();
 const posts=h.calls.filter(c=>c.body);assert.equal(posts.length,1);assert.equal(posts[0].url,'/api/visual/preparar');
 assert.deepEqual(JSON.parse(JSON.stringify(posts[0].body)),{caso:'A',expediente_sha256:FP,revision:R,recortes:[C]});
 const shown=h.state.emitted.filter(e=>e.detail).at(-1);assert.equal(shown.type,'d2m-visual-package');
 assert.equal(shown.detail.id,P);assert.notEqual(shown.detail.solicitud_id,P,'Solicitud y contenedor tienen identidades separadas');
 assert.equal(shown.detail.transmision_externa,false);assert.equal(shown.detail.aprueba_ingenieria,false);
 assert.match(h.get('visualEstado').textContent,/sin envío/);
});

test('opciones sin vigencia no se seleccionan como fuentes',async()=>{
 const h=harness();h.state.history.revisiones[0].vigente=false;h.state.history.recortes[0].vigente=false;await h.load();
 assert.equal(h.get('visualRevision').options.find(v=>v.value===R).disabled,true);
 assert.equal(h.get('visualRecortes').options.find(v=>v.value===C).disabled,true);assert.equal(h.get('visualPreparar').disabled,true);
});

for(const change of ['caso','version'])for(const rejected of [false,true]){
 test('descarta '+(rejected?'error':'respuesta')+' obsoleto de paquete por '+change,async()=>{
  const h=harness();await h.load();const pending=deferred();h.state.handler=url=>url.pathname==='/api/visual/paquete'&&url.searchParams.get('version')===P?pending.promise:undefined;
  const request=h.open(P);if(change==='caso'){h.changeCase();await flush();}else await h.open(Q);
  const before=h.get('visualDetalle').textContent,errors=h.state.errors.length,emitted=h.state.emitted.length;
  if(rejected)pending.reject(Error('ERROR OBSOLETO'));else pending.resolve(response(packet()));
  await request;await flush();assert.equal(h.get('visualDetalle').textContent,before);assert.equal(h.state.errors.length,errors);assert.equal(h.state.emitted.length,emitted);
 });
}

for(const operation of ['revisar','preparar'])for(const rejected of [false,true]){
 test('descarta '+(rejected?'error':'respuesta')+' obsoleto de '+operation+' por caso',async()=>{
  const h=harness();await h.load();h.select();const pending=deferred();h.state.handler=url=>url.pathname==='/api/visual/'+operation?pending.promise:undefined;
  const request=h.get(operation==='revisar'?'visualRevisar':'visualPreparar').onclick();h.changeCase();await flush();
  const before=h.get('visualEstado').textContent,errors=h.state.errors.length;
  if(rejected)pending.reject(Error('ERROR OBSOLETO'));else pending.resolve(response(operation==='revisar'?{id:R,resumen:{archivos_con_error:0}}:packet()));
  await request;await flush();assert.equal(h.get('visualEstado').textContent,before);assert.equal(h.state.errors.length,errors);
 });
}

test('descarta estado obsoleto si cambia caso durante listado posterior a revisar',async()=>{
 const h=harness();await h.load();const pending=deferred();h.state.handler=url=>url.pathname==='/api/visual/historial'&&url.searchParams.get('caso')==='A'?pending.promise:undefined;
 const request=h.get('visualRevisar').onclick();await flush();h.changeCase();await flush();const before=h.get('visualEstado').textContent;
 pending.resolve(response(history()));await request;await flush();assert.equal(h.get('visualEstado').textContent,before);
});

test('cambio de caso limpia paquete y evento; historial no relanza acciones',async()=>{
 const h=harness();await h.load();await h.open(P);h.changeCase();await flush();
 assert.equal(h.get('visualDetalle').textContent,'');assert.equal(h.get('visualPreparar').disabled,true);
 assert.equal(h.state.emitted.at(-1).detail,null);assert.equal(h.calls.some(c=>c.body),false);
});

(async()=>{let failures=0;for(const {name,fn} of tests){try{await fn();console.log('OK '+name);}catch(error){failures++;console.error('FAIL '+name+'\n'+error.stack);}}
 console.log(`${tests.length-failures}/${tests.length} comprobaciones de preparación correctas`);if(failures)process.exitCode=1;
})().catch(error=>{console.error(error);process.exitCode=1;});
