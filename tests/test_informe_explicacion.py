"""Núcleo del informe: campos opcionales contexto_verificado/explicacion, compatibilidad y rechazos."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from draft2model.fuentes import huella_corpus
from draft2model.informe import crear_informe, exportar_informe, renderizar_html, validar_informe, aprobar_informe
from draft2model.resultados_estructurales import huella_declaracion

EXAMPLES = Path(__file__).resolve().parents[1]/'examples'
FRAG = 'Deriva: relación desplazamiento/altura.'


def fixture(name):
    return json.loads((EXAMPLES/name).read_text(encoding='utf-8'))


class InformeExplicacionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); self.folder = Path(tmp.name)
        self.resultados = fixture('resultados_estructurales_sinteticos.json')
        self.reglas = fixture('reglas_estructurales_sinteticas.json')
        source = self.folder/'fuente.txt'; source.write_text('Fuente SINTETICA. '+FRAG, encoding='utf-8')
        corpus = {'contrato': 'draft2model.corpus', 'version': '0.1.0', 'datos_sinteticos': True,
                  'documentos': [{'id': 'D1', 'titulo': 'Fuente sintética', 'edicion': 'prueba', 'archivo': 'fuente.txt',
                                  'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}],
                  'fragmentos': [{'id': 'F1', 'documento': 'D1', 'pagina': 3, 'apartado': 'Deriva', 'texto': FRAG}],
                  'aprobacion': None}
        corpus['aprobacion'] = {'huella': huella_corpus(corpus), 'revisor_declarado': 'Prueba', 'fecha': '2026-10-18',
                                'alcance': 'Software'}
        self.corpus = self.folder/'corpus.json'; self.corpus.write_text(json.dumps(corpus), encoding='utf-8')
        self.huella_corpus = huella_corpus(corpus)
        self.contexto = {'titulo': 'Informe sintético con contexto', 'hipotesis': ['Datos fabricados.'],
                         'faltantes': ['Revisión real.'], 'sitio': None}
        self.cv = {'evaluacion': {'id': 'a'*32, 'sha256_salida': 'b'*64,
                                  'fuentes': {'reglas': {'id': 'c'*32, 'huella': huella_declaracion(self.reglas)}, 'resultado': None}},
                   'recuperacion': {'id': 'd'*32, 'sha256_salida': 'e'*64,
                                    'fuentes': {'corpus': {'id': 'f'*32, 'huella': self.huella_corpus}, 'resultado': None}},
                   'sitio': None}
        self.citas = [{'fragmento_id': 'F1', 'texto': FRAG}]

    def explicacion(self, **cambios):
        base = {'trabajo': '1'*32, 'estado_trabajo': 'completado_llm_verificado', 'huella_salida': '2'*64,
                'modo': 'llm_verificado', 'causa': None, 'generacion_llm_real': False,
                'modo_transporte': 'transporte_prueba_python', 'modelo_declarado': 'modelo-fixture',
                'declaraciones': [{'id': 'D1', 'texto': 'El cortante V1 en la base es 100.0 kN.', 'indicadores': ['R:V1'],
                                   'cifras': [{'indicador': 'R:V1', 'valor': 100.0, 'unidad': 'kN'}],
                                   'citas': [{'fragmento_id': 'F1', 'texto': FRAG}],
                                   'estado': 'propuesta_pendiente_revision_humana'}],
                'abstenciones': [{'tema': 'sitio', 'motivo': 'Sin consulta de sitio.'}],
                'limites_verificables': ['No se verifica el sentido técnico del texto libre.'],
                'estado_revision': 'propuesta_pendiente_revision_humana'}
        base.update(cambios)
        return base

    def crear(self, **kw):
        return crear_informe(self.resultados, self.reglas, self.contexto, corpus=self.corpus, citas=self.citas,
                             contexto_verificado=kw.pop('cv', self.cv), explicacion=kw.pop('explicacion', self.explicacion()), **kw)

    def test_compatibilidad_sin_campos_opcionales(self):
        informe = crear_informe(self.resultados, self.reglas, self.contexto)
        self.assertNotIn('contexto_verificado', informe); self.assertNotIn('explicacion', informe)
        self.assertEqual(set(informe['huellas']), {'resultados', 'reglas', 'evaluacion'})
        self.assertTrue(validar_informe(informe))

    def test_explicacion_llm_valida_render_export_y_aprobacion(self):
        informe = self.crear()
        self.assertTrue(validar_informe(informe)); self.assertIn('explicacion', informe['huellas'])
        html = renderizar_html(informe)
        self.assertIn('TRANSPORTE DE PRUEBA, NO ES UNA LLAMADA REAL', html); self.assertIn('PENDIENTE DE REVISIÓN HUMANA', html)
        self.assertNotIn('LLM REAL)', html)
        out = exportar_informe(informe, self.folder/'paquete', corpus=self.corpus)
        self.assertTrue((out/'informe.pdf').read_bytes().startswith(b'%PDF'))
        aprobado = aprobar_informe(informe, revisor_declarado='Revisor declarado', fecha='2026-10-18', motivo='Revisión documental')
        self.assertEqual(aprobado['explicacion'], informe['explicacion']); self.assertTrue(validar_informe(aprobado))

    def test_contingencia_identificada(self):
        ex = self.explicacion(modo='contingencia_deterministica', causa='clave_ausente', declaraciones=None,
                              estado_trabajo='contingencia')
        html = renderizar_html(self.crear(explicacion=ex))
        self.assertIn('CONTINGENCIA DETERMINÍSTICA (clave_ausente)', html); self.assertIn('NO ES GENERACIÓN LLM', html)
        for cambios in ({'generacion_llm_real': True}, {'declaraciones': []}, {'causa': None}):
            with self.subTest(cambios=cambios), self.assertRaises(ValueError):
                self.crear(explicacion={**ex, **cambios})

    def test_rechaza_explicacion_no_sustentada_o_aprobada(self):
        decl = self.explicacion()['declaraciones'][0]
        malas = [{**decl, 'cifras': [{'indicador': 'R:V1', 'valor': 101.0, 'unidad': 'kN'}]},
                 {**decl, 'cifras': [{'indicador': 'R:V1', 'valor': 100.0, 'unidad': 'N'}]},
                 {**decl, 'citas': [{'fragmento_id': 'F1', 'texto': 'inventado'}]},
                 {**decl, 'indicadores': ['R:INEXISTENTE'], 'cifras': []},
                 {**decl, 'estado': 'aprobado'},
                 {**decl, 'indicadores': [], 'cifras': [], 'citas': []}]
        for mala in malas:
            with self.subTest(mala=mala), self.assertRaises(ValueError):
                self.crear(explicacion=self.explicacion(declaraciones=[mala]))
        with self.assertRaises(ValueError):
            crear_informe(self.resultados, self.reglas, self.contexto, explicacion=self.explicacion())
        informe = self.crear(); informe['explicacion']['declaraciones'][0]['texto'] = 'Texto cambiado tras crear.'
        with self.assertRaises(ValueError):
            validar_informe(informe)  # huella de explicación

    def test_referencias_incoherentes_con_contenido(self):
        cv = copy.deepcopy(self.cv); cv['evaluacion']['fuentes']['reglas']['huella'] = '0'*64
        with self.assertRaises(ValueError):
            self.crear(cv=cv)
        cv = copy.deepcopy(self.cv); cv['sitio'] = {'id': '9'*32, 'sha256_salida': '9'*64, 'fuentes': {'sitio': {'huella': '9'*64}}}
        with self.assertRaises(ValueError):
            self.crear(cv=cv)  # sitio referenciado pero el contexto no lo trae
        with self.assertRaises(ValueError):
            crear_informe(self.resultados, None, self.contexto, contexto_verificado=self.cv)


    def test_sitio_limite_es_franja_incierta_sin_asignacion(self):
        from draft2model.revision_explicaciones import ServicioExplicaciones
        sitio = {'contrato': 'draft2model.sitio', 'version': '0.1.0', 'ubicacion': {'longitud': 0.0, 'latitud': 0.0, 'crs': 'EPSG:4326'},
                 'estado': 'limite', 'zonas': [{'id': 'Z1', 'etiqueta': 'Zona sintética', 'posicion': 'limite'}],
                 'fuente': {'titulo': 'Capa SINTÉTICA', 'edicion': 'prueba', 'referencia': 'fixture'}, 'fecha_fuente': '2026-10-18',
                 'precision_m': 10, 'datos_sinteticos': True, 'sha256_capa': 'a'*64, 'huella_capa': 'b'*64,
                 'parametros_geotecnicos': None, 'capacidad_portante': None, 'aviso': 'Cobertura referencial.'}
        html = renderizar_html(crear_informe(self.resultados, self.reglas, {**self.contexto, 'sitio': sitio}))
        self.assertIn('FRANJA INCIERTA', html); self.assertIn('NO confirma pertenencia', html)
        self.assertIn('no es asignación territorial', html); self.assertIn('DECLARACIÓN CONTEXTUAL', html)
        det = ServicioExplicaciones._deterministico('c', 'r', 'h', self.resultados, {'sitio': {'salida': sitio}})
        self.assertIn({'tema': 'sitio', 'motivo': 'Estado de sitio limite: no se afirma pertenencia a una zona ni parámetros de suelo.'}, det['abstenciones'])
        self.assertIsNone(det['sitio']['parametros_geotecnicos'])

if __name__ == '__main__':
    unittest.main()
