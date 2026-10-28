// informes.js real: selección optativa de controles postsolver exacta (mismo análisis, ID y SHA), sin heredar ni elegir la última.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const R='1'.repeat(32),A='2'.repeat(32),B='3'.repeat(32),C='4'.repeat(32),D='6'.repeat(32),N='7'.repeat(32),FP='a'.repeat(64),H='b'.repeat(64),SC='c'.repeat(64);
const response=v=>({json:async()=>structuredClone(v)}),settle=async()=>{for(let i=0;i<4;i++)await new Promise(setImmediate);};
function report(id,ref){return {id,caso:'A',resultado:R,analisis:A,huella_resultados:H,expediente_sha256:FP,estado:'borrador',archivos:{'informe.json':H},
 aprueba_resultados:false,revision_resultados:'pendiente',conformidad_normativa:'no_evaluada',...(ref?{controles_analisis_seleccionados:ref,controles_analisis:{estado_global:'sin_datos',apto_proyeccion_controlado:false}}:{})};}
function harness(){
 const elements={},listeners={},state={calls:[],records:{[D]:report(D)},rows:[{id:D,vigente:true}],dropRef:false};
 const get=id=>elements[id]??={value:'',textContent:'',checked:false,disabled:false,options:[],events:{},reset(){},reportValidity(){return true;},addEventListener(k,f){(this.events[k]??=[]).push(f);}};
 const window={addEventListener(k,f){(listeners[k]??=[]).push(f);}},ctx={docs:{caso:'A',expediente_sha256:FP},busy:false,$:get,window,URLSearchParams,structuredClone,
  options(select,rows){select.options=rows.map(([value,textContent])=>({value,textContent}));select.value=rows[0][0];},message(text){state.error=text;},action:fn=>fn(),
  URL:{createObjectURL(){return 'blob:t';},revokeObjectURL(){}},document:{createElement(){return {click(){}};}},
  async api(url,body){if(body)body=JSON.parse(JSON.stringify(body));state.calls.push({url,body});const p=new URL(url,'http://localhost');
   switch(p.pathname){
    case '/api/analisis':return response({versiones:[{id:A,vigente:null,verificacion:'pendiente',estados:null,casos:null},{id:B,vigente:null,verificacion:'pendiente',estados:null,casos:null}]});
    case '/api/analisis/comprobar':return response({id:p.searchParams.get('analisis'),vigente:true,verificacion:'completa',estados:{},casos:[]});
    case '/api/informes':return response({versiones:state.rows});
    case '/api/informe':return response(state.records[p.searchParams.get('version')]);
    case '/api/informe/crear':{const v=report(N,state.dropRef?undefined:body.controles_analisis);v.analisis=body.analisis;state.records[N]=v;state.rows.push({id:N,vigente:true});return response(v);}
    default:throw Error('Ruta inesperada '+p.pathname);
   }}};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/informes.js'),'utf8'),ctx,{filename:'informes.js'});
 const emit=(t,d)=>{for(const f of listeners[t]||[])f({detail:d});};
 async function input(id,type='input'){for(const f of get(id).events[type]||[])await f({type});}
 async function init(){emit('d2m-result',{version:R,record:{caso:'A',expediente_sha256:FP,huella:H}});await settle();get('informeTitulo').value='Prueba';}
 async function analysis(id){get('informeAnalisis').value=id;await input('informeAnalisis','change');await settle();}
 const controls=(extra={})=>({caso:'A',expediente_sha256:FP,id:C,sha256_controles:SC,analisis:A,estado_global:'sin_datos',apto_proyeccion_controlado:false,...extra});
 async function submit(){await get('informeForm').onsubmit({preventDefault(){}});await settle();return state.calls.filter(c=>c.url==='/api/informe/crear').at(-1)?.body;}
 return {get,state,emit,input,init,analysis,controls,submit};
}
const tests=[];function test(n,f){tests.push({n,f});}

test('sin selección explícita el cuerpo no incluye controles',async()=>{
 const h=harness();await h.init();await h.analysis(A);assert.equal(h.get('informeUsarControles').disabled,true);
 const body=await h.submit();assert.equal('controles_analisis' in body,false);assert.match(h.get('informeControlesInfo').textContent,/Sin controles/);
});

test('mismo análisis + opt-in envía {id, sha256_controles} exactos y el creado debe conservarlos',async()=>{
 const h=harness();await h.init();await h.analysis(A);h.emit('d2m-controls-review',h.controls());
 assert.equal(h.get('informeUsarControles').checked,false);assert.equal(h.get('informeUsarControles').disabled,false);
 h.get('informeUsarControles').checked=true;await h.input('informeUsarControles');assert.match(h.get('informeControlesInfo').textContent,/NO apto/);
 const body=await h.submit();assert.deepEqual(body.controles_analisis,{id:C,sha256_controles:SC});assert.equal(body.analisis,A);
 h.state.dropRef=true;h.emit('d2m-controls-review',h.controls());h.get('informeUsarControles').checked=true;await h.input('informeUsarControles');
 await h.submit();assert.match(h.state.error||h.get('informeEstado').textContent,/no conserva los controles/);
});

test('controles de otro análisis o caso no se aceptan y cambiar análisis desmarca',async()=>{
 const h=harness();await h.init();await h.analysis(B);h.emit('d2m-controls-review',h.controls());
 assert.equal(h.get('informeUsarControles').disabled,true);
 await h.analysis(A);h.emit('d2m-controls-review',h.controls());h.get('informeUsarControles').checked=true;await h.input('informeUsarControles');
 await h.analysis(B);assert.equal(h.get('informeUsarControles').checked,false);
 h.emit('d2m-controls-review',h.controls({caso:'OTRO'}));await h.analysis(A);assert.equal(h.get('informeUsarControles').disabled,false); // evento ajeno ignorado; conserva el válido previo
 h.emit('d2m-controls-review',null);assert.equal(h.get('informeUsarControles').disabled,true);
});

(async()=>{for(const t of tests)await t.f();console.log('Informe-controles: opt-in exacto, conservación al crear y aislamiento de análisis/caso: OK ('+tests.length+')');})()
 .catch(e=>{console.error(e);process.exit(1);});
