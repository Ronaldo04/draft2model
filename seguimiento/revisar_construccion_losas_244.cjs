// Contraste focal del formulario congelado243 con configuración0.5; DOM/API dobles, sin red ni ETABS.
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const code=fs.readFileSync(path.join(root,'tmp/revision_codex_243/draft2model/revision_web/construccion.js'),'utf8');
const flush=()=>new Promise(r=>setImmediate(r));
function harness(extra){
 const els={},events={},calls=[],state={};
 const get=id=>els[id]??={value:'',textContent:'',checked:false,disabled:false,reset(){},reportValidity(){return true;},addEventListener(n,f){this[n]=f;}};
 const context={docs:{caso:'piloto-doble',expediente_sha256:'a'.repeat(64)},busy:false,$:get,URLSearchParams,
  crypto:{randomUUID(){return 'c'.repeat(32);}},CustomEvent:class{},setTimeout(){},clearTimeout(){},
  window:{addEventListener(n,f){events[n]=f;},dispatchEvent(){}},options(){},
  message(s){state.error=s;},action:async f=>{try{await f();}catch(e){state.error=e.message;}},
  api:async(url,body)=>{calls.push({url,body});return {json:async()=>({trabajos:[],id:'job',estado:'preparado'})};}};
 vm.runInNewContext(code,context);
 events['d2m-config']({detail:{id:'config05',datos:{version_contrato:'0.5.0',revision:{estado:'aprobado'},
  secciones:[{id:'PISO',tipo:'shell_losa_homogenea'},{id:'FONDO',tipo:'shell_losa_homogenea'}]},comprobacion:{apto_para_adaptador:true}}});
 get('construccionPlantilla').value='plantilla-doble.edb';get('construccionShell').value='ShellThin';
 get('construccionGravedad').value='9.80665';get('construccionOpciones').value=JSON.stringify(extra);
 return {get,calls,state};
}
(async()=>{
 const result=[];
 for(const [name,extra] of [['opciones_vacias',{}],['intento_shell_losa',{tipo_shell_losa:'Membrane'}]]){
  const h=harness(extra);h.get('construccionForm').onsubmit({preventDefault(){}});await flush();await flush();
  const sent=h.calls.find(x=>x.url==='/api/construccion/preparar');
  result.push({caso:name,envio:!!sent,opciones_enviadas:sent?.body.opciones??null,error:h.state.error??null,
   permite_declarar_losa:!!sent&&Object.hasOwn(sent.body.opciones,'tipo_shell_losa')});
 }
 const out={estado:result.every(x=>x.permite_declarar_losa)?'correcto':'brecha_reproducida',casos:result,
  alcance:'Prueba del transporte cliente con DOM/API dobles; no prueba navegador ni ETABS. Configuración0.5aprobada es simulada.',api_llamadas:0};
 fs.writeFileSync(path.join(root,'seguimiento/BRECHA_UI_LOSAS_244.json'),JSON.stringify(out,null,2)+'\n');
 console.log(JSON.stringify(out));
})().catch(e=>{console.error(e);process.exitCode=1;});
