// Preparar no ejecuta; confirmación, idempotencia y respuestas tardías con DOM mínimo.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/construccion.js'),'utf8');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
function harness(){
 const elements={},events={},calls=[],pending={},state={jobs:[],next:null};let serial=0;
 const element=()=>({value:'',textContent:'',checked:false,disabled:false,events:{},children:[],reset(){},reportValidity(){return true;},addEventListener(name,fn){this.events[name]=fn;},append(...children){this.children.push(...children);},replaceChildren(...children){this.children=children;}});
 const get=id=>elements[id]??=element();
 const context={busy:false,docs:{caso:'A',expediente_sha256:'a'.repeat(64)},$:get,URLSearchParams,CustomEvent:class{constructor(type,options){this.type=type;this.detail=options.detail;}},
  crypto:{randomUUID(){return (++serial).toString().padStart(32,'0');}},setTimeout(){return 1;},clearTimeout(){},
  window:{addEventListener(name,fn){events[name]=fn;},dispatchEvent(event){state.event=event;}},
  options(select,rows){select.options=rows.map(([value,textContent])=>({value,textContent}));select.value=rows[0][0];},
  node(tag,textContent){return Object.assign(element(),{tag,textContent:textContent??''});},
  message(text){state.error=text;},action:async fn=>{try{return await fn();}catch(error){state.error=error.message;}},
  api(url,body){
   calls.push({url,body});const parsed=new URL(url,'http://127.0.0.1');
   if(parsed.pathname==='/api/construccion/preparar'){
    if(state.deferPrepare){pending.prepare=deferred();return pending.prepare.promise;}
    if(state.failPrepare)return Promise.reject(Error('Conexión interrumpida'));
    const created=record('nuevo');state.jobs=[created];return Promise.resolve(response(created));
   }
   if(parsed.pathname==='/api/construccion/ejecutar'){if(state.deferExecute){pending.execute=deferred();return pending.execute.promise;}return Promise.resolve(response(record(body.trabajo,'en_ejecucion')));}
   if(parsed.pathname==='/api/construccion/trabajos')return Promise.resolve(response({trabajos:state.jobs}));
   const id=parsed.searchParams.get('trabajo');if(state.defer){pending[id]=deferred();return pending[id].promise;}
   return Promise.resolve(response(state.next||record(id)));
  }};
 vm.runInNewContext(code,context);
 function config(approved=true,secciones=[{id:'MURO',tipo:'shell_muro'}],id='cfg'){events['d2m-config']({detail:{id,datos:{secciones,revision:{estado:approved?'aprobado':'borrador'}},comprobacion:{apto_para_adaptador:approved}}});}
 return {get,context,events,calls,pending,state,config};
}
function record(id,estado='preparado'){return {id,estado,vigente:true,configuracion_version:'cfg',expediente_sha256:'a'.repeat(64),huella_preparacion:'b'.repeat(64),modelo_id:null};}
function response(data){return {json:async()=>data};}
async function preparation(){
 const h=harness();h.config(false);assert.equal(h.get('construccionPreparar').disabled,true);h.config();
 h.get('construccionPlantilla').value='plantilla.edb';h.get('construccionShell').value='ShellThin';
 h.get('construccionGravedad').value='9.80665';h.get('construccionOpciones').value='{}';
 h.state.failPrepare=true;h.get('construccionForm').onsubmit({preventDefault(){}});await flush();
 h.state.failPrepare=false;h.get('construccionForm').onsubmit({preventDefault(){}});await flush();await flush();
 const prepares=h.calls.filter(c=>c.url==='/api/construccion/preparar');assert.equal(prepares.length,2);
 assert.equal(prepares[0].body.clave_solicitud,prepares[1].body.clave_solicitud,'No duplicar preparación tras pérdida de respuesta');
 assert.equal(h.calls.some(c=>c.url==='/api/construccion/ejecutar'),false);
 assert.equal(h.get('construccionEjecutar').disabled,true);
 await h.get('construccionEjecutar').onclick();assert.equal(h.calls.some(c=>c.url==='/api/construccion/ejecutar'),false);
 h.get('construccionConfirmar').checked=true;h.get('construccionConfirmar').events.input();assert.equal(h.get('construccionEjecutar').disabled,false);
 h.state.next=record('nuevo','en_ejecucion');await h.get('construccionEjecutar').onclick();
 const executes=h.calls.filter(c=>c.url==='/api/construccion/ejecutar');assert.equal(executes.length,1);assert.equal(executes[0].body.confirmacion_explicita,true);
 assert.equal(h.get('construccionConfirmar').checked,false);
 h.events['d2m-case']();assert.equal(h.get('construccionEjecutar').disabled,true);await flush();
 h.get('construccionVersion').value='aceptado';h.state.next={...record('aceptado','aceptado'),modelo_id:'modelo-nuevo'};
 await h.get('construccionVersion').onchange();assert.equal(h.state.event.type,'d2m-model-created');assert.equal(h.state.event.detail.modelo,'modelo-nuevo');
}
async function stale(reject){
 const h=harness();h.config();h.state.defer=true;
 h.get('construccionVersion').value='viejo';h.get('construccionVersion').onchange();
 h.get('construccionVersion').value='nuevo';h.get('construccionVersion').onchange();
 h.pending.nuevo.resolve(response(record('nuevo')));await flush();const expected=h.get('construccionEstado').textContent;
 if(reject)h.pending.viejo.reject(Error('error viejo'));else h.pending.viejo.resolve(response(record('viejo')));
 await flush();assert.equal(h.get('construccionEstado').textContent,expected);assert.equal(h.state.error,undefined);
 h.config(false);h.get('construccionConfirmar').checked=true;h.context.window.constructionControls();assert.equal(h.get('construccionEjecutar').disabled,true);
}
function form(h){h.get('construccionPlantilla').value='plantilla.edb';h.get('construccionGravedad').value='9.80665';h.get('construccionOpciones').value='{}';}
function fields(h,index){const children=h.get('construccionLosas').children[index].children;return {funcion:children[2],tipo:children[4],justificacion:children[6]};}
function choose(row,funcion,tipo,justificacion='Elección revisada por sección'){Object.assign(row.funcion,{value:funcion});Object.assign(row.tipo,{value:tipo});Object.assign(row.justificacion,{value:justificacion});}
async function submit(h){h.get('construccionForm').onsubmit({preventDefault(){}});await flush();await flush();}
async function losas(){
 const h=harness(),sections=[{id:'PISO<img>',tipo:'shell_losa_homogenea'},{id:'FONDO',tipo:'shell_losa_homogenea'},{id:'NERVADA',tipo:'shell_losa_nervada_v1'},{id:'CASETONADA',tipo:'shell_losa_casetonada_v1'}];
 h.config(true,sections);form(h);assert.equal(h.get('construccionMuros').hidden,true);assert.equal(h.get('construccionShell').required,false);assert.equal(h.get('construccionShell').disabled,true);
 assert.equal(h.get('construccionLosas').children.length,4);assert.equal(h.get('construccionLosas').children[0].children[0].textContent,'Sección PISO<img> · shell_losa_homogenea');
 const rows=sections.map((_,i)=>fields(h,i));for(const row of rows){assert.equal(row.funcion.value,'');assert.equal(row.tipo.value,'');assert.equal(row.justificacion.required,true);}
 await submit(h);assert.equal(h.calls.some(c=>c.body),false);assert.match(h.state.error,/Completa/);
 choose(rows[0],'piso','Membrane');choose(rows[1],'fondo_deposito','ShellThin');choose(rows[2],'piso','Membrane');choose(rows[3],'otra','ShellThick');
 await submit(h);const sent=h.calls.find(c=>c.url==='/api/construccion/preparar').body.opciones;
 assert.equal(Object.hasOwn(sent,'tipo_shell_muro'),false);assert.deepEqual(Object.keys(sent.tipo_shell_losa),sections.map(s=>s.id));
 assert.equal(sent.tipo_shell_losa['PISO<img>'].tipo,'Membrane');assert.equal(sent.tipo_shell_losa.FONDO.tipo,'ShellThin');assert.equal(sent.tipo_shell_losa.NERVADA.funcion,'piso');assert.equal(sent.tipo_shell_losa.CASETONADA.justificacion,'Elección revisada por sección');
 for(const row of rows)for(const key of ['tipo','funcion','justificacion']){h.get('construccionConfirmar').checked=true;row[key].events.input();assert.equal(h.get('construccionConfirmar').checked,false);}
 const count=h.calls.filter(c=>c.url==='/api/construccion/preparar').length;
 choose(rows[1],'fondo_deposito','Membrane');await submit(h);assert.match(h.state.error,/presión normal/);
 choose(rows[1],'tapa_deposito','Membrane');await submit(h);assert.match(h.state.error,/presión normal/);
 choose(rows[1],'fondo_deposito','ShellThin','   ');await submit(h);assert.match(h.state.error,/Completa/);
 choose(rows[1],'fondo_deposito','ShellThin');h.get('construccionOpciones').value='{"tipo_shell_losa":"Membrane"}';await submit(h);assert.match(h.state.error,/retíralo del JSON/);
 assert.equal(h.calls.filter(c=>c.url==='/api/construccion/preparar').length,count);
 h.config(true,[{id:'OTRA',tipo:'shell_losa_homogenea'}],'cfg2');assert.equal(h.get('construccionLosas').children.length,1);assert.equal(fields(h,0).tipo.value,'');assert.equal(h.get('construccionEjecutar').disabled,true);
 h.context.docs={caso:'B',expediente_sha256:'c'.repeat(64)};h.events['d2m-case']();assert.equal(h.get('construccionLosas').children.length,0);await flush();
 // Configuración 0.1 de frames sin superficies: no requiere opciones de shell.
 const frames=harness();frames.config(true,[{id:'VIGA',tipo:'frame_rectangular'}]);form(frames);await submit(frames);
 const frameOptions=frames.calls.find(c=>c.url==='/api/construccion/preparar').body.opciones;assert.equal(Object.hasOwn(frameOptions,'tipo_shell_losa'),false);assert.equal(Object.hasOwn(frameOptions,'tipo_shell_muro'),false);
}
async function latePreparation(change,reject=false){
 const h=harness();h.config();form(h);h.get('construccionShell').value='ShellThin';h.state.deferPrepare=true;
 await submit(h);const before=h.calls.length;
 if(change==='config')h.config(true,[{id:'VIGA',tipo:'frame_rectangular'}],'cfg2');
 if(change==='edit'){h.get('construccionGravedad').value='9.81';h.get('construccionGravedad').events.input();}
 if(change==='version'){h.get('construccionVersion').value='otro';await h.get('construccionVersion').onchange();}
 if(change==='case'){h.context.docs={caso:'B',expediente_sha256:'c'.repeat(64)};h.events['d2m-case']();await flush();}
 const afterChange=h.calls.length;
 if(reject)h.pending.prepare.reject(Error('Error tardío'));else h.pending.prepare.resolve(response(record('tardio')));await flush();await flush();
 assert.equal(h.calls.slice(change==='case'?afterChange:before).some(c=>c.url.includes('/trabajos?')),false,'La preparación tardía no selecciona otro trabajo tras '+change);
 assert.equal(h.get('construccionConfirmar').checked,false);
 assert.equal(h.state.error,undefined);
}
async function lateExecution(change,reject){
 const h=harness();h.config();h.get('construccionVersion').value='original';await h.get('construccionVersion').onchange();
 h.get('construccionConfirmar').checked=true;h.state.deferExecute=true;const running=h.get('construccionEjecutar').onclick();
 if(change==='config')h.config(true,[{id:'VIGA',tipo:'frame_rectangular'}],'cfg2');
 if(change==='edit')h.get('construccionGravedad').events.input();
 if(change==='version'){h.get('construccionVersion').value='otro';await h.get('construccionVersion').onchange();}
 if(change==='case'){h.context.docs={caso:'B',expediente_sha256:'c'.repeat(64)};h.events['d2m-case']();await flush();}
 const detail=h.get('construccionDetalle').textContent,count=h.calls.length;
 if(reject)h.pending.execute.reject(Error('Ejecución antigua'));else h.pending.execute.resolve(response(record('original','en_ejecucion')));await running;await flush();
 assert.equal(h.get('construccionDetalle').textContent,detail);assert.equal(h.calls.length,count);assert.equal(h.state.error,undefined);assert.equal(h.get('construccionConfirmar').checked,false);
}
(async()=>{await preparation();await stale(false);await stale(true);await losas();for(const change of ['config','edit','version','case'])for(const reject of [false,true]){await latePreparation(change,reject);await lateExecution(change,reject);}console.log('Construcción: losas por sección, muros aplicables, validación explícita, confirmación, reintentos y respuestas tardías: OK (DOM/API dobles, sin red ni ETABS)');})().catch(error=>{console.error(error);process.exitCode=1;});
