const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const elements=[],listeners={},calls=[];let loads=0;
class Element{
 constructor(tag){this.tagName=tag;this.children=[];this.events={};this._value=undefined;this.disabled=false;elements.push(this);}
 append(...ns){this.children.push(...ns);}after(){}replaceChildren(...ns){this.children=ns;}setAttribute(){}
 get options(){return this.children;}
 get value(){return this._value===undefined?(this.tagName==='select'?this.children[0]?.value||'':''):this._value;}set value(v){this._value=String(v);}
 addEventListener(n,fn){(this.events[n]??=[]).push(fn);}async emit(n){for(const fn of this.events[n]||[])await fn({preventDefault(){}});}
}
const DOC={caso:'A',expediente_sha256:'a'.repeat(64),versiones:['f'.repeat(32)]},GEO='b'.repeat(32),D1='c'.repeat(32),D2='d'.repeat(32);
const cfg={caso:'A',materiales:[],geometria_origen:{version_id:GEO},revision:{estado:'borrador',aprobacion:null}};
const ctx={document:{createElement:t=>new Element(t)},window:{D2MEtapas:{containers:new Map([['ingenieria',{querySelector(){return new Element('guide');}}]])},
 D2MEditorIngenieria:{clavesConfiguracion:['materiales'],mount(){return {load(){loads++;}};}},
 addEventListener(n,fn){(listeners[n]??=[]).push(fn);},dispatchEvent(){}},docs:DOC,geoRecord:{comprobacion:{correcta:true}},
 $(){return {value:GEO};},URLSearchParams,CustomEvent:class{},
 api:async(url,body)=>{calls.push({url,body});let value;
  if(url.includes('/preparaciones?'))value={versiones:[]};
  else if(url.endsWith('/crear'))value={...DOC,id:D1,datos:cfg,sha256_configuracion:'h1',puede_registrar:false,validacion:{errores:['Materiales pendientes.']}};
  else if(url.endsWith('/guardar'))value={...DOC,id:D2,datos:JSON.parse(body.configuracion_json),sha256_configuracion:'h2',puede_registrar:false,validacion:{errores:['Cargas pendientes.']}};
  else if(url.endsWith('/registrar'))value={registrada:false,validacion:{errores:['Cargas pendientes.']}};
  else if(url.endsWith('/conexiones/proponer'))value={cantidad:1,sha256_propuesta:'propuesta-exacta',limites:['Sin proximidad'],
   conexiones:[{id:'CX1',a:{superficie:'S1',desde:'A',hasta:'B'},b:{superficie:'S2',desde:'C',hasta:'D'}}]};
  else if(url.endsWith('/conexiones/declarar'))value={...DOC,id:'e'.repeat(32),datos:cfg,sha256_configuracion:'h3',puede_registrar:false,validacion:{errores:[]}};
  else if(url.endsWith('/lecturas'))value={extraccion:'f'.repeat(32),huella_lectura:'huella',lecturas:[{id:'R1',tipo:'propiedad',texto:"f'c=210",valor:210,unidad:'kgf/cm2',estado_lectura:'pendiente',resistencia_concreto:true}]};
  else if(url.endsWith('/material'))value={...DOC,id:'1'.repeat(32),datos:cfg,sha256_configuracion:'h4',puede_registrar:false,validacion:{errores:[]}};
  else throw Error('Ruta inesperada');return {json:async()=>value};}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/preparacion_configuracion.js'),'utf8'),ctx);
const button=text=>elements.find(e=>e.tagName==='button'&&e.textContent===text),flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 for(const fn of listeners['d2m-case'])await fn();await flush();
 await button('Preparar desde la geometría abierta').emit('click');
 const textarea=elements.find(e=>e.id==='preConfigJson');assert.deepEqual(JSON.parse(textarea.value),cfg);assert.ok(loads>0);
 const changed=JSON.parse(textarea.value);changed.materiales.push({id:'MAT-pendiente'});textarea.value=JSON.stringify(changed);await textarea.emit('input');
 assert.equal(button('Validar y registrar configuración').disabled,true);
 const form=elements.find(e=>e.tagName==='form');await form.emit('submit');
 const save=calls.find(c=>c.url.endsWith('/guardar'));assert.equal(save.body.version,D1);assert.equal(save.body.sha256_configuracion,'h1');
 await button('Validar y registrar configuración').emit('click');
 assert.ok(elements.some(e=>e.tagName==='li'&&e.textContent==='Cargas pendientes.'));
 assert.equal(calls.some(c=>c.url.includes('/etabs')||c.url.includes('/analisis/ejecutar')),false);
 assert.equal(JSON.parse(textarea.value).revision.aprobacion,null);
 await button('Calcular conexiones propuestas').emit('click');await flush();
 const check=elements.find(e=>e.id==='preConfigConexionCX1');assert.ok(check);assert.equal(Boolean(check.checked),false);
 await button('Seleccionar todas las conexiones').emit('click');assert.equal(check.checked,true);
 const confirmation=elements.find(e=>e.id==='preConfigConfirma');confirmation.checked=true;
 elements.find(e=>e.id==='preConfigDeclarante').value='Revisor SINTÉTICO';elements.find(e=>e.id==='preConfigFecha').value='2026-10-24';
 elements.find(e=>e.id==='preConfigAlcance').value='Continuidad sintética seleccionada.';
 const review=elements.filter(e=>e.tagName==='form')[1];await review.emit('submit');await flush();
 const declared=calls.find(c=>c.url.endsWith('/conexiones/declarar'));assert.deepEqual(Array.from(declared.body.conexiones_seleccionadas),['CX1']);
 assert.equal(declared.body.sha256_propuesta,'propuesta-exacta');assert.equal(declared.body.confirmacion_explicita,true);
 assert.equal(button('Guardar continuidad revisada').disabled,true);
 await button('Consultar propiedades y cargas detectadas').emit('click');await flush();
 for(const fn of listeners['d2m-parameter-readings-created'])await fn({detail:{...DOC,extraccion:DOC.versiones[0],materiales_para_revision:[{lectura:'R1',material_id:'MAT-DEL-PLANO'}]}});await flush();
 const fc=elements.find(e=>e.id==='preConfigFc');fc.value='R1';await fc.emit('change');
 assert.equal(elements.find(e=>e.id==='preConfigMatId').value,'MAT-DEL-PLANO');
 assert.equal(button('Calcular material y guardar borrador').disabled,false);
 const fill=(id,value)=>elements.find(e=>e.id===id).value=value;
 fill('preConfigMatPeso','24');fill('preConfigMatRevisor','Revisor SINTÉTICO');fill('preConfigMatFecha','2026-10-25');fill('preConfigMatAlcance','Ejemplo sintético, no piloto.');
 elements.find(e=>e.id==='preConfigMatNormal').checked=true;elements.find(e=>e.id==='preConfigMatConfirma').checked=true;
 const materialForm=elements.filter(e=>e.tagName==='form')[2];await materialForm.emit('submit');await flush();
 const materialRequest=calls.find(c=>c.url.endsWith('/material'));assert.equal(materialRequest.body.lectura,'R1');assert.equal(materialRequest.body.peso_kN_m3,24);
 assert.equal(materialRequest.body.concreto_normal_sin_ensayos,true);assert.equal(materialRequest.body.huella_lectura,'huella');
 assert.equal(materialRequest.body.material_id,'MAT-DEL-PLANO');
 assert.equal(elements.find(e=>e.id==='preConfigMatConfirma').checked,false);
 await button('Calcular conexiones propuestas').emit('click');await flush();
 await textarea.emit('input');assert.equal(button('Guardar continuidad revisada').disabled,true);
 ctx.docs={caso:'B',expediente_sha256:'b'.repeat(64)};for(const fn of listeners['d2m-case'])await fn();await flush();
 assert.equal(elements.find(e=>e.id==='preConfigDeclarante').value,'');assert.equal(button('Guardar continuidad revisada').disabled,true);
 console.log('Preparación348: datos internos sin archivo, cambios versionados, faltantes visibles y sin aprobación ni ETABS: OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
