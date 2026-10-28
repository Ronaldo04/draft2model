"""Incorpora consulta local y previsualización, sin aplicar regiones por sí sola."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
html = root / 'draft2model/revision_web/index.html'
text = html.read_text(encoding='utf-8')
marker = '    <label for="estado">'
assert text.count(marker) == 1 and 'id="buscarLiteral"' not in text
text = text.replace(marker, '''    <div><button id="buscarLiteral" type="button">Buscar texto literal en PDF local</button>
    <p id="busquedaLiteralEstado" class="hint">Solo propone regiones del texto vectorial; no aplica cambios ni usa APIs.</p>
    <div id="busquedaLiteralOpciones"></div></div>
''' + marker)
html.write_text(text, encoding='utf-8')
app = root / 'draft2model/revision_web/app.js'
text = app.read_text(encoding='utf-8')
marker = 'function selectCandidate(id)'
assert text.count(marker) == 1
helper = '''function limpiarBusquedaLiteral(){
 $('busquedaLiteralOpciones').replaceChildren();$('busquedaLiteralEstado').textContent='Solo propone regiones; no aplica cambios ni usa APIs.';
 $('buscarLiteral').disabled=false;
}
async function buscarLiteral(){
 if(busy||!record||!selected||!docs)return;
 const original=record,id=selected,version=$('version').value;
 $('buscarLiteral').disabled=true;$('busquedaLiteralOpciones').replaceChildren();$('busquedaLiteralEstado').textContent='Buscando palabras completas en la fuente local…';
 try{
  const res=await api('/api/localizar-lectura?'+new URLSearchParams({caso:docs.caso,version,candidato:id,expediente_sha256:docs.expediente_sha256,huella:record.huella}));
  const data=await res.json();if(record!==original||selected!==id)return;
  if(data.huella!==record.huella||data.candidato!==id||data.version!==version||data.modifica_datos!==false)throw Error('La búsqueda no corresponde a la lectura abierta.');
  if(data.estado==='sin_texto_literal'){$('busquedaLiteralEstado').textContent='Sin texto literal registrado: no se infiere a partir del valor propuesto.';return;}
  let total=0;const estados=[];
  for(const fuente of data.fuentes||[]){
   estados.push(fuente.archivo_id+' / '+fuente.pagina+': '+fuente.estado+' ('+fuente.total+')');
   for(const region of fuente.regiones||[]){
    const b=node('button','Previsualizar opción '+(++total)+' · '+fuente.archivo_id+' / '+fuente.pagina);b.type='button';
    b.onclick=async()=>{if(busy||record!==original||selected!==id)return;try{
      const box=parseBbox(region.bbox_normalizada.join(','));await showEvidence(fuente);
      if(record!==original||selected!==id)return;
      $('reubicarBbox').value=box.join(',');$('reubicarGuardar').disabled=true;showPreview(box);
      $('busquedaLiteralEstado').textContent='Región cargada para contraste visual. No se guardó ni aprobó: revisa el plano antes de reubicar.';
     }catch(e){message(e.message,true);}};
    $('busquedaLiteralOpciones').append(b);
   }
  }
  $('busquedaLiteralEstado').textContent=estados.join(' · ')+'. '+(total>1?'Hay varias regiones; ninguna se selecciona automáticamente.':'Contrastar con la imagen antes de reubicar.');
 }catch(error){if(record===original&&selected===id)message(error.message,true);}
 finally{if(record===original&&selected===id)$('buscarLiteral').disabled=false;}
}
$('buscarLiteral').onclick=buscarLiteral;
'''
text = text.replace(marker, helper + marker)
old = 'selected=id;const c=record.datos.candidatos.find'
assert text.count(old) == 1
text = text.replace(old, 'selected=id;limpiarBusquedaLiteral();const c=record.datos.candidatos.find')
app.write_text(text, encoding='utf-8')
print('Búsqueda local y previsualización integradas; sin guardado automático.')
