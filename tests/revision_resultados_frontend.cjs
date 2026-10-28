// Prueba de carreras del cliente con DOM mínimo, sin navegador ni motor.
const fs=require('node:fs');const vm=require('node:vm');const assert=require('node:assert/strict');const path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/resultados.js'),'utf8');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function element(tag='div'){
 return {tag,value:'',textContent:'',disabled:false,children:[],append(...nodes){this.children.push(...nodes);},replaceChildren(...nodes){this.children=nodes;},click(){}};
}
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
function harness(){
 const elements=new Map(),events={},requests={},state={};
 const get=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);};
 const context={console,docs:null,busy:false,$:get,Blob,URLSearchParams,CustomEvent:class {constructor(type,options){this.type=type;this.detail=options.detail;}},URL:{createObjectURL(blob){state.blob=blob;return 'blob:prueba';},revokeObjectURL(){}},
  window:{addEventListener(name,fn){events[name]=fn;},dispatchEvent(event){events[event.type]?.(event);}},document:{createElement:element},
  options(select,rows){select.replaceChildren(...rows.map(([value,label])=>({...element('option'),value,textContent:label})));select.value=rows[0][0];},
  message(text){state.message=text;},action:async fn=>fn(),
  api(url){
   const parsed=new URL(url,'http://127.0.0.1');const caso=parsed.searchParams.get('caso');
   if(['/api/modelos','/api/resultados'].includes(parsed.pathname))return Promise.resolve({json:async()=>({versiones:[{id:caso,vigente:true}]})});
   const request=deferred();requests[caso]=request;return request.promise;
  }};
 vm.runInNewContext(code,context);
 return {get,events,requests,context,state};
}
function response(caso){return {json:async()=>({datos:{datos_sinteticos:true,motor:{nombre:caso,version:'1'},resultados:[{id:caso,caso,direccion:'X',ubicacion:'base',valor:1,unidad:'kN'}],advertencias:[],omisiones:[]}})};}
async function staleRequest(reject){
 const h=harness();
 h.context.docs={caso:'A',expediente_sha256:'a'.repeat(64)};h.events['d2m-case']();await flush();
 h.get('resultadoVersion').value='A';h.get('resultadoVersion').onchange();
 h.context.docs={caso:'B',expediente_sha256:'b'.repeat(64)};h.events['d2m-case']();await flush();
 h.get('resultadoVersion').value='B';h.get('resultadoVersion').onchange();h.requests.B.resolve(response('B'));await flush();
 const expected=h.get('resultadoEstado').textContent;
 if(reject)h.requests.A.reject(Error('Error obsoleto del expediente A'));else h.requests.A.resolve(response('A'));
 await flush();assert.equal(h.get('resultadoEstado').textContent,expected,'La respuesta obsoleta alteró el expediente nuevo');
 assert.equal(h.get('resultadoFilas').children[0].children[0].textContent,'B');
 h.get('resultadoDescargar').onclick();assert.equal(JSON.parse(await h.state.blob.text()).motor.nombre,'B');
}
(async()=>{await staleRequest(false);await staleRequest(true);console.log('Carreras de éxito/error y descarga del expediente vigente: OK');})().catch(error=>{console.error(error);process.exitCode=1;});
