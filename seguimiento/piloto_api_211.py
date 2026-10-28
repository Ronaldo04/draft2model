"""Coordinación del piloto autorizado: una petición explícita; contador conservador persistente.

Sin argumento prepara y estima localmente. --enviar-openai reserva un uso antes
de llamar al recorrido público, sin transporte inyectado ni reintentos.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from draft2model import proveedor_openai as api
from draft2model.credenciales_locales import cargar


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enviar-openai', action='store_true')
    parser.add_argument('--plan', type=Path, help='Plan nuevo ya preparado y revisado, sin envío previo.')
    args = parser.parse_args()
    expediente = ROOT / 'data/private/provisional-001/expediente.json'
    solicitud = expediente.parent / 'vision/solicitudes/bfda0ef3570049b1bc4dca02f11848c6/solicitud.json'
    modelo = 'gpt-5.4'
    max_tokens = 8192
    if args.plan:
        plan_previo = args.plan.resolve()
        plan_previo.relative_to(expediente.parent)
        previo = json.loads(plan_previo.read_text(encoding='utf-8'))
        if (previo['contrato'] != 'draft2model.plan_vision_openai'
                or previo['configuracion']['modelo'] != modelo
                or previo['configuracion']['max_output_tokens'] not in (8192, 16384)
                or previo['configuracion']['detalle'] != 'high'):
            raise ValueError('Plan ajeno a la configuración acotada.')
        solicitud = expediente.parent / previo['solicitud']
        max_tokens = previo['configuracion']['max_output_tokens']
    payload, resumen = api.preparar_peticion(expediente, solicitud, modelo=modelo, max_tokens=max_tokens, detalle='high')
    # Regla publicada: high <=2500 patches por imagen, multiplicador1.2.
    # Para texto/esquema se reserva un token por byte UTF8 +1000 de margen.
    sin_imagenes = copy.deepcopy(payload)
    n = 0
    for mensaje in sin_imagenes['input']:
        for parte in mensaje['content']:
            if parte['type'] == 'input_image':
                parte['image_url'] = ''
                n += 1
    entrada_max = len(json.dumps(sin_imagenes, ensure_ascii=False).encode('utf-8')) + 1000 + n * 3000
    coste_max = entrada_max * 2.5 / 1_000_000 + max_tokens * 15 / 1_000_000
    if entrada_max >= 272000 or coste_max > 1:
        raise ValueError('Estimación excede la reserva conservadora; no enviar.')
    prueba = {'modelo': modelo, 'imagenes': n, 'max_output_tokens': max_tokens,
              'entrada_cota_conservadora_tokens': entrada_max, 'coste_cota_conservadora_usd': coste_max,
              'reserva_por_intento_usd': 1, 'peticion_sha256': resumen['peticion_sha256'],
              'fuentes_precio': ['https://developers.openai.com/api/docs/models/gpt-5.4',
                                 'https://developers.openai.com/api/docs/guides/images-vision'],
              'fecha_consulta': '2026-10-21', 'llamadas_realizadas_por_esta_preparacion': 0}
    preparado = ROOT / ('seguimiento/PREPARACION_API_211_' + resumen['peticion_sha256'][:12] + '.json')
    preparado.write_text(json.dumps(prueba, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if not args.enviar_openai:
        print(json.dumps(prueba, ensure_ascii=False))
        return
    # Solo se cargan claves dentro del proceso de envío; no se imprimen ni guardan.
    valores = cargar(ROOT / 'data/private/credenciales.local.md')
    clave = valores.get('OPENAI_API_KEY')
    if not clave:
        raise ValueError('Clave OpenAI ausente; no se envió.')
    os.environ['OPENAI_API_KEY'] = clave
    registro = ROOT / 'seguimiento/CONSUMO_API_211.json'
    lock = ROOT / 'seguimiento/CONSUMO_API_211.lock'
    with lock.open('x', encoding='utf-8') as f:
        f.write('Reserva exclusiva. Si el proceso se interrumpe, no repetir sin revisar intentos.\n')
    try:
        datos = json.loads(registro.read_text(encoding='utf-8')) if registro.exists() else {'openai': [], 'gemini': []}
        if len(datos['openai']) >= 5 or sum(x['reserva_usd'] for x in datos['openai']) + 1 > 5:
            raise ValueError('Límite autorizado agotado.')
        # No se salta un intento anterior incierto o fallido mediante otro plan.
        if any(x['estado'] != 'respuesta_pendiente_revision' and not x.get('revision_de_fallo') for x in datos['openai']):
            raise ValueError('Revisar intento anterior antes de autorizar otro envío.')
        for anterior in datos['openai']:
            anterior_plan = json.loads((ROOT / anterior['plan']).read_text(encoding='utf-8'))
            if anterior_plan['configuracion']['peticion_sha256'] == resumen['peticion_sha256']:
                raise ValueError('La misma petición ya se intentó; no repetir.')
        plan = plan_previo if args.plan else api.preparar_plan(expediente, solicitud, modelo=modelo, max_tokens=max_tokens, detalle='high')
        intento = {'numero': len(datos['openai']) + 1, 'modelo': modelo, 'reserva_usd': 1,
                   'cota_coste_usd': coste_max, 'estado': 'reservado_no_reintentar',
                   'fecha_utc': datetime.now(timezone.utc).isoformat(),
                   'plan': str(plan.relative_to(ROOT)), 'plan_sha256': hashlib.sha256(plan.read_bytes()).hexdigest()}
        intento['peticion_sha256'] = resumen['peticion_sha256']
        datos['openai'].append(intento)
        registro.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        resultado = api.ejecutar_plan(expediente, plan, autorizar_envio=True, timeout=180,
                                     importar_automaticamente=False)
        observado = json.loads(resultado.read_text(encoding='utf-8'))
        intento.update(estado=observado['estado'], resultado=str(resultado.relative_to(ROOT)),
                       uso=observado.get('usage'))
        registro.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'estado': intento['estado'], 'resultado': intento['resultado'],
                          'peticiones_openai_reservadas': len(datos['openai']), 'peticiones_gemini': len(datos['gemini']),
                          'uso': intento['uso']}, ensure_ascii=False))
    finally:
        os.environ.pop('OPENAI_API_KEY', None)
        lock.unlink()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Nunca imprimir valores de variables, payloads ni excepciones de terceros.
        print(json.dumps({'estado': 'detenido_revisar_sin_reintento', 'tipo': type(error).__name__}))
        raise SystemExit(2)
