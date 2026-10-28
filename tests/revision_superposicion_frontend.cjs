// app.js y superposicion.js reales en un mismo contexto, con HTTP/DOM/SVG simulados.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const G='1'.repeat(32),G2='2'.repeat(32),S='3'.repeat(32),FP='a'.repeat(64);
const flush=()=>new Promise(r=>setImmediate(r));async function settle(){for(let i=0;i<8;i++)await flush();}
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
const response=v=>({ok:true,json:async()=>v,blob:async()=>new Blob(['png'])});
function schema(id=G,huella='h'.repeat(64),cx=4){
 const n=(i,x,y)=>({id:i,x,y});const A=n('A',0,0),B=n('B',4,0),C=n('C',cx,3),D=n('D',0,3);
 const wall=(id,a,b)=>({id,nivel_inferior:'N0',nivel_superior:'N1',inicio:a,fin:b,longitud:Math.hypot(b.x-a.x,b.y-a.y),espesor:id==='M4'?null:0.15});
 return {geometria:id,caso:'A',huella_geometria:huella,sha256_geometria:'s'.repeat(64),unidad_longitud:'m',estado_revision:'borrador',procedencia:'sintetico',
  disponible_para_modelado:false,nodos:[A,B,C,D],extension:{x:[0,cx],y:[0,3]},
  niveles:[{id:'N0',nombre:'Base',cota:0,muros:[wall('M1',A,B),wall('M2',B,C),wall('M3',C,D),wall('M4',D,A)]},{id:'N1',nombre:null,cota:2.6,muros:[]}]};
}
function overlay(){
 const p=(nodo,u,v)=>({nodo,u,v,dentro_imagen:u>=0&&u<=1&&v>=0&&v<=1});
 return {id:S,caso:'A',expediente_sha256:FP,vigente:true,aprueba_ingenieria:false,aprueba_geometria:false,naturaleza:'correspondencia_declarada_no_deteccion',
  geometria:{id:G,huella:'h'.repeat(64)},fuente:{archivo:'L0001',pagina:1,preview_px:[400,240]},nivel:'N0',
  anclas:[{nodo:'A',punto:[0.6,0.9]},{nodo:'C',punto:[0.9,0.6]},{nodo:'D',punto:[0.2,0.3]}],declaracion:{revisor_declarado:'Revisora declarada',fecha:'2026-10-18',motivo:'m'},
  muros:schema().niveles[0].muros.map(m=>({...m,proyeccion:[p(m.inicio.id,...{A:[.6,.9],B:[1.3,1.2],C:[.9,.6],D:[.2,.3]}[m.inicio.id]),p(m.fin.id,...{A:[.6,.9],B:[1.3,1.2],C:[.9,.6],D:[.2,.3]}[m.fin.id])]})),
  fuera_imagen:[{muro:'M1',nodo:'B',u:1.3,v:1.2},{muro:'M2',nodo:'B',u:1.3,v:1.2}]};
}
function harness(){
 const elements={},events={},state={calls:[],schemas:{[G]:schema(),[G2]:schema(G2,'k'.repeat(64),5)},rows:[],emitted:[]};
 function element(tag){return {tag,attrs:{},value:'',textContent:'',disabled:false,checked:false,hidden:false,style:{},children:[],events:{},files:[],options:[],
  classList:{toggle(){}},parentElement:{classList:{toggle(){}}},append(...v){this.children.push(...v);},replaceChildren(...v){this.children=v;this.options=v;},
  setAttribute(k,v){this.attrs[k]=v;},removeAttribute(){},addEventListener(n,f){(this.events[n]??=[]).push(f);},checkValidity(){return true;},reportValidity(){return true;},click(){}};}
 const get=id=>elements[id]??=element('x');
 const window={addEventListener(t,f){(events[t]??=[]).push(f);},dispatchEvent(e){state.emitted.push(e);for(const f of events[e.type]||[])f(e);}};
 const context={window,document:{getElementById:get,querySelector(){return {content:'s'};},createElement:element,createElementNS:(ns,tag)=>element(tag)},
  URLSearchParams,Blob,CustomEvent:class{constructor(t,o){this.type=t;this.detail=o?.detail;}},Event:class{constructor(t){this.type=t;}},
  URL:{createObjectURL(){return 'blob:preview';},revokeObjectURL(){}},
  fetch(url,init={}){const p=new URL(url,'http://x'),body=init.body?JSON.parse(init.body):undefined;state.calls.push({url:p.pathname,body,params:Object.fromEntries(p.searchParams)});
   const custom=state.handler?.(p,body);if(custom!==undefined)return custom;
   const r={'/api/casos':{casos:[]},'/api/superposicion/historial':{versiones:state.rows,seleccion_automatica:false},
    '/api/superposicion/esquema':state.schemas[p.searchParams.get('version')],'/api/superposicion/version':overlay(),'/api/pagina':{},
    '/api/geometrias':{versiones:[G,G2]},'/api/geometria':{datos:{revision:{estado:'borrador',aprobacion:null}},huella:'h',metadatos:{},
     comprobacion:{correcta:true,validacion:{consistente:true,faltantes:[],datos_sinteticos:true,disponible_para_modelado:false}}}}[p.pathname];
   if(p.pathname==='/api/superposicion/crear'){state.rows=[{id:S,vigente:true,nivel:'N0',geometria:G}];return Promise.resolve(response(overlay()));}
   if(r===undefined)throw Error('Ruta inesperada '+p.pathname);return Promise.resolve(response(r));}};
 vm.createContext(context);for(const n of ['app','superposicion'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/'+n+'.js'),'utf8'),context,{filename:n+'.js'});
 function setCase(caso='A',fp=FP){vm.runInContext(`docs=${JSON.stringify({caso,expediente_sha256:fp,versiones:[],geometrias:[G,G2],documentos:[{id:'L0001',nombre:'plano.pdf',paginas:2,error:null}]})}`,context);window.dispatchEvent(new context.Event('d2m-case'));}
 const svg=()=>get('supLienzo').children[0];const kids=tag=>(svg()?.children||[]).filter(c=>c.tag===tag);
 async function load(id=G){get('supGeometria').value=id;get('supGeometria').onchange();await settle();}
 function fill(){for(const [i,n,u,v] of [[1,'A',0.6,0.9],[2,'C',0.9,0.6],[3,'D',0.2,0.3]]){get('supNodo'+i).value=n;get('supU'+i).value=String(u);get('supV'+i).value=String(v);}
  get('supDocumento').value='L0001';get('supDocumento').onchange();get('supPagina').value='1';get('supRevisor').value='Revisora declarada';get('supMotivo').value='Anclas declaradas';
  for(const f of get('supMotivo').events.input||[])f();}
 return {get,state,context,window,setCase,svg,kids,load,fill,init:async()=>{await settle();setCase();await settle();},posts:()=>state.calls.filter(c=>c.body)};
}
const tests=[];function test(n,f){tests.push({n,f});}

test('sin correspondencia: esquema métrico, advertencia y sin imagen de fondo',async()=>{
 const h=harness();await h.init();await h.load();
 assert.equal(h.kids('line').length,4);assert.equal(h.kids('image').length,0);assert.match(h.get('supAviso').textContent,/NO está alineado/);
 assert.equal(h.get('supRegistrar').disabled,true);assert.equal(h.posts().length,0);
 h.get('supNivel').value='N1';h.get('supNivel').onchange();assert.equal(h.kids('line').length,0);
});

test('detalle de elemento con extremos, unidad, faltante y versión',async()=>{
 const h=harness();await h.init();await h.load();h.get('supElemento').value='M4';h.get('supElemento').onchange();
 const text=h.get('supElementoDetalle').textContent;
 for(const part of ['Muro M4','D (0, 3)','A (0, 0)','longitud 3 m','faltante declarado','geometría '+G,'sin proyección'])assert.ok(text.includes(part),part);
});

test('registro confirmado envía anclas exactas y la superposición usa la página y lista fuera de imagen',async()=>{
 const h=harness();await h.init();await h.load();h.fill();assert.equal(h.get('supRegistrar').disabled,true);
 h.get('supConfirmar').checked=true;for(const f of h.get('supConfirmar').events.input)f();assert.equal(h.get('supRegistrar').disabled,false);
 await h.get('supRegistrar').onclick();await settle();const post=h.posts()[0];
 assert.equal(post.url,'/api/superposicion/crear');assert.equal(post.body.huella_geometria,'h'.repeat(64));assert.equal(post.body.confirmacion_explicita,true);
 assert.deepEqual(JSON.parse(JSON.stringify(post.body.anclas)),[{nodo:'A',punto:[0.6,0.9]},{nodo:'C',punto:[0.9,0.6]},{nodo:'D',punto:[0.2,0.3]}]);
 assert.equal(post.body.pagina,1);assert.equal(post.body.nivel,'N0');
 assert.ok(h.state.calls.some(c=>c.url==='/api/pagina'&&c.params.archivo==='L0001'));
 assert.equal(h.kids('image').length,1);assert.equal(h.svg().attrs.viewBox,'0 0 400 240');
 assert.match(h.get('supFuera').textContent,/M1\/B \(1\.3, 1\.2\)/);assert.match(h.get('supAviso').textContent,/DECLARADA/);
 assert.equal(h.get('supConfirmar').checked,false);
});

test('cambiar a geometría corregida recarga esquema y exige correspondencia nueva',async()=>{
 const h=harness();h.state.rows=[{id:S,vigente:true,nivel:'N0',geometria:G}];await h.init();
 h.get('supVersion').value=S;await h.get('supVersion').onchange();await settle();assert.equal(h.kids('image').length,1);
 h.get('geoVersion').value=G2;for(const f of h.get('geoVersion').events.change)f();await settle();
 assert.equal(h.get('supGeometria').value,G2);assert.equal(h.kids('image').length,0);assert.equal(h.get('supU1').value,'');
 assert.match(h.get('supAviso').textContent,/NO está alineado/);assert.match(h.get('supEstado').textContent,/no se hereda/);
});

test('respuesta tardía del esquema tras cambiar de caso se descarta',async()=>{
 const h=harness();await h.init();const slow=deferred();h.state.handler=p=>p.pathname==='/api/superposicion/esquema'?slow.promise:undefined;
 h.get('supGeometria').value=G;h.get('supGeometria').onchange();h.setCase('B','c'.repeat(64));slow.resolve(response(schema()));await settle();
 assert.equal(h.get('supLienzo').children.length,0);assert.equal(h.get('supNivel').disabled,true);
 const src=fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/superposicion.js'),'utf8');assert.ok(!/innerHTML|eval\(|new Function/.test(src));
});

function schemaSurface(){const g=schema();g.version_geometria='0.2.0';g.niveles=[];g.nodos=[];g.vertices_m=[['VA',0,0],['VB',4,0],['VC',4,3],['VD',0,3]].map(([id,x,y])=>({id,x,y,z:2.6,procedencia:{tipo:'sintetico'}}));g.superficies=[{id:'SF1',vertices:['VA','VB','VC','VD'],vertices_m:g.vertices_m.map(v=>[v.x,v.y,v.z]),area_m2:12,papel_geometrico:'piso sintético',procedencia:{tipo:'sintetico'},normal_unitaria:[0,0,1]}];return g;}
function surfaceOverlay(){const g=schemaSurface(),v=overlay();v.version_contrato='0.2.0';v.nivel=null;v.plano={tipo:'horizontal',cota_m:2.6};v.anclas=[{vertice:'VA',punto:[.1,.9]},{vertice:'VB',punto:[.9,.9]},{vertice:'VD',punto:[.1,.1]}];v.muros=[];v.fuera_imagen=[];v.superficies=[{...g.superficies[0],proyeccion:[['VA',.1,.9],['VB',.9,.9],['VC',.9,.1],['VD',.1,.1]].map(([vertice,u,z])=>({vertice,u,v:z,dentro_imagen:true}))}];return v;}
async function readySurface(h){h.state.schemas[G]=schemaSurface();await h.load();h.get('supCota').value='2.6';for(const f of h.get('supCota').events.input)f();h.get('supElemento').value='SF1';h.get('supElemento').onchange();h.fill();for(const [i,n,u,v]of [[1,'VA',.1,.9],[2,'VB',.9,.9],[3,'VD',.1,.1]]){h.get('supNodo'+i).value=n;h.get('supU'+i).value=String(u);h.get('supV'+i).value=String(v);}for(const f of h.get('supMotivo').events.input||[])f();}
test('superficie horizontal usa contorno y anclas XYZ sin nodo ni Story',async()=>{const h=harness();await h.init();await readySurface(h);assert.equal(h.kids('polygon').length,1);assert.equal(h.kids('line').length,0);assert.match(h.get('supElementoDetalle').textContent,/12 m²/);h.state.handler=p=>p.pathname==='/api/superposicion/crear'||p.pathname==='/api/superposicion/version'?Promise.resolve(response(surfaceOverlay())):p.pathname==='/api/superposicion/historial'?Promise.resolve(response({versiones:[{id:S,vigente:true,plano:{cota_m:2.6},geometria:G}]})):undefined;h.get('supConfirmar').checked=true;for(const f of h.get('supConfirmar').events.input)f();assert.equal(h.get('supRegistrar').disabled,false);await h.get('supRegistrar').onclick();await settle();const body=h.posts()[0].body;assert.equal(body.version_contrato,'0.2.0');assert.equal(body.nivel,undefined);assert.deepEqual(JSON.parse(JSON.stringify(body.plano)),{tipo:'horizontal',cota_m:2.6});assert.equal(body.anclas[0].vertice,'VA');assert.equal(body.anclas[0].nodo,undefined);assert.equal(h.kids('polygon').length,1);assert.equal(h.kids('image').length,1);});
test('cota distinta invalida confirmación y no aplana superficie inclinada',async()=>{const h=harness();await h.init();await readySurface(h);h.get('supConfirmar').checked=true;h.get('supCota').value='3';for(const f of h.get('supCota').events.input)f();assert.equal(h.get('supConfirmar').checked,false);assert.equal(h.kids('polygon').length,0);assert.equal(h.get('supRegistrar').disabled,true);assert.equal(h.posts().length,0);});

function schemaVertical(){const g=schemaSurface();g.vertices_m.forEach(v=>{v.z=v.y;v.y=0;});g.superficies[0].vertices_m=g.vertices_m.map(v=>[v.x,v.y,v.z]);g.superficies[0].normal_unitaria=[0,-1,0];return g;}
async function ready3d(h){h.state.schemas[G]=schemaVertical();await h.load();h.get('supTipo').value='superficies_plano3d';h.get('supTipo').onchange();for(const [id,val]of [['supOrigen3d','0,0,0'],['supEjeU3d','1,0,0'],['supEjeV3d','0,0,1']]){h.get(id).value=val;for(const f of h.get(id).events.input||[])f();}h.get('supElemento').value='SF1';h.get('supElemento').onchange();h.fill();for(const [i,n,u,v]of [[1,'VA',.1,.9],[2,'VB',.9,.9],[3,'VD',.1,.1]]){h.get('supNodo'+i).value=n;h.get('supU'+i).value=String(u);h.get('supV'+i).value=String(v);}for(const f of h.get('supMotivo').events.input||[])f();}
function overlay3d(){const v=surfaceOverlay();v.version_contrato='0.3.0';v.plano={tipo:'base_ortonormal_3d',origen_m:[0,0,0],eje_u:[1,0,0],eje_v:[0,0,1]};v.huella_plano='p'.repeat(64);v.base_vista={normal_u_cruz_v:[0,-1,0]};v.superficies[0]={...schemaVertical().superficies[0],vertices_plano_m:[[0,0],[4,0],[4,3],[0,3]],proyeccion:v.superficies[0].proyeccion};return v;}
test('plano3D vertical conserva base declarada en solicitud y dibuja contorno',async()=>{const h=harness();await h.init();await ready3d(h);assert.equal(h.kids('polygon').length,1);h.state.handler=p=>p.pathname==='/api/superposicion/crear'||p.pathname==='/api/superposicion/version'?Promise.resolve(response(overlay3d())):p.pathname==='/api/superposicion/historial'?Promise.resolve(response({versiones:[{id:S,vigente:true,plano:overlay3d().plano,geometria:G}]})):undefined;h.get('supConfirmar').checked=true;for(const f of h.get('supConfirmar').events.input)f();assert.equal(h.get('supRegistrar').disabled,false);await h.get('supRegistrar').onclick();await settle();const b=h.posts()[0].body;assert.equal(b.version_contrato,'0.3.0');assert.deepEqual(JSON.parse(JSON.stringify(b.plano)),overlay3d().plano);assert.deepEqual(JSON.parse(JSON.stringify(b.superficies)),['SF1']);assert.equal(b.nivel,undefined);assert.equal(h.kids('image').length,1);assert.equal(h.kids('polygon').length,1);});
test('plano3D rechaza base inválida o no coplanar y retira confirmación',async()=>{for(const [id,value]of [['supEjeU3d','2,0,0'],['supEjeV3d','1,0,0'],['supOrigen3d','0,1,0'],['supOrigen3d','0,,0']]){const h=harness();await h.init();await ready3d(h);h.get('supConfirmar').checked=true;h.get(id).value=value;for(const f of h.get(id).events.input||[])f();assert.equal(h.get('supConfirmar').checked,false);assert.equal(h.get('supRegistrar').disabled,true);assert.equal(h.kids('polygon').length,0);assert.equal(h.posts().length,0);}});

(async()=>{for(const t of tests)await t.f();console.log('Superposición: esquema sin alineación, detalle, registro con anclas, geometría corregida y obsolescencia: OK ('+tests.length+')');})()
 .catch(e=>{console.error(e);process.exit(1);});
