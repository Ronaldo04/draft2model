const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/informes.js'),'utf8');
const flush=()=>new Promise(r=>setImmediate(r));
const id='a'.repeat(32),fp='b'.repeat(64),result='c'.repeat(32);
async function scenario(failure){
 const elements={},events={},calls=[];let resolve,reject;
 const opened=new Promise((a,b)=>{resolve=a;reject=b;});
 const get=id=>elements[id]??={value:'',textContent:'',disabled:false,checked:false,options:[],reset(){},reportValidity(){return true;}};
 const context={busy:false,docs:{caso:'caso',expediente_sha256:fp},$:get,URLSearchParams,
  options(el,rows){el.options=rows.map(([value,textContent])=>({value,textContent}));el.value=rows[0][0];},
  window:{addEventListener(name,fn){events[name]=fn;}},document:{createElement(){return {click(){}};}},
  message(){},action:async fn=>fn(),URL:{createObjectURL(){return 'blob:test';},revokeObjectURL(){}},
  api(url){calls.push(url);const u=new URL(url,'http://localhost');
   if(u.pathname==='/api/analisis')return Promise.resolve({json:async()=>({versiones:[]})});
   if(u.pathname==='/api/informes')return Promise.resolve({json:async()=>({modo:'inventario',versiones:[{id,vigente:null,verificacion:'pendiente',estado:null,analisis:null}]})});
   if(u.pathname==='/api/informe')return opened;
   throw Error('Solicitud inesperada: '+u.pathname);
  }};
 vm.runInNewContext(code,context);
 events['d2m-result']({detail:{version:result,record:{expediente_sha256:fp}}});await flush();
 assert.ok(calls.some(u=>u.startsWith('/api/informes?')&&u.includes('modo=inventario')));
 assert.match(get('informeVersion').options[1].textContent,/sin comprobar/);
 assert.equal(get('informePdf').disabled,true);assert.equal(get('informeAprobar').disabled,true);
 assert.equal(calls.filter(u=>u.startsWith('/api/informe?')).length,0);
 get('informeVersion').value=id;const task=get('informeVersion').onchange();await flush();
 assert.equal(get('informePdf').disabled,true);assert.match(get('informeEstado').textContent,/Comprobando/);
 if(failure)reject(Error('Fuente alterada'));else resolve({json:async()=>({id,caso:'caso',resultado:result,expediente_sha256:fp,estado:'borrador',archivos:{'informe.json':'d'.repeat(64)}})});
 await task;await flush();
 assert.equal(get('informePdf').disabled,failure);
 assert.equal(calls.filter(u=>u.startsWith('/api/informe?')).length,1);
}
(async()=>{await scenario(false);await scenario(true);console.log('Inventario no habilita descarga/aprobación; apertura verificada o rechazada: OK');})().catch(e=>{console.error(e);process.exitCode=1;});
