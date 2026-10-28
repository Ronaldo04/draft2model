"""Candidato independiente de UI; no modifica el producto que integra Claude."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1]
src=root/'draft2model/revision_web/resultados.js';raw=src.read_bytes();text=raw.decode('utf-8')
a=text.index(' async function listing(');b=text.index('\n function query(',a)
replacement=''' async function listing(preferredModel,preferredResult){
  const own=context,seq=++listTicket,caso=docs?.caso;if(!caso)return;
  const active=()=>own===context&&seq===listTicket&&docs?.caso===caso;
  async function column(prefix,endpoint,preferred){
   $(prefix+'Estado').textContent='Consultando versiones y comprobando fuentes…';
   if(!$(prefix+'Version').value)options($(prefix+'Version'),[['','Consultando versiones…']]);
   try{
    const response=await api(endpoint+'?'+new URLSearchParams({caso}));
    const list=await response.json();if(!active())return;
    const rows=list.versiones,previous=$(prefix+'Version').value;
    if(prefix==='resultado')invalidResults=new Set(rows.filter(v=>!v.vigente).map(v=>v.id));
    options($(prefix+'Version'),[['',rows.length?'Selecciona versión':'Sin versiones'],...rows.map(r=>[r.id,r.id+(r.vigente?'':' · requiere revisión')])]);
    if(rows.some(r=>r.id===previous))$(prefix+'Version').value=previous;
    if(prefix==='resultado'&&previous&&!rows.some(r=>r.id===previous&&r.vigente)){resultTicket++;resetResult();}
    $(prefix+'Estado').textContent=rows.length?rows.length+' versión(es) conservada(s).':'No hay versiones conservadas en este expediente.';
    window.resultControls();if(!active())return;
    if(preferred){
     const row=rows.find(v=>v.id===preferred);
     $(prefix+'Version').value=row?preferred:'';
     if(row?.vigente)await (prefix==='modelo'?openModel():openResult());
     else if(prefix==='resultado'){resultTicket++;resetResult();$('resultadoEstado').textContent='El resultado seleccionado no está vigente. Vuelve a comprobar sus fuentes.';}
    }
   }catch(error){
    if(!active())return;
    $(prefix+'Estado').textContent=error.message;
    if(prefix==='resultado'){resultTicket++;resetResult();}
    window.resultControls();message(error.message,true);
   }
  }
  await Promise.all([column('modelo','/api/modelos',preferredModel),column('resultado','/api/resultados',preferredResult)]);
 }
'''
out=root/'tmp/candidato_listados_270';out.mkdir(exist_ok=False)
(out/'resultados.js').write_text(text[:a]+replacement+text[b:],encoding='utf-8')
(out/'ORIGEN.json').write_text(json.dumps({'fuente':str(src.relative_to(root)),'sha256':hashlib.sha256(raw).hexdigest(),'producto_modificado':False},indent=2)+'\n',encoding='utf-8')
print('Candidato preparado: tmp/candidato_listados_270/resultados.js; producto intacto.')
