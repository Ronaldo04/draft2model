const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/mapeos.js'),'utf8');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
function record(id,estado='borrador'){return {id,analisis:'a'.repeat(32),expediente_sha256:'f'.repeat(64),huella_mapeo:'h-'+id,
 mapeo:{id,revision:{estado,aprobacion:null}},previsualizacion:{publicado:false},analisis_verificado:{corrida_id:'a'.repeat(32)}};}
function harness(){
 const elements={},events={},calls=[],pending={},state={records:{aprobado:record('aprobado','aprobado')},events:[]};let serial=0;
 const get=id=>elements[id]??={value:'',textContent:'',checked:false,disabled:false,events:{},checkValidity(){return true;},reportValidity(){return true;},addEventListener(name,fn){this.events[name]=fn;}};
 const context={busy:false,docs:{caso:'caso',expediente_sha256:'f'.repeat(64)},$:get,URLSearchParams,TextEncoder,Uint8Array,
  crypto:{randomUUID(){return (++serial).toString().padStart(32,'0');},subtle:require('node:crypto').webcrypto.subtle},
  CustomEvent:class{constructor(type,options){this.type=type;this.detail=options.detail;}},
  window:{addEventListener(name,fn){events[name]=fn;},dispatchEvent(event){state.events.push(event);}},
  options(select,rows){select.options=rows.map(([value,textContent])=>({value,textContent}));select.value=rows[0][0];},
  message(text){state.error=text;},action:async fn=>{try{return await fn();}catch(error){state.error=error.message;}},
  api(url,body){calls.push({url,body});const parsed=new URL(url,'http://127.0.0.1');
   if(parsed.pathname==='/api/mapeo/fuente'&&state.proof)return Promise.resolve({json:async()=>state.proof});
   if(parsed.pathname==='/api/mapeo/importar-lectura')return Promise.resolve({json:async()=>({id:'aprobado'})});
   if(parsed.pathname==='/api/mapeos')return Promise.resolve({json:async()=>({versiones:[{id:'aprobado',vigente:true,estado:'aprobado'}]})});
   if(parsed.pathname==='/api/mapeo/aprobar')return Promise.resolve({json:async()=>({id:'aprobado'})});
   if(parsed.pathname==='/api/mapeo/normalizar')return Promise.resolve({json:async()=>({resultado:'resultado-nuevo'})});
   const id=parsed.searchParams.get('version');if(state.records[id])return Promise.resolve({json:async()=>state.records[id]});
   const req=deferred();pending[id]=req;return req.promise;
  }};
 vm.runInNewContext(code,context);return {get,events,calls,pending,state,context};
}
(async()=>{
 const h=harness();h.get('mapeoVersion').value='viejo';h.get('mapeoVersion').onchange();
 h.get('mapeoVersion').value='actual';h.get('mapeoVersion').onchange();h.pending.actual.resolve({json:async()=>record('actual')});await flush();
 h.pending.viejo.reject(Error('Error de versión vieja'));await flush();assert.equal(h.state.error,undefined);assert.equal(h.get('mapeoHuella').value,'h-actual');
 for(const id of ['mapeoRevisor','mapeoMotivo','mapeoAlcance'])h.get(id).value='Revisión sintética';h.get('mapeoFecha').value='2026-10-17';
 h.get('mapeoConfirmar').checked=true;h.context.window.mappingControls();assert.equal(h.get('mapeoAprobar').disabled,false);
 const original=h.get('mapeoJson').value;h.get('mapeoJson').value+=' ';h.get('mapeoJson').events.input();assert.equal(h.get('mapeoConfirmar').checked,false);assert.equal(h.get('mapeoAprobar').disabled,true);
 h.get('mapeoJson').value=original;h.get('mapeoConfirmar').checked=true;h.get('mapeoAprobacionForm').onsubmit({preventDefault(){}});await flush();await flush();
 assert.equal(h.get('mapeoHuella').value,'h-aprobado');assert.equal(h.get('mapeoNormalizar').disabled,true);
 for(let i=0;i<2;i++){h.get('mapeoNormalizarConfirmar').checked=true;await h.get('mapeoNormalizar').onclick();}
 const norms=h.calls.filter(c=>c.url==='/api/mapeo/normalizar');assert.equal(norms.length,2);assert.equal(norms[0].body.clave_solicitud,norms[1].body.clave_solicitud);
 assert.equal(h.state.events.at(-1).type,'d2m-result-created');assert.equal(h.state.events.at(-1).detail.resultado,'resultado-nuevo');
 h.events['d2m-case']();assert.equal(h.get('mapeoNormalizar').disabled,true);
 const n=harness();n.state.proof={corrida_id:'a'.repeat(32),datos_sinteticos:true,configuracion:{huella:'c'.repeat(64)},sha256_edb_analizado:'e'.repeat(64),version_etabs:'21'};
 const reading={id:'t'.repeat(32),analisis:'a'.repeat(32),caso:'caso',expediente_sha256:'f'.repeat(64),lectura_verificada:true,vigente:true,
  modo_ejecucion:'doble',sha256_respuesta:'r'.repeat(64),datos_tablas:{unidades:'kN_m_C',tablas:[]}};
 n.events['d2m-reading']({detail:{...reading,caso:'ajeno'}});assert.equal(n.calls.length,0);
 n.events['d2m-reading']({detail:reading});await flush();
 const skeleton=JSON.parse(n.get('mapeoJson').value);assert.equal(skeleton.sha256_respuesta,reading.sha256_respuesta);assert.equal(skeleton.selectores.length,0);
 assert.equal(n.get('mapeoImportar').disabled,false);await n.get('mapeoImportar').onclick();
 const transfer=n.calls.find(c=>c.url==='/api/mapeo/importar-lectura');assert.equal(transfer.body.trabajo_lectura,reading.id);assert.equal(transfer.body.respuesta_json,undefined);
 assert.equal(n.calls.some(c=>c.url==='/api/mapeo/importar'),false);
 console.log('Mapeos: descarte obsoleto, cambios sin aprobar, confirmación y clave idempotente: OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
