"""Paneles técnicos persistidos sobre la fixture portable ETABS sintética, solo en copias temporales."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch

from draft2model import revision_paneles as rp
from draft2model.evidencia_analisis import verificar_evidencia
from draft2model.revision_paneles import ErrorPaneles, ServicioPaneles
from draft2model.revision_visual import RevisionLocal
from tests.fixture_etabs import extraer_evidencia

CASO = 'demo-integrada-sintetica'
RESULTADO = '72c06efb3bfe477bb1fe565809aeddec'
ANALISIS = 'adf97fbc232141e8ae687872c0d71232'
OTRO_ANALISIS = '28f6d928fac949acadd19f294e6bf644'


def enlazar_carpeta(enlace, destino):
    try:
        import _winapi
        _winapi.CreateJunction(str(destino), str(enlace))
        return True
    except (ImportError, OSError):
        pass
    try:
        os.symlink(destino, enlace, target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        return False


class LockContado:
    """RLock que cuenta adquisiciones, para comprobar que el servicio usa el lock de la app."""

    def __init__(self):
        self._lock = threading.RLock()
        self.entradas = 0

    def __enter__(self):
        self._lock.acquire()
        self.entradas += 1
        return self

    def __exit__(self, *exc):
        self._lock.release()


class PanelesTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.bundle = extraer_evidencia(Path(temp.name).resolve() / 'fixture')
        self.app = RevisionLocal(self.bundle / 'private')
        self.service = ServicioPaneles(self.app)
        self.fp = self.app.expediente(CASO)[2]
        self.caso_dir = self.app.raiz / CASO
        self.body = {'caso': CASO, 'resultado': RESULTADO, 'expediente_sha256': self.fp, 'analisis': None}

    def copiar_analisis(self, ident=ANALISIS, origen='analisis'):
        destino = self.caso_dir / 'analisis_etabs' / ident
        shutil.copytree(self.bundle / origen / ident, destino)
        return destino

    def archivo(self, ident, fp=None):
        return self.service.archivo(CASO, ident, expediente_sha256=fp or self.fp)

    def consultar(self, ident, fp=None):
        return self.service.consultar(CASO, ident, expediente_sha256=fp or self.fp)

    def listar(self, fp=None):
        return self.service.listar(CASO, RESULTADO, expediente_sha256=fp or self.fp)['versiones']

    def datos_html(self, raw):
        return json.loads(raw.decode('utf-8').split(rp.MARCA_DATOS)[1].split('</script>')[0])

    def carpeta(self, ident):
        return self.caso_dir / 'paneles' / ident

    # -- generación ---------------------------------------------------------------
    def test_sin_analisis_estados_pendientes_y_sin_rutas(self):
        panel = self.service.crear(self.body)
        self.assertEqual(panel['estados'], {'calculo': 'sin_vinculo_de_analisis', 'revision_resultados': 'pendiente',
                                            'conformidad_normativa': 'no_evaluada', 'reglas': 'pendientes'})
        self.assertIsNone(panel['analisis'])
        self.assertIsNone(panel['evidencia_analisis'])
        self.assertFalse(panel['aprueba_resultados'] or panel['aprueba_ingenieria'])
        self.assertEqual(sorted(p.name for p in self.carpeta(panel['id']).iterdir()), ['manifiesto.json', 'panel.html'])
        raw = self.archivo(panel['id'])
        self.assertTrue(raw.startswith(b'<!doctype html>'))
        self.assertEqual(hashlib.sha256(raw).hexdigest(), panel['sha256_html'])
        datos = self.datos_html(raw)
        self.assertIsNone(datos['evaluacion'])
        self.assertNotIn('evidencia_analisis', datos)
        self.assertEqual(datos['numero_muros'], 1)
        self.assertIn('Evaluación pendiente', raw.decode('utf-8'))
        resultados = self.app.resultados.consultar_resultado(CASO, RESULTADO, expediente_sha256=self.fp)
        self.assertEqual(datos['resultados'], resultados['datos'])
        texto = json.dumps(panel, ensure_ascii=False) + raw.decode('utf-8')
        for privado in (str(self.bundle), str(self.app.raiz), json.dumps(str(self.app.raiz))[1:-1]):
            self.assertNotIn(privado, texto)

    def test_analisis_vinculado_y_alteracion_del_edb(self):
        corrida = self.copiar_analisis()
        panel = self.service.crear({**self.body, 'analisis': ANALISIS})
        esperado = verificar_evidencia(self.app.raiz, CASO, RESULTADO, corrida)
        self.assertEqual(panel['evidencia_analisis'], esperado)
        self.assertEqual(panel['estados']['calculo'], 'completado_verificado')
        self.assertEqual(panel['estados']['revision_resultados'], 'pendiente')
        self.assertEqual(panel['fuentes']['sha256_edb_analizado'], esperado['analisis']['sha256_edb_analizado'])
        self.assertEqual(self.datos_html(self.archivo(panel['id']))['evidencia_analisis'], esperado)
        (corrida / 'analizado.edb').write_bytes(b'ALTERADO')
        for operacion in (lambda: self.archivo(panel['id']), lambda: self.consultar(panel['id'])):
            with self.assertRaises(ErrorPaneles):
                operacion()
        self.assertEqual(self.listar(), [{'id': panel['id'], 'vigente': False, 'problemas': ['version_no_vigente']}])

    def test_analisis_de_otro_modelo_o_fuera_de_analisis_etabs_rechazado(self):
        self.copiar_analisis(OTRO_ANALISIS, 'otro_analisis')
        with self.assertRaises(ErrorPaneles):
            self.service.crear({**self.body, 'analisis': OTRO_ANALISIS})
        with self.assertRaises(ErrorPaneles):  # existe en la fixture, pero no en <caso>/analisis_etabs
            self.service.crear({**self.body, 'analisis': ANALISIS})
        self.assertFalse((self.caso_dir / 'paneles').exists() and any(self.carpeta('').iterdir()))

    def test_listado_y_nueva_version_sin_sobrescritura(self):
        primero = self.service.crear(self.body)
        antes = {p.name: p.read_bytes() for p in self.carpeta(primero['id']).iterdir()}
        segundo = self.service.crear(self.body)
        self.assertNotEqual(primero['id'], segundo['id'])
        self.assertEqual({p.name: p.read_bytes() for p in self.carpeta(primero['id']).iterdir()}, antes)
        filas = self.listar()
        self.assertEqual(sorted(f['id'] for f in filas), sorted([primero['id'], segundo['id']]))
        self.assertTrue(all(f['vigente'] and f['analisis'] is None for f in filas))
        self.assertEqual([p.name for p in self.carpeta('').iterdir() if p.name.startswith('.')], [])  # sin temporales
        (self.carpeta('') / 'no-es-version').mkdir()
        self.assertEqual(len(self.listar()), 2)

    # -- alteraciones ---------------------------------------------------------------
    def test_html_y_manifiesto_alterados(self):
        panel = self.service.crear(self.body)
        html = self.carpeta(panel['id']) / 'panel.html'
        original = html.read_bytes()
        html.write_bytes(original.replace(b'Panel', b'Pane1', 1))
        with self.assertRaises(ErrorPaneles):
            self.archivo(panel['id'])
        # HTML editado con el manifiesto rehecho: lo detecta la comparación con las fuentes vigentes.
        datos = self.datos_html(original)
        datos['resultados']['resultados'][0]['valor'] = 99.0
        bloque = json.dumps(datos, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
        texto = original.decode('utf-8')
        alterado = (texto.split(rp.MARCA_DATOS)[0] + rp.MARCA_DATOS + bloque + '</script>'
                    + texto.split(rp.MARCA_DATOS)[1].split('</script>', 1)[1]).encode('utf-8')
        html.write_bytes(alterado)
        manifiesto = self.carpeta(panel['id']) / 'manifiesto.json'
        meta = json.loads(manifiesto.read_bytes())
        meta['artefacto']['panel.html'] = hashlib.sha256(alterado).hexdigest()
        manifiesto.write_text(json.dumps(meta), encoding='utf-8')
        with self.assertRaises(ErrorPaneles):
            self.archivo(panel['id'])

    def test_shell_html_alterado_con_sha_rehecho_se_rechaza(self):
        panel = self.service.crear(self.body)
        html = self.carpeta(panel['id']) / 'panel.html'
        manifiesto = self.carpeta(panel['id']) / 'manifiesto.json'
        original = html.read_bytes(); meta = json.loads(manifiesto.read_bytes())
        for alterado in (original.replace(b'Panel', b'APROBADO', 1),
                         original.replace(b'</html>', b'<script>document.body.textContent="APROBADO"</script></html>')):
            with self.subTest(script=b'<script>document.body' in alterado):
                html.write_bytes(alterado)
                meta['artefacto']['panel.html'] = hashlib.sha256(alterado).hexdigest()
                manifiesto.write_text(json.dumps(meta), encoding='utf-8')
                for op in (lambda: self.consultar(panel['id']), lambda: self.archivo(panel['id'])):
                    with self.assertRaises(ErrorPaneles):op()

    def test_manifiesto_alterado_durante_segunda_validacion_descarga(self):
        panel = self.service.crear(self.body)
        manifiesto = self.carpeta(panel['id']) / 'manifiesto.json'
        real = self.service._comprobar_html; llamadas = []
        def alterar(html, fuente):
            real(html, fuente); llamadas.append(1)
            if len(llamadas) == 2:manifiesto.write_text('[]', encoding='utf-8')
        with patch.object(self.service, '_comprobar_html', side_effect=alterar):
            with self.assertRaises(ErrorPaneles):self.archivo(panel['id'])
        self.assertEqual(len(llamadas), 2)

    def test_html_cambia_despues_de_validar_datos_se_rechaza(self):
        panel = self.service.crear(self.body)
        html_path = self.carpeta(panel['id']) / 'panel.html'
        real = self.service._comprobar_html
        def alterar(html, fuente):
            real(html, fuente)
            html_path.write_bytes(html + b'ALTERADO')
        with patch.object(self.service, '_comprobar_html', side_effect=alterar):
            with self.assertRaises(ErrorPaneles):self.consultar(panel['id'])

    def test_descarga_compara_bytes_manifiesto_entre_ambas_cargas(self):
        panel = self.service.crear(self.body)
        manifiesto = self.carpeta(panel['id']) / 'manifiesto.json'
        real = self.service._cargar; llamadas = []
        def alterar(*args):
            result = real(*args); llamadas.append(1)
            if len(llamadas) == 1:
                # JSON equivalente: ambas cargas validan por separado, pero la
                # versión cambió entre sus snapshots y no debe descargarse.
                manifiesto.write_bytes(manifiesto.read_bytes() + b' ')
            return result
        with patch.object(self.service, '_cargar', side_effect=alterar):
            with self.assertRaises(ErrorPaneles):self.archivo(panel['id'])
        self.assertEqual(len(llamadas), 2)

    def test_manifiesto_con_tipos_o_identidad_invalidos(self):
        panel = self.service.crear(self.body)
        manifiesto = self.carpeta(panel['id']) / 'manifiesto.json'
        original = json.loads(manifiesto.read_bytes())
        cambios = {
            'artefacto lista': lambda m: m.update(artefacto=['panel.html']),
            'fuentes texto': lambda m: m.update(fuentes='x'),
            'estados lista': lambda m: m.update(estados=[]),
            'manifiesto lista': None,
            'otro resultado': lambda m: m.update(resultado='0' * 32),
            'aprobado': lambda m: m.update(aprueba_resultados=True),
            'revision aprobada': lambda m: m['estados'].update(revision_resultados='aprobado'),
            'evidencia inventada': lambda m: m['fuentes'].update(huella_evidencia='1' * 64),
            'otro expediente': lambda m: m.update(expediente_sha256='2' * 64),
            'clave extra': lambda m: m.update(exitosa=True),
        }
        for nombre, cambio in cambios.items():
            with self.subTest(nombre):
                meta = copy.deepcopy(original)
                if cambio is None:
                    meta = [meta]
                else:
                    cambio(meta)
                manifiesto.write_text(json.dumps(meta), encoding='utf-8')
                with self.assertRaises(ErrorPaneles):
                    self.consultar(panel['id'])
        manifiesto.write_text(json.dumps(original), encoding='utf-8')
        self.assertEqual(self.consultar(panel['id'])['id'], panel['id'])

    def test_fuentes_alteradas(self):
        panel = self.service.crear(self.body)
        resultados = self.caso_dir / 'resultados_estructurales' / RESULTADO / 'resultados.json'
        original = resultados.read_bytes()
        resultados.write_bytes(original.replace(b'3e-06', b'4e-06'))
        with self.assertRaises(ErrorPaneles):
            self.archivo(panel['id'])
        resultados.write_bytes(original)
        self.assertTrue(self.archivo(panel['id']))
        geometria = self.caso_dir / 'geometrias' / panel['fuentes']['geometria_id'] / 'geometria.json'
        original_geo = geometria.read_bytes()
        geometria.write_bytes(original_geo + b' ')
        with self.assertRaises(ErrorPaneles):
            self.archivo(panel['id'])
        geometria.write_bytes(original_geo)
        # Un original alterado cambia la huella del expediente: la consulta con la huella anterior se rechaza.
        documento = next((self.caso_dir / 'originales').iterdir())
        documento.write_bytes(b'ALTERADO')
        with self.assertRaises(ErrorPaneles):
            self.listar()

    def test_cambio_de_fuente_durante_la_descarga(self):
        panel = self.service.crear(self.body)
        documento = next((self.caso_dir / 'originales').iterdir())
        real = rp._datos_embebidos
        llamadas = {'n': 0}

        def alterar_tras_primera(html):
            llamadas['n'] += 1
            if llamadas['n'] == 1:
                documento.write_bytes(b'ALTERADO DURANTE LA DESCARGA')
            return real(html)

        with patch.object(rp, '_datos_embebidos', side_effect=alterar_tras_primera):
            with self.assertRaises(ErrorPaneles):
                self.archivo(panel['id'])

    # -- rutas e identificadores -------------------------------------------------------
    def test_cuerpo_rutas_e_identificadores_rechazados(self):
        malos = ({'resultado': '../fuera'}, {'resultado': RESULTADO.upper()}, {'caso': 'otro'}, {'caso': '../x'},
                 {'expediente_sha256': '0' * 64}, {'expediente_sha256': 'corto'}, {'analisis': '../otra'},
                 {'analisis': ANALISIS.upper()}, {'analisis': 5})
        for extra in malos:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.service.crear({**self.body, **extra})
        for cuerpo in ({k: v for k, v in self.body.items() if k != 'analisis'}, {**self.body, 'reglas': None}, [self.body]):
            with self.subTest(cuerpo=cuerpo), self.assertRaises(ErrorPaneles):
                self.service.crear(cuerpo)
        panel = self.service.crear(self.body)
        for version in ('../' + panel['id'], panel['id'].upper(), 'x' * 32):
            with self.subTest(version=version), self.assertRaises(ErrorPaneles):
                self.archivo(version)
        self.assertFalse((self.caso_dir / 'paneles' / 'fuera').exists())

    def test_carpetas_enlazadas_rechazadas(self):
        externa = self.bundle / 'analisis'
        if not enlazar_carpeta(self.caso_dir / 'analisis_etabs', externa):
            self.skipTest('El sistema no permite crear junction ni enlace simbólico.')
        with self.assertRaises(ErrorPaneles):
            self.service.crear({**self.body, 'analisis': ANALISIS})
        destino_paneles = Path(tempfile.mkdtemp(dir=self.bundle))
        if enlazar_carpeta(self.caso_dir / 'paneles', destino_paneles):
            with self.assertRaises(ErrorPaneles):
                self.service.crear(self.body)
            self.assertEqual(list(destino_paneles.iterdir()), [])

    def test_usa_el_lock_de_la_app(self):
        self.app.lock = LockContado()
        panel = self.service.crear(self.body)
        entradas = self.app.lock.entradas
        self.archivo(panel['id'])
        self.listar()
        self.assertGreater(entradas, 0)
        self.assertGreater(self.app.lock.entradas, entradas)

    def test_listado_no_incluye_panel_roto_de_otro_resultado(self):
        panel=self.service.crear(self.body);ident='e'*32;target=self.caso_dir/'paneles'/ident
        shutil.copytree(self.carpeta(panel['id']),target)
        path=target/'manifiesto.json';meta=json.loads(path.read_bytes());meta.update(id=ident,resultado='f'*32)
        path.write_text(json.dumps(meta))
        self.assertEqual([v['id'] for v in self.listar()],[panel['id']])


if __name__ == '__main__':
    unittest.main()
