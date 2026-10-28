from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from draft2model.orquestacion import RegistroCorridas,ErrorCorrida


class CorridasTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.case=self.root/'demo';self.case.mkdir()
        (self.case/'config.json').write_text('{}')
        self.r=RegistroCorridas(self.root)

    def crear(self): return self.r.crear('demo','analisis',['config.json'])

    def test_recorrido_persistencia_e_invalidacion(self):
        ident=self.crear();self.r.iniciar(ident)
        (self.case/'resultados.json').write_text('{"motor":"simulado"}')
        data=self.r.finalizar(ident,['resultados.json'])
        self.assertEqual(data['estado'],'completada');self.assertTrue(data['vigente'])
        self.assertEqual(RegistroCorridas(self.root).consultar(ident)['estado'],'completada')
        (self.case/'config.json').write_text('{"cambio":true}')
        self.assertFalse(self.r.consultar(ident)['vigente'])
        with self.assertRaises(ErrorCorrida):self.r.iniciar(ident)

    def test_un_motor_incluso_con_dos_clientes(self):
        a,b=self.crear(),self.crear()
        def start(ident):
            try:RegistroCorridas(self.root).iniciar(ident);return True
            except ErrorCorrida:return False
        with ThreadPoolExecutor(2) as pool:values=list(pool.map(start,[a,b]))
        self.assertEqual(sum(values),1)

    def test_recuperacion_no_reintenta_y_exige_motor_detenido(self):
        a,b=self.crear(),self.crear();self.r.iniciar(a)
        with self.assertRaises(ErrorCorrida):self.r.recuperar(a,motor_detenido_declarado=False,motivo='timeout')
        with self.assertRaises(ErrorCorrida):self.r.iniciar(b)
        self.assertEqual(self.r.recuperar(a,motor_detenido_declarado=True,motivo='Motor inspeccionado, sin trabajo activo')['estado'],'interrumpida')
        self.r.iniciar(b)

    def test_fuente_cambiada_bloquea_terminar_hasta_registrar_fallo(self):
        a=self.crear();self.r.iniciar(a)
        (self.case/'config.json').write_text('cambio');(self.case/'out.json').write_text('{}')
        with self.assertRaises(ErrorCorrida):self.r.finalizar(a,['out.json'])
        self.assertEqual(self.r.fallar(a,'Entrada modificada')['estado'],'fallida')

    def test_rutas_invalidas_sin_sobrescribir_entradas(self):
        for case,paths in (('../fuera',['config.json']),('demo',['../fuera']),('demo',['config.json','config.json'])):
            with self.subTest(case=case),self.assertRaises(ErrorCorrida):self.r.crear(case,'analisis',paths)
        a=self.crear();self.r.iniciar(a)
        with self.assertRaises(ErrorCorrida):self.r.finalizar(a,['config.json'])
