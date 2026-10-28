// informes.js real; DOM/HTTP controlados, sin navegador ni red.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const D='1'.repeat(32),C='2'.repeat(32),O='3'.repeat(32),R='4'.repeat(32),FP='a'.repeat(64),SHA='b'.repeat(64);
const response=value=>({json:async()=>value}),settle=async()=>{await new Promise(setImmediate);await new Promise(setImmediate);};
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
function report(id=D,estado='borrador'){return {id,estado,caso:'A',resultado:R,expediente_sha256:FP,archivos:{'informe.json':SHA},evidencia_analisis:null,aprueba_resultados:false,revision_resultados:'pendiente',conformidad_normativa:'no_evaluada',...(estado==='aprobado'?{padre:{id:D,sha256_informe:SHA}}:{})};}
function harness(){const elements={},events={},state={calls:[],records:{[D]:report(),[C]:report(C,'aprobado'),[O]:report(O)},rows:[{id:D,vigente:true,estado:'borrador'},{id:O,vigente:true,estado:'borrador'}],downloads:[]};
 const get=id=>elements[id]??={value:'',textContent:'',disabled:false,checked:false,options:[],events:{},reset(){},reportValidity(){return true;},addEventListener(k,f){this.events[k]=f;}};
 const context={busy:false,docs:{caso:'A',expediente_sha256:FP},$:get,URLSearchParams,
  URL:{createObjectURL(blob){state.blob=blob;return 'blob:test';},revokeObjectURL(){}},document:{createElement(){return {click(){state.downloads.push(this.download);}};}},
  window:{addEventListener(k,f){events[k]=f;}},options(select,rows){select.options=rows.map(([value,textContent])=>({value,textContent}));select.value=rows[0][0];},message(text){state.error=text;},action:async fn=>fn(),
  api(url,body){if(body)body=JSON.parse(JSON.stringify(body));state.calls.push({url,body});const parsed=new URL(url,'http://localhost'),special=state.handler?.(parsed,body);if(special!==undefined)return special;
   switch(parsed.pathname){case '/api/analisis':return Promise.resolve(response({versiones:[]}));case '/api/informes':return Promise.resolve(response({versiones:state.rows}));
    case '/api/informe':return Promise.resolve(response(state.records[parsed.searchParams.get('version')]));
    case '/api/informe/aprobar':state.rows.push({id:C,vigente:true,estado:'aprobado'});return Promise.resolve(response(state.records[C]));
    case '/api/informe/archivo':return Promise.resolve({blob:async()=>new Blob([parsed.searchParams.get('version')])});
    default:throw Error('Ruta inesperada '+parsed.pathname);
   }
  }};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/informes.js'),'utf8'),context);
 function select(caso='A',fp=FP){context.docs={caso,expediente_sha256:fp};events['d2m-result']({detail:{version:R,record:{expediente_sha256:fp}}});}
 async function init(){select();await settle();}
 async function open(id=D){get('informeVersion').value=id;await get('informeVersion').onchange();await settle();}
 function fill(){for(const [id,value]of Object.entries({informeRevisor:'Revisor documental declarado',informeFecha:'2026-10-18',informeMotivo:'Revisión documental SINTÉTICA.'})){get(id).value=value;get(id).events.input();}}
 return {get,events,state,context,select,init,open,fill};
}
const tests=[];const test=(name,fn)=>tests.push({name,fn});
test('declaración y confirmación independientes; historial no aprueba',async()=>{
 const h=harness();await h.init();await h.open();assert.equal(h.get('informeSha').value,SHA);assert.equal(h.get('informeAprobar').disabled,true);h.fill();assert.equal(h.get('informeAprobar').disabled,true);
 await h.get('informeAprobar').onclick();assert.equal(h.state.calls.some(c=>c.body),false);await h.get('informeActualizar').onclick();assert.equal(h.state.calls.some(c=>c.body),false);
});
test('aprobación exacta abre hija, conserva padre y descarga revisada sin aprobar resultados',async()=>{
 const h=harness();await h.init();await h.open();h.fill();h.get('informeConfirmar').checked=true;h.get('informeConfirmar').events.input();assert.equal(h.get('informeAprobar').disabled,false);await h.get('informeAprobar').onclick();
 assert.deepEqual(h.state.calls.find(c=>c.body).body,{caso:'A',version:D,expediente_sha256:FP,sha256_informe:SHA,revisor_declarado:'Revisor documental declarado',fecha:'2026-10-18',motivo:'Revisión documental SINTÉTICA.',confirmacion_explicita:true});
 assert.equal(h.get('informeVersion').value,C);assert.equal(h.get('informeAprobar').disabled,true);assert.equal(h.get('informeConfirmar').checked,false);assert.match(h.get('informeEstado').textContent,/DOCUMENTAL/);assert.match(h.get('informeEstado').textContent,/resultados pendiente/);assert.match(h.get('informeEstado').textContent,/normativa no evaluada/);
 await h.get('informePdf').onclick();assert.equal(await h.state.blob.text(),C);assert.equal(h.state.downloads[0],'informe-'+C+'.pdf');assert.equal(h.state.rows.some(v=>v.id===D),true);
 h.get('informeConfirmar').checked=true;await h.get('informeAprobar').onclick();assert.equal(h.state.calls.filter(c=>c.body).length,1);
});
test('editar declaración/contexto invalida confirmación; SHA manipulado no aprueba',async()=>{
 const h=harness();await h.init();await h.open();h.fill();for(const id of ['informeRevisor','informeFecha','informeMotivo','informeTitulo','informeHipotesis','informeFaltantes','informeAnalisis']){h.get('informeConfirmar').checked=true;h.get(id).events.input();assert.equal(h.get('informeConfirmar').checked,false);}
 h.get('informeSha').value='0'.repeat(64);h.get('informeConfirmar').checked=true;await h.get('informeAprobar').onclick();assert.equal(h.state.calls.some(c=>c.body),false);
});
test('fecha real válida y campos completos requeridos',async()=>{
 const h=harness();await h.init();await h.open();h.fill();for(const value of ['2026-02-30','ayer','']){h.get('informeFecha').value=value;h.get('informeFecha').events.input();h.get('informeConfirmar').checked=true;await h.get('informeAprobar').onclick();}assert.equal(h.state.calls.some(c=>c.body),false);
});
test('sin vigencia al relistar limpia SHA/descargas; preferida inválida no abre',async()=>{
 const h=harness();await h.init();await h.open();h.fill();h.get('informeConfirmar').checked=true;h.state.rows=[{id:D,vigente:false}];await h.get('informeActualizar').onclick();assert.equal(h.get('informeSha').value,'');assert.equal(h.get('informePdf').disabled,true);assert.equal(h.get('informeAprobar').disabled,true);
});
test('fuente/hash cambiados invalidan selección y error de aprobar limpia permisos',async()=>{
 const h=harness();await h.init();await h.open();h.fill();h.get('informeConfirmar').checked=true;h.state.handler=url=>url.pathname==='/api/informe/aprobar'?Promise.reject(Error('fuente alterada')):undefined;await h.get('informeAprobar').onclick();assert.equal(h.get('informeSha').value,'');assert.equal(h.get('informePdf').disabled,true);assert.equal(h.get('informeConfirmar').checked,false);
 h.state.handler=undefined;await h.open();h.fill();h.get('informeConfirmar').checked=true;h.select('A','9'.repeat(64));assert.equal(h.get('informeSha').value,'');assert.equal(h.get('informeAprobar').disabled,true);
});
for(const change of ['caso','version','hash'])for(const reject of [false,true])test('descarta '+(reject?'error':'respuesta')+' de aprobación obsoleta por '+change,async()=>{
 const h=harness();await h.init();await h.open();h.fill();h.get('informeConfirmar').checked=true;const pending=deferred();h.state.handler=url=>url.pathname==='/api/informe/aprobar'?pending.promise:undefined;const running=h.get('informeAprobar').onclick();
 if(change==='version')await h.open(O);else h.select(change==='caso'?'B':'A',change==='hash'?'9'.repeat(64):FP);await settle();const before=h.get('informeEstado').textContent;
 if(reject)pending.reject(Error('ERROR OBSOLETO'));else pending.resolve(response(report(C,'aprobado')));await running;assert.equal(h.get('informeEstado').textContent,before);assert.notEqual(h.get('informeVersion').value,C);
});
test('error tardío de historial no reemplaza nueva versión',async()=>{
 const h=harness();await h.init();await h.open();const pending=deferred();h.state.handler=url=>url.pathname==='/api/informes'?pending.promise:undefined;const running=h.get('informeActualizar').onclick();await h.open(O);const before=h.get('informeEstado').textContent;pending.reject(Error('HISTORIAL OBSOLETO'));await running;assert.equal(h.get('informeEstado').textContent,before);
});
(async()=>{for(const {name,fn}of tests){await fn();console.log('OK '+name);}console.log(`${tests.length}/${tests.length} OK`);})().catch(error=>{console.error(error);process.exitCode=1;});
