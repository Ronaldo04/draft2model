const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const all=[],events={};
class Element{
 constructor(tag){this.tagName=tag;this.children=[];this.events={};this.attrs={};this.disabled=false;this._value=undefined;this.textContent='';all.push(this);}
 append(...nodes){this.children.push(...nodes);for(const n of nodes)if(n&&typeof n==='object')n.parent=this;}
 before(node){if(this.parent){const i=this.parent.children.indexOf(this);this.parent.children.splice(i,0,node);node.parent=this.parent;}}
 replaceChildren(...nodes){this.children=[];this.append(...nodes);}
 setAttribute(k,v){this.attrs[k]=v;}
 get value(){return this._value===undefined?(this.tagName==='select'?this.children[0]?.value||'':''):this._value;}
 set value(v){this._value=String(v);}
 get options(){return this.children;}
 addEventListener(name,fn){(this.events[name]??=[]).push(fn);}
 dispatchEvent(e){for(const fn of this.events[e.type]||[])fn(e);}
 setCustomValidity(text){this.validation=text;}
 querySelectorAll(){return [];}
}
const nodes={};for(const prefix of ['geo','config']){nodes[prefix+'Json']=new Element('textarea');new Element('form').append(nodes[prefix+'Json']);}
nodes.geoJson.value=JSON.stringify({unidad_longitud:'m',niveles:[],vertices:[{id:'P1',x:1,y:2,z:3}],revision:{estado:'borrador',aprobacion:null}});
nodes.configJson.value=JSON.stringify({masa:null,materiales:[]});
const context={document:{createElement:t=>new Element(t),querySelector(){return null;}},$:(id)=>nodes[id],
 window:{addEventListener(n,fn){(events[n]??=[]).push(fn);},dispatchEvent(e){for(const fn of events[e.type]||[])fn(e);}},
 MutationObserver:class{observe(){}},Event:class{constructor(type){this.type=type;}},docs:{caso:'A'},JSON,Number,Array,Object,Set};
vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(__dirname,'../draft2model/revision_web/editor_ingenieria.js'),'utf8'),context);
const group=all.find(n=>n.attrs['aria-label']==='Grupo de datos geométricos');
group.value='vertices';group.dispatchEvent({type:'change'});
const label=all.find(n=>n.tagName==='label'&&n.textContent==='Coordenada X'),field=all.find(n=>n.id===label.htmlFor);
field.value='2.75';field.dispatchEvent({type:'input'});
assert.equal(JSON.parse(nodes.geoJson.value).vertices[0].x,2.75);
assert.equal(JSON.parse(nodes.geoJson.value).revision.aprobacion,null);
field.value='abc';field.dispatchEvent({type:'input'});
assert.equal(JSON.parse(nodes.geoJson.value).vertices[0].x,2.75);assert.ok(field.validation);
const configGroup=all.find(n=>n.attrs['aria-label']==='Grupo de configuración estructural');
configGroup.value='masa';configGroup.dispatchEvent({type:'change'});
const complete=all.find(n=>n.tagName==='button'&&n.textContent==='Completar Fuente de masa');complete.dispatchEvent({type:'click'});
const mass=JSON.parse(nodes.configJson.value).masa;assert.equal(mass.gravedad_m_s2,null);assert.equal(mass.incluir_masa_propia,null);
assert.deepEqual(mass.factores_patrones,[]);
console.log('Editor344: formulario modifica borrador, rechaza no finitos, no aprueba y crea datos pendientes sin valores físicos inventados: OK');
