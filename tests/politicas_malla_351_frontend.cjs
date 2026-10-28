const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const elements=[],listeners={},calls=[],sent=[];let deferred=null;
class Element{
 constructor(tag){this.tagName=tag.toUpperCase();this.children=[];this.events={};this._value=undefined;this.disabled=false;this.checked=false;this.parent=null;elements.push(this);}
 append(...nodes){for(const n of nodes){this.children.push(n);n.parent=this;}}
 replaceChildren(...nodes){for(const n of this.children)n.parent=null;this.children=[];this.append(...nodes);}
 remove(){if(this.parent){this.parent.children=this.parent.children.filter(n=>n!==this);this.parent=null;}}
 setAttribute(){}
 get value(){return this._value===undefined?(this.tagName==='SELECT'?this.children[0]?.value||'':''):this._value;}
 set value(value){this._value=String(value);}
 addEventListener(name,fn){(this.events[name]??=[]).push(fn);}
 async emit(name,event){event??={target:this,preventDefault(){}};for(const fn of this.events[name]||[])await fn(event);
  if(this.parent&&['input','change'].includes(name))await this.parent.emit(name,event);}
}
const target=new Element('main');
const DOC={caso:'A',expediente_sha256:'a'.repeat(64)};
const cfg={fuentes:[{id:'F1',descripcion:'Fuente de fixture'}],puntos:[{id:'P1'},{id:'P2'}],diafragmas:[{id:'DIA1'}]};
const record=(caso='A')=>({id:'c'.repeat(32),caso,expediente_sha256:caso==='A'?'a'.repeat(64):'b'.repeat(64),sha256_configuracion:'d'.repeat(64),datos:cfg,validacion:{errores:[]}});
function preview(complete=true){return {malla_calculable:true,politicas_completas:complete,huella_propuesta:'vista-exacta',sha256_algoritmo:'algoritmo-exacto',
 propuesta:{resumen:{total_nodos_derivados:8,nodos_derivados_resueltos:complete?8:0,total_frames_subdivididos:1,frames_subdivididos_resueltos:complete?1:0},
 errores:[],conflictos:[],pendientes:complete?[]:[{motivo:'Reglas pendientes.'}]},otros_faltantes_tecnicos:[{ruta:'$.masa',motivo:'Masa pendiente.'}],validacion:{errores:[]}};}
const ctx={document:{createElement:tag=>new Element(tag)},docs:DOC,CustomEvent:class{constructor(type,options){this.type=type;this.detail=options.detail;}},
 window:{D2MEtapas:{containers:new Map([['ingenieria',target]])},addEventListener(name,fn){(listeners[name]??=[]).push(fn);},
 dispatchEvent(event){sent.push(event);for(const fn of listeners[event.type]||[])fn(event);}},
 api:async(url,body)=>{calls.push({url,body});if(deferred)return await deferred(url,body);
  if(url.endsWith('/previsualizar'))return {json:async()=>preview(Boolean(body.reglas.resto_restricciones&&body.reglas.resto_diafragma&&body.reglas.subdivision_frames))};
  if(url.endsWith('/aplicar'))return {json:async()=>({...record(body.caso),id:'e'.repeat(32),sha256_configuracion:'f'.repeat(64)})};throw Error('Ruta inesperada.');}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/politicas_malla.js'),'utf8'),ctx);
const by=id=>elements.find(e=>e.id===id),flush=()=>new Promise(resolve=>setImmediate(resolve));
const dispatch=(type,detail)=>{for(const fn of listeners[type]||[])fn({type,detail});};
async function set(id,value,checkbox=false){const n=by(id);if(checkbox)n.checked=value;else n.value=value;await n.emit('change');}
async function completeForm(){await set('pmSource','DECISION-FORMULARIO');await set('pmRestR','libre');await set('pmRestRMotive','Libertades del resto elegidas expresamente.');
 await set('pmRestD','excluir');await set('pmRestDMotive','Resto fuera de diafragmas por decisión explícita.');await set('pmSubdivide',true,true);
 await set('pmSubdivideMotive','Autorización explícita de subdivisiones.');await set('pmReviewer','Ingeniero SINTÉTICO');await set('pmDate','2026-10-25');await set('pmScope','Solo fixture sintética.');}
(async()=>{
 assert.equal(by('pmPreview').disabled,true);assert.equal(elements.some(e=>e.tagName==='TEXTAREA'),false);
 dispatch('d2m-preconfig-opened',record());assert.equal(by('pmPreview').disabled,false);
 for(const id of ['pmReviewer','pmDate','pmScope','pmRestR','pmRestD'])assert.equal(by(id).value,'');
 assert.equal(by('pmSubdivide').checked,false);assert.equal(by('pmConfirm').checked,false);
 await by('pmPreview').emit('click');assert.equal(calls[0].body.declaracion,null);assert.equal(calls[0].body.reglas.resto_restricciones,null);
 assert.equal(calls[0].body.reglas.resto_diafragma,null);assert.equal(calls[0].body.reglas.subdivision_frames,null);
 assert.equal(by('pmApply').disabled,true);assert.ok(by('pmIssues').children.some(n=>n.textContent==='Reglas pendientes.'));
 await completeForm();await by('pmPreview').emit('click');assert.equal(by('pmApply').disabled,true);assert.equal(by('pmConfirm').checked,false);
 const before=calls.length;await by('pmForm').emit('submit');assert.equal(calls.length,before,'No aplicar sin confirmación.');
 await set('pmConfirm',true,true);assert.equal(by('pmApply').disabled,false);await by('pmForm').emit('submit');
 const apply=calls.find(c=>c.url.endsWith('/aplicar'));assert.equal(apply.body.confirmacion_explicita,true);assert.equal(apply.body.huella_propuesta,'vista-exacta');assert.equal(apply.body.sha256_algoritmo,'algoritmo-exacto');
 assert.deepEqual(Array.from(apply.body.reglas.resto_restricciones.restricciones),[false,false,false,false,false,false]);
 assert.equal(apply.body.reglas.resto_restricciones.fuente,'DECISION-FORMULARIO');assert.equal(apply.body.declaracion.declarado_por,'Ingeniero SINTÉTICO');
 const created=sent.find(e=>e.type==='d2m-preconfig-created');assert.equal(created.detail.configuracion_preparacion,'e'.repeat(32));assert.equal(created.detail.sha256_configuracion,'f'.repeat(64));assert.equal(created.detail.preparacion_origen,'c'.repeat(32));
 assert.equal(by('pmApply').disabled,true);assert.equal(by('pmConfirm').checked,false);
 await by('pmPreview').emit('click');await set('pmConfirm',true,true);await set('pmScope','Cambio de alcance.');
 assert.equal(by('pmApply').disabled,true);assert.equal(by('pmConfirm').checked,false);assert.equal(by('pmConfirm').disabled,true);
 const prior=calls.length;dispatch('d2m-preconfig-edited',{...DOC,id:record().id,sin_guardar:true});assert.equal(by('pmPreview').disabled,true);
 await by('pmPreview').emit('click');assert.equal(calls.length,prior);dispatch('d2m-preconfig-opened',record());assert.equal(by('pmPreview').disabled,false);await completeForm();
 // Una vista tardía no puede reactivar otra preparación/caso.
 let release;deferred=()=>new Promise(resolve=>{release=resolve;});const pending=by('pmPreview').emit('click');await flush();
 ctx.docs={caso:'B',expediente_sha256:'b'.repeat(64)};dispatch('d2m-case');release({json:async()=>preview(true)});await pending;
 assert.equal(by('pmPreview').disabled,true);assert.equal(by('pmApply').disabled,true);assert.equal(by('pmReviewer').value,'');
 dispatch('d2m-preconfig-opened',record('A'));assert.equal(by('pmPreview').disabled,true,'Evento antiguo de otro caso ignorado.');
 dispatch('d2m-preconfig-opened',record('B'));assert.equal(by('pmPreview').disabled,false);assert.equal(by('pmRestR').value,'');
 deferred=null;await completeForm();
 // Formularios reales: un cero escrito se distingue de cota vacía; seis estados explícitos.
 await by('pmAddRestriction').emit('click');const kind=elements.find(e=>/^pmRKind/.test(e.id||'')),id=kind.id.replace('pmRKind','');
 await set(kind.id,'plano_z');const count=calls.length;await by('pmPreview').emit('click');assert.equal(calls.length,count);
 assert.match(by('pmStatus').textContent,/cota vacía/);
 await set('pmRZ'+id,'0');for(const axis of ['UX','UY','UZ','RX','RY','RZ'])await set('pmR'+axis+id,'restringido');
 await set('pmRMotive'+id,'Plano de apoyo sintético expresamente definido.');await set('pmRHosts'+id,'S1,S2');
 await by('pmAddDiaphragm').emit('click');const z=elements.find(e=>/^pmDZ/.test(e.id||'')),did=z.id.replace('pmDZ','');
 await set(z.id,'2.6');await set('pmDAction'+did,'asignar');await set('pmDId'+did,'DIA1');await by('pmPreview').emit('click');
 const request=calls.at(-1).body;assert.equal(request.reglas.reglas_restricciones[0].selector.z_m,0);
 assert.deepEqual(Array.from(request.reglas.reglas_restricciones[0].selector.hosts),['S1','S2']);assert.equal(request.reglas.reglas_diafragma[0].diafragma,'DIA1');
 assert.equal(request.reglas.reglas_diafragma[0].motivo_sin_diafragma,null);
 await set(kind.id,'borde_entre_puntos');await set('pmRStart'+id,'P1');await set('pmREnd'+id,'P2');await by('pmPreview').emit('click');
 const border=calls.at(-1).body.reglas.reglas_restricciones[0].selector;assert.equal(border.tipo,'borde_entre_puntos');assert.equal(border.inicio,'P1');assert.equal(border.fin,'P2');assert.equal('z_m' in border,false);
 // Otra rama del mismo caso: notificar hijo disponible con su origen, sin tocar formulario actual.
 await set('pmConfirm',true,true);let releaseBranch;deferred=()=>new Promise(resolve=>{releaseBranch=resolve;});const branchApply=by('pmForm').emit('submit');await flush();
 dispatch('d2m-preconfig-opened',{...record('B'),id:'8'.repeat(32)});const branchEvents=sent.length;
 releaseBranch({json:async()=>({...record('B'),id:'6'.repeat(32)})});await branchApply;
 assert.equal(sent.length,branchEvents+1);assert.equal(sent.at(-1).detail.preparacion_origen,'c'.repeat(32));assert.equal(by('pmReviewer').value,'');assert.equal(by('pmApply').disabled,true);
 deferred=null;await completeForm();await by('pmPreview').emit('click');
 // Aplicación tardía: no emitir hijo del caso que dejó de estar abierto.
 await set('pmConfirm',true,true);let releaseApply;deferred=()=>new Promise(resolve=>{releaseApply=resolve;});const oldApply=by('pmForm').emit('submit');await flush();const eventsBefore=sent.length;
 ctx.docs={caso:'C',expediente_sha256:'7'.repeat(64)};dispatch('d2m-case');releaseApply({json:async()=>({...record('B'),id:'9'.repeat(32)})});await oldApply;assert.equal(sent.length,eventsBefore);
 assert.equal(by('pmApply').disabled,true);assert.equal(calls.some(c=>/etabs|ejecutar/.test(c.url)),false);
 console.log('Políticas352 frontend: formulario sin JSON, decisiones explícitas, invalidación, confirmación, eventos y respuestas tardías: OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
