"""Aprobación documental HTTP con evidencia portable sintética; transporte en memoria."""
import json
import unittest
from tests import test_revision_entregables_http as fixtures


class AprobacionInformeHTTPTests(unittest.TestCase):
    setUp=fixtures.EntregablesHTTPTests.setUp
    request=fixtures.EntregablesHTTPTests.request
    create=fixtures.EntregablesHTTPTests.create
    url=fixtures.EntregablesHTTPTests.url

    def body_aprobar(self,draft):return {'caso':fixtures.CASO,'version':draft['id'],'expediente_sha256':self.fp,
        'sha256_informe':draft['archivos']['informe.json'],'revisor_declarado':'Revisor SINTÉTICO documental',
        'fecha':'2026-10-18','motivo':'Prueba de revisión exclusivamente documental.','confirmacion_explicita':True}

    def test_hija_historial_descargas_y_padre_intacto(self):
        draft=self.create();folder=self.app.raiz/fixtures.CASO/'informes'/draft['id'];before={p.name:p.read_bytes() for p in folder.iterdir()}
        status,raw,_=self.request('POST','/api/informe/aprobar',self.body_aprobar(draft));self.assertEqual(status,201,raw);child=json.loads(raw)
        self.assertNotEqual(child['id'],draft['id']);self.assertEqual(child['estado'],'aprobado');self.assertEqual(child['padre']['id'],draft['id'])
        self.assertEqual(child['padre']['sha256_informe'],draft['archivos']['informe.json'])
        self.assertFalse(child['aprueba_resultados']);self.assertEqual(child['revision_resultados'],'pendiente');self.assertEqual(child['conformidad_normativa'],'no_evaluada')
        self.assertEqual(before,{p.name:p.read_bytes() for p in folder.iterdir()})
        status,raw,_=self.request('GET',self.url('informes'));self.assertEqual(status,200);self.assertEqual({x['estado'] for x in json.loads(raw)['versiones']},{'borrador','aprobado'})
        for fmt in ('pdf','json'):
            status,raw,headers=self.request('GET',self.url('informe/archivo',version=child['id'],formato=fmt));self.assertEqual(status,200)
            self.assertIn(child['id'],headers['Content-Disposition']);self.assertEqual(headers['Cache-Control'],'no-store')
            if fmt=='pdf':self.assertTrue(raw.startswith(b'%PDF'))
            else:self.assertEqual(json.loads(raw)['revision']['estado'],'aprobado')
        self.assertEqual(self.create()['estado'],'borrador')
        self.assertEqual(self.request('POST','/api/informe/aprobar',self.body_aprobar(child))[0],409)

    def test_identidad_fecha_confirmacion_y_sha_exactos(self):
        draft=self.create();body=self.body_aprobar(draft)
        for change in ({'confirmacion_explicita':False},{'confirmacion_explicita':1},{'sha256_informe':'0'*64},
                       {'fecha':'2026-02-30'},{'revisor_declarado':''},{'motivo':''},{'ruta':'C:/privado'},
                       {'expediente_sha256':'0'*64},{'version':'../otro'}):
            with self.subTest(change=change):
                status,raw,_=self.request('POST','/api/informe/aprobar',{**body,**change});self.assertEqual(status,409,raw);self.assertNotIn(str(self.app.raiz).encode(),raw)
        self.assertEqual(len(list((self.app.raiz/fixtures.CASO/'informes').iterdir())),1)

    def test_origen_sesion_fuentes_y_padre_alterados(self):
        draft=self.create();body=self.body_aprobar(draft)
        for headers in ({'X-Revision-Session':'otro'},{'Origin':'https://ajeno.invalid'}):
            self.assertEqual(self.request('POST','/api/informe/aprobar',body,headers=headers)[0],403)
        status,raw,_=self.request('POST','/api/informe/aprobar',body);self.assertEqual(status,201);child=json.loads(raw)
        path=self.app.raiz/fixtures.CASO/'informes'/draft['id']/'informe.html';path.write_bytes(path.read_bytes()+b'<!--alterado-->')
        self.assertEqual(self.request('POST','/api/informe/aprobar',body)[0],409)
        self.assertEqual(self.request('GET',self.url('informe/archivo',version=child['id'],formato='pdf'))[0],409)
        other=self.create();source=next((self.app.raiz/fixtures.CASO/'originales').iterdir());source.write_bytes(b'SINTETICO ALTERADO')
        self.assertEqual(self.request('POST','/api/informe/aprobar',self.body_aprobar(other))[0],409)

if __name__=='__main__':unittest.main()
