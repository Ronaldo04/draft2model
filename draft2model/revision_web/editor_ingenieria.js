'use strict';
(()=>{
 const names={niveles:'Niveles',nodos:'Nodos en planta',muros:'Muros',vertices:'Puntos del modelo 3D',superficies:'Superficies',aberturas:'Aberturas',
  materiales:'Materiales',secciones:'Secciones',sitio:'Ubicación y sistema resistente',hipotesis:'Hipótesis de ingeniería',fuentes:'Fuentes de los datos',
  patrones:'Patrones de carga',cargas:'Cargas',masa:'Fuente de masa',apoyos:'Apoyos',diafragmas:'Diafragmas',sin_diafragma:'Puntos sin diafragma',
  espectros:'Espectros',casos:'Casos de análisis',combinaciones:'Combinaciones',analisis:'Opciones de análisis',liquidos:'Agua en depósitos',
  frames:'Columnas y vigas',puntos:'Puntos estructurales',asignaciones_frames:'Secciones de columnas y vigas',asignaciones_superficies:'Secciones de superficies',
  asignaciones_muros:'Secciones de muros',malla:'Malla de cálculo',conexiones_borde:'Conexiones entre superficies',cortes_nivel:'Cortes por nivel',
  id:'Identificador',x:'Coordenada X',y:'Coordenada Y',z:'Coordenada Z',cota:'Cota del nivel',espesor:'Espesor',
  nodo_inicio:'Nodo inicial',nodo_fin:'Nodo final',nivel_inferior:'Nivel inferior',nivel_superior:'Nivel superior',
  inicio:'Punto inicial',fin:'Punto final',tipo:'Tipo',material:'Material',objetivo:'Elemento al que se aplica',seccion:'Sección',
  fuente:'Fuente que respalda el dato',descripcion:'Descripción',ubicacion:'Ubicación',sistema_resistente:'Sistema resistente',
  E_kN_m2:'Módulo elástico (kN/m²)',peso_kN_m3:'Peso específico (kN/m³)',poisson:'Coeficiente de Poisson',
  ancho_m:'Ancho (m)',alto_m:'Alto (m)',espesor_m:'Espesor (m)',valor:'Valor',unidad:'Unidad',
  faltantes:'Datos pendientes',procedencia:'Procedencia',referencia:'Referencia',nombre:'Nombre',papel_geometrico:'Función geométrica'};
 const help={sitio:'La ubicación y el sistema resistente intervienen en la selección de parámetros de análisis. El estudio de suelos no se sustituye por una suposición silenciosa.',
  fuentes:'Vincula cada valor a su plano, documento o hipótesis explícita para poder revisar y reproducir el modelo.',
  masa:'Define qué cargas participan como masa en el análisis dinámico. Revisa el agua cuando existan depósitos.',
  diafragmas:'Expresa cómo se vincula el movimiento del entrepiso; revisa si la idealización representa sus losas y aberturas.',
  liquidos:'Indica si los depósitos aplican al proyecto y cómo se representan sus cargas y masa. La ausencia debe estar justificada.',
  conexiones_borde:'Establece continuidad entre superficies. Una unión visual no demuestra que los nodos de cálculo estén conectados.',
  hipotesis:'Registra decisiones de representación y sus límites. Estas decisiones forman parte de la revisión del ingeniero.'};
 const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
 const templates={niveles:{id:'',cota:null},nodos:{id:'',x:null,y:null},muros:{id:'',nodo_inicio:'',nodo_fin:'',nivel_inferior:'',nivel_superior:'',espesor:null},
  vertices:{id:'',x:null,y:null,z:null,procedencia:{tipo:'plano',descripcion:''}},
  superficies:{id:'',vertices:[],papel_geometrico:'',procedencia:{tipo:'plano',descripcion:''}},
  aberturas:{id:'',superficie:'',vertices:[],procedencia:{tipo:'plano',descripcion:''}},
  fuentes:{id:'',descripcion:'',referencia:'',sha256:''},hipotesis:{id:'',descripcion:'',fuente:''},
  materiales:{id:'',tipo:'isotropo_lineal',E_kN_m2:null,poisson:null,peso_kN_m3:null,fuente:''},
  secciones:{id:'',tipo:'frame_rectangular',material:'',dimensiones:{ancho_m:null,alto_m:null},fuente:''},
  frames:{id:'',inicio:'',fin:'',tipo:'columna',fuente:''},
  asignaciones_muros:{objetivo:'',seccion:'',fuente:''},asignaciones_frames:{objetivo:'',seccion:'',fuente:''},asignaciones_superficies:{objetivo:'',seccion:'',fuente:''},
  patrones:{id:'',tipo:'muerta',multiplicador_peso_propio:null,fuente:''},
  cargas:{id:'',patron:'',objetivo_tipo:'punto',objetivo:'',componentes:[null,null,null],unidad:'kN',sistema:'global',fuente:''},
  casos:{id:'',tipo:'estatico_lineal',parametros:{patrones:[]},fuente:''},combinaciones:{id:'',tipo:'lineal',casos:[],fuente:''},
  sitio:{descripcion:'',ubicacion:'',sistema_resistente:'',parametros:[],fuente:''},
  masa:{metodo:'patrones',gravedad_m_s2:null,incluir_masa_propia:null,factores_patrones:[],masas_puntos:[],fuente:''},
  analisis:{casos_ejecutar:[],combinaciones_resultados:[],fuente:''},
  factores_patrones:{patron:'',factor:null},masas_puntos:{punto:'',masa_kN_s2_m:null},
  parametros:{id:'',valor:null,unidad:'',fuente:''},apoyos:{punto:'',restricciones:[null,null,null,null,null,null],fuente:''}};
 let nextId=0;
 function mount(prefix,keys){
  const textarea=$(prefix+'Json');if(!textarea)return;
  const advanced=el('details'),summary=el('summary','Representación técnica avanzada (JSON)');advanced.append(summary);
  textarea.before(advanced);const label=document.querySelector('label[for="'+textarea.id+'"]');if(label)advanced.append(label);advanced.append(textarea);
  const box=el('div');box.className='editor-ingenieria';advanced.before(box);
  box.append(el('h3','Editar datos de ingeniería'),el('p','Los cambios se preparan aquí. Usa «Guardar nueva versión» y completa la revisión para conservarlos; no se aprueban automáticamente.'));
  const chooser=el('select');chooser.setAttribute('aria-label',prefix==='geo'?'Grupo de datos geométricos':'Grupo de configuración estructural');
  const status=el('p'),fields=el('div');fields.className='editor-fields';box.append(chooser,status,fields);
  let data=null;
  function sync(){textarea.value=JSON.stringify(data,null,2);textarea.dispatchEvent(new Event('input',{bubbles:true}));status.textContent='Cambios preparados sin guardar. La versión registrada se conserva.';window.dispatchEvent(new Event('d2m-geometry-edit'));}
  function draw(value,parent,key,path,depth){
   if(depth>9){fields.append(el('p','Esta estructura anidada requiere la vista técnica avanzada.'));return;}
   if(value===null&&templates[key]&&!Array.isArray(templates[key])){
    const create=el('button','Completar '+(names[key]||key));create.type='button';create.disabled=textarea.disabled;
    create.addEventListener('click',()=>{parent[key]=JSON.parse(JSON.stringify(templates[key]));sync();render();});parentTarget.append(create);return;
   }
   if(Array.isArray(value)){
    const group=el('fieldset'),legend=el('legend',names[key]||key);group.append(legend);const picker=el('select');picker.setAttribute('aria-label',(names[key]||key)+' · registro');
    value.forEach((v,i)=>{const option=el('option',String(i+1)+' · '+(v?.id||v?.objetivo||v?.frame||v?.nombre||'Registro'));option.value=i;picker.append(option);});
    const area=el('div');area.className='editor-fields';group.append(picker,area);parentTarget.append(group);
    const show=()=>{area.replaceChildren();const saved=parentTarget;parentTarget=area;if(value.length)draw(value[Number(picker.value)||0],value,Number(picker.value)||0,path+'.'+picker.value,depth+1);else area.append(el('p','No hay registros en esta colección.'));parentTarget=saved;};
    picker.addEventListener('change',show);show();
    const duplicate=el('button','Duplicar registro seleccionado para editar');duplicate.type='button';duplicate.disabled=!value.length||textarea.disabled;
    duplicate.addEventListener('click',()=>{const v=JSON.parse(JSON.stringify(value[Number(picker.value)||0]));if(v&&typeof v==='object'&&!Array.isArray(v)&&'id'in v)v.id=v.id+'-nuevo';value.push(v);sync();render();});
    const add=el('button','Añadir registro');add.type='button';add.disabled=textarea.disabled;
    add.addEventListener('click',()=>{
     let blank=templates[key];
     if(!blank){const sample=value[0];blank=typeof sample==='number'?null:typeof sample==='boolean'?null:sample&&typeof sample==='object'?JSON.parse(JSON.stringify(sample)):'';}
     if(key==='patrones'&&path.startsWith('casos.'))blank={patron:'',factor:null};
     if(key==='casos'&&path.startsWith('combinaciones.'))blank={caso:'',factor:null};
     if(['vertices','casos_ejecutar','combinaciones_resultados'].includes(key)&&depth>0)blank='';
     value.push(JSON.parse(JSON.stringify(blank)));sync();render();
    });
    const remove=el('button','Quitar registro seleccionado del borrador');remove.type='button';remove.disabled=!value.length||textarea.disabled;
    remove.addEventListener('click',()=>{value.splice(Number(picker.value)||0,1);sync();render();});
    group.append(add,duplicate,remove);
    return;
   }
   if(value!==null&&typeof value==='object'){
    const group=el('fieldset'),legend=el('legend',names[key]||key);group.append(legend);const inner=el('div');inner.className='editor-fields';group.append(inner);parentTarget.append(group);
    const old=parentTarget;parentTarget=inner;
    Object.keys(value).forEach(k=>draw(value[k],value,k,path+'.'+k,depth+1));parentTarget=old;return;
   }
   const nullBool=value===null&&(['incluir_masa_propia','transformar_rigidez'].includes(key)||path.includes('.restricciones.'));
   const refGroups={nodo_inicio:'nodos',nodo_fin:'nodos',nivel_inferior:'niveles',nivel_superior:'niveles',material:'materiales',seccion:'secciones',fuente:'fuentes',patron:'patrones',caso:'casos',superficie:'superficies'};
   const values=refGroups[key]&&Array.isArray(data[refGroups[key]])?data[refGroups[key]].map(r=>r.id):null;
   const holder=el('div'),label=el('label',names[key]||key),input=el(values||nullBool?'select':'input');input.id=prefix+'Campo'+(++nextId);label.htmlFor=input.id;
   if(nullBool){for(const [v,t]of [['','Sin definir'],['true','Sí'],['false','No']]){const o=el('option',t);o.value=v;input.append(o);}}
   if(values){const empty=el('option','Selecciona una referencia');empty.value='';input.append(empty);for(const id of new Set([value,...values].filter(Boolean))){const o=el('option',id);o.value=id;input.append(o);}}
   const bool=typeof value==='boolean',numeric=typeof value==='number'||(value===null&&!refGroups[key]&&!nullBool);
   if(!values&&!nullBool)input.type=bool?'checkbox':numeric?'number':'text';if(numeric&&!nullBool)input.step='any';
   if(bool)input.checked=value;else input.value=value===null?'':String(value);
   input.disabled=textarea.disabled;const changed=()=>{
    if(nullBool)parent[key]=input.value===''?null:input.value==='true';else if(bool)parent[key]=input.checked;else if(numeric){if(input.value!==''&&!Number.isFinite(Number(input.value))){input.setCustomValidity('Introduce un número finito.');return;}input.setCustomValidity('');parent[key]=input.value===''?null:Number(input.value);}else parent[key]=input.value;
    sync();
   };input.addEventListener('input',changed);input.addEventListener('change',changed);holder.append(label,input);parentTarget.append(holder);
  }
  let parentTarget=fields;
  function render(){
   fields.replaceChildren();parentTarget=fields;
   if(!data){status.textContent='Abre una versión conservada para consultar o editar sus datos.';return;}
   const key=chooser.value;status.textContent=(help[key]||'Revisa estos datos contra sus fuentes. La validación se ejecuta al guardar la nueva versión.')+(prefix==='geo'?' Unidad de longitud: '+data.unidad_longitud+'.':'');
   if(key in data)draw(data[key],data,key,key,0);
  }
  function load(){
   try{data=textarea.value?JSON.parse(textarea.value):null;}catch{status.textContent='Hay un error de formato en la vista técnica avanzada.';return;}
   const previous=chooser.value;chooser.replaceChildren();
   if(data)keys.filter(k=>k in data).forEach(k=>{const option=el('option',names[k]||k);option.value=k;chooser.append(option);});
   if([...chooser.options].some(o=>o.value===previous))chooser.value=previous;
   render();
  }
  chooser.addEventListener('change',render);
  textarea.addEventListener('change',load);
  new MutationObserver(()=>box.querySelectorAll('input,button').forEach(n=>n.disabled=textarea.disabled)).observe(textarea,{attributes:true,attributeFilter:['disabled']});
  if(prefix==='geo')window.addEventListener('d2m-geometry-opened',load);
  else window.addEventListener('d2m-config',e=>{if(e.detail)load();});
  window.addEventListener('d2m-case',()=>{if(!docs){data=null;render();}});load();
 }
 mount('geo',['niveles','nodos','muros','vertices','superficies','aberturas','procedencia','faltantes']);
 mount('config',['sitio','hipotesis','fuentes','materiales','secciones','puntos','frames','asignaciones_muros','asignaciones_frames','asignaciones_superficies','patrones','cargas','masa','apoyos','diafragmas','sin_diafragma','espectros','casos','combinaciones','analisis','liquidos','conexiones_borde','malla','cortes_nivel','nodos_derivados','subdivision_frames','faltantes']);
})();
