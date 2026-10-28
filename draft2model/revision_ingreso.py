"""Ingreso local de bytes del navegador; originales nuevos y revisión documental."""
import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from .ingreso import registrar_expediente, file_hash, EXTENSIONS, RESERVED
from .revision_documental import revisar_expediente
from .gestion_extraccion import json_desde_bytes

MAX_ARCHIVO=16*1024*1024
MAX_TOTAL=48*1024*1024
MAX_SOLICITUD=65*1024*1024


class ServicioIngreso:
    def __init__(self,app):self.app=app

    def registrar(self,body):
        try:return self._registrar(body)
        except (OSError,KeyError,TypeError,RuntimeError):
            raise ValueError('Ingreso o evidencia documental inválidos; comprueba la selección y el expediente.') from None

    def _registrar(self,body):
        fields={'caso','clave_solicitud','uso_autorizado','provisional_fuera_alcance','archivos'}
        if (not isinstance(body,dict) or set(body)!=fields or body['uso_autorizado'] is not True
                or type(body['provisional_fuera_alcance']) is not bool
                or not isinstance(body['caso'],str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,63}',body['caso'])
                or body['caso'].upper() in RESERVED or not isinstance(body['clave_solicitud'],str)
                or not re.fullmatch('[0-9a-f]{32}',body['clave_solicitud'])
                or not isinstance(body['archivos'],list) or not 1<=len(body['archivos'])<=20):
            raise ValueError('Ingreso incompleto o sin autorización declarada.')
        decoded=[];names=set();total=0
        for item in body['archivos']:
            if not isinstance(item,dict) or set(item)!={'nombre','contenido_base64'}:raise ValueError('Archivo inválido.')
            name,encoded=item['nombre'],item['contenido_base64']
            if (not isinstance(name,str) or not 1<=len(name)<=150 or name in ('.','..')
                    or any(c in name for c in '/\\:<>"|?*') or any(ord(c)<32 for c in name)
                    or name.rstrip(' .')!=name or Path(name).stem.upper() in RESERVED
                    or Path(name).suffix.lower() not in EXTENSIONS or name.casefold() in names
                    or not isinstance(encoded,str) or len(encoded)>4*((MAX_ARCHIVO+2)//3)):
                raise ValueError('Nombre, formato o tamaño de archivo inválido.')
            try:raw=base64.b64decode(encoded,validate=True)
            except (ValueError,binascii.Error):raise ValueError('Contenido base64 inválido.') from None
            total+=len(raw)
            if not raw or len(raw)>MAX_ARCHIVO or total>MAX_TOTAL:raise ValueError('Archivos fuera del límite de ingreso.')
            names.add(name.casefold());decoded.append((name,raw))
        signature=hashlib.sha256(json.dumps(body,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        with self.app.lock:
            root=self.app.raiz
            if root.resolve()!=root:raise ValueError('Raíz enlazada.')
            root.mkdir(parents=True,exist_ok=True);target=root/body['caso']
            if os.path.lexists(target):
                if target.resolve()!=target:raise ValueError('Destino enlazado.')
                receipt=target/'ingreso_web.json'
                if receipt.resolve()!=receipt:raise ValueError('Registro enlazado.')
                meta=json_desde_bytes(receipt.read_bytes(),'ingreso')
                if (not isinstance(meta,dict) or set(meta)!={'clave_solicitud','sha256_solicitud','expediente_sha256','revision_documental','revision_sha256'}
                        or meta['clave_solicitud']!=body['clave_solicitud'] or meta['sha256_solicitud']!=signature):
                    raise ValueError('El expediente ya existe; no se sobrescribe.')
                return self._respuesta(body['caso'],meta,decoded,body['provisional_fuera_alcance'])
            with tempfile.TemporaryDirectory(prefix='.carga-',dir=root) as temporal:
                stage=Path(temporal).resolve();sources=stage/'entradas';sources.mkdir()
                paths=[]
                for name,raw in decoded:
                    path=sources/name;path.write_bytes(raw);paths.append(path)
                manifest=registrar_expediente(body['caso'],paths,stage/'casos',uso_autorizado=True,
                    provisional_fuera_alcance=body['provisional_fuera_alcance'])
                report=revisar_expediente(manifest)
                meta={'clave_solicitud':body['clave_solicitud'],'sha256_solicitud':signature,
                      'expediente_sha256':file_hash(manifest),'revision_documental':report.parent.name,'revision_sha256':file_hash(report)}
                (manifest.parent/'ingreso_web.json').write_text(json.dumps(meta),encoding='utf-8')
                if os.path.lexists(target):raise ValueError('El expediente ya existe; no se sobrescribe.')
                manifest.parent.rename(target)
            return self._respuesta(body['caso'],meta,decoded,body['provisional_fuera_alcance'])

    def _respuesta(self,caso,meta,decoded,provisional):
        folder,manifest,fingerprint=self.app.expediente(caso)
        if fingerprint!=meta['expediente_sha256']:raise ValueError('Expediente cambiado desde el ingreso.')
        entries=manifest['archivos']
        if (len(entries)!=len(decoded) or manifest.get('alcance',{}).get('estado')!=('fuera_mvp_declarado' if provisional else 'pendiente_verificar')):
            raise ValueError('El expediente no corresponde a la selección enviada.')
        for index,(entry,(name,content)) in enumerate(zip(entries,decoded),1):
            raw,_,_=self.app._original(caso,entry['id'])
            if (entry['id']!=f'L{index:04d}' or entry.get('nombre_original')!=name or raw!=content
                    or entry.get('bytes')!=len(content)):
                raise ValueError('Los originales no corresponden a la selección enviada.')
        ident=meta['revision_documental']
        if not isinstance(ident,str) or not re.fullmatch('[0-9a-f]{32}',ident):raise ValueError('Revisión inválida.')
        path=folder/'revision_documental'/ident/'revision.json'
        if path.resolve()!=path:raise ValueError('Revisión enlazada.')
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=meta['revision_sha256']:raise ValueError('Revisión alterada desde el ingreso.')
        report=json_desde_bytes(raw,'revisión documental')
        if report['caso']!=caso or report['expediente_sha256']!=file_hash(folder/'expediente.json'):
            raise ValueError('Revisión documental sin vigencia.')
        # Solo resumen; mensajes del parser pueden contener rutas privadas.
        for entry in manifest['archivos']:self.app._original(caso,entry['id'])
        if self.app.expediente(caso)[2]!=fingerprint or path.read_bytes()!=raw:raise ValueError('Fuentes cambiadas durante el ingreso.')
        return {'caso':caso,'expediente_sha256':fingerprint,'revision_documental':path.parent.name,
                'resumen':report['resumen'],'documentos':[{'id':d['id'],'con_error':bool(d.get('error')),
                    'paginas':len(d['paginas'])} for d in report['documentos']],
                'estado':'pendiente_revision_humana','aprueba_ingenieria':False,'transmision_externa':False}
