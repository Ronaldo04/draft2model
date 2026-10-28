const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/revision_modelo.js'),'utf8');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
function harness(){
 const elements={},events={},pending={},calls=[],state={};
 const get=id=>elements[id]??={value:'',textContent:'',checked:false,disabled:false,events:{},checkValidity(){return true;},reportValidity(){return true;},addEventListener(name,fn){this.events[name]=fn;}};
 const context={busy:false,docs:{caso:'A'},$:get,URLSearchParams,Date,CustomEvent:class{constructor(type,options){this.type=type;this.detail=options.detail;}},
  window:{addEventListener(name,fn){events[name]=fn;},dispatchEvent(event){state.event=event;}},
  message(text){state.error=text;},action:async fn=>fn(),
  api(url,body){calls.push({url,body});if(body)return Promise.resolve({json:async()=>review(body.modelo,'aprobado')});
   const id=new URL(url,'http://127.0.0.1').searchParams.get('modelo');pending[id]=deferred();return pending[id].promise;
  }};vm.runInNewContext(code,context);
 return {get,events,pending,calls,state,context};
}
function review(modelo,estado='pendiente'){return {modelo,huella_modelo:modelo,aprobaciones:estado==='aprobado'?[{id:'propia'}]:[],estado};}
function open(h,id){h.events['d2m-model']({detail:{version:id,record:{expediente_sha256:'a'.repeat(64)}}});}
async function test(){
 const h=harness();open(h,'viejo');open(h,'nuevo');h.pending.nuevo.resolve({json:async()=>review('nuevo')});await flush();
 h.pending.viejo.reject(Error('Fallo viejo'));await flush();assert.equal(h.state.error,undefined);assert.equal(h.get('modeloRevisionHuella').value,'nuevo');
 assert.equal(h.get('modeloAprobar').disabled,true);
 for(const id of ['modeloRevisor','modeloAlcance'])h.get(id).value='Declaración sintética';h.get('modeloFecha').value='2026-10-17';
 const boxes=['modeloControlGeometria','modeloControlMateriales','modeloControlCargas','modeloControlApoyos','modeloControlCasos'];
 for(const id of boxes)h.get(id).checked=true;h.context.window.modelReviewControls();assert.equal(h.get('modeloAprobar').disabled,true);
 h.get('modeloRevisionConfirmar').checked=true;h.context.window.modelReviewControls();assert.equal(h.get('modeloAprobar').disabled,false);
 h.get('modeloControlCasos').checked=false;await h.get('modeloRevisionForm').onsubmit({preventDefault(){}});await flush();assert.equal(h.calls.filter(c=>c.body).length,0);
 h.get('modeloControlCasos').checked=true;h.get('modeloRevisionForm').onsubmit({preventDefault(){}});await flush();await flush();
 const body=h.calls.find(c=>c.body).body;assert.equal(body.modelo,'nuevo');assert.equal(body.huella_modelo,'nuevo');assert.equal(body.confirmacion_explicita,true);
 assert.equal(Object.keys(body.controles).length,5);assert.ok(Object.values(body.controles).every(v=>v===true));
 for(const id of [...boxes,'modeloRevisionConfirmar'])assert.equal(h.get(id).checked,false);
 h.events['d2m-case']();assert.equal(h.get('modeloAprobar').disabled,true);assert.equal(h.state.event.detail,null);
 console.log('Revisión propia: selección vigente, cinco controles, confirmación y limpieza: OK');
}
test().catch(error=>{console.error(error);process.exitCode=1;});
