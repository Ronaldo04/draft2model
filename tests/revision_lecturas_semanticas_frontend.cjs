// Encargo 07: corrección de lecturas 0.2.0 en app.js real (DOM/HTTP simulados): reclasificar una «cota 6» como
// cantidad, unidades según tipo, propuesta cargada sin guardar, reubicación de bbox y rechazo de cantidades no enteras.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const FP='a'.repeat(64);
const settle=async()=>{for(let i=0;i<4;i++)await new Promise(setImmediate);};
const response=value=>({ok:true,json:async()=>value});
const EV={archivo_id:'L0001',pagina:1,original_sha256:'b'.repeat(64),bbox_normalizada:[.1,.1,.2,.2],recorte_id:'R1',imagen_sha256:'c'.repeat(64)};
const datos=version=>({contrato:'draft2model.extraccion_preliminar',version_contrato:version,candidatos:[
 {id:'C017',tipo:'cota',valor_propuesto:6,unidad:'desconocida',texto_fuente:'6ø1/2"',metodo:{tipo:'vision'},evidencia:[EV],revision:{estado:'pendiente',historial:[]},
  ...(version==='0.2.0'?{clasificacion_propuesta:{tipo:'cantidad',valor:6,unidad:'no_aplica',motivo:'barras',origen:'asistente'}}:{})}],
 ...(version==='0.2.0'?{cobertura:[{recorte_id:'R1',estado:'parcial',observacion:'tabla sin leer'}]}:{})});
function harness(version,localizacion){const elements={},calls=[];
 function element(){return {value:'',textContent:'',disabled:false,checked:false,hidden:false,required:false,style:{},children:[],events:{},className:'',
  get options(){return this.children;},append(...v){this.children.push(...v);},replaceChildren(...v){this.children=v;if(this.children.length&&'value' in this.children[0]&&this.children[0].value!==undefined)this.value=this.children[0].value;},
  setAttribute(){},removeAttribute(){},addEventListener(k,f){this.events[k]=f;},classList:{toggle(){}},parentElement:{classList:{toggle(){}}}};}
 const get=id=>elements[id]??=element();
 const context={window:{addEventListener(){},dispatchEvent(){}},document:{getElementById:get,querySelector(){return {content:'s'};},createElement:element},
  URLSearchParams,Event:class{constructor(t){this.type=t;}},CustomEvent:class{constructor(t,o){this.type=t;this.detail=o?.detail;}},URL:{revokeObjectURL(){}},Date,
  fetch(url,init={}){const u=new URL(url,'http://x'),body=init.body?JSON.parse(init.body):undefined;calls.push({path:u.pathname,body});
   if(u.pathname==='/api/pagina')return new Promise(()=>{}); // la imagen del plano no interviene
   if(u.pathname==='/api/casos')return Promise.resolve(response({casos:[]}));
   if(u.pathname==='/api/localizar-lectura')return Promise.resolve(response(localizacion));
   if(u.pathname==='/api/corregir')return Promise.resolve(response({id:'d'.repeat(32)}));
   if(u.pathname==='/api/documentos')return Promise.resolve(response({caso:'A',expediente_sha256:FP,versiones:[],documentos:[],geometrias:[]}));
   return Promise.resolve(response({}));}};
 vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/app.js'),'utf8'),context,{filename:'app.js'});
 vm.runInContext(`docs=${JSON.stringify({caso:'A',expediente_sha256:FP,versiones:[],documentos:[{id:'L0001',paginas:1}],geometrias:[]})};
  record=${JSON.stringify({huella:'e'.repeat(64),expediente_sha256:FP,datos:datos(version),metadatos:{operacion:'migracion_semantica',creado_utc:'t'}})};`,context);
 get('version').value='f'.repeat(32);get('revisor').value='Revisor';get('motivo').value='contrastado';
 return {get,calls,context};}
(async()=>{
 {const {get,calls,context}=harness('0.2.0');await settle();
  vm.runInContext("selectCandidate('C017')",context);
  assert.equal(get('campoTipo').hidden,false);assert.match(get('literal').textContent,/6ø1\/2/);assert.equal(get('clasificacion').hidden,false);
  assert.deepEqual(get('unidad').children.map(o=>o.value),['desconocida','m','cm','mm']);
  get('usarClasificacion').onclick();assert.equal(get('tipoRevisado').value,'cantidad');assert.deepEqual(get('unidad').children.map(o=>o.value),['no_aplica']);
  assert.equal(calls.filter(c=>c.path==='/api/corregir').length,0,'cargar la propuesta no guarda');
  get('valor').value='6.5';get('correccion').events.submit({preventDefault(){}});await settle();
  assert.equal(calls.filter(c=>c.path==='/api/corregir').length,0);assert.match(get('mensaje').textContent,/entero no negativo/);
  get('valor').value='6';get('correccion').events.submit({preventDefault(){}});await settle();
  const body=calls.find(c=>c.path==='/api/corregir').body;
  assert.equal(body.tipo_revisado,'cantidad');assert.equal(body.valor_revisado,6);assert.equal(body.unidad_revisada,'no_aplica');
  assert.equal('evidencia_revisada' in body,false);
  // Reubicación: operación aparte con vista previa; no se guarda sin pulsar y no lleva estado de revisión.
  const recargar=()=>{vm.runInContext('record='+JSON.stringify({huella:'e'.repeat(64),expediente_sha256:FP,datos:datos('0.2.0'),metadatos:{operacion:'correccion',creado_utc:'t'}})+";docs="+JSON.stringify({caso:'A',expediente_sha256:FP,versiones:[],documentos:[{id:'L0001',paginas:1}],geometrias:[]})+";selectCandidate('C017')",context);get('version').value='f'.repeat(32);};recargar();
  const antes=calls.length;get('reubicarBbox').value='0.1,0.12,0.2,1.5';get('reubicarVer').onclick();
  assert.equal(get('reubicarGuardar').disabled,true);assert.match(get('mensaje').textContent,/Región/);
  get('reubicarBbox').value='0.1,0.12,0.2,0.22';get('reubicarVer').onclick();assert.equal(get('reubicarGuardar').disabled,false);
  assert.equal(calls.length,antes,'previsualizar no envía nada');
  get('reubicarMotivo').value='desplazada';get('reubicarGuardar').onclick();await settle();
  const reub=calls.find(c=>c.path==='/api/reubicar').body;
  assert.deepEqual(reub.bbox,[0.1,0.12,0.2,0.22]);assert.equal(reub.candidato,'C017');assert.equal('estado' in reub,false);
  recargar();
  // Lectura manual: literal obligatorio, región de la página abierta, tipo y unidad.
  get('documento').value='L0001';get('pagina').value='1';get('manualTipo').value='propiedad';get('manualTipo').onchange();
  get('manualUnidad').value='kgf/cm2';get('manualValor').value='175';get('manualBbox').value='0.3,0.4,0.35,0.42';get('manualVer').onclick();
  get('manualGuardar').onclick();await settle();assert.equal(calls.filter(c=>c.path==='/api/lectura-manual').length,0);assert.match(get('mensaje').textContent,/literal/);
  get('manualTexto').value="CONCRETO f'c=175 Kg/cm2";get('manualSimbolo').value="f'c";get('manualGuardar').onclick();await settle();
  const man=calls.find(c=>c.path==='/api/lectura-manual').body;
  assert.deepEqual([man.tipo,man.valor,man.unidad,man.archivo_id,man.pagina,man.simbolo],['propiedad',175,'kgf/cm2','L0001',1,"f'c"]);}
 {const {get,calls,context}=harness('0.1.0');await settle();
  vm.runInContext("selectCandidate('C017')",context);
  assert.equal(get('campoTipo').hidden,true);
  get('valor').value='6';get('unidad').value='m';get('correccion').events.submit({preventDefault(){}});await settle();
  const body=calls.find(c=>c.path==='/api/corregir').body;
  assert.equal('tipo_revisado' in body,false);assert.equal('evidencia_revisada' in body,false);assert.equal(body.valor_revisado,6);}
 {const {get,calls,context}=harness('0.2.0');await settle();
  const original=vm.runInContext('JSON.stringify(record.datos)',context);
  get('filtro').value='todas';
  vm.runInContext(`record.comprobacion={validacion:{advertencias:[
   {ruta:'$.candidatos[0].unidad',mensaje:'Unidad <sin respaldo> & revisar'},
   {ruta:'$.candidatos[0]',mensaje:'Número distinto del literal'},
   {ruta:'$.candidatos[01]',mensaje:'NO ASOCIAR'},
   {ruta:'$.candidatos[1]',mensaje:'OTRO CANDIDATO'},
   {ruta:'$.alcance',mensaje:'GLOBAL'}]}};renderReadings();`,context);
  const button=get('candidatos').children[0];
  assert.deepEqual(button.children.filter(c=>c.className==='warning').map(c=>c.textContent),[
   'Revisar evidencia: Unidad <sin respaldo> & revisar',
   'Revisar evidencia: Número distinto del literal']);
  assert.equal(vm.runInContext('JSON.stringify(record.datos)',context),original);
  assert.equal(calls.filter(c=>c.body).length,0,'mostrar alertas no guarda ni envía datos');
  vm.runInContext('delete record.comprobacion;renderReadings()',context);
  assert.equal(get('candidatos').children[0].children.filter(c=>c.className==='warning').length,0);
 }
 {const result={huella:'e'.repeat(64),version:'f'.repeat(32),candidato:'C017',modifica_datos:false,
   estado:'propuestas_sin_aplicar',fuentes:[{archivo_id:'L0001',pagina:1,estado:'ambigua',total:2,
    regiones:[{bbox_normalizada:[.1,.2,.3,.4]},{bbox_normalizada:[.4,.5,.6,.7]}]}]};
  const {get,calls,context}=harness('0.2.0',result);await settle();
  vm.runInContext("selectCandidate('C017')",context);
  const before=vm.runInContext('JSON.stringify(record.datos)',context);
  await vm.runInContext('buscarLiteral()',context);
  assert.equal(get('busquedaLiteralOpciones').children.length,2);
  assert.match(get('busquedaLiteralEstado').textContent,/ninguna se selecciona automáticamente/);
  assert.equal(vm.runInContext('JSON.stringify(record.datos)',context),before);
  assert.equal(calls.filter(c=>c.body).length,0,'buscar no corrige ni usa proveedor');
  result.estado='sin_texto_literal';result.fuentes=[];
  await vm.runInContext('buscarLiteral()',context);
  assert.equal(get('busquedaLiteralOpciones').children.length,0);
  assert.match(get('busquedaLiteralEstado').textContent,/no se infiere/);
 }
 console.log('Lecturas: reclasificación, regiones, avisos y búsqueda literal local sin guardar; registros heredados compatibles.');
})().catch(e=>{console.error(e);process.exitCode=1;});
