"""Preparar un ensayo estático SINTÉTICO; nunca conecta con ETABS."""
import argparse
import json
from pathlib import Path

from draft2model.ingreso import file_hash
from draft2model.modelo_estructural import huella_configuracion
from draft2model.operaciones_etabs import generar_plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raiz', type=Path, required=True)
    parser.add_argument('--configuracion-base', type=Path, required=True)
    parser.add_argument('--plantilla', type=Path, required=True)
    parser.add_argument('--salida', type=Path, required=True)
    parser.add_argument('--gravedad-programa', type=float, required=True,
                        help='Gravedad del programa comprobada; no se supone un valor universal')
    args = parser.parse_args(argv)
    data = json.loads(args.configuracion_base.read_bytes())
    if data.get('datos_sinteticos') is not True:
        raise ValueError('Este ejemplo solo admite datos sintéticos.')
    destination = args.salida.resolve()
    if destination.exists():
        raise ValueError('La salida debe ser nueva.')
    # Se define otro experimento; no se afirma haber aplicado los casos retirados.
    data['id'] = 'ensayo-estatico-etabs-sintetico'
    data['casos'] = [c for c in data['casos'] if c['tipo'] == 'estatico_lineal']
    if len(data['casos']) != 1:
        raise ValueError('Se requiere exactamente un caso estático de la fixture.')
    case = data['casos'][0]['id']
    data['espectros'] = []
    data['combinaciones'] = [{'id': 'COMB1', 'tipo': 'lineal',
        'casos': [{'caso': case, 'factor': 1.2}], 'fuente': 'F-SINTETICA'}]
    data['analisis'] = {'casos_ejecutar': [case], 'combinaciones_resultados': ['COMB1'], 'fuente': 'F-SINTETICA'}
    data['masa']['gravedad_m_s2'] = args.gravedad_programa
    data['plantilla']['sha256'] = file_hash(args.plantilla)
    data['plantilla']['representacion'] = 'Plantilla vacía ETABS para ensayo de software estático sintético.'
    data['revision'] = {'estado': 'aprobado', 'aprobacion': {
        'revisor_declarado': 'Operador SINTÉTICO de prueba de software', 'fecha': '2026-10-17',
        'huella_configuracion': huella_configuracion(data),
        'alcance': 'Fixture estática inventada para verificar construcción API; sin aprobación de ingeniería.',
        'identidad_revisor': 'declarada_no_verificada'}}
    plan = generar_plan(args.raiz, data, destino_guardado=str(destination / 'modelo_construido.edb'),
        tipo_shell_muro='ShellThin', gravedad_programa_m_s2=args.gravedad_programa)
    destination.mkdir(parents=True, exist_ok=False)
    for name, value in [('configuracion.json', data), ('plan.json', plan.datos)]:
        with (destination / name).open('x', encoding='utf-8') as output:
            json.dump(value, output, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({'preparado': True, 'datos_sinteticos': True, 'ejecuto_etabs': False,
                      'operaciones': len(plan.operaciones), 'huella_plan': plan.huella}))


if __name__ == '__main__':
    main()
