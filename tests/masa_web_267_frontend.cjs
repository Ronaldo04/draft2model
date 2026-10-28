const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
// Reutiliza los DOM/HTTP simulados existentes y ejecuta los controladores reales.
function fixture(file,end){let source=fs.readFileSync(path.join(__dirname,file),'utf8').split(end)[0];source=source.replace('async api(url,body){','async api(url,body){if(state.handler){const intercepted=state.handler(url,body);if(intercepted!==undefined)return intercepted;}');const sandbox={require,__dirname,console,URL,URLSearchParams,structuredClone,setImmediate};vm.runInNewContext(source+'\nglobalThis.make=harness;',sandbox);return sandbox.make;}
const reading=fixture('revision_lecturas_frontend.cjs','const tests=[];'),reports=fixture('informe_relectura_frontend.cjs','(async()=>{');
const A='2'.repeat(32),FP='a'.repeat(64),J='5'.repeat(32),L='6'.repeat(32),S='c'.repeat(64),E='d'.repeat(64);
const mass={caso:'A',expediente_sha256:FP,analisis:A,trabajo:J,lectura_id:L,sha256_respuesta:S,sha256_edb:E,modo_ejecucion:'real',datos_sinteticos:false};
const ref={trabajo:J,lectura_id:L,sha256_respuesta:S};
const response=value=>({json:async()=>value}),settle=async()=>{for(let i=0;i<4;i++)await new Promise(setImmediate);};
function defer(){let resolve;return {promise:new Promise(r=>resolve=r),resolve:v=>resolve(v)};}
const tests=[];const test=(name,fn)=>tests.push({name,fn});

test('lecturas: configuración de modelo solicitada explícitamente junto a masa',async()=>{
 const h=reading();h.select();h.get('lecturaMasaApi').checked=true;h.get('lecturaMasaApi').events.input();
 h.get('lecturaConfigAuto').checked=true;h.get('lecturaConfigAuto').events.input();await h.get('lecturaPreparar').onclick();
 const b=h.calls.filter(c=>c.url==='/api/lectura/preparar').at(-1).body;
 assert.equal(JSON.stringify(b.resultados_api),'["AssembledJointMass","ConfiguracionAuto"]');
 assert.equal(h.calls.some(c=>c.url==='/api/lectura/ejecutar'),false);
});

test('informes: estimación requiere configuración en la misma lectura y selección explícita',async()=>{
 const h=reports();await h.init();h.emit('d2m-mass-reading',mass);
 h.get('informeUsarMasaNativa').checked=true;await h.input('informeUsarMasaNativa');
 assert.equal(h.get('informeEstimarAuto').disabled,true);
 h.emit('d2m-mass-reading',{...mass,configuracion_auto_disponible:true});
 h.get('informeUsarMasaNativa').checked=true;await h.input('informeUsarMasaNativa');
 assert.equal(h.get('informeEstimarAuto').disabled,false);
 h.get('informeEstimarAuto').checked=true;const b=await h.submit();
 assert.equal(b.masa_nativa.estimar_auto,true);assert.equal(b.masa_nativa.sha256_respuesta,S);
 h.emit('d2m-mass-reading',null);assert.equal(h.get('informeEstimarAuto').checked,false);
});
test('lecturas: opt-in conserva payload previo y tablas/casos; no ejecuta automáticamente',async()=>{
 const h=reading();h.select();await h.get('lecturaPreparar').onclick();assert.equal('resultados_api' in h.calls.find(c=>c.body).body,false);
 h.get('lecturaMasaApi').checked=true;h.get('lecturaMasaApi').events.input();await h.get('lecturaPreparar').onclick();const b=h.calls.filter(c=>c.url==='/api/lectura/preparar').at(-1).body;assert.equal(JSON.stringify(b.resultados_api),'["AssembledJointMass"]');assert.equal(b.tablas[0],'Story Drifts');assert.equal(b.casos[0],'EST');assert.equal(h.calls.some(c=>c.url==='/api/lectura/ejecutar'),false);
});
test('lecturas: evento compacto solo aceptado vigente, invalidación y respuesta atrasada',async()=>{
 const h=reading();h.select({analisis:A});const record={...mass,id:J,estado:'aceptado',vigente:true,lectura_verificada:true,expediente_sha256:'f'.repeat(64),resultados_api:['AssembledJointMass'],datos_tablas:{resultados_api:{enorme:Array(1000).fill(1)}}};await h.open(record);
 const events=()=>h.state.emitted.filter(e=>e.type==='d2m-mass-reading');assert.equal(events().at(-1).detail.trabajo,J);assert.equal('datos_tablas' in events().at(-1).detail,false);
 h.get('lecturaCasos').events.input();assert.equal(events().at(-1).detail,null);
 const pending=defer();h.state.handler=url=>url.pathname==='/api/lectura/trabajo'?pending.promise:undefined;const request=h.open(record);h.get('lecturaAnalisis').value='9'.repeat(32);h.get('lecturaAnalisis').events.input();pending.resolve(response(record));await request;assert.equal(events().at(-1).detail,null);
 h.state.handler=undefined;h.select({analisis:A});for(const change of [{estado:'preparado'},{vigente:false},{lectura_verificada:false},{resultados_api:[]}]){await h.open({...record,...change});assert.equal(events().at(-1).detail,null);}
});
test('informes: inventario requiere análisis y captura nativa requiere real del mismo análisis',async()=>{
 const h=reports();await h.init();assert.equal('contenido_masa' in await h.submit(),false);assert.equal('masa_nativa' in await h.submit(),false);
 h.get('informeAnalisis').value='';h.get('informeUsarContenidoMasa').checked=true;const before=h.state.calls.length;await h.submit();assert.equal(h.state.calls.slice(before).some(c=>c.url==='/api/informe/crear'),false);
 h.get('informeAnalisis').value=A;await h.input('informeAnalisis','change');await settle();
 for(const extra of [{modo_ejecucion:'doble',datos_sinteticos:true},{datos_sinteticos:true},{analisis:'3'.repeat(32)},{sha256_edb:null}]){h.emit('d2m-mass-reading',{...mass,...extra});assert.equal(h.get('informeUsarMasaNativa').disabled,true);}
 h.emit('d2m-mass-reading',{...mass,modo_ejecucion:'doble',datos_sinteticos:true});assert.match(h.get('informeMasaEstado').textContent,/DOBLE/);
 h.emit('d2m-mass-reading',mass);assert.equal(h.get('informeUsarMasaNativa').disabled,false);h.get('informeUsarMasaNativa').checked=true;h.get('informeUsarContenidoMasa').checked=true;
 const b=await h.submit();assert.equal(b.contenido_masa,true);assert.deepEqual(JSON.parse(JSON.stringify(b.masa_nativa)),ref);assert.match(h.state.error,/referencias exactas de masa/); // El doble HTTP anterior omite las referencias: se rechaza.
 h.emit('d2m-mass-reading',null);assert.equal(h.get('informeUsarContenidoMasa').checked,false);assert.equal(h.get('informeUsarMasaNativa').checked,false);
});
test('informes: referencias exactas conservadas al crear/abrir y respuestas atrasadas descartadas',async()=>{
 const h=reports();await h.init();const report={id:'7'.repeat(32),caso:'A',resultado:'1'.repeat(32),expediente_sha256:FP,analisis:A,estado:'borrador',revision_resultados:'pendiente',archivos:{'informe.json':S},contenido_masa_seleccionado:true,masa_nativa_seleccionada:ref,contenido_masa:{estado:'sin_depositos'},masa_nativa:{estado:'capturada'}};
 h.state.handler=(url,body)=>{if(url==='/api/informe/crear'){h.state.records[report.id]=report;return response(report);}};
 h.emit('d2m-mass-reading',mass);h.get('informeUsarContenidoMasa').checked=true;h.get('informeUsarMasaNativa').checked=true;await h.submit();assert.equal(h.get('informeSha').value,S);
 const pending=defer();h.state.handler=url=>url==='/api/informe/crear'?pending.promise:undefined;const request=h.get('informeForm').onsubmit({preventDefault(){}});h.emit('d2m-mass-reading',null);pending.resolve(response(report));await request;await settle();assert.equal(h.get('informeUsarMasaNativa').checked,false);
 // Abrir datos calculados no autoriza inferir una referencia ausente.
 h.state.handler=undefined;h.state.records[report.id]={...report,masa_nativa_seleccionada:null};h.get('informeVersion').value=report.id;await h.get('informeVersion').onchange();assert.equal(h.get('informeSha').value,'');assert.match(h.state.error,/referencias explícitas válidas de masa/);
});
(async()=>{let failed=0;for(const {name,fn} of tests){try{await fn();console.log('OK '+name);}catch(e){failed++;console.error('FAIL '+name+'\n'+e.stack);}}console.log(`${tests.length-failed}/${tests.length} masa web 267`);if(failed)process.exitCode=1;})();

