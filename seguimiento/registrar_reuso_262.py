"""Preparar diff revisable del candidato262 sin alterar implementación de Claude."""
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
base=root/'tmp/reuso_preparacion_262'
work=base/'fuentes'
manifest=json.loads((base/'congelado.json').read_bytes())
old_model='            self.preparacion = mp.preparar_malla(geometria, d)'
new_model='''            from . import reuso_preparacion as rp
            try:
                entradas_preparacion = rp.huellas(geometria, d)
                self.preparacion = mp.preparar_malla(geometria, d)
                self.r._preparacion_malla_reutilizable = rp.sellar(geometria, d, self.preparacion, entradas_preparacion)
            except (ValueError, TypeError) as error:
                raise mp.ErrorMalla(str(error)) from error'''
old_ops='        prep = me.mp.preparar_malla(consulta.geometria, config)'
new_ops='''        from . import reuso_preparacion as rp
        prep = rp.obtener(getattr(resultado, "_preparacion_malla_reutilizable", None), consulta.geometria, config)
        if prep is None:
            prep = me.mp.preparar_malla(consulta.geometria, config)'''
chunks=[]
for name,old,new in [('draft2model/modelo_estructural.py',old_model,new_model),('draft2model/operaciones_etabs.py',old_ops,new_ops)]:
    text=(work/name).read_text(encoding='utf-8')
    if text.count(new)!=1:raise ValueError('Fragmento candidato no único: '+name)
    previous=text.replace(new,old)
    variants=(previous.encode('utf-8'),previous.replace('\n','\r\n').encode('utf-8'))
    original=next((raw for raw in variants if hashlib.sha256(raw).hexdigest()==manifest['fuentes_base'][name]),None)
    if original is None:raise ValueError('No se pudo reconstruir base exacta: '+name)
    target=base/'original'/name
    target.parent.mkdir(exist_ok=True,parents=True)
    with target.open('xb') as stream:stream.write(original)
    chunks.extend(difflib.unified_diff(previous.splitlines(keepends=True),text.splitlines(keepends=True),fromfile='a/'+name,tofile='b/'+name))
(base/'candidato.patch').write_text(''.join(chunks),encoding='utf-8')
current={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in manifest['fuentes_base']}
record={'fecha_utc':datetime.now(timezone.utc).isoformat(),'responsable':'Codex','portado':False,
    'candidato':'tmp/reuso_preparacion_262','fuentes_base':manifest['fuentes_base'],'fuentes_actuales':current,
    'base_sigue_igual':current==manifest['fuentes_base'],'pruebas_propias':'6 OK, 8.095s',
    'comparaciones':json.loads((work/'comparaciones.json').read_bytes()),
    'contraste_adicional':'Plan0.5 con contenido/agua220kN idéntico completo; dos preparaciones→una',
    'alcance':'Instantánea JSON privada en ResultadoModelo, sin alterar a_dict ni hashes de planes, sin caché global/disco; fingerprint íntegro de ambas entradas, incluye revisión; copia por consumidor, fallback original y precondiciones conservados',
    'limites':['No se midió aceleración del caso real; solo se comprobó evitar un cálculo de dos en escenarios sintéticos',
               'Requiere fusión por propietario de archivos actuales y prueba focal en destino',
               'La primera copia candidata tuvo saltos CRCRLF, fixtures examples ausentes y nombre de escenario incorrecto; corregidos en candidato, nunca en producto'],
    'apis_remotas':0,'etabs':False}
(root/'seguimiento/CANDIDATO_REUSO_262.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'portado':False,'pruebas':'6OK','base_sigue_igual':record['base_sigue_igual'],'parche':'tmp/reuso_preparacion_262/candidato.patch'}))
