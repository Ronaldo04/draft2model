"""Preparar únicamente el contraste B pendiente, conservando íntegra la entrega315."""
from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1]
src = root/'seguimiento/claude_ruta/ensayo_auto_315'
marker = json.loads((root/'seguimiento/claude_ruta/MARCADOR_AUTO_315.json').read_text(encoding='utf-8'))
for name, digest in marker['archivos_permitidos_sha256'].items():
    assert name.startswith('seguimiento/claude_ruta/ensayo_auto_315/')
    assert hashlib.sha256((root/name).read_bytes()).hexdigest() == digest, name
out = root/'seguimiento/ensayo_codex_auto_316'
out.mkdir(exist_ok=False)
text = (src/'ensayar_auto_315.ps1').read_text(encoding='utf-8-sig')
changes = {
    "foreach($modelo in @('A','B'))": "foreach($modelo in @('B'))",
    '$tolA=$null': '$tolA=0.001 # configuración por defecto observada en315A, no offset inferido',
    "'registro_315.json'": "'registro_316.json'",
    'auto_315_$modelo.edb': 'auto_316_$modelo.edb',
    '# nunca cierra ni toca otras sesiones; no abre EDB reales. Una sola instancia para los modelos A (tolerancia por defecto) y B (5x).':
        '# 316: solo modelo B, instancia nueva. No repite A ni abre EDB reales.',
    "Check ($sap.GetMergeTol([ref]$t0)) 'GetMergeTol'":
        "Check ($sap.GetMergeTol([ref]$t0)) 'GetMergeTol'\n    if([math]::Abs($t0-0.001) -gt 1e-12){throw 'Default distinto de315A; se requiere otra matriz antes de continuar.'}"
}
for before, after in changes.items():
    assert text.count(before) == 1, before
    text = text.replace(before, after)
target = out/'ensayar_B_316.ps1'
target.write_text(text,encoding='utf-8-sig')
(out/'corrida_B').mkdir()
provenance = {'origen':str((src/'ensayar_auto_315.ps1').relative_to(root)),
              'origen_sha256':hashlib.sha256((src/'ensayar_auto_315.ps1').read_bytes()).hexdigest(),
              'derivado_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
              'cambios':list(changes), 'matriz':'Mismo modelo_B sellado315, sin casos nuevos ni ajuste a resultados',
              'justificacion':'315B bloqueó en segunda construcción de instancia reutilizada. Una única ejecución B aislada discrimina ese contexto; causa todavía no probada.',
              'presupuesto':'Una ejecución adicional B, máximo180s; no reintentos automáticos, no repetir A ni piloto.',
              'limites':'Extensión técnica del presupuesto local315, no elusión de cuota ni autorización de nube; cero llamadas remotas.',
              'nativo_ejecutado':False,'goal_completo':False}
(out/'PROCEDENCIA_316.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')
review = {'tarea':'auto_315','hashes_verificados':len(marker['archivos_permitidos_sha256']),
          'aceptacion':'Solo faseA y diagnóstico de fallo; no prueba completa de hipótesis de tolerancia',
          'evidencia_A':'seguimiento/QA_PARCIAL_AUTO_315_CODEX.json',
          'cierre':'CIERRE_REPARACION_315: PID44832 ausente; ApplicationExit no confirmado por IPC terminado; no confundir ausencia con retorno0.',
          'limites':['Mensaje de modal comunicado porClaude, sin captura incorporada al marcador',
                     'Espacio libre suficiente no prueba por sí solo la causa del error de arrays',
                     'No universalizar Lc=0.002m sin contraste de tolerancia/unidades'],
          'producto312':'Conservado sin modificaciones','siguiente':'B aislado por Codex, solo tras revalidar que315 terminó',
          'goal_completo':False}
(root/'seguimiento/REVISION_AUTO_316.json').write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding='utf-8')
print('315:21hashes verificados. B316 preparado; todavía no ejecutado.')
