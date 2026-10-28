"""Merger puro con registros sintéticos reproducibles del contrato353."""
import copy
import hashlib
import json
import unittest

from draft2model import contratos as c
from draft2model import digitizacion_calibrada as dc
from draft2model import lectura_contornos as lc
from draft2model.contornos_a_geometria import incorporar_contornos
from tests.test_lectura_contornos import caso


def sellar(registro):
    raw = {k: v for k, v in registro.items() if k not in {'huella_version', 'sha256_registro', 'vigente'}}
    raw['huella_version'] = lc.huella(raw)
    return {**raw, 'sha256_registro': hashlib.sha256(lc.canonico(raw)+b'\n').hexdigest(), 'vigente': True}


def fixture(geo=None, raw=None, contexto=None, limites=None):
    g, r, manifest, ctx = caso()
    geo = copy.deepcopy(geo if geo is not None else g)
    raw = copy.deepcopy(raw if raw is not None else r)
    if contexto is None:
        ctx['geometria'].update(huella_contenido=c.huella_contenido(geo), sha256_geometria_canonica=lc.huella(geo),
                                unidad_longitud=geo['unidad_longitud'], datos_sinteticos=geo['procedencia']['tipo'] == 'sintetico')
        ctx['planos'][0]['unidad_longitud'] = geo['unidad_longitud']
        ctx['puntos_resueltos'] = [v['id'] for v in geo['vertices']]
        ctx['planos'][0]['puntos_resueltos'] = [v['id'] for v in geo['vertices'] if v['z'] == 0]
        ctx['catalogo_vertices'] = copy.deepcopy(geo['vertices'])
    else:
        ctx = copy.deepcopy(contexto)
    lectura = lc.validar_respuesta(raw, manifest, {('L1', 1)}, ctx)
    dibujos = {}
    for d in lectura['datos']['dibujos']:
        plano, fuente = d['plano'], d['fuente']; cg = ctx['geometria']
        usados = {v['punto_resuelto'] for group in ('anclas', 'controles') for v in d[group]}
        registro_puntos = {}; catalogo = []
        for v in geo['vertices']:
            if v['id'] not in usados:
                continue
            ident = v['id']; coords = [float(v[k]) for k in plano['ejes']]
            hr = lc.huella({'caso': geo['id'], 'geometria_id': cg['version_id'], 'sha256_geometria': cg['sha256_geometria'],
                           'huella_geometria': cg['huella_contenido'], 'vertice_id': ident, 'coordenadas': coords,
                           'unidad_longitud': plano['unidad_longitud'], 'plano': plano, 'procedencia': v['procedencia']})
            registro_puntos[ident] = {'coordenadas': coords, 'unidad_longitud': plano['unidad_longitud'], 'plano': copy.deepcopy(plano),
                                      'fuente': copy.deepcopy(fuente), 'huella_resolucion': hr,
                                      'referencias': v['procedencia'].get('referencias') or ['descriptor_geometrico:'+cg['version_id']]}
            catalogo.append({'id': ident, 'coordenadas': coords, 'huella_resolucion': hr, 'utilizable_en_fuente': True})
        prop = {'contrato': dc.CONTRATO, 'version': dc.VERSION, 'id': d['id'], 'fuente': copy.deepcopy(fuente), 'plano': copy.deepcopy(plano),
                'limites': {'residuo_ajuste_max_m': .02, 'error_control_max_m': .02, 'incertidumbre_max_m': .1,
                            'localizacion_uv': .001, 'referencia_m': .001, 'condicion_max': 50,
                            'escala_min_m_por_uv': .1, 'escala_max_m_por_uv': 500, 'coordenada_abs_max_m': 10000}}
        if limites:
            prop['limites'].update(limites)
        for group in ('anclas', 'controles', 'puntos'):
            prop[group] = [{**{k: copy.deepcopy(v) for k, v in row.items() if k != 'evidencias'},
                            'fuente': copy.deepcopy(fuente), 'plano_id': plano['id']} for row in d[group]]
        resultado = dc.calibrar_digitizacion(prop, fuente_vigente=fuente, puntos_resueltos=registro_puntos)
        registro = {'contrato': 'draft2model.revision_digitizacion', 'version': '0.1.0', 'id': 'd'*32, 'etapa': 'calculada',
                    'caso': geo['id'], 'expediente_sha256': 'c'*64, 'datos_sinteticos': cg['datos_sinteticos'],
                    'geometria_origen': {k: cg[k] for k in ('version_id', 'sha256_geometria', 'huella_contenido', 'unidad_longitud')},
                    'fuente_vigente': fuente, 'fuente_solicitud':copy.deepcopy(fuente),'evidencia_fuente':{'preview_sha256':'7'*64},
                    'plano': plano, 'propuesta': prop, 'catalogo_referencias': catalogo,
                    'resultado': resultado, 'sha256_resultado': hashlib.sha256(lc.canonico(resultado)+b'\n').hexdigest(),
                    'hashes_entradas': {'original_sha256': fuente['sha256'], 'sha256_geometria': cg['sha256_geometria'],
                                       'geometria_id': cg['version_id'], 'huella_geometria': cg['huella_contenido'],
                                       'expediente_sha256': 'c'*64,'preview_sha256':'7'*64,'huella_catalogo_referencias':lc.huella(catalogo),
                                       'huella_entrada_modulo': resultado['huella_entrada']},
                    'hashes_codigo': {name: 'e'*64 for name in ('revision_digitizacion.py', 'digitizacion_calibrada.py', 'revision_superposicion.py')},
                    'resumen': {'exactitud_documental_acreditada': False}, 'pendientes': [],
                    'revision': {'estado': 'borrador', 'aprobacion': None}, 'aprueba_ingenieria': False,
                    'disponible_para_modelado': False, 'ejecuta_etabs': False}
        dibujos[d['id']] = copy.deepcopy(sellar(registro))
    return geo, lectura, dibujos


class ContornosGeometriaTests(unittest.TestCase):
    def test_cara_nueva_vano_y_frame_con_origen_preservado(self):
        g, lectura, registros = fixture(); antes = copy.deepcopy((g, lectura, registros))
        result = incorporar_contornos(g, lectura, registros)
        self.assertTrue(result['aplicado'], result['conflictos'])
        self.assertTrue(result['validacion']['consistente'])
        self.assertEqual(len(result['geometria']['vertices']), 11)
        self.assertEqual(result['agregados']['superficies'], ['CARA'])
        self.assertEqual(result['geometria']['aberturas'][0]['superficie'], 'CARA')
        self.assertEqual(result['frames_propuestos'][0]['puntos'], ['B', 'N3'])
        self.assertEqual(result['geometria']['vertices'][:3], g['vertices'])
        self.assertIn(g['faltantes'][0], result['geometria']['faltantes'])
        self.assertTrue(any('Faltante nuevo' in p['descripcion'] for p in result['faltantes']))
        self.assertFalse(result['completo']); self.assertFalse(result['ejecutable_etabs'])
        self.assertFalse(result['validacion']['disponible_para_modelado'])
        self.assertEqual(result['geometria']['revision'], {'estado': 'borrador', 'aprobacion': None})
        self.assertEqual((g, lectura, registros), antes)
        n1 = next(v for v in result['geometria']['vertices'] if v['id'] == 'N1')
        self.assertTrue({'COTA_A', 'COTA_B', 'COTA_C'} <= set(n1['procedencia']['referencias']))
        json.dumps(result, allow_nan=False)

    def test_colision_rechaza_transaccion_y_conserva_existentes_exactos(self):
        raw = caso()[1]; raw['elementos'][0]['id'] = 'BASE'; raw['aberturas'][0]['host'] = 'BASE'
        g, lectura, registros = fixture(raw=raw); result = incorporar_contornos(g, lectura, registros)
        self.assertFalse(result['aplicado']); self.assertTrue(result['conflictos'])
        for group in ('vertices', 'superficies', 'aberturas'):
            self.assertEqual(result['geometria'][group], g[group])
        self.assertEqual(result['frames_propuestos'], [])

    def test_colision_de_frame_preexistente_en_contexto(self):
        ctx = caso()[3]; ctx['frames'] = ['VIGA']
        g, lectura, registros = fixture(contexto=ctx)
        self.assertFalse(incorporar_contornos(g, lectura, registros)['aplicado'])

    def test_source_plano_huella_y_propuesta_ajenos_aunque_rehash(self):
        cambios = [lambda r:r['fuente_vigente'].update(sha256='0'*64),
                   lambda r:r['fuente_vigente'].update(pagina=2),
                   lambda r:r['fuente_vigente'].update(bbox_pagina=[.1, .1, .9, .9]),
                   lambda r:r['plano'].update(valor_constante=3),
                   lambda r:r['geometria_origen'].update(version_id='0'*32),
                   lambda r:r['propuesta'].update(id='OTRA'),
                   lambda r:r['propuesta']['puntos'][0].update(uv_local=[.3, .4]),
                   lambda r:r.update(datos_sinteticos=False)]
        for change in cambios:
            g, lectura, registros = fixture(); change(registros['D1']); registros['D1'] = sellar(registros['D1'])
            result = incorporar_contornos(g, lectura, registros)
            self.assertFalse(result['aplicado']); self.assertTrue(result['conflictos'])
        g, lectura, registros = fixture(); registros['D1']['huella_version'] = '0'*64
        self.assertFalse(incorporar_contornos(g, lectura, registros)['aplicado'])

    def test_resultado_fisico_alterado_rehash_no_basta(self):
        g, lectura, registros = fixture(); registros['D1']['resultado']['puntos'][0]['coordenadas_m']['x'] = 123
        registros['D1']['sha256_resultado'] = hashlib.sha256(lc.canonico(registros['D1']['resultado'])+b'\n').hexdigest()
        registros['D1'] = sellar(registros['D1'])
        result = incorporar_contornos(g, lectura, registros)
        self.assertFalse(result['aplicado']); self.assertTrue(any('reproducible' in x['motivo'] for x in result['conflictos']))

    def test_sin_fuente_documental_calcula_pero_conserva_carencias(self):
        g = caso()[0]
        for v in g['vertices']: v['procedencia'].pop('referencias')
        g, lectura, registros = fixture(geo=g); result = incorporar_contornos(g, lectura, registros)
        self.assertTrue(result['aplicado'], result['conflictos'])
        self.assertTrue(any('descriptor geométrico' in a for a in result['advertencias']))
        self.assertTrue(any('tres controles' in a for a in result['advertencias']))

    def test_control_con_error_no_se_ignora_aunque_incertidumbre_amplia(self):
        g, raw, _, _ = caso()
        for ident, x, y in [('D', 10, 10), ('E', 5, 0), ('F', 5, 5)]:
            g['vertices'].append({'id':ident,'x':float(x),'y':float(y),'z':0.0,
                                  'procedencia':{'tipo':'sintetico','descripcion':'Control externo sintético.','referencias':['CTRL_'+ident]}})
        raw['dibujos'][0]['controles'] = [{'id':'CTRL'+ident,'punto_resuelto':ident,'uv_local':uv,'evidencias':['E1']}
                                          for ident,uv in [('D',[.9,0]),('E',[.5,1]),('F',[.5,.5])]]
        g, lectura, registros = fixture(geo=g,raw=raw,limites={'incertidumbre_max_m':5})
        self.assertTrue(all(p['incertidumbre']['dentro_limite'] for p in registros['D1']['resultado']['puntos']))
        result = incorporar_contornos(g,lectura,registros)
        self.assertFalse(result['aplicado']);self.assertTrue(any('control fuera' in c['motivo'] for c in result['conflictos']))

    def test_lectura_vacia_conserva_pendiente_sin_publicar_cambio(self):
        g, raw, _, _ = caso();raw.update(dibujos=[],elementos=[],aberturas=[])
        g, lectura, registros = fixture(raw=raw)
        result=incorporar_contornos(g,lectura,registros)
        self.assertFalse(result['aplicado']);self.assertTrue(result['pendientes'])

    def test_resumen_falsa_acreditacion_no_se_acepta(self):
        g, lectura, registros = fixture(); registros['D1']['resumen']['exactitud_documental_acreditada'] = True
        registros['D1'] = sellar(registros['D1'])
        self.assertFalse(incorporar_contornos(g, lectura, registros)['aplicado'])

    def test_fuera_de_incertidumbre_no_incorpora_y_falta_registro_no_inventa(self):
        g, lectura, registros = fixture(); registro = registros['D1']; registro['propuesta']['limites']['incertidumbre_max_m'] = .000001
        # Rehacer el resultado para representar un ajuste legítimo pero inadecuado a su umbral.
        fuente, plano = registro['fuente_vigente'], registro['plano']; cg = lectura['contexto']['geometria']
        mapa = {v['id']:v for v in g['vertices']}; cat = {v['id']:v for v in registro['catalogo_referencias']}
        puntos = {i:{'coordenadas':cat[i]['coordenadas'],'unidad_longitud':'m','plano':plano,'fuente':fuente,
                     'huella_resolucion':cat[i]['huella_resolucion'],'referencias':mapa[i]['procedencia']['referencias']} for i in mapa}
        registro['resultado'] = dc.calibrar_digitizacion(registro['propuesta'], fuente_vigente=fuente, puntos_resueltos=puntos)
        registro['sha256_resultado'] = hashlib.sha256(lc.canonico(registro['resultado'])+b'\n').hexdigest()
        registro['hashes_entradas']['huella_entrada_modulo'] = registro['resultado']['huella_entrada']; registros['D1'] = sellar(registro)
        self.assertFalse(incorporar_contornos(g, lectura, registros)['aplicado'])
        result = incorporar_contornos(g, lectura, {})
        self.assertFalse(result['aplicado']); self.assertTrue(result['pendientes'])

    def test_geometria_invalida_vano_fuera_host_revierte_todo(self):
        raw = caso()[1]; raw['aberturas'][0]['host'] = 'BASE'
        g, lectura, registros = fixture(raw=raw); result = incorporar_contornos(g, lectura, registros)
        self.assertFalse(result['aplicado']); self.assertFalse(result['validacion_propuesta']['consistente'])
        self.assertTrue(result['validacion']['consistente'])
        self.assertEqual(result['geometria']['vertices'], g['vertices'])

    def test_orden_respuesta_no_cambia_incorporacion(self):
        a = fixture(); raw = caso()[1]
        raw['elementos'].reverse(); raw['dibujos'][0]['puntos'].reverse(); raw['dibujos'][0]['anclas'].reverse()
        b = fixture(raw=raw)
        self.assertEqual(a[1]['huella_lectura'], b[1]['huella_lectura'])
        ra, rb = incorporar_contornos(*a), incorporar_contornos(*b)
        self.assertEqual(ra['geometria'], rb['geometria']); self.assertEqual(ra['frames_propuestos'], rb['frames_propuestos'])

    def test_unidades_y_naturaleza_se_conservan_sin_mutacion(self):
        for unit, factor in [('cm', 100), ('mm', 1000)]:
            g = caso()[0]; g['unidad_longitud'] = unit
            for v in g['vertices']:
                for k in ('x', 'y', 'z'): v[k] *= factor
            g, lectura, registros = fixture(geo=g); result = incorporar_contornos(g, lectura, registros)
            self.assertTrue(result['aplicado'], result['conflictos']); self.assertEqual(result['geometria']['unidad_longitud'], unit)
            n = next(v for v in result['geometria']['vertices'] if v['id'] == 'N1')
            self.assertAlmostEqual(n['x'], 6*factor)
        g = caso()[0]
        for item in [g]+g['vertices']+g['superficies']: item['procedencia']['tipo'] = 'plano'
        g, lectura, registros = fixture(geo=g); result = incorporar_contornos(g, lectura, registros)
        self.assertTrue(result['aplicado'], result['conflictos']); self.assertFalse(result['validacion']['datos_sinteticos'])

    def test_lectura_y_catalogo_no_pueden_cambiar_geometria_contextual(self):
        g, lectura, registros = fixture(); lectura['contexto']['catalogo_vertices'][0]['x'] = 4
        lectura['huella_lectura'] = lc.huella({'datos': lectura['datos'], 'contexto': lectura['contexto']})
        with self.assertRaisesRegex(ValueError, 'Catálogo espacial'): incorporar_contornos(g, lectura, registros)

    def test_aprobacion_anterior_no_se_hereda_ni_modifica(self):
        g=caso()[0];g['faltantes']=[]
        g['revision']={'estado':'aprobado','aprobacion':{'declarada_por':'Revisor SINTÉTICO','fecha':'2026-10-25',
                                                     'huella_contenido':c.huella_contenido(g)}}
        g,lectura,registros=fixture(geo=g);anterior=copy.deepcopy(g)
        result=incorporar_contornos(g,lectura,registros)
        self.assertTrue(result['aplicado'],result['conflictos'])
        self.assertEqual(result['revision_anterior'],anterior['revision']);self.assertEqual(g,anterior)
        self.assertEqual(result['geometria']['revision'],{'estado':'borrador','aprobacion':None})


if __name__ == '__main__': unittest.main()
