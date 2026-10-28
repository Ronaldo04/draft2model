// app.js y respuestas.js reales, DOM/HTTP locales simulados y bus compartido.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const P='1'.repeat(32),R='2'.repeat(32),S='3'.repeat(32),E='4'.repeat(32),FP='a'.repeat(64);
const settle=async()=>{await new Promise(setImmediate);await new Promise(setImmediate);};
const response=value=>({ok:true,json:async()=>value});
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
function record(id=R,test=false){return {id,caso:'A',expediente_sha256:FP,paquete:P,sha256_extraccion:'b'.repeat(64),
 extraccion:{candidatos:[{revision:{estado:'pendiente'}}]},proveedor_declarado:'Local declarado',modelo_declarado:'Sin llamada',modo_prueba:test,
 origen:'respuesta_local_declarada',transmision_externa:false,traslado_permitido:!test,estado:'pendiente_revision',aprueba_ingenieria:false};}
function harness(){const elements={},events={},state={calls:[],rows:[{id:R,vigente:true},{id:S,vigente:true}],records:{[R]:record(),[S]:record(S,true)},emitted:[],versions:[]};
 function element(){return {value:'',textContent:'',disabled:false,checked:false,hidden:false,style:{},children:[],events:{},files:[],classList:{toggle(){}},parentElement:{classList:{toggle(){}}},
  append(...v){this.children.push(...v);},replaceChildren(...v){this.children=v;},setAttribute(){},removeAttribute(){},addEventListener(k,f){this.events[k]=f;},checkValidity(){return true;},reportValidity(){return true;}};}
 const get=id=>elements[id]??=element(),window={addEventListener(k,f){(events[k]??=[]).push(f);},dispatchEvent(e){state.emitted.push(e);for(const f of events[e.type]||[])f(e);}};
 const context={window,document:{getElementById:get,querySelector(){return {content:'session'};},createElement:element},URLSearchParams,Blob,
  CustomEvent:class{constructor(type,options){this.type=type;this.detail=options.detail;}},Event:class{constructor(type){this.type=type;}},URL:{revokeObjectURL(){}},
  fetch(url,init={}){const parsed=new URL(url,'http://localhost'),body=init.body?JSON.parse(init.body):undefined;state.calls.push({url,body});const special=state.handler?.(parsed,body);if(special!==undefined)return special;
   if(parsed.pathname==='/api/casos')return Promise.resolve(response({casos:[]}));
   if(parsed.pathname==='/api/respuestas')return Promise.resolve(response({versiones:state.rows}));
   if(parsed.pathname==='/api/respuesta')return Promise.resolve(response(state.records[parsed.searchParams.get('version')]));
   if(parsed.pathname==='/api/respuesta/registrar'){state.records[R]=record(R,body.modo_prueba);return Promise.resolve(response(state.records[R]));}
   if(parsed.pathname==='/api/respuesta/importar'){state.versions=[E];return Promise.resolve(response({caso:'A',extraccion:E,estado:'pendiente_revision',aprueba_ingenieria:false}));}
   if(parsed.pathname==='/api/documentos')return Promise.resolve(response({caso:'A',expediente_sha256:FP,versiones:state.versions}));
   throw Error('Ruta inesperada '+parsed.pathname);
  }};
 vm.createContext(context);for(const name of ['app','respuestas'])vm.runInContext(fs.readFileSync(path.join(__dirname,`../draft2model/revision_web/${name}.js`),'utf8'),context,{filename:name+'.js'});
 function setCase(caso='A'){vm.runInContext(`docs=${JSON.stringify({caso,expediente_sha256:FP,versiones:[],documentos:[],geometrias:[]})}`,context);window.dispatchEvent(new context.Event('d2m-case'));}
 function packet(id=P){window.dispatchEvent(new context.CustomEvent('d2m-visual-package',{detail:{id,solicitud_id:'f'.repeat(32),caso:'A',expediente_sha256:FP,sha256_solicitud:'c'.repeat(64),estado:'preparado_sin_envio',transmision_externa:false,aprueba_ingenieria:false}}));}
 async function init(){await settle();setCase();await settle();}
 async function open(id=R){get('respuestaVersion').value=id;await get('respuestaVersion').onchange();await settle();}
 function fill(){packet();for(const [id,value]of Object.entries({respuestaJson:'{"solicitud_id":"local"}',respuestaProveedor:'Declarado',respuestaModelo:'Modelo declarado',respuestaModo:'expediente'})){get(id).value=value;get(id).events.input();}}
 return {get,state,context,window,setCase,packet,init,open,fill};
}
const tests=[];const test=(name,fn)=>tests.push({name,fn});
test('selección de paquete y modo explícitos; consultar historial no registra',async()=>{
 const h=harness();await h.init();assert.equal(h.get('respuestaRegistrar').disabled,true);await h.get('respuestaActualizar').onclick();assert.equal(h.state.calls.some(c=>c.body),false);
 h.fill();h.get('respuestaModo').value='';h.get('respuestaModo').events.input();assert.equal(h.get('respuestaRegistrar').disabled,true);await h.get('respuestaRegistrar').onclick();assert.equal(h.state.calls.some(c=>c.body),false);
});
test('registro local conserva declaración y no importa ni transmite',async()=>{
 const h=harness();await h.init();h.fill();await h.get('respuestaRegistrar').onclick();await settle();const posts=h.state.calls.filter(c=>c.body);assert.equal(posts.length,1);
 assert.deepEqual(posts[0].body,{caso:'A',expediente_sha256:FP,paquete:P,respuesta_json:'{"solicitud_id":"local"}',proveedor_declarado:'Declarado',modelo_declarado:'Modelo declarado',modo_prueba:false});
 assert.equal(h.get('respuestaImportar').disabled,true);assert.match(h.get('respuestaEstado').textContent,/declarada/);assert.equal(h.state.emitted.some(e=>e.type==='d2m-extraction-created'),false);
});
test('cuarentena solo con casilla explícita y estado muestra cobertura efectiva (R236)',async()=>{
 const h=harness();await h.init();h.fill();assert.equal(h.get('respuestaCuarentena').disabled,false);assert.equal(h.get('respuestaCuarentena').checked,false);
 h.get('respuestaCuarentena').checked=true;await h.get('respuestaRegistrar').onclick();await settle();
 const post=h.state.calls.find(c=>c.body);assert.equal(post.body.cuarentena,true);
 h.state.records[R]={...record(),candidatos_en_cuarentena:2,cobertura:[{recorte_id:'c6bef19fdeee',estado:'completa',observacion:'',efectiva:{estado:'parcial',candidatos_declarados:19,recuperados:17,en_cuarentena:2,motivo:'m'}}]};
 await h.open();
 assert.match(h.get('respuestaEstado').textContent,/2 candidato\(s\) en cuarentena, sin corregir/);
 assert.match(h.get('respuestaEstado').textContent,/c6bef19f 17\/19 \(parcial; declarada completa\)/);
 h.get('respuestaCuarentena').checked=false;h.state.calls.length=0;await h.get('respuestaRegistrar').onclick();await settle();
 assert.equal('cuarentena' in h.state.calls.find(c=>c.body).body,false);
});
test('importación separada exacta refresca historial pendiente sin aprobar',async()=>{
 const h=harness();await h.init();await h.open();await h.get('respuestaImportar').onclick();assert.equal(h.state.calls.some(c=>c.body),false);
 h.get('respuestaConfirmar').checked=true;h.get('respuestaConfirmar').events.input();await h.get('respuestaImportar').onclick();await settle();
 assert.deepEqual(h.state.calls.find(c=>c.body).body,{caso:'A',expediente_sha256:FP,respuesta:R,sha256_extraccion:'b'.repeat(64),confirmacion_explicita:true});
 assert.equal(h.get('respuestaConfirmar').checked,false);assert.equal(h.get('version').children.some(c=>c.value===E),true);assert.equal(h.get('version').value,'');
 assert.equal(h.state.emitted.filter(e=>e.type==='d2m-extraction-created').length,1);assert.equal(h.state.calls.some(c=>/aprobar|proveedor|etabs/.test(c.url)),false);
});
test('prueba sintética visible y no trasladable, invalidez limpia detalle',async()=>{
 const h=harness();await h.init();await h.open(S);assert.match(h.get('respuestaEstado').textContent,/PRUEBA SINTÉTICA/);h.get('respuestaConfirmar').checked=true;await h.get('respuestaImportar').onclick();assert.equal(h.state.calls.some(c=>c.body),false);
 h.state.rows=[{id:S,vigente:false}];await h.get('respuestaActualizar').onclick();assert.equal(h.get('respuestaDetalle').textContent,'');assert.equal(h.get('respuestaImportar').disabled,true);
});
for(const change of ['caso','version'])for(const reject of [false,true])test('descarta '+(reject?'error':'respuesta')+' tardía por '+change,async()=>{
 const h=harness();await h.init();const pending=deferred();h.state.handler=url=>url.pathname==='/api/respuesta'&&url.searchParams.get('version')===R?pending.promise:undefined;
 const running=h.open();if(change==='caso'){h.setCase('B');await settle();}else await h.open(S);
 const before=h.get('respuestaEstado').textContent;if(reject)pending.reject(Error('ERROR OBSOLETO'));else pending.resolve(response(record()));await running;
 assert.equal(h.get('respuestaEstado').textContent,before);assert.equal(h.get('respuestaDetalle').textContent.includes('ERROR OBSOLETO'),false);
});
test('cambio de paquete descarta archivo y registro en vuelo',async()=>{
 const h=harness();await h.init();h.fill();const pending=deferred();h.state.handler=url=>url.pathname==='/api/respuesta/registrar'?pending.promise:undefined;
 const running=h.get('respuestaRegistrar').onclick();h.packet(S);pending.resolve(response(record()));await running;await settle();assert.equal(h.get('respuestaDetalle').textContent,'');assert.equal(h.get('respuestaJson').value,'');
 const file=deferred();h.get('respuestaArchivo').files=[{size:10,text:()=>file.promise}];const reading=h.get('respuestaArchivo').onchange();h.packet(P);file.resolve('{}');await reading;assert.equal(h.get('respuestaJson').value,'');
});
test('límites locales y cambio de caso impiden evento tras importación tardía',async()=>{
 const h=harness();await h.init();h.packet();h.get('respuestaArchivo').files=[{size:1536*1024+1,text:()=>{throw Error('No leer');}}];await h.get('respuestaArchivo').onchange();assert.match(h.get('respuestaEstado').textContent,/1.5 MiB/);
 await h.open();h.get('respuestaConfirmar').checked=true;const pending=deferred();h.state.handler=url=>url.pathname==='/api/respuesta/importar'?pending.promise:undefined;const running=h.get('respuestaImportar').onclick();h.setCase('B');await settle();pending.resolve(response({caso:'A',extraccion:E,estado:'pendiente_revision',aprueba_ingenieria:false}));await running;
 assert.equal(h.state.emitted.some(e=>e.type==='d2m-extraction-created'),false);
});
test('origen local nunca acredita llamada real y proveedor exige trabajo coherente',async()=>{
 const h=harness();await h.init();h.state.records[R]={...record(),llamada_real_acreditada:true};await h.open();assert.equal(h.get('respuestaDetalle').textContent,'');
 h.state.records[R]={...record(),origen:'proveedor_verificado',trabajo_proveedor:P,llamada_real_acreditada:true,transmision_externa:true};await h.open();assert.match(h.get('respuestaEstado').textContent,/transmisión real acreditada/);
 h.state.records[R]={...h.state.records[R],modo_prueba:true};await h.open();assert.equal(h.get('respuestaDetalle').textContent,'');assert.equal(h.get('respuestaImportar').disabled,true);
});
(async()=>{for(const {name,fn}of tests){await fn();console.log('OK '+name);}console.log(`${tests.length}/${tests.length} OK`);})().catch(error=>{console.error(error);process.exitCode=1;});
