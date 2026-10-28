const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path'),crypto=require('node:crypto');
const elements=[],listeners={},calls=[];
class Element{
 constructor(tag){this.tagName=tag;this.children=[];this.events={};this._value=undefined;this.checked=false;this.disabled=false;elements.push(this);}
 append(...ns){this.children.push(...ns);}prepend(...ns){this.children.unshift(...ns);}after(){}replaceChildren(...ns){this.children=ns;}
 setAttribute(){}get value(){return this._value===undefined?(this.tagName==='select'?this.children[0]?.value||'':''):this._value;}set value(v){this._value=String(v);}
 addEventListener(n,fn){(this.events[n]??=[]).push(fn);}async emit(n){for(const fn of this.events[n]||[])await fn({preventDefault(){}});}
}
const DOC={caso:'A',expediente_sha256:'a'.repeat(64)},JOB='b'.repeat(32);
const ctx={document:{createElement:t=>new Element(t)},window:{D2MEtapas:{containers:new Map([['geometria',{querySelector(){return new Element('guide');}}]])},
 addEventListener(n,fn){(listeners[n]??=[]).push(fn);},dispatchEvent(){}},docs:DOC,URLSearchParams,crypto,
 clearTimeout(){},setTimeout(){return 1;},CustomEvent:class{},
 api:async(url,body)=>{calls.push({url,body});let value;
  if(url.endsWith('/cuota'))value={gemini:{configurada:true,restantes:3,limite:5,credencial_configurada:true},openai:{configurada:true,restantes:0,limite:5,credencial_configurada:true}};
  else if(url.includes('/historial'))value={trabajos:[]};
  else if(url.endsWith('/preparar'))value={...DOC,id:JOB,estado:'preparado',paso:'Preparación local, sin envío.'};
  else if(url.endsWith('/ejecutar'))value={id:JOB,estado:'en_ejecucion'};
  else if(url.includes('/estado'))value={...DOC,id:JOB,estado:'terminado_con_faltantes',paso:'Falta revisar la unidad.',tiene_respuesta_conservada:true,resultado:{faltantes:['Unidad sin respaldo.'],geometria_version:null,resumen_lectura:{niveles:1,puntos:4,medidas:2,alineaciones:4,elementos_validos:1,elementos_totales:1,unidad_efectiva:null},conflictos:[]}};
  else if(url.endsWith('/recuperar'))value={...DOC,id:JOB,estado:'geometria_borrador',paso:'Geometría reconstruida; falta revisión y configuración de ingeniería.',tiene_respuesta_conservada:true,resultado:{faltantes:[],geometria_version:'v1',unidad_declarada_ingenieria:body.unidad_revisada||null,resumen_lectura:{niveles:1,puntos:4,medidas:2,alineaciones:4,elementos_validos:1,elementos_totales:1,unidad_efectiva:'m'},conflictos:[]}};
  else throw Error('Ruta inesperada');return {json:async()=>value};}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/reconstruccion.js'),'utf8'),ctx);
const find=(tag,text)=>elements.find(e=>e.tagName===tag&&e.textContent===text),flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 for(const fn of listeners['d2m-case'])await fn();
 assert.equal(calls.filter(c=>c.url.endsWith('/ejecutar')).length,0);
 const initialProvider=elements.find(e=>e.id==='reconProveedor');initialProvider.value='gemini';await initialProvider.emit('change');
 const form=elements.find(e=>e.tagName==='form');await form.emit('submit');
 const run=find('button','Leer planos y generar geometría');assert.equal(run.disabled,true);
 const confirm=elements.find(e=>e.id==='reconConfirmar');confirm.checked=true;await confirm.emit('change');assert.equal(run.disabled,false);
 await run.emit('click');await flush();assert.equal(calls.filter(c=>c.url.endsWith('/ejecutar')).length,1);
 assert.ok(elements.some(e=>e.tagName==='li'&&e.textContent==='Unidad sin respaldo.'));
 const unitBox=elements.find(e=>e.id==='reconUnidadBox');assert.equal(unitBox.hidden,false);
 const unitSelect=elements.find(e=>e.id==='reconUnidadValor'),unitRev=elements.find(e=>e.id==='reconUnidadRevisor'),unitMot=elements.find(e=>e.id==='reconUnidadMotivo'),unitBtn=elements.find(e=>e.id==='reconAplicarUnidad');
 assert.equal(unitBtn.disabled,true);
 unitSelect.value='m';unitRev.value='Ing. Demo';unitMot.value='Niveles NPT en metros';await unitMot.emit('input');
 assert.equal(unitBtn.disabled,false);
 await unitBtn.emit('click');await flush();
 assert.equal(calls.filter(c=>c.url.endsWith('/recuperar')).length,1);
 assert.equal(calls.filter(c=>c.url.endsWith('/ejecutar')).length,1);
 const provider=elements.find(e=>e.id==='reconProveedor');provider.value='openai';await provider.emit('change');
 confirm.checked=true;await confirm.emit('change');assert.equal(run.disabled,true);
 assert.equal(calls.filter(c=>c.url.endsWith('/ejecutar')).length,1);
 console.log('Reconstrucción345: navegación no envía, preparación local, confirmación, recuperación local sin API, cuota agotada y faltantes visibles: OK');
})().catch(e=>{console.error(e);process.exitCode=1;});
