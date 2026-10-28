// informes.js y paneles.js reales; HTTP/DOM simulados. 301: el selector de análisis usa inventario (vigente:null, sin acreditar
// vínculo); al seleccionar se comprueba SOLO ese análisis vía /api/analisis/comprobar; crear queda bloqueado hasta respuesta vigente
// de esa misma selección/caso/resultado; respuestas antiguas se descartan; fuente alterada (error) no habilita; sin caché de vigencia.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const R='1'.repeat(32),R2='5'.repeat(32),A='2'.repeat(32),B='3'.repeat(32),FP='a'.repeat(64),H='b'.repeat(64);
const settle=async()=>{for(let i=0;i<8;i++)await new Promise(setImmediate);};
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
const response=v=>({json:async()=>structuredClone(v)});
const ok=id=>({id,vigente:true,verificacion:'completa',estados:{},casos:['EST']});
function harness(modulo,inventario=[{id:A,vigente:null,verificacion:'pendiente',estados:null,casos:null},{id:B,vigente:null,verificacion:'pendiente',estados:null,casos:null}]){
 const elements={},listeners={},state={calls:[],pending:{},error:null};
 const get=id=>elements[id]??={value:'',textContent:'',checked:false,disabled:false,options:[],events:{},reset(){},reportValidity(){return true;},addEventListener(k,f){(this.events[k]??=[]).push(f);}};
 const window={addEventListener(k,f){(listeners[k]??=[]).push(f);}};
 const ctx={docs:{caso:'A',expediente_sha256:FP},busy:false,$:get,window,URLSearchParams,structuredClone,
  options(select,rows){select.options=rows.map(([value,textContent])=>({value,textContent}));select.value=rows[0][0];},message(text){state.error=text;},action:fn=>fn(),
  URL:{createObjectURL(){return 'blob:t';},revokeObjectURL(){}},document:{createElement(){return {click(){}};}},
  async api(url,body){state.calls.push({url,body});const p=new URL(url,'http://localhost');
   switch(p.pathname){
    case '/api/analisis':return response({versiones:inventario});
    case '/api/analisis/comprobar':{const d=deferred();(state.pending[p.searchParams.get('analisis')]??=[]).push(d);return d.promise;}
    case '/api/informes':case '/api/paneles':return response({versiones:[]});
    case '/api/informe/crear':case '/api/panel/crear':return Promise.reject(Error('creación simulada'));
    default:throw Error('Ruta inesperada '+p.pathname);
   }}};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/'+modulo+'.js'),'utf8'),ctx,{filename:modulo+'.js'});
 const pre=modulo==='informes'?'informe':'panel',emit=(t,d)=>{for(const f of listeners[t]||[])f({detail:d});};
 const result=(version=R)=>emit('d2m-result',{version,record:{caso:'A',expediente_sha256:FP,huella:H}});
 async function select(id){get(pre+'Analisis').value=id;for(const f of get(pre+'Analisis').events.change||[])f({type:'change'});await settle();}
 const checks=id=>state.calls.filter(c=>c.url.startsWith('/api/analisis/comprobar')&&(!id||new URL(c.url,'http://x').searchParams.get('analisis')===id));
 const crear=()=>get(pre+'Crear');
 async function submit(){if(modulo==='informes'){get('informeTitulo').value='Prueba';await get('informeForm').onsubmit({preventDefault(){}});}else await get('panelCrear').onclick();await settle();
  return state.calls.filter(c=>c.url===(modulo==='informes'?'/api/informe/crear':'/api/panel/crear'));}
 return {get,state,ctx,emit,result,select,checks,crear,submit,pre};
}
const tests=[];function test(n,f){tests.push({n,f});}

for(const modulo of ['informes','paneles']){
 test(modulo+': inventario con modo=inventario, «sin comprobar», sin comprobación ni selección automáticas',async()=>{
  const h=harness(modulo);h.result();await settle();
  const listado=h.state.calls.find(c=>c.url.startsWith('/api/analisis?'));assert.equal(new URL(listado.url,'http://x').searchParams.get('modo'),'inventario');
  const sel=h.get(h.pre+'Analisis');assert.equal(sel.value,'');assert.deepEqual(Array.from(sel.options,o=>o.value),['',A,B]);
  assert.ok(sel.options.slice(1).every(o=>/sin comprobar/.test(o.textContent)&&!o.disabled));
  assert.equal(h.checks().length,0);assert.equal(h.crear().disabled,false);   // sin análisis elegido: recorrido anterior sin evidencia
 });
 test(modulo+': seleccionar comprueba una vez y crear queda bloqueado hasta respuesta vigente',async()=>{
  const h=harness(modulo);h.result();await settle();await h.select(A);
  assert.equal(h.checks(A).length,1);assert.equal(h.checks().length,1);
  const q=new URL(h.checks(A)[0].url,'http://x').searchParams;assert.deepEqual([q.get('caso'),q.get('resultado'),q.get('expediente_sha256')],['A',R,FP]);
  assert.equal(h.crear().disabled,true);assert.equal((await h.submit()).length,0);
  h.state.pending[A][0].resolve(response(ok(A)));await settle();
  assert.equal(h.crear().disabled,false);assert.match(h.get(h.pre+'AnalisisEstado').textContent,/comprobado/);
  assert.equal((await h.submit()).length,1);
 });
 test(modulo+': respuesta antigua tras cambiar selección o resultado se descarta',async()=>{
  const h=harness(modulo);h.result();await settle();await h.select(A);await h.select(B);
  h.state.pending[A][0].resolve(response(ok(A)));await settle();assert.equal(h.crear().disabled,true);
  h.state.pending[B][0].resolve(response(ok(B)));await settle();assert.equal(h.crear().disabled,false);
  await h.select(A);h.result(R2);await settle();h.state.pending[A][1].resolve(response(ok(A)));await settle();
  assert.equal(h.get(h.pre+'Analisis').value,'');assert.doesNotMatch(h.get(h.pre+'AnalisisEstado').textContent,/comprobado/);
 });
 test(modulo+': fuente alterada (error del servidor) no habilita y no hay POST',async()=>{
  const h=harness(modulo);h.result();await settle();await h.select(A);
  h.state.pending[A][0].reject(Error('Fuente alterada: huella de análisis distinta.'));await settle();
  assert.equal(h.crear().disabled,true);assert.match(h.get(h.pre+'AnalisisEstado').textContent,/Comprobación fallida: Fuente alterada/);
  assert.equal((await h.submit()).length,0);
 });
 test(modulo+': respuesta ajena o incompleta no habilita; null del inventario nunca se toma como vigente',async()=>{
  const h=harness(modulo,[{id:A,vigente:true,verificacion:'completa'}]);h.result();await settle();
  assert.equal(h.get(h.pre+'Analisis').options[1].textContent.includes('sin comprobar'),true);
  await h.select(A);assert.equal(h.crear().disabled,true);
  h.state.pending[A][0].resolve(response({...ok(A),verificacion:'pendiente'}));await settle();assert.equal(h.crear().disabled,true);
  await h.select(A);h.state.pending[A][1].resolve(response({...ok(B)}));await settle();assert.equal(h.crear().disabled,true);
  await h.select(A);h.state.pending[A][2].resolve(response({...ok(A),vigente:null}));await settle();assert.equal(h.crear().disabled,true);
 });
 test(modulo+': sin caché de vigencia; reseleccionar vuelve a comprobar',async()=>{
  const h=harness(modulo);h.result();await settle();await h.select(A);h.state.pending[A][0].resolve(response(ok(A)));await settle();
  assert.equal(h.crear().disabled,false);await h.select('');assert.equal(h.crear().disabled,false);await h.select(A);
  assert.equal(h.checks(A).length,2);assert.equal(h.crear().disabled,true);
 });
}

test('informes: opciones dependientes de evidencia (inventario de masa) solo tras comprobación vigente',async()=>{
 const h=harness('informes');h.result();await settle();await h.select(A);
 assert.equal(h.get('informeUsarContenidoMasa').disabled,true);
 h.state.pending[A][0].resolve(response(ok(A)));await settle();assert.equal(h.get('informeUsarContenidoMasa').disabled,false);
});

(async()=>{let fallos=0;for(const {n,f} of tests){try{await f();}catch(e){fallos++;console.error('FAIL '+n+'\n'+e.stack);}}
 if(fallos){console.error(fallos+' fallo(s)');process.exit(1);}console.log('Análisis 301: inventario, comprobación explícita por selección, descarte obsoleto y bloqueo: OK ('+tests.length+')');})();
