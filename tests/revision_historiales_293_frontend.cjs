// app.js + cada etapa real; HTTP/DOM simulados. 293: seleccionar expediente no consulta historiales costosos (cada fila revalida
// aprobación/plan en el servidor bajo el lock compartido); Actualizar consulta; cambio de caso descarta respuestas antiguas;
// abrir una versión sigue dependiendo de la comprobación del servidor (fuente alterada → error, sin publicar).
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const FP='a'.repeat(64),FP2='e'.repeat(64);
const flush=()=>new Promise(r=>setImmediate(r));async function settle(){for(let i=0;i<10;i++)await flush();}
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
const response=v=>({ok:true,json:async()=>structuredClone(v)});
const ETAPAS={
 lecturas:{boton:'lecturaActualizar',estado:'lecturaEstado',rutas:['/api/lectura/trabajos']},
 construccion:{boton:'construccionActualizar',estado:'construccionEstado',rutas:['/api/construccion/trabajos']},
 analisis:{boton:'analisisActualizar',estado:'analisisEstado',rutas:['/api/analisis/trabajos']},
 mapeos:{boton:'mapeoActualizar',estado:'mapeoEstado',rutas:['/api/mapeos']},
 recuperacion:{boton:'recuperacionActualizar',estado:'recuperacionEstado',rutas:['/api/normalizacion/estado']},
 contexto:{boton:'ctxActualizar',estado:'ctxEstado',rutas:['/api/contexto/historial']},
 explicaciones:{boton:'expActualizar',estado:'expEstado',rutas:['/api/explicaciones/trabajos']},
 controles:{boton:'ctlActualizar',estado:'ctlEstado',rutas:['/api/lectura/trabajos','/api/controles/historial']},
};
const HISTORIALES=new Set(Object.values(ETAPAS).flatMap(e=>e.rutas));
function harness(nombre){
 const elements={},events={},state={calls:[],emitted:[],errors:[],handler:null};
 function element(tag){return {tag,value:'',textContent:'',disabled:false,checked:false,hidden:false,style:{},children:[],events:{},options:[],className:'',dataset:{},
  classList:{toggle(){},add(){},remove(){}},parentElement:{classList:{toggle(){}}},append(...v){this.children.push(...v);},replaceChildren(...v){this.children=v;this.options=v;},
  before(){},setAttribute(){},removeAttribute(){},addEventListener(n,f){(this.events[n]??=[]).push(f);},checkValidity(){return true;},reportValidity(){return true;},click(){},reset(){},focus(){}};}
 const get=id=>elements[id]??=element('x');
 const window={addEventListener(t,f){(events[t]??=[]).push(f);},dispatchEvent(e){state.emitted.push(e);for(const f of events[e.type]||[])f(e);}};
 const ctx={window,document:{getElementById:get,querySelector(){return {content:'s'};},querySelectorAll(){return [];},createElement:element},URLSearchParams,Blob,structuredClone,
  CustomEvent:class{constructor(t,o){this.type=t;this.detail=o?.detail;}},Event:class{constructor(t){this.type=t;}},URL:{createObjectURL(){},revokeObjectURL(){}},
  setTimeout,clearTimeout,
  fetch(url){const p=new URL(url,'http://x');state.calls.push(p);const custom=state.handler?.(p);if(custom!==undefined)return custom;
   if(p.pathname==='/api/casos')return Promise.resolve(response({casos:[]}));return Promise.reject(Error('Ruta no simulada '+p.pathname));}};
 vm.createContext(ctx);for(const n of ['app',nombre])vm.runInContext(fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/'+n+'.js'),'utf8'),ctx,{filename:n+'.js'});
 // Igual que openCase de app.js: primer evento con docs=null (limpieza), segundo con el expediente cargado.
 function setCase(caso='A',fp=FP){vm.runInContext('docs=null',ctx);window.dispatchEvent(new ctx.Event('d2m-case'));
  vm.runInContext(`docs=${JSON.stringify({caso,expediente_sha256:fp,versiones:[],geometrias:[],documentos:[]})}`,ctx);window.dispatchEvent(new ctx.Event('d2m-case'));}
 const historiales=()=>state.calls.filter(c=>HISTORIALES.has(c.pathname));
 const errores=()=>vm.runInContext('typeof messages==="undefined"?null:messages',ctx);
 return {get,state,ctx,setCase,historiales,errores};
}
const tests=[];function test(n,f){tests.push({n,f});}

for(const [nombre,etapa] of Object.entries(ETAPAS)){
 test(nombre+': seleccionar expediente no consulta el historial y lo declara «sin consultar»',async()=>{
  const h=harness(nombre);await settle();h.setCase();await settle();
  assert.deepEqual(h.historiales().map(c=>c.pathname),[]);
  assert.match(h.get(etapa.estado).textContent,/Historial sin consultar/);
  h.setCase('B',FP2);await settle();h.setCase('A');await settle();   // cambios repetidos: sigue sin cascadas
  assert.equal(h.historiales().length,0);
 });
 test(nombre+': Actualizar consulta el historial del expediente actual',async()=>{
  const h=harness(nombre);await settle();h.setCase();await settle();
  h.state.handler=p=>HISTORIALES.has(p.pathname)?Promise.reject(Error('consulta simulada')):undefined;
  await h.get(etapa.boton).onclick();await settle();
  const pedidos=h.historiales();assert.equal(pedidos[0]?.pathname,etapa.rutas[0]);
  assert.ok(pedidos.every(c=>c.searchParams.get('caso')==='A'));
 });
 test(nombre+': respuesta (error) antigua tras cambiar expediente se descarta',async()=>{
  const h=harness(nombre);await settle();h.setCase();await settle();const pendiente=deferred();
  h.state.handler=p=>HISTORIALES.has(p.pathname)?pendiente.promise:undefined;
  const clic=h.get(etapa.boton).onclick();await settle();assert.equal(h.historiales().length,1);
  h.setCase('B',FP2);await settle();const antes=h.get(etapa.estado).textContent;
  pendiente.reject(Error('RESPUESTA OBSOLETA'));await clic;await settle();
  assert.equal(h.get(etapa.estado).textContent,antes);assert.doesNotMatch(antes,/OBSOLETA/);
  assert.ok(!JSON.stringify(h.get('mensaje').textContent||'').includes('OBSOLETA'));
  assert.equal(h.historiales().length,1);   // el cambio de caso no relanzó la consulta
 });
}

test('lecturas: consulta explícita exitosa pasa a «consultado»; una respuesta exitosa de otro expediente no',async()=>{
 const h=harness('lecturas');await settle();h.setCase();await settle();
 h.state.handler=p=>p.pathname==='/api/lectura/trabajos'?Promise.resolve(response({trabajos:[]})):undefined;
 await h.get('lecturaActualizar').onclick();await settle();assert.match(h.get('lecturaEstado').textContent,/Historial consultado y comprobado/);
 const pendiente=deferred();h.state.handler=p=>p.pathname==='/api/lectura/trabajos'?pendiente.promise:undefined;
 const clic=h.get('lecturaActualizar').onclick();await settle();h.setCase('B',FP2);await settle();
 pendiente.resolve(response({trabajos:[]}));await clic;await settle();
 assert.match(h.get('lecturaEstado').textContent,/Historial sin consultar/);
});

test('lecturas: abrir una versión sigue exigiendo la comprobación del servidor (fuente alterada → error, sin publicar)',async()=>{
 const h=harness('lecturas'),ID='1'.repeat(32);await settle();h.setCase();await settle();
 h.state.handler=p=>{
  if(p.pathname==='/api/lectura/trabajos')return Promise.resolve(response({trabajos:[{id:ID,caso:'A',expediente_sha256:FP,analisis:'3'.repeat(32),estado:'aceptado',
   vigente:true,lectura_verificada:true,tablas:['Story Drifts'],casos:['EST'],modo_ejecucion:'doble'}]}));
  if(p.pathname==='/api/lectura/trabajo')return Promise.reject(Error('Fuente alterada: la huella del análisis no coincide.'));
 };
 await h.get('lecturaActualizar').onclick();await settle();
 h.state.emitted.length=0;h.get('lecturaVersion').value=ID;await h.get('lecturaVersion').onchange?.();await settle();
 const abiertas=h.state.calls.filter(c=>c.pathname==='/api/lectura/trabajo');assert.equal(abiertas.length,1);
 assert.match(h.get('lecturaEstado').textContent+' '+h.get('mensaje').textContent,/Fuente alterada/);
 assert.equal(h.state.emitted.filter(e=>e.type==='d2m-reading'&&e.detail).length,0);
});

(async()=>{let fallos=0;for(const {n,f} of tests){try{await f();}catch(e){fallos++;console.error('FAIL '+n+'\n'+e.stack);}}
 if(fallos){console.error(fallos+' fallo(s)');process.exit(1);}console.log('Historiales 293: sin consulta al seleccionar, Actualizar explícito, descarte obsoleto y apertura comprobada: OK ('+tests.length+')');})();
