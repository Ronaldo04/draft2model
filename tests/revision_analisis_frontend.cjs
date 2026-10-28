const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/analisis.js'),'utf8');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function harness(){
 const elements={},events={},calls=[],state={jobs:[],running:false};let serial=0;
 const get=id=>elements[id]??={value:'',textContent:'',checked:false,disabled:false,events:{},addEventListener(name,fn){this.events[name]=fn;}};
 const context={busy:false,docs:{caso:'A',expediente_sha256:'a'.repeat(64)},$:get,URLSearchParams,CustomEvent:class{constructor(type,options){this.type=type;this.detail=options.detail;}},
  crypto:{randomUUID(){return (++serial).toString().padStart(32,'0');}},setTimeout(){return 1;},clearTimeout(){},
  window:{addEventListener(name,fn){events[name]=fn;},dispatchEvent(event){state.event=event;}},message(text){state.error=text;},
  options(select,rows){select.options=rows.map(([value,textContent])=>({value,textContent}));select.value=rows[0][0];},
  action:async fn=>{try{return await fn();}catch(error){state.error=error.message;}},
  api(url,body){calls.push({url,body});const route=new URL(url,'http://127.0.0.1').pathname;
   if(route==='/api/analisis/preparar'){state.jobs=[job()];return Promise.resolve({json:async()=>job()});}
   if(route==='/api/analisis/ejecutar'){state.running=true;return Promise.resolve({json:async()=>job()});}
   return Promise.resolve({json:async()=>route==='/api/analisis/trabajos'?{trabajos:state.jobs}:job()});
  }};
 function job(){return {id:'trabajo',modelo:'modelo',aprobacion:'propia',estado:state.running?'en_ejecucion':'preparado',vigente:true,huella_preparacion:'b'.repeat(64),expediente_sha256:'a'.repeat(64)};}
 vm.runInNewContext(code,context);return {get,events,calls,state,context};
}
(async()=>{
 const h=harness();h.events['d2m-model-review']({detail:{caso:'A',modelo:'modelo',aprobaciones:[{id:'propia',fecha:'2026-10-17',revisor_declarado:'Fixture'}]}});
 assert.equal(h.get('analisisAprobacion').value,'','No elegir aprobación implícitamente');assert.equal(h.get('analisisPreparar').disabled,true);
 await h.get('analisisPreparar').onclick();assert.equal(h.calls.length,0);
 h.get('analisisAprobacion').value='propia';h.get('analisisAprobacion').onchange();await h.get('analisisPreparar').onclick();
 assert.equal(h.calls.filter(c=>c.url==='/api/analisis/preparar').length,1);assert.equal(h.calls.filter(c=>c.url==='/api/analisis/ejecutar').length,0);
 assert.equal(h.get('analisisEjecutar').disabled,true);h.get('analisisConfirmar').checked=true;h.get('analisisConfirmar').events.input();assert.equal(h.get('analisisEjecutar').disabled,false);
 h.events['d2m-model-review']({detail:null});assert.equal(h.get('analisisEjecutar').disabled,true);await h.get('analisisEjecutar').onclick();assert.equal(h.state.running,false);
 h.events['d2m-model-review']({detail:{caso:'A',modelo:'modelo',aprobaciones:[{id:'propia'}]}});h.get('analisisAprobacion').value='propia';h.get('analisisAprobacion').onchange();h.get('analisisConfirmar').checked=true;
 await h.get('analisisEjecutar').onclick();assert.equal(h.state.running,true);assert.equal(h.calls.find(c=>c.url==='/api/analisis/ejecutar').body.confirmacion_explicita,true);
 assert.equal(h.get('analisisConfirmar').checked,false);h.events['d2m-case']();await flush();assert.equal(h.get('analisisEjecutar').disabled,true);
 console.log('Análisis: aprobación explícita, preparación sin motor, confirmación y cambio de modelo: OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
