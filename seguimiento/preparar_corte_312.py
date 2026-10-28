"""Preparar fuente congelada312 sin atribuirle una validación todavía pendiente."""
from pathlib import Path
import json
import hashlib
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
headers = {
    'README.md': ('**Corte de validación:', '**Corte312, 24 de octubre de 2026.** La base306 pasó1424pruebas Python y36de interfaz. Este corte añade la incrustación de la fuente del pie PDF y una prueba de regresión:67pruebas de informes correctas; las ocho páginas del informe técnico conservan texto y píxeles en MuPDF. La validación global de este ZIP se identifica por su huella en el archivo VALIDACION.json junto al paquete; no se atribuye automáticamente la suite306 al código nuevo. La descarga real comprobada pertenece a303 y la apertura de interfaz a306. El benchmark humano y la aceptación global siguen pendientes.'),
    'docs/ENTREGA_AECODE.md': ('Corte documental24', 'Corte312, 24 de octubre de2026: se conserva la base306 y se integra la fuente del pie PDF sin cambiar los datos estructurales. Hay67pruebas focales de informes correctas; el resumen VALIDACION.json junto al ZIP indica el resultado global de esa huella. No confundir las pruebas históricas306 con la validación de este corte. El benchmark humano y la aceptación global permanecen abiertos.'),
    'docs/GUIA_REPRODUCIBLE.md': ('Corte24de octubre', 'Corte312,24de octubre de2026: instalación offline303 comprobada y entorno reutilizable con lock/wheels idénticos. La base306 pasó1424Python y36interfaz;312 integra la fuente del pie PDF y una prueba adicional. Consultar VALIDACION.json junto al ZIP para conocer las comprobaciones de su huella exacta. Esta guía distingue demo, dobles, ensayos nativos sintéticos y piloto real; el benchmark humano y la aceptación global siguen abiertos. [RETOMAR](RETOMAR.md) corresponde al seguimiento del repositorio de desarrollo.'),
    'docs/CONTEXTO_PROYECTO.md': ('Actualizado:24de octubre', 'Actualizado:24de octubre de2026, corte312. La base306 pasó1424Python y36pruebas de interfaz.312 integra la fuente del pie PDF y una prueba adicional;67pruebas focales de informes correctas. El resumen junto al ZIP informa la validación de su huella exacta. Piloto construido y analizado; extracción sin benchmark humano completo, masa no_coherente y diez comparaciones no satisfactorias conservadas. La aceptación global sigue abierta; no se ha demostrado generalización a cualquier construcción. [RETOMAR](RETOMAR.md) conserva el seguimiento interno.')
}
for name, (prefix, replacement) in headers.items():
    path = root / name
    lines = path.read_text(encoding='utf-8').splitlines()
    indices = [i for i, line in enumerate(lines) if line.startswith(prefix)]
    assert len(indices) == 1, (name, indices)
    lines[indices[0]] = replacement
    if name.endswith('GUIA_REPRODUCIBLE.md'):
        lines = [line.replace('QA real de la integración301, compatibilidad entre renderizadores PDF y validación global final',
                             'Contenido técnico conservado. Contraste309/310 con MuPDF, Poppler y Windows.Data.Pdf; fuente del pie incrustada en312. No acredita todos los visores ni aprobación de ingeniería') for line in lines]
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

path = root / 'docs/METODO_TRABAJO_EFICIENTE.md'
text = path.read_text(encoding='utf-8')
text = text.replace('Heartbeat coordinar-entregas-de-claude activo cada3 minutos por petición del usuario.',
                    'Se configuró heartbeat cada3minutos por petición del usuario; actualmente permanece pausado. El registro de seguimiento indica su estado vigente; no se promete supervisión durante pausas o límites.')
path.write_text(text, encoding='utf-8')

marker = root / 'seguimiento/claude_ruta/MARCADOR_BENCHMARK_311.json'
data = json.loads(marker.read_text(encoding='utf-8'))
for name, digest in data['archivos_permitidos_sha256'].items():
    assert name.startswith('seguimiento/claude_ruta/preparacion_benchmark_311/')
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name
assert json.loads((root/'tmp/inventario_codex_312.json').read_text(encoding='utf-8')) == json.loads(
    (root/'seguimiento/claude_ruta/preparacion_benchmark_311/INVENTARIO_COHORTES_311.json').read_text(encoding='utf-8'))
review = {'tarea':'benchmark_311', 'archivos_sha_verificados':len(data['archivos_permitidos_sha256']),
          'pruebas_focales': '9 unittest correctas, ejecutadas por Codex',
          'inventario': 'Regenerado localmente por Codex; igualdad JSON exacta con entregaClaude',
          'aceptacion':'Preparación aceptada; no se han calculado métricas ni validado entradas humanas todavía',
          'limites':['No autentica al revisor declarado', 'No acredita precisión ni generalización',
                     'Las sugerencias quedan pendientes y no usan valores para elegir correspondencias'],
          'goal_completo':False}
(root/'seguimiento/REVISION_BENCHMARK_312.json').write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding='utf-8')
control_path = root/'seguimiento/CLAUDE_ESTADO.json'
control = json.loads(control_path.read_text(encoding='utf-8'))
assert control['tarea'] == 'benchmark_311'
control.update(estado='revisado', revision='seguimiento/REVISION_BENCHMARK_312.json',
               siguiente_dependencia='Referencia humana efectiva y correspondencias revisadas; no fabricar puntajes')
control_path.write_text(json.dumps(control,ensure_ascii=False,indent=2),encoding='utf-8')
subprocess.run([sys.executable,'scripts/crear_paquete_aecode.py','--salida','entregas/AECODE_ENTREGA_312',
                '--wheels','tmp/validacion_distribucion_306/fuentes/wheels'],cwd=root,check=True)
print('Fuente312 congelada. Preparación311 revisada; benchmark humano pendiente.')
