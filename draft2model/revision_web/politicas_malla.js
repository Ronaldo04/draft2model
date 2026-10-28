'use strict';
(()=>{
 const target=window.D2MEtapas?.containers.get('ingenieria');if(!target)return;
 const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
 const panel=el('section');panel.className='geometry';panel.setAttribute('aria-label','Políticas explícitas de malla');
 panel.append(el('h2','Condiciones de los nodos de malla'),el('p','Define reglas para los nodos que el programa calcula al mallar superficies y subdividir barras. Las reglas no cambian los apoyos de los puntos originales. Ningún nodo se libera, apoya o incorpora a un diafragma sin una decisión explícita.'));
 const form=el('form');form.id='pmForm';const controls=[];let serial=0,current=null,epoch=0,edit=0,working=false,dirty=false,preview=null;
 const restrictions=[],diaphragms=[];
 const status=el('p','Abre una configuración en preparación para revisar su malla.');status.id='pmStatus';status.setAttribute('role','status');status.setAttribute('aria-live','polite');
 const summary=el('p'),issues=el('ul');issues.id='pmIssues';
 const details=el('details'),computed=el('ul');details.append(el('summary','Ver condiciones calculadas y barras a subdividir'),computed);
 function field(parent,id,text,type='text'){const n=el('input');n.id=id;n.type=type;if(type==='number')n.step='any';const label=el('label',text);label.htmlFor=id;parent.append(label,n);controls.push(n);return n;}
 function select(parent,id,text,options){const n=el('select');n.id=id;const label=el('label',text);label.htmlFor=id;for(const [value,text] of options){const o=el('option',text);o.value=value;n.append(o);}parent.append(label,n);controls.push(n);return n;}
 function button(parent,id,text,fn){const n=el('button',text);n.id=id;n.type='button';n.addEventListener('click',fn);parent.append(n);controls.push(n);return n;}
 const source=select(form,'pmSource','Fuente de las reglas que introduces', [['','Selecciona una fuente'],['DECISION-FORMULARIO','Declaración de este formulario']]);
 const rr=el('fieldset');rr.append(el('legend','Restricciones por plano o borde'));
 const rrList=el('div');rr.append(rrList);button(rr,'pmAddRestriction','Añadir regla de restricciones',()=>addRestriction());form.append(rr);
 const dd=el('fieldset');dd.append(el('legend','Diafragma o exclusión por plano Z'));
 const ddList=el('div');dd.append(ddList);button(dd,'pmAddDiaphragm','Añadir regla de diafragma',()=>addDiaphragm());form.append(dd);
 const rest=el('fieldset');rest.append(el('legend','Resto de los nodos derivados'),el('p','Estas opciones afectan solo a nodos no cubiertos por una regla. Dejarlas sin resolver conserva pendientes.'));
 const restR=select(rest,'pmRestR','Restricciones del resto',[['','Sin resolver'],['libre','Declarar las seis libertades del resto sin restricción']]);
 const restRMotive=field(rest,'pmRestRMotive','Sustento de las libertades del resto');
 const restD=select(rest,'pmRestD','Diafragma del resto',[['','Sin resolver'],['excluir','Excluir explícitamente el resto de los diafragmas']]);
 const restDMotive=field(rest,'pmRestDMotive','Motivo de exclusión del resto');form.append(rest);
 const subdivide=field(form,'pmSubdivide','Autorizo las subdivisiones de barras calculadas que se mostrarán en la vista previa','checkbox');
 const subdivideMotive=field(form,'pmSubdivideMotive','Sustento de la autorización de subdivisiones');
 const declaration=el('fieldset');declaration.append(el('legend','Responsable y alcance de la decisión'));
 const reviewer=field(declaration,'pmReviewer','Declarante de las reglas'),date=field(declaration,'pmDate','Fecha de declaración','date'),scope=field(declaration,'pmScope','Alcance y límites de las reglas');form.append(declaration);
 const previewButton=button(form,'pmPreview','Previsualizar políticas de malla',()=>run(false));
 const confirm=field(form,'pmConfirm','He revisado los nodos, subdivisiones, pendientes y conflictos de esta propuesta','checkbox');
 const apply=el('button','Guardar políticas en un nuevo borrador');apply.id='pmApply';apply.type='submit';form.append(apply);controls.push(apply);
 panel.append(form,status,summary,issues,details);target.append(panel);const baseControls=controls.slice();
 function update(){for(const n of controls)n.disabled=!current||working||dirty;apply.disabled=!current||working||dirty||!preview?.politicas_completas||!confirm.checked;confirm.disabled=!current||working||dirty||!preview?.politicas_completas;}
 function invalidate(){edit++;preview=null;confirm.checked=false;summary.textContent='';issues.replaceChildren();computed.replaceChildren();update();}
 function removeCard(card,rows,row){const index=rows.indexOf(row);if(index>=0)rows.splice(index,1);card.remove();invalidate();}
 function hosts(parent,id){return field(parent,id,'Hosts opcionales, IDs separados por coma');}
 function pointOptions(){return [['','Selecciona un punto'],...(current?.datos?.puntos||[]).map(p=>[p.id,p.id])];}
 function diaphragmOptions(){return [['','Selecciona un diafragma existente'],...(current?.datos?.diafragmas||[]).map(p=>[p.id,p.id])];}
 function addRestriction(){if(!current)return;const id=++serial,card=el('fieldset');card.append(el('legend','Regla de restricciones '+id));
  const kind=select(card,'pmRKind'+id,'Seleccionar nodos mediante',[['','Selecciona plano o borde'],['plano_z','Plano Z'],['borde_entre_puntos','Borde entre puntos existentes']]);
  const z=field(card,'pmRZ'+id,'Cota Z del plano (m)','number'),start=select(card,'pmRStart'+id,'Inicio del borde',pointOptions()),end=select(card,'pmREnd'+id,'Fin del borde',pointOptions()),host=hosts(card,'pmRHosts'+id);
  const states=['UX','UY','UZ','RX','RY','RZ'].map(axis=>select(card,'pmR'+axis+id,axis,[['','Elige restricción'],['restringido','Restringido'],['libre','Libre']]));
  const motive=field(card,'pmRMotive'+id,'Motivo de esta regla');const row={id,kind,z,start,end,host,states,motive};restrictions.push(row);
  button(card,'pmRRemove'+id,'Quitar regla de restricciones',()=>removeCard(card,restrictions,row));rrList.append(card);invalidate();}
 function addDiaphragm(){if(!current)return;const id=++serial,card=el('fieldset');card.append(el('legend','Regla de diafragma '+id));
  const z=field(card,'pmDZ'+id,'Cota Z del plano (m)','number'),host=hosts(card,'pmDHosts'+id);
  const action=select(card,'pmDAction'+id,'Decisión para este plano',[['','Selecciona una decisión'],['asignar','Asignar a diafragma existente'],['excluir','Excluir con motivo explícito']]);
  const diaphragm=select(card,'pmDId'+id,'Diafragma',diaphragmOptions()),motive=field(card,'pmDMotive'+id,'Motivo de exclusión, cuando corresponda');const row={id,z,host,action,diaphragm,motive};diaphragms.push(row);
  button(card,'pmDRemove'+id,'Quitar regla de diafragma',()=>removeCard(card,diaphragms,row));ddList.append(card);invalidate();}
 function number(field){if(!field.value.trim()||!Number.isFinite(Number(field.value)))throw Error('Completa las cotas numéricas explícitas; una cota vacía no significa cero.');return Number(field.value);}
 function text(field,label){const value=field.value.trim();if(!value)throw Error('Completa '+label+'.');return value;}
 function optionalHosts(field){const ids=field.value.split(',').map(v=>v.trim()).filter(Boolean);if(new Set(ids).size!==ids.length)throw Error('Los hosts no deben repetirse.');return ids.length?{hosts:ids}:{};}
 function declarationBody(required){if(!required&&!reviewer.value.trim()&&!date.value&&!scope.value.trim())return null;
  return {declarado_por:text(reviewer,'el declarante'),fecha:text(date,'la fecha'),alcance:text(scope,'el alcance de la decisión')};}
 function body(){const rules={contrato:'draft2model.reglas_politica_malla',version_contrato:'0.1.0',unidad_longitud:'m',reglas_restricciones:[],resto_restricciones:null,reglas_diafragma:[],resto_diafragma:null,subdivision_frames:null};
  const active=restrictions.length||diaphragms.length||restR.value||restD.value||subdivide.checked;
  if(active&&!source.value)throw Error('Selecciona la fuente de las reglas.');
  for(const row of restrictions){let selector;if(row.kind.value==='plano_z')selector={tipo:'plano_z',z_m:number(row.z),...optionalHosts(row.host)};
   else if(row.kind.value==='borde_entre_puntos')selector={tipo:'borde_entre_puntos',inicio:text(row.start,'el inicio del borde'),fin:text(row.end,'el fin del borde'),...optionalHosts(row.host)};
   else throw Error('Selecciona un plano o un borde para cada regla de restricciones.');
   if(row.states.some(n=>!n.value))throw Error('Declara las seis restricciones de cada regla.');
   rules.reglas_restricciones.push({id:'RF'+row.id,selector,restricciones:row.states.map(n=>n.value==='restringido'),fuente:source.value,motivo:text(row.motive,'el motivo de la regla')});}
  for(const row of diaphragms){if(!row.action.value)throw Error('Selecciona asignar o excluir en cada regla de diafragma.');
   const assign=row.action.value==='asignar';rules.reglas_diafragma.push({id:'DF'+row.id,selector:{tipo:'plano_z',z_m:number(row.z),...optionalHosts(row.host)},accion:row.action.value,
    diafragma:assign?text(row.diaphragm,'el diafragma existente'):null,motivo_sin_diafragma:assign?null:text(row.motive,'el motivo de exclusión'),fuente:source.value});}
  if(restR.value==='libre')rules.resto_restricciones={restricciones:[false,false,false,false,false,false],fuente:source.value,motivo:text(restRMotive,'el sustento de las libertades del resto')};
  if(restD.value==='excluir')rules.resto_diafragma={accion:'excluir',diafragma:null,motivo_sin_diafragma:text(restDMotive,'el motivo de exclusión del resto'),fuente:source.value};
  if(subdivide.checked)rules.subdivision_frames={modo:'autorizar_calculadas',fuente:source.value,motivo:text(subdivideMotive,'el sustento de las subdivisiones')};
  return {caso:current.caso,expediente_sha256:current.expediente_sha256,version:current.id,sha256_configuracion:current.sha256_configuracion,reglas:rules,declaracion:declarationBody(active&&source.value==='DECISION-FORMULARIO')};}
 function show(value){const p=value.propuesta||{},r=p.resumen||{};summary.textContent=(value.malla_calculable?'Malla calculable. ':'Malla todavía no calculable. ')+(value.politicas_completas?'Políticas completas para esta malla; la configuración conserva su revisión pendiente. ':'Políticas incompletas. ')+
  (r.nodos_derivados_resueltos??0)+'/'+(r.total_nodos_derivados??0)+' nodos y '+(r.frames_subdivididos_resueltos??0)+'/'+(r.total_frames_subdivididos??0)+' barras resueltos.';
  issues.replaceChildren();for(const group of ['errores','conflictos','pendientes'])for(const row of p[group]||[])issues.append(el('li',row.mensaje||row.motivo||row.ruta||group));
  for(const row of value.otros_faltantes_tecnicos||[])issues.append(el('li','Otro dato pendiente: '+(row.ruta||'')+' '+row.motivo));
  for(const error of value.validacion?.errores||[])issues.append(el('li','Configuración: '+error));}
 function showComputed(value){computed.replaceChildren();const p=value.propuesta||{};
  for(const row of p.nodos_derivados_propuestos||[]){const restrained=['UX','UY','UZ','RX','RY','RZ'].filter((_,i)=>row.restricciones?.[i]);
   computed.append(el('li',row.nodo+' · ('+(row.xyz_m||[]).join(', ')+') m · restringidos: '+(restrained.join(', ')||'ninguno por decisión explícita')+' · diafragma: '+(row.diafragma||'excluido: '+row.motivo_sin_diafragma)));}
  for(const row of p.subdivision_frames_propuesta||[])computed.append(el('li','Barra '+row.frame+' · subdividir en los nodos '+(row.nodos||[]).join(', ')));
  for(const id of p.reglas_sin_coincidencia||[])issues.append(el('li','Regla sin coincidencias en esta malla: '+id));}
 async function run(applying){if(!current||working||dirty)return;if(applying&&(!preview?.politicas_completas||!confirm.checked)){status.textContent='Previsualiza y confirma la propuesta antes de aplicarla.';return;}
  const own=epoch,revision=edit;let request;try{request=body();if(applying){request.declaracion=declarationBody(true);request={...request,confirmacion_explicita:true,huella_propuesta:preview.huella_propuesta,sha256_algoritmo:preview.sha256_algoritmo};}}
  catch(error){status.textContent=error.message;return;}
  working=true;update();try{const response=await api('/api/politicas-malla/'+(applying?'aplicar':'previsualizar'),request),value=await response.json();
   if(applying){const active=typeof docs!=='undefined'?docs:current;if(!active||active.caso!==request.caso||active.expediente_sha256!==request.expediente_sha256)return;
    window.dispatchEvent(new CustomEvent('d2m-preconfig-created',{detail:{caso:value.caso,expediente_sha256:value.expediente_sha256,configuracion_preparacion:value.id,sha256_configuracion:value.sha256_configuracion,preparacion_origen:request.version}}));
    if(own!==epoch||revision!==edit)return;preview=null;confirm.checked=false;status.textContent='Políticas conservadas en un nuevo borrador. No se aprobó la configuración ni se ejecutó ETABS.';}
   else{if(own!==epoch||revision!==edit)return;preview=value;confirm.checked=false;show(value);showComputed(value);status.textContent='Revisa la propuesta calculada antes de confirmar su aplicación.';}}
  catch(error){if(own===epoch&&revision===edit){preview=null;confirm.checked=false;status.textContent=error.message;}}
  finally{if(own===epoch){working=false;update();}}}
 form.addEventListener('submit',event=>{event.preventDefault();return run(true);});
 form.addEventListener('input',event=>{if(event.target===confirm){update();return;}invalidate();});
 form.addEventListener('change',event=>{if(event.target===confirm){update();return;}invalidate();});
 function reset(value){epoch++;edit++;current=value;working=false;dirty=false;preview=null;confirm.checked=false;restrictions.splice(0);diaphragms.splice(0);rrList.replaceChildren();ddList.replaceChildren();controls.splice(0,controls.length,...baseControls);
  for(const n of controls){if(n.type==='checkbox')n.checked=false;else if(n.tagName?.toLowerCase()==='input'||n.tagName?.toLowerCase()==='select')n.value='';}
  source.replaceChildren();for(const [value,text] of [['','Selecciona una fuente'],['DECISION-FORMULARIO','Declaración de este formulario'],...(current?.datos?.fuentes||[]).map(f=>[f.id,f.id+' · '+f.descripcion])]){const o=el('option',text);o.value=value;source.append(o);}source.value='';
  summary.textContent='';issues.replaceChildren();computed.replaceChildren();status.textContent=value?'Declara reglas o consulta la malla con decisiones todavía pendientes.':'Abre una configuración en preparación para revisar su malla.';update();}
 window.addEventListener('d2m-preconfig-opened',event=>{const value=event.detail;if(!value?.id||!value.datos)return;
  if(typeof docs!=='undefined'&&docs&&(value.caso!==docs.caso||value.expediente_sha256!==docs.expediente_sha256))return;reset(value);});
 window.addEventListener('d2m-preconfig-edited',event=>{const value=event.detail;if(current&&value?.sin_guardar===true&&value.id===current.id&&value.caso===current.caso&&value.expediente_sha256===current.expediente_sha256){dirty=true;invalidate();status.textContent='Guarda los cambios de configuración y abre su versión conservada antes de revisar políticas de malla.';}});
 window.addEventListener('d2m-case',()=>reset(null));update();
})();
