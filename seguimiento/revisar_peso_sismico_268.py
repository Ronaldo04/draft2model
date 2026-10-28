"""Contraste offline: selección por cota de nudo frente a tabla por piso."""
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[1]
names = ['tmp/recorrido_09d1/registro_resultados.json',
         'tmp/recorrido_09d1/masa_pisos_diagnostico.json',
         'tmp/recorrido_09d1/configuracion.json',
         'seguimiento/claude_ruta/resultados_09.py']
raw = {name: (root/name).read_bytes() for name in names}
reg, diag, cfg = (json.loads(raw[n].decode('utf-8-sig')) for n in names[:3])
rows = diag['tablas']['Mass Summary by Story']['filas']
mass = sum(float(row['UX']) for row in rows if row['Story'] in ('N1', 'N2', 'N3', 'N4'))
g = cfg['masa']['gravedad_m_s2']
old = reg['masa']['P_sobre_base_kN']
report = {
    'fecha_utc': datetime.now(timezone.utc).isoformat(),
    'hallazgo': 'P_seleccionado_por_cota_de_nudo_no_equivale_a_masa_por_piso',
    'masa_N1_N4_tabla': mass, 'gravedad_configuracion': g,
    'peso_N1_N4_tabla_kn': mass*g, 'P_registrado_por_z_nudo_kn': old,
    'diferencia_kn': old-mass*g,
    'lectura_diagnostica': diag['lectura'],
    'alcance': 'Contraste aritmético de archivos; no nueva lectura ETABS ni validación normativa.',
    'riesgo': 'El runner describe P de N1–N4 por tabla, pero etapa_reglas toma P_sobre_base_kN calculado filtrando global_xyz de AssembledJointMass. Las coordenadas de esos nudos no representan la distribución por piso con diafragmas rígidos, según el hallazgo de Claude. El denominador de Vdin/Vest queda pendiente de corregir o justificar.',
    'accion': 'Vincular/verificar la tabla nativa por piso al mismo análisis/EDB y usar un criterio de selección explícito. Si no existe evidencia aceptada, abstener la regla afectada. No alterar tolerancia ni recalibrar el modelo para hacer pasar resultados.',
    'sha256_fuentes': {n: hashlib.sha256(b).hexdigest() for n,b in raw.items()},
    'fuentes_estables': all((root/n).read_bytes() == b for n,b in raw.items()),
    'producto_modificado': False, 'goal_completo': False,
}
(root/'seguimiento/HALLAZGO_PESO_SISMICO_268.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({k:report[k] for k in ('hallazgo','peso_N1_N4_tabla_kn','P_registrado_por_z_nudo_kn','diferencia_kn','fuentes_estables')}, ensure_ascii=False))
