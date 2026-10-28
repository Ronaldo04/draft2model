"""Claves ficticias; no red, proveedor ni acceso a credenciales del usuario."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from draft2model.credenciales_locales import cargar, estado


class CredencialesTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.file=Path(t.name)/'local.md'
    def escribir(self,text):self.file.write_text(text,encoding='utf-8');return self.file
    def test_carga_literal_sin_evaluar_y_solo_presencia(self):
        data=cargar(self.escribir('# Local\n```env\nGEMINI_API_KEY="FICTICIA-$(no_ejecutar)"\nOPENAI_API_KEY=\n```\n'))
        self.assertEqual(data,{'GEMINI_API_KEY':'FICTICIA-$(no_ejecutar)'})
        self.assertTrue(estado(data)['GEMINI_API_KEY']);self.assertFalse(estado(data)['OPENAI_API_KEY'])
    def test_rechaza_duplicados_variables_codigo_y_bloques(self):
        for text in ['```env\nGEMINI_API_KEY=A\nGEMINI_API_KEY=B\n```',
                     '```env\nPATH=FICTICIA\n```','```env\nprint(1)\n```',
                     '```env\nGEMINI_API_KEY="incompleta\n```','sin bloque',
                     '```env\n```\n```env\n```']:
            with self.subTest(text=text),self.assertRaises(ValueError):cargar(self.escribir(text))
    def test_endpoint_publico_validado_sin_red(self):
        with self.assertRaises(ValueError):cargar(self.escribir('```env\nD2M_COMPATIBLE_ENDPOINT=http://localhost/chat/completions\n```'))
        self.assertIn('D2M_COMPATIBLE_ENDPOINT',cargar(self.escribir('```env\nD2M_COMPATIBLE_ENDPOINT=https://example.com/v1/chat/completions\n```')))
    def test_comprobar_no_muestra_clave_ni_arranca_servidor(self):
        path=Path(__file__).resolve().parents[1]/'scripts/usar_credenciales_locales.py'
        spec=importlib.util.spec_from_file_location('launcher_credenciales_prueba',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        self.escribir('```env\nANTHROPIC_API_KEY=FICTICIA-SECRETA-PRUEBA\n```')
        out=io.StringIO()
        with patch.object(m.subprocess,'call',side_effect=AssertionError('No arrancar')),contextlib.redirect_stdout(out):
            self.assertEqual(m.main(['--archivo',str(self.file),'--comprobar']),0)
        self.assertNotIn('FICTICIA-SECRETA-PRUEBA',out.getvalue())
        result=json.loads(out.getvalue());self.assertFalse(result['envio_realizado']);self.assertTrue(result['presencia_en_archivo']['ANTHROPIC_API_KEY'])
