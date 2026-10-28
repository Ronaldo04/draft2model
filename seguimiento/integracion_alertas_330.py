"""Comprueba el recorrido real de importación/consulta con un PDF sintético."""
import hashlib
import json
from pathlib import Path
from tests.test_revision_visual import CasoVisual

root = Path(__file__).resolve().parents[1]
fixture = CasoVisual()
fixture.setUp()
try:
    c = fixture.extraction['candidatos'][0]
    c.update(texto_fuente='260 cm', metodo={'tipo': 'vision'})
    version = fixture.imported()
    path = fixture.manifest.parent / 'extracciones' / version / 'extraccion.json'
    before = path.read_bytes()
    record = fixture.app.version('demo', version)
    validation = record['comprobacion']['validacion']
    codes = {a['codigo'] for a in validation['advertencias']}
    assert {'valor_sin_correspondencia_literal', 'unidad_sin_respaldo_literal'} <= codes
    assert record['datos']['candidatos'][0]['valor_propuesto'] == 2.6
    assert record['datos']['candidatos'][0].get('revision', {}).get('estado', 'pendiente') == 'pendiente'
    assert before == path.read_bytes()
    evidence = {'tipo': 'integracion_local_sintetica', 'resultado': 'correcto',
                'ruta_publica': '/api/version', 'proveedor_llamado': False,
                'datos_modificados_por_consulta': False, 'aviso_no_es_aprobacion': True,
                'sha256_extraccion': hashlib.sha256(before).hexdigest(),
                'advertencias': validation['advertencias']}
    (root / 'seguimiento/INTEGRACION_ALERTAS_330.json').write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Importación, consulta y avisos correctos; lectura pendiente y archivo intacto.')
finally:
    fixture.doCleanups()
