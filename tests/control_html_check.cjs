// Lógica de carga file:// en un DOM mínimo. No sustituye una prueba de navegador.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const nodes={};
class Element{
 constructor(){this.listeners={};this.hidden=false;this.textContent='';this.classList={toggle(){}};}
 addEventListener(k,fn){this.listeners[k]=fn;}
 cloneNode(){return new Element();}
 replaceWith(other){nodes.refresh=other;}
 remove(){delete nodes[this.id];}
}
const html=fs.readFileSync('Control de avance.html','utf8');
for(const match of html.matchAll(/id="([^"]+)"/g))nodes[match[1]]=new Element();
let interval,intervalMs,fetches=0,lastScript;
const ctx=vm.createContext({
 document:{baseURI:'file:///D:/proyecto/Control%20de%20avance.html',getElementById:id=>nodes[id]||null,
 createElement:()=>new Element(),head:{append(script){nodes[script.id]=script;lastScript=script;}}},
 location:{protocol:'file:'},window:{},URL,Date,console,
 fetch(){fetches++;throw Error('El HTML local no debe usar fetch');},
 setInterval(fn,ms){interval=fn;intervalMs=ms;}
});
vm.runInContext(fs.readFileSync('seguimiento/web/app.js','utf8'),ctx);
assert.equal(intervalMs,2000);
assert.ok(lastScript.src.startsWith('file:///D:/proyecto/tmp/control_avance/estado.js?v='));
// Sustituir solo el render: este ensayo verifica carga, actualización y controles de archivo.
vm.runInContext('draw=s=>{latest=s;};',ctx);
ctx.window.recibirControlAvance({last_scan:new Date().toISOString(),github_mode:'snapshot',value:1});
assert.equal(vm.runInContext('latest.value',ctx),1);
assert.equal(nodes.tests.disabled,true);assert.equal(nodes.connect.hidden,true);
lastScript.onload();
const previous=lastScript;
interval();assert.notEqual(previous,lastScript);
ctx.window.recibirControlAvance({last_scan:'2000-01-01T00:00:00Z',github_mode:'snapshot',value:2});
assert.equal(vm.runInContext('latest.value',ctx),2);
assert.ok(nodes.githubMessage.textContent.includes('Lectura anterior'));
lastScript.onerror();assert.equal(nodes.error.hidden,false);
assert.equal(vm.runInContext('latest.value',ctx),2);
nodes.refresh.listeners.click();assert.notEqual(lastScript,previous);
assert.equal(fetches,0);
console.log('HTML enlazado: actualización, antigüedad, recuperación y ausencia de peticiones HTTP comprobadas.');
