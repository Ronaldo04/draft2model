"""Ruta 201 · encargo 07: contrato visual 0.2.0 con tipos semánticos, texto literal y cobertura por recorte.

Distingue cota, carga, propiedad, parámetro, cantidad, texto y resultado impreso; los resultados impresos nunca
se exportan como entradas. Los paquetes y extracciones 0.1.0 siguen siendo válidos. Sin red, claves ni ETABS.
"""
import json
import unittest

from draft2model import gestion_extraccion as g
from draft2model.entrada_vision import ErrorVision, adaptar_respuesta, cargar_paquete, preparar_paquete
from draft2model.extraccion_preliminar import TIPOS_SEMANTICOS, corregir, exportar_revisados, validar_extraccion
from draft2model.proveedor_openai import preparar_peticion
from tests.respuesta_vision_semantica import respuesta
from tests import test_entrada_vision as tev

EV = [{'imagen_id': 'REC0001', 'bbox_imagen_normalizada': [.25, .25, .75, .75]}]
LECTURAS = [
    {'id': 'C1', 'tipo': 'cota', 'valor_propuesto': 0.15, 'unidad': 'm', 'texto_fuente': '.15', 'simbolo': None},
    {'id': 'C2', 'tipo': 'cantidad', 'valor_propuesto': 6, 'unidad': 'no_aplica', 'texto_fuente': '6 ø 1/2"', 'simbolo': None},
    {'id': 'C3', 'tipo': 'carga', 'valor_propuesto': 200, 'unidad': 'kgf/m2', 'texto_fuente': 'S/C: 200 Kg/m2', 'simbolo': 'S/C'},
    {'id': 'C4', 'tipo': 'propiedad', 'valor_propuesto': 210, 'unidad': 'kgf/cm2', 'texto_fuente': "f'c = 210 Kg/cm2", 'simbolo': "f'c"},
    {'id': 'C5', 'tipo': 'parametro', 'valor_propuesto': 0.4, 'unidad': 'adimensional', 'texto_fuente': 'Z=0.40', 'simbolo': 'Z'},
    {'id': 'C6', 'tipo': 'resultado_impreso', 'valor_propuesto': 0.166, 'unidad': 'adimensional', 'texto_fuente': 'Vx=0.166 Peso', 'simbolo': 'Vx'},
    {'id': 'C7', 'tipo': 'texto', 'valor_propuesto': 'GRAVA ARENOSA (GP)', 'unidad': 'no_aplica', 'texto_fuente': 'GRAVA ARENOSA (GP)', 'simbolo': None},
]


def lecturas():
    return [{**c, 'evidencia': EV} for c in LECTURAS]


class VisionSemanticaTests(unittest.TestCase):
    def setUp(self):
        self.base = tev.EntradaVisionTests('test_empty_response_does_not_invent_readings')
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        self.manifest, self.revision, self.crop = self.base.manifest, self.base.revision, self.base.crop

    def pack(self, version='0.2.0'):
        return preparar_paquete(self.manifest, self.revision, [self.crop], version=version)

    def adapt(self, path, data):
        return self.base.adapt(path, data)

    def test_paquete_nuevo_pide_texto_literal_tipos_y_cobertura(self):
        path = self.pack()
        req, sha, _, _ = cargar_paquete(self.manifest, path)
        self.assertEqual(req['version_contrato'], '0.2.0')
        prompt = (path.parent / 'prompt.txt').read_text(encoding='utf-8')
        for palabra in ('resultado_impreso', 'cantidad', 'kgf/cm2', 'cobertura', 'texto_fuente'):
            self.assertIn(palabra, prompt)
        payload, _ = preparar_peticion(self.manifest, path, modelo='fixture-vision', max_tokens=512)
        texto = payload['input'][0]['content'][0]['text']
        self.assertNotIn('omite los campos opcionales texto_fuente', texto)  # incoherencia 0.1 resuelta
        esquema = payload['text']['format']['schema']
        variantes = esquema['properties']['candidatos']['items']['anyOf']
        self.assertTrue(all('texto_fuente' in v['required'] for v in variantes))
        self.assertIn('resultado_impreso', [t for v in variantes for t in v['properties']['tipo']['enum']])
        self.assertIn('cobertura', esquema['required'])

    def test_paquete_heredado_01_conserva_su_contrato(self):
        path = self.pack('0.1.0')
        req, sha, _, _ = cargar_paquete(self.manifest, path)
        payload, _ = preparar_peticion(self.manifest, path, modelo='fixture-vision', max_tokens=512)
        self.assertIn('omite los campos opcionales texto_fuente', payload['input'][0]['content'][0]['text'])
        self.assertEqual(payload['text']['format']['schema']['properties']['candidatos']['items']['properties']['tipo']['enum'],
                         ['cota', 'etiqueta', 'elemento'])
        data = respuesta(req, sha, [{'id': 'C1', 'tipo': 'cota', 'valor_propuesto': 2.6, 'unidad': 'm', 'evidencia': EV}])
        self.assertEqual(self.adapt(path, data)['version_contrato'], '0.1.0')
        data['candidatos'][0]['tipo'] = 'cantidad'
        with self.assertRaises(ErrorVision):
            self.adapt(path, data)

    def test_tipos_semanticos_unidades_y_cobertura_parcial(self):
        path = self.pack()
        req, sha, _, _ = cargar_paquete(self.manifest, path)
        cob = [{'imagen_id': 'REC0001', 'estado': 'parcial', 'observacion': 'cuadro inferior sin leer'}]
        result = self.adapt(path, respuesta(req, sha, lecturas(), cobertura=cob))
        self.assertEqual(result['version_contrato'], '0.2.0')
        self.assertEqual(result['cobertura'], [{'recorte_id': req['imagenes'][1]['recorte_id'],
                                                'estado': 'parcial', 'observacion': 'cuadro inferior sin leer'}])
        self.assertEqual({c['id']: c.get('simbolo') for c in result['candidatos']}['C4'], "f'c")
        check = validar_extraccion(result)
        codigos = {h.codigo for h in check.advertencias}
        self.assertTrue(check.consistente)
        self.assertIn('cobertura_incompleta', codigos)
        self.assertIn('resultado_impreso', codigos)

    def test_rechazos_semanticos(self):
        path = self.pack()
        req, sha, _, _ = cargar_paquete(self.manifest, path)
        casos = {
            'sin texto literal': lambda d: d['candidatos'][0].pop('texto_fuente'),
            'cantidad fraccionaria': lambda d: d['candidatos'][1].update(valor_propuesto=6.5),
            'carga en metros': lambda d: d['candidatos'][2].update(unidad='m'),
            'propiedad sin número': lambda d: d['candidatos'][3].update(valor_propuesto="f'c"),
            'cobertura omitida': lambda d: d.update(cobertura=[]),
            'cobertura repetida': lambda d: d['cobertura'].append(dict(d['cobertura'][0])),
        }
        for nombre, mutar in casos.items():
            data = respuesta(req, sha, lecturas())
            mutar(data)
            with self.subTest(nombre), self.assertRaises(ErrorVision):
                self.adapt(path, data)

    def test_reclasificacion_revisada_y_exportacion_sin_resultados_impresos(self):
        path = self.pack()
        req, sha, _, _ = cargar_paquete(self.manifest, path)
        lect = lecturas()
        lect[1].update(tipo='cota', unidad='desconocida')  # error real del piloto: barras leídas como cota
        data = self.adapt(path, respuesta(req, sha, lect))
        kw = dict(motivo='lectura contrastada', fecha='2026-10-21', revisor_declarado='revisor')
        data = corregir(data, 'C2', estado='revisado', valor_revisado=6, unidad_revisada='no_aplica', tipo_revisado='cantidad', **kw)
        data = corregir(data, 'C6', estado='revisado', valor_revisado=0.166, unidad_revisada='adimensional', **kw)
        data = corregir(data, 'C3', estado='revisado', valor_revisado=200, unidad_revisada='kgf/m2', **kw)
        with self.assertRaises(ValueError):  # una cantidad no admite unidad de longitud
            corregir(data, 'C1', estado='revisado', valor_revisado=6, unidad_revisada='m', tipo_revisado='cantidad', **kw)
        exp = exportar_revisados(data)
        por_id = {c['id']: c for c in exp['candidatos']}
        self.assertEqual((por_id['C2']['tipo'], por_id['C2']['tipo_propuesto'], por_id['C2']['corregido']), ('cantidad', 'cota', True))
        self.assertEqual(por_id['C3']['simbolo'], 'S/C')
        self.assertNotIn('C6', por_id)
        self.assertEqual(exp['excluidos']['resultados_impresos'], ['C6'])
        self.assertIsNone(exp['aprobacion_ingenieria'])

    def test_extraccion_01_no_admite_reclasificar(self):
        path = self.pack('0.1.0')
        req, sha, _, _ = cargar_paquete(self.manifest, path)
        data = self.adapt(path, respuesta(req, sha, [{'id': 'C1', 'tipo': 'cota', 'valor_propuesto': 6, 'unidad': 'desconocida', 'evidencia': EV}]))
        with self.assertRaises(ValueError):
            corregir(data, 'C1', estado='revisado', valor_revisado=6, unidad_revisada='no_aplica', tipo_revisado='cantidad',
                     motivo='m', fecha='2026-10-21', revisor_declarado='r')

    def test_migracion_01_a_02_conserva_lecturas_y_deja_propuesta_pendiente(self):
        path = self.pack('0.1.0')
        req, sha, _, _ = cargar_paquete(self.manifest, path)
        # Importable solo con procedencia de expediente (respuesta local simulada, sin red).
        data = adaptar_respuesta(self.manifest, path, respuesta(req, sha, [{'id': 'C1', 'tipo': 'cota', 'valor_propuesto': 6,
                                 'unidad': 'desconocida', 'evidencia': EV}]), proveedor='local', modelo='fixture')
        entrada = self.base.root / 'extraccion01.json'
        entrada.write_text(json.dumps(data), encoding='utf-8')
        raiz = self.manifest.parent.parent
        padre = g.importar_extraccion(raiz, 'sintetico-vision', entrada)
        prop = {'C1': {'tipo': 'cantidad', 'valor': 6, 'unidad': 'no_aplica', 'motivo': 'número de barras junto a ø'}}
        hija = g.migrar_version(raiz, 'sintetico-vision', padre.identificador, prop, origen='asistente (sin aprobación)')
        c = hija.datos and json.loads((hija.ruta / 'extraccion.json').read_text(encoding='utf-8'))['candidatos'][0]
        self.assertEqual((c['tipo'], c['valor_propuesto'], c['unidad']), ('cota', 6, 'desconocida'))  # lectura intacta
        self.assertEqual(c['clasificacion_propuesta']['tipo'], 'cantidad')
        self.assertEqual(c['revision']['estado'], 'pendiente')
        meta = json.loads((hija.ruta / 'version.json').read_text(encoding='utf-8'))
        self.assertEqual((meta['operacion'], meta['migracion']['aprueba_lecturas'], meta['aprobacion_ingenieria']),
                         ('migracion_semantica', False, None))
        self.assertTrue(g.validar_version(raiz, 'sintetico-vision', hija.identificador).correcta)
        with self.assertRaises(g.ErrorEvidencia):
            g.migrar_version(raiz, 'sintetico-vision', hija.identificador, {}, origen='x')
        with self.assertRaises(g.ErrorEvidencia):
            g.migrar_version(raiz, 'sintetico-vision', padre.identificador, {'C9': prop['C1']}, origen='x')
        r = g.corregir_version(raiz, 'sintetico-vision', hija.identificador, 'C1', estado='revisado', motivo='acepto',
                               fecha='2026-10-21', revisor_declarado='usuario', valor_revisado=6, unidad_revisada='no_aplica',
                               tipo_revisado='cantidad')
        self.assertEqual(r.datos['correccion']['estado'], 'revisado')


class OperacionesEvidenciaTests(unittest.TestCase):
    """Encargo 08: reubicación y lectura manual como versiones nuevas que no aprueban; vigencia de derivados."""

    def setUp(self):
        self.base = tev.EntradaVisionTests('test_empty_response_does_not_invent_readings')
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        self.manifest = self.base.manifest
        path = preparar_paquete(self.manifest, self.base.revision, [self.base.crop])
        req, sha, _, _ = cargar_paquete(self.manifest, path)
        data = adaptar_respuesta(self.manifest, path, respuesta(req, sha, lecturas()), proveedor='local', modelo='fixture')
        entrada = self.base.root / 'extraccion02.json'
        entrada.write_text(json.dumps(data), encoding='utf-8')
        self.raiz = self.manifest.parent.parent
        self.v0 = g.importar_extraccion(self.raiz, 'sintetico-vision', entrada).identificador
        self.kw = dict(motivo='bbox desplazada', fecha='2026-10-21', revisor_declarado='revisor declarado')

    def leer(self, vid):
        caso_dir = g.carpeta_caso(self.raiz, 'sintetico-vision')
        return g.cargar_version(caso_dir, 'sintetico-vision', vid)

    def test_reubicar_conserva_region_anterior_y_no_aprueba(self):
        antes, _, _ = self.leer(self.v0)
        vieja = antes['candidatos'][0]['evidencia'][0]['bbox_normalizada']
        nueva = [vieja[0], vieja[1], vieja[2], round(vieja[3] - 0.02, 6)]
        r = g.reubicar_evidencia(self.raiz, 'sintetico-vision', self.v0, 'C1', bbox=nueva, **self.kw)
        data, meta, problemas = self.leer(r.identificador)
        c = data['candidatos'][0]
        self.assertEqual(problemas, [])
        self.assertEqual(c['evidencia'][0]['bbox_normalizada'], nueva)
        self.assertEqual(c['historial_evidencia'][0]['bbox_anterior'], vieja)
        self.assertEqual(c['revision'], {'estado': 'pendiente', 'historial': []})
        self.assertEqual((c['tipo'], c['valor_propuesto'], c['unidad']), ('cota', 0.15, 'm'))
        self.assertEqual((meta['operacion'], meta['reubicacion']['aprueba_lectura'], meta['aprobacion_ingenieria']),
                         ('reubicacion_evidencia', False, None))
        self.assertEqual(self.leer(self.v0)[0], antes)  # la versión padre no cambia
        exp = exportar_revisados(corregir(data, 'C1', estado='revisado', valor_revisado=0.15, unidad_revisada='m',
                                          motivo='ok', fecha='2026-10-22', revisor_declarado='r'))
        self.assertEqual(exp['candidatos'][0]['historial_evidencia'][0]['bbox_nueva'], nueva)

    def test_reubicar_limites(self):
        vieja = self.leer(self.v0)[0]['candidatos'][0]['evidencia'][0]['bbox_normalizada']
        malos = {'sin cambio': dict(bbox=vieja), 'fuera de página': dict(bbox=[0.5, 0.5, 1.2, 0.6]),
                 'área nula': dict(bbox=[0.5, 0.5, 0.5, 0.6]), 'índice': dict(bbox=[.1, .1, .2, .2], indice=3),
                 'candidato': dict(bbox=[.1, .1, .2, .2], candidato='C99'), 'sin motivo': dict(bbox=[.1, .1, .2, .2], motivo=' ')}
        for nombre, extra in malos.items():
            kw = {**self.kw, **extra}
            cand = kw.pop('candidato', 'C1')
            with self.subTest(nombre), self.assertRaises((g.ErrorEvidencia, ValueError)):
                g.reubicar_evidencia(self.raiz, 'sintetico-vision', self.v0, cand, **kw)
        data = self.leer(self.v0)[0]
        data['candidatos'][0]['historial_evidencia'] = [{'indice': 0, 'bbox_anterior': [.1, .1, .2, .2], 'bbox_nueva': [.1, .1, .3, .3],
                                                        'motivo': 'm', 'fecha': '2026-10-21', 'revisor_declarado': 'r'}]
        self.assertIn('historial_incoherente', {e.codigo for e in validar_extraccion(data).errores})  # no coincide con la vigente

    def test_lectura_manual_procedencia_id_y_pendiente(self):
        r = g.agregar_lectura(self.raiz, 'sintetico-vision', self.v0, tipo='propiedad', valor=35, unidad='kgf/cm2',
                              texto_fuente="f'm = 35 Kg/cm2", simbolo="f'm", archivo_id='L0001', pagina=1,
                              bbox=[.2, .3, .7, .5], **self.kw)
        data, meta, _ = self.leer(r.identificador)
        m = data['candidatos'][-1]
        self.assertEqual(m['id'], 'M001')
        self.assertEqual(m['metodo']['tipo'], 'manual')
        self.assertIn('No proviene de un modelo de IA', m['metodo']['descripcion'])
        self.assertEqual(m['revision']['estado'], 'pendiente')
        self.assertEqual(meta['lectura']['aprueba_lectura'], False)
        r2 = g.agregar_lectura(self.raiz, 'sintetico-vision', r.identificador, tipo='texto', valor='GRAVA', unidad='no_aplica',
                               texto_fuente='GRAVA', archivo_id='L0001', pagina=1, bbox=[.2, .3, .7, .5], **self.kw)
        self.assertEqual(self.leer(r2.identificador)[0]['candidatos'][-1]['id'], 'M002')
        malos = {'sin literal': dict(texto_fuente=' '), 'unidad de otro tipo': dict(unidad='m'),
                 'original inexistente': dict(archivo_id='L0099'), 'página inexistente': dict(pagina=9),
                 'cantidad fraccionaria': dict(tipo='cantidad', valor=6.5, unidad='no_aplica')}
        for nombre, extra in malos.items():
            kw = dict(tipo='propiedad', valor=35, unidad='kgf/cm2', texto_fuente="f'm = 35", archivo_id='L0001', pagina=1,
                      bbox=[.2, .3, .7, .5], **self.kw)
            kw.update(extra)
            with self.subTest(nombre), self.assertRaises((g.ErrorEvidencia, ValueError)):
                g.agregar_lectura(self.raiz, 'sintetico-vision', self.v0, **kw)

    def test_operaciones_exigen_02(self):
        path = preparar_paquete(self.manifest, self.base.revision, [self.base.crop], version='0.1.0')
        req, sha, _, _ = cargar_paquete(self.manifest, path)
        data = adaptar_respuesta(self.manifest, path, respuesta(req, sha, [{'id': 'C1', 'tipo': 'cota', 'valor_propuesto': 2.6,
                                 'unidad': 'm', 'evidencia': EV}]), proveedor='local', modelo='fixture')
        entrada = self.base.root / 'extraccion01b.json'
        entrada.write_text(json.dumps(data), encoding='utf-8')
        v01 = g.importar_extraccion(self.raiz, 'sintetico-vision', entrada).identificador
        with self.assertRaisesRegex(g.ErrorEvidencia, 'rechazada'):
            g.reubicar_evidencia(self.raiz, 'sintetico-vision', v01, 'C1', bbox=[.1, .1, .2, .2], **self.kw)

    def test_exportacion_queda_superada_por_cambio_posterior(self):
        kw = dict(motivo='ok', fecha='2026-10-21', revisor_declarado='r')
        rev = g.corregir_version(self.raiz, 'sintetico-vision', self.v0, 'C1', estado='revisado', valor_revisado=0.15,
                                 unidad_revisada='m', **kw).identificador
        g.exportar_version(self.raiz, 'sintetico-vision', rev)
        self.assertEqual([e['estado'] for e in g.vigencia(self.raiz, 'sintetico-vision', rev)['exportaciones']], ['vigente'])
        g.reubicar_evidencia(self.raiz, 'sintetico-vision', rev, 'C1', bbox=[.3, .3, .6, .6], **self.kw)
        v = g.vigencia(self.raiz, 'sintetico-vision', rev)
        self.assertEqual([(e['estado'], e['candidatos_afectados']) for e in v['exportaciones']], [('superada', ['C1'])])
        self.assertEqual(v['descendientes'][0]['operacion'], 'reubicacion_evidencia')

    def test_servicio_web_reubica_agrega_y_expone_vigencia(self):
        from draft2model.revision_visual import ErrorRevision, RevisionLocal
        app = RevisionLocal(self.raiz)
        v = app.version('sintetico-vision', self.v0)
        base = {'caso': 'sintetico-vision', 'version': self.v0, 'huella': v['huella'], 'expediente_sha256': v['expediente_sha256']}
        r = app.actuar('reubicar', {**base, 'candidato': 'C1', 'indice': 0, 'bbox': [.3, .3, .6, .6], **self.kw})
        self.assertEqual(self.leer(r['id'])[1]['operacion'], 'reubicacion_evidencia')
        r2 = app.actuar('lectura_manual', {**base, 'tipo': 'texto', 'valor': 'GP', 'unidad': 'no_aplica', 'texto_fuente': 'GP',
                                           'archivo_id': 'L0001', 'pagina': 1, 'bbox': [.2, .3, .7, .5], **self.kw})
        self.assertEqual(self.leer(r2['id'])[0]['candidatos'][-1]['metodo']['tipo'], 'manual')
        self.assertEqual(len(app.version('sintetico-vision', self.v0)['vigencia']['descendientes']), 2)
        for op, extra in (('reubicar', {'estado': 'revisado'}), ('lectura_manual', {'aprobado': True})):
            with self.subTest(op), self.assertRaises(ErrorRevision):  # campos ajenos (aprobación/estado) rechazados
                app.actuar(op, {**base, **extra, 'bbox': [.1, .1, .2, .2], **self.kw})


class CuarentenaTests(unittest.TestCase):
    """R235: recuperación explícita; los inválidos se apartan íntegros, sin corregir ni reordenar."""

    def setUp(self):
        self.base = tev.EntradaVisionTests('test_empty_response_does_not_invent_readings')
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        self.path = preparar_paquete(self.base.manifest, self.base.revision, [self.base.crop])
        self.req, self.sha, _, _ = cargar_paquete(self.base.manifest, self.path)

    def respuesta_mixta(self):
        lect = lecturas()
        lect[0] = {**lect[0], 'evidencia': [{'imagen_id': 'REC0001', 'bbox_imagen_normalizada': [.75, .25, .25, .75]}]}  # invertida
        lect[6] = {**lect[6], 'tipo': 'elemento', 'unidad': 'm'}  # unidad incompatible con el tipo
        return respuesta(self.req, self.sha, lect)

    def adaptar(self, data, **kw):
        return adaptar_respuesta(self.base.manifest, self.path, data, proveedor='local', modelo='fixture', modo_prueba=True, **kw)

    def test_sin_decision_explicita_se_rechaza_todo(self):
        with self.assertRaisesRegex(ErrorVision, 'cuarentena explícita'):
            self.adaptar(self.respuesta_mixta())

    def test_cuarentena_aparta_integros_y_conserva_cobertura(self):
        data = self.respuesta_mixta()
        original = json.loads(json.dumps(data))
        r = self.adaptar(data, cuarentena=True)
        self.assertEqual(data, original)  # la respuesta no se toca
        self.assertEqual([c['id'] for c in r['candidatos']], ['C2', 'C3', 'C4', 'C5', 'C6'])
        q = {a['id']: a for a in r['cuarentena']}
        self.assertEqual(set(q), {'C1', 'C7'})
        self.assertEqual(q['C1']['candidato_original']['evidencia'][0]['bbox_imagen_normalizada'], [.75, .25, .25, .75])  # sin reordenar
        self.assertIn('unidad', q['C7']['errores'][0])
        self.assertEqual(r['cobertura'][0]['estado'], 'completa')  # declaración intacta
        codigos = {h.codigo for h in validar_extraccion(r).advertencias}
        self.assertTrue({'candidatos_en_cuarentena', 'cobertura_con_cuarentena'} <= codigos)

    def test_cobertura_efectiva_no_se_eleva(self):  # R236
        r = self.adaptar(self.respuesta_mixta(), cuarentena=True)
        ef = r['cobertura'][0]['efectiva']
        self.assertEqual((r['cobertura'][0]['estado'], ef['estado'], ef['candidatos_declarados'], ef['recuperados'], ef['en_cuarentena']),
                         ('completa', 'parcial', 7, 5, 2))
        for cambio in ({'estado': 'completa'}, {'recuperados': 6}, {'en_cuarentena': -1}):
            mala = json.loads(json.dumps(r))
            mala['cobertura'][0]['efectiva'].update(cambio)
            with self.subTest(cambio=cambio):
                self.assertFalse(validar_extraccion(mala).consistente)
        sin = self.adaptar(respuesta(self.req, self.sha, lecturas()))
        self.assertNotIn('efectiva', sin['cobertura'][0])  # sin cuarentena no se inventa una cobertura derivada

    def test_limites(self):
        dup = self.respuesta_mixta()
        dup['candidatos'][1]['id'] = 'C3'
        with self.assertRaisesRegex(ErrorVision, 'repetidos'):
            self.adaptar(dup, cuarentena=True)
        viejo = preparar_paquete(self.base.manifest, self.base.revision, [self.base.crop], version='0.1.0')
        req, sha, _, _ = cargar_paquete(self.base.manifest, viejo)
        with self.assertRaisesRegex(ErrorVision, '0.2.0'):
            adaptar_respuesta(self.base.manifest, viejo, respuesta(req, sha, [{'id': 'C1', 'tipo': 'cota', 'valor_propuesto': 1,
                              'unidad': 'm', 'evidencia': EV}]), proveedor='l', modelo='f', cuarentena=True)

    def test_esquema_por_tipo_impide_unidades_ajenas(self):
        payload, _ = preparar_peticion(self.base.manifest, self.path, modelo='fixture-vision', max_tokens=512)
        variantes = payload['text']['format']['schema']['properties']['candidatos']['items']['anyOf']
        por_tipo = {t: v['properties']['unidad']['enum'] for v in variantes for t in v['properties']['tipo']['enum']}
        self.assertEqual(por_tipo['elemento'], ['no_aplica'])
        self.assertEqual(por_tipo['texto'], ['no_aplica'])
        self.assertNotIn('m', por_tipo['propiedad'])
        self.assertIn('mm', por_tipo['resultado_impreso'])
        self.assertEqual(set(por_tipo), set(TIPOS_SEMANTICOS))
        self.assertIn('x0 < x1 e y0 < y1', payload['input'][0]['content'][0]['text'])


class AuditoriaEvidenciaTests(unittest.TestCase):
    def setUp(self):
        self.base = tev.EntradaVisionTests('test_empty_response_does_not_invent_readings')
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)

    def extraccion(self, bboxes):
        manifest = json.loads(self.base.manifest.read_text(encoding='utf-8'))
        sha = manifest['archivos'][0]['sha256']
        return {'contrato': 'draft2model.extraccion_preliminar', 'version_contrato': '0.1.0', 'caso': manifest['id'],
                'procedencia': {'tipo': 'expediente', 'descripcion': 'prueba'}, 'alcance': manifest['alcance'],
                'sistema_coordenadas': 'pagina_visible_normalizada',
                'candidatos': [{'id': f'C{i}', 'tipo': 'cota', 'valor_propuesto': 2.6, 'unidad': 'm', 'metodo': {'tipo': 'manual'},
                                'evidencia': [{'archivo_id': 'L0001', 'pagina': 1, 'original_sha256': sha, 'bbox_normalizada': b}]}
                               for i, b in enumerate(bboxes)]}

    def test_region_vacia_frente_a_region_con_texto(self):
        from draft2model.auditoria_evidencia import auditar
        r = auditar(self.base.manifest, self.extraccion([[.2, .3, .7, .5], [.8, .8, .95, .95]]))
        self.assertEqual([c['estado'] for c in r['candidatos']], ['con_trazos', 'vacia'])
        self.assertEqual(r['resumen']['ids_evidencia_vacia'], ['C1'])
        self.assertIsNone(r['aprobacion_ingenieria'])
        self.assertIn('no confirma el valor', r['aviso'])

    def test_original_alterado_no_se_audita(self):
        from draft2model.auditoria_evidencia import auditar
        data = self.extraccion([[.2, .3, .7, .5]])
        original = next(self.base.case.glob('originales/*'))
        original.write_bytes(original.read_bytes() + b'%')
        with self.assertRaisesRegex(ValueError, 'alterado'):
            auditar(self.base.manifest, data)


if __name__ == '__main__':
    unittest.main()
