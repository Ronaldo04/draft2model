"""Registro idempotente de revisión y envío observado; no modifica producto."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent
p = root / 'claude_ruta/REVISIONES.json'
r = json.loads(p.read_text(encoding='utf-8-sig'))
for ident in ('d3de8e4b14fa4ccbbbe7931f0f983c34', 'c54f77043471420fac2dc2a30cee5749'):
    if ident not in r['revisadas']:
        r['revisadas'].append(ident)
items = [
    ('R236-01', 'P1_normativa', 'Cortante estático devuelve V utilizable bajo mínimo aunque advierte C/R<.11; además acepta TL<TP en rama T<=TP. Prueba independiente congelada: esperado mínimo49.5kN frente1.40625kN.', 'Validar dominio en todas las ramas; distinguir bruto/aplicado y mínimo o bloqueo explícito; probar consumidores.'),
    ('R236-02', 'P2_cobertura', 'Recuperación real59válidos/12cuarentena funciona con advertencias; conserva cobertura original completa en2recortes afectados y falta indicador web. No se afirma ocultación total.', 'Conservar declaración original separada de cobertura efectiva del lote recuperado y exponer cantidades/descartes en web.'),
    ('R237-01', 'coordinacion', 'Encargo09 observado en historial de Claude, compositor vacío y lista de tareas09/lectura iniciada. No prueba entrega. Auditoría orientación237 independiente en curso.', 'Continuar secuencia09 automáticamente; pruebas focales y piloto real, sin API ni duplicar auditoría; no cierre sintético.'),
]
for ident, prioridad, hallazgo, criterio in items:
    if not any(x['id'] == ident for x in r['observaciones']):
        r['observaciones'].append(dict(id=ident, prioridad=prioridad, etapas=['04', '06'], hallazgo=hallazgo,
            evidencia='seguimiento/REVISION_NORMATIVA_RECUPERACION_236.json' if ident.startswith('R236') else 'seguimiento/COORDINACION_CLAUDE_237.json', criterio_aceptacion=criterio))
p.write_text(json.dumps(r, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
c = dict(encargo='seguimiento/claude_ruta/09_INTEGRACION_PILOTO.md', estado='envio_observado_y_lectura_iniciada',
    ventana=3082800, conversacion='Comandos CLI geometría', proyecto='PROYECTO FINAL',
    evidencia_visual='Mensaje09 visible completo en historial; compositor vacío; lista Leer encargo09/R236 y Reading commission09. No prueba calidad ni finalización.',
    observacion='Tras Enter la captura inmediata mantuvo texto; intento CtrlEnter reportó entrada manual. Reobservación posterior confirmó envío, por tanto no reenviar.')
(root/'COORDINACION_CLAUDE_237.json').write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p = root/'CLAUDE_ESTADO.json'
s = json.loads(p.read_text(encoding='utf-8-sig'))
s.update(encargo_actual=c['encargo'],confirmacion_actual='seguimiento/COORDINACION_CLAUDE_237.json')
p.write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Revision236 y coordinacion237 registradas; objetivo sigue incompleto.')
