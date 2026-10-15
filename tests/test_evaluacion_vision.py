"""Evaluación sintética: precisión condicionada, omisiones y revisión separadas."""
import copy
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from draft2model.evaluacion_vision import ErrorEvaluacion, evaluar_lecturas, main
from draft2model.extraccion_preliminar import huella

ROOT = Path(__file__).resolve().parents[1]


def fixtures():
    read = lambda name: json.loads((ROOT / 'examples' / name).read_text(encoding='utf-8'))
    return (read('referencia_vision_sintetica.json'), read('extraccion_sintetica.json'),
            read('correspondencias_vision_sinteticas.json'))


def refreshed(ref, ext, mapping):
    mapping['huella_referencia'], mapping['huella_extraccion'] = huella(ref), huella(ext)
    return evaluar_lecturas(ref, ext, mapping)


class EvaluacionVisionTests(unittest.TestCase):
    def test_expected_counts_and_denominators(self):
        r = evaluar_lecturas(*fixtures())
        self.assertEqual(r['metricas']['cobertura'], {'numerador': 4, 'denominador': 5, 'proporcion': 0.8})
        self.assertEqual(r['metricas']['exactitud_valor_legible_emparejado']['proporcion'], 1)
        self.assertEqual(r['metricas']['exactitud_unidad_emparejada']['proporcion'], 0.75)
        self.assertEqual(r['metricas']['lecturas_completas_sobre_legibles'], {'numerador': 2, 'denominador': 4, 'proporcion': 0.5})
        self.assertEqual(r['metricas']['omisiones'], ['R006'])
        self.assertEqual(r['evidencia_confirmada_sobre_emitidos']['proporcion'], 0.8)
        self.assertEqual(r['sin_respaldo_declarados'], ['C005'])
        self.assertIsNone(r['aprobacion_ingenieria'])
        json.dumps(r, allow_nan=False)

    def test_corrections_and_rejections_do_not_improve_original_score(self):
        ref, ext, mapping = fixtures()
        r = evaluar_lecturas(ref, ext, mapping)
        # C003 fue corregido a cm, C005 rechazado: ambos permanecen en la evaluación original.
        self.assertEqual(r['candidatos_emitidos'], 5)
        self.assertEqual(r['metricas']['unidades_propuestas_desconocidas'], 2)
        ext['candidatos'][2].pop('revision')
        ext['candidatos'][4].pop('revision')
        self.assertEqual(refreshed(ref, ext, mapping)['metricas'], r['metricas'])

    def test_unknown_units_and_null_are_not_filled(self):
        r = evaluar_lecturas(*fixtures())
        self.assertEqual(r['metricas']['unidades_referencia_desconocidas'], 1)
        self.assertEqual(r['metricas']['abstenciones_correctas_sobre_ilegibles']['numerador'], 1)

    def test_unit_conversion_is_not_applied(self):
        ref, ext, mapping = fixtures()
        ext['candidatos'][0]['valor_propuesto'] = 260
        ext['candidatos'][0]['unidad'] = 'cm'
        r = refreshed(ref, ext, mapping)
        self.assertEqual(r['metricas']['exactitud_valor_legible_emparejado']['numerador'], 2)
        self.assertEqual(r['metricas']['lecturas_completas_sobre_legibles']['numerador'], 1)

    def test_omission_not_hidden_by_conditional_accuracy(self):
        ref, ext, mapping = fixtures()
        mapping['pares'] = mapping['pares'][1:]
        r = refreshed(ref, ext, mapping)
        self.assertEqual(r['metricas']['exactitud_valor_legible_emparejado']['proporcion'], 1)
        self.assertEqual(r['metricas']['cobertura']['numerador'], 3)
        self.assertIn('R001', r['metricas']['omisiones'])
        self.assertEqual(r['sin_clasificar'], ['C001'])

    def test_unmatched_candidate_not_automatically_false_positive(self):
        ref, ext, mapping = fixtures()
        mapping['sin_respaldo'] = []
        r = refreshed(ref, ext, mapping)
        self.assertEqual(r['sin_clasificar'], ['C005'])
        self.assertEqual(r['sin_respaldo_declarados'], [])

    def test_declared_duplicate_does_not_increase_coverage(self):
        ref, ext, mapping = fixtures()
        extra = copy.deepcopy(ext['candidatos'][0])
        extra['id'] = 'C006'
        ext['candidatos'].append(extra)
        pair = copy.deepcopy(mapping['pares'][0])
        pair.update(candidato_id='C006', principal=False)
        mapping['pares'].append(pair)
        r = refreshed(ref, ext, mapping)
        self.assertEqual(r['metricas']['cobertura']['numerador'], 4)
        self.assertEqual(r['duplicados_declarados'], ['C006'])

    def test_ambiguous_observation_excluded_from_scoring(self):
        ref, ext, mapping = fixtures()
        ref['observaciones'][0]['legibilidad'] = 'ambigua'
        r = refreshed(ref, ext, mapping)
        self.assertEqual(r['metricas']['ambiguas_excluidas'], 1)
        self.assertEqual(r['metricas']['cobertura']['denominador'], 4)

    def test_absent_types_have_null_ratio_not_perfect_score(self):
        ref, ext, mapping = fixtures()
        ref['observaciones'] = [o for o in ref['observaciones'] if o['tipo'] != 'elemento']
        r = refreshed(ref, ext, mapping)
        self.assertIsNone(r['por_tipo']['elemento']['lecturas_completas_sobre_legibles']['proporcion'])

    def test_wrong_evidence_decreases_complete_readings(self):
        ref, ext, mapping = fixtures()
        mapping['pares'][0]['evidencia_correcta'] = False
        r = refreshed(ref, ext, mapping)
        self.assertEqual(r['metricas']['lecturas_completas_sobre_legibles']['numerador'], 1)

    def test_stale_mapping_rejected(self):
        ref, ext, mapping = fixtures()
        ext['candidatos'][0]['valor_propuesto'] = 2.7
        with self.assertRaisesRegex(ErrorEvaluacion, 'desactualizadas'):
            evaluar_lecturas(ref, ext, mapping)

    def test_case_scope_and_provenance_mismatch_rejected(self):
        for field, value in [('caso', 'otro'), ('alcance', {'estado': 'otro'}),
                             ('procedencia', {'tipo': 'expediente', 'descripcion': 'Otro origen'})]:
            with self.subTest(field=field):
                ref, ext, mapping = fixtures()
                ext[field] = value
                with self.assertRaises(ErrorEvaluacion):
                    refreshed(ref, ext, mapping)

    def test_false_evidence_identity_and_disjoint_bbox_rejected(self):
        for field, value in [('pagina', 2), ('original_sha256', '0'*64), ('bbox_normalizada', [0.9,0.9,1,1])]:
            ref, ext, mapping = fixtures()
            ext['candidatos'][0]['evidencia'][0][field] = value
            with self.assertRaises(ErrorEvaluacion):
                refreshed(ref, ext, mapping)

    def test_invalid_and_duplicate_matches_rejected(self):
        for change in ('duplicate', 'unknown', 'no_primary', 'bad_index', 'non_bool', 'double_classification'):
            ref, ext, mapping = fixtures()
            if change == 'duplicate': mapping['pares'].append(copy.deepcopy(mapping['pares'][0]))
            if change == 'unknown': mapping['pares'][0]['candidato_id'] = 'absent'
            if change == 'no_primary': mapping['pares'][0]['principal'] = False
            if change == 'bad_index': mapping['pares'][0]['indice_evidencia_candidato'] = True
            if change == 'non_bool': mapping['pares'][0]['evidencia_correcta'] = 'true'
            if change == 'double_classification': mapping['sin_respaldo'].append('C001')
            with self.subTest(change=change), self.assertRaises(ErrorEvaluacion):
                refreshed(ref, ext, mapping)

    def test_reference_review_and_legibility_required(self):
        for change in ('unreviewed', 'empty_reviewer', 'date', 'unknown_legibility', 'illegible_value'):
            ref, ext, mapping = fixtures()
            if change == 'unreviewed': ref['revision']['estado'] = 'pendiente'
            if change == 'empty_reviewer': ref['revision']['revisor_declarado'] = ''
            if change == 'date': ref['revision']['fecha'] = '15/10/2026'
            if change == 'unknown_legibility': ref['observaciones'][0]['legibilidad'] = 'buena'
            if change == 'illegible_value': ref['observaciones'][0]['legibilidad'] = 'ilegible'
            with self.subTest(change=change), self.assertRaises(ErrorEvaluacion):
                refreshed(ref, ext, mapping)

    def test_input_immutability_and_outside_mvp_preserved(self):
        ref, ext, mapping = fixtures()
        ref['alcance'] = ext['alcance'] = {'estado': 'fuera_mvp_declarado', 'uso': 'pruebas_procesamiento'}
        mapping['huella_referencia'], mapping['huella_extraccion'] = huella(ref), huella(ext)
        before = copy.deepcopy((ref, ext, mapping))
        result = evaluar_lecturas(ref, ext, mapping)
        result['alcance']['estado'] = 'modificado'
        self.assertEqual((ref, ext, mapping), before)

    def test_cli_writes_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            out = Path(tmp) / 'report.json'
            args = ['--referencia', str(ROOT/'examples/referencia_vision_sintetica.json'), '--extraccion',
                    str(ROOT/'examples/extraccion_sintetica.json'), '--correspondencias',
                    str(ROOT/'examples/correspondencias_vision_sinteticas.json'), '--salida', str(out)]
            self.assertEqual(main(args), 0)
            first = out.read_bytes()
            self.assertEqual(main(args), 1)
            self.assertEqual(out.read_bytes(), first)

    def test_cli_bad_json_creates_no_report(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            inp, out = Path(tmp)/'bad.json', Path(tmp)/'report.json'
            inp.write_text('{"a":1,"a":2}',encoding='utf-8')
            self.assertEqual(main(['--referencia',str(inp),'--extraccion',str(inp),'--correspondencias',str(inp),'--salida',str(out)]),1)
            self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
