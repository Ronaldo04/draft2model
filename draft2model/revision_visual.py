"""Revisión local: evidencia renderizada, lecturas y geometría versionada.



Ejecutar con ``python -m draft2model.revision_visual``. No extrae lecturas,

prepara planes locales y permite envíos a proveedor solo con confirmación explícita.

Registra aprobaciones geométricas explícitas de identidad

declarada, sin certificar ingeniería. Solo escucha en loopback.

"""

from __future__ import annotations



import argparse

import hashlib

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from io import BytesIO

import json

import math

from pathlib import Path

import re

import secrets

import socket

import tempfile

import threading

from urllib.parse import parse_qs, urlsplit

import webbrowser



import pymupdf

from PIL import Image, ImageOps



from . import gestion_extraccion as g

from . import gestion_geometria as geo

from .extraccion_preliminar import huella

from .revision_configuracion import ServicioConfiguracion

from .revision_resultados import ServicioResultados

from .revision_entregables import ServicioEntregables

from .revision_ejecucion import ServicioEjecucion, ErrorEjecucion

from .revision_aprobacion_modelo import ServicioRevisionModelo, ErrorRevisionModelo

from .revision_analisis import ServicioAnalisis

from .revision_mapeos import ServicioMapeos, ErrorNormalizacionPendiente

from .revision_paneles import ServicioPaneles

from .revision_lecturas import ServicioLecturas

from .revision_verificacion_modelo import ServicioVerificacionModelo

from .revision_ingreso import ServicioIngreso, MAX_SOLICITUD

from .revision_preparacion import ServicioPreparacion

from .revision_conversion import ServicioConversion

from .revision_respuestas import ServicioRespuestas

from .revision_proveedor import ServicioProveedor, ErrorProveedorWeb

from .revision_contexto import ServicioContexto

from .revision_explicaciones import ServicioExplicaciones, ErrorExplicaciones

from .revision_tabular import ServicioTabular, ErrorTabular

from .revision_superposicion import ServicioSuperposicion, ErrorSuperposicion

from .revision_controles import ServicioControles, ErrorControles

from .revision_aprobacion_resultados import ServicioRevisionResultados, ErrorRevisionResultados



WEB = Path(__file__).with_name('revision_web')

WEB_ASSETS={'/':'index.html',**{'/'+name:name for name in (

    'reconstruccion.js','preparacion_configuracion.js','etapas.js','etapas.css','editor_ingenieria.js','modelo_3d.js','verificacion_modelo.js','app.js','configuracion.js','construccion.js','resultados.js','revision_modelo.js','analisis.js','mapeos.js','informes.js','paneles.js','lecturas.js','ingreso.js','preparacion.js','recuperacion.js','conversion.js','respuestas.js','proveedor.js','contexto.js','explicaciones.js','preprocesamiento.js','tabular.js','superposicion.js','controles.js','revision_resultados.js','style.css')}}

WEB_ASSETS.update({'/parametros.js':'parametros.js','/politicas_malla.js':'politicas_malla.js','/digitizacion.js':'digitizacion.js','/contornos.js':'contornos.js','/navegacion_modulos.js':'navegacion_modulos.js','/katex_render.js':'katex_render.js','/herramienta_e030.js':'herramienta_e030.js','/v04_vista_modelo.png':'v04_vista_modelo.png','/Pueblo_Libre_V04_40cm.EDB':'Pueblo_Libre_V04_40cm.EDB','/etabs_geometry_v04.js':'etabs_geometry_v04.js','/etabs_geometry_v04.json':'etabs_geometry_v04.json'})

MAX_BODY = 2 * 1024 * 1024

MAX_SOURCE = 128 * 1024 * 1024





class ErrorRevision(ValueError):

    pass





class RevisionLocal:

    def __init__(self, raiz=g.RAIZ_PRIVADA):

        self.raiz = Path(raiz).resolve()

        self.lock = threading.RLock()

        self.configuraciones = ServicioConfiguracion(self)

        self.resultados = ServicioResultados(self)

        self.entregables = ServicioEntregables(self)

        self._ejecucion = None

        self.revision_modelo = ServicioRevisionModelo(self)

        self._analisis = None

        self.mapeos = ServicioMapeos(self)

        self.paneles = ServicioPaneles(self)

        self._lecturas = None

        self._verificacion_modelo = None

        self.ingreso = ServicioIngreso(self)

        self.preparacion = ServicioPreparacion(self)

        self.conversion = ServicioConversion(self)

        self.tabular = ServicioTabular(self)

        self.superposicion = ServicioSuperposicion(self)

        self.controles = ServicioControles(self)

        self.revision_resultados = ServicioRevisionResultados(self)

        self.respuestas = ServicioRespuestas(self)

        self._proveedor = None

        self.contexto = ServicioContexto(self)

        self._explicaciones = None

        self._reconstruccion = None

        self._preparacion_configuracion = None

        self._parametros = None

        self._politicas_malla = None

        self._digitizacion = None

        self._contornos = None



    @property

    def contornos(self):

        with self.lock:

            if self._contornos is None:

                from .revision_contornos import ServicioContornos

                self._contornos=ServicioContornos(self)

            return self._contornos



    @property

    def digitizacion(self):

        with self.lock:

            if self._digitizacion is None:

                from .revision_digitizacion import ServicioDigitizacion

                self._digitizacion=ServicioDigitizacion(self)

            return self._digitizacion



    @property

    def politicas_malla(self):

        with self.lock:

            if self._politicas_malla is None:

                from .revision_politicas_malla import ServicioPoliticasMalla

                self._politicas_malla=ServicioPoliticasMalla(self)

            return self._politicas_malla



    @property

    def parametros(self):

        with self.lock:

            if self._parametros is None:

                from .revision_parametros import ServicioParametros

                self._parametros=ServicioParametros(self)

            return self._parametros



    @property

    def preparacion_configuracion(self):

        with self.lock:

            if self._preparacion_configuracion is None:

                from .preparacion_configuracion import ServicioPreparacionConfiguracion

                self._preparacion_configuracion = ServicioPreparacionConfiguracion(self)

            return self._preparacion_configuracion



    @property

    def reconstruccion(self):

        with self.lock:

            if self._reconstruccion is None:

                from .revision_reconstruccion import ServicioReconstruccion

                self._reconstruccion = ServicioReconstruccion(self)

            return self._reconstruccion



    def tabular_version(self, caso, version, expediente_sha256):

        with self.lock:

            proyeccion = self.tabular.consultar(caso, version, expediente_sha256=expediente_sha256)

            geometria = self.tabular._cargar(caso, version, expediente_sha256)[3]

            return {**proyeccion, 'geometria': geometria}



    @property

    def explicaciones(self):

        with self.lock:

            if self._explicaciones is None:

                self._explicaciones = ServicioExplicaciones(self)

            return self._explicaciones



    @property

    def proveedor(self):

        with self.lock:

            if self._proveedor is None:

                self._proveedor = ServicioProveedor(self)

            return self._proveedor



    @property

    def ejecucion(self):

        with self.lock:

            if self._ejecucion is None:

                self._ejecucion = ServicioEjecucion(self)

            return self._ejecucion



    @property

    def analisis(self):

        with self.lock:

            if self._analisis is None:

                self._analisis = ServicioAnalisis(self)

            return self._analisis



    @property

    def lecturas(self):

        with self.lock:

            if self._lecturas is None:

                self._lecturas = ServicioLecturas(self)

            return self._lecturas



    @property

    def verificacion_modelo(self):

        with self.lock:

            if self._verificacion_modelo is None:

                self._verificacion_modelo = ServicioVerificacionModelo(self)

            return self._verificacion_modelo



    def expediente(self, caso):

        folder = g.carpeta_caso(self.raiz, caso)

        manifest = folder / 'expediente.json'

        if manifest.resolve() != manifest:

            raise ErrorRevision('El expediente está enlazado; no se abre.')

        raw = manifest.read_bytes()

        data = g.json_desde_bytes(raw, 'expediente.json')

        if (not isinstance(data, dict) or data.get('id') != caso

                or data.get('uso_autorizado_declarado') is not True

                or not isinstance(data.get('archivos'), list)):

            raise ErrorRevision('Expediente inválido o sin autorización de uso declarada.')

        return folder, data, hashlib.sha256(raw).hexdigest()



    def casos(self):

        result = []

        if self.raiz.is_dir():

            for folder in sorted(self.raiz.iterdir()):

                if not re.fullmatch(g.PATRON_CASO, folder.name) or not folder.is_dir():

                    continue

                try:

                    _, data, _ = self.expediente(folder.name)

                    result.append({'id': folder.name, 'alcance': data.get('alcance')})

                except (g.ErrorGestion, ErrorRevision, OSError):

                    continue

        return result



    def _original(self, caso, archivo):

        folder, data, fingerprint = self.expediente(caso)

        entries = [x for x in data['archivos'] if isinstance(x, dict) and x.get('id') == archivo]

        if len(entries) != 1:

            raise ErrorRevision('Archivo ausente o identificador repetido.')

        entry = entries[0]

        relative = entry.get('archivo')

        if not isinstance(relative, str) or Path(relative).is_absolute():

            raise ErrorRevision('Ruta de original inválida.')

        path = folder / relative

        if path.resolve() != path or not path.resolve().is_relative_to(folder):

            raise ErrorRevision('Original enlazado o fuera del caso.')

        if path.stat().st_size > MAX_SOURCE:

            raise ErrorRevision('El original excede el límite local de 128 MiB.')

        raw = path.read_bytes()

        if hashlib.sha256(raw).hexdigest() != entry.get('sha256'):

            raise ErrorRevision('El original cambió: su huella no coincide con el expediente.')

        return raw, path.suffix.lower(), fingerprint



    def documentos(self, caso):

        _, manifest, fingerprint = self.expediente(caso)

        documents = []

        for entry in manifest['archivos']:

            if not isinstance(entry, dict):

                raise ErrorRevision('Entrada de archivo inválida.')

            row = {'id': entry.get('id'), 'nombre': entry.get('nombre_original', entry.get('id'))}

            try:

                raw, suffix, _ = self._original(caso, entry.get('id'))

                if suffix == '.pdf':

                    with pymupdf.open(stream=raw, filetype='pdf') as doc:

                        if doc.needs_pass:

                            raise ErrorRevision('PDF protegido; requiere preparación por su propietario.')

                        row['paginas'] = doc.page_count

                else:

                    with Image.open(BytesIO(raw)) as image:

                        image.verify()

                    row['paginas'] = 1

                row['error'] = None

            except (ValueError, RuntimeError, OSError, Image.DecompressionBombError) as exc:

                row.update(paginas=0, error=str(exc))

            documents.append(row)

        versions = []

        versions_dir = g.carpeta_caso(self.raiz, caso) / 'extracciones'

        if versions_dir.resolve() != versions_dir:

            raise ErrorRevision('La carpeta de versiones está enlazada.')

        if versions_dir.is_dir():

            for path in sorted(versions_dir.iterdir()):

                if re.fullmatch(g.PATRON_VERSION, path.name) and path.is_dir():

                    # El listado no otorga validez: al abrir siempre se comprueba la versión.

                    versions.append(path.name)

        geometrias = self.geometrias(caso)

        return {'caso': caso, 'alcance': manifest.get('alcance'), 'documentos': documents,

                'geometrias': geometrias,

                'versiones': versions, 'expediente_sha256': fingerprint}



    def geometrias(self, caso):

        folder, _, _ = self.expediente(caso)

        base = folder / geo.CARPETA_GEOMETRIAS

        if base.resolve() != base:

            raise ErrorRevision('La carpeta geométrica está enlazada.')

        return sorted(p.name for p in base.iterdir()

                      if re.fullmatch(geo.PATRON_VERSION, p.name) and p.is_dir()) if base.is_dir() else []



    def geometria(self, caso, version):

        _, _, fingerprint = self.expediente(caso)

        result = geo.consultar_version(self.raiz, caso, version)

        if not result.comprobacion.correcta:

            raise ErrorRevision('Geometría o evidencia sin vigencia.')

        return {'datos': result.geometria, 'metadatos': result.metadatos,

                'comprobacion': result.comprobacion.a_dict(),

                'huella': result.comprobacion.huella_contenido,

                'sha256_geometria': result.comprobacion.sha256_geometria,

                'expediente_sha256': fingerprint}



    def actuar_geometria(self, operacion, body):

        if not isinstance(body, dict):

            raise ErrorRevision('Se esperaba un objeto JSON.')

        with self.lock:

            caso = body.get('caso')

            folder, _, fingerprint = self.expediente(caso)

            base = {'caso', 'expediente_sha256'}

            if body.get('expediente_sha256') != fingerprint:

                raise ErrorRevision('El expediente cambió; vuelve a abrirlo.')

            if operacion == 'importar':

                if set(body) != base | {'geometria_json'} or not isinstance(body['geometria_json'], str):

                    raise ErrorRevision('Campos de importación geométrica inválidos.')

                raw = body['geometria_json'].encode('utf-8')

                g.json_desde_bytes(raw, 'geometría')

                with tempfile.TemporaryDirectory(prefix='.revision-', dir=folder) as tmp:

                    source = Path(tmp) / 'geometria.json'

                    source.write_bytes(raw)

                    result = geo.importar_geometria(self.raiz, caso, source)

            else:

                base |= {'version', 'huella', 'sha256_geometria', 'motivo', 'fecha', 'revisor_declarado'}

                extra = ({'geometria_json'} if operacion == 'revisar' else set() if operacion == 'migrar-superficies' else {'alcance_revision', 'confirmacion_explicita'})

                if operacion not in {'revisar', 'aprobar', 'migrar-superficies'} or set(body) != base | extra:

                    raise ErrorRevision('Campos de revisión geométrica inválidos.')

                current = self.geometria(caso, body['version'])

                if (current['huella'] != body['huella'] or

                        current['sha256_geometria'] != body['sha256_geometria']):

                    raise ErrorRevision('La geometría abierta cambió; recarga la versión.')

                options = {key: body[key] for key in ('motivo', 'fecha', 'revisor_declarado')}

                if operacion == 'migrar-superficies':

                    result = geo.migrar_geometria_superficies(self.raiz, caso, body['version'],

                        huella_esperada=body['huella'], **options)

                elif operacion == 'revisar':

                    if not isinstance(body['geometria_json'], str):

                        raise ErrorRevision('La revisión requiere texto JSON completo.')

                    proposed = g.json_desde_bytes(body['geometria_json'].encode('utf-8'), 'geometría')

                    result = geo.revisar_geometria(self.raiz, caso, body['version'], proposed, **options)

                else:

                    if body['confirmacion_explicita'] is not True:

                        raise ErrorRevision('La aprobación requiere declaración explícita.')

                    result = geo.aprobar_geometria(self.raiz, caso, body['version'],

                        huella_esperada=body['huella'], alcance_revision=body['alcance_revision'], **options)

            return {'id': result.identificador, 'operacion': operacion,

                    'ruta_relativa': result.ruta.relative_to(folder).as_posix()}



    def version(self, caso, version):

        folder, _, fingerprint = self.expediente(caso)

        data, meta, problems = g.cargar_version(folder, caso, version)

        comp = g.validar_version(self.raiz, caso, version)

        if problems or not comp.correcta:

            raise ErrorRevision('Versión o evidencia sin vigencia. ' + ' '.join(problems + comp.problemas))

        return {'datos': data, 'metadatos': meta, 'comprobacion': comp.a_dict(),

                'huella': huella(data), 'expediente_sha256': fingerprint,

                'vigencia': g.vigencia(self.raiz, caso, version)}



    def localizar_lectura(self, caso, version, candidato, expediente_sha256, huella_esperada):

        from .localizacion_literal_pdf import localizar_literal_pdf

        record = self.version(caso, version)

        if (record['expediente_sha256'] != expediente_sha256 or record['huella'] != huella_esperada):

            raise ErrorRevision('La versión o el expediente cambió; vuelva a consultarlo.')

        matches = [c for c in record['datos']['candidatos'] if c['id'] == candidato]

        if len(matches) != 1:

            raise ErrorRevision('Candidato no disponible.')

        literal = matches[0].get('texto_fuente')

        result = {'caso': caso, 'version': version, 'candidato': candidato,

                  'expediente_sha256': expediente_sha256, 'huella': huella_esperada,

                  'metodo': 'palabras_pdf_local', 'modifica_datos': False,

                  'texto_fuente': literal, 'fuentes': []}

        if not isinstance(literal, str) or not literal.strip():

            result['estado'] = 'sin_texto_literal'

            return result

        sources = sorted({(e['archivo_id'], e['pagina']) for e in matches[0]['evidencia']})

        for archivo, pagina in sources:

            raw, suffix, fingerprint = self._original(caso, archivo)

            if fingerprint != expediente_sha256:

                raise ErrorRevision('El expediente cambió durante la búsqueda.')

            finding = (localizar_literal_pdf(raw, pagina, literal) if suffix == '.pdf'

                       else {'estado': 'fuente_no_vectorial', 'total': 0, 'regiones': []})

            result['fuentes'].append({'archivo_id': archivo, 'pagina': pagina,

                                     'original_sha256': hashlib.sha256(raw).hexdigest(), **finding})

        result['estado'] = 'propuestas_sin_aplicar'

        return result



    def pagina(self, caso, archivo, pagina, expediente_sha256):

        if not isinstance(pagina, int) or isinstance(pagina, bool) or pagina < 1:

            raise ErrorRevision('Número de página inválido.')

        raw, suffix, current = self._original(caso, archivo)

        if current != expediente_sha256:

            raise ErrorRevision('El expediente cambió; vuelve a abrirlo antes de ver la página.')

        if suffix == '.pdf':

            with pymupdf.open(stream=raw, filetype='pdf') as doc:

                if doc.needs_pass or pagina > doc.page_count:

                    raise ErrorRevision('Página ausente o PDF protegido.')

                page = doc[pagina - 1]

                width, height = page.rect.width, page.rect.height

                if not all(math.isfinite(x) and x > 0 for x in (width, height)):

                    raise ErrorRevision('Dimensiones de página inválidas.')

                # Misma página visible usada por bbox_normalizada; respeta /Rotate y CropBox.

                scale = min(2, 2399 / max(width, height))

                return page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes('png')

        if suffix not in {'.png', '.jpg', '.jpeg'} or pagina != 1:

            raise ErrorRevision('Formato o página no compatible.')

        with Image.open(BytesIO(raw)) as image:

            shown = ImageOps.exif_transpose(image).convert('RGB')

            shown.thumbnail((2400, 2400))

            out = BytesIO()

            shown.save(out, format='PNG')

            return out.getvalue()



    def actuar(self, operacion, body):

        if not isinstance(body, dict):

            raise ErrorRevision('Se esperaba un objeto JSON.')

        caso = body.get('caso')

        with self.lock:

            folder, _, fingerprint = self.expediente(caso)

            if fingerprint != body.get('expediente_sha256'):

                raise ErrorRevision('El expediente cambió; vuelve a abrirlo.')

            if operacion == 'importar':

                allowed = {'caso', 'expediente_sha256', 'extraccion_json'}

                if set(body) != allowed:

                    raise ErrorRevision('Campos de importación inválidos.')

                # JSON recibido del selector local; ninguna ruta la elige el navegador.

                with tempfile.TemporaryDirectory(prefix='.revision-', dir=folder) as tmp:

                    source = Path(tmp) / 'entrada.json'

                    if not isinstance(body['extraccion_json'], str):

                        raise ErrorRevision('La importación requiere texto JSON.')

                    raw = body['extraccion_json'].encode('utf-8')

                    g.json_desde_bytes(raw, 'extracción')

                    source.write_bytes(raw)

                    result = g.importar_extraccion(self.raiz, caso, source)

            else:

                base = {'caso', 'version', 'huella', 'expediente_sha256'}

                allowed = base | ({'candidato', 'estado', 'motivo', 'fecha', 'revisor_declarado',

                                   'valor_revisado', 'unidad_revisada', 'tipo_revisado'} if operacion == 'corregir' else

                                  {'candidato', 'indice', 'bbox', 'motivo', 'fecha', 'revisor_declarado'} if operacion == 'reubicar' else

                                  {'tipo', 'valor', 'unidad', 'texto_fuente', 'simbolo', 'archivo_id', 'pagina', 'bbox', 'motivo', 'fecha',

                                   'revisor_declarado'} if operacion == 'lectura_manual' else set())

                if set(body) - allowed or not base.issubset(body):

                    raise ErrorRevision('Campos de operación inválidos.')

                current = self.version(caso, body.get('version'))

                if current['huella'] != body.get('huella'):

                    raise ErrorRevision('La lectura abierta cambió; recarga la versión.')

                if operacion == 'corregir':

                    options = {key: body[key] for key in allowed - base - {'candidato'} if key in body}

                    required = {'estado', 'motivo', 'fecha', 'revisor_declarado'}

                    if not required.issubset(options) or 'candidato' not in body:

                        raise ErrorRevision('Completa estado, motivo, fecha y revisor.')

                    result = g.corregir_version(self.raiz, caso, body['version'], body['candidato'], **options)

                elif operacion in ('reubicar', 'lectura_manual'):

                    # Operaciones deliberadas: crean versión nueva pendiente; no aprueban la lectura.

                    opciones = {key: body[key] for key in allowed - base if key in body}

                    faltan = {'bbox', 'motivo', 'fecha', 'revisor_declarado'} - set(opciones)

                    if faltan:

                        raise ErrorRevision('Completa: ' + ', '.join(sorted(faltan)) + '.')

                    if operacion == 'reubicar':

                        result = g.reubicar_evidencia(self.raiz, caso, body['version'], opciones.pop('candidato', None), **opciones)

                    else:

                        result = g.agregar_lectura(self.raiz, caso, body['version'], **opciones)

                elif operacion == 'exportar':

                    result = g.exportar_version(self.raiz, caso, body['version'])

                else:

                    raise ErrorRevision('Operación desconocida.')

            return {'id': result.identificador, 'operacion': operacion,

                    'ruta_relativa': result.ruta.relative_to(folder).as_posix()}





class ServidorRevision(ThreadingHTTPServer):

    daemon_threads = True

    # En Windows SO_REUSEADDR puede dejar dos versiones atendiendo el mismo puerto.

    allow_reuse_address = False



    def server_bind(self):

        if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):

            self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)

        super().server_bind()



    def __init__(self, raiz=g.RAIZ_PRIVADA, puerto=8766):

        self.revision = RevisionLocal(raiz)

        self.token = secrets.token_urlsafe(32)

        super().__init__(('127.0.0.1', puerto), ManejadorRevision)

        self.origen = f'http://127.0.0.1:{self.server_port}'





class ManejadorRevision(BaseHTTPRequestHandler):

    def log_message(self, *args):

        pass  # No registrar nombres de expedientes, contenido ni token.



    def responder(self, status, data, tipo='application/json; charset=utf-8', descarga=None):

        raw = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')

        self.send_response(status)

        self.send_header('Content-Type', tipo)

        self.send_header('Content-Length', str(len(raw)))

        if descarga is not None:self.send_header('Content-Disposition','attachment; filename="'+descarga+'"')

        self.send_header('Cache-Control', 'no-store')

        self.send_header('X-Content-Type-Options', 'nosniff')

        self.send_header('Referrer-Policy', 'no-referrer')

        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")

        self.end_headers()

        self.wfile.write(raw)



    def permitido(self, api=False):

        expected = urlsplit(self.server.origen).netloc

        if self.headers.get('Host') != expected:

            return False

        origin = self.headers.get('Origin')

        if origin is not None and origin != self.server.origen:

            return False

        if self.headers.get('Sec-Fetch-Site') not in (None, 'same-origin', 'none'):

            return False

        if not api:
            return True
        header_tok = self.headers.get('X-Revision-Session', '')
        query = parse_qs(urlsplit(self.path).query) if '?' in self.path else {}
        param_tok = query.get('token', [''])[0]
        tok = header_tok or param_tok
        return secrets.compare_digest(tok.encode('utf-8'), self.server.token.encode('utf-8'))



    def do_GET(self):

        route = urlsplit(self.path)

        if not self.permitido(route.path.startswith('/api/')):

            return self.responder(403, {'error': 'Acceso local no autorizado.'})

        try:
            if route.path.startswith('/katex/'):
                rel_path = route.path.lstrip('/')
                target = (WEB / rel_path).resolve()
                if target.is_file() and str(target).startswith(str(WEB.resolve())):
                    raw = target.read_bytes()
                    if rel_path.endswith('.woff2'):
                        tipo = 'font/woff2'
                    elif rel_path.endswith('.woff'):
                        tipo = 'font/woff'
                    elif rel_path.endswith('.ttf'):
                        tipo = 'font/ttf'
                    elif rel_path.endswith('.js') or rel_path.endswith('.mjs'):
                        tipo = 'text/javascript; charset=utf-8'
                    elif rel_path.endswith('.css'):
                        tipo = 'text/css; charset=utf-8'
                    else:
                        tipo = 'application/octet-stream'
                    return self.responder(200, raw, tipo, descarga=desc if 'desc' in locals() else None)

            if route.path in WEB_ASSETS:

                name = WEB_ASSETS[route.path]

                raw = (WEB / name).read_bytes()

                if name == 'index.html':

                    raw = raw.replace(b'__SESSION__', self.server.token.encode('ascii'))

                    from html import escape

                    from .proveedores import CATALOGO

                    from .politica_uso_ia import PROVEEDORES_AUTORIZADOS  # solo opciones operativas (Google/OpenAI)

                    opciones = ''.join('<option value="'+escape(p.id, quote=True)+'" data-detalle-auto="'+str(p.detalle_auto).lower()+'">'+escape(p.nombre)+'</option>' for p in CATALOGO.values() if p.id in PROVEEDORES_AUTORIZADOS)

                    raw = raw.replace(b'__OPCIONES_IA__', opciones.encode('utf-8'))

                tipo='text/javascript; charset=utf-8' if name.endswith('.js') else ('text/css; charset=utf-8' if name.endswith('.css') else ('image/png' if name.endswith('.png') else ('application/octet-stream' if name.endswith(('.edb', '.EDB')) else 'text/html; charset=utf-8')))
                desc = name if name.endswith(('.edb', '.EDB')) else None

                return self.responder(200, raw, tipo, descarga=desc if 'desc' in locals() else None)

            query = parse_qs(route.query, strict_parsing=True) if route.query else {}



            def arg(key):

                values = query.get(key, [])

                if len(values) != 1:

                    raise ErrorRevision('Parámetro ausente o repetido: ' + key)

                return values[0]



            app = self.server.revision

            if route.path == '/api/visual/original-raster':

                return self.responder(200,app.preparacion.original_raster(arg('caso'),arg('archivo'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/visual/preprocesamientos':

                return self.responder(200,app.preparacion.preprocesamientos(arg('caso'),arg('archivo'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/visual/preprocesamiento':

                return self.responder(200,app.preparacion.preprocesamiento(arg('caso'),arg('version'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/visual/preprocesado-imagen':

                return self.responder(200,app.preparacion.imagen_preprocesada(arg('caso'),arg('version'),expediente_sha256=arg('expediente_sha256')),'image/png')

            if route.path == '/api/contexto/historial':

                return self.responder(200,app.contexto.listar(arg('caso'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/contexto/version':

                return self.responder(200,app.contexto.consultar(arg('caso'),arg('tipo'),arg('version'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/contexto/derivado':

                return self.responder(200,app.contexto.consultar_derivado(arg('caso'),arg('version'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/explicaciones/trabajos':

                return self.responder(200,app.explicaciones.listar(arg('caso')))

            if route.path == '/api/explicaciones/trabajo':

                return self.responder(200,app.explicaciones.consultar(arg('caso'),arg('trabajo')))

            if route.path == '/api/configuracion/preparaciones':

                return self.responder(200,{'versiones':app.preparacion_configuracion.listar(arg('caso'),arg('expediente_sha256'))})

            if route.path == '/api/configuracion/preparacion/para-geometria':

                return self.responder(200,app.preparacion_configuracion.para_geometria(arg('caso'),arg('expediente_sha256'),arg('geometria')))

            if route.path == '/api/configuracion/preparacion':

                return self.responder(200,app.preparacion_configuracion.consultar(arg('caso'),arg('expediente_sha256'),arg('version')))

            if route.path == '/api/reconstruccion/cuota':

                return self.responder(200,app.reconstruccion.estado_cuota())

            if route.path == '/api/reconstruccion/historial':

                return self.responder(200,{'trabajos':app.reconstruccion.listar(arg('caso'),arg('expediente_sha256'))})

            if route.path == '/api/reconstruccion/estado':

                return self.responder(200,app.reconstruccion.consultar(arg('caso'),arg('expediente_sha256'),arg('trabajo')))

            if route.path == '/api/parametros/historial':

                return self.responder(200,{'trabajos':app.parametros.listar(arg('caso'),arg('expediente_sha256'))})

            if route.path == '/api/digitizacion/historial':

                return self.responder(200,app.digitizacion.listar(arg('caso'),arg('expediente_sha256')))

            if route.path == '/api/contornos/historial':

                return self.responder(200,{'trabajos':app.contornos.listar(arg('caso'),arg('expediente_sha256'))})

            if route.path == '/api/contornos/estado':

                return self.responder(200,app.contornos.consultar(arg('caso'),arg('expediente_sha256'),arg('trabajo')))

            if route.path == '/api/digitizacion/registro':

                return self.responder(200,app.digitizacion.consultar(arg('caso'),arg('expediente_sha256'),arg('id')))

            if route.path == '/api/parametros/estado':

                return self.responder(200,app.parametros.consultar(arg('caso'),arg('expediente_sha256'),arg('trabajo')))

            if route.path == '/api/credenciales/estado':

                from .credenciales_locales import cargar

                path = Path(app.raiz) / 'credenciales.local.md'

                try:

                    values = cargar(path) if path.is_file() else {}

                except Exception:

                    values = {}

                return self.responder(200, {

                    'openai': bool(values.get('OPENAI_API_KEY')),

                    'gemini': bool(values.get('GEMINI_API_KEY'))

                })

            if route.path == '/api/casos':

                return self.responder(200, {'casos': app.casos()})

            if route.path == '/api/modulos':

                from .modulos_sistema import listar_modulos

                return self.responder(200, {'modulos': listar_modulos()})

            if route.path == '/api/modulos/especificacion':

                from .modulo_porticado import obtener_especificacion_modulo

                modulo_id = arg('id') if 'id' in query else 'porticado'

                return self.responder(200, obtener_especificacion_modulo(modulo_id))

            if route.path == '/api/normativa/anexo-ii':
                from . import normativa_e030 as n
                dep = query.get('departamento', [None])[0]
                prov = query.get('provincia', [None])[0]
                dist = query.get('distrito', [None])[0]
                if dist and prov and dep:
                    return self.responder(200, n.consultar_zona_distrito(dep, prov, dist))
                elif prov and dep:
                    return self.responder(200, {'departamento': dep, 'provincia': prov, 'distritos': n.listar_distritos(dep, prov)})
                elif dep:
                    return self.responder(200, {'departamento': dep, 'provincias': n.listar_provincias(dep)})
                else:
                    return self.responder(200, {'departamentos': n.listar_departamentos()})

            if route.path == '/api/normativa/espectro-etabs':
                from . import normativa_e030 as n
                z = float(arg('Z'))
                u = float(arg('U'))
                s = float(arg('S'))
                r = float(arg('R'))
                tp = float(arg('TP'))
                tl = float(arg('TL'))
                t_max = float(query.get('T_max', [4.0])[0])
                dt = float(query.get('dT', [0.05])[0])
                tipo = query.get('tipo', ['C'])[0]
                descargar = query.get('descargar', ['false'])[0].lower() in ('1', 'true')
                txt = n.exportar_archivo_espectro_etabs(None, Z=z, U=u, S=s, R=r, TP=tp, TL=tl, T_max=t_max, dT=dt, tipo=tipo)
                if descargar:
                    nombre_archivo = f"Espectro_E030_2026_{tipo}_Z{z}_U{u}_S{s}_R{r}.txt"
                    return self.responder(200, txt.encode('utf-8'), 'text/plain; charset=utf-8', descarga=nombre_archivo)
                puntos = n.generar_curva_espectro(Z=z, U=u, S=s, R=r, TP=tp, TL=tl, T_max=t_max, dT=dt, tipo=tipo)
                return self.responder(200, {'puntos': puntos, 'formato_txt': txt})

            if route.path == '/api/localizar-lectura':

                if set(query) != {'caso', 'version', 'candidato', 'expediente_sha256', 'huella'}:

                    raise ErrorRevision('Parámetros de búsqueda local inválidos.')

                return self.responder(200, app.localizar_lectura(arg('caso'), arg('version'), arg('candidato'),

                                                               arg('expediente_sha256'), arg('huella')))

            if route.path == '/api/documentos':

                return self.responder(200, app.documentos(arg('caso')))

            if route.path == '/api/version':

                return self.responder(200, app.version(arg('caso'), arg('version')))

            if route.path == '/api/geometrias':

                return self.responder(200, {'versiones': app.geometrias(arg('caso'))})

            if route.path == '/api/revision-resultados/fuentes':

                return self.responder(200,app.revision_resultados.consultar_fuentes(arg('caso'),arg('resultado'),arg('analisis'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/revision-resultados/historial':

                return self.responder(200,app.revision_resultados.listar(arg('caso'),arg('resultado'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/revision-resultados/version':

                return self.responder(200,app.revision_resultados.consultar(arg('caso'),arg('revision'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/controles/historial':

                return self.responder(200,app.controles.listar(arg('caso'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/controles/version':

                return self.responder(200,app.controles.consultar(arg('caso'),arg('version'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/superposicion/esquema':

                return self.responder(200,app.superposicion.esquema(arg('caso'),arg('version'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/superposicion/historial':

                return self.responder(200,app.superposicion.listar(arg('caso'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/superposicion/version':

                return self.responder(200,app.superposicion.consultar(arg('caso'),arg('version'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/tabular/historial':

                return self.responder(200,app.tabular.listar(arg('caso'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/tabular/version':

                return self.responder(200,app.tabular_version(arg('caso'),arg('version'),arg('expediente_sha256')))

            if route.path == '/api/conversiones':

                return self.responder(200,app.conversion.listar(arg('caso'),expediente_sha256=arg('expediente_sha256')))

            if route.path in ('/api/respuestas','/api/respuesta'):

                try:

                    result=(app.respuestas.listar(arg('caso'),expediente_sha256=arg('expediente_sha256'))

                        if route.path=='/api/respuestas' else app.respuestas.consultar(arg('caso'),arg('version'),expediente_sha256=arg('expediente_sha256')))

                except (KeyError,TypeError,AttributeError) as error:

                    raise ValueError('Respuesta visual no verificable.') from error

                return self.responder(200,result)

            if route.path == '/api/conversion':

                return self.responder(200,app.conversion.consultar(arg('caso'),arg('version'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/geometria':

                return self.responder(200, app.geometria(arg('caso'), arg('version')))

            if route.path == '/api/configuraciones':

                return self.responder(200, {'versiones':app.configuraciones.listar(arg('caso'))})

            if route.path == '/api/configuracion':

                return self.responder(200, app.configuraciones.consultar(arg('caso'),arg('version')))

            if route.path == '/api/configuracion/malla':

                # Solo lectura: preparación 0.4 reproducida desde la versión registrada; no admite parámetros de edición.

                if set(query)!={'caso','version'}:raise ErrorRevision('Consulta de malla de solo lectura: solo caso y version.')

                return self.responder(200, app.configuraciones.malla(arg('caso'),arg('version')))

            if route.path in ('/api/resultados', '/api/modelos'):

                # modo=inventario (opcional, exacto): IDs sin comprobar; abrir cada versión ejecuta la comprobación completa.

                if set(query) - {'caso', 'modo'} or ('modo' in query and arg('modo') != 'inventario'):

                    raise ErrorRevision('Listado: solo caso y modo=inventario opcional.')

                listar = app.resultados.listar_resultados if route.path == '/api/resultados' else app.resultados.listar_modelos

                return self.responder(200, listar(arg('caso'), inventario='modo' in query))

            if route.path == '/api/resultado':

                return self.responder(200, app.resultados.consultar_resultado(arg('caso'),arg('version'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/modelo/vista-etabs':
                img_path = Path(__file__).resolve().parent.parent / 'etabs_entrega_v04' / 'V04_Vista_Modelo.png'
                if img_path.is_file():
                    return self.responder(200, img_path.read_bytes(), 'image/png')
                raise ErrorRevision('Imagen del modelo ETABS no encontrada.')

            if route.path == '/api/modelo/descargar-edb':
                edb_path = Path(__file__).resolve().parent.parent / 'etabs_entrega_v04' / 'Pueblo_Libre_V04_40cm.EDB'
                if edb_path.is_file():
                    return self.responder(200, edb_path.read_bytes(), 'application/octet-stream', descarga='modelo_pueblo-libre-v04.edb')
                raise ErrorRevision('Archivo EDB del modelo ETABS no encontrado.')

            if route.path == '/api/modelo':

                return self.responder(200, app.resultados.consultar_modelo(arg('caso'),arg('version'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/modelo/verificacion/historial':

                return self.responder(200,app.verificacion_modelo.listar(arg('caso')))

            if route.path == '/api/modelo/verificacion/estado':

                return self.responder(200,app.verificacion_modelo.consultar(arg('caso'),arg('trabajo')))

            if route.path == '/api/modelo/revision':

                return self.responder(200,app.revision_modelo.consultar(arg('caso'),arg('modelo'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/analisis':

                if set(query)-{'caso','resultado','expediente_sha256','modo'}:

                    raise ErrorRevision('Parámetros de consulta de análisis no admitidos.')

                modo=arg('modo') if 'modo' in query else 'verificado'

                return self.responder(200,app.entregables.listar_analisis(arg('caso'),arg('resultado'),expediente_sha256=arg('expediente_sha256'),modo=modo))

            if route.path == '/api/analisis/comprobar':

                if set(query)!={'caso','resultado','analisis','expediente_sha256'}:

                    raise ErrorRevision('Selecciona el análisis exacto que se comprobará.')

                return self.responder(200,app.entregables.comprobar_analisis(arg('caso'),arg('resultado'),arg('analisis'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/construccion/trabajos':

                return self.responder(200,app.ejecucion.listar(arg('caso')))

            if route.path == '/api/construccion/trabajo':

                return self.responder(200,app.ejecucion.consultar(arg('caso'),arg('trabajo')))

            if route.path == '/api/analisis/trabajos':

                return self.responder(200,app.analisis.listar(arg('caso')))

            if route.path == '/api/analisis/trabajo':

                return self.responder(200,app.analisis.consultar(arg('caso'),arg('trabajo')))

            if route.path == '/api/lectura/trabajos':

                return self.responder(200,app.lecturas.listar(arg('caso')))

            if route.path == '/api/proveedor/trabajos':

                return self.responder(200,app.proveedor.listar(arg('caso')))

            if route.path == '/api/proveedor/trabajo':

                return self.responder(200,app.proveedor.consultar(arg('caso'),arg('trabajo')))

            if route.path == '/api/lectura/trabajo':

                return self.responder(200,app.lecturas.consultar(arg('caso'),arg('trabajo')))

            if route.path == '/api/visual/historial':

                return self.responder(200,app.preparacion.listar(arg('caso'),expediente_sha256=arg('expediente_sha256')))

            visual_read={'/api/visual/revision':'revision','/api/visual/recorte':'recorte','/api/visual/paquete':'paquete','/api/visual/imagen':'imagen'}.get(route.path)

            if visual_read:

                result=getattr(app.preparacion,visual_read)(arg('caso'),arg('version'),expediente_sha256=arg('expediente_sha256'))

                return self.responder(200,result,'image/png' if visual_read=='imagen' else 'application/json; charset=utf-8')

            if route.path == '/api/mapeos':

                return self.responder(200,app.mapeos.listar(arg('caso'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/normalizacion/estado':

                return self.responder(200,app.mapeos.estado_normalizacion(arg('caso'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/mapeo/fuente':

                return self.responder(200,app.mapeos.fuente(arg('caso'),arg('analisis'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/mapeo':

                return self.responder(200,app.mapeos.consultar(arg('caso'),arg('version'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/informes':

                if set(query)-{'caso','resultado','expediente_sha256','modo'}:

                    raise ErrorRevision('Parámetros de consulta de informes no admitidos.')

                modo=arg('modo') if 'modo' in query else 'verificado'

                return self.responder(200,app.entregables.listar(arg('caso'),arg('resultado'),expediente_sha256=arg('expediente_sha256'),modo=modo))

            if route.path == '/api/paneles':

                return self.responder(200,app.paneles.listar(arg('caso'),arg('resultado'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/panel':

                return self.responder(200,app.paneles.consultar(arg('caso'),arg('version'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/panel/archivo':

                version=arg('version')

                raw=app.paneles.archivo(arg('caso'),version,expediente_sha256=arg('expediente_sha256'))

                return self.responder(200,raw,'text/html; charset=utf-8',descarga='panel-'+version+'.html')

            if route.path == '/api/informe':

                return self.responder(200,app.entregables.consultar(arg('caso'),arg('version'),expediente_sha256=arg('expediente_sha256')))

            if route.path == '/api/informe/archivo':

                formato=arg('formato');version=arg('version')

                raw=app.entregables.archivo(arg('caso'),version,formato,expediente_sha256=arg('expediente_sha256'))

                tipo={'pdf':'application/pdf','html':'text/html; charset=utf-8','json':'application/json; charset=utf-8'}[formato]

                return self.responder(200,raw,tipo,descarga='informe-'+version+'.'+formato)

            if route.path == '/api/pagina':

                return self.responder(200, app.pagina(arg('caso'), arg('archivo'), int(arg('pagina')),

                                                    arg('expediente_sha256')), 'image/png')

            return self.responder(404, {'error': 'Ruta inexistente.'})

        except (ErrorEjecucion, ErrorRevisionModelo, ErrorProveedorWeb, ErrorExplicaciones, ErrorRevisionResultados) as error:

            return self.responder(409, {'error': error.codigo, 'codigo': error.codigo})

        except (ErrorTabular, ErrorSuperposicion, ErrorControles) as error:  # mensajes fijos del servicio, sin rutas

            return self.responder(409, {'error': str(error)})

        except (ValueError, RuntimeError, OSError, Image.DecompressionBombError):

            # No exponer rutas absolutas, detalles del parser o contenido privado en errores HTTP.

            return self.responder(409, {'error': 'No se pudo abrir: documento o versión sin vigencia, inválido o ausente. Vuelve a consultar el expediente.'})



    def do_POST(self):

        if not self.permitido(True) or self.headers.get('Origin') != self.server.origen:

            return self.responder(403, {'error': 'Solicitud local no autorizada.'})

        if self.path == '/api/normativa/verificar-cortante-dinamico':
            from . import normativa_e030 as n
            import json
            size = int(self.headers.get('Content-Length', '0'))
            cuerpo = json.loads(self.rfile.read(size).decode('utf-8'))
            res = n.verificar_escala_cortante_dinamico(
                V_estatico=float(cuerpo['V_estatico']),
                V_dinamico=float(cuerpo['V_dinamico']),
                regular=bool(cuerpo.get('regular', True))
            )
            return self.responder(200, res)

        geometry_operation = {'/api/geometria/importar': 'importar', '/api/geometria/revisar': 'revisar',

                              '/api/geometria/aprobar': 'aprobar', '/api/geometria/migrar-superficies': 'migrar-superficies'}.get(self.path)

        reconstruction_operation={'/api/reconstruccion/preparar':'preparar_originales','/api/reconstruccion/ejecutar':'ejecutar','/api/reconstruccion/recuperar':'recuperar'}.get(self.path)

        parameters_operation={'/api/parametros/preparar':'preparar_originales','/api/parametros/ejecutar':'ejecutar','/api/parametros/recuperar':'recuperar','/api/parametros/aplicar':'aplicar'}.get(self.path)

        mesh_policy_operation={'/api/politicas-malla/previsualizar':'previsualizar','/api/politicas-malla/aplicar':'aplicar'}.get(self.path)

        digitization_operation={'/api/digitizacion/preparar':'preparar','/api/digitizacion/calcular':'calcular'}.get(self.path)

        contour_operation={'/api/contornos/preparar':'preparar_originales','/api/contornos/ejecutar':'ejecutar','/api/contornos/recuperar':'recuperar'}.get(self.path)

        config_preparation_operation={'/api/configuracion/preparacion/crear':'crear','/api/configuracion/preparacion/guardar':'guardar','/api/configuracion/preparacion/registrar':'registrar',

                                      '/api/configuracion/preparacion/conexiones/proponer':'proponer_conexiones',

                                      '/api/configuracion/preparacion/conexiones/declarar':'declarar_conexiones',

                                      '/api/configuracion/preparacion/lecturas':'leer_propiedades',

                                      '/api/configuracion/preparacion/material':'material_desde_lectura'}.get(self.path)

        config_operation = {'/api/configuracion/importar':'importar','/api/configuracion/revisar':'revisar','/api/configuracion/aprobar':'aprobar'}.get(self.path)

        report_operation={'/api/informe/crear':'crear','/api/informe/aprobar':'aprobar'}.get(self.path)

        credenciales_operation=self.path=='/api/credenciales/guardar'

        intake_operation=self.path=='/api/ingreso/registrar'

        panel_operation=self.path=='/api/panel/crear'

        construction_operation={'/api/construccion/preparar':'preparar','/api/construccion/ejecutar':'ejecutar'}.get(self.path)

        analysis_operation={'/api/analisis/preparar':'preparar','/api/analisis/ejecutar':'ejecutar'}.get(self.path)

        verification_operation={'/api/modelo/verificacion/preparar':'preparar','/api/modelo/verificacion/ejecutar':'ejecutar'}.get(self.path)

        reading_operation={'/api/lectura/preparar':'preparar','/api/lectura/ejecutar':'ejecutar'}.get(self.path)

        visual_operation={'/api/visual/revisar':'revisar','/api/visual/recortar':'recortar','/api/visual/preparar':'preparar','/api/visual/preprocesar':'preprocesar'}.get(self.path)

        model_operation=self.path=='/api/modelo/aprobar'

        conversion_operation={'/api/conversion/crear':'crear','/api/conversion/importar-geometria':'importar_geometria'}.get(self.path)

        tabular_operation={'/api/tabular/crear':'crear','/api/tabular/importar':'importar'}.get(self.path)

        overlay_operation=self.path=='/api/superposicion/crear'

        controls_operation=self.path=='/api/controles/crear'

        result_review_operation=self.path=='/api/revision-resultados/registrar'

        response_operation={'/api/respuesta/registrar':'registrar','/api/respuesta/importar':'importar','/api/respuestas/vincular-proveedor':'vincular_proveedor'}.get(self.path)

        provider_operation={'/api/proveedor/preparar':'preparar','/api/proveedor/ejecutar':'ejecutar','/api/proveedor/recuperar':'recuperar'}.get(self.path)

        context_operation={'/api/contexto/corpus/registrar':'registrar_corpus','/api/contexto/reglas/registrar':'registrar_reglas',

            '/api/contexto/sitio/registrar':'registrar_sitio','/api/contexto/recuperar':'recuperar',

            '/api/contexto/consultar-sitio':'consultar_sitio','/api/contexto/evaluar':'evaluar'}.get(self.path)

        explanation_operation={'/api/explicaciones/preparar':'preparar','/api/explicaciones/ejecutar':'ejecutar','/api/explicaciones/recuperar':'recuperar'}.get(self.path)

        mapping_operation={'/api/mapeo/importar-lectura':'importar_lectura','/api/mapeo/importar':'importar','/api/mapeo/revisar':'revisar','/api/mapeo/aprobar':'aprobar','/api/mapeo/normalizar':'normalizar'}.get(self.path)

        if self.path=='/api/normalizacion/recuperar':mapping_operation='recuperar'

        operation = contour_operation or digitization_operation or mesh_policy_operation or parameters_operation or config_preparation_operation or reconstruction_operation or ('controles' if controls_operation else None) or ('superposicion' if overlay_operation else None) or ('revision_resultados' if result_review_operation else None) or tabular_operation or context_operation or explanation_operation or provider_operation or response_operation or conversion_operation or config_operation or geometry_operation or construction_operation or analysis_operation or verification_operation or reading_operation or visual_operation or mapping_operation or ('credenciales' if credenciales_operation else None) or ('ingreso' if intake_operation else None) or ('panel' if panel_operation else None) or ('modelo' if model_operation else None) or ('informe' if report_operation else None) or {'/api/corregir': 'corregir', '/api/exportar': 'exportar', '/api/importar': 'importar', '/api/reubicar': 'reubicar',

          '/api/lectura-manual': 'lectura_manual'}.get(self.path)

        if operation is None:

            return self.responder(404, {'error': 'Operación inexistente.'})

        try:

            size = int(self.headers.get('Content-Length', '0'))

            limit=(MAX_SOLICITUD if intake_operation else 24*1024*1024 if self.path in ('/api/contexto/corpus/registrar','/api/tabular/crear') else MAX_BODY)

            if not 0 < size <= limit or self.headers.get_content_type() != 'application/json':

                return self.responder(413, {'error': 'Solicitud JSON fuera del límite permitido para esta operación.'})

            self.connection.settimeout(15)

            raw = self.rfile.read(size)

            if len(raw) != size:

                raise ErrorRevision('Solicitud incompleta.')

            body = g.json_desde_bytes(raw, 'solicitud')

            action = self.server.revision.configuraciones.actuar if config_operation else (self.server.revision.actuar_geometria if geometry_operation else self.server.revision.actuar)

            if contour_operation:

                result=getattr(self.server.revision.contornos,contour_operation)(body)

            elif digitization_operation:

                result=getattr(self.server.revision.digitizacion,digitization_operation)(body)

            elif mesh_policy_operation:

                result=getattr(self.server.revision.politicas_malla,mesh_policy_operation)(body)

            elif parameters_operation:

                result=getattr(self.server.revision.parametros,parameters_operation)(body)

            elif config_preparation_operation:

                result=getattr(self.server.revision.preparacion_configuracion,config_preparation_operation)(body)

            elif reconstruction_operation:

                result=getattr(self.server.revision.reconstruccion,reconstruction_operation)(body)

            elif controls_operation:

                result=self.server.revision.controles.crear(body)

            elif overlay_operation:

                result=self.server.revision.superposicion.crear(body)

            elif result_review_operation:

                result=self.server.revision.revision_resultados.registrar(body)

            elif tabular_operation:

                result=getattr(self.server.revision.tabular,tabular_operation)(body)

            elif context_operation:

                result=getattr(self.server.revision.contexto,context_operation)(body)

            elif explanation_operation:

                result=getattr(self.server.revision.explicaciones,explanation_operation)(body)

            elif provider_operation:

                result=getattr(self.server.revision.proveedor,provider_operation)(body)

            elif response_operation:

                try:

                    result=getattr(self.server.revision.respuestas,response_operation)(body)

                except (KeyError,TypeError,AttributeError) as error:

                    raise ValueError('Respuesta visual no verificable.') from error

            elif conversion_operation:

                result=getattr(self.server.revision.conversion,conversion_operation)(body)

            elif construction_operation:

                result=getattr(self.server.revision.ejecucion,construction_operation)(body)

            elif analysis_operation:

                result=getattr(self.server.revision.analisis,analysis_operation)(body)

            elif verification_operation:

                result=getattr(self.server.revision.verificacion_modelo,verification_operation)(body)

            elif reading_operation:

                result=getattr(self.server.revision.lecturas,reading_operation)(body)

            elif visual_operation:

                result=getattr(self.server.revision.preparacion,visual_operation)(body)

            elif model_operation:

                result=self.server.revision.revision_modelo.aprobar(body)

            elif mapping_operation:

                result=getattr(self.server.revision.mapeos,mapping_operation)(body)

            elif panel_operation:

                result=self.server.revision.paneles.crear(body)

            elif credenciales_operation:

                openai_key = (body.get('openai') or '').strip()

                gemini_key = (body.get('gemini') or '').strip()

                path = Path(self.server.revision.raiz) / 'credenciales.local.md'

                from .credenciales_locales import cargar

                try:

                    current = cargar(path) if path.is_file() else {}

                except Exception:

                    current = {}

                if openai_key:

                    current['OPENAI_API_KEY'] = openai_key

                if gemini_key:

                    current['GEMINI_API_KEY'] = gemini_key

                lines = ['# Credenciales locales privadas (no rastreadas por git)', '```env']

                for k, v in sorted(current.items()):

                    lines.append(f'{k} = "{v}"')

                lines.append('```')

                path.write_text('\n'.join(lines), encoding='utf-8')

                result = {'ok': True, 'mensaje': 'Credenciales guardadas localmente.'}

            elif intake_operation:

                result=self.server.revision.ingreso.registrar(body)

            else:

                result = getattr(self.server.revision.entregables,report_operation)(body) if report_operation else action(operation, body)

            return self.responder(201, result)

        except ErrorNormalizacionPendiente:

            return self.responder(409,{'error':'Normalización pendiente: consulta su recuperación antes de publicar otra. No se recalcula automáticamente.',

                'codigo':'normalizacion_pendiente','requiere_recuperacion':True})

        except (ErrorEjecucion, ErrorRevisionModelo, ErrorProveedorWeb, ErrorExplicaciones, ErrorRevisionResultados) as error:

            return self.responder(409, {'error': error.codigo, 'codigo': error.codigo})

        except (ErrorTabular, ErrorSuperposicion, ErrorControles) as error:  # mensajes fijos del servicio, sin rutas

            return self.responder(409, {'error': str(error)})

        except (ValueError, RuntimeError, OSError, TypeError, RecursionError) as error:

            return self.responder(409, {'error': str(error).strip() or 'No se guardó la operación: revisa campos, unidades y vigencia de la evidencia. Recarga la versión antes de reintentar.'})





def main():

    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument('--raiz', type=Path, default=g.RAIZ_PRIVADA)

    parser.add_argument('--puerto', type=int, default=8766)

    parser.add_argument('--sin-navegador', action='store_true')

    args = parser.parse_args()

    server = ServidorRevision(args.raiz, args.puerto)

    print('Revisión local: ' + server.origen, flush=True)

    if not args.sin_navegador:

        threading.Thread(target=webbrowser.open, args=(server.origen,), daemon=True).start()

    try:

        server.serve_forever()

    except KeyboardInterrupt:

        pass

    finally:

        server.server_close()





if __name__ == '__main__':

    main()



