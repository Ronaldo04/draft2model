"""Persistencia/revisión de modelos fabricados; no contacta ETABS."""
import copy
import json
from pathlib import Path
import unittest
from unittest import mock
from types import SimpleNamespace

from draft2model import revision_modelo as r
from draft2model.ejecucion_modelo import EjecutorVerificado
from draft2model import ejecutor_etabs as e
from tests.test_ejecutor_etabs import EjecutorBase


class RevisionModeloTests(unittest.TestCase):
    def setUp(self):
        self.base = EjecutorBase(); self.base.setUp(); self.addCleanup(self.base.doCleanups)
        executor = EjecutorVerificado(e.configuracion_doble(self.base.corridas, ('no-ejecutar',)))
        prepared = self.base.preparar(executor)
        self.folder = prepared.carpeta
        self.plan = json.loads((self.folder/'plan.json').read_bytes())
        self.config = self.base.aprobar_config()
        self.root = self.base.raiz; self.case = self.config['caso']
        self.target = prepared.destino; self.target.parent.mkdir(parents=True, exist_ok=True)
        raw = b'EDB FABRICADO DE SOFTWARE, NO ES UN ARCHIVO ETABS'
        self.target.write_bytes(raw)
        saved = {'ruta': str(self.target), 'sha256': r._sha(raw)}
        acceptance = {'modo':'doble','aceptada':True,'origen':self.plan['origen'],
            'huella_plan':self.plan['huella_plan'],'guardado':saved,'analisis_ejecutado':False,'aprueba_modelo':False}
        self.write('aceptacion_integracion.json', acceptance)
        names = {s['registra']:s['debe_ser'] for op in self.plan['operaciones'] for s in op.get('salidas',[])}
        self.write('respuesta.json', {'estado':'ok','operacion':'ejecutar_plan','modo_ejecucion':'doble',
            'id_solicitud':prepared.solicitud.id,'datos':{'guardado':saved,'huella_plan':self.plan['huella_plan'],
            'analisis_ejecutado':False,'aprueba_modelo':False},
            'progreso':{'operaciones_ejecutadas':len(self.plan['operaciones']),'mapeo_nombres':names}})
        rows = []
        for op in self.plan['operaciones']:
            rows.append({'orden':op['orden'],'metodo':op['metodo'],'evento':'inicio'})
            rows.append({'orden':op['orden'],'metodo':op['metodo'],'evento':'fin','retorno':0,
                         'salidas':{s['registra']:s['debe_ser'] for s in op.get('salidas',[])}})
        (self.folder/'traza.jsonl').write_bytes(b''.join(r._bytes(x).replace(b'\n',b'')+b'\n' for x in rows))

    def write(self, name, data): (self.folder/name).write_bytes(r._bytes(data))
    def register(self): return r.registrar(self.root,self.case,self.config,self.plan,self.folder)
    def approve(self, model, **changes):
        state = r.consultar(self.root,self.case,model.name)
        opts = dict(huella_esperada=state['huella_modelo'],revisor='Revisor SINTÉTICO',fecha='2026-10-17',
            alcance='Ensayo de revisión de software; sin ingeniería.',controles={k:True for k in r.CONTROLES})
        opts.update(changes)
        return r.aprobar(self.root,self.case,model.name,**opts)

    def test_borrador_no_hereda_aprobacion_y_aprobacion_propia(self):
        model = self.register(); before = {p.name:p.read_bytes() for p in model.iterdir()}
        state = r.consultar(self.root,self.case,model.name)
        self.assertEqual(state['estado'],'pendiente'); self.assertIsNone(state['aprobacion'])
        approval = self.approve(model)
        approved = r.consultar_aprobacion(self.root,self.case,approval.name)
        self.assertEqual(approved['estado'],'aprobado')
        self.assertTrue(approved['origen']['datos_sinteticos'])
        self.assertEqual(before,{p.name:p.read_bytes() for p in model.iterdir()})
        self.target.write_bytes(b'externo modificado tras capturar')
        self.assertEqual(r.consultar_aprobacion(self.root,self.case,approval.name)['estado'],'aprobado')

    def test_alteracion_edb_snapshot_y_geometria_invalidan_aprobacion(self):
        model = self.register(); approval = self.approve(model)
        target = model/'modelo.edb'; original = target.read_bytes(); target.write_bytes(b'alterado')
        with self.assertRaises(ValueError): r.consultar_aprobacion(self.root,self.case,approval.name)
        target.write_bytes(original); self.base.original.write_bytes(b'original geometrico cambiado')
        with self.assertRaises(ValueError): r.consultar_aprobacion(self.root,self.case,approval.name)

    def test_controles_y_huella_explicitos(self):
        model = self.register()
        for changes in ({'controles':{k:True for k in r.CONTROLES[:-1]}}, {'huella_esperada':'0'*64},
                        {'controles':{k:1 for k in r.CONTROLES}}, {'fecha':'2026-02-30'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError): self.approve(model,**changes)

    def test_no_acepta_modelo_cambiado_ni_integracion_fallida(self):
        raw = self.target.read_bytes(); self.target.write_bytes(b'cambiado')
        with self.assertRaises(ValueError): self.register()
        self.target.write_bytes(raw); self.write('revision_integracion_fallida.json',{})
        with self.assertRaises(ValueError): self.register()

    def test_traza_reordenada_o_retorno_no_cero_rechazados(self):
        target = self.folder/'traza.jsonl'; raw = target.read_bytes(); rows = raw.splitlines()
        target.write_bytes(b'\n'.join(rows[2:]+rows[:2])+b'\n')
        with self.assertRaises(ValueError): self.register()
        target.write_bytes(raw.replace(b'"retorno": 0', b'"retorno": 1', 1))
        with self.assertRaises(ValueError): self.register()

    def test_aprobacion_ajena_y_documento_alterado_rechazados(self):
        model = self.register(); approval = self.approve(model)
        target = approval/'aprobacion.json'; data = json.loads(target.read_bytes())
        data['huella_modelo'] = '0'*64; target.write_bytes(r._bytes(data))
        with self.assertRaises(ValueError): r.consultar_aprobacion(self.root,self.case,approval.name)

    def test_catalogo_informativo_nuevo_no_invalida_modelo_historico(self):
        model=self.register();approval=self.approve(model)
        regenerated=copy.deepcopy(self.plan)
        regenerated['pendientes']=[{'capacidad':'nueva','motivo':'Información de otra versión del programa'}]
        with mock.patch.object(r,'generar_plan',return_value=SimpleNamespace(datos=regenerated)):
            self.assertEqual(r.consultar_aprobacion(self.root,self.case,approval.name)['estado'],'aprobado')
        regenerated['operaciones'][0]['metodo']='cPointObj.GetNameList'
        with mock.patch.object(r,'generar_plan',return_value=SimpleNamespace(datos=regenerated)):
            with self.assertRaises(ValueError):r.consultar_aprobacion(self.root,self.case,approval.name)


if __name__ == '__main__': unittest.main()
