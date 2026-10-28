// Ruta 201 · etapa 01: resumen de malla en la relectura y huella de configuración en la preparación 0.4.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const fp='f'.repeat(64),sha='a'.repeat(64),model='b'.repeat(32);
(async()=>{
 // 1. Relectura: el estado muestra cobertura y hosts de malla cuando el resultado los trae, y nada si no.
 {const els={},events={};const $=id=>els[id]??={value:'',checked:false,disabled:false,textContent:'',events:{},addEventListener(k,fn){this.events[k]=fn;}};
  let job=null;
  const c={busy:false,docs:{caso:'A'},$,URLSearchParams,JSON,Object,crypto:{randomUUID:()=>'1'.repeat(32)},CustomEvent:class{constructor(t,o){this.detail=o.detail;}},
   window:{addEventListener(k,fn){events[k]=fn;},dispatchEvent(){}},options(){},action:async fn=>fn(),api:async()=>({json:async()=>job})};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/verificacion_modelo.js'),'utf8'),c);
  events['d2m-model']({detail:{version:model,record:{huella_modelo:sha,expediente_sha256:fp}}});
  const base={caso:'A',modelo:model,huella_modelo:sha,expediente_sha256:fp,id:'c'.repeat(32),huella_preparacion:sha,estado:'aceptado',vigente:true,lectura_comprobada:true,modo_ejecucion:'doble'};
  job={...base,resultado:{estado:'verificado',cobertura:{malla:'completa'},malla:{hosts:{S1:{triangulos_leidos:14,area_triangulos_leida_m2:11},S2:{triangulos_leidos:0,area_triangulos_leida_m2:null}}}}};
  $('vmTrabajo').value=job.id;await $('vmTrabajo').onchange();
  assert.match($('vmEstado').textContent,/malla 0\.4: cobertura completa · S1 14 triángulos, S2 área no leída/);
  assert.match($('vmEstado').textContent,/no aprueba ni autoriza análisis$/);
  job={...base,resultado:{estado:'verificado',cobertura:{}}};await $('vmTrabajo').onchange();
  assert.doesNotMatch($('vmEstado').textContent,/malla/);}
 // 2. Preparación de malla: una huella de configuración distinta de la abierta se rechaza sin mostrarse.
 {const ids=new Map(),events={};
  const element=id=>{if(!ids.has(id))ids.set(id,{value:'',textContent:'',checked:false,disabled:false,handlers:{},addEventListener(n,f){this.handlers[n]=f},checkValidity(){return true}});return ids.get(id)};
  const H='a'.repeat(64),E='e'.repeat(64);let huellaServidor=H;
  const rec={id:'v04',huella:H,sha256_configuracion:'d'.repeat(64),expediente_sha256:E,metadatos:{},cadena:['v04'],
   datos:{version_contrato:'0.4.0',revision:{estado:'borrador',aprobacion:null},fuentes:[],malla:{estrategia:'x',fuente:'F'},nodos_derivados:[],subdivision_frames:[]},
   comprobacion:{consistente:true,geometria_comprobada:true,faltantes:[],apto_para_adaptador:false,geometria_aprobada_por_huella:true}};
  const prep={huella_preparacion:'f'.repeat(64),hosts:{},triangulos:[],nodos:[],nodos_derivados:[],plantilla_nodos_derivados:[],frames_subdivision_requerida:[],cortes_nivel:null,conexiones:[]};
  let errores=[];
  const ctx=vm.createContext({window:{addEventListener(n,f){events[n]=f},dispatchEvent(){}},docs:null,busy:false,$:element,JSON,Date,Error,Event,URLSearchParams,Map,Set,Array,Number,String,Object,
   CustomEvent:class{constructor(t,o){this.detail=o.detail}},options(s,e){s.value=e[0]?.[0]||''},message(m,err){if(err)errores.push(m)},action:async f=>{try{await f()}catch(e){errores.push(e.message)}},
   api:async p=>({json:async()=>p.startsWith('/api/configuraciones?')?{versiones:['v04']}:p.startsWith('/api/configuracion/malla?')
    ?{id:'v04',preparacion:prep,faltantes:[],apto_para_adaptador:false,aprueba_ingenieria:false,expediente_sha256:E,huella_configuracion:huellaServidor}:JSON.parse(JSON.stringify(rec))})});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/configuracion.js'),'utf8'),ctx);
  ctx.docs={caso:'demo',expediente_sha256:E};events['d2m-case']();
  element('configVersion').value='v04';await element('configVersion').onchange();
  await element('mallaConsultar').onclick();assert.notEqual(element('mallaResumen').textContent,'');assert.deepEqual(errores,[]);
  huellaServidor='0'.repeat(64);await element('configVersion').onchange();await element('mallaConsultar').onclick();
  assert.equal(element('mallaResumen').textContent,'');assert.match(errores.at(-1),/no corresponde a la versión/);
  // R203-01: ausencia, null o tipo incorrecto de la huella también se rechazan.
  for(const mala of [undefined,null,42]){huellaServidor=mala;await element('configVersion').onchange();const antes=errores.length;await element('mallaConsultar').onclick();
   assert.equal(element('mallaResumen').textContent,'');assert.equal(errores.length,antes+1);}}
 console.log('Ruta201 UI: resumen de malla en relectura y huella de preparación correctos.');
})().catch(e=>{console.error(e);process.exitCode=1;});
