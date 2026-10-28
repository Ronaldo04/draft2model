const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const web=path.join(__dirname,'../draft2model/revision_web');
const scripts=['preparacion.js','preprocesamiento.js'].map(name=>fs.readFileSync(path.join(web,name),'utf8'));
const FP='f'.repeat(64),V='1'.repeat(64),W='2'.repeat(64),C='c'.repeat(32),D='d'.repeat(32),R='a'.repeat(32);
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
const response=value=>({json:async()=>value,blob:async()=>Buffer.from('PNG SINTETICO')});
function version(id=V){return {id,caso:'A',archivo_id:'L0001',expediente_sha256:FP,config:{rotacion_grados:90,contraste:1.2,perspectiva:null},
 registro:{creado_utc:'2026-10-18T12:00:00+00:00'},transformacion:{dimensiones_salida_px:[60,80]}};}
function harness(){
 const elements={},events={},calls=[],state={errors:[],emitted:[],versions:[version(),version(W)],created:false,urls:[],revoked:[]};
 const get=id=>elements[id]??={value:'',checked:false,disabled:false,hidden:false,textContent:'',options:[],events:{},
  get selectedOptions(){return this.options.filter(o=>o.selected);},
  addEventListener(name,fn){(this.events[name]??=[]).push(fn);},removeAttribute(name){delete this[name];},reportValidity(){return true;}};
 const context={busy:false,docs:{caso:'A',expediente_sha256:FP,documentos:[{id:'L0001',nombre:'foto.png'},{id:'L0002',nombre:'plano.pdf'}]},$:get,URLSearchParams,
  URL:{createObjectURL(){const url='blob:sintetico-'+state.urls.length;state.urls.push(url);return url;},revokeObjectURL(url){state.revoked.push(url);}},
  CustomEvent:class{constructor(type,options){this.type=type;this.detail=options.detail;}},
  window:{addEventListener(name,fn){(events[name]??=[]).push(fn);},dispatchEvent(event){state.emitted.push(event);for(const fn of events[event.type]||[])fn(event);}},
  options(select,rows){select.options=rows.map(([value,textContent])=>({value,textContent,selected:false,disabled:false}));select.value=rows[0]?.[0]??'';},
  message(text){state.errors.push(text);},changeDocument:async()=>{},openPage:async()=>{},
  async action(fn){if(context.busy)return;context.busy=true;context.window.visualControls?.();context.window.preprocessControls?.();try{return await fn();}catch(error){state.errors.push(error.message);}finally{context.busy=false;context.window.visualControls?.();context.window.preprocessControls?.();}},
  api(url,body){calls.push({url,body});const parsed=new URL(url,'http://127.0.0.1');const custom=state.handler?.(parsed,body);if(custom!==undefined)return custom;
   const name=parsed.pathname;
   if(name==='/api/visual/historial')return Promise.resolve(response({revisiones:[{id:R,vigente:true,datos:{resumen:{paginas_renderizadas:1}}}],
    recortes:[C,...(state.created?[D]:[])].map(id=>({id,vigente:true,datos:{archivo_id:'L0001',pagina:1,etiqueta:'Prueba'}})),paquetes:[]}));
   if(name==='/api/visual/original-raster')return Promise.resolve(response({caso:'A',archivo_id:'L0001',expediente_sha256:FP,exif_original:{orientacion_exif:6,dimensiones_original_px:[80,60]}}));
   if(name==='/api/visual/preprocesamientos')return Promise.resolve(response({caso:'A',archivo_id:'L0001',expediente_sha256:FP,versiones:state.versions}));
   if(name==='/api/visual/preprocesamiento')return Promise.resolve(response(version(parsed.searchParams.get('version'))));
   if(name==='/api/visual/preprocesado-imagen')return Promise.resolve(response({}));
   if(name==='/api/visual/preprocesar')return Promise.resolve(response(version()));
   if(name==='/api/visual/recortar'){state.created=true;return Promise.resolve(response({id:D,caso:'A',archivo_id:'L0001',expediente_sha256:FP,preprocesamiento_id:body.preprocesamiento}));}
   throw Error('Ruta inesperada '+name);
  }};
 for(const code of scripts)vm.runInNewContext(code,context);
 function emit(type,detail){context.window.dispatchEvent({type,detail});}
 async function load(){emit('d2m-case');await flush();get('fotoArchivo').value='L0001';await get('fotoArchivo').onchange();await flush();}
 async function open(id=V){get('fotoVersion').value=id;await get('fotoVersion').onchange();}
 function changeCase(){context.docs={caso:'B',expediente_sha256:'9'.repeat(64),documentos:[]};emit('d2m-case');}
 function fill(){get('fotoRotacion').value='90';get('fotoContraste').value='1.2';get('fotoRevisor').value='Revisor SINTÉTICO';get('fotoMotivo').value='Preparación explícita';
  for(const [id,value] of [['fotoBX0','.1'],['fotoBY0','.2'],['fotoBX1','.8'],['fotoBY1','.9'],['fotoEtiqueta','Región sintética']])get(id).value=value;}
 return {state,get,calls,events,context,emit,load,open,changeCase,fill};
}
const tests=[];const test=(name,fn)=>tests.push({name,fn});
test('HTML monta cada ID una vez y carga módulo defer después de preparación',async()=>{
 const html=fs.readFileSync(path.join(web,'index.html'),'utf8');
 const ids=['fotoPanel','fotoArchivo','fotoConsultar','fotoOriginalInfo','fotoTransformarForm','fotoRotacion','fotoContraste','fotoPerspectiva',
  'fotoEsquinas','fotoAncho','fotoAlto','fotoRevisor','fotoMotivo','fotoRegistrar','fotoVersion','fotoCargar','fotoPreview','fotoDetalle',
  'fotoRecorteForm','fotoBX0','fotoBY0','fotoBX1','fotoBY1','fotoEtiqueta','fotoRecortar','fotoEstado',
  ...[0,1,2,3].flatMap(i=>['fotoX'+i,'fotoY'+i])];
 for(const id of ids)assert.equal(html.split('id="'+id+'"').length-1,1,id);
 assert.match(html,/<script src="\/preprocesamiento\.js" defer><\/script>/);
 assert.ok(html.indexOf('src="/preprocesamiento.js"')>html.indexOf('src="/preparacion.js"'));
 assert.match(fs.readFileSync(path.join(web,'app.js'),'utf8'),/window\.preprocessControls\?\.\(\)/);
});
test('consulta solo originales raster sin publicación automática ni rutas exteriores',async()=>{
 const h=harness();await h.load();assert.equal(h.get('fotoArchivo').options.some(o=>o.value==='L0002'),false);
 assert.match(h.get('fotoOriginalInfo').textContent,/orientacion_exif/);assert.equal(h.calls.some(c=>c.body),false);
 assert.equal(h.get('fotoRecortar').disabled,true);assert.equal(h.get('fotoVersion').value,'');
 assert.ok(h.calls.every(c=>c.url.startsWith('/api/visual/')));
});
test('configuración explícita conserva rotación sin auto EXIF y genera preview verificado',async()=>{
 const h=harness();await h.load();h.fill();h.get('fotoPerspectiva').checked=true;
 for(const [i,[x,y]] of [[0,0],[80,0],[80,60],[0,60]].entries()){h.get('fotoX'+i).value=String(x);h.get('fotoY'+i).value=String(y);}
 h.get('fotoAncho').value='60';h.get('fotoAlto').value='40';
 await h.get('fotoTransformarForm').onsubmit({preventDefault(){}});
 const posts=h.calls.filter(c=>c.body);assert.equal(posts.length,1);assert.equal(posts[0].url,'/api/visual/preprocesar');
 assert.deepEqual(JSON.parse(JSON.stringify(posts[0].body)),{caso:'A',expediente_sha256:FP,archivo:'L0001',config:{rotacion_grados:90,contraste:1.2,
  perspectiva:{esquinas_px:[[0,0],[80,0],[80,60],[0,60]],dimensiones_salida_px:[60,40]}},revisor_declarado:'Revisor SINTÉTICO',motivo:'Preparación explícita'});
 assert.equal(h.get('fotoVersion').value,V);assert.equal(h.get('fotoPreview').hidden,false);assert.equal(h.get('fotoRecortar').disabled,false);
});
test('recorte derivado agrega selección al paquete sin perder revisión ni recortes anteriores',async()=>{
 const h=harness();await h.load();h.fill();await h.open();h.get('visualRevision').value=R;
 h.get('visualRecortes').options.find(o=>o.value===C).selected=true;
 await h.get('fotoRecorteForm').onsubmit({preventDefault(){}});await flush();await flush();
 const post=h.calls.find(c=>c.url==='/api/visual/recortar');assert.equal(post.body.preprocesamiento,V);
 assert.deepEqual(Array.from(post.body.bbox),[.1,.2,.8,.9]);assert.equal(post.body.pagina,1);
 assert.equal(h.get('visualRevision').value,R);
 assert.deepEqual(h.get('visualRecortes').selectedOptions.map(o=>o.value),[C,D]);
 assert.equal(h.calls.some(c=>c.url==='/api/visual/preparar'),false);
 const count=h.calls.length;h.emit('d2m-visual-crop',{caso:'B',expediente_sha256:FP,recorte:{id:D}});await flush();assert.equal(h.calls.length,count);
 h.emit('d2m-visual-crop',{caso:'A',expediente_sha256:FP,recorte:{id:'../x',caso:'A',expediente_sha256:FP}});await flush();assert.equal(h.calls.length,count);
});
test('campos vacíos y bbox inválido no se convierten silenciosamente a cero',async()=>{
 const h=harness();await h.load();h.fill();h.get('fotoContraste').value='';await h.get('fotoTransformarForm').onsubmit({preventDefault(){}});
 assert.equal(h.calls.some(c=>c.body),false);assert.ok(h.state.errors.length);
 await h.open();h.get('fotoBX1').value='.05';await h.get('fotoRecorteForm').onsubmit({preventDefault(){}});
 assert.equal(h.calls.some(c=>c.body),false);
});
for(const rejected of [false,true])test('descarta consulta original obsoleta '+(rejected?'con error':'correcta'),async()=>{
 const h=harness();const pending=deferred();h.state.handler=url=>url.pathname==='/api/visual/original-raster'?pending.promise:undefined;
 h.emit('d2m-case');h.get('fotoArchivo').value='L0001';const old=h.get('fotoArchivo').onchange();h.changeCase();await flush();
 const before=h.get('fotoEstado').textContent,errors=h.state.errors.length;
 rejected?pending.reject(Error('OBSOLETO')):pending.resolve(response({caso:'A',archivo_id:'L0001',expediente_sha256:FP}));await old;await flush();
 assert.equal(h.get('fotoEstado').textContent,before);assert.equal(h.state.errors.length,errors);assert.equal(h.get('fotoOriginalInfo').textContent,'');
});
for(const rejected of [false,true])test('descarta versión antigua al elegir otra '+(rejected?'con error':'correcta'),async()=>{
 const h=harness();await h.load();const pending=deferred();h.state.handler=url=>url.pathname==='/api/visual/preprocesamiento'&&url.searchParams.get('version')===V?pending.promise:undefined;
 const old=h.open(V);await h.open(W);const before=h.get('fotoDetalle').textContent,errors=h.state.errors.length;
 rejected?pending.reject(Error('OBSOLETO')):pending.resolve(response(version(V)));await old;await flush();
 assert.equal(h.get('fotoDetalle').textContent,before);assert.equal(h.state.errors.length,errors);assert.equal(h.get('fotoVersion').value,W);
});
test('imagen tardía de versión anterior no reemplaza preview actual y se revocan blobs al salir',async()=>{
 const h=harness();await h.load();const pending=deferred();h.state.handler=url=>url.pathname==='/api/visual/preprocesado-imagen'&&url.searchParams.get('version')===V?pending.promise:undefined;
 const old=h.open(V);await flush();await h.open(W);const preview=h.get('fotoPreview').src;
 pending.resolve(response({}));await old;assert.equal(h.get('fotoPreview').src,preview);assert.equal(h.state.urls.length,1);
 h.changeCase();await flush();assert.ok(h.state.revoked.includes(preview));assert.equal(h.get('fotoPreview').hidden,true);
});
test('respuesta POST de caso anterior no abre ni publica selección en el nuevo',async()=>{
 const h=harness();await h.load();h.fill();const pending=deferred();h.state.handler=url=>url.pathname==='/api/visual/preprocesar'?pending.promise:undefined;
 const old=h.get('fotoTransformarForm').onsubmit({preventDefault(){}});h.changeCase();await flush();const before=h.get('fotoEstado').textContent;
 pending.resolve(response(version()));await old;await flush();assert.equal(h.get('fotoEstado').textContent,before);assert.equal(h.get('fotoVersion').value,'');assert.equal(h.get('fotoPreview').hidden,true);
});
(async()=>{let failures=0;for(const {name,fn} of tests){try{await fn();console.log('OK '+name);}catch(error){failures++;console.error('FAIL '+name+'\n'+error.stack);}}
 console.log(`${tests.length-failures}/${tests.length} comprobaciones de preprocesamiento correctas`);if(failures)process.exitCode=1;
})().catch(error=>{console.error(error);process.exitCode=1;});
