// Diagnóstico focal: controladores reales con bus/HTTP/DOM simulados; no servidor ni ETABS.
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'revision_eventos_integrados_frontend.cjs'),'utf8').split('const tests=[];')[0];
const sandbox={require,__dirname,console,URL,URLSearchParams,Blob,TextEncoder,Uint8Array,setImmediate};
vm.runInNewContext(source+'\nglobalThis.make=harness;',sandbox);const h=sandbox.make();
const get=h.get;
get('informeForm').reset=()=>{};
vm.runInContext(fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/informes.js'),'utf8'),h.context,{filename:'informes.js'});
const settle=async()=>{for(let i=0;i<6;i++)await new Promise(setImmediate);};
(async()=>{
 h.context.docs=null;h.emit('d2m-case');await settle();assert.equal(get('resultadoEstado').textContent,'Selecciona un expediente.');
 const before=h.calls.length;h.context.docs={caso:'A',expediente_sha256:'a'.repeat(64)};h.emit('d2m-case');await settle();
 assert.equal(get('resultadoEstado').textContent,'1 versión(es) conservada(s); se comprueban al abrir.');
 assert.equal(get('modeloEstado').textContent,'No hay versiones conservadas en este expediente.');
 assert.equal(get('lecturaMasaApi').disabled,false);
 assert.equal(h.calls.slice(before).some(c=>c.url.startsWith('/api/modelos?')),true);
 assert.equal(h.calls.slice(before).some(c=>c.url.startsWith('/api/resultados?')),true);
 assert.equal(h.state.errors.length,0,JSON.stringify(h.state.errors));
 console.log('OK: d2m-case null→caso real, resultados+modelos listados, masa habilitada, informes sin colisión ni excepción.');
 // Un fallo síncrono anterior al final de clear reproduce el síntoma de estado antiguo.
 const original=get('resultadoFilas').replaceChildren;
 get('resultadoFilas').replaceChildren=()=>{throw Error('DOM hipotéticamente inválido');};
 h.context.docs=null;try{h.emit('d2m-case');}catch{}
 get('resultadoEstado').textContent='Selecciona un expediente.';
 h.context.docs={caso:'A',expediente_sha256:'a'.repeat(64)};const calls=h.calls.length;
 assert.throws(()=>h.emit('d2m-case'),/DOM hipotéticamente inválido/);
 assert.equal(get('resultadoEstado').textContent,'Selecciona un expediente.');
 assert.equal(h.calls.slice(calls).some(c=>c.url.startsWith('/api/resultados?')),false);
 get('resultadoFilas').replaceChildren=original;
 console.log('OK: síntoma reproducible inyectando fallo síncrono en resetResult, sin atribuirlo a masa267.');
})().catch(e=>{console.error(e);process.exitCode=1;});
