import copy
import json
import unittest
from unittest.mock import patch
from draft2model.revision_visual import RevisionLocal
from draft2model.revision_respuestas import ServicioRespuestas
from tests import test_entrada_vision as fixtures


class RespuestasWebTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.EntradaVisionTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.app=RevisionLocal(self.fixture.case.parent);self.service=ServicioRespuestas(self.app)
        self.path=self.fixture.pack();self.response=self.fixture.response(self.path)
        self.caso=self.fixture.case.name;self.fp=self.app.expediente(self.caso)[2]
        self.body={'caso':self.caso,'expediente_sha256':self.fp,'paquete':self.path.parent.name,
            'respuesta_json':json.dumps(self.response),'proveedor_declarado':'Prueba local','modelo_declarado':'Sin proveedor real','modo_prueba':True}

    def register(self):return self.service.registrar(self.body)

    def test_registro_y_traslado_pendiente_sin_procesos(self):
        with patch('subprocess.Popen',side_effect=AssertionError('Sin proveedor ni procesos')):
            item=self.register()
            with self.assertRaises(ValueError):self.service.importar({'caso':self.caso,'expediente_sha256':self.fp,'respuesta':item['id'],
                'sha256_extraccion':item['sha256_extraccion'],'confirmacion_explicita':True})
            # La contingencia declarada del expediente no afirma llamada real a un proveedor.
            declared=self.service.registrar({**self.body,'modo_prueba':False})
            result=self.service.importar({'caso':self.caso,'expediente_sha256':self.fp,'respuesta':declared['id'],
                'sha256_extraccion':declared['sha256_extraccion'],'confirmacion_explicita':True})
        self.assertEqual(item['extraccion']['candidatos'][0]['revision']['estado'],'pendiente')
        self.assertEqual(item['extraccion']['procedencia']['tipo'],'sintetico');self.assertFalse(item['transmision_externa'] or item['aprueba_ingenieria'])
        self.assertEqual(result['estado'],'pendiente_revision');self.assertTrue((self.fixture.case/'extracciones'/result['extraccion']).is_dir())
        self.assertNotIn(str(self.app.raiz),json.dumps(item));self.assertEqual(len(self.service.listar(self.caso,expediente_sha256=self.fp)['versiones']),2)

    def test_respuesta_ajena_y_confirmacion_incompleta_rechazadas(self):
        bad=copy.deepcopy(self.response);bad['solicitud_id']='f'*32
        with self.assertRaises(ValueError):self.service.registrar({**self.body,'respuesta_json':json.dumps(bad)})
        item=self.register();body={'caso':self.caso,'expediente_sha256':self.fp,'respuesta':item['id'],
            'sha256_extraccion':item['sha256_extraccion'],'confirmacion_explicita':False}
        with self.assertRaises(ValueError):self.service.importar(body)
        with self.assertRaises(ValueError):self.service.importar({**body,'confirmacion_explicita':True,'sha256_extraccion':'0'*64})

    def test_alteracion_de_respuesta_o_paquete_invalida_lectura(self):
        item=self.register();target=self.fixture.case/'vision/respuestas'/item['id']/'respuesta_original.json'
        original=target.read_bytes();target.write_bytes(b'[]')
        with self.assertRaises(ValueError):self.service.consultar(self.caso,item['id'],expediente_sha256=self.fp)
        target.write_bytes(original);(self.path.parent/'prompt.txt').write_text('Alterado')
        with self.assertRaises(ValueError):self.service.consultar(self.caso,item['id'],expediente_sha256=self.fp)

    def test_cuarentena_explicita_desde_el_formulario(self):  # R236
        mala=copy.deepcopy(self.response);mala['candidatos'].append({**copy.deepcopy(mala['candidatos'][0]),'id':'C002',
            'evidencia':[{'imagen_id':'REC0001','bbox_imagen_normalizada':[.75,.25,.25,.75]}]})  # bbox invertida
        body={**self.body,'respuesta_json':json.dumps(mala)}
        with self.assertRaisesRegex(ValueError,'cuarentena'):self.service.registrar(body)  # sin decisión: nada se registra
        self.assertEqual(self.service.listar(self.caso,expediente_sha256=self.fp)['versiones'],[])
        item=self.service.registrar({**body,'cuarentena':True})
        self.assertEqual(item['candidatos_en_cuarentena'],1)
        self.assertEqual([c['id'] for c in item['extraccion']['candidatos']],['C001'])
        cob=item['cobertura'][0]
        self.assertEqual((cob['estado'],cob['efectiva']['estado'],cob['efectiva']['recuperados'],cob['efectiva']['en_cuarentena']),
                         ('completa','parcial',1,1))  # declaración intacta; efectiva no se eleva
        self.assertEqual(self.service.consultar(self.caso,item['id'],expediente_sha256=self.fp)['candidatos_en_cuarentena'],1)
        with self.assertRaises(ValueError):self.service.registrar({**body,'cuarentena':'si'})

    def test_rutas_y_campos_no_admitidos(self):
        for changes in ({'paquete':'../x'},{'caso':'../otro'},{'ruta':'C:/privado'}, {'modo_prueba':1},{'modelo_declarado':None}):
            with self.subTest(changes=changes),self.assertRaises((ValueError,OSError)):
                self.service.registrar({**self.body,**changes})

    def test_importacion_interrumpida_no_duplica_y_replay_alterado_se_rechaza(self):
        from draft2model.revision_respuestas import importar_extraccion
        item=self.service.registrar({**self.body,'modo_prueba':False})
        body={'caso':self.caso,'expediente_sha256':self.fp,'respuesta':item['id'],
            'sha256_extraccion':item['sha256_extraccion'],'confirmacion_explicita':True}
        def partial(*args):
            importar_extraccion(*args)
            raise OSError('Interrupción después de publicar')
        with patch('draft2model.revision_respuestas.importar_extraccion',side_effect=partial),self.assertRaises(OSError):
            self.service.importar(body)
        before=list((self.fixture.case/'extracciones').iterdir())
        with patch('draft2model.revision_respuestas.importar_extraccion',side_effect=AssertionError('No repetir')),self.assertRaises(ValueError):
            self.service.importar(body)
        self.assertEqual(before,list((self.fixture.case/'extracciones').iterdir()))
        other=self.service.registrar({**self.body,'modo_prueba':False})
        new={**body,'respuesta':other['id'],'sha256_extraccion':other['sha256_extraccion']}
        accepted=self.service.importar(new)
        (self.fixture.case/'extracciones'/accepted['extraccion']/'version.json').write_text('{}')
        with self.assertRaises(ValueError):self.service.importar(new)
