const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const candidate=fs.readFileSync(path.join(root,'tmp/candidato_listados_270/resultados.js'),'utf8');
const previous=fs.readFileSync(path.join(root,'tests/revision_resultados_frontend.cjs'),'utf8');
const prefix=previous.slice(0,previous.indexOf('(async()=>{await staleRequest'));
const bind=source=>source.replace(/^const code=.*$/m,'const code='+JSON.stringify(candidate)+';');
const sandbox={require,console,process:{},__dirname:path.join(root,'tests'),setImmediate,Blob,URL,URLSearchParams,module:{exports:{}}};
vm.runInNewContext(bind(prefix)+'\nmodule.exports={harness,flush,deferred};',sandbox);
const {harness,flush,deferred}=sandbox.module.exports;
function setup(){
 const h=harness(),requests={};
 h.context.api=url=>{const u=new URL(url,'http://localhost');const key=u.searchParams.get('caso')+u.pathname;return(requests[key]=deferred()).promise;};
 return {h,requests};
}
const rows=id=>({json:async()=>({versiones:[{id,vigente:true}]})});
const choose=(h,caso)=>{h.context.docs={caso,expediente_sha256:caso.repeat(64)};h.events['d2m-case']();};
(async()=>{
 let {h,requests}=setup();choose(h,'A');
 assert.match(h.get('resultadoEstado').textContent,/Consultando/);
 requests['A/api/resultados'].resolve(rows('res-A'));await flush();await flush();
 assert.equal(h.get('resultadoVersion').children[1].value,'res-A','Resultados deben aparecer aunque modelos sigan pendientes');
 assert.match(h.get('modeloEstado').textContent,/Consultando/);
 requests['A/api/modelos'].reject(Error('Fallo modelos independiente'));await flush();await flush();
 assert.equal(h.get('resultadoVersion').children[1].value,'res-A');
 assert.match(h.get('modeloEstado').textContent,/Fallo modelos/);
 console.log('Resultado disponible antes de modelos + error aislado: OK');

 ({h,requests}=setup());choose(h,'A');choose(h,'B');
 requests['B/api/resultados'].resolve(rows('res-B'));requests['B/api/modelos'].resolve(rows('mod-B'));
 await flush();await flush();
 const expected=h.get('resultadoEstado').textContent;
 requests['A/api/resultados'].reject(Error('Error obsoleto'));requests['A/api/modelos'].resolve(rows('mod-A'));
 await flush();await flush();
 assert.equal(h.get('resultadoVersion').children[1].value,'res-B');
 assert.equal(h.get('modeloVersion').children[1].value,'mod-B');
 assert.equal(h.get('resultadoEstado').textContent,expected);
 assert.notEqual(h.state.message,'Error obsoleto');
 console.log('Respuestas y errores de caso anterior no reemplazan columnas vigentes: OK');

 const regression={...sandbox,module:{exports:{}},process:{}};
 await vm.runInNewContext(bind(previous),regression);
 assert.notEqual(regression.process.exitCode,1);
 console.log('Regresiones existentes de selección/descarga sobre candidato: OK');
})().catch(e=>{console.error(e);process.exitCode=1;});
