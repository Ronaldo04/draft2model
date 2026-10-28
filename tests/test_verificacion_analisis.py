"""Verificación pública de análisis conservado, sin resultado ni motor."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from draft2model.evidencia_analisis import ErrorEvidenciaAnalisis, verificar_analisis_aceptado
from tests.fixture_etabs import extraer_evidencia

CASO='demo-integrada-sintetica';ANALISIS='adf97fbc232141e8ae687872c0d71232'


class VerificacionAnalisisTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.bundle=extraer_evidencia(Path(temp.name).resolve()/'fixture')
        self.root=self.bundle/'private';self.case=self.root/CASO
        self.run=self.case/'analisis_etabs'/ANALISIS
        shutil.copytree(self.bundle/'analisis'/ANALISIS,self.run)

    def verify(self):return verificar_analisis_aceptado(self.root,CASO,self.run)

    def test_proyeccion_controlada_sin_escrituras_ni_rutas(self):
        before={p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result=self.verify()
        self.assertEqual(result['corrida_id'],ANALISIS);self.assertEqual(result['casos'],['EST'])
        self.assertEqual(result['estados_casos'],{'EST':4})
        self.assertTrue(result['analisis_ejecutado']);self.assertFalse(result['aprueba_resultados'])
        self.assertNotIn(str(self.bundle),json.dumps(result));self.assertNotIn('id_proceso',json.dumps(result))
        self.assertEqual(before,{p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_rechaza_corrida_externa_caso_ajeno_y_artefactos_alterados(self):
        for path,case in ((self.bundle/'analisis'/ANALISIS,CASO),(self.run,'otro'),(self.case/'analisis_etabs'/'..',CASO)):
            with self.subTest(path=path,case=case),self.assertRaises(ErrorEvidenciaAnalisis):
                verificar_analisis_aceptado(self.root,case,path)
        for name in ('aceptacion_analisis.json','solicitud.json','respuesta.json','entrada.edb','analizado.edb'):
            with self.subTest(name=name):
                path=self.run/name;raw=path.read_bytes();path.write_bytes(b'alterado')
                with self.assertRaises(ErrorEvidenciaAnalisis):self.verify()
                path.write_bytes(raw)

    def test_aprobacion_origen_y_tipos_malformados_rechazados(self):
        result=self.verify();approval=self.case/'aprobaciones_modelo'/result['aprobacion_id']/'aprobacion.json'
        raw=approval.read_bytes();value=json.loads(raw);value['controles']=list(value['controles'])
        approval.write_text(json.dumps(value),encoding='utf-8')
        with self.assertRaises(ErrorEvidenciaAnalisis):self.verify()
        approval.write_bytes(raw)
        manifest=json.loads((self.case/'expediente.json').read_bytes());original=self.case/manifest['archivos'][0]['archivo']
        original.write_bytes(b'original alterado')
        with self.assertRaises(ErrorEvidenciaAnalisis) as ctx:self.verify()
        self.assertNotIn(str(self.bundle),str(ctx.exception))


if __name__=='__main__':unittest.main()
