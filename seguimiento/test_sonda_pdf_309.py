"""Comprobación focal del perímetro de la auditoría309; datos sintéticos."""
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
from seguimiento import estado_claude as sonda

with tempfile.TemporaryDirectory() as directory:
    root=Path(directory).resolve()
    control=root/'seguimiento/CLAUDE_ESTADO.json';control.parent.mkdir()
    marker=root/'seguimiento/claude_ruta/MARCADOR_PDF_309.json';marker.parent.mkdir()
    allowed='seguimiento/claude_ruta/diagnostico_pdf_309/revision.md'
    artifact=root/allowed;artifact.parent.mkdir();artifact.write_text('SOLO PRUEBA',encoding='utf-8')
    cfg={'tarea':'pdf_309','modo':'auditoria_pdf_309','estado':'trabajando',
         'archivos':[],'marcador':str(marker.relative_to(root)).replace('\\','/'),
         'prefijos_autorizados':['seguimiento/claude_ruta/diagnostico_pdf_309/']}
    control.write_text(json.dumps(cfg),encoding='utf-8')
    payload={'tarea':309,'estado':'entrega_candidata','archivos_permitidos_sha256':{allowed:hashlib.sha256(artifact.read_bytes()).hexdigest()}}
    with patch.object(sonda,'ROOT',root):
        assert sonda.estado()['estado']=='sin_marcador'
        activity=sonda.estado()
        assert activity['archivos_presentes']==1
        assert activity['actividad_no_prueba_ejecucion'] is True
        assert activity['ultima_modificacion_utc'] is not None
        assert activity['requiere_revision'] is False
        cfg['prefijos_autorizados']=['draft2model/']
        control.write_text(json.dumps(cfg),encoding='utf-8')
        try:sonda.estado();raise AssertionError('Se leyó actividad fuera del perímetro')
        except ValueError:pass
        cfg['prefijos_autorizados']=['seguimiento/claude_ruta/diagnostico_pdf_309/']
        control.write_text(json.dumps(cfg),encoding='utf-8')
        marker.write_text(json.dumps(payload),encoding='utf-8')
        assert sonda.estado()['estado']=='entrega_candidata'
        artifact.write_text('CAMBIO POSTERIOR',encoding='utf-8')
        try:sonda.estado();raise AssertionError('Se aceptó hash alterado')
        except ValueError:pass
        outside=root/'draft2model/ajeno.py';outside.parent.mkdir();outside.write_text('x')
        payload['archivos_permitidos_sha256']={'draft2model/ajeno.py':hashlib.sha256(outside.read_bytes()).hexdigest()}
        marker.write_text(json.dumps(payload),encoding='utf-8')
        try:sonda.estado();raise AssertionError('Se aceptó archivo fuera del encargo')
        except ValueError:pass
        cfg.update(tarea='pdf_310',modo='auditoria_pdf',prefijos_autorizados=['seguimiento/claude_ruta/diagnostico_pdf_310/'])
        control.write_text(json.dumps(cfg),encoding='utf-8')
        payload['tarea']='pdf_309'
        marker.write_text(json.dumps(payload),encoding='utf-8')
        try:sonda.estado();raise AssertionError('Se aceptó marcador de otra tarea')
        except ValueError:pass
        allowed310='seguimiento/claude_ruta/diagnostico_pdf_310/revision.md'
        artifact310=root/allowed310;artifact310.parent.mkdir();artifact310.write_text('NUEVA PRUEBA')
        payload.update(tarea='pdf_310',archivos_permitidos_sha256={allowed310:hashlib.sha256(artifact310.read_bytes()).hexdigest()})
        marker.write_text(json.dumps(payload),encoding='utf-8')
        assert sonda.estado()['estado']=='entrega_candidata'
        cfg.update(tarea='benchmark_311',modo='auditoria_aislada',prefijos_autorizados=['seguimiento/claude_ruta/preparacion_benchmark_311/'])
        control.write_text(json.dumps(cfg),encoding='utf-8')
        allowed311='seguimiento/claude_ruta/preparacion_benchmark_311/revision.md'
        artifact311=root/allowed311;artifact311.parent.mkdir();artifact311.write_text('TERCERA PRUEBA')
        payload.update(tarea='benchmark_311',archivos_permitidos_sha256={allowed311:hashlib.sha256(artifact311.read_bytes()).hexdigest()})
        marker.write_text(json.dumps(payload),encoding='utf-8')
        assert sonda.estado()['estado']=='entrega_candidata'
        cfg['prefijos_autorizados']=['draft2model/']
        control.write_text(json.dumps(cfg),encoding='utf-8')
        try:sonda.estado();raise AssertionError('Se amplió auditoría al producto')
        except ValueError:pass
print('Sonda:10OK (actividad sin marcador, PDF/benchmark, hashes y perímetros).')
