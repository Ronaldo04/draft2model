// app.js y conversion.js reales en un mismo contexto, con HTTP/DOM simulados.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const E='1'.repeat(32),C='2'.repeat(32),D='3'.repeat(32),G='4'.repeat(32),FP='a'.repeat(64);
const flush=()=>new Promise(resolve=>setImmediate(resolve));async function settle(){await flush();await flush();}
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
function response(value){return {ok:true,json:async()=>value};}
function conversion(id=C){return {id,caso:'A',extraccion:E,expediente_sha256:FP,huella_conversion:'b'.repeat(64),sha256_geometria:'c'.repeat(64),
 manifiesto:{contrato:'draft2model.conversion_geometria',caso:'A',declaracion:'Solo prueba de cliente'},
 geometria:{revision:{estado:'borrador',aprobacion:null}},trazabilidad:{aprobacion_ingenieria:null},estado:'borrador',aprobacion:null,vigente:true};}
function harness(){
 const elements={},events={},state={calls:[],records:{[C]:conversion(),[D]:conversion(D)},rows:[{id:C,vigente:true},{id:D,vigente:true}],emitted:[],geo:[]};
 function element(){return {value:'',textContent:'',disabled:false,checked:false,hidden:false,style:{},children:[],events:{},files:[],
  classList:{toggle(){}},parentElement:{classList:{toggle(){}}},append(...v){this.children.push(...v);},replaceChildren(...v){this.children=v;},
  setAttribute(){},removeAttribute(){},addEventListener(name,fn){this.events[name]=fn;},checkValidity(){return true;},reportValidity(){return true;},click(){}};}
 const get=id=>elements[id]??=element();const window={addEventListener(type,fn){(events[type]??=[]).push(fn);},dispatchEvent(event){state.emitted.push(event);for(const fn of events[event.type]||[])fn(event);}};
 const context={window,document:{getElementById:get,querySelector(){return {content:'sesion'};},createElement:element},URLSearchParams,
  CustomEvent:class{constructor(type,options){this.type=type;this.detail=options.detail;}},Event:class{constructor(type){this.type=type;}},
  URL:{createObjectURL(){return 'blob:simulado';},revokeObjectURL(){}},Blob,
  fetch(url,init={}){const parsed=new URL(url,'http://127.0.0.1'),body=init.body?JSON.parse(init.body):undefined;state.calls.push({url,body});
   const custom=state.handler?.(parsed,body);if(custom!==undefined)return custom;
   if(parsed.pathname==='/api/casos')return Promise.resolve(response({casos:[]}));
   if(parsed.pathname==='/api/conversiones')return Promise.resolve(response({versiones:state.rows}));
   if(parsed.pathname==='/api/conversion')return Promise.resolve(response(state.records[parsed.searchParams.get('version')]));
   if(parsed.pathname==='/api/version')return Promise.resolve(response({expediente_sha256:FP,datos:{candidatos:[{id:'C001',tipo:'cota',revision:{estado:'revisado',historial:[]}}]}}));
   if(parsed.pathname==='/api/conversion/crear'){
    const value=conversion();value.manifiesto=JSON.parse(body.manifiesto_json);state.records[C]=value;return Promise.resolve(response(value));
   }
   if(parsed.pathname==='/api/conversion/importar-geometria'){
    state.geo=[G];return Promise.resolve(response({caso:'A',conversion:body.version,geometria:G,expediente_sha256:FP,estado:'borrador',aprobacion:null,disponible_para_modelado:false}));
   }
   if(parsed.pathname==='/api/geometrias')return Promise.resolve(response({versiones:state.geo}));
   if(parsed.pathname==='/api/geometria')return Promise.resolve(response({datos:{revision:{estado:'borrador',aprobacion:null}},huella:'h',
    metadatos:{},comprobacion:{correcta:true,validacion:{consistente:true,faltantes:[],datos_sinteticos:true,disponible_para_modelado:false}}}));
   throw Error('Ruta inesperada '+parsed.pathname);
  }};
 vm.createContext(context);for(const name of ['app','conversion'])vm.runInContext(fs.readFileSync(path.join(__dirname,`../draft2model/revision_web/${name}.js`),'utf8'),context,{filename:name+'.js'});
 function setCase(caso='A',fp=FP){vm.runInContext(`docs=${JSON.stringify({caso,expediente_sha256:fp,versiones:[E],documentos:[],geometrias:[]})}`,context);window.dispatchEvent(new context.Event('d2m-case'));}
 async function init(){await settle();setCase();await settle();}
 async function open(id=C){get('conversionVersion').value=id;await get('conversionVersion').onchange();await settle();}
 async function select(){get('conversionExtraccion').value=E;await get('conversionExtraccion').onchange();await settle();}
 return {get,state,context,window,setCase,init,open,select};
}
const tests=[];function test(name,fn){tests.push({name,fn});}

test('selección y manifiesto físicos explícitos, historial sin crear ni importar',async()=>{
 const h=harness();await h.init();assert.equal(h.get('conversionExtraccion').value,'');assert.equal(h.get('conversionManifiesto').value,'');
 assert.equal(h.get('conversionCrear').disabled,true);assert.equal(h.get('conversionImportar').disabled,true);await h.get('conversionActualizar').onclick();
 assert.equal(h.state.calls.some(c=>c.body),false);
});

test('crear conserva manifiesto declarado y requiere importación separada',async()=>{
 const h=harness();await h.init();await h.select();const text=JSON.stringify(conversion().manifiesto);h.get('conversionManifiesto').value=text;h.get('conversionManifiesto').events.input();
 await h.get('conversionCrear').onclick();await settle();const posts=h.state.calls.filter(c=>c.body);
 assert.equal(posts.length,1);assert.equal(posts[0].url,'/api/conversion/crear');assert.equal(posts[0].body.manifiesto_json,text);assert.equal(posts[0].body.extraccion,E);
 assert.equal(h.get('conversionImportar').disabled,true);assert.equal(h.state.emitted.some(e=>e.type==='d2m-geometry-created'),false);
});

test('confirmar importa borrador y app refresca geometría sin aprobar',async()=>{
 const h=harness();await h.init();await h.open();await h.get('conversionImportar').onclick();assert.equal(h.state.calls.some(c=>c.body),false);
 h.get('conversionConfirmar').checked=true;h.get('conversionConfirmar').events.input();assert.equal(h.get('conversionImportar').disabled,false);
 await h.get('conversionImportar').onclick();await settle();const post=h.state.calls.find(c=>c.url==='/api/conversion/importar-geometria');
 assert.deepEqual(post.body,{caso:'A',version:C,expediente_sha256:FP,huella_conversion:'b'.repeat(64),confirmacion_explicita:true});
 assert.equal(h.get('conversionConfirmar').checked,false);assert.equal(h.get('geoVersion').value,G);assert.equal(h.get('geoConfirmar').checked,false);assert.equal(h.get('geoAprobar').disabled,true);
 assert.equal(JSON.parse(h.get('geoJson').value).revision.aprobacion,null);assert.equal(h.state.calls.some(c=>/aprobar|etabs|proveedor/.test(c.url)),false);
});

test('editar manifiesto invalida confirmación/importación del snapshot',async()=>{
 const h=harness();await h.init();await h.open();h.get('conversionConfirmar').checked=true;h.get('conversionManifiesto').value+=' ';h.get('conversionManifiesto').events.input();
 assert.equal(h.get('conversionConfirmar').checked,false);assert.equal(h.get('conversionImportar').disabled,true);h.get('conversionConfirmar').checked=true;await h.get('conversionImportar').onclick();
 assert.equal(h.state.calls.some(c=>c.body),false);
});

for(const change of ['caso','version'])for(const reject of [false,true])test('descarta '+(reject?'error':'respuesta')+' de conversión obsoleta por '+change,async()=>{
 const h=harness();await h.init();const pending=deferred();h.state.handler=url=>url.pathname==='/api/conversion'&&url.searchParams.get('version')===C?pending.promise:undefined;
 const request=h.open();if(change==='caso'){h.setCase('B','9'.repeat(64));await settle();}else await h.open(D);
 const before=h.get('conversionDetalle').textContent,message=h.get('mensaje').textContent;
 if(reject)pending.reject(Error('ERROR OBSOLETO'));else pending.resolve(response(conversion()));await request;
 assert.equal(h.get('conversionDetalle').textContent,before);assert.equal(h.get('mensaje').textContent,message);
});

test('relistado inválido limpia conversión e importación',async()=>{
 const h=harness();await h.init();await h.open();h.get('conversionConfirmar').checked=true;h.state.rows=[{id:C,vigente:false}];await h.get('conversionActualizar').onclick();
 assert.equal(h.get('conversionDetalle').textContent,'');assert.equal(h.get('conversionImportar').disabled,true);assert.equal(h.get('conversionConfirmar').checked,false);
});

test('importación tardía de otro caso no refresca geometría actual',async()=>{
 const h=harness();await h.init();await h.open();const pending=deferred();h.state.handler=url=>url.pathname==='/api/conversion/importar-geometria'?pending.promise:undefined;
 h.get('conversionConfirmar').checked=true;const request=h.get('conversionImportar').onclick();h.setCase('B','9'.repeat(64));await settle();
 pending.resolve(response({caso:'A',conversion:C,geometria:G,expediente_sha256:FP,estado:'borrador',aprobacion:null,disponible_para_modelado:false}));await request;await settle();
 assert.equal(h.state.emitted.some(e=>e.type==='d2m-geometry-created'),false);assert.equal(h.get('conversionImportar').disabled,true);
});

function prepararMigracion(h){const data={version_contrato:'0.1.0',revision:{estado:'borrador',aprobacion:null}};const record={datos:data,huella:'b'.repeat(64),sha256_geometria:'c'.repeat(64),expediente_sha256:FP,comprobacion:{correcta:true,validacion:{consistente:true,faltantes:[]}}};vm.runInContext(`geoRecord=${JSON.stringify(record)}`,h.context);h.get('geoVersion').value=G;h.get('geoJson').value=JSON.stringify(data,null,2);for(const id of ['geoRevisor','geoFecha','geoMotivo'])h.get(id).value='declarado';vm.runInContext('geoControls()',h.context);}
test('migración crea hija explícita y no aprobación',async()=>{const h=harness();await h.init();prepararMigracion(h);assert.equal(h.get('geoMigrarSuperficies').disabled,false);h.state.handler=(url,body)=>{if(url.pathname==='/api/geometria/migrar-superficies'){h.state.geo=[D];return Promise.resolve(response({id:D}));}};await h.get('geoMigrarSuperficies').onclick();const posts=h.state.calls.filter(c=>c.body);assert.equal(posts.length,1);assert.equal(posts[0].url,'/api/geometria/migrar-superficies');assert.equal(posts[0].body.version,G);assert.equal(posts[0].body.huella,'b'.repeat(64));assert.equal(posts[0].body.confirmacion_explicita,undefined);assert.equal(h.get('geoVersion').value,D);assert.equal(h.get('geoMigrarSuperficies').disabled,true);});
test('migración descarta resultado tardío al cambiar de caso',async()=>{const h=harness();await h.init();prepararMigracion(h);const pending=deferred();h.state.handler=url=>url.pathname==='/api/geometria/migrar-superficies'?pending.promise:undefined;const running=h.get('geoMigrarSuperficies').onclick();h.setCase('B');await settle();const before=h.state.calls.filter(c=>c.url.startsWith('/api/geometrias')).length;pending.resolve(response({id:D}));await running;assert.equal(h.state.calls.filter(c=>c.url.startsWith('/api/geometrias')).length,before);});
(async()=>{let failures=0;for(const {name,fn} of tests){try{await fn();console.log('OK '+name);}catch(error){failures++;console.error('FAIL '+name+'\n'+error.stack);}}
 console.log(`${tests.length-failures}/${tests.length} comprobaciones de conversión correctas`);if(failures)process.exitCode=1;
})().catch(error=>{console.error(error);process.exitCode=1;});
