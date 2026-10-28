"""Lecturas y configuración sintéticas propias: sin expedientes, redes ni ETABS."""
import copy
import json
import unittest

from draft2model import lectura_parametros as lp
from draft2model import modelo_estructural as modelo
from draft2model.parametros_a_configuracion import aplicar_parametros, ErrorParametros


def cantidad(nombre, valor, unidad):
    return {'nombre': nombre, 'valor': valor, 'unidad': unidad, 'evidencias': ['E1']}


def propiedades():
    return [cantidad('E', 24000, 'MPa'), cantidad('poisson', .2, 'adimensional'),
            cantidad('peso_especifico', 2400, 'kgf/m3')]


def seccion(ident='S1', tipo='rectangular', dimensiones=None):
    return {'id': ident, 'nombre': 'Sección sintética ' + ident, 'tipo': tipo, 'material': 'M1',
            'parametros': dimensiones if dimensiones is not None else [cantidad('ancho', 25, 'cm'), cantidad('alto', 400, 'mm')],
            'evidencias': ['E1']}


def configuracion():
    return {'contrato': modelo.CONTRATO, 'version_contrato': '0.5.0', 'id': 'ConfigSintetica', 'caso': 'CasoSintetico',
            'datos_sinteticos': True, 'unidades': {'longitud': 'm', 'fuerza': 'kN', 'tiempo': 's', 'temperatura': 'C'},
            'geometria_origen': {'version_id': 'a'*32, 'sha256_geometria': 'a'*64, 'huella_contenido': 'b'*64},
            'plantilla': None, 'fuentes': [], 'hipotesis': [], 'sitio': None, 'materiales': [], 'secciones': [],
            'puntos': [{'id': 'P1', 'vertice_geometria': 'V1'}, {'id': 'P2', 'vertice_geometria': 'V2'}],
            'frames': [{'id': 'F1', 'inicio': 'P1', 'fin': 'P2', 'tipo': 'columna', 'fuente': 'PENDIENTE'}],
            'asignaciones_muros': [], 'asignaciones_frames': [],
            'asignaciones_superficies': [{'objetivo': 'A1', 'seccion': None, 'fuente': None},
                                         {'objetivo': 'W1', 'seccion': None, 'fuente': None}],
            'vertices_compartidos': [], 'patrones': [], 'cargas': [], 'masa': None, 'apoyos': [],
            'diafragmas': [], 'sin_diafragma': [], 'espectros': [], 'casos': [], 'combinaciones': [], 'analisis': None,
            'faltantes': [], 'conexiones_borde': None, 'malla': {'estrategia': modelo.mp.ESTRATEGIA, 'fuente': None},
            'cortes_nivel': [], 'nodos_derivados': [], 'subdivision_frames': [],
            'liquidos': {'aplicabilidad': 'informacion_insuficiente', 'fuente': None, 'motivo': 'Pendiente sintético.', 'declaraciones': []},
            'revision': {'estado': 'borrador', 'aprobacion': None}}


CATALOGO = {'F1': {'tipo': 'frame'}, 'P1': {'tipo': 'punto'},
            'A1': {'tipo': 'superficie', 'vertical': False}, 'W1': {'tipo': 'superficie', 'vertical': True}}


def respuesta(props=None, secciones=None, asignaciones=None, cargas=None):
    raw = {'contrato': lp.CONTRATO, 'version_contrato': lp.VERSION, 'caso': 'CasoSintetico',
           'evidencias': [{'id': 'E1', 'archivo_id': 'PlanoSintetico', 'pagina': 1,
                          'bbox_normalizada': [.1, .1, .9, .9], 'texto': 'Cuadro sintético de pruebas.'}],
           'materiales': [{'id': 'M1', 'nombre': 'Material sintético', 'clase': 'concreto',
                           'propiedades': props if props is not None else propiedades(), 'evidencias': ['E1']}],
           'secciones': secciones if secciones is not None else [seccion()],
           'asignaciones': asignaciones if asignaciones is not None else [{'elemento': 'F1', 'seccion': 'S1', 'evidencias': ['E1']}],
           'cargas': cargas if cargas is not None else [], 'faltantes': []}
    manifest = {'id': raw['caso'], 'archivos': [{'id': 'PlanoSintetico', 'sha256': 'a'*64}]}
    return lp.validar_respuesta(raw, manifest, {('PlanoSintetico', 1)}, CATALOGO)


def ejecutar(lectura=None, config=None, catalogo=None):
    return aplicar_parametros(config if config is not None else configuracion(),
                              lectura if lectura is not None else respuesta(),
                              elementos_permitidos=catalogo if catalogo is not None else CATALOGO)


def carga(ident='CV1', valor=200, unidad='kgf/m2', elementos=None, direccion='global_z_negativa', tipo='viva'):
    return {'id': ident, 'nombre': 'Carga externa sintética', 'tipo': tipo, 'valor': valor, 'unidad': unidad,
            'alcance': 'Superficie A1 indicada explícitamente.', 'elementos': ['A1'] if elementos is None else elementos,
            'direccion': direccion, 'evidencias': ['E1']}


class ParametrosConfiguracionTests(unittest.TestCase):
    def test_material_seccion_asignacion_fuentes_unidades_sin_mutar(self):
        lectura = respuesta(); cfg = configuracion(); anteriores = copy.deepcopy((lectura, cfg))
        result = ejecutar(lectura, cfg); out = result['configuracion']
        self.assertEqual((lectura, cfg), anteriores)
        material = out['materiales'][0]
        self.assertEqual(material['E_kN_m2'], 24000000)
        self.assertAlmostEqual(material['peso_kN_m3'], 23.53596)
        self.assertEqual(out['secciones'][0]['dimensiones'], {'ancho_m': .25, 'alto_m': .4})
        self.assertEqual(out['asignaciones_frames'][0]['seccion'], 'S1')
        self.assertGreaterEqual(len(result['trazabilidad']), 8)
        self.assertTrue(all(t['evidencias'][0]['original_sha256'] == 'a'*64 for t in result['trazabilidad']))
        self.assertTrue(all('norma' not in s['id'].lower() for s in out['fuentes']))
        self.assertEqual(out['revision'], {'estado': 'borrador', 'aprobacion': None})
        self.assertFalse(result['ejecutable_etabs']); self.assertFalse(result['completa'])
        json.dumps(result, allow_nan=False)

    def test_material_resistencia_sola_no_deriva_ni_crea_stub(self):
        lectura = respuesta(props=[cantidad('fc', 210, 'kgf/cm2')])
        result = ejecutar(lectura)
        self.assertEqual(result['configuracion']['materiales'], [])
        self.assertEqual(result['configuracion']['secciones'], [])
        self.assertEqual(result['configuracion']['asignaciones_frames'], [])
        material = next(f for f in result['faltantes'] if f['coleccion'] == 'materiales')
        self.assertEqual(material['id'], 'M1')
        self.assertEqual(material['dato']['propiedades'][0]['valor'], 210)
        self.assertIn('no derivan', material['motivo'])

    def test_reaplicacion_despues_de_ui_material_sin_nueva_lectura(self):
        lectura = respuesta(props=[cantidad('fc', 210, 'kgf/cm2')])
        first = ejecutar(lectura)
        cfg = copy.deepcopy(first['configuracion'])
        cfg['fuentes'].append({'id': 'DECISION-UI', 'descripcion': 'Fixture de decisión externa explícita.',
                               'referencia': 'fixture', 'sha256': 'b'*64})
        cfg['materiales'].append({'id': 'M1', 'tipo': 'isotropo_lineal', 'E_kN_m2': 21000000,
                                 'poisson': .15, 'peso_kN_m3': 24, 'fuente': 'DECISION-UI'})
        second = ejecutar(lectura, cfg)
        self.assertEqual(second['faltantes'], [])
        self.assertEqual(len(second['configuracion']['secciones']), 1)
        self.assertEqual(len(second['configuracion']['asignaciones_frames']), 1)
        self.assertEqual(second['configuracion']['materiales'], cfg['materiales'])
        self.assertEqual(second['configuracion']['faltantes'], [])
        self.assertEqual(lectura, first['lectura_conservada'])

    def test_idempotencia_reaplicando_la_misma_lectura(self):
        for lectura in [respuesta(), respuesta(props=[cantidad('fm', 60, 'kgf/cm2')]), respuesta(cargas=[carga()])]:
            first = ejecutar(lectura); second = ejecutar(lectura, first['configuracion'])
            self.assertEqual(first['configuracion'], second['configuracion'])
            self.assertEqual(first['faltantes'], second['faltantes'])

    def test_material_existente_no_se_sobrescribe_con_distinto_E(self):
        first = ejecutar(); cfg = first['configuracion']; antes = copy.deepcopy(cfg['materiales'])
        lectura = respuesta(props=[cantidad('E', 30000, 'MPa'), cantidad('poisson', .2, 'adimensional'), cantidad('peso_especifico', 24, 'kN/m3')])
        result = ejecutar(lectura, cfg)
        self.assertEqual(result['configuracion']['materiales'], antes)
        self.assertTrue(result['conflictos'])
        self.assertTrue(any(p['coleccion'] == 'secciones' for p in result['faltantes']))

    def test_material_incompleto_con_E_contradictorio_no_usa_el_existente(self):
        cfg = ejecutar()['configuracion']
        result = ejecutar(respuesta(props=[cantidad('E', 1, 'MPa')]), cfg)
        self.assertTrue(any('contradice' in p['motivo'] for p in result['faltantes']))

    def test_unidad_E_kgf_cm2_y_peso_tf_m3(self):
        result = ejecutar(respuesta(props=[cantidad('E', 200000, 'kgf/cm2'), cantidad('poisson', .2, 'adimensional'), cantidad('peso_especifico', 2.4, 'tf/m3')]))
        m = result['configuracion']['materiales'][0]
        self.assertAlmostEqual(m['E_kN_m2'], 19613300)
        self.assertAlmostEqual(m['peso_kN_m3'], 23.53596)

    def test_poisson_y_unidad_fisica_invalidos_conservan_pendiente(self):
        for props in [[cantidad('E', 24000, 'MPa'), cantidad('poisson', .5, 'adimensional'), cantidad('peso_especifico', 24, 'kN/m3')],
                      [cantidad('E', 24000, 'desconocida'), cantidad('poisson', .2, 'adimensional'), cantidad('peso_especifico', 24, 'kN/m3')]]:
            result = ejecutar(respuesta(props=props))
            self.assertEqual(result['configuracion']['materiales'], [])
            self.assertTrue(result['faltantes'])

    def test_seccion_L_sin_espejos_queda_pendiente_sin_rectangular(self):
        dims = [cantidad('ancho', 50, 'cm'), cantidad('alto', 50, 'cm'),
                cantidad('espesor_ala', 15, 'cm'), cantidad('espesor_alma', 15, 'cm')]
        r = ejecutar(respuesta(secciones=[seccion(tipo='L', dimensiones=dims)]))
        self.assertEqual(r['configuracion']['secciones'], [])
        self.assertTrue(any('espejo' in p['motivo'] for p in r['faltantes']))
        dims += [cantidad('espejo_eje_2', 0, 'adimensional'), cantidad('espejo_eje_3', 1, 'adimensional')]
        r = ejecutar(respuesta(secciones=[seccion(tipo='L', dimensiones=dims)]))
        sec = r['configuracion']['secciones'][0]
        self.assertEqual(sec['tipo'], modelo.SECCION_L)
        self.assertIs(sec['dimensiones']['espejo_eje_2'], False)
        self.assertIs(sec['dimensiones']['espejo_eje_3'], True)
        self.assertNotIn('insercion_frames', r['configuracion'])

    def test_aligerados_completos_conservan_su_tipo_y_orientacion(self):
        comunes = [cantidad('alto_total', 20, 'cm'), cantidad('capa', 5, 'cm'),
                   cantidad('ancho_nervio_superior', 10, 'cm'), cantidad('ancho_nervio_inferior', 8, 'cm'),
                   cantidad('angulo_ejes_locales_grados', 0, 'grados')]
        casos = [('losa_aligerada_unidireccional', modelo.TIPOS_ALIGERADOS[0],
                  [cantidad('separacion', 40, 'cm'), cantidad('direccion_nervios', 2, 'adimensional')]),
                 ('losa_aligerada_bidireccional', modelo.TIPOS_ALIGERADOS[1],
                  [cantidad('separacion_1', 40, 'cm'), cantidad('separacion_2', 50, 'cm')])]
        for tipo, esperado, extra in casos:
            lectura = respuesta(secciones=[seccion(tipo=tipo, dimensiones=comunes + extra)],
                                asignaciones=[{'elemento': 'A1', 'seccion': 'S1', 'evidencias': ['E1']}])
            r = ejecutar(lectura); sec = r['configuracion']['secciones'][0]
            self.assertEqual(sec['tipo'], esperado)
            self.assertEqual(set(sec['dimensiones']), set(modelo.DIM_ALIGERADOS[esperado].split()))
            self.assertEqual(r['configuracion']['asignaciones_superficies'][0]['seccion'], 'S1')
            self.assertFalse(any('seccion.dimensiones' in e for e in r['validacion']['errores']))
            lectura['datos']['secciones'][0]['parametros'].pop()
            r = ejecutar(lectura)
            self.assertEqual(r['configuracion']['secciones'], [])
            self.assertTrue(r['faltantes'])

    def test_muro_y_maciza_no_intercambian_forma_ni_orientacion(self):
        for tipo, elemento, esperado in [('muro', 'W1', 'shell_muro'), ('losa_maciza', 'A1', 'shell_losa_homogenea')]:
            lectura = respuesta(secciones=[seccion(tipo=tipo, dimensiones=[cantidad('espesor', 15, 'cm')])],
                                asignaciones=[{'elemento': elemento, 'seccion': 'S1', 'evidencias': ['E1']}])
            r = ejecutar(lectura)
            self.assertEqual(r['configuracion']['secciones'][0]['tipo'], esperado)
            self.assertTrue(any(a['id'] == elemento for a in r['aplicados']))
            lectura['datos']['asignaciones'][0]['elemento'] = 'W1' if elemento == 'A1' else 'A1'
            r = ejecutar(lectura)
            self.assertTrue(any('incompatible' in f['motivo'] for f in r['faltantes']))

    def test_asignaciones_contradictorias_no_eligen_ultima_fila(self):
        sections = [seccion(), seccion('S2')]
        asignaciones = [{'elemento': 'F1', 'seccion': s, 'evidencias': ['E1']} for s in ('S1', 'S2')]
        r = ejecutar(respuesta(secciones=sections, asignaciones=asignaciones))
        self.assertEqual(r['configuracion']['asignaciones_frames'], [])
        self.assertEqual(len(r['conflictos']), 2)

    def test_asignacion_existente_a_otra_seccion_no_se_sobrescribe(self):
        cfg = ejecutar()['configuracion']
        lectura = respuesta(secciones=[seccion('S2')], asignaciones=[{'elemento': 'F1', 'seccion': 'S2', 'evidencias': ['E1']}])
        r = ejecutar(lectura, cfg)
        self.assertEqual(r['configuracion']['asignaciones_frames'], cfg['asignaciones_frames'])
        self.assertTrue(r['conflictos'])

    def test_asignacion_ajena_y_sin_orientacion_se_conservan(self):
        lectura = respuesta(asignaciones=[{'elemento': 'AJENO', 'seccion': 'S1', 'evidencias': ['E1']}])
        r = ejecutar(lectura)
        self.assertEqual(r['configuracion']['asignaciones_frames'], [])
        self.assertTrue(any('ajeno' in f['motivo'] for f in r['faltantes']))
        lectura = respuesta(secciones=[seccion(tipo='muro', dimensiones=[cantidad('espesor', 15, 'cm')])],
                            asignaciones=[{'elemento': 'W1', 'seccion': 'S1', 'evidencias': ['E1']}])
        r = ejecutar(lectura, catalogo=set(CATALOGO))
        self.assertTrue(any('orientación' in f['motivo'] for f in r['faltantes']))

    def test_seccion_existente_con_datos_distintos_bloquea_asignacion(self):
        cfg = ejecutar()['configuracion']; cfg['asignaciones_frames'] = []
        lectura = respuesta(secciones=[seccion(dimensiones=[cantidad('ancho', 30, 'cm'), cantidad('alto', 40, 'cm')])])
        r = ejecutar(lectura, cfg)
        self.assertEqual(r['configuracion']['secciones'], cfg['secciones'])
        self.assertEqual(r['configuracion']['asignaciones_frames'], [])
        self.assertTrue(r['conflictos'])

    def test_carga_completa_patron_dedicado_sin_peso_propio_ni_masa(self):
        r = ejecutar(respuesta(cargas=[carga()]))
        cfg = r['configuracion']; c = cfg['cargas'][0]
        self.assertAlmostEqual(c['componentes'][2], -1.96133)
        self.assertEqual(c['objetivo'], 'A1'); self.assertEqual(c['unidad'], 'kN/m2')
        self.assertEqual(cfg['patrones'][0]['multiplicador_peso_propio'], 0)
        self.assertIsNone(cfg['masa']); self.assertEqual(cfg['casos'], [])
        self.assertTrue(any(p['coleccion'] == 'politica_peso_masa' for p in r['faltantes']))
        self.assertTrue(any('aislamiento' in h['descripcion'] for h in cfg['hipotesis']))

    def test_cargas_por_punto_frame_y_superficie_unidades_compatibles(self):
        for unidad, elemento, esperado in [('tf', 'P1', 'kN'), ('kgf/m', 'F1', 'kN/m'), ('kN/m2', 'W1', 'kN/m2')]:
            r = ejecutar(respuesta(cargas=[carga(unidad=unidad, elementos=[elemento])]))
            self.assertEqual(r['configuracion']['cargas'][0]['unidad'], esperado)

    def test_carga_incompleta_ajena_o_incompatible_no_aplica_a_todo(self):
        cargas = [carga(elementos=[]), carga(direccion='desconocida'), carga(elementos=['AJENO']),
                  carga(unidad='kN/m', elementos=['A1']), carga(elementos=['A1', 'F1']), carga(tipo='agua')]
        for row in cargas:
            r = ejecutar(respuesta(cargas=[row]))
            self.assertEqual(r['configuracion']['cargas'], [])
            self.assertEqual(r['configuracion']['patrones'], [])
            self.assertTrue(any(f['coleccion'] == 'cargas' for f in r['faltantes']))

    def test_alcance_general_no_aplica_aunque_haya_lista(self):
        row = carga(); row['alcance'] = 'Carga general de todo el edificio.'
        r = ejecutar(respuesta(cargas=[row]))
        self.assertEqual(r['configuracion']['cargas'], [])
        self.assertTrue(any('Alcance general' in f['motivo'] for f in r['faltantes']))

    def test_material_desconocido_y_forma_otro_permanecen_pendientes(self):
        lectura = respuesta(); lectura['datos']['secciones'][0]['material'] = 'desconocido'
        r = ejecutar(lectura)
        self.assertEqual(r['configuracion']['secciones'], [])
        lectura = respuesta(secciones=[seccion(tipo='otro')]); r = ejecutar(lectura)
        self.assertEqual(r['configuracion']['secciones'], [])
        self.assertTrue(any('no se sustituye' in f['motivo'] for f in r['faltantes']))

    def test_catalogo_no_incorpora_geometria_frame_ausente(self):
        catalogo = {**CATALOGO, 'F2': {'tipo': 'frame'}}
        lectura = respuesta(asignaciones=[{'elemento': 'F2', 'seccion': 'S1', 'evidencias': ['E1']}],
                            cargas=[carga(elementos=['F2'], unidad='kN/m')])
        r = ejecutar(lectura, catalogo=catalogo)
        self.assertEqual(r['configuracion']['asignaciones_frames'], [])
        self.assertEqual(r['configuracion']['cargas'], [])

    def test_conflicto_de_carga_es_atomico_y_no_sobrescribe(self):
        cfg = ejecutar(respuesta(cargas=[carga()]))['configuracion']
        anterior = copy.deepcopy(cfg['cargas'])
        r = ejecutar(respuesta(cargas=[carga(valor=250)]), cfg)
        self.assertEqual(r['configuracion']['cargas'], anterior)
        self.assertTrue(r['conflictos'])

    def test_naturaleza_revision_y_faltantes_previos_preservados(self):
        cfg = configuracion(); cfg['revision'] = {'estado': 'aprobado', 'aprobacion': {'fixture': 'solo sintético'}}
        cfg['faltantes'] = [{'ruta': '$.sitio', 'motivo': 'Dato externo pendiente.', 'fuente': 'EXTERNA'}]
        lectura = respuesta(); antes = copy.deepcopy(lectura)
        r = ejecutar(lectura, cfg)
        self.assertTrue(r['configuracion']['datos_sinteticos'])
        self.assertEqual(r['revision_configuracion_previa'], cfg['revision'])
        self.assertEqual(r['configuracion']['revision'], {'estado': 'borrador', 'aprobacion': None})
        self.assertIn(cfg['faltantes'][0], r['configuracion']['faltantes'])
        self.assertEqual(lectura, antes); self.assertEqual(r['lectura_conservada'], antes)
        cfg['datos_sinteticos'] = False; lectura['simulado'] = True
        with self.assertRaises(ErrorParametros): ejecutar(lectura, cfg)

    def test_contrato_sin_sha_o_fuente_fuera_tabla_se_rechaza(self):
        for cambio in ['sha', 'refs', 'caso']:
            lectura = respuesta()
            if cambio == 'sha': del lectura['datos']['evidencias'][0]['original_sha256']
            elif cambio == 'refs': lectura['datos']['materiales'][0]['propiedades'][0]['evidencias'] = ['AUSENTE']
            else: lectura['datos']['caso'] = 'OtroCaso'
            with self.assertRaises(ErrorParametros): ejecutar(lectura)
        with self.assertRaises(ErrorParametros): ejecutar({'datos': respuesta()['datos']})

    def test_propiedades_duplicadas_se_conservan_pendientes(self):
        r = ejecutar(respuesta(props=propiedades() + [cantidad('E', 30000, 'MPa')]))
        self.assertEqual(r['configuracion']['materiales'], [])
        self.assertTrue(any('repetido' in f['motivo'] for f in r['faltantes']))


if __name__ == '__main__':
    unittest.main()
