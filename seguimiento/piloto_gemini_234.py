"""Un envío focal autorizado a Gemini gratuito. Sin argumento solo prepara localmente."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tmp/revision_codex_233'))
from draft2model import proveedor_openai as api
from draft2model.credenciales_locales import cargar


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enviar-gemini', action='store_true')
    args = parser.parse_args()
    expediente = ROOT / 'data/private/provisional-001/expediente.json'
    solicitud = expediente.parent / 'vision/solicitudes/777e5eb009c649b1a6a3db21cfc6876d/solicitud.json'
    opciones = dict(modelo='gemini-3.8-flash', proveedor='gemini', max_tokens=16384, detalle='auto')
    payload, resumen = api.preparar_peticion(expediente, solicitud, **opciones)
    prueba = dict(resumen, fecha_utc=datetime.now(timezone.utc).isoformat(),
                  nivel='Free, sin facturación: confirmado expresamente por el usuario',
                  fuentes=['https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash',
                           'https://ai.google.dev/gemini-api/docs/pricing'],
                  finalidad='revision_extraccion_planos', reintentos=0,
                  herramientas_externas=False, facturacion_habilitada_por_codex=False)
    (ROOT / 'seguimiento/PREPARACION_GEMINI_234.json').write_text(
        json.dumps(prueba, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if not args.enviar_gemini:
        print(json.dumps({'estado': 'preparado_sin_red', 'modelo': opciones['modelo'],
                          'peticion_sha256': resumen['peticion_sha256']}))
        return
    registro = ROOT / 'seguimiento/CONSUMO_API_211.json'
    lock = ROOT / 'seguimiento/CONSUMO_API_211.lock'
    with lock.open('x', encoding='utf-8') as f:
        f.write('Reserva exclusiva Gemini. No repetir si se interrumpe el proceso.\n')
    try:
        datos = json.loads(registro.read_text(encoding='utf-8'))
        if len(datos['gemini']) >= 5:
            raise ValueError('Límite Gemini agotado.')
        if any(x['estado'] != 'respuesta_pendiente_revision' and not x.get('revision_de_fallo')
               for x in datos['gemini']):
            raise ValueError('Hay intento previo incierto o fallido sin revisión.')
        if any(x.get('peticion_sha256') == resumen['peticion_sha256'] for x in datos['gemini']):
            raise ValueError('Petición ya intentada.')
        clave = cargar(ROOT / 'data/private/credenciales.local.md').get('GEMINI_API_KEY')
        if not clave:
            raise ValueError('Clave ausente; no se envió.')
        os.environ['GEMINI_API_KEY'] = clave
        plan = api.preparar_plan(expediente, solicitud, **opciones)
        intento = dict(numero=len(datos['gemini']) + 1, modelo=opciones['modelo'],
                       reserva_usd=0, nivel_confirmado='Free sin facturación',
                       estado='reservado_no_reintentar', fecha_utc=datetime.now(timezone.utc).isoformat(),
                       plan=str(plan.relative_to(ROOT)),
                       plan_sha256=hashlib.sha256(plan.read_bytes()).hexdigest(),
                       peticion_sha256=resumen['peticion_sha256'])
        datos['gemini'].append(intento)
        registro.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        resultado = api.ejecutar_plan(expediente, plan, autorizar_envio=True, timeout=180,
                                     importar_automaticamente=False)
        observado = json.loads(resultado.read_text(encoding='utf-8'))
        intento.update(estado=observado['estado'], resultado=str(resultado.relative_to(ROOT)),
                       uso=observado.get('usage'))
        registro.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'estado': intento['estado'], 'resultado': intento['resultado'],
                          'peticiones_gemini': len(datos['gemini']),
                          'peticiones_openai': len(datos['openai']), 'uso': intento['uso']}))
    finally:
        os.environ.pop('GEMINI_API_KEY', None)
        lock.unlink()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'estado': 'detenido_revisar_sin_reintento', 'tipo': type(error).__name__}))
        raise SystemExit(2)
