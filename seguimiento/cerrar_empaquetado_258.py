"""Consolidar evidencia terminal258; conserva el fallo del sandbox."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root/'tmp/validacion_paquete_258'
manifest = json.loads((root/'entregas/AECODE_CANDIDATO_258/MANIFIESTO.json').read_bytes())
installation = json.loads((base/'instalacion/verificacion.json').read_bytes())
http = json.loads((base/'http_host.json').read_bytes())
assert installation['completa'] and len(installation['comprobaciones']) == 6
assert http['estado'] == 'arranque_http_verificado' and http['servidor_propio_cerrado']
record = {'fecha_utc': datetime.now(timezone.utc).isoformat(), 'responsable': 'Codex',
    'paquete': 'entregas/AECODE_CANDIDATO_258', 'archivos': len(manifest['archivos']),
    'huella_fuentes': manifest['huella_fuentes'], 'zip_sha256': manifest['zip_sha256'],
    'pruebas_empaquetado': '8 OK, 1.015s', 'instalacion_aislada': True, 'pasos_instalacion': 6,
    'demo_sintetica_verificada': True, 'arranque_http_host': 200, 'apis_remotas': 0,
    'etabs_ejecutado': False, 'piloto_verificado': False, 'aceptacion_global': False,
    'fallo_previo': 'Socket HTTP bloqueado por sandbox WinError10013; no fallo acreditado del producto. Se conserva registro original y reintento; comprobación host autorizada200.',
    'evidencias': {name: hashlib.sha256((base/name).read_bytes()).hexdigest() for name in
        ('verificacion.json','instalacion/verificacion.json','http_reintento.json','http_host.json')},
    'limites': ['Sin revisión visual del navegador en esta copia', 'Sin prueba real de ETABS ni visión',
                'Fuentes congeladas258; regenerar paquete tras integración de Claude']}
(root/'seguimiento/REVISION_PAQUETE_258.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
coord = {'fecha_utc': datetime.now(timezone.utc).isoformat(),
    'conversacion': 'Comandos CLI geometría', 'proyecto': 'PROYECTO FINAL',
    'carpeta': str(root), 'mensaje': 'Coordinación Codex258', 'enviado_confirmado': True,
    'evidencia': 'Enter; mensaje258 visible en historial y compositor vacío en dos capturas, sin Enviar ahora. Árbol de accesibilidad retuvo valor previo; se usa evidencia visual.',
    'respuesta_258_observada': False, 'lectura_257_observada': True,
    'avance_ajeno_no_aceptado': '09d en preparación; masa_contenido y escalera en integración declarada. Sin marcador nuevo. 09t4 construcción29416OK/cierreTrue en registro, aún sin relectura final.',
    'interrupcion': False, 'sin_sondeo_continuo': True}
(root/'seguimiento/COORDINACION_CLAUDE_258.json').write_text(json.dumps(coord,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
path = root/'seguimiento/CLAUDE_ESTADO.json'
state = json.loads(path.read_bytes())
state['computer_use_suspendido'] = False
state['motivo_ultima_suspension'] = 'Histórico: Escape257. Nueva petición humana retomó coordinación; aviso258 enviado/confirmado sin interrupción. No sondear ventana rutinariamente.'
state['confirmacion_actual'] = 'seguimiento/COORDINACION_CLAUDE_258.json'
state['lectura_encargo_257_observada'] = True
state['propietario_implementacion'] = 'Claude: implementación existente, salvo archivos nuevos independientes de Codex en reservas250/254/258; sin ediciones simultáneas.'
state['reserva_nuevos_archivos_258']['aviso_integracion_enviado'] = True
path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'paquete': 'instalacion_demo_http_verificados', 'piloto': False, 'coordinacion258': 'enviada_confirmada'}))
