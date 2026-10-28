"""Opt-in web de API y puente de masa conservada: solo transporte local sintético."""
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from draft2model.revision_lecturas import ErrorLecturas, ServicioLecturas
from draft2model.revision_ejecucion import _bytes, _sha
from tests import test_revision_lecturas as fixtures

MASS = {'unidades':'kN_m_C','retorno':0,'numero_resultados':0,
        **{k:[] for k in ('point_elements','mass_sources','U1','U2','U3','R1','R2','R3','observaciones')}}

class MasaWeb267Tests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.LecturasWebTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.service, self.caso = self.f.service, self.f.caso
        script = self.f.fixture.command[1]
        from pathlib import Path
        path = Path(script)
        text = path.read_text(encoding='utf-8')
        text = text.replace("r.write_text(json.dumps(out),encoding='utf-8')",
            "if 'resultados_api' in s:out['datos']['resultados_api']={'AssembledJointMass':"+repr(MASS)+"}\n"
            "r.write_text(json.dumps(out),encoding='utf-8')")
        path.write_text(text, encoding='utf-8')

    def accepted(self, opt=True):
        prep = self.f.prepare(**({'resultados_api':['AssembledJointMass']} if opt else {}))
        self.f.execute(prep); result = self.f.finish(prep)
        self.assertEqual(result['estado'], 'aceptado', result)
        return result

    def rehash(self, result, mutate):
        record, state = self.service._leer(self.caso, result['id'])
        folder = self.f.fixture.work/result['lectura_id']
        response = json.loads((folder/'respuesta.json').read_bytes()); mutate(response)
        (folder/'respuesta.json').write_bytes(_bytes(response))
        receipt = json.loads((folder/'aceptacion_lectura.json').read_bytes())
        receipt['sha256_respuesta'] = _sha(_bytes(response))
        (folder/'aceptacion_lectura.json').write_bytes(_bytes(receipt))
        work = self.service._carpeta(self.caso, result['id'])
        web = json.loads((work/'aceptacion_web.json').read_bytes())
        web['archivos'] = {k:_sha((folder/k).read_bytes()) for k in web['archivos']}
        (work/'aceptacion_web.json').write_bytes(_bytes(web))
        self.service._estado(record,state,huella_aceptacion=_sha(_bytes(web)),sha256_respuesta=receipt['sha256_respuesta'])

    def test_opt_in_replay_persistencia_y_payload_anterior(self):
        with patch('subprocess.Popen',side_effect=AssertionError('No motor en preparar')):
            old = self.f.prepare()
            self.assertNotIn('resultados_api', old)
            with self.assertRaises(ErrorLecturas):self.f.prepare(resultados_api=['AssembledJointMass'])
        self.f.body['clave_solicitud'] = uuid4().hex
        result = self.accepted()
        self.assertEqual(result['resultados_api'], ['AssembledJointMass'])
        self.assertNotIn('resultados_api', result['datos_tablas'])
        record, _ = self.service._leer(self.caso,result['id'])
        prep = json.loads((self.service._carpeta(self.caso,result['id'])/'preparacion.json').read_bytes())
        request = json.loads((self.f.fixture.work/result['lectura_id']/'solicitud.json').read_bytes())
        for value in (record, prep, request):self.assertEqual(value['resultados_api'], ['AssembledJointMass'])
        self.assertEqual(ServicioLecturas(self.f.app,self.f.factory).consultar(self.caso,result['id']), result)
        self.assertEqual(json.loads(self.service.respuesta_bytes(self.caso,result['id'],expediente_sha256=result['expediente_sha256']))['datos']['resultados_api']['AssembledJointMass'], MASS)

    def test_opt_in_invalido_y_preparacion_rehashada(self):
        for value in (None, [], ['AssembledJointMass']*2, ['Otro'], 'AssembledJointMass', [True], [{}]):
            with self.subTest(value=value), self.assertRaises(ErrorLecturas):self.f.prepare(resultados_api=value)
        prepared = self.f.prepare(resultados_api=['AssembledJointMass'])
        record, state = self.service._leer(self.caso,prepared['id'])
        path = self.service._carpeta(self.caso,prepared['id'])/'preparacion.json'
        prep = json.loads(path.read_bytes()); prep.pop('resultados_api'); path.write_bytes(_bytes(prep))
        self.service._estado(record,state,huella_preparacion=_sha(_bytes(prep)))
        self.assertFalse(self.service.consultar(self.caso,prepared['id'])['vigente'])

    def test_api_no_solicitada_y_datos_tipados_alterados_rehashados(self):
        result = self.accepted(False)
        self.rehash(result,lambda response:response['datos'].update(resultados_api={'AssembledJointMass':MASS}))
        self.assertFalse(self.service.consultar(self.caso,result['id'])['vigente'])
        self.f.body['clave_solicitud'] = uuid4().hex
        result = self.accepted()
        self.rehash(result,lambda response:response['datos']['resultados_api']['AssembledJointMass'].update(numero_resultados=True))
        self.assertFalse(self.service.consultar(self.caso,result['id'])['vigente'])
        for invalid in ({}, {'AssembledJointMass':MASS,'BaseReact':{}}, {'AssembledJointMass':{}}):
            with self.subTest(api=invalid):
                self.rehash(result,lambda response:response['datos'].update(resultados_api=invalid))
                self.assertFalse(self.service.consultar(self.caso,result['id'])['vigente'])

    def test_puente_rechaza_doble_y_referencias_ajenas(self):
        result = self.accepted()
        args = dict(lectura_id=result['lectura_id'], sha256_respuesta=result['sha256_respuesta'],
            analisis=result['analisis'],sha256_edb=result['sha256_edb'],expediente_sha256=result['expediente_sha256'])
        with patch('subprocess.Popen',side_effect=AssertionError('Puente no abre motor')):
            with self.assertRaises(ErrorLecturas):self.service.captura_masa_para_informe(self.caso,result['id'],**args)
        # La rama real se prueba con evidencia controlada en memoria; no se etiqueta un doble conservado como real.
        record, _ = self.service._leer(self.caso,result['id'])
        real = {**record,'modo_ejecucion':'real','datos_sinteticos':False}
        proof = {'modo':'real','datos_sinteticos':False,'sha256_edb_analizado':args['sha256_edb']}
        with patch.object(self.service,'_leer',return_value=(real,'aceptado')), \
             patch.object(self.service,'_aceptada',return_value=(b'',{'resultados_api':{'AssembledJointMass':MASS}})) as accepted, \
             patch.object(self.service,'_revalidar',return_value=(proof,None,None)), \
             patch('subprocess.Popen',side_effect=AssertionError('No motor')):
            value = self.service.captura_masa_para_informe(self.caso,result['id'],**args)
            self.assertEqual(value, {'captura':MASS,'recibo':{'lectura_id':args['lectura_id'],
                'corrida_analisis_id':args['analisis'],'sha256_edb':args['sha256_edb'],
                'sha256_respuesta':args['sha256_respuesta'],'modo':'real'}})
            self.assertEqual(accepted.call_count,1)
            for field in args:
                with self.subTest(field=field), self.assertRaises(ErrorLecturas):
                    self.service.captura_masa_para_informe(self.caso,result['id'],**{**args,field:'0'*len(args[field])})
            with patch.object(self.service,'_aceptada',side_effect=ErrorLecturas('aceptacion_web_alterada')):
                with self.assertRaisesRegex(ErrorLecturas,'aceptacion_web_alterada'):
                    self.service.captura_masa_para_informe(self.caso,result['id'],**args)
            with patch.object(self.service,'_leer',return_value=(real,'preparado')):
                with self.assertRaises(ErrorLecturas):self.service.captura_masa_para_informe(self.caso,result['id'],**args)

if __name__ == '__main__':unittest.main()
