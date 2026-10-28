const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/ingreso.js'),'utf8');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function harness(){
 const elements={},calls=[],state={fail:true,opened:0};let serial=0;
 const get=id=>elements[id]??={value:'',disabled:false,checked:false,textContent:'',files:[],events:{},reportValidity(){return true;},addEventListener(name,fn){this.events[name]=fn;}};
 const context={busy:false,$:get,crypto:{randomUUID(){return (++serial).toString().padStart(32,'0');}},
  FileReader:class{readAsDataURL(file){this.result='data:image/png;base64,'+file.encoded;this.onload();}},
  options(){},openCase:async()=>state.opened++,action:async fn=>{try{await fn();}catch(error){state.error=error.message;}},
  api:async(url,body)=>{calls.push({url,body});if(url==='/api/ingreso/registrar'){
   if(state.fail)throw Error('Fallo de conexión');return {json:async()=>({caso:body.caso,resumen:{paginas_renderizadas:1,archivos_con_error:0}})};}
   return {json:async()=>({casos:[{id:'nuevo'}]})};},window:{}};
 vm.runInNewContext(code,context);get('ingresoCaso').value='nuevo';get('ingresoArchivos').files=[{name:'plano.png',size:5,encoded:'Ynl0ZXM='}];
 return {get,calls,state,context,submit:async()=>{get('ingresoForm').onsubmit({preventDefault(){}});await flush();}};
}
(async()=>{
 const h=harness();await h.submit();assert.equal(h.calls.length,0);assert.match(h.state.error,/autorizado/);
 h.get('ingresoAutorizado').checked=true;await h.submit();await h.submit();
 assert.equal(h.calls[0].body.clave_solicitud,h.calls[1].body.clave_solicitud);assert.equal(h.calls[0].body.archivos[0].contenido_base64,'Ynl0ZXM=');
 h.get('ingresoCaso').events.input();h.state.fail=false;await h.submit();
 assert.notEqual(h.calls[2].body.clave_solicitud,h.calls[1].body.clave_solicitud);assert.equal(h.state.opened,1);assert.equal(h.get('caso').value,'nuevo');
 assert.match(h.get('ingresoEstado').textContent,/revisión humana pendiente/);
 const b=harness();b.get('ingresoAutorizado').checked=true;b.get('ingresoArchivos').files=[{size:17*1024*1024}];await b.submit();assert.equal(b.calls.length,0);
 console.log('Ingreso: autorización, tamaño, clave tras fallo de conexión, nueva selección y apertura: OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
