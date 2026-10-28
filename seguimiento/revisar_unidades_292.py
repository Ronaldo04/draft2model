"""Contraste independiente sobre runtime292 fijo, sin ETABS ni APIs."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'tmp/runtime_qa_292'
sys.path.insert(0, str(RUNTIME))
from draft2model import informe
from draft2model.evaluacion_estructural import evaluar_resultados, validar_reglas
from draft2model.resultados_estructurales import exigir_resultados, huella_declaracion
from tests.test_evaluacion_estructural import fixture, approve


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def evaluate(data, rules):
    return evaluar_resultados(data, rules,
        huella_resultados_esperada=exigir_resultados(data)['huella'],
        huella_reglas_esperada=validar_reglas(rules)['huella'])


def main():
    assert Path(informe.__file__).is_relative_to(RUNTIME)
    manifest = read(RUNTIME / 'RUNTIME_MANIFIESTO.json')
    raw = read(ROOT / 'data/private/pueblo-libre-002/resultados_estructurales/697bb37e9ce64f90ba1ef3e25733c8cc/resultados.json')
    rules_path = ROOT / 'tmp/recorrido_09d3/resultados/reglas_e030.json'
    rules_raw = rules_path.read_bytes()
    rules = json.loads(rules_raw)
    output = evaluate(raw, rules)
    old = read(ROOT / 'tmp/evaluacion_independiente_286.json')
    keys = ('regla_id', 'resultado_id', 'valor_entrada', 'valor_evaluado',
            'limite', 'comparador', 'satisface_regla_configurada')
    assert [{k: e[k] for k in keys} for e in output['evaluaciones']] == [
        {k: e[k] for k in keys} for e in old['evaluaciones']]
    ratios = [e for e in output['evaluaciones'] if e['regla_id'].startswith('VMIN-')]
    assert len(ratios) == 2
    assert all((e['unidad'], e['unidad_resultado']) == ('kN', '1') for e in ratios)
    # Refirmar cada caso evita que una aprobación obsoleta oculte errores de unidad.
    invalids = []
    for unit in ('s', 'kN·m', 1, None):
        r = fixture('reglas_estructurales_sinteticas.json')
        target = next(x for x in r['reglas'] if x['variable'] == 'cortante')
        target['unidad_resultado'] = unit
        approve(r)
        check = validar_reglas(r)
        assert check['aprobacion_vigente'] is True
        assert check['correcta'] is False and any('unidad_resultado' in e for e in check['errores'])
        invalids.append({'unidad': unit, 'rechazada_por_unidad': True})
    data = fixture('resultados_estructurales_sinteticos.json')
    base_rules = fixture('reglas_estructurales_sinteticas.json')
    baseline = evaluate(data, base_rules)
    assert all('unidad_resultado' not in e for e in baseline['evaluaciones'])
    changed = copy.deepcopy(base_rules)
    target = next(x for x in changed['reglas'] if x['variable'] == 'cortante')
    target['formula']['factor'] = 0.01
    target['unidad_resultado'] = '1'
    target['limite'] = 0.8
    approve(changed)
    document = informe.crear_informe(data, changed, {
        'titulo': 'Prueba sintética de unidades; no piloto', 'hipotesis': [],
        'faltantes': ['Fixture sin geometría ni evidencia nativa.'], 'sitio': None})
    html = informe.renderizar_html(document)  # Render completo, sin extraer ni ejecutar fragmentos de código.
    row = next(e for e in document['evaluacion']['evaluaciones'] if e['regla_id'] == target['id'])
    assert f'evaluado: {row["valor_evaluado"]} 1;' in html
    assert rules_path.read_bytes() == rules_raw
    result = {'fecha_utc': datetime.now(timezone.utc).isoformat(),
        'runtime': str(RUNTIME.relative_to(ROOT)), 'huella_fuentes': manifest['huella_fuentes'],
        'evaluaciones_reales': 18, 'valores_y_decisiones_iguales_286': True,
        'cocientes_entrada_kN_salida_1': True, 'rechazos_con_aprobacion_vigente': invalids,
        'compatibilidad_sin_campo': True, 'HTML_sintetico_render_completo': True,
        'sha256_reglas_reales': hashlib.sha256(rules_raw).hexdigest(),
        'limites': 'No revisión normativa profesional ni nueva revalidación de fuentes nativas; informe/PDF real corregido aún pendiente.',
        'api_remota': False, 'etabs_ejecutado': False, 'goal_completo': False}
    (ROOT / 'seguimiento/REVISION_UNIDADES_292.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('18evaluaciones reales idénticas;2cocientes adimensionales;4rechazos con firma vigente;HTML completo y compatibilidad OK.')


if __name__ == '__main__':
    main()
