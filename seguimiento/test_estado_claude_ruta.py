"""Regresión de coordinación: entregas consecutivas no deben perder revisiones."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from seguimiento import estado_claude as s


class ColaRutaTests(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'tmp')
        self.addCleanup(temporal.cleanup)
        self.root = Path(temporal.name).resolve()
        parche = patch.object(s, 'ROOT', self.root)
        parche.start()
        self.addCleanup(parche.stop)
        self.control = {'tarea': 'ruta_autonoma_201', 'modo': 'ruta_autonoma',
                        'estado_ruta': 'seguimiento/claude_ruta/estado.json',
                        'revisiones_ruta': 'seguimiento/claude_ruta/REVISIONES.json'}
        self.escribir('seguimiento/CLAUDE_ESTADO.json', self.control)
        self.revisadas([])

    def escribir(self, nombre, contenido):
        p = self.root / nombre
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(contenido), encoding='utf-8')

    def revisadas(self, ids):
        self.escribir(self.control['revisiones_ruta'], {'revisadas': ids})

    def entrega(self, etapa, prefijo='entregas', ident=None, fecha=None):
        ident = ident or etapa
        carpeta = f'{prefijo}/{etapa}-{ident}'
        z = self.root / carpeta / 'fuentes.zip'
        z.parent.mkdir(parents=True)
        with zipfile.ZipFile(z, 'x') as archivo:
            archivo.writestr('docs/ejemplo.md', b'fuentes congeladas')
        marker = carpeta + '/manifiesto.json'
        self.escribir(marker, {'tarea': self.control['tarea'], 'id': ident,
                              'etapa': etapa, 'estado': 'entregado',
                              **({'creado_utc': fecha} if fecha is not None else {}),
                              'snapshot': {'ruta': carpeta + '/fuentes.zip',
                                           'sha256': hashlib.sha256(z.read_bytes()).hexdigest()},
                              'archivos': {'docs/ejemplo.md': hashlib.sha256(b'fuentes congeladas').hexdigest()}})
        self.escribir(self.control['estado_ruta'], {'tarea': self.control['tarea'],
                      'estado': 'trabajando', 'etapa_actual': '04', 'ultima_entrega': marker})
        return z

    def test_tres_entregas_entre_sondeos_se_revisan_en_orden(self):
        self.entrega('01')
        self.entrega('02', 'seguimiento/claude_ruta/entregas')
        self.entrega('03')
        for etapa, ids in [('01', []), ('02', ['01']), ('03', ['01', '02'])]:
            self.revisadas(ids)
            observado = s.estado()
            self.assertEqual((observado['estado'], observado['etapa']), ('entrega_candidata', etapa))
        self.revisadas(['01', '02', '03'])
        self.assertEqual(s.estado()['estado'], 'sin_marcador')

    def test_ultima_revisada_no_oculta_anterior_alterada(self):
        archivo = self.entrega('01')
        self.entrega('02')
        self.revisadas(['02'])
        archivo.write_bytes(b'alterado')
        with self.assertRaisesRegex(ValueError, 'hash de snapshot'):
            s.estado()

    def test_candidato_fuera_del_proyecto_rechazado(self):
        self.entrega('01')
        self.escribir(self.control['estado_ruta'], {'tarea': self.control['tarea'],
                      'estado': 'trabajando', 'ultima_entrega': 'entregas/../data/private/marker.json'})
        with self.assertRaises(ValueError):
            s.estado()

    def test_incrementos_misma_etapa_ordenan_por_fecha_no_uuid(self):
        self.entrega('04', ident='z-antigua', fecha='2026-10-22T10:00:00Z')
        self.entrega('04', ident='a-nueva', fecha='2026-10-22T10:01:00+00:00')
        self.assertEqual(s.estado()['entrega_id'], 'z-antigua')
        self.revisadas(['z-antigua'])
        self.assertEqual(s.estado()['entrega_id'], 'a-nueva')
        self.revisadas(['z-antigua', 'a-nueva'])
        self.assertEqual(s.estado()['estado'], 'sin_marcador')

    def test_fecha_normalizada_y_precedencia_etapa(self):
        self.entrega('04', ident='a-nueva', fecha='2026-10-22T10:00:00+00:00')
        self.entrega('04', ident='z-antigua', fecha='2026-10-22T10:30:00+01:00')
        self.entrega('06', fecha='2026-10-21T00:00:00Z')
        self.assertEqual(s.estado()['entrega_id'], 'z-antigua')
        self.revisadas(['z-antigua', 'a-nueva'])
        self.assertEqual(s.estado()['etapa'], '06')

    def test_fecha_presente_invalida_no_se_trata_como_antigua(self):
        for fecha in ('no-fecha', '2026-10-22T10:00:00', 123):
            with self.subTest(fecha=fecha):
                with self.assertRaises(ValueError):
                    s.orden_entrega((self.root/'entregas/04-x/manifiesto.json',
                                    {'etapa': '04', 'creado_utc': fecha}))


if __name__ == '__main__':
    unittest.main()
