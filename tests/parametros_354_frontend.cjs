/* Revisión focal de producto congelado al inicio; DOM/API simulados, sin red. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),paths=['draft2model/revision_web/parametros.js','draft2model/revision_web/preparacion_configuracion.js'];
const code=Object.fromEntries(paths.map(p=>[p,fs.readFileSync(path.join(root,p),'utf8')]));
const sha=s=>crypto.createHash('sha256').update(s).digest('hex');
const P1='1'.repeat(32),P2='2'.repeat(32),CHILD='3'.repeat(32),J1='4'.repeat(32),J2='5'.repeat(32),FP='a'.repeat(64),H='b'.repeat(64);
function record(id=P1){return {id,caso:'A',expediente_sha256:FP,sha256_configuracion:H,datos:{id:'ConfigA',marcador:id,materiales:[],fuentes:[],puntos:[],diafragmas:[],geometria_origen:{version_id:'6'.repeat(32)},revision:{estado:'borrador',aprobacion:null}},validacion:{errores:[]},puede_registrar:false};}
function job(id=J1,estado='preparado',name='UNO',child=null){return {id,estado,paso:'Estado '+name,origen_preparacion:P1,origen_sha256_configuracion:H,tiene_respuesta_conservada:estado==='terminado',resultado:estado!=='terminado'?null:{configuracion_preparacion:child,sha256_configuracion:H,lectura:{datos:{materiales:[{id:'M1',nombre:name,propiedades:[]}],secciones:[],cargas:[]},advertencias:[]},faltantes:[],faltantes_adaptacion_lecturas:[]}};}
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
const flush=async()=>{await new Promise(r=>setImmediate(r));await new Promise(r=>setImmediate(r));};
function harness({integrated=false,remaining=2}={}){
 const elements=[],listeners={},calls=[],events=[],timers=new Map();let nextTimer=0,uuid=0;const overrides=[];
 class Element{
  constructor(tag){this.tagName=tag;this.children=[];this.parent=null;this.events={};this.attributes={};this._value=undefined;this.disabled=false;this.checked=false;elements.push(this);}
  append(...nodes){for(const node of nodes){this.children.push(node);node.parent=this;}}
  after(node){if(this.parent){const i=this.parent.children.indexOf(this);this.parent.children.splice(i+1,0,node);node.parent=this.parent;}}
  replaceChildren(...nodes){this.children=[];this.append(...nodes);}setAttribute(k,v){this.attributes[k]=v;}
  get options(){return this.children.filter(n=>n.tagName==='option');}
  get value(){return this._value===undefined?(this.tagName==='select'?this.children[0]?.value||'':''):this._value;}set value(v){this._value=String(v);}
  querySelector(selector){const matches=n=>selector==='p'?n.tagName==='p':selector==='.stage-guide'?n.className==='stage-guide':n.attributes?.['aria-label']===selector.match(/^\[aria-label="(.*)"\]$/)?.[1];
   const visit=n=>{for(const child of n.children){if(matches(child))return child;const nested=visit(child);if(nested)return nested;}return null;};return visit(this);}
  addEventListener(name,fn){(this.events[name]??=[]).push(fn);}async emit(name){for(const fn of this.events[name]||[])await fn({target:this,preventDefault(){}});}
 }
 const target=new Element('main'),guide=new Element('p');guide.className='stage-guide';target.append(guide);
 const ctx={document:{createElement:t=>new Element(t)},docs:{caso:'A',expediente_sha256:FP,versiones:[]},geoRecord:{comprobacion:{correcta:true}},
  URLSearchParams,crypto:{randomUUID:()=>`00000000-0000-4000-8000-${String(++uuid).padStart(12,'0')}`},
  setTimeout(fn){const id=++nextTimer;timers.set(id,fn);return id;},clearTimeout(id){timers.delete(id);},
  CustomEvent:class{constructor(type,opts){this.type=type;this.detail=opts.detail;}},
  window:{D2MEtapas:{containers:new Map([['ingenieria',target]])},D2MEditorIngenieria:{clavesConfiguracion:[],mount:()=>({load(){}})},
   addEventListener(name,fn){(listeners[name]??=[]).push(fn);},dispatchEvent(event){events.push(event);for(const fn of listeners[event.type]||[])fn(event);}},
  $(id){return elements.find(e=>e.id===id)||{value:'6'.repeat(32)};},
  api:async(url,body)=>{calls.push({url,body});for(const override of overrides){if(override.match(url,body)){const value=await override.run(url,body);return {json:async()=>value};}}
   let value;if(url.endsWith('/cuota'))value={openai:{restantes:remaining,limite:10,credencial_configurada:true},gemini:{restantes:1,limite:5,credencial_configurada:true}};
   else if(url.includes('/parametros/historial?'))value={trabajos:[J1,J2]};
   else if(url.endsWith('/parametros/preparar'))value={...job(),origen_preparacion:body.configuracion_preparacion,origen_sha256_configuracion:body.sha256_configuracion};
   else if(url.endsWith('/parametros/ejecutar'))value=job(J1,'en_ejecucion');
   else if(url.includes('/parametros/estado?'))value=job(new URLSearchParams(url.split('?')[1]).get('trabajo'),'terminado','UNO',CHILD);
   else if(url.endsWith('/parametros/aplicar'))value={...record(CHILD),configuracion_preparacion:CHILD,aplicacion:{faltantes:[]}};
   else if(url.endsWith('/parametros/recuperar'))value=job(J1,'terminado','UNO',CHILD);
   else if(url.includes('/configuracion/preparaciones?'))value={versiones:[P1,P2,CHILD]};
   else if(url.endsWith('/configuracion/preparacion/crear'))value=record();
   else if(url.includes('/configuracion/preparacion?'))value=record(new URLSearchParams(url.split('?')[1]).get('version'));
   else throw Error('Ruta inesperada en fixture: '+url);return {json:async()=>value};}};
 vm.createContext(ctx);if(integrated)vm.runInContext(code[paths[1]],ctx);vm.runInContext(code[paths[0]],ctx);
 const by=id=>elements.find(e=>e.id===id),button=text=>elements.find(e=>e.tagName==='button'&&e.textContent===text),form=()=>elements.find(e=>e.tagName==='form'&&e.attributes['aria-label']==='Preparar lectura de ingeniería');
 const dispatch=(type,detail)=>{for(const fn of listeners[type]||[])fn({type,detail});};
 const click=async n=>{assert.ok(n,'Control existente');if(!n.disabled)await n.emit('click');};
 const initialize=async()=>{dispatch('d2m-case');await flush();if(integrated){await click(button('Preparar desde la geometría abierta'));await flush();}else dispatch('d2m-preconfig-opened',record());};
 const prepare=async()=>{await form().emit('submit');await flush();};
 const consent=async()=>{by('parConfirmar').checked=true;await by('parConfirmar').emit('change');};
 const openBranch=async id=>{if(integrated){by('preConfigVersion').value=id;await click(button('Abrir preparación'));await flush();}else dispatch('d2m-preconfig-opened',record(id));};
 return {ctx,elements,calls,events,timers,overrides,by,button,dispatch,click,initialize,prepare,consent,openBranch};
}
const results=[];
async function check(name,fn){try{await fn();results.push({prueba:name,ok:true});console.log('OK '+name);}catch(error){results.push({prueba:name,ok:false,error:error.message,stack:error.stack});console.error('FALLO '+name+': '+error.message);}}
(async()=>{
 await check('Preparar es local; navegar/preparar no ejecuta proveedor',async()=>{const h=harness();await h.initialize();await h.prepare();assert.equal(h.calls.filter(c=>c.url.endsWith('/parametros/preparar')).length,1);assert.equal(h.calls.filter(c=>c.url.endsWith('/parametros/ejecutar')).length,0);assert.equal(h.button('Leer cuadros e incorporar datos').disabled,true);});
 await check('Consentimiento realiza un solo envío; error no genera retry',async()=>{const h=harness();await h.initialize();await h.prepare();await h.consent();
  h.overrides.push({match:u=>u.endsWith('/parametros/ejecutar'),run:()=>{throw Error('Error de transporte sintético.');}});await h.click(h.button('Leer cuadros e incorporar datos'));await flush();
  assert.equal(h.calls.filter(c=>c.url.endsWith('/parametros/ejecutar')).length,1);assert.equal(h.by('parConfirmar').checked,false);assert.equal(h.timers.size,0);assert.equal(h.button('Leer cuadros e incorporar datos').disabled,true);});
 await check('Cuota cero impide enviar aunque se prepare y consienta',async()=>{const h=harness({remaining:0});await h.initialize();await h.prepare();await h.consent();assert.equal(h.button('Leer cuadros e incorporar datos').disabled,true);await h.click(h.button('Leer cuadros e incorporar datos'));assert.equal(h.calls.filter(c=>c.url.endsWith('/parametros/ejecutar')).length,0);});
 await check('Evento de hijo conserva preparación origen y SHA de configuración',async()=>{const h=harness();await h.initialize();await h.prepare();await h.consent();await h.click(h.button('Leer cuadros e incorporar datos'));const e=h.events.find(e=>e.type==='d2m-preconfig-created');assert.ok(e);assert.equal(e.detail.preparacion_origen,P1);assert.equal(e.detail.configuracion_preparacion,CHILD);assert.equal(e.detail.sha256_configuracion,H,'Falta SHA del hijo en evento d2m-preconfig-created.');});
 await check('Edición sin guardar bloquea preparar/enviar y protege textarea ante hijo',async()=>{const h=harness({integrated:true});await h.initialize();await h.prepare();await h.consent();
  const textarea=h.by('preConfigJson'),changed=JSON.parse(textarea.value);changed.materiales.push({id:'DECISION-LOCAL'});textarea.value=JSON.stringify(changed);await textarea.emit('input');
  assert.equal(h.button('Preparar lectura de cuadros').disabled,true);assert.equal(h.button('Leer cuadros e incorporar datos').disabled,true);assert.equal(h.by('parConfirmar').checked,false);
  const count=h.calls.length;await h.prepare();assert.equal(h.calls.filter(c=>c.url.endsWith('/parametros/preparar')).length,1);
  h.dispatch('d2m-preconfig-created',{caso:'A',expediente_sha256:FP,configuracion_preparacion:CHILD,preparacion_origen:P1,sha256_configuracion:H});await flush();assert.equal(JSON.parse(textarea.value).materiales[0].id,'DECISION-LOCAL');});
 await check('Aplicación en vuelo sobre otra rama notifica sin reemplazarla',async()=>{const h=harness({integrated:true});await h.initialize();await h.prepare();h.by('parHistorial').value=J1;await h.click(h.button('Consultar lectura de ingeniería'));await flush();
  // Abrir el origen otra vez permite reaplicar; el resultado consultado puede haber abierto su hijo.
  await h.openBranch(P1);const wait=deferred();h.overrides.push({match:u=>u.endsWith('/parametros/aplicar'),run:()=>wait.promise});
  const pending=h.click(h.button('Actualizar preparación abierta con estos datos sin API'));await flush();await h.openBranch(P2);
  wait.resolve({configuracion_preparacion:CHILD,sha256_configuracion:H,aplicacion:{faltantes:[]}});await pending;await flush();
  assert.equal(JSON.parse(h.by('preConfigJson').value).marcador,P2);assert.equal(h.events.filter(e=>e.type==='d2m-preconfig-created').at(-1).detail.preparacion_origen,P1);
  assert.equal(h.calls.filter(c=>c.url.endsWith('/parametros/ejecutar')).length,0);});
 await check('Respuesta tardía de otro caso no publica hijo ni reactiva lectura',async()=>{const h=harness();await h.initialize();await h.prepare();await h.consent();const wait=deferred();h.overrides.push({match:u=>u.endsWith('/parametros/ejecutar'),run:()=>wait.promise});const pending=h.click(h.button('Leer cuadros e incorporar datos'));await flush();
  h.ctx.docs={caso:'B',expediente_sha256:'c'.repeat(64),versiones:[]};h.dispatch('d2m-case');wait.resolve(job(J1,'terminado','ANTIGUO',CHILD));await pending;await flush();
  assert.equal(h.events.some(e=>e.type==='d2m-preconfig-created'),false);assert.equal(h.button('Leer cuadros e incorporar datos').disabled,true);});
 await check('Sondeo antiguo del mismo caso no sustituye lectura seleccionada',async()=>{const h=harness();await h.initialize();await h.prepare();await h.consent();let first=true;const old=deferred();
  h.overrides.push({match:u=>u.includes('/parametros/estado?'),run:u=>{const id=new URLSearchParams(u.split('?')[1]).get('trabajo');if(id===J2)return job(J2,'terminado','DOS');if(first){first=false;return job(J1,'en_ejecucion','UNO');}return old.promise;}});
  await h.click(h.button('Leer cuadros e incorporar datos'));assert.equal(h.timers.size,1);const timer=h.timers.values().next().value;const pending=timer();await flush();h.by('parHistorial').value=J2;
  await h.click(h.button('Consultar lectura de ingeniería'));assert.ok(h.elements.some(e=>e.tagName==='li'&&e.textContent==='Material DOS [M1]: '));
  old.resolve(job(J1,'terminado','UNO'));await pending;await flush();
  assert.ok(h.elements.some(e=>e.tagName==='ul'&&e.children.some(n=>n.textContent==='Material DOS [M1]: ')),'Respuesta tardía de J1 sustituyó la lectura J2 actualmente seleccionada.');});
 const failures=results.filter(r=>!r.ok),receipt={fecha_utc:new Date().toISOString(),revision:354,estado:failures.length?'defectos_reproducidos':'focal_ok',
  producto_sha256:Object.fromEntries(paths.map(p=>[p,sha(code[p])])),prueba_sha256:sha(fs.readFileSync(__filename)),comando:'node tests/parametros_354_frontend.cjs',
  pruebas:results,aprobadas:results.length-failures.length,fallidas:failures.length,apis_reales:0,etabs:false,gui:false,
  limites:['DOM y API simulados; no acredita navegador/HTTP reales','Producto solo leído; snapshots congelados al inicio','No suite completa; no llamadas reales ni claves','La disponibilidad de rutas y controles backend no se valida en esta revisión']};
 fs.writeFileSync(path.join(root,'seguimiento/REVISION_PARAMETROS_UI_354.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify({aprobadas:receipt.aprobadas,fallidas:receipt.fallidas,recibo:'seguimiento/REVISION_PARAMETROS_UI_354.json'}));process.exitCode=failures.length?1:0;
})().catch(error=>{console.error(error);process.exitCode=1;});
