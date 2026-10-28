// Estados de aprobación y aislamiento entre expedientes del editor de configuración.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const ids=new Map(),events={};
function element(id){if(!ids.has(id))ids.set(id,{value:'',textContent:'',checked:false,disabled:false,handlers:{},addEventListener(n,f){this.handlers[n]=f},checkValidity(){return true}});return ids.get(id)}
let record={id:'version-prueba',datos:{revision:{estado:'borrador',aprobacion:null},datos_sinteticos:true},huella:'a'.repeat(64),
 comprobacion:{consistente:true,geometria_comprobada:true,faltantes:[],apto_para_adaptador:false,comprobacion_geometria:{validacion:{disponible_para_modelado:true}}}};
const window={addEventListener(n,f){events[n]=f},dispatchEvent(){}};
const ctx=vm.createContext({window,docs:null,busy:false,$:element,JSON,Date,Error,Event,URLSearchParams,CustomEvent:class{constructor(type,options){this.type=type;this.detail=options.detail;}},
 options(select,entries){select.value=entries[0]?.[0]||''},message(){},action:async f=>f(),
 api:async path=>({json:async()=>path.startsWith('/api/configuraciones?')?{versiones:['version-prueba']}:JSON.parse(JSON.stringify(record))})});
vm.runInContext(fs.readFileSync('draft2model/revision_web/configuracion.js','utf8'),ctx);
(async()=>{
 assert.equal(element('configAprobar').disabled,true);
 ctx.docs={caso:'demo',expediente_sha256:'b'.repeat(64)};
 element('configVersion').value='version-prueba';await element('configVersion').onchange();
 assert.equal(element('configAprobar').disabled,true);
 for(const id of ['configRevisor','configFecha','configMotivo','configAlcance'])element(id).value='Prueba';
 window.configControls();assert.equal(element('configAprobar').disabled,true);
 element('configConfirmar').checked=true;window.configControls();assert.equal(element('configAprobar').disabled,false);
 element('configJson').value+=' ';element('configJson').handlers.input();assert.equal(element('configConfirmar').checked,false);assert.equal(element('configAprobar').disabled,true);
 await element('configVersion').onchange();record.comprobacion.faltantes=[{campo:'E'}];await element('configVersion').onchange();element('configConfirmar').checked=true;window.configControls();assert.equal(element('configAprobar').disabled,true);
 record.comprobacion.faltantes=[];record.comprobacion.comprobacion_geometria.validacion.disponible_para_modelado=false;await element('configVersion').onchange();element('configConfirmar').checked=true;window.configControls();assert.equal(element('configAprobar').disabled,true);
 // Las revisiones declaradas 0.2/0.3 permiten un plan de desarrollo; no habilitan ETABS.
 for(const version of ['0.2.0','0.3.0']){
 record.datos.version_contrato=version;record.comprobacion.geometria_aprobada_por_huella=true;
 await element('configVersion').onchange();assert.equal(element('configAprobar').disabled,true);
 element('configConfirmar').checked=true;window.configControls();assert.equal(element('configAprobar').disabled,false);
 assert.equal(record.comprobacion.comprobacion_geometria.validacion.disponible_para_modelado,false);
 record.comprobacion.geometria_aprobada_por_huella=false;
 await element('configVersion').onchange();element('configConfirmar').checked=true;window.configControls();assert.equal(element('configAprobar').disabled,true);
 }
 record.comprobacion.geometria_aprobada_por_huella=true;record.datos.version_contrato='0.1.0';
 await element('configVersion').onchange();element('configConfirmar').checked=true;window.configControls();assert.equal(element('configAprobar').disabled,true);
 record.comprobacion.comprobacion_geometria.validacion.disponible_para_modelado=true;record.datos.revision.estado='aprobado';await element('configVersion').onchange();element('configConfirmar').checked=true;window.configControls();assert.equal(element('configAprobar').disabled,true);
 ctx.docs=null;events['d2m-case']();assert.equal(element('configJson').value,'');assert.equal(element('configAprobar').disabled,true);
 console.log('Configuración web: estados de aprobación 0.1/0.2/0.3 y aislamiento correctos.');
})().catch(error=>{console.error(error);process.exitCode=1});
