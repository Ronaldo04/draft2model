// Cliente documental: descarta consultas tardías y conserva la descarga vigente.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/informes.js'),'utf8');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
function harness(){
 const elements={},events={},requests={},state={};
 const get=id=>elements[id]??=( {value:'',textContent:'',disabled:false,options:[],reset(){},reportValidity(){return true;}} );
 const context={busy:false,docs:{caso:'A'},$:get,URLSearchParams,
  URL:{createObjectURL(blob){state.blob=blob;return 'blob:prueba';},revokeObjectURL(){}},
  document:{createElement(){return {click(){state.clicked=true;}};}},
  window:{addEventListener(name,fn){events[name]=fn;}},
  options(select,rows){select.options=rows.map(([value,textContent])=>({value,textContent}));select.value=rows[0][0];},
  message(text){state.error=text;},action:async fn=>fn(),
  api(url){const parsed=new URL(url,'http://127.0.0.1');const id=parsed.searchParams.get('version');
   if(['/api/analisis','/api/informes'].includes(parsed.pathname))return Promise.resolve({json:async()=>({versiones:[]})});
   if(parsed.pathname==='/api/informe/archivo')return Promise.resolve({blob:async()=>new Blob([id])});
   const req=deferred();requests[id]=req;return req.promise;
  }};
 vm.runInNewContext(code,context);
 function selectResult(caso){context.docs={caso};events['d2m-result']({detail:{version:caso,record:{expediente_sha256:caso.repeat(64)}}});}
 return {get,context,events,requests,state,selectResult};
}
const response=id=>({json:async()=>({id,evidencia_analisis:null})});
async function race(reject,sameCase){
 const h=harness();h.selectResult('A');await flush();
 h.get('informeVersion').value='antiguo';h.get('informeVersion').onchange();
 if(!sameCase){h.selectResult('B');await flush();}
 h.get('informeVersion').value='vigente';h.get('informeVersion').onchange();
 h.requests.vigente.resolve(response('vigente'));await flush();
 const expected=h.get('informeEstado').textContent;
 if(reject)h.requests.antiguo.reject(Error('Error obsoleto'));else h.requests.antiguo.resolve(response('antiguo'));
 await flush();assert.equal(h.get('informeEstado').textContent,expected);assert.equal(h.state.error,undefined);
 await h.get('informePdf').onclick();assert.equal(await h.state.blob.text(),'vigente');assert.equal(h.state.clicked,true);
 h.events['d2m-case']();assert.equal(h.get('informePdf').disabled,true);
}
(async()=>{for(const reject of [false,true])for(const sameCase of [false,true])await race(reject,sameCase);
 console.log('Informes: respuestas obsoletas en caso/versión, descarga y reinicio: OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
