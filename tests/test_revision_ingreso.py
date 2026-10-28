import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from PIL import Image
from draft2model.revision_visual import RevisionLocal
from tests import test_revision_visual as httpfixtures


class IngresoWebTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.app=RevisionLocal(Path(temp.name).resolve()/'private')
        out=io.BytesIO();Image.new('RGB',(80,60),'white').save(out,format='PNG');self.raw=out.getvalue()
        self.body={'caso':'ingreso-web','clave_solicitud':'a'*32,'uso_autorizado':True,'provisional_fuera_alcance':False,
            'archivos':[{'nombre':'plano.png','contenido_base64':base64.b64encode(self.raw).decode()}]}
        self.server=SimpleNamespace(revision=self.app,token='prueba',origen='http://127.0.0.1:8766')

    def request(self,*args,**kwargs):return httpfixtures.HTTPRevisionTests.request(self,*args,**kwargs)

    def test_registro_replay_preserva_original_y_rechaza_cambios(self):
        with patch('subprocess.Popen',side_effect=AssertionError('Ingreso local sin procesos')):
            first=self.app.ingreso.registrar(self.body);again=self.app.ingreso.registrar(self.body)
        self.assertEqual(first,again);self.assertEqual(first['resumen']['paginas_renderizadas'],1)
        self.assertFalse(first['aprueba_ingenieria'] or first['transmision_externa'])
        original=self.app.raiz/'ingreso-web/originales/lamina-0001.png'
        self.assertEqual(original.read_bytes(),self.raw)
        with self.assertRaises(ValueError):self.app.ingreso.registrar({**self.body,'clave_solicitud':'b'*32})
        original.write_bytes(b'alterado')
        with self.assertRaises(ValueError):self.app.ingreso.registrar(self.body)

    def test_rechazos_sin_caso_parcial(self):
        bad=[]
        for name in ('../x.png','C:\\x.png','CON.png','a.exe','a.png '):
            body=copy.deepcopy(self.body);body['archivos'][0]['nombre']=name;bad.append(body)
        bad += [{**self.body,'uso_autorizado':False},{**self.body,'uso_autorizado':1},
                {**self.body,'caso':'../otro'}, {**self.body,'archivos':self.body['archivos']*2},
                {**self.body,'archivos':self.body['archivos']+[{**self.body['archivos'][0],'nombre':'otra.png'}]},
                {**self.body,'archivos':[{'nombre':'x.png','contenido_base64':'!!!!'}]}]
        for body in bad:
            with self.subTest(body=body),self.assertRaises((ValueError,OSError)):self.app.ingreso.registrar(body)
        self.assertFalse((self.app.raiz/'ingreso-web').exists())
        self.assertFalse(self.app.raiz.exists() and list(self.app.raiz.glob('.carga-*')))

    def test_firma_pdf_sin_lectura_se_conserva_como_error_documental(self):
        body=copy.deepcopy(self.body);body['archivos']=[{'nombre':'danado.pdf','contenido_base64':base64.b64encode(b'%PDF-invalid').decode()}]
        result=self.app.ingreso.registrar(body)
        self.assertEqual(result['resumen']['archivos_con_error'],1)
        self.assertTrue(result['documentos'][0]['con_error']);self.assertNotIn(str(self.app.raiz),json.dumps(result))
        self.assertEqual((self.app.raiz/'ingreso-web/originales/lamina-0001.pdf').read_bytes(),b'%PDF-invalid')

    def test_http_autorizacion_y_registro_nuevo(self):
        self.assertEqual(self.request('POST','/api/ingreso/registrar',self.body,headers={'X-Revision-Session':'otro'})[0],403)
        self.assertEqual(self.request('POST','/api/ingreso/registrar',{**self.body,'ruta':'C:/privado'})[0],409)
        status,raw,_=self.request('POST','/api/ingreso/registrar',self.body)
        self.assertEqual(status,201,raw);self.assertEqual(json.loads(raw)['caso'],'ingreso-web')
        self.assertNotIn(str(self.app.raiz),raw.decode())
        status,raw,_=self.request('GET','/api/documentos?caso=ingreso-web')
        self.assertEqual(status,200,raw);self.assertEqual(json.loads(raw)['documentos'][0]['paginas'],1)

    def test_revision_alterada_y_tamano_no_se_acreditan(self):
        with patch('draft2model.revision_ingreso.MAX_ARCHIVO',3):
            with self.assertRaises(ValueError):self.app.ingreso.registrar(self.body)
        result=self.app.ingreso.registrar(self.body)
        path=self.app.raiz/'ingreso-web/revision_documental'/result['revision_documental']/'revision.json'
        path.write_bytes(b'[]')
        status,raw,_=self.request('POST','/api/ingreso/registrar',self.body)
        self.assertEqual(status,409,raw);self.assertNotIn(str(self.app.raiz),raw.decode())

    def test_replay_contrasta_bytes_enviados_aun_con_registros_rehashados(self):
        result=self.app.ingreso.registrar(self.body);folder=self.app.raiz/'ingreso-web'
        output=io.BytesIO();Image.new('RGB',(80,60),'red').save(output,format='PNG');changed=output.getvalue()
        original=folder/'originales/lamina-0001.png';original.write_bytes(changed)
        manifest_path=folder/'expediente.json';manifest=json.loads(manifest_path.read_bytes())
        manifest['archivos'][0].update(sha256=hashlib.sha256(changed).hexdigest(),bytes=len(changed))
        manifest_path.write_text(json.dumps(manifest));manifest_sha=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        report_path=folder/'revision_documental'/result['revision_documental']/'revision.json'
        report=json.loads(report_path.read_bytes());report['expediente_sha256']=manifest_sha;report_path.write_text(json.dumps(report))
        receipt_path=folder/'ingreso_web.json';receipt=json.loads(receipt_path.read_bytes())
        receipt.update(expediente_sha256=manifest_sha,revision_sha256=hashlib.sha256(report_path.read_bytes()).hexdigest());receipt_path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError,'selección enviada'):self.app.ingreso.registrar(self.body)
