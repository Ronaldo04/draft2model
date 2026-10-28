// app.js + controles.js reales; HTTP/DOM simulados. Controles declarados, selección manual y evento tras consulta exacta.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const L='1'.repeat(32),L2='2'.repeat(32),A='3'.repeat(32),C='4'.repeat(32),FP='a'.repeat(64),SR='b'.repeat(64),SC='c'.repeat(64);
const flush=()=>new Promise(r=>setImmediate(r));async function settle(){for(let i=0;i<8;i++)await flush();}
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
const response=v=>({ok:true,json:async()=>structuredClone(v)});
function item(extra={}){return {id:C,caso:'A',expediente_sha256:FP,sha256_controles:SC,lectura:L,analisis:A,modelo:{id:'m',sha256_edb:SR},casos:['EST'],datos_sinteticos:true,vigente:true,
 estado_motor:'csi_4_terminado_no_equivale_a_controlado',aprueba_resultados:false,conformidad_normativa:'no_evaluada',
 contenido:{estado_global:'sin_datos',apto_proyeccion_controlado:false,faltantes_criticos:['SOLVER'],controles_solo_declarados:[],criticos_no_aplicables:[],
  avisos_lector:['Aviso del lector <b>no</b> es log'],advertencias_solver:null,fuentes:{respuesta:{sha256:SR},avisos_solver:null},huellas_tablas:{},estado_casos_declarado:{EST:4},
  declaracion:{revisor_declarado:'R',fecha:'2026-10-18',alcance:'S',controles:[{id:'EQ',critico:true,fuente_criterio:'Prueba'},{id:'SOLVER',critico:true,fuente_criterio:'Prueba'}]},
  controles:[{id:'EQ',tipo:'equilibrio',caso:'EST',estado:'satisfactorio',base_datos:'tablas_lectura',verificacion:'recalculada_desde_bytes_de_lectura',formula:'abs(...) <= tol',valores:{residuo_firmado:0,unidad:'kN'},motivos:['m']},
   {id:'SOLVER',tipo:'advertencias_solver',caso:null,estado:'sin_datos',base_datos:'fuente_solver_declarada',verificacion:'declarada_no_verificada',formula:null,valores:null,motivos:['Sin fuente <script>']}]},...extra};}
function harness(){
 const elements={},events={},state={calls:[],emitted:[],rows:[{id:C,vigente:true,estado_global:'sin_datos',apto_proyeccion_controlado:false}]};
 function element(tag){return {tag,value:'',textContent:'',disabled:false,checked:false,hidden:false,style:{},children:[],events:{},options:[],className:'',
  classList:{toggle(){}},parentElement:{classList:{toggle(){}}},append(...v){this.children.push(...v);},replaceChildren(...v){this.children=v;this.options=v;},
  setAttribute(){},removeAttribute(){},addEventListener(n,f){(this.events[n]??=[]).push(f);},checkValidity(){return true;},reportValidity(){return true;},click(){}};}
 const get=id=>elements[id]??=element('x');
 const window={addEventListener(t,f){(events[t]??=[]).push(f);},dispatchEvent(e){state.emitted.push(e);for(const f of events[e.type]||[])f(e);}};
 const ctx={window,document:{getElementById:get,querySelector(){return {content:'s'};},createElement:element},URLSearchParams,Blob,structuredClone,
  CustomEvent:class{constructor(t,o){this.type=t;this.detail=o?.detail;}},Event:class{constructor(t){this.type=t;}},URL:{createObjectURL(){},revokeObjectURL(){}},
  fetch(url,init={}){const p=new URL(url,'http://x'),body=init.body?JSON.parse(init.body):undefined;state.calls.push({url:p.pathname,body});
   const custom=state.handler?.(p,body);if(custom!==undefined)return custom;
   const r={'/api/casos':{casos:[]},'/api/lectura/trabajos':{trabajos:[{id:L,estado:'aceptado',vigente:true,lectura_verificada:true,expediente_sha256:FP,analisis:A,casos:['EST'],sha256_respuesta:SR},
     {id:L2,estado:'preparado',vigente:true,lectura_verificada:false,expediente_sha256:FP,analisis:A,casos:['EST'],sha256_respuesta:null}]},
    '/api/controles/historial':{versiones:state.rows,seleccion_automatica:false},'/api/controles/version':item()}[p.pathname];
   if(p.pathname==='/api/controles/crear')return Promise.resolve(response(item()));
   if(r===undefined)throw Error('Ruta inesperada '+p.pathname);return Promise.resolve(response(r));}};
 vm.createContext(ctx);for(const n of ['app','controles'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/'+n+'.js'),'utf8'),ctx,{filename:n+'.js'});
 function setCase(caso='A',fp=FP){vm.runInContext(`docs=${JSON.stringify({caso,expediente_sha256:fp,versiones:[],geometrias:[],documentos:[]})}`,ctx);window.dispatchEvent(new ctx.Event('d2m-case'));}
 const text=n=>n?(n.textContent||'')+(n.children||[]).map(text).join(' '):'';
 function fill(){get('ctlLectura').value=L;get('ctlLectura').onchange();get('ctlControles').value='[{"id":"EQ"}]';get('ctlRevisor').value='R';get('ctlAlcance').value='S';
  for(const f of get('ctlAlcance').events.input||[])f();}
 return {get,state,ctx,window,setCase,text,fill,init:async()=>{await settle();setCase();await settle();await get('ctlActualizar').onclick();await settle();},posts:()=>state.calls.filter(c=>c.body),
  reviews:()=>state.emitted.filter(e=>e.type==='d2m-controls-review')};
}
const tests=[];function test(n,f){tests.push({n,f});}

test('solo lecturas aceptadas vigentes; sin confirmación no hay POST; cuerpo exacto sin defaults',async()=>{
 const h=harness();await h.init();assert.deepEqual(h.get('ctlLectura').options.map(o=>o.value),['',L]);
 h.fill();assert.equal(h.get('ctlRegistrar').disabled,true);await h.get('ctlRegistrar').onclick();await settle();assert.equal(h.posts().length,0);
 h.get('ctlConfirmar').checked=true;for(const f of h.get('ctlConfirmar').events.input)f();assert.equal(h.get('ctlRegistrar').disabled,false);
 await h.get('ctlRegistrar').onclick();await settle();const post=h.posts()[0];
 assert.equal(post.url,'/api/controles/crear');assert.equal(post.body.sha256_respuesta,SR);assert.equal(post.body.avisos_solver_json,null);
 assert.deepEqual(post.body.controles,[{id:'EQ'}]);assert.equal(post.body.confirmacion_explicita,true);
 assert.equal(h.get('ctlVersion').value,C);
});

test('consulta exacta muestra estados/base/verificación como texto y emite evento solo después',async()=>{
 const h=harness();await h.init();assert.equal(h.reviews().length,0);
 h.get('ctlVersion').value=C;await h.get('ctlVersion').onchange();await settle();
 const all=h.text(h.get('ctlTabla'))+h.text(h.get('ctlListas'));
 for(const part of ['satisfactorio','tablas_lectura','declarada_no_verificada','sin_datos','Sin fuente <script>','Aviso del lector <b>no</b> es log','SOLVER'])assert.ok(all.includes(part),part);
 assert.match(h.get('ctlEstado').textContent,/NO apto/);assert.match(h.get('ctlEstado').textContent,/DATOS SINTÉTICOS/);
 const ev=h.reviews().at(-1).detail;assert.deepEqual([ev.id,ev.sha256_controles,ev.analisis,ev.apto_proyeccion_controlado],[C,SC,A,false]);
});

test('respuesta tardía tras cambiar de caso se descarta y la selección publica null',async()=>{
 const h=harness();await h.init();h.get('ctlVersion').value=C;await h.get('ctlVersion').onchange();await settle();
 const slow=deferred();h.state.handler=p=>p.pathname==='/api/controles/version'?slow.promise:undefined;
 h.get('ctlVersion').value=C;const pending=h.get('ctlVersion').onchange();assert.equal(h.reviews().at(-1).detail,null);
 h.setCase('B','e'.repeat(64));slow.resolve(response(item()));await pending;await settle();
 assert.equal(h.get('ctlTabla').children.length,0);assert.equal(h.reviews().filter(e=>e.detail).length,1);
 const src=fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/controles.js'),'utf8');assert.ok(!/innerHTML|eval\(|new Function/.test(src));
});

(async()=>{for(const t of tests)await t.f();console.log('Controles: lecturas aceptadas, confirmación, texto seguro, evento tras consulta y obsolescencia: OK ('+tests.length+')');})()
 .catch(e=>{console.error(e);process.exit(1);});
