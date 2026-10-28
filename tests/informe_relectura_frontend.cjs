// Integración del controlador real: selección explícita, cambios de fuente y respuesta del servidor.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const R='1'.repeat(32),A='2'.repeat(32),B='3'.repeat(32),M='4'.repeat(32),J='5'.repeat(32),V='6'.repeat(32),N='7'.repeat(32);
const FP='a'.repeat(64),H='b'.repeat(64),S='c'.repeat(64),MH='d'.repeat(64);
const ref={trabajo:J,id:V,sha256_registro:S};
const settle=async()=>{for(let i=0;i<4;i++)await new Promise(setImmediate);};
function harness(){
 const elements={},listeners={},state={calls:[],records:{},dropRef:false};
 const get=id=>elements[id]??={value:'',textContent:'',checked:false,disabled:false,events:{},reset(){},reportValidity(){return true;},addEventListener(k,f){(this.events[k]??=[]).push(f);}};
 const response=x=>({json:async()=>structuredClone(x)});
 const ctx={docs:{caso:'A',expediente_sha256:FP},busy:false,$:get,URLSearchParams,structuredClone,
  window:{addEventListener(k,f){(listeners[k]??=[]).push(f);}},
  options(el,rows){el.options=rows;el.value=rows[0][0];},message(x){state.error=x;},action:f=>f(),
  async api(url,body){state.calls.push({url,body:body&&JSON.parse(JSON.stringify(body))});const p=new URL(url,'http://localhost');
   if(p.pathname==='/api/analisis')return response({versiones:[{id:A,vigente:null,verificacion:'pendiente',estados:null,casos:null},{id:B,vigente:null,verificacion:'pendiente',estados:null,casos:null}]});
   if(p.pathname==='/api/analisis/comprobar')return response({id:p.searchParams.get('analisis'),vigente:true,verificacion:'completa',estados:{},casos:[]});
   if(p.pathname==='/api/informes')return response({versiones:Object.values(state.records).map(x=>({id:x.id,vigente:true}))});
   if(p.pathname==='/api/informe')return response(state.records[p.searchParams.get('version')]);
   if(p.pathname==='/api/informe/crear'){
    const item={id:N,caso:'A',resultado:R,analisis:body.analisis,huella_resultados:H,expediente_sha256:FP,estado:'borrador',archivos:{'informe.json':H},aprueba_resultados:false,revision_resultados:'pendiente',conformidad_normativa:'no_evaluada'};
    if(body.relectura_modelo&&!state.dropRef)item.relectura_modelo_seleccionada=body.relectura_modelo;
    state.records[N]=item;return response(item);
   }throw Error('Ruta inesperada '+url);
  }};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/informes.js'),'utf8'),ctx);
 const emit=(type,detail)=>{for(const f of listeners[type]||[])f({detail});};
 const input=async(id,type='input')=>{for(const f of get(id).events[type]||[])await f({type});};
 const selectModel=()=>emit('d2m-model',{version:M,record:{expediente_sha256:FP,huella_modelo:MH}});
 const proof=extra=>({id:J,verificacion_id:V,sha256_registro:S,caso:'A',expediente_sha256:FP,modelo:M,huella_modelo:MH,estado:'aceptado',lectura_comprobada:true,vigente:true,resultado:{estado:'incompleto',verificacion_global_del_plan:false},...extra});
 async function init(){emit('d2m-result',{version:R,record:{caso:'A',expediente_sha256:FP,huella:H}});await settle();get('informeAnalisis').value=A;await input('informeAnalisis','change');await settle();selectModel();get('informeTitulo').value='Prueba sintética';}
 async function submit(){await get('informeForm').onsubmit({preventDefault(){}});await settle();return state.calls.filter(x=>x.url==='/api/informe/crear').at(-1)?.body;}
 return {get,state,emit,input,selectModel,proof,init,submit};
}
(async()=>{
 const h=harness();await h.init();assert.equal(h.get('informeUsarRelectura').disabled,true);
 assert.equal('relectura_modelo' in await h.submit(),false);
 h.emit('d2m-model-verification',h.proof());assert.equal(h.get('informeUsarRelectura').disabled,false);assert.equal(h.get('informeUsarRelectura').checked,false);
 h.get('informeUsarRelectura').checked=true;await h.input('informeUsarRelectura');
 assert.match(h.get('informeRelecturaInfo').textContent,/incompleto/);assert.deepEqual((await h.submit()).relectura_modelo,ref);
 h.state.dropRef=true;h.emit('d2m-model-verification',h.proof());h.get('informeUsarRelectura').checked=true;await h.input('informeUsarRelectura');await h.submit();
 assert.match(h.state.error||h.get('informeEstado').textContent,/no conserva la relectura/);
 for(const extra of [{vigente:false},{lectura_comprobada:false},{modelo:B},{huella_modelo:H}]){h.emit('d2m-model-verification',h.proof(extra));assert.equal(h.get('informeUsarRelectura').disabled,true);}
 h.emit('d2m-model-verification',h.proof());h.get('informeUsarRelectura').checked=true;h.get('informeAnalisis').value=B;await h.input('informeAnalisis','change');await settle();assert.equal(h.get('informeUsarRelectura').checked,false);
 h.selectModel();assert.equal(h.get('informeUsarRelectura').disabled,true);
 h.emit('d2m-model-verification',h.proof());h.emit('d2m-model-verification',null);assert.equal(h.get('informeUsarRelectura').disabled,true);
 const html=fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/index.html'),'utf8');
 for(const id of ['informeUsarRelectura','informeRelecturaInfo','informeRelecturaDatos'])assert.equal(html.split('id="'+id+'"').length-1,1);
 console.log('Informe-relectura: selección exacta, incompleto visible, invalidación, conservación del servidor y controles HTML: OK');
})().catch(e=>{console.error(e);process.exit(1);});
