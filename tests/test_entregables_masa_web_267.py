"""Ciclo documental con fuentes de masa sustituidas, sin atribuir prueba de motor."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch

from tests import test_revision_entregables as fx
from tests.test_informe_contenido_261 import BASE as CONTENT
from tests.test_informe_masa_nativa_263 import BASE as NATIVE
from tests.test_informe_masa_nativa_263 import EVID,RES


class EntregablesMasa267Tests(unittest.TestCase):
    setUp=fx.EntregablesTests.setUp
    archivo=fx.EntregablesTests.archivo

    def fuentes(self):
        target=self.app.raiz/fx.CASO/'analisis_etabs'/fx.ANALISIS
        shutil.copytree(self.bundle/'analisis'/fx.ANALISIS,target)
        self.body['analisis']=fx.ANALISIS
        _,_,_,ev=self.service._fuente(fx.CASO,fx.RESULTADO,self.fp,fx.ANALISIS)
        content=copy.deepcopy(CONTENT)
        content.update(caso_id=fx.CASO,modelo_id=ev['modelo']['modelo_id'])
        native=copy.deepcopy(NATIVE)
        native.update(caso_id=fx.CASO,corrida_analisis_id=fx.ANALISIS,
                      sha256_edb=ev['analisis']['sha256_edb_analizado'])
        self.content,self.native=content,native
        for name,value in (('_contenido_masa',content),('_masa_nativa',native)):
            mock=patch('draft2model.informe.'+name,
                side_effect=lambda source,*args,v=value:copy.deepcopy(v) if source is not None else None)
            mock.start();self.addCleanup(mock.stop)
        self.ref={'trabajo':'d'*32,'lectura_id':native['lectura_id'],'sha256_respuesta':native['sha256_respuesta']}

    def test_solicitud_optativa_estricta_y_sin_analisis(self):
        invalid=[{'contenido_masa':v} for v in (False,1,None,'true',{})]
        invalid += [{'masa_nativa':v} for v in (None,{}, {'ruta':'x'},
                    {'trabajo':'d'*32,'lectura_id':'a'*32,'sha256_respuesta':'z'*64})]
        invalid += [{'contenido_masa':True}, {'masa_nativa':{'trabajo':'d'*32,'lectura_id':'a'*32,'sha256_respuesta':'b'*64}}]
        for change in invalid:
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.service.crear({**self.body,**change})

    def test_referencias_persisten_descarga_aprobacion_e_invalidacion(self):
        self.fuentes()
        draft=self.service.crear({**self.body,'contenido_masa':True,'masa_nativa':self.ref})
        self.assertIs(draft['contenido_masa_seleccionado'],True)
        self.assertEqual(draft['masa_nativa_seleccionada'],self.ref)
        self.assertEqual(draft['contenido_masa'],self.content)
        self.assertEqual(draft['masa_nativa'],self.native)
        report=json.loads(self.archivo(draft['id'],'json'))
        self.assertEqual(report['masa_nativa'],self.native)
        child=self.service.aprobar({'caso':fx.CASO,'version':draft['id'],'expediente_sha256':self.fp,
            'sha256_informe':draft['archivos']['informe.json'],'revisor_declarado':'Prueba sintética documental',
            'fecha':'2026-10-22','motivo':'Prueba de propagación, no ingeniería.','confirmacion_explicita':True})
        self.assertEqual(child['masa_nativa_seleccionada'],self.ref)
        self.assertIs(child['contenido_masa_seleccionado'],True)
        self.assertTrue(self.archivo(child['id']).startswith(b'%PDF'))
        with patch('draft2model.informe._masa_nativa',side_effect=ValueError('Captura modificada')):
            for ident in (draft['id'],child['id']):
                with self.subTest(ident=ident),self.assertRaises(ValueError):self.archivo(ident)

    def test_quitar_referencia_no_desvincula_silenciosamente_los_datos(self):
        self.fuentes()
        draft=self.service.crear({**self.body,'masa_nativa':self.ref})
        p=self.app.raiz/fx.CASO/'informes'/draft['id']/'paquete.json'
        meta=json.loads(p.read_bytes());meta.pop('masa_nativa');p.write_text(json.dumps(meta),encoding='utf-8')
        with self.assertRaises(ValueError):self.archivo(draft['id'],'json')


class PuenteFuenteMasa267Tests(unittest.TestCase):
    def test_fuente_web_usa_servicio_y_modelo_del_analisis(self):
        from draft2model.informe import _masa_nativa
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);case=root/RES['caso_id']
            folder=case/'modelos_construidos'/EVID['modelo']['modelo_id'];folder.mkdir(parents=True)
            (folder/'configuracion.json').write_text(json.dumps({'geometria_origen':{'version_id':'geo'}}))
            ref={'caso':RES['caso_id'],'expediente_sha256':'f'*64,'trabajo':'d'*32,
                 'lectura_id':NATIVE['lectura_id'],'sha256_respuesta':NATIVE['sha256_respuesta']}
            receipt={k:NATIVE[k] for k in ('lectura_id','sha256_respuesta','corrida_analisis_id','sha256_edb')}
            capture={'captura':'marcador de prueba'}
            loader=Mock(return_value={'recibo':receipt,'captura':capture})
            app=SimpleNamespace(raiz=root,lecturas=SimpleNamespace(captura_masa_para_informe=loader))
            book={'masa_total_kn_s2_m':30.,'contribuciones':{
                k:{'masa_kn_s2_m':v} for k,v in NATIVE['libro']['contribuciones_kn_s2_m'].items()}}
            with patch('draft2model.revision_modelo.consultar'), \
                 patch('draft2model.revision_modelo.carpeta_caso',return_value=case), \
                 patch('draft2model.gestion_geometria.consultar_version',return_value=SimpleNamespace(geometria='geo')), \
                 patch('draft2model.malla_preparacion.preparar_malla',return_value='malla'), \
                 patch('draft2model.validacion_geometria.validar_geometria',return_value='validada'), \
                 patch('draft2model.libro_masa.libro_masa',return_value=book), \
                 patch('draft2model.libro_masa.contrastar_masa_nativa',return_value=NATIVE['contraste']) as contrast:
                value=_masa_nativa({'app':app,**ref},RES,EVID)
            self.assertEqual(value,NATIVE)
            loader.assert_called_once_with(RES['caso_id'],ref['trabajo'],lectura_id=ref['lectura_id'],
                sha256_respuesta=ref['sha256_respuesta'],expediente_sha256=ref['expediente_sha256'],
                analisis=EVID['analisis']['corrida_id'],sha256_edb=EVID['analisis']['sha256_edb_analizado'])
            self.assertIs(contrast.call_args.args[0],capture)
            self.assertFalse((case/'lecturas_analisis').exists())

    def test_lectura_cli_doble_no_se_publica_como_masa_nativa(self):
        from draft2model.informe import _masa_nativa
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/RES['caso_id']/'lecturas_analisis'/NATIVE['lectura_id'];folder.mkdir(parents=True)
            (folder/'aceptacion_lectura.json').write_text(json.dumps({'aceptada':True,'modo':'doble','lectura_id':NATIVE['lectura_id']}))
            (folder/'respuesta.json').write_bytes(b'{}')
            with patch('draft2model.revision_modelo.carpeta_caso',return_value=Path(temp)/RES['caso_id']),self.assertRaises(ValueError):
                _masa_nativa({'raiz':temp,'caso':RES['caso_id'],'lectura_id':NATIVE['lectura_id']},RES,EVID)


if __name__=='__main__':unittest.main()
