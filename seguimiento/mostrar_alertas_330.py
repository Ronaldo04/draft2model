"""Integra avisos ya calculados, sin modificar registros ni pruebas en ejecución."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / 'draft2model/revision_web/app.js'
text = path.read_text(encoding='utf-8')
marker = 'function renderReadings(){'
assert text.count(marker) == 1
helper = '''function avisosCandidato(index){
 const ruta='$.candidatos['+index+']';
 const avisos=record?.comprobacion?.validacion?.advertencias;
 return Array.isArray(avisos)?avisos.filter(a=>a&&typeof a.ruta==='string'&&typeof a.mensaje==='string'&&(a.ruta===ruta||a.ruta.startsWith(ruta+'.')||a.ruta.startsWith(ruta+'['))):[];
}
'''
assert 'function avisosCandidato' not in text
old = 'for(const c of candidates){if'
assert text.count(old) == 1
text = text.replace(old, 'for(const [index,c] of candidates.entries()){if')
old = 'b.onclick=()=>selectCandidate(c.id);b.disabled=busy;list.append(b);'
assert text.count(old) == 1
new = "for(const aviso of avisosCandidato(index))b.append(node('small','Revisar evidencia: '+aviso.mensaje,'warning'));" + old
text = text.replace(old, new).replace(marker, helper + marker)
path.write_text(text, encoding='utf-8')
print('Avisos incorporados a la lista de candidatos; copia global329 sin cambios.')
