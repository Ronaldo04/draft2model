const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/verificacion_modelo.js'),'utf8');
const fp='f'.repeat(64),sha='a'.repeat(64),model='b'.repeat(32);
function harness(){
 const els={},events={},calls=[],state={emitted:[]};let serial=0;
 const $=id=>els[id]??={value:'',checked:false,disabled:false,textContent:'',events:{},addEventListener(k,fn){this.events[k]=fn;}};
 const c={busy:false,docs:{caso:'A'},$,URLSearchParams,crypto:{randomUUID:()=>String(++serial).padStart(32,'0')},
  CustomEvent:class{constructor(type,options){this.type=type;this.detail=options.detail;}},window:{addEventListener(k,fn){events[k]=fn;},dispatchEvent(event){state.emitted.push(event);}},options(el,rows){el.options=rows;},action:async fn=>{if(c.busy)return;c.busy=true;c.window.modelVerificationControls?.();try{return await fn();}finally{c.busy=false;c.window.modelVerificationControls?.();}},
  api:async(url,body)=>{calls.push({url,body});if(state.handler)return state.handler(url,body);
   if(url.endsWith('preparar'))state.job={...body,id:'c'.repeat(32),huella_preparacion:sha,estado:'preparado',vigente:true,modo_ejecucion:'doble'};
   if(url.endsWith('ejecutar'))state.job={...state.job,estado:'en_ejecucion'};
   return {json:async()=>state.job};}};
 vm.runInNewContext(code,c);
 function select(){events['d2m-model']({detail:{version:model,record:{huella_modelo:sha,expediente_sha256:fp}}});$('vmCriterios').value='{"relativo":0,"absolutos":{"x":0}}';$('vmCriterios').events.input();}
 return {$,events,calls,state,c,select};
}
const tests=[];const test=(name,fn)=>tests.push({name,fn});
test('preparar no ejecuta y confirmación se consume al ejecutar',async()=>{
 const h=harness();h.select();await h.$('vmPreparar').onclick();assert.equal(h.calls.length,1);
 assert.equal(h.$('vmEjecutar').disabled,true);h.$('vmConfirmar').checked=true;h.$('vmConfirmar').events.input();
 assert.equal(h.$('vmEjecutar').disabled,false);await h.$('vmEjecutar').onclick();
 assert.equal(h.calls[1].body.confirmacion_explicita,true);assert.equal(h.$('vmConfirmar').checked,false);
});
test('editar criterios o ejes invalida preparación y confirmación',async()=>{
 for(const id of ['vmCriterios','vmEjes']){const h=harness();h.select();await h.$('vmPreparar').onclick();h.$('vmConfirmar').checked=true;
 h.$(id).value='{}';h.$(id).events.input();assert.equal(h.$('vmConfirmar').checked,false);assert.equal(h.$('vmEjecutar').disabled,true);}
});
test('respuesta tardía al cambiar modelo o caso se descarta',async()=>{
 for(const change of ['model','case']){const h=harness();h.select();let resolve;
 h.state.handler=()=>new Promise(r=>resolve=r);const pending=h.$('vmPreparar').onclick();
 if(change==='case'){h.c.docs={caso:'B'};h.events['d2m-case']();}else h.events['d2m-model']({detail:null});
 resolve({json:async()=>({id:'late',huella_preparacion:sha,estado:'preparado'})});await pending;
 assert.equal(h.$('vmHuella').value,'');assert.equal(h.$('vmEjecutar').disabled,true);}
});
test('clave idempotente tras fallo y nueva tras edición',async()=>{
 const h=harness();h.select();h.state.handler=()=>Promise.reject(Error('red'));
 await assert.rejects(h.$('vmPreparar').onclick());await assert.rejects(h.$('vmPreparar').onclick());
 assert.equal(h.calls[0].body.clave_solicitud,h.calls[1].body.clave_solicitud);
 h.$('vmCriterios').events.input();await assert.rejects(h.$('vmPreparar').onclick());
 assert.notEqual(h.calls[1].body.clave_solicitud,h.calls[2].body.clave_solicitud);
});
test('huella ajena y resultado parcial nunca habilitan ejecución',async()=>{
 const h=harness();h.select();h.state.handler=async()=>({json:async()=>({caso:'A',modelo:model,huella_modelo:'0'.repeat(64),expediente_sha256:fp,estado:'preparado',vigente:true})});
 await h.$('vmPreparar').onclick();h.$('vmConfirmar').checked=true;h.$('vmConfirmar').events.input();assert.equal(h.$('vmEjecutar').disabled,true);
});
test('historial y consulta consumen confirmación sin lanzar; error tardío se descarta',async()=>{
 const h=harness();h.select();await h.$('vmPreparar').onclick();const prep=h.state.job;
 h.state.handler=async url=>({json:async()=>url.includes('historial')?{trabajos:[prep]}:prep});
 h.$('vmConfirmar').checked=true;await h.$('vmHistorial').onclick();assert.equal(h.$('vmConfirmar').checked,false);
 h.$('vmTrabajo').value=prep.id;await h.$('vmTrabajo').onchange();assert.equal(h.calls.filter(x=>x.url.endsWith('ejecutar')).length,0);
 let reject;h.state.handler=()=>new Promise((_,r)=>reject=r);const pending=h.$('vmPreparar').onclick();h.events['d2m-model']({detail:null});reject(Error('respuesta vieja'));await pending;
 assert.equal(h.$('vmEjecutar').disabled,true);
});
(async()=>{for(const t of tests){await t.fn();console.log('OK '+t.name);}console.log(tests.length+' pruebas OK');})().catch(e=>{console.error(e);process.exitCode=1;});
