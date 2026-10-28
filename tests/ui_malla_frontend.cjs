// Cliente de preparación de malla 0.4: legado 0.1–0.3, sin selección, respuesta obsoleta, faltantes, exportación y texto sin HTML.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const ids=new Map(),events={};
function element(id){if(!ids.has(id))ids.set(id,{value:'',textContent:'',checked:false,disabled:false,handlers:{},addEventListener(n,f){this.handlers[n]=f},checkValidity(){return true}});return ids.get(id)}
const H='a'.repeat(64),E='e'.repeat(64);
const fuentes=[{id:'F1',descripcion:'Fuente <b>sintética</b>',referencia:'r',sha256:'0'.repeat(64)}];
function config(id,version,extra={}){return {id,huella:id==='v04b'?'c'.repeat(64):H,sha256_configuracion:'d'.repeat(64),expediente_sha256:E,
 datos:{version_contrato:version,revision:{estado:'borrador',aprobacion:null},datos_sinteticos:true,fuentes,malla:{estrategia:'particion_franjas_triangulada_v1',fuente:'F1'},
  nodos_derivados:[{nodo:'MN_S1_1',xyz_m:[0,1,2.6],restricciones:[false,false,false,false,false,false],diafragma:'DIA1',motivo_sin_diafragma:null,fuente:'F1'}],
  subdivision_frames:[],...extra},
 comprobacion:{consistente:true,geometria_comprobada:true,faltantes:[],apto_para_adaptador:false,geometria_aprobada_por_huella:true,comprobacion_geometria:{validacion:{disponible_para_modelado:false}}},metadatos:{},cadena:[id]};}
const prep={huella_preparacion:'f'.repeat(64),hosts:{S1:{},S2:{}},triangulos:[{},{},{}],
 nodos:[{csi:'MN_S1_1',xyz_m:[0,1,2.6]},{csi:'MC_1',xyz_m:[0,0.5,1.2]},{csi:'V1',xyz_m:[0,0,2.6]}],nodos_derivados:['MC_1','MN_S1_1'],
 plantilla_nodos_derivados:[{nodo:'MC_1',xyz_m:[0,0.5,1.2],restricciones:null,diafragma:null,motivo_sin_diafragma:null,fuente:null},
  {nodo:'MN_S1_1',xyz_m:[0,1,2.6],restricciones:null,diafragma:null,motivo_sin_diafragma:null,fuente:null}],
 frames_subdivision_requerida:[{frame:'VIGA1',nodos:['V1','MN_S1_1','V4'],subframes:['VIGA1_S1','VIGA1_S2']}],
 cortes_nivel:{niveles_z_m:[1.2],declaraciones:[{z_m:1.2,fuente:'F1',motivo:'Nivel libre <script>x</script>'}],nodos_corte:['MC_1'],no_crea_pisos:true,conserva_ambos_lados:true},
 conexiones:[{id:'C1',nodos_compartidos:['V1','MN_S1_1']}]};
const faltantes=[{ruta:'$.nodos_derivados.MC_1',motivo:'política de apoyo y diafragma del nodo derivado sin declarar',fuente:null},
 {ruta:'$.subdivision_frames.VIGA1',motivo:'frame atraviesa nodos de malla',fuente:null}];
const records={v01:config('v01','0.1.0'),v03:config('v03','0.3.0'),v04:config('v04','0.4.0'),v04b:config('v04b','0.4.0')};
let pendiente=null,llamadasMalla=[];
const window={addEventListener(n,f){events[n]=f},dispatchEvent(){}};
const ctx=vm.createContext({window,docs:null,busy:false,$:element,JSON,Date,Error,Event,URLSearchParams,Map,Set,Array,Number,String,
 CustomEvent:class{constructor(t,o){this.type=t;this.detail=o.detail}},options(select,entries){select.value=entries[0]?.[0]||''},message(){},action:async f=>f(),
 api:async path=>{
  if(path.startsWith('/api/configuraciones?'))return {json:async()=>({versiones:Object.keys(records)})};
  const q=new URLSearchParams(path.split('?')[1]);
  if(path.startsWith('/api/configuracion/malla?')){llamadasMalla.push(q.get('version'));
   const body={id:q.get('version'),huella_configuracion:records[q.get('version')].huella,preparacion:JSON.parse(JSON.stringify(prep)),faltantes:JSON.parse(JSON.stringify(faltantes)),apto_para_adaptador:false,aprueba_ingenieria:false,expediente_sha256:E};
   if(pendiente){const p=pendiente;pendiente=null;return {json:()=>p.then(()=>body)};}
   return {json:async()=>body};}
  return {json:async()=>JSON.parse(JSON.stringify(records[q.get('version')]))};}});
vm.runInContext(fs.readFileSync('draft2model/revision_web/configuracion.js','utf8'),ctx);
const abrir=async v=>{element('configVersion').value=v;await element('configVersion').onchange();};
(async()=>{
 // Sin expediente ni selección: nada consultable ni exportable.
 assert.equal(element('mallaConsultar').disabled,true);assert.equal(element('mallaExportar').disabled,true);
 assert.throws(()=>window.mallaExportacion(),/Consulta primero/);
 ctx.docs={caso:'demo',expediente_sha256:E};events['d2m-case']();
 assert.equal(element('mallaConsultar').disabled,true);
 // Legado 0.1 y 0.3: selector conserva el recorrido; la malla no se ofrece.
 for(const v of ['v01','v03']){await abrir(v);assert.equal(element('mallaConsultar').disabled,true);assert.match(element('mallaEstado').textContent,/sin malla 0\.4/);assert.match(element('configEstado').textContent,/^Contrato 0\.[13]\.0/);}
 // 0.4: consulta y faltantes visibles; aprobación existente sigue bloqueada por los faltantes del contrato.
 await abrir('v04');assert.match(element('configEstado').textContent,/^Contrato 0\.4\.0 \(malla\)/);
 assert.equal(element('mallaConsultar').disabled,false);
 await element('mallaConsultar').onclick();
 assert.deepEqual(llamadasMalla,['v04']);
 assert.match(element('mallaIdentidad').textContent,new RegExp('Caso demo · versión v04 · huella '+H));
 assert.match(element('mallaResumen').textContent,/Nodos derivados: 2 · frames a subdividir: 1 · cortes Z: 1/);
 assert.match(element('mallaResumen').textContent,/no certifica ingeniería/);
 assert.match(element('mallaFaltantes').textContent,/\$\.nodos_derivados\.MC_1/);
 assert.match(element('mallaNodos').textContent,/MC_1 \(0, 0\.5, 1\.2\) · FALTA política/);
 assert.match(element('mallaNodos').textContent,/MN_S1_1 \(0, 1, 2\.6\) · declarada .*diafragma DIA1/);
 assert.match(element('mallaSubdivisiones').textContent,/VIGA1: V1 → MN_S1_1 → V4 .*FALTA declaración/);
 // Contenido de JSON como texto literal (sin interpretar HTML).
 assert.ok(element('mallaCortes').textContent.includes('Nivel libre <script>x</script>'));
 assert.ok(element('mallaCortes').textContent.includes('Fuente <b>sintética</b>'));
 assert.match(element('mallaEstado').textContent,/2 faltante\(s\).*bloqueada/);
 // Exportación coherente con la selección y sin políticas escritas.
 assert.equal(element('mallaExportar').disabled,false);
 const doc=JSON.parse(JSON.stringify(window.mallaExportacion()));  // objetos de otro contexto vm
 assert.equal(doc.configuracion_version,'v04');assert.equal(doc.huella_configuracion,H);assert.equal(doc.caso,'demo');
 assert.equal(doc.huella_preparacion,prep.huella_preparacion);assert.equal(doc.aprueba_ingenieria,false);
 assert.deepEqual(doc.plantilla_nodos_pendientes.map(n=>n.nodo),['MC_1']);
 assert.ok(doc.plantilla_nodos_pendientes.every(n=>n.restricciones===null&&n.fuente===null&&n.diafragma===null));
 assert.deepEqual(doc.subdivisiones_pendientes,[{frame:'VIGA1',nodos:['V1','MN_S1_1','V4'],fuente:null}]);
 assert.equal(doc.faltantes.length,2);
 assert.equal(element('configJson').value,JSON.stringify(records.v04.datos,null,2));  // la exportación no toca el JSON
 // Editar el JSON avisa que la preparación es de la versión registrada.
 element('configJson').handlers.input();assert.match(element('mallaEstado').textContent,/aún no está guardado/);
 // Cambiar de selección invalida la preparación visible.
 await abrir('v04b');assert.equal(element('mallaResumen').textContent,'');assert.equal(element('mallaExportar').disabled,true);
 assert.throws(()=>window.mallaExportacion(),/Consulta primero/);
 // Respuesta obsoleta: la consulta de v04b llega después de seleccionar v04; se descarta.
 let liberar;pendiente=new Promise(r=>{liberar=r});
 const vieja=element('mallaConsultar').onclick();
 await new Promise(r=>setImmediate(r));
 await abrir('v04');liberar();await vieja;
 assert.equal(element('mallaResumen').textContent,'');assert.equal(element('mallaIdentidad').textContent,'');
 assert.throws(()=>window.mallaExportacion(),/Consulta primero/);
 // Cambio de expediente: todo vuelve a vacío.
 await element('mallaConsultar').onclick();assert.notEqual(element('mallaResumen').textContent,'');
 ctx.docs=null;events['d2m-case']();
 assert.equal(element('mallaResumen').textContent,'');assert.equal(element('mallaConsultar').disabled,true);
 // Aprobación 0.4: la geometría aprobada por huella habilita el botón solo sin faltantes (lógica existente).
 ctx.docs={caso:'demo',expediente_sha256:E};events['d2m-case']();await abrir('v04');
 for(const id of ['configRevisor','configFecha','configMotivo','configAlcance'])element(id).value='Prueba';
 element('configConfirmar').checked=true;window.configControls();assert.equal(element('configAprobar').disabled,false);
 records.v04.comprobacion.faltantes=faltantes;await abrir('v04');element('configConfirmar').checked=true;window.configControls();assert.equal(element('configAprobar').disabled,true);
 console.log('UI malla 0.4: legado, sin selección, obsoletas, faltantes, exportación y texto sin HTML correctos.');
})().catch(error=>{console.error(error);process.exitCode=1});
