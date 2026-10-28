// app.js y tabular.js reales en un mismo contexto, con HTTP/DOM/archivos simulados.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const T='1'.repeat(32),U='2'.repeat(32),G='4'.repeat(32),FP='a'.repeat(64),H='b'.repeat(64);
const flush=()=>new Promise(resolve=>setImmediate(resolve));async function settle(){for(let i=0;i<4;i++)await flush();}
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
function response(value){return {ok:true,json:async()=>value};}
function file(name,text,size){const bytes=Buffer.from(text);let reads=0;return {name,size:size??bytes.length,get reads(){return reads;},
 text:async()=>{reads++;return text;},arrayBuffer:async()=>{reads++;return bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.length);}};}
function version(id=T,extra={}){return {id,caso:'A',expediente_sha256:FP,huella_tabular:H,formato:'csv',nombre_original:null,archivos:{},
 resumen:{unidad_longitud:'m',niveles:2,nodos:4,muros:4,faltantes:1,procedencia_declarada:'sintetico'},estado:'borrador',aprobacion:null,
 importacion:null,disponible_para_modelado:false,aprueba_geometria:false,aprueba_ingenieria:false,vigente:true,
 geometria:{revision:{estado:'borrador',aprobacion:null}},...extra};}
function harness(){
 const elements={},events={},state={calls:[],records:{[T]:version(),[U]:version(U)},rows:[{id:T,vigente:true,formato:'csv'},{id:U,vigente:true,formato:'csv'}],emitted:[],geo:[]};
 function element(){return {value:'',textContent:'',disabled:false,checked:false,hidden:false,style:{},children:[],events:{},files:[],
  classList:{toggle(){}},parentElement:{classList:{toggle(){}}},append(...v){this.children.push(...v);},replaceChildren(...v){this.children=v;},
  setAttribute(){},removeAttribute(){},addEventListener(name,fn){this.events[name]=fn;},checkValidity(){return true;},reportValidity(){return true;},click(){}};}
 const get=id=>elements[id]??=element();
 const window={addEventListener(type,fn){(events[type]??=[]).push(fn);},dispatchEvent(event){state.emitted.push(event);for(const fn of events[event.type]||[])fn(event);}};
 const context={window,document:{getElementById:get,querySelector(){return {content:'sesion'};},createElement:element},URLSearchParams,btoa,Uint8Array,
  CustomEvent:class{constructor(type,options){this.type=type;this.detail=options.detail;}},Event:class{constructor(type){this.type=type;}},
  URL:{createObjectURL(){return 'blob:simulado';},revokeObjectURL(){}},Blob,
  fetch(url,init={}){const parsed=new URL(url,'http://127.0.0.1'),body=init.body?JSON.parse(init.body):undefined;state.calls.push({url:parsed.pathname,body});
   const custom=state.handler?.(parsed,body);if(custom!==undefined)return custom;
   if(parsed.pathname==='/api/casos')return Promise.resolve(response({casos:[]}));
   if(parsed.pathname==='/api/tabular/historial')return Promise.resolve(response({versiones:state.rows}));
   if(parsed.pathname==='/api/tabular/version')return Promise.resolve(response(state.records[parsed.searchParams.get('version')]));
   if(parsed.pathname==='/api/tabular/crear'){const value=version(T);delete value.geometria;return Promise.resolve(response(value));}
   if(parsed.pathname==='/api/tabular/importar'){state.geo=[G];state.records[T]=version(T,{importacion:{estado:'importada',geometria:G,huella_tabular:H}});
    return Promise.resolve(response({caso:'A',expediente_sha256:FP,tabular:body.version,huella_tabular:body.huella_tabular,geometria:G,estado:'borrador',
     aprobacion:null,disponible_para_modelado:false,aprueba_geometria:false,aprueba_ingenieria:false}));}
   if(parsed.pathname==='/api/geometrias')return Promise.resolve(response({versiones:state.geo}));
   if(parsed.pathname==='/api/geometria')return Promise.resolve(response({datos:{revision:{estado:'borrador',aprobacion:null}},huella:'h',
    metadatos:{},comprobacion:{correcta:true,validacion:{consistente:true,faltantes:[],datos_sinteticos:true,disponible_para_modelado:false}}}));
   throw Error('Ruta inesperada '+parsed.pathname);
  }};
 vm.createContext(context);for(const name of ['app','tabular'])vm.runInContext(fs.readFileSync(path.join(__dirname,`../draft2model/revision_web/${name}.js`),'utf8'),context,{filename:name+'.js'});
 function setCase(caso='A',fp=FP){vm.runInContext(`docs=${JSON.stringify({caso,expediente_sha256:fp,versiones:[],documentos:[],geometrias:[]})}`,context);window.dispatchEvent(new context.Event('d2m-case'));}
 async function init(){await settle();setCase();await settle();}
 async function open(id=T){get('tabularVersion').value=id;await get('tabularVersion').onchange();await settle();}
 function attach(meta,tables,formato='csv'){get('tabularMetadatos').files=meta;get('tabularArchivos').files=tables;get('tabularFormato').value=formato;get('tabularArchivos').events.change();}
 const posts=()=>state.calls.filter(c=>c.body);
 return {get,state,context,window,setCase,init,open,attach,posts};
}
const csvFiles=()=>[file('niveles.csv','id,elevacion\nN1,0\n'),file('nodos.csv','id,x,y\nA,0,0\n'),file('muros.csv','id\nM1\n')];
const metaFile=()=>file('metadatos.json','{"id":"A","unidad_longitud":"m"}');
const tests=[];function test(name,fn){tests.push({name,fn});}

test('validación previa: nombres y tamaños antes de leer, sin POST',async()=>{
 const h=harness();await h.init();assert.equal(h.get('tabularRegistrar').disabled,true);
 const bad=[file('niveles.csv','x'),file('nodos.csv','x'),file('otro.csv','x')];h.attach([metaFile()],bad);
 await h.get('tabularRegistrar').onclick();await settle();assert.equal(h.posts().length,0);assert.match(h.get('tabularEstado').textContent,/exactamente niveles/);
 const big=file('libro.xlsx','PK',17*1024*1024);h.attach([metaFile()],[big],'xlsx');await h.get('tabularRegistrar').onclick();await settle();
 assert.equal(big.reads,0);assert.equal(h.posts().length,0);
 const meta=file('metadatos.txt','{}');h.attach([meta],csvFiles());await h.get('tabularRegistrar').onclick();await settle();assert.equal(meta.reads,0);
});

test('registrar CSV envía bytes exactos y no importa ni emite geometría',async()=>{
 const h=harness();await h.init();const tables=csvFiles();h.attach([metaFile()],tables);assert.equal(h.get('tabularRegistrar').disabled,false);
 await h.get('tabularRegistrar').onclick();await settle();const posts=h.posts();
 assert.equal(posts.length,1);assert.equal(posts[0].url,'/api/tabular/crear');assert.equal(posts[0].body.formato,'csv');
 assert.equal(posts[0].body.metadatos_json,'{"id":"A","unidad_longitud":"m"}');assert.equal(posts[0].body.expediente_sha256,FP);
 assert.deepEqual(posts[0].body.archivos.map(a=>[a.nombre,Buffer.from(a.contenido_base64,'base64').toString()]),[['niveles.csv','id,elevacion\nN1,0\n'],['nodos.csv','id,x,y\nA,0,0\n'],['muros.csv','id\nM1\n']]);
 assert.equal(h.get('tabularVersion').value,T);assert.equal(h.get('tabularImportar').disabled,true);
 assert.equal(h.state.emitted.some(e=>e.type==='d2m-geometry-created'),false);
 assert.match(h.get('tabularEstado').textContent,/contingencia tabular supervisada/);
});

test('importación separada confirmada con huella exacta, evento y refresco geométrico',async()=>{
 const h=harness();await h.init();await h.open();await h.get('tabularImportar').onclick();await settle();assert.equal(h.posts().length,0);
 h.get('tabularConfirmar').checked=true;h.get('tabularConfirmar').events.input();assert.equal(h.get('tabularImportar').disabled,false);
 await h.get('tabularImportar').onclick();await settle();const posts=h.posts();
 assert.equal(posts.length,1);assert.deepEqual(posts[0].body,{caso:'A',expediente_sha256:FP,version:T,huella_tabular:H,confirmacion_explicita:true});
 const event=h.state.emitted.find(e=>e.type==='d2m-geometry-created');assert.equal(event.detail.geometria,G);assert.equal(event.detail.aprobacion,null);
 assert.ok(h.state.calls.some(c=>c.url==='/api/geometrias'));assert.equal(h.get('geoVersion').value,G);
 assert.equal(h.get('tabularConfirmar').checked,false);assert.match(h.get('tabularEstado').textContent,/ya importada/);
});

test('respuestas obsoletas descartadas al cambiar de caso y confirmación no heredada',async()=>{
 const h=harness();await h.init();const slow=deferred();
 h.state.handler=(url)=>url.pathname==='/api/tabular/version'&&url.searchParams.get('version')===U?slow.promise:undefined;
 h.get('tabularVersion').value=U;const pending=h.get('tabularVersion').onchange();
 h.setCase('B','c'.repeat(64));slow.resolve(response(version(U)));await pending;await settle();
 assert.equal(h.get('tabularDetalle').textContent,'');assert.equal(h.get('tabularImportar').disabled,true);
 h.state.handler=null;h.setCase();await settle();await h.open();h.get('tabularConfirmar').checked=true;h.get('tabularConfirmar').events.input();
 await h.open(U);assert.equal(h.get('tabularConfirmar').checked,false);assert.equal(h.get('tabularImportar').disabled,true);
});

test('interrumpida bloquea; registro ajeno o aprobado se rechaza; texto sin HTML',async()=>{
 const h=harness();h.state.records[T]=version(T,{importacion:{estado:'interrumpida',geometria:null,huella_tabular:H}});await h.init();await h.open();
 assert.equal(h.get('tabularConfirmar').disabled,true);assert.match(h.get('tabularEstado').textContent,/interrumpida/);
 h.state.records[U]=version(U,{aprobacion:{revisor:'x'},nombre_original:'<img src=x onerror=alert(1)>'});await h.open(U);
 assert.equal(h.get('tabularImportar').disabled,true);assert.match(h.get('tabularEstado').textContent,/sin vigencia/);
 assert.equal(h.get('tabularDetalle').textContent,'');
});

test('0.2 CSV cinco archivos según metadatos explícitos',async()=>{
 const h=harness();await h.init();
 const tables=[...csvFiles(),file('vertices.csv','id,x,y,z,procedencia\n'),file('superficies.csv','id,vertices,papel_geometrico,procedencia\n')];
 h.attach([file('metadatos.json','{"version_contrato":"0.2.0"}')],tables);
 await h.get('tabularRegistrar').onclick();await settle();
 assert.equal(h.posts().length,1);assert.equal(h.posts()[0].body.archivos.length,5);
 assert.equal(h.posts()[0].url,'/api/tabular/crear');
});
test('0.2 no acepta tres CSV y 0.1 no acepta cinco CSV',async()=>{
 for(const [version,tables] of [['0.2.0',csvFiles()],['0.1.0',[...csvFiles(),file('vertices.csv','id'),file('superficies.csv','id')]]]){
  const h=harness();await h.init();h.attach([file('metadatos.json',JSON.stringify({version_contrato:version}))],tables);
  await h.get('tabularRegistrar').onclick();await settle();assert.equal(h.posts().length,0);
  assert.ok(tables.every(f=>f.reads===0));
 }
});

(async()=>{for(const t of tests){await t.fn();}console.log('Tabular: validación previa, registro sin importar, importación confirmada, obsolescencia e interrupción: OK ('+tests.length+')');})()
 .catch(error=>{console.error(error);process.exit(1);});
