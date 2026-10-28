// Cliente real compartido: app + respuestas + proveedor; sin navegador/red/clave.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const P='1'.repeat(32),J='2'.repeat(32),K='3'.repeat(32),R='4'.repeat(32),FP='a'.repeat(64),SHA='b'.repeat(64);
const response=value=>({ok:true,json:async()=>value}),settle=async()=>{await new Promise(setImmediate);await new Promise(setImmediate);};
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
function job(id=J,estado='preparado',mode=null){return {id,caso:'A',paquete:P,expediente_sha256:FP,modelo_declarado:'fixture-vision',opciones:{detalle:'low',max_tokens:512,timeout_s:30},huella_preparacion:SHA,sha256_solicitud:SHA,estado,vigente:true,requiere_recuperacion:estado==='incierto',modo:mode,proveedor_declarado:mode==='real'?'openai':'simulado',llamada_real_acreditada:mode==='real'&&estado==='completado_verificado',costo_estimado:null,observado:{usage:null},respuesta_visual:estado==='completado_verificado'?{id:R,sha256_extraccion:SHA}:null,aprueba_ingenieria:false,aprueba_resultados:false};}
function visual(current){return {id:R,caso:'A',paquete:P,expediente_sha256:FP,sha256_extraccion:SHA,extraccion:{candidatos:[]},proveedor_declarado:current.proveedor_declarado,modelo_declarado:current.modelo_declarado,modo_prueba:current.modo==='transporte_prueba_python',origen:'proveedor_verificado',trabajo_proveedor:current.id,llamada_real_acreditada:current.llamada_real_acreditada,transmision_externa:current.llamada_real_acreditada,traslado_permitido:current.modo==='real',estado:'pendiente_revision',aprueba_ingenieria:false};}
function harness(){const elements={},events={},timers=new Map(),state={calls:[],jobs:{[J]:job(),[K]:job(K)},rows:[J,K],responses:[],emitted:[]};let timerID=0,uuid=0;
 function element(){return {value:'',textContent:'',disabled:false,checked:false,hidden:false,style:{},children:[],events:{},files:[],classList:{toggle(){}},parentElement:{classList:{toggle(){}}},append(...v){this.children.push(...v);},replaceChildren(...v){this.children=v;this.value=v[0]?.value??'';},setAttribute(){},removeAttribute(){},addEventListener(k,f){this.events[k]=f;},checkValidity(){return true;},reportValidity(){return true;}};}
 const get=id=>{if(!elements[id]){elements[id]=element();if(id==='proveedorTipo')Object.defineProperty(elements[id],'selectedOptions',{get(){return [{dataset:{detalleAuto:['gemini','anthropic','fixture_auto'].includes(this.value)?'true':'false'}}];}});}return elements[id];},window={addEventListener(k,f){(events[k]??=[]).push(f);},dispatchEvent(e){state.emitted.push(e);for(const f of events[e.type]||[])f(e);}};
 const context={window,document:{getElementById:get,querySelector(){return {content:'session'};},createElement:element},URLSearchParams,Blob,crypto:{randomUUID(){return (++uuid).toString(16).padStart(32,'0');}},
  CustomEvent:class{constructor(type,opts){this.type=type;this.detail=opts.detail;}},Event:class{constructor(type){this.type=type;}},URL:{revokeObjectURL(){}},setTimeout(fn){const id=++timerID;timers.set(id,fn);return id;},clearTimeout(id){timers.delete(id);},
  fetch(url,init={}){const parsed=new URL(url,'http://localhost'),body=init.body?JSON.parse(init.body):undefined;state.calls.push({url,body});const special=state.handler?.(parsed,body);if(special!==undefined)return special;
   switch(parsed.pathname){
    case '/api/casos':return Promise.resolve(response({casos:[]}));
    case '/api/respuestas':return Promise.resolve(response({versiones:state.responses.map(v=>({id:v.id,vigente:true}))}));
    case '/api/respuesta':return Promise.resolve(response(state.responses.find(v=>v.id===parsed.searchParams.get('version'))));
    case '/api/proveedor/trabajos':return Promise.resolve(response({trabajos:state.rows.map(id=>state.jobs[id])}));
    case '/api/proveedor/trabajo':return Promise.resolve(response(state.jobs[parsed.searchParams.get('trabajo')]));
    case '/api/proveedor/preparar':state.jobs[J]=job();return Promise.resolve(response(state.jobs[J]));
    case '/api/proveedor/ejecutar':state.jobs[body.trabajo]=job(body.trabajo,'en_ejecucion','real');return Promise.resolve(response(state.jobs[body.trabajo]));
    case '/api/proveedor/recuperar':state.jobs[body.trabajo]=job(body.trabajo,'incierto_resuelto','real');return Promise.resolve(response(state.jobs[body.trabajo]));
    case '/api/respuestas/vincular-proveedor':{const value=visual(state.jobs[body.trabajo]);state.responses=[value];return Promise.resolve(response(value));}
    default:throw Error('Ruta inesperada '+parsed.pathname);
   }
  }};
 vm.createContext(context);for(const name of ['app','respuestas','proveedor'])vm.runInContext(fs.readFileSync(path.join(__dirname,`../draft2model/revision_web/${name}.js`),'utf8'),context,{filename:name+'.js'});
 function setCase(caso='A'){vm.runInContext(`docs=${JSON.stringify({caso,expediente_sha256:FP,versiones:[],documentos:[],geometrias:[]})}`,context);window.dispatchEvent(new context.Event('d2m-case'));}
 function packet(id=P){window.dispatchEvent(new context.CustomEvent('d2m-visual-package',{detail:{id,caso:'A',expediente_sha256:FP,solicitud_id:K,sha256_solicitud:SHA,estado:'preparado_sin_envio',transmision_externa:false,aprueba_ingenieria:false}}));}
 function fill(){packet();for(const [id,value]of Object.entries({proveedorModelo:'fixture-vision',proveedorTokens:'512',proveedorDetalle:'low',proveedorTimeout:'30'})){get(id).value=value;get(id).events.input();}}
 async function init(){await settle();setCase();await settle();}
 async function open(id=J){get('proveedorVersion').value=id;await get('proveedorVersion').onchange();await settle();}
 async function tick(){const entry=timers.entries().next().value;if(!entry)return false;timers.delete(entry[0]);entry[1]();await settle();return true;}
 return {get,state,context,window,timers,setCase,packet,fill,init,open,tick};
}
const tests=[];const test=(name,fn)=>tests.push({name,fn});
test('preparación exige selección y opciones explícitas; historial solo consulta',async()=>{
 const h=harness();await h.init();assert.equal(h.get('proveedorModelo').value,'');assert.equal(h.get('proveedorPreparar').disabled,true);await h.get('proveedorActualizar').onclick();await h.get('proveedorPreparar').onclick();assert.equal(h.state.calls.some(c=>c.body),false);h.fill();assert.equal(h.get('proveedorPreparar').disabled,false);
});
test('preparación preserva misma clave tras fallo de red y no ejecuta',async()=>{
 const h=harness();await h.init();h.fill();let attempts=0;h.state.handler=(url)=>url.pathname==='/api/proveedor/preparar'&&++attempts===1?Promise.reject(Error('red simulada')):undefined;
 await h.get('proveedorPreparar').onclick();await h.get('proveedorPreparar').onclick();const posts=h.state.calls.filter(c=>c.body);assert.equal(posts.length,2);assert.deepEqual(posts[0].body,posts[1].body);assert.equal(posts[0].body.modelo,'fixture-vision');assert.equal(h.get('proveedorEjecutar').disabled,true);assert.match(h.get('proveedorEstado').textContent,/PLAN LOCAL/);
 h.get('proveedorTokens').value='600';h.get('proveedorTokens').events.input();await h.get('proveedorPreparar').onclick();assert.notEqual(h.state.calls.filter(c=>c.body)[2].body.clave_solicitud,posts[0].body.clave_solicitud);
});
test('ejecutar requiere confirmación exacta; editar opciones la invalida',async()=>{
 const h=harness();await h.init();h.fill();await h.open();await h.get('proveedorEjecutar').onclick();assert.equal(h.state.calls.some(c=>c.body),false);
 h.get('proveedorConfirmar').checked=true;h.get('proveedorConfirmar').events.input();assert.equal(h.get('proveedorEjecutar').disabled,false);
 h.get('proveedorTokens').value='600';h.get('proveedorTokens').events.input();assert.equal(h.get('proveedorConfirmar').checked,false);assert.equal(h.get('proveedorEjecutar').disabled,true);
 h.get('proveedorTokens').value='512';h.get('proveedorTokens').events.input();h.get('proveedorConfirmar').checked=true;await h.get('proveedorEjecutar').onclick();
 assert.deepEqual(h.state.calls.find(c=>c.body).body,{caso:'A',trabajo:J,huella_preparacion:SHA,expediente_sha256:FP,confirmacion_explicita:true});assert.equal(h.timers.size,1);assert.match(h.get('proveedorEstado').textContent,/transmisión posible/);
});
test('sondeo acotado solo activo, conserva paneles y no relanza',async()=>{
 const h=harness();await h.init();h.state.jobs[J]=job(J,'en_ejecucion','real');await h.open();h.get('respuestaDetalle').textContent='CONSERVADO';
 for(let n=0;n<30;n++)assert.equal(await h.tick(),true);assert.equal(h.timers.size,0);assert.match(h.get('proveedorEstado').textContent,/30 consultas/);assert.equal(h.get('respuestaDetalle').textContent,'CONSERVADO');assert.equal(h.state.calls.some(c=>c.body),false);
 h.state.jobs[J]=job(J,'completado_verificado','real');await h.get('proveedorActualizar').onclick();assert.equal(h.timers.size,0);assert.match(h.get('proveedorEstado').textContent,/llamada acreditada/);
});
test('mismo estado consultado conserva confirmación y no publica cambios ajenos',async()=>{
 const h=harness();await h.init();h.fill();await h.open();h.get('proveedorConfirmar').checked=true;h.get('proveedorConfirmar').events.input();const count=h.state.emitted.length;await h.get('proveedorActualizar').onclick();assert.equal(h.get('proveedorConfirmar').checked,true);assert.equal(h.state.emitted.length,count);
 h.state.jobs[J]=job(J,'incierto','real');await h.get('proveedorActualizar').onclick();assert.equal(h.get('proveedorConfirmar').checked,false);assert.equal(h.get('proveedorEjecutar').disabled,true);
});
test('recuperación explícita cierra sin reenvío',async()=>{
 const h=harness();await h.init();h.state.jobs[J]=job(J,'incierto','real');await h.open();await h.get('proveedorRecuperar').onclick();assert.equal(h.state.calls.some(c=>c.body),false);
 h.get('proveedorConfirmarRecuperar').checked=true;await h.get('proveedorRecuperar').onclick();assert.deepEqual(h.state.calls.find(c=>c.body).body,{caso:'A',trabajo:J,huella_preparacion:SHA,confirmacion_explicita:true,resolucion:'cerrar_sin_reintento'});assert.match(h.get('proveedorEstado').textContent,/incierto_resuelto/);assert.equal(h.timers.size,0);
});
for(const mode of ['real','transporte_prueba_python'])test('vínculo separado conserva origen '+mode+' y no importa',async()=>{
 const h=harness();await h.init();h.state.jobs[J]=job(J,'completado_verificado',mode);await h.open();await h.get('proveedorImportar').onclick();assert.equal(h.state.calls.some(c=>c.body),false);
 h.get('proveedorConfirmarVincular').checked=true;await h.get('proveedorImportar').onclick();await settle();const posts=h.state.calls.filter(c=>c.body);assert.equal(posts.length,1);assert.equal(posts[0].url,'/api/respuestas/vincular-proveedor');assert.equal(posts[0].body.huella_preparacion,SHA);assert.equal(h.state.emitted.filter(e=>e.type==='d2m-response-created').length,1);
 assert.equal(h.get('respuestaVersion').value,R);assert.equal(h.get('respuestaImportar').disabled,true);assert.match(h.get('respuestaEstado').textContent,mode==='real'?/transmisión real acreditada/:/PRUEBA SINTÉTICA/);assert.equal(h.state.calls.some(c=>c.url==='/api/respuesta/importar'),false);
});
for(const change of ['caso','version'])for(const reject of [false,true])test('descarta '+(reject?'error':'estado')+' obsoleto por '+change,async()=>{
 const h=harness();await h.init();const pending=deferred();h.state.handler=url=>url.pathname==='/api/proveedor/trabajo'&&url.searchParams.get('trabajo')===J?pending.promise:undefined;const running=h.open();
 if(change==='caso'){h.setCase('B');await settle();}else await h.open(K);const before=h.get('proveedorEstado').textContent;if(reject)pending.reject(Error('OBSOLETO'));else pending.resolve(response(job(J,'en_ejecucion','real')));await running;assert.equal(h.get('proveedorEstado').textContent,before);assert.equal(h.timers.size,0);
});
test('cambio de paquete invalida confirmación y preparación tardía',async()=>{
 const h=harness();await h.init();h.fill();const pending=deferred();h.state.handler=url=>url.pathname==='/api/proveedor/preparar'?pending.promise:undefined;const running=h.get('proveedorPreparar').onclick();h.packet(K);pending.resolve(response(job()));await running;assert.equal(h.get('proveedorDatos').textContent,'');assert.equal(h.get('proveedorEjecutar').disabled,true);
});
test('cambio de caso descarta vínculo tardío sin evento',async()=>{
 const h=harness();await h.init();const completed=job(J,'completado_verificado','real');h.state.jobs[J]=completed;await h.open();h.get('proveedorConfirmarVincular').checked=true;
 const pending=deferred();h.state.handler=url=>url.pathname==='/api/respuestas/vincular-proveedor'?pending.promise:undefined;const running=h.get('proveedorImportar').onclick();h.setCase('B');pending.resolve(response(visual(completed)));await running;assert.equal(h.state.emitted.some(e=>e.type==='d2m-response-created'),false);
});
test('proveedor distinto invalida confirmación y forma una preparación nueva',async()=>{const h=harness();await h.init();h.fill();await h.open();h.get('proveedorConfirmar').checked=true;h.get('proveedorTipo').value='gemini';h.get('proveedorTipo').events.input();assert.equal(h.get('proveedorConfirmar').checked,false);assert.equal(h.get('proveedorEjecutar').disabled,true);assert.equal(h.get('proveedorPreparar').disabled,true);h.get('proveedorDetalle').value='auto';h.get('proveedorDetalle').events.input();assert.equal(h.get('proveedorPreparar').disabled,false);await h.get('proveedorPreparar').onclick();await settle();const first=h.state.calls.filter(c=>c.url==='/api/proveedor/preparar').at(-1).body;assert.equal(first.proveedor,'gemini');h.get('proveedorTipo').value='openai_compatible';h.get('proveedorTipo').events.input();await h.get('proveedorPreparar').onclick();await settle();const second=h.state.calls.filter(c=>c.url==='/api/proveedor/preparar').at(-1).body;assert.equal(second.proveedor,'openai_compatible');assert.notEqual(first.clave_solicitud,second.clave_solicitud);assert.equal(h.state.calls.some(c=>c.url==='/api/proveedor/ejecutar'),false);});
test('capacidad de detalle proviene del catálogo y no del nombre comercial',async()=>{const h=harness();await h.init();h.fill();h.get('proveedorTipo').value='fixture_auto';h.get('proveedorTipo').events.input();assert.equal(h.get('proveedorPreparar').disabled,true);h.get('proveedorDetalle').value='auto';h.get('proveedorDetalle').events.input();assert.equal(h.get('proveedorPreparar').disabled,false);});
(async()=>{for(const {name,fn}of tests){await fn();console.log('OK '+name);}console.log(`${tests.length}/${tests.length} OK`);})().catch(error=>{console.error(error);process.exitCode=1;});
