"""Contraste independiente de un registro cerrado; no prueba el navegador ni código en edición."""
import hashlib
import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
base = ROOT/'data/private/provisional-001/vision/respuestas/34528ff1579441758ae0adf34d60f144'
rawbytes = (base/'respuesta_original.json').read_bytes()
raw = json.loads(rawbytes)
data = json.loads((base/'extraccion.json').read_text(encoding='utf-8'))
reg = json.loads((base/'registro.json').read_text(encoding='utf-8'))
original = {c['id']:c for c in raw['candidatos']}
valid = Counter(e['recorte_id'] for c in data['candidatos'] for e in c['evidencia'])
invalid = Counter(r for c in data['cuarentena'] for r in set(c['recortes']))
checks = []
for c in data['cobertura']:
    recorte = c['recorte_id']
    eff = c['efectiva']
    checks.append(dict(recorte=recorte, declarada=c['estado'],
        validos_contados=valid[recorte], apartados_contados=invalid[recorte],
        pasa=eff['recuperados']==valid[recorte] and eff['en_cuarentena']==invalid[recorte]
        and eff['candidatos_declarados']==valid[recorte]+invalid[recorte]
        and (not invalid[recorte] or eff['estado']!='completa')))
unchanged = all(q['candidato_original']==original[q['id']] for q in data['cuarentena'])
digest = hashlib.sha256(rawbytes).hexdigest()
api_path = ROOT/'data/private/provisional-001/vision/intentos_gemini/1f11d8e291ad4ad2a5a44600223b515b/respuesta_visual.json'
api_bytes = api_path.read_bytes()
api_original = json.loads(api_bytes)
out = dict(estado='verificacion_focal_de_registro_no_entrega', registro=base.name,
    registro_web_bytes_validos=digest==reg['respuesta_sha256'],
    fuente_api_original_intacta=hashlib.sha256(api_bytes).hexdigest()=='7ccd952e8bd0909627b8988917543d257d220880789568fd521900a7748577af',
    contenido_web_igual_al_original=raw==api_original,
    nota_bytes='El registro web reserializa JSON con su propio SHA; se contrasta contenido además del SHA de la fuente API conservada. No son copias de bytes idénticas.',
    cuarentena_original_intacta=unchanged, comprobaciones=checks,
    api_llamadas=0, limites='No se acepta todavía implementación09 ni se verifica interacción visual con el formulario. Esperar entrega estable para pruebas de código.')
out['correcto']=out['registro_web_bytes_validos'] and out['fuente_api_original_intacta'] and out['contenido_web_igual_al_original'] and unchanged and all(c['pasa'] for c in checks)
(ROOT/'seguimiento/COBERTURA_REAL_239.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out,ensure_ascii=True))
raise SystemExit(0 if out['correcto'] else 1)
