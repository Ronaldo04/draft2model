"""Contraste de instrucciones de reanudación con recibos existentes, sin servicios."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ledger = json.loads((ROOT/'seguimiento/CONSUMO_API_211.json').read_text(encoding='utf-8'))
facts = []
for provider in ('openai','gemini'):
    for item in ledger.get(provider, []):
        path = item.get('resultado')
        facts.append(dict(proveedor=provider, numero=item['numero'], estado=item['estado'],
            resultado=path, existe=bool(path and (ROOT/path).is_file())))
assert len(ledger['openai']) == 4 and len(ledger['gemini']) == 2
assert all(f['existe'] for f in facts)
observation = dict(id='R239-01', prioridad='P1_reanudacion_y_cuotas', etapas=['04','06'],
    hallazgo='docs/RETOMAR.md y MATRIZ_REQUISITOS_REFERENCIA.md todavía indican una petición real y plan2 sin envío, y edición normativa no elegida. El ledger registra4OpenAI/2Gemini con recibos existentes; plan2 fue enviado y falló por truncamiento. Usuario eligió RNEvigente y entregó arquitectura. Instrucción obsoleta de reanudar plan2 puede inducir duplicación; no ejecutarla.',
    evidencia='seguimiento/DESFASE_DOCUMENTAL_239.json',
    criterio_aceptacion='Actualizar documentación vigente en09 con fecha/recibos y diferenciar corpus229, implementación08/09 y aplicación real pendiente. Plan2 histórico enviado/fallido, nunca pendiente de primera transmisión; no más llamadas por este hallazgo.')
p = ROOT/'seguimiento/claude_ruta/REVISIONES.json'
r = json.loads(p.read_text(encoding='utf-8'))
if not any(x['id']==observation['id'] for x in r['observaciones']):
    r['observaciones'].append(observation)
    p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
out = dict(estado='desfase_vigente_verificado', observacion=observation, recibos=facts,
    pendientes_reales='Geometría/configuración y recorrido del piloto real; datos materiales no resueltos. No comparación manual aplazada.',
    api_nuevas=0, implementacion_por='Claude encargo09; Codex no modifica docs simultáneamente')
(ROOT/'seguimiento/DESFASE_DOCUMENTAL_239.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('R239 registrado: 6 recibos existentes; documentación de reanudación requiere actualización09, sin nueva API.')
