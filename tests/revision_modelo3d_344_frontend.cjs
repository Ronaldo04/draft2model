const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
function node(){return {className:'',textContent:'',tabIndex:0,append(){},setAttribute(){},addEventListener(){},getBoundingClientRect(){return {width:0,height:0};}};}
const container={querySelector(){return {after(){}};}};
const context={document:{createElement:node},window:{addEventListener(){},D2MEtapas:{containers:new Map([['geometria',container]])}},
 geoRecord:null,$(){return {value:''};},Map,Math,Number,String};
vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/modelo_3d.js'),'utf8'),context);
const entities=context.window.D2MModelo3D.entities;
const base={unidad_longitud:'cm',vertices:[{id:'V1',x:100,y:200,z:300},{id:'V2',x:200,y:200,z:300},{id:'V3',x:200,y:300,z:300}],
 superficies:[{id:'S1',vertices:['V1','V2','V3'],papel_geometrico:'losa'}],niveles:[],nodos:[],muros:[]};
const before=JSON.stringify(base),scene=entities(base,{puntos:[{id:'P1',vertice_geometria:'V1'},{id:'P2',vertice_geometria:'V2'}],frames:[{id:'F1',inicio:'P1',fin:'P2'}]});
assert.deepEqual(Array.from(scene.points.get('V1')),[1,2,3]);
assert.deepEqual(Array.from(scene.points.get('P1')),[1,2,3]);assert.equal(scene.faces.length,1);assert.equal(scene.lines.length,1);
assert.equal(JSON.stringify(base),before);
const withHole=entities({...base,aberturas:[{id:'H1',superficie:'S1',vertices:['V1','V2','V3']}]},null);
assert.deepEqual(Array.from(withHole.faces[0].holes[0]),['V1','V2','V3']);
assert.equal(entities(null,null).points.size,0);
assert.equal(entities({...base,unidad_longitud:'desconocida'},null).points.size,0);
const wall={unidad_longitud:'m',vertices:[],superficies:[],niveles:[{id:'N0',cota:0},{id:'N1',cota:2.6}],
 nodos:[{id:'A',x:0,y:0},{id:'B',x:4,y:0}],muros:[{id:'M1',nodo_inicio:'A',nodo_fin:'B',nivel_inferior:'N0',nivel_superior:'N1'}]};
const result=entities(wall,null);assert.equal(result.points.size,4);assert.equal(result.faces.length,1);
assert.deepEqual(Array.from(result.points.get('M1_c')),[4,0,2.6]);
console.log('Visor3D344: geometría real del contrato, unidades, frames, muros, ausencia e inmutabilidad: OK');
