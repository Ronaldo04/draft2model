"""Servicio persistente en expedientes sintéticos temporales, sin HTTP ni ETABS."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from draft2model import revision_politicas_malla as servicio
from draft2model import politicas_malla_automatica as motor
from draft2model.revision_visual import RevisionLocal
from tests import test_integracion_malla as fixtures
from tests.test_gestion_geometria import CASO


DECLARACION = {'declarado_por': 'Ingeniero SINTÉTICO de prueba', 'fecha': '2026-10-25',
               'alcance': 'Reglas explícitas para fixture de software; sin proyecto real.'}


def reglas(fuente=servicio.SENTINEL):
    r = motor.plantilla_reglas_vacia()
    r['reglas_restricciones'] = [{'id': 'BASE', 'selector': {'tipo': 'plano_z', 'z_m': 0},
                                  'restricciones': [True]*6, 'fuente': fuente, 'motivo': 'Base sintética expresamente restringida.'}]
    r['resto_restricciones'] = {'restricciones': [False]*6, 'fuente': fuente, 'motivo': 'Libertades explícitas del resto sintético.'}
    r['reglas_diafragma'] = [{'id': 'PISO', 'selector': {'tipo': 'plano_z', 'z_m': 2.6}, 'accion': 'asignar',
                              'diafragma': 'DIA1', 'motivo_sin_diafragma': None, 'fuente': fuente}]
    r['resto_diafragma'] = {'accion': 'excluir', 'diafragma': None, 'motivo_sin_diafragma': 'Resto sintético excluido explícitamente.', 'fuente': fuente}
    r['subdivision_frames'] = {'modo': 'autorizar_calculadas', 'fuente': fuente, 'motivo': 'Autorización sintética de las subdivisiones calculadas.'}
    return r


class RevisionPoliticasMallaTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CasoMalla(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        cfg = self.fixture.montar('conectados_corte')
        cfg['version_contrato'] = '0.5.0'
        cfg['liquidos'] = {'aplicabilidad': 'informacion_insuficiente', 'fuente': fixtures.F,
                          'motivo': 'Dato técnico sintético todavía pendiente.', 'declaraciones': []}
        self.app = RevisionLocal(self.fixture.raiz)
        self.fp = self.app.expediente(CASO)[2]
        self.parent = self.app.preparacion_configuracion._guardar(CASO, self.fp, cfg, origen={'tipo': 'fixture_sintetica'})
        self.service = servicio.ServicioPoliticasMalla(self.app)

    def solicitud(self, regla=None):
        return {'caso': CASO, 'expediente_sha256': self.fp, 'version': self.parent['id'],
                'sha256_configuracion': self.parent['sha256_configuracion'],
                'reglas': reglas() if regla is None else regla, 'declaracion': copy.deepcopy(DECLARACION)}

    def aplicar(self, body, vista):
        return self.service.aplicar({**body, 'confirmacion_explicita': True,
                                     'huella_propuesta': vista['huella_propuesta'], 'sha256_algoritmo': vista['sha256_algoritmo']})

    def test_sin_reglas_previsualiza_pendientes_sin_mutar_ni_publicar(self):
        body = self.solicitud(motor.plantilla_reglas_vacia()); body['declaracion'] = None
        previos = self.app.preparacion_configuracion.listar(CASO, self.fp)
        antes = copy.deepcopy(self.parent['datos'])
        vista = self.service.previsualizar(body)
        self.assertTrue(vista['malla_calculable']); self.assertFalse(vista['politicas_completas'])
        self.assertGreater(vista['propuesta']['resumen']['pendientes'], 0)
        self.assertIsNone(vista['fuente_decision'])
        self.assertEqual(self.app.preparacion_configuracion.listar(CASO, self.fp), previos)
        self.assertEqual(self.app.preparacion_configuracion._cargar(CASO, self.fp, self.parent['id'])[0], antes)
        with self.assertRaises(ValueError): self.aplicar({**body, 'declaracion': DECLARACION}, vista)

    def test_reglas_completas_guardan_hijo_fuente_decision_y_padre_exactos(self):
        body = self.solicitud(); antes = copy.deepcopy(body)
        vista = self.service.previsualizar(body)
        self.assertTrue(vista['politicas_completas'], vista['propuesta'])
        self.assertFalse(vista['configuracion_completa'])
        self.assertTrue(any(f['ruta'] == '$.liquidos.aplicabilidad' for f in vista['otros_faltantes_tecnicos']))
        child = self.aplicar(body, vista)
        self.assertNotEqual(child['id'], self.parent['id'])
        self.assertTrue(child['datos']['nodos_derivados']); self.assertTrue(child['datos']['subdivision_frames'])
        self.assertEqual(child['datos']['revision'], {'estado': 'borrador', 'aprobacion': None})
        self.assertTrue(child['datos']['datos_sinteticos'])
        self.assertEqual(child['datos']['liquidos'], self.parent['datos']['liquidos'])
        self.assertEqual(child['registro']['padre'], {k: self.parent[k] for k in ['id', 'sha256_registro', 'sha256_configuracion']})
        self.assertEqual(child['registro']['origen']['decision']['declaracion'], DECLARACION)
        self.assertEqual(child['registro']['origen']['decision']['identidad'], 'declarada_no_verificada')
        fuente = vista['fuente_decision']; self.assertIn(fuente, child['datos']['fuentes'])
        self.assertEqual(child['datos']['fuentes'][:-1], self.parent['datos']['fuentes'])
        self.assertTrue(all(n['fuente'] == fuente['id'] for n in child['datos']['nodos_derivados']))
        self.assertEqual(body, antes); self.assertFalse(child['ejecutable_etabs'])
        self.assertEqual(self.app.preparacion_configuracion._cargar(CASO, self.fp, self.parent['id'])[0], self.parent['datos'])
        json.dumps(child, allow_nan=False)

    def test_huella_reglas_declaracion_algoritmo_y_confirmacion_vigentes(self):
        body = self.solicitud(); vista = self.service.previsualizar(body)
        aplicar = {**body, 'confirmacion_explicita': True, 'huella_propuesta': vista['huella_propuesta'],
                   'sha256_algoritmo': vista['sha256_algoritmo']}
        for clave, valor in [('confirmacion_explicita', False), ('huella_propuesta', '0'*64),
                             ('sha256_algoritmo', '0'*64), ('sha256_configuracion', '0'*64)]:
            with self.subTest(clave=clave), self.assertRaises(ValueError): self.service.aplicar({**aplicar, clave: valor})
        changed = copy.deepcopy(aplicar); changed['declaracion']['alcance'] += ' Cambio.'
        with self.assertRaises(ValueError): self.service.aplicar(changed)
        changed = copy.deepcopy(aplicar); changed['reglas']['resto_restricciones']['motivo'] += ' Cambio.'
        with self.assertRaises(ValueError): self.service.aplicar(changed)
        codigo = {**self.service._codigo_cargado, 'politicas_malla_automatica.py': '0'*64}
        with patch.object(servicio, '_codigo', return_value=codigo), self.assertRaisesRegex(ValueError, 'código'):
            self.service.aplicar(aplicar)

    def test_original_alterado_rechaza_aplicacion(self):
        body = self.solicitud(); vista = self.service.previsualizar(body)
        self.fixture.f.original.write_bytes(b'%PDF-1.4\nfixture modificada\n')
        with self.assertRaises(ValueError): self.aplicar(body, vista)

    def test_geometria_alterada_rechaza_aplicacion(self):
        body = self.solicitud(); vista = self.service.previsualizar(body)
        path = Path(self.fixture.raiz)/CASO/'geometrias'/self.fixture.version.identificador/'geometria.json'
        path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(ValueError): self.aplicar(body, vista)

    def test_fuente_configuracion_alterada_no_se_reconcilia_silenciosamente(self):
        body = self.solicitud(); vista = self.service.previsualizar(body)
        path = Path(self.fixture.raiz)/CASO/'configuraciones_en_preparacion'/self.parent['id']/'configuracion.json'
        data = json.loads(path.read_bytes()); data['fuentes'][0]['sha256'] = '0'*64
        path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(ValueError): self.aplicar(body, vista)

    def test_registro_padre_modificado_invalida_la_vista_previa(self):
        body = self.solicitud(); vista = self.service.previsualizar(body)
        path = Path(self.fixture.raiz)/CASO/'configuraciones_en_preparacion'/self.parent['id']/'registro.json'
        data = json.loads(path.read_bytes()); data['origen']['nota'] = 'Cambio posterior a previsualización.'
        path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'propuesta'): self.aplicar(body, vista)

    def test_fuente_existente_se_utiliza_sin_sustituirla_y_fuente_ajena_bloquea(self):
        body = self.solicitud(reglas(fixtures.F)); vista = self.service.previsualizar(body)
        self.assertIsNone(vista['fuente_decision'])
        child = self.aplicar(body, vista)
        self.assertEqual(child['datos']['fuentes'], self.parent['datos']['fuentes'])
        body = self.solicitud(reglas('NO-EXISTE')); vista = self.service.previsualizar(body)
        self.assertFalse(vista['politicas_completas'])
        self.assertTrue(vista['propuesta']['errores'])
        with self.assertRaises(ValueError): self.aplicar(body, vista)

    def test_conflictos_y_fechas_invalidas_no_generan_hijos(self):
        body = self.solicitud()
        body['reglas']['reglas_restricciones'].append({**body['reglas']['reglas_restricciones'][0], 'id': 'CONFLICTO', 'restricciones': [False]*6})
        vista = self.service.previsualizar(body)
        self.assertTrue(vista['propuesta']['conflictos'])
        with self.assertRaises(ValueError): self.aplicar(body, vista)
        body = self.solicitud(); body['declaracion']['fecha'] = '2026-02-30'
        with self.assertRaises(ValueError): self.service.previsualizar(body)

    def test_naturaleza_incompatible_rechazada_sin_transformarla(self):
        cfg = copy.deepcopy(self.parent['datos']); cfg['datos_sinteticos'] = False
        child = self.app.preparacion_configuracion._guardar(CASO, self.fp, cfg, origen={'tipo': 'fixture_incompatible'})
        body = {**self.solicitud(), 'version': child['id'], 'sha256_configuracion': child['sha256_configuracion']}
        with self.assertRaisesRegex(ValueError, 'naturaleza'): self.service.previsualizar(body)


if __name__ == '__main__':
    unittest.main()
