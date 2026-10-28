'use strict';
let session = '', latest = null, busy = false, rendered = '';
const $ = id => document.getElementById(id);
const names = {pendiente:'Pendiente',en_desarrollo:'En desarrollo',implementado:'Implementado',verificado:'Verificado',bloqueado:'Bloqueado'};
const dates = value => value ? new Date(value).toLocaleString('es-PE',{timeZone:'America/Lima',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}) + ' · Perú' : 'Sin lectura disponible';
function el(tag, text, cls){const x=document.createElement(tag);if(text!==undefined)x.textContent=text;if(cls)x.className=cls;return x;}
function badge(state){return el('span',names[state]||state,'badge '+state);}
function mini(value,total,remote=false){const x=el('div',undefined,'mini'+(remote?' remote':''));const label=el('div',undefined,'bar-label');label.append(el('span',remote?'Publicado':'Local'),el('b',`${value}/${total}`));const track=el('div',undefined,'track'),bar=el('div');bar.style.width=(total?100*value/total:0)+'%';track.append(bar);x.append(label,track);return x;}
function drawMilestones(s){
  const key=JSON.stringify([s.local,s.published,$('filter').value]);if(key===rendered)return;rendered=key;
  const open=new Set([...document.querySelectorAll('.milestone[open]')].map(x=>x.id));
  const target=$('milestones');target.replaceChildren();
  s.local.milestones.forEach((m,i)=>{
    const r=s.published.milestones[i], card=el('details',undefined,'milestone');card.id='milestone-'+m.id;if(open.has(card.id))card.open=true;
    const summary=el('summary'), title=el('div',m.title,'milestone-title');title.append(el('small',m.depends.length?'Depende de '+m.depends.join(', '):'Base del proyecto'));
    summary.append(el('div',m.id,'milestone-id'),title,mini(m.done,m.total),mini(r.done,r.total,true),el('span','›','chevron'));card.append(summary);
    const body=el('div',undefined,'criteria'),head=el('div',undefined,'criteria-head');head.append(el('span','CRITERIO DE CUMPLIMIENTO'),el('span','LOCAL'),el('span','PUBLICADO'));body.append(head);
    let shown=0;
    m.criteria.forEach((c,j)=>{
      const rc=r.criteria[j],f=$('filter').value;if(f==='pending'&&c.state==='verificado')return;if(f==='verified'&&c.state!=='verificado')return;shown++;
      const row=el('div',undefined,'criterion'),name=el('div',undefined,'criterion-name');name.append(el('code',c.id),document.createTextNode(c.title));
      const local=el('div'),remote=el('div');local.append(badge(c.state));remote.append(badge(rc.state));row.append(name,local,remote);
      const d=el('details');d.append(el('summary','Ver evidencia y pendientes'),el('p','Local: '+c.reason),el('p','Publicado: '+rc.reason));
      const evidence=[...c.evidence.map(x=>'Local · '+(x.kind==='pruebas'?x.tests+' pruebas · ':x.reviewer?x.reviewer+' · ':'' )+dates(x.date)),...rc.evidence.map(x=>'Publicado · '+(x.kind==='pruebas'?'Prueba local sobre archivos publicados idénticos · ':x.reviewer?x.reviewer+' · ':'')+dates(x.date))];
      if(evidence.length){const ul=el('ul');evidence.forEach(e=>ul.append(el('li',e)));d.append(ul);}
      if(c.files.length){const ul=el('ul');c.files.forEach(p=>ul.append(el('li',p+(c.missing.includes(p)?' · ausente local':''))));d.append(ul);}
      row.append(d);body.append(row);
    });
    if(!shown)body.append(el('p','No hay criterios para este filtro.','empty'));
    const a=el('a','Abrir Issue del hito ↗','issue-link');a.href=m.issue;a.target='_blank';a.rel='noopener noreferrer';body.append(a);card.append(body);target.append(card);
  });
}
function draw(s){
  latest=s;session=s.session;
  $('connection').textContent='● Carpeta local en observación';
  $('localPercent').textContent=s.local.percent+'%';$('remotePercent').textContent=s.github.sha?s.published.percent+'%':'—';
  $('localBar').style.width=s.local.percent+'%';$('remoteBar').style.width=(s.github.sha?s.published.percent:0)+'%';
  $('localCount').textContent=`${s.local.done} de ${s.local.total} criterios verificados`;
  $('remoteCount').textContent=s.github.sha?`${s.published.done} de ${s.published.total} criterios verificados`:'Sin lectura del repositorio';
  $('remoteDate').textContent='Consulta: '+dates(s.github.checked_at);
  $('pendingCount').textContent=s.local.total-s.local.done;
  const flat=s.local.milestones.flatMap(m=>m.criteria);$('pendingDetail').textContent=`${flat.filter(c=>c.state==='implementado').length} implementados por comprobar · ${flat.filter(c=>c.state==='bloqueado').length} bloqueados`;
  $('diffCount').textContent=s.github.sha?s.differences.length:'—';
  $('tests').disabled=s.testing;$('tests').textContent=s.testing?'Comprobando…':'Comprobar pruebas';
  $('githubStatus').textContent=s.github_mode==='automatico'?'GitHub conectado · consulta automática cada 60 s':'GitHub · última lectura conservada';
  $('githubMessage').textContent=s.github_error||(s.github_mode==='automatico'?'Rama '+s.github.branch+' · solo lectura. Se muestran resultados comprobados; publicar archivos no los aprueba automáticamente.':'Lectura obtenida mediante el conector del chat. Conecta una credencial para seguir consultando mientras el tablero está abierto.');
  $('githubNotice').classList.toggle('ok',s.github_mode==='automatico');$('connect').textContent=s.github_mode==='automatico'?'Cambiar conexión':'Conectar GitHub';
  $('commit').textContent=s.github.sha?s.github.branch+' · '+s.github.sha.slice(0,8):'Sin commit consultado';
  drawMilestones(s);
  const differences=$('differences');differences.replaceChildren();
  s.differences.slice(0,150).forEach(d=>{const row=el('div',undefined,'file-row');row.append(el('code',d.path),el('span',{nuevo:'Solo local',modificado:'Diferente',solo_github:'Solo GitHub'}[d.kind]||d.kind,'badge'));differences.append(row);});
  if(!s.differences.length)differences.append(el('div',s.github.sha?'Los archivos comparables coinciden.':'Conecta GitHub para comparar archivos.','empty'));
  const activity=$('activity');activity.replaceChildren();
  s.activity.slice(0,35).forEach(a=>{const row=el('div',undefined,'activity-row'),text=el('div',a.message,'activity-message');if(a.interpretation)text.append(el('small',a.interpretation+(a.criteria?.length?' · '+a.criteria.join(', '):'')));row.append(el('span','','dot'),text,el('time',dates(a.date)));activity.append(row);});
  if(!s.activity.length)activity.append(el('div','Punto de partida registrado. Los siguientes cambios aparecerán aquí.','empty'));
  $('updated').textContent='Última lectura local: '+dates(s.last_scan)+(s.tests.finished?' · Pruebas: '+s.tests.count+(s.tests.skipped?.length?' · '+s.tests.skipped.length+' omitidas':'')+' · '+dates(s.tests.finished):'');
  if(s.scan_errors.length)showError(s.scan_errors.join(' · '));else $('error').hidden=true;
}
function showError(message){$('error').hidden=false;$('error').textContent=message;}
async function poll(){if(busy)return;busy=true;try{const r=await fetch('/api/state',{cache:'no-store'});if(!r.ok)throw Error('No se pudo leer el catálogo. Se conserva la vista anterior.');draw(await r.json());}catch(e){$('connection').textContent='● Sin conexión al controlador';showError(e.message+' Abre “Abrir control de avance.cmd” si el proceso está detenido.');}finally{busy=false;}}
async function post(route,body={}){const r=await fetch(route,{method:'POST',headers:{'Content-Type':'application/json','X-Control-Session':session},body:JSON.stringify(body)});if(!r.ok)throw Error((await r.json()).error||'No se completó la operación.');await poll();}
$('refresh').addEventListener('click',()=>post('/api/refresh').catch(e=>showError(e.message)));
$('tests').addEventListener('click',()=>post('/api/tests').catch(e=>showError(e.message)));
$('filter').addEventListener('change',()=>{if(latest)drawMilestones(latest);});
$('connect').addEventListener('click',()=>$('auth').showModal());$('closeAuth').addEventListener('click',()=>$('auth').close());
$('authForm').addEventListener('submit',async e=>{e.preventDefault();try{const value=$('token').value;$('token').value='';await post('/api/connect',{token:value});$('auth').close();$('authError').textContent='';}catch(error){$('authError').textContent=error.message;}});
if(location.protocol==='file:'){
  let loadingFile=false;
  window.recibirControlAvance=s=>{
    try{
      draw(s);session='';
      $('connection').textContent='HTML vinculado · lectura de archivo';
      $('tests').disabled=true;$('tests').textContent='Pruebas mediante observador';
      $('connect').hidden=true;
      const old=!s.last_scan||Date.now()-new Date(s.last_scan).getTime()>15000;
      $('githubMessage').textContent=(s.github_error?s.github_error+' ':'')+
        'Datos enlazados: tmp/control_avance/estado.js. '+
        (old?'Lectura anterior: inicia “Abrir control de avance.cmd” para calcular cambios nuevos.':'Observador reciente. El HTML vuelve a leer los datos cada 2 segundos.')+
        ' GitHub conserva su propia fecha de consulta.';
      $('githubStatus').textContent=s.github_mode==='automatico'?'GitHub · consulta mediante observador':'GitHub · lectura guardada';
    }catch(error){showError('Archivo de datos inválido; se conserva la lectura anterior.');}
  };
  function readLinkedFile(){
    if(loadingFile)return;loadingFile=true;
    const previous=document.getElementById('control-data-script');if(previous)previous.remove();
    const script=document.createElement('script');script.id='control-data-script';
    script.src=new URL('tmp/control_avance/estado.js?v='+Date.now(),document.baseURI).href;
    script.onload=()=>{loadingFile=false;};
    script.onerror=()=>{loadingFile=false;$('connection').textContent='Archivo de datos no disponible';showError('No se pudo leer estado.js. Ejecuta “Abrir control de avance.cmd” desde la carpeta del proyecto.');};
    document.head.append(script);
  }
  // Los botones del servidor no se usan al abrir un HTML local.
  $('refresh').replaceWith($('refresh').cloneNode(true));
  $('refresh').addEventListener('click',readLinkedFile);
  $('tests').disabled=true;$('connect').hidden=true;
  readLinkedFile();setInterval(readLinkedFile,2000);
}else{
  poll();setInterval(poll,2000);
}
