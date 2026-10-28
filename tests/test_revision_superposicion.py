"""Superposición geometría↔página con anclas explícitas: servicio y HTTP, datos sintéticos, sin red."""
import json
import math
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

import pymupdf

from draft2model import gestion_geometria as geo
from draft2model.ingreso import registrar_expediente
from draft2model.revision_superposicion import ErrorSuperposicion, ServicioSuperposicion, aplicar
from draft2model.revision_visual import RevisionLocal
from tests import test_revision_visual as httpfixtures

ROOT = Path(__file__).resolve().parents[1]
CASO = 'superposicion-sintetica'


def matriz(theta=math.radians(30), s=0.08, tu=0.3, tv=0.6):
    """Rotación, escala, traslación e inversión de y (imagen hacia abajo)."""
    c, n = math.cos(theta), math.sin(theta)
    return [[s*c, -s*n, tu], [-s*n, -s*c, tv]]


class SuperposicionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); root = Path(tmp.name).resolve()
        for caso in (CASO, 'otro-caso'):
            pdf = root/(caso+'.pdf')
            with pymupdf.open() as doc:
                doc.new_page(width=200, height=120).insert_text((40, 50), 'PLANO SINTETICO'); doc.save(pdf)
            registrar_expediente(caso, [pdf], root/'casos', uso_autorizado=True, provisional_fuera_alcance=True)
        self.app = RevisionLocal(root/'casos'); self.service = ServicioSuperposicion(self.app)
        self.fp = self.app.expediente(CASO)[2]; self.case = self.app.raiz/CASO; self.root = root
        self.archivo = self.app.expediente(CASO)[1]['archivos'][0]['id']
        self.geo_id = self.importar()
        for target in ('subprocess.Popen', 'urllib.request.urlopen', 'socket.create_connection'):
            guard = patch(target, side_effect=AssertionError('Sin red ni procesos')); guard.start(); self.addCleanup(guard.stop)
        self.server = SimpleNamespace(revision=self.app, token='prueba', origen='http://127.0.0.1:8766')

    def importar(self, unidad='m', caso=CASO):
        data = json.loads((ROOT/'examples/geometria_sintetica.json').read_text(encoding='utf-8'))
        data['id'] = caso; data['unidad_longitud'] = unidad
        path = self.root/(caso+unidad+'.json'); path.write_text(json.dumps(data), encoding='utf-8')
        return geo.importar_geometria(self.app.raiz, caso, path).identificador

    def actual(self, version=None):
        return self.app.geometria(CASO, version or self.geo_id)

    def body(self, m=None, nodos=('A', 'B', 'C'), version=None, **cambios):
        m = m or matriz(); current = self.actual(version)
        xy = {n['id']: (n['x'], n['y']) for n in current['datos']['nodos']}
        anclas = [{'nodo': k, 'punto': list(aplicar(m, *xy[k]))} for k in nodos]
        return {'caso': CASO, 'expediente_sha256': self.fp, 'geometria': version or self.geo_id, 'huella_geometria': current['huella'],
                'sha256_geometria': current['sha256_geometria'], 'archivo': self.archivo, 'pagina': 1, 'nivel': 'N0',
                'anclas': anclas, 'revisor_declarado': 'Revisor declarado sintético', 'fecha': '2026-10-18',
                'motivo': 'Correspondencia de prueba con anclas fabricadas.', 'confirmacion_explicita': True, **cambios}

    def request(self, *args, **kwargs):
        return httpfixtures.HTTPRevisionTests.request(self, *args, **kwargs)

    # -- servicio ------------------------------------------------------------------------
    def test_transformacion_conocida_proyeccion_e_historial(self):
        esquema = self.service.esquema(CASO, self.geo_id, expediente_sha256=self.fp)
        self.assertEqual(esquema['unidad_longitud'], 'm'); self.assertEqual(esquema['estado_revision'], 'borrador')
        self.assertFalse(esquema['disponible_para_modelado'])
        n0 = next(n for n in esquema['niveles'] if n['id'] == 'N0')
        m1 = next(m for m in n0['muros'] if m['id'] == 'M1')
        self.assertEqual((m1['inicio']['id'], m1['fin']['id'], m1['longitud'], m1['espesor']), ('A', 'B', 4.0, 0.15))
        item = self.service.crear(self.body())
        for fila, esperada in zip(item['transformacion']['matriz'], matriz()):
            for a, b in zip(fila, esperada):
                self.assertAlmostEqual(a, b, places=12)
        d = next(e for m in item['muros'] for e in m['proyeccion'] if e['nodo'] == 'D')
        self.assertAlmostEqual(d['u'], aplicar(matriz(), 0.0, 3.0)[0], places=12)
        self.assertAlmostEqual(d['v'], aplicar(matriz(), 0.0, 3.0)[1], places=12)
        self.assertEqual(item['fuera_imagen'], []); self.assertEqual(item['transformacion']['de'], 'modelo_xy_m')
        self.assertFalse(item['aprueba_ingenieria'] or item['aprueba_geometria'])
        self.assertEqual(item['naturaleza'], 'correspondencia_declarada_no_deteccion')
        self.assertEqual(item['fuente']['preview_px'][0] > 0, True)
        rows = self.service.listar(CASO, expediente_sha256=self.fp)
        self.assertEqual([(r['id'], r['vigente']) for r in rows['versiones']], [(item['id'], True)]); self.assertFalse(rows['seleccion_automatica'])
        text = json.dumps([esquema, item, rows]); self.assertNotIn(str(self.app.raiz), text); self.assertNotIn(json.dumps(str(self.app.raiz))[1:-1], text)

    def test_puntos_fuera_de_imagen_se_listan_sin_recortar(self):
        # Afín: B = A + C - D. Con A, C y D dentro de la página, B queda en (1.3, 1.2), fuera de imagen.
        anclas = [{'nodo': 'A', 'punto': [0.6, 0.9]}, {'nodo': 'C', 'punto': [0.9, 0.6]}, {'nodo': 'D', 'punto': [0.2, 0.3]}]
        item = self.service.crear({**self.body(), 'anclas': anclas})
        fuera = {f['muro']+':'+f['nodo']: (f['u'], f['v']) for f in item['fuera_imagen']}
        self.assertEqual(set(fuera), {'M1:B', 'M2:B'})
        self.assertAlmostEqual(fuera['M1:B'][0], 1.3, places=12); self.assertAlmostEqual(fuera['M1:B'][1], 1.2, places=12)
        b = [e for m in item['muros'] for e in m['proyeccion'] if e['nodo'] == 'B']
        self.assertTrue(b and all(e['dentro_imagen'] is False for e in b))

    def test_anclas_unidades_ids_y_declaracion_invalidas(self):
        base = self.body()
        malos = {'duplicado': {'anclas': [base['anclas'][0], base['anclas'][0], base['anclas'][2]]},
                 'colineal_imagen': {'anclas': [{'nodo': 'A', 'punto': [0.1, 0.1]}, {'nodo': 'B', 'punto': [0.5, 0.5]}, {'nodo': 'C', 'punto': [0.9, 0.9]}]},
                 'casi_colineal': {'anclas': [{'nodo': 'A', 'punto': [0.1, 0.1]}, {'nodo': 'B', 'punto': [0.5, 0.5]}, {'nodo': 'C', 'punto': [0.9, 0.9002]}]},
                 'fuera_rango': {'anclas': [{**base['anclas'][0], 'punto': [1.2, 0.1]}, *base['anclas'][1:]]},
                 'no_finito': {'anclas': [{**base['anclas'][0], 'punto': [float('nan'), 0.1]}, *base['anclas'][1:]]},
                 'nodo_inexistente': {'anclas': [{**base['anclas'][0], 'nodo': 'Z'}, *base['anclas'][1:]]},
                 'dos_anclas': {'anclas': base['anclas'][:2]},
                 'nivel_sin_muros': {'nivel': 'N1'}, 'nivel_inexistente': {'nivel': 'NX'},
                 'sin_confirmacion': {'confirmacion_explicita': False}, 'fecha': {'fecha': '2026-02-30'},
                 'campo_extra': {'ruta': 'C:/x'}, 'huella': {'huella_geometria': '0'*64}, 'pagina': {'pagina': 9},
                 'archivo': {'archivo': 'L9999'}, 'expediente': {'expediente_sha256': '0'*64}}
        for nombre, cambios in malos.items():
            body = {**base, **cambios}
            if nombre == 'campo_extra':
                body = {**base, 'ruta': 'C:/x'}
            if nombre == 'no_finito':
                with self.subTest(nombre), self.assertRaises((ErrorSuperposicion, ValueError)):
                    self.service.crear(body)
                continue
            with self.subTest(nombre), self.assertRaises(ErrorSuperposicion):
                self.service.crear(body)
        self.assertFalse((self.case/'superposiciones').exists() and any(p.name[:1] != '.' for p in (self.case/'superposiciones').iterdir()))

    def test_unidad_del_contrato_sin_conversion(self):
        cm = self.importar('cm')
        esquema = self.service.esquema(CASO, cm, expediente_sha256=self.fp)
        self.assertEqual(esquema['unidad_longitud'], 'cm')
        m1 = next(m for m in esquema['niveles'][0]['muros'] if m['id'] == 'M1'); self.assertEqual(m1['longitud'], 4.0)
        item = self.service.crear(self.body(version=cm)); self.assertEqual(item['transformacion']['de'], 'modelo_xy_cm')

    def test_geometria_corregida_exige_nueva_correspondencia(self):
        first = self.service.crear(self.body())
        data = self.actual()['datos']; data['nodos'][2]['x'] = 4.5
        nueva = geo.revisar_geometria(self.app.raiz, CASO, self.geo_id, data, motivo='Corrección sintética', fecha='2026-10-18',
                                      revisor_declarado='Revisor').identificador
        viejo = self.body()
        with self.assertRaises(ErrorSuperposicion):
            self.service.crear({**viejo, 'geometria': nueva})  # huella de la versión anterior
        segunda = self.service.crear(self.body(version=nueva))
        self.assertNotEqual(segunda['geometria']['huella'], first['geometria']['huella'])
        self.assertTrue(self.service.consultar(CASO, first['id'], expediente_sha256=self.fp)['vigente'])  # versión antigua inmutable

    def test_fuentes_registro_y_caso_alterados_invalidan(self):
        item = self.service.crear(self.body()); folder = self.case/'superposiciones'/item['id']
        with patch.object(self.app, 'pagina', return_value=b'\x89PNG\r\n\x1a\n'+b'\x00'*8+b'IHDR'+b'\x00\x00\x00\x10\x00\x00\x00\x10'):
            with self.assertRaises(ErrorSuperposicion):
                self.service.consultar(CASO, item['id'], expediente_sha256=self.fp)  # vista previa distinta
        reg = json.loads((folder/'correspondencia.json').read_text(encoding='utf-8'))
        reg['anclas'][0]['punto'][0] += 0.01
        raw = (json.dumps(reg, sort_keys=True, ensure_ascii=False, indent=2)+'\n').encode()
        original_reg = (folder/'correspondencia.json').read_bytes(); original_meta = (folder/'version.json').read_bytes()
        (folder/'correspondencia.json').write_bytes(raw)
        meta = json.loads(original_meta); import hashlib; meta['sha256_correspondencia'] = hashlib.sha256(raw).hexdigest()
        (folder/'version.json').write_text(json.dumps(meta), encoding='utf-8')
        with self.assertRaises(ErrorSuperposicion):
            self.service.consultar(CASO, item['id'], expediente_sha256=self.fp)  # calibración alterada con hash rehecho
        (folder/'correspondencia.json').write_bytes(original_reg); (folder/'version.json').write_bytes(original_meta)
        self.assertTrue(self.service.consultar(CASO, item['id'], expediente_sha256=self.fp)['vigente'])
        otro = self.app.raiz/'otro-caso'/'superposiciones'; otro.mkdir(); shutil.copytree(folder, otro/item['id'])
        with self.assertRaises(ErrorSuperposicion):
            self.service.consultar('otro-caso', item['id'], expediente_sha256=self.app.expediente('otro-caso')[2])
        pdf = next(self.case.rglob('*.pdf')); pdf.write_bytes(pdf.read_bytes()+b'%alterado')
        with self.assertRaises(ErrorSuperposicion):
            self.service.consultar(CASO, item['id'], expediente_sha256=self.fp)

    def test_geometria_cambia_durante_render_no_es_vigente(self):
        item = self.service.crear(self.body())
        path = next((self.case/'geometrias'/self.geo_id).glob('geometria.json')); original = path.read_bytes(); real = self.app.pagina
        def alterar(*args, **kwargs):
            value = real(*args, **kwargs); path.write_bytes(original+b' ')
            return value
        try:
            with patch.object(self.app, 'pagina', side_effect=alterar):
                with self.assertRaises(ErrorSuperposicion):
                    self.service.consultar(CASO, item['id'], expediente_sha256=self.fp)
        finally:
            path.write_bytes(original)
        self.assertTrue(self.service.consultar(CASO, item['id'], expediente_sha256=self.fp)['vigente'])

    # -- HTTP ------------------------------------------------------------------------------
    def test_http_rutas_sesion_limite_y_errores(self):
        q = lambda kind, **kw: '/api/superposicion/'+kind+'?'+urlencode({'caso': CASO, 'expediente_sha256': self.fp, **kw})
        status, raw, _ = self.request('GET', q('esquema', version=self.geo_id)); self.assertEqual(status, 200, raw)
        self.assertEqual(json.loads(raw)['geometria'], self.geo_id)
        status, raw, _ = self.request('POST', '/api/superposicion/crear', self.body()); self.assertEqual(status, 201, raw)
        item = json.loads(raw)
        status, raw, _ = self.request('GET', q('historial')); self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)['versiones'][0]['id'], item['id'])
        status, raw, _ = self.request('GET', q('version', version=item['id'])); self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)['sha256_correspondencia'], item['sha256_correspondencia'])
        self.assertNotIn(str(self.app.raiz).encode(), raw)
        self.assertEqual(self.request('GET', q('historial'), headers={'X-Revision-Session': 'otra'})[0], 403)
        self.assertEqual(self.request('POST', '/api/superposicion/crear', self.body(), headers={'Origin': 'http://evil.test'})[0], 403)
        self.assertEqual(self.request('POST', '/api/superposicion/crear', {**self.body(), 'motivo': 'x'*(3*1024*1024)})[0], 413)
        status, raw, _ = self.request('POST', '/api/superposicion/crear', {**self.body(), 'confirmacion_explicita': False})
        self.assertEqual(status, 409); self.assertIn('Confirma', json.loads(raw)['error'])
        status, raw, _ = self.request('GET', q('version', version='../x')); self.assertEqual(status, 409)
        status, raw, _ = self.request('GET', '/superposicion.js'); self.assertEqual(status, 200); self.assertIn(b'/api/superposicion/crear', raw)
        status, raw, _ = self.request('GET', '/'); self.assertEqual(raw.count(b'src="/superposicion.js"'), 1); self.assertIn(b'id="supLienzo"', raw)


if __name__ == '__main__':
    unittest.main()
