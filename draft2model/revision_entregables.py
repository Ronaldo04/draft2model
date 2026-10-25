"""Informes documentales del expediente: versiones nuevas, fuentes vigentes y descarga."""
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from uuid import uuid4
from datetime import datetime,timezone
from .evidencia_analisis import verificar_evidencia
from .informe import crear_informe,exportar_informe,validar_informe,aprobar_informe
from .gestion_extraccion import json_desde_bytes
from .resultados_estructurales import huella_declaracion,huella_resultados

CAMPOS_CREAR={'caso','resultado','expediente_sha256','contexto','analisis'}
CAMPOS_REFERENCIAS={'evaluacion','recuperacion','sitio','explicacion'}
ESTADOS_EXPLICACION=('completado_llm_verificado','contingencia','incierto_resuelto')


class ServicioEntregables:
    def __init__(self,app):self.app=app

    def _fuentes_masa(self,caso,fingerprint,seleccion,analisis):
        """Solo referencias exactas: nunca inventarios o rutas recibidos del navegador."""
        fuentes={}
        if 'contenido_masa' in seleccion:
            if seleccion['contenido_masa'] is not True:
                raise ValueError('El inventario opcional requiere true; omite el campo si no se selecciona.')
            self._id(analisis)
            fuentes['fuente_contenido_masa']={'raiz':self.app.raiz,'caso':caso}
        if 'masa_nativa' in seleccion:
            ref=seleccion['masa_nativa']
            if (not isinstance(ref,dict) or set(ref) not in ({'trabajo','lectura_id','sha256_respuesta'}, {'trabajo','lectura_id','sha256_respuesta','estimar_auto'})
                    or ('estimar_auto' in ref and ref['estimar_auto'] is not True)
                    or not isinstance(ref['sha256_respuesta'],str)
                    or not re.fullmatch('[0-9a-f]{64}',ref['sha256_respuesta'])):
                raise ValueError('La masa nativa requiere trabajo, lectura y SHA256 exactos.')
            self._id(analisis);self._id(ref['trabajo']);self._id(ref['lectura_id'])
            fuentes['fuente_masa_nativa']={'app':self.app,'caso':caso,'expediente_sha256':fingerprint,**ref}
        return fuentes

    @staticmethod
    def _masa_actual(fuentes,checked,evidencia):
        from .informe import _contenido_masa,_masa_nativa
        return {'contenido_masa':_contenido_masa(fuentes.get('fuente_contenido_masa'),checked['datos'],evidencia),
                'masa_nativa':_masa_nativa(fuentes.get('fuente_masa_nativa'),checked['datos'],evidencia)}

    @staticmethod
    def _id(value):
        if not isinstance(value,str) or not re.fullmatch(r'[0-9a-f]{32}',value):raise ValueError('Identificador inválido.')
        return value

    @staticmethod
    def _seguro(path):
        if path.resolve()!=path:raise ValueError('Ruta enlazada no permitida.')
        return path

    def _caso(self,caso,fingerprint):
        folder,_,actual=self.app.expediente(caso)
        if fingerprint!=actual:raise ValueError('Expediente cambiado; vuelve a consultarlo.')
        return self._seguro(folder)

    def _fuente(self,caso,resultado,fingerprint,analisis):
        checked=self.app.resultados.consultar_resultado(caso,self._id(resultado),expediente_sha256=fingerprint)
        folder=self._caso(caso,fingerprint)
        geo=self._id(checked['datos']['geometria']['id'])
        geometry=self._seguro(folder/'geometrias'/geo/'geometria.json')
        if hashlib.sha256(geometry.read_bytes()).hexdigest()!=checked['datos']['geometria']['sha256']:
            raise ValueError('La geometría ya no coincide.')
        source=None;evidence=None
        if analisis is not None:
            run=self._seguro(folder/'analisis_etabs'/self._id(analisis))
            evidence=verificar_evidencia(self.app.raiz,caso,resultado,run)
            source={'raiz':self.app.raiz,'caso':caso,'resultado':resultado,'corrida':run}
        return checked,geometry,source,evidence

    def _fuente_revision(self,caso,fingerprint,referencia,analisis):
        if referencia is None:
            return None
        if (not isinstance(referencia,dict) or set(referencia)!={'id','sha256_revision'}
                or not isinstance(referencia['sha256_revision'],str)
                or not re.fullmatch('[0-9a-f]{64}',referencia['sha256_revision'])):
            raise ValueError('Selecciona revisión con ID y SHA256 exactos.')
        self._id(referencia['id']);self._id(analisis)
        return {'app':self.app,'caso':caso,'expediente_sha256':fingerprint,**referencia}

    def _fuente_controles(self,caso,fingerprint,referencia,analisis):
        if referencia is None:
            return None
        if (not isinstance(referencia,dict) or set(referencia)!={'id','sha256_controles'}
                or not isinstance(referencia['sha256_controles'],str)
                or not re.fullmatch('[0-9a-f]{64}',referencia['sha256_controles'])):
            raise ValueError('Selecciona controles con ID y SHA256 exactos.')
        self._id(referencia['id']);self._id(analisis)
        return {'app':self.app,'caso':caso,'expediente_sha256':fingerprint,**referencia}

    def _fuente_relectura(self,caso,fingerprint,referencia,analisis):
        if referencia is None:return None
        if (not isinstance(referencia,dict) or set(referencia)!={'trabajo','id','sha256_registro'}
                or not isinstance(referencia['sha256_registro'],str)
                or not re.fullmatch('[0-9a-f]{64}',referencia['sha256_registro'])):
            raise ValueError('Selecciona relectura con trabajo, ID y SHA256 exactos.')
        self._id(referencia['trabajo']);self._id(referencia['id']);self._id(analisis)
        return {'app':self.app,'caso':caso,'expediente_sha256':fingerprint,**referencia}

    @staticmethod
    def _relectura_actual(fuente,checked,evidencia):
        from .informe import _relectura_modelo
        return _relectura_modelo(fuente,checked['datos'],evidencia)

    @staticmethod
    def _controles_actual(fuente,checked,evidencia):
        from .informe import _controles_analisis
        return _controles_analisis(fuente,checked['datos'],evidencia)

    @staticmethod
    def _revision_actual(fuente,checked,evidencia):
        from .informe import _revision_resultados
        return _revision_resultados(fuente,checked['datos'],evidencia)

    # -- contexto verificado y explicación (opcionales) ---------------------------------
    def _validar_referencias(self,refs):
        if not isinstance(refs,dict) or set(refs)!=CAMPOS_REFERENCIAS:
            raise ValueError('referencias requiere exactamente evaluacion, recuperacion, sitio y explicacion (UUID o null).')
        for value in refs.values():
            if value is not None:self._id(value)
        return dict(refs)

    def _contexto(self):
        servicio=getattr(self.app,'contexto',None)
        if servicio is None:
            from .revision_contexto import ServicioContexto
            servicio=ServicioContexto(self.app)
        return servicio

    def _explicaciones(self):
        servicio=getattr(self.app,'explicaciones',None)
        if servicio is None:
            from .revision_explicaciones import ServicioExplicaciones
            servicio=ServicioExplicaciones(self.app)
        return servicio

    def _referencias(self,caso,fingerprint,resultado,huella,refs):
        """Derivados reproducidos por ServicioContexto y trabajo de explicación vigente; solo IDs y huellas."""
        ctx=self._contexto();folder=self._caso(caso,fingerprint)
        ligado={'id':resultado,'huella':huella};cv={};salidas={}
        for tipo in ('evaluacion','recuperacion','sitio'):
            ident=refs[tipo]
            if ident is None:
                cv[tipo]=None;continue
            item=ctx.consultar_derivado(caso,ident,expediente_sha256=fingerprint)
            if item['tipo']!=tipo or item.get('vigente') is not True:raise ValueError('La referencia no corresponde a un derivado de ese tipo vigente.')
            vinculado=item['fuentes'].get('resultado')
            if (tipo=='evaluacion' and vinculado!=ligado) or (vinculado is not None and vinculado!=ligado):
                raise ValueError('El derivado pertenece a otro resultado o a otra huella.')
            cv[tipo]={'id':ident,'sha256_salida':item['sha256_salida'],'fuentes':item['fuentes']};salidas[tipo]=item['salida']
        reglas=evaluacion=corpus=sitio=None;citas=None
        if cv['evaluacion'] is not None:
            rid=self._id(cv['evaluacion']['fuentes']['reglas']['id'])
            ctx.consultar(caso,'reglas',rid,expediente_sha256=fingerprint)  # validador nativo y huellas del registro
            reglas=json_desde_bytes(self._seguro(folder/'contexto'/'reglas'/rid/'reglas.json').read_bytes(),'reglas.json')
            if huella_declaracion(reglas)!=cv['evaluacion']['fuentes']['reglas']['huella']:raise ValueError('Reglas distintas de la evaluación.')
            evaluacion=salidas['evaluacion']
        if cv['recuperacion'] is not None:
            cid=self._id(cv['recuperacion']['fuentes']['corpus']['id'])
            ctx.consultar(caso,'corpus',cid,expediente_sha256=fingerprint)
            corpus=self._seguro(folder/'contexto'/'corpus'/cid/'corpus.json')
            citas=[{'fragmento_id':f['id'],'texto':f['texto']} for f in salidas['recuperacion']['fragmentos']]
        if cv['sitio'] is not None:
            sitio=salidas['sitio']
        explicacion=None
        if refs['explicacion'] is not None:
            job=self._explicaciones().consultar(caso,refs['explicacion'])
            esperados={k:refs[k] for k in ('recuperacion','evaluacion','sitio')}
            if (job['estado'] not in ESTADOS_EXPLICACION or job.get('vigente') is not True or job.get('salida') is None
                    or job['resultado']!=resultado or job['huella_resultados']!=huella or job['expediente_sha256']!=fingerprint
                    or job['derivados']!=esperados):
                raise ValueError('La explicación no está terminada, vigente o ligada a estas referencias exactas.')
            salida=job['salida']
            llm=salida['declaraciones_llm']
            explicacion={'trabajo':job['id'],'estado_trabajo':job['estado'],'huella_salida':huella_resultados(salida),
                         'modo':salida['modo'],'causa':salida['causa'],'generacion_llm_real':salida['generacion_llm_real'],
                         'modo_transporte':salida['modo_transporte'],'modelo_declarado':salida['modelo_declarado'],
                         'declaraciones':llm['declaraciones'] if llm else None,
                         'abstenciones':salida['deterministico']['abstenciones']+(llm['abstenciones'] if llm else []),
                         'limites_verificables':salida['deterministico']['limites_verificables'],
                         'estado_revision':'propuesta_pendiente_revision_humana'}
        firma={'cv':cv,'reglas':reglas,'evaluacion':evaluacion,'citas':citas,'sitio':sitio,'explicacion':explicacion,
               'corpus':corpus.read_bytes() if corpus else None}
        return {'reglas':reglas,'evaluacion':evaluacion,'corpus':corpus,'citas':citas,'sitio':sitio,
                'contexto_verificado':cv,'explicacion':explicacion,'firma':firma}

    @staticmethod
    def _contexto_informe(contexto,refs_data):
        if refs_data is None:
            return contexto
        if not isinstance(contexto,dict) or contexto.get('sitio') is not None:
            raise ValueError('Con referencias, el sitio solo proviene del derivado comprobado; envía sitio null.')
        return {**contexto,'sitio':refs_data['sitio']}

    def _construir(self,checked,geometry,source,contexto,refs_data,revision_source=None,controles_source=None,relectura_source=None,masa_sources=None):
        masa_sources=masa_sources or {}
        if refs_data is None:
            return crear_informe(checked['datos'],None,contexto,geometria_archivo=geometry,evidencia_analisis=source,fuente_revision_resultados=revision_source,
                                 fuente_controles_analisis=controles_source,fuente_relectura_modelo=relectura_source,**masa_sources)
        return crear_informe(checked['datos'],refs_data['reglas'],self._contexto_informe(contexto,refs_data),
                             evaluacion=refs_data['evaluacion'],geometria_archivo=geometry,corpus=refs_data['corpus'],
                             citas=refs_data['citas'],evidencia_analisis=source,
                             contexto_verificado=refs_data['contexto_verificado'],explicacion=refs_data['explicacion'],
                             fuente_revision_resultados=revision_source,fuente_controles_analisis=controles_source,fuente_relectura_modelo=relectura_source,**masa_sources)

    def listar_analisis(self,caso,resultado,*,expediente_sha256,modo='verificado'):
        if modo not in ('verificado','inventario'):
            raise ValueError('Modo de consulta de análisis no admitido.')
        with self.app.lock:
            if modo == 'inventario':
                # Solo pertenencia física e IDs: ni el resultado ni el vínculo están comprobados.
                folder=self._caso(caso,expediente_sha256)
                version=self._seguro(folder/'resultados_estructurales'/self._id(resultado))
                if not self._seguro(version/'resultados.json').is_file():
                    raise ValueError('Resultado no registrado en este expediente.')
                base=self._seguro(folder/'analisis_etabs')
                rows=[]
                for path in sorted(base.iterdir()) if base.is_dir() else []:
                    if re.fullmatch(r'[0-9a-f]{32}',path.name) and self._seguro(path).is_dir():
                        rows.append({'id':path.name,'vigente':None,'verificacion':'pendiente','estados':None,'casos':None})
                self._caso(caso,expediente_sha256)
                return {'modo':'inventario','versiones':rows}
            self._fuente(caso,resultado,expediente_sha256,None)
            base=self._seguro(self._caso(caso,expediente_sha256)/'analisis_etabs');rows=[]
            for path in sorted(base.iterdir()) if base.is_dir() else []:
                if not re.fullmatch(r'[0-9a-f]{32}',path.name):continue
                try:
                    _,_,_,ev=self._fuente(caso,resultado,expediente_sha256,path.name)
                    rows.append({'id':path.name,'vigente':True,'estados':ev['estados'],'casos':ev['analisis']['casos']})
                except (ValueError,OSError,KeyError,TypeError):rows.append({'id':path.name,'vigente':False})
            self._caso(caso,expediente_sha256)
            return {'versiones':rows}

    def comprobar_analisis(self,caso,resultado,analisis,*,expediente_sha256):
        with self.app.lock:
            ident=self._id(analisis)
            _,_,_,ev=self._fuente(caso,resultado,expediente_sha256,ident)
            self._caso(caso,expediente_sha256)
            return {'id':ident,'vigente':True,'verificacion':'completa',
                    'estados':ev['estados'],'casos':ev['analisis']['casos']}

    def crear(self,body):
        if not isinstance(body,dict) or not CAMPOS_CREAR<=set(body) or set(body)-CAMPOS_CREAR-{'referencias','revision_resultados','controles_analisis','relectura_modelo','contenido_masa','masa_nativa'}:
            raise ValueError('Selecciona expediente, resultado y contexto completos.')
        with self.app.lock:
            caso=body['caso'];fingerprint=body['expediente_sha256']
            refs=self._validar_referencias(body['referencias']) if 'referencias' in body else None
            if 'revision_resultados' in body and body['revision_resultados'] is None:raise ValueError('Omite la revisión opcional; null no es una selección.')
            revision_source=self._fuente_revision(caso,fingerprint,body.get('revision_resultados'),body['analisis'])
            if 'controles_analisis' in body and body['controles_analisis'] is None:raise ValueError('Omite los controles opcionales; null no es una selección.')
            controles_source=self._fuente_controles(caso,fingerprint,body.get('controles_analisis'),body['analisis'])
            if 'relectura_modelo' in body and body['relectura_modelo'] is None:raise ValueError('Omite la relectura opcional; null no es una selección.')
            relectura_source=self._fuente_relectura(caso,fingerprint,body.get('relectura_modelo'),body['analisis'])
            masa_sources=self._fuentes_masa(caso,fingerprint,body,body['analisis'])
            checked,geometry,source,_=self._fuente(caso,body['resultado'],fingerprint,body['analisis'])
            refs_data=self._referencias(caso,fingerprint,body['resultado'],checked['huella'],refs) if refs else None
            report=self._construir(checked,geometry,source,body['contexto'],refs_data,revision_source,controles_source,relectura_source,masa_sources)
            folder=self._caso(caso,fingerprint);base=self._seguro(folder/'informes');base.mkdir(exist_ok=True)
            ident=uuid4().hex;target=base/ident
            with tempfile.TemporaryDirectory(prefix='.informe-',dir=base) as temp:
                stage=Path(temp).resolve()
                if stage.parent!=base:raise ValueError('Temporal fuera del caso.')
                bundle=stage/'paquete'
                exportar_informe(report,bundle,geometria_archivo=geometry,corpus=refs_data['corpus'] if refs_data else None,
                                 evidencia_analisis=source,fuente_revision_resultados=revision_source,fuente_controles_analisis=controles_source,fuente_relectura_modelo=relectura_source,**masa_sources)
                hashes={name:hashlib.sha256((bundle/name).read_bytes()).hexdigest() for name in ('informe.json','informe.html','informe.pdf')}
                current,_,_,_=self._fuente(caso,body['resultado'],fingerprint,body['analisis'])
                if current!=checked:raise ValueError('Las fuentes cambiaron al generar el informe.')
                if refs and self._referencias(caso,fingerprint,body['resultado'],checked['huella'],refs)['firma']!=refs_data['firma']:
                    raise ValueError('El contexto o la explicación cambiaron al generar el informe.')
                meta={'id':ident,'caso':caso,'resultado':body['resultado'],'huella_resultados':checked['huella'],
                      'analisis':body['analisis'],'expediente_sha256':fingerprint,'archivos':hashes,
                      'creado_utc':datetime.now(timezone.utc).isoformat(),'estado':'borrador','aprueba_resultados':False}
                if refs:meta['referencias']=refs
                for key in ('contenido_masa','masa_nativa'):
                    if key in body:meta[key]=body[key]
                if revision_source:meta['revision_resultados']=body['revision_resultados']
                if controles_source:meta['controles_analisis']=body['controles_analisis']
                if relectura_source:meta['relectura_modelo']=body['relectura_modelo']
                (bundle/'paquete.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
                self._leer_version(caso,ident,fingerprint,ruta=bundle)
                if os.path.lexists(target):raise ValueError('Destino existente; no se sobrescribe.')
                bundle.rename(target)
            return self.consultar(caso,ident,expediente_sha256=fingerprint)

    def listar(self,caso,resultado,*,expediente_sha256,modo='verificado'):
        if modo not in ('verificado','inventario'):
            raise ValueError('Modo de consulta de informes no admitido.')
        with self.app.lock:
            if modo == 'inventario':
                # El manifiesto se usa solo para filtrar candidatos, nunca para dar vigencia.
                folder=self._caso(caso,expediente_sha256)
                version=self._seguro(folder/'resultados_estructurales'/self._id(resultado))
                if not self._seguro(version/'resultados.json').is_file():
                    raise ValueError('Resultado no registrado en este expediente.')
                base=self._seguro(folder/'informes');rows=[]
                for path in sorted(base.iterdir()) if base.is_dir() else []:
                    if not re.fullmatch(r'[0-9a-f]{32}',path.name):continue
                    try:
                        candidate=json.loads(self._seguro(path/'paquete.json').read_bytes())
                        if not isinstance(candidate,dict) or candidate.get('resultado')!=resultado:continue
                    except (ValueError,OSError,TypeError):continue
                    rows.append({'id':path.name,'vigente':None,'verificacion':'pendiente',
                                 'estado':None,'analisis':None})
                self._caso(caso,expediente_sha256)
                return {'modo':'inventario','versiones':rows}
            self._fuente(caso,resultado,expediente_sha256,None)
            base=self._seguro(self._caso(caso,expediente_sha256)/'informes');rows=[]
            for path in sorted(base.iterdir()) if base.is_dir() else []:
                if not re.fullmatch(r'[0-9a-f]{32}',path.name):continue
                try:
                    candidate=json.loads(self._seguro(path/'paquete.json').read_bytes())
                    if not isinstance(candidate,dict) or candidate.get('resultado')!=resultado:continue
                except (ValueError,OSError,TypeError):continue
                try:
                    meta=self.consultar(caso,path.name,expediente_sha256=expediente_sha256)
                    if meta['resultado']==resultado:rows.append({'id':path.name,'vigente':True,'estado':meta['estado'],'analisis':meta['analisis'],
                                                                 'referencias':meta.get('referencias')})
                except (ValueError,OSError,TypeError,KeyError):rows.append({'id':path.name,'vigente':False})
            self._caso(caso,expediente_sha256)
            return {'versiones':rows}

    def _leer_version(self,caso,version,expediente_sha256,*,ruta=None,solo_borrador=False):
        folder=self._caso(caso,expediente_sha256)
        target=self._seguro(ruta if ruta is not None else folder/'informes'/self._id(version))
        raw_meta=self._seguro(target/'paquete.json').read_bytes()
        meta=json_desde_bytes(raw_meta,'paquete.json')
        fields={'id','caso','resultado','huella_resultados','analisis','expediente_sha256','archivos','creado_utc','estado','aprueba_resultados'}
        approved=isinstance(meta,dict) and meta.get('estado')=='aprobado'
        expected=fields|({'padre'} if approved else set())
        if isinstance(meta,dict):expected=expected|({'referencias','revision_resultados','controles_analisis','relectura_modelo','contenido_masa','masa_nativa'}&set(meta))
        if (not isinstance(meta,dict) or set(meta)!=expected
                or meta['id']!=version or meta['caso']!=caso
                or meta['expediente_sha256']!=expediente_sha256 or meta['estado'] not in ('borrador','aprobado') or meta['aprueba_resultados'] is not False
                or (solo_borrador and approved)
                or not isinstance(meta['archivos'],dict)
                or set(meta['archivos'])!={'informe.json','informe.html','informe.pdf'}
                or any(not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha) for sha in meta['archivos'].values())):
            raise ValueError('Paquete documental inválido.')
        refs=self._validar_referencias(meta['referencias']) if 'referencias' in meta else None
        if 'revision_resultados' in meta and meta['revision_resultados'] is None:raise ValueError('Revisión seleccionada inválida.')
        revision_source=self._fuente_revision(caso,expediente_sha256,meta.get('revision_resultados'),meta['analisis'])
        if 'controles_analisis' in meta and meta['controles_analisis'] is None:raise ValueError('Controles seleccionados inválidos.')
        controles_source=self._fuente_controles(caso,expediente_sha256,meta.get('controles_analisis'),meta['analisis'])
        if 'relectura_modelo' in meta and meta['relectura_modelo'] is None:raise ValueError('Relectura seleccionada inválida.')
        relectura_source=self._fuente_relectura(caso,expediente_sha256,meta.get('relectura_modelo'),meta['analisis'])
        masa_sources=self._fuentes_masa(caso,expediente_sha256,meta,meta['analisis'])
        contents={name:self._seguro(target/name).read_bytes() for name in meta['archivos']}
        for name,sha in meta['archivos'].items():
            if hashlib.sha256(contents[name]).hexdigest()!=sha:raise ValueError('Informe alterado.')
        checked,geometry,source,ev=self._fuente(caso,meta['resultado'],expediente_sha256,meta['analisis'])
        report=json_desde_bytes(contents['informe.json'],'informe.json');validar_informe(report)
        snapshot={'datos':json.loads(geometry.read_bytes()),'sha256_archivo':checked['datos']['geometria']['sha256'],
                  'version_id_declarada':checked['datos']['geometria']['id']}
        if report['geometria']!=snapshot:raise ValueError('La geometría del informe no corresponde a su fuente.')
        if report['revision']['estado']!=meta['estado']:raise ValueError('La revisión documental no coincide.')
        if (checked['huella']!=meta['huella_resultados'] or report['resultados']!=checked['datos']
                or report.get('evidencia_analisis')!=ev):raise ValueError('Informe de otras fuentes.')
        revision_actual=self._revision_actual(revision_source,checked,ev)
        if report.get('revision_resultados')!=revision_actual:raise ValueError('La revisión del informe no corresponde a la fuente vigente.')
        controles_actual=self._controles_actual(controles_source,checked,ev)
        if report.get('controles_analisis')!=controles_actual:raise ValueError('Los controles del informe no corresponden a la fuente vigente.')
        relectura_actual=self._relectura_actual(relectura_source,checked,ev)
        if report.get('relectura_modelo')!=relectura_actual:raise ValueError('La relectura del informe no corresponde a su fuente vigente.')
        masa_actual=self._masa_actual(masa_sources,checked,ev)
        if any(report.get(k)!=v for k,v in masa_actual.items()):
            raise ValueError('La masa del informe no corresponde a las fuentes vigentes.')
        refs_data=None
        if refs is None:
            if 'contexto_verificado' in report or 'explicacion' in report:raise ValueError('Contexto verificado sin referencias registradas.')
        else:
            # Las fuentes del contexto se reproducen ahora: un cambio invalida informe, aprobación y descarga
            # aunque los bytes y hashes del paquete sigan iguales.
            refs_data=self._referencias(caso,expediente_sha256,meta['resultado'],checked['huella'],refs)
            if report['contexto']['sitio']!=refs_data['sitio']:
                raise ValueError('El sitio del informe no corresponde al derivado.')
            contexto={**report['contexto'],'sitio':None}
            rebuilt=self._construir(checked,geometry,source,contexto,refs_data,revision_source,controles_source,relectura_source,masa_sources)
            if {k:v for k,v in rebuilt.items() if k!='revision'}!={k:v for k,v in report.items() if k!='revision'}:
                raise ValueError('El informe no corresponde a su contexto o explicación vigentes.')
        parent_snapshot=None
        if approved:
            parent=meta['padre']
            if (not isinstance(parent,dict) or set(parent)!={'id','sha256_informe','sha256_paquete'}
                    or parent.get('id')==version
                    or any(not isinstance(parent.get(k),str) or not re.fullmatch('[0-9a-f]{64}',parent[k])
                           for k in ('sha256_informe','sha256_paquete'))):
                raise ValueError('Vínculo de padre inválido.')
            self._id(parent['id'])
            pm,pr,praw=self._leer_version(caso,parent['id'],expediente_sha256,solo_borrador=True)
            if (hashlib.sha256(praw).hexdigest()!=parent['sha256_paquete']
                    or pm['archivos']['informe.json']!=parent['sha256_informe']
                    or pm.get('referencias')!=meta.get('referencias')
                    or pm.get('revision_resultados_seleccionada')!=meta.get('revision_resultados')
                    or pm.get('controles_analisis_seleccionados')!=meta.get('controles_analisis')
                    or pm.get('contenido_masa_seleccionado')!=meta.get('contenido_masa')
                    or pm.get('masa_nativa_seleccionada')!=meta.get('masa_nativa')
                    or pm.get('relectura_modelo_seleccionada')!=meta.get('relectura_modelo')
                    or {k:v for k,v in report.items() if k!='revision'}!={k:v for k,v in pr.items() if k!='revision'}):
                raise ValueError('El padre o contenido documental ya no corresponde.')
            parent_snapshot=(pm,pr,praw)
        current,_,_,current_ev=self._fuente(caso,meta['resultado'],expediente_sha256,meta['analisis'])
        if current!=checked or current_ev!=ev:raise ValueError('Las fuentes cambiaron durante la consulta.')
        if self._revision_actual(revision_source,current,current_ev)!=revision_actual:raise ValueError('La revisión cambió durante la consulta.')
        if self._controles_actual(controles_source,current,current_ev)!=controles_actual:raise ValueError('Los controles cambiaron durante la consulta.')
        if self._relectura_actual(relectura_source,current,current_ev)!=relectura_actual:raise ValueError('La relectura cambió durante la consulta.')
        if self._masa_actual(masa_sources,current,current_ev)!=masa_actual:
            raise ValueError('Las fuentes de masa cambiaron durante la consulta.')
        if refs is not None and self._referencias(caso,expediente_sha256,meta['resultado'],checked['huella'],refs)['firma']!=refs_data['firma']:
            raise ValueError('El contexto cambió durante la consulta.')
        if parent_snapshot is not None:
            again=self._leer_version(caso,meta['padre']['id'],expediente_sha256,solo_borrador=True)
            if again!=parent_snapshot:raise ValueError('El padre cambió durante la consulta.')
        self._caso(caso,expediente_sha256)
        if self._seguro(target/'paquete.json').read_bytes()!=raw_meta:
            raise ValueError('El paquete cambió durante la consulta.')
        for name,raw in contents.items():
            if self._seguro(target/name).read_bytes()!=raw:raise ValueError('El informe cambió durante la consulta.')
        extra={}
        if refs is not None:
            ex=report.get('explicacion')
            extra={'contexto_verificado':{k:(None if v is None else {'id':v['id'],'sha256_salida':v['sha256_salida']})
                                          for k,v in report['contexto_verificado'].items()},
                   'explicacion':None if ex is None else {k:ex[k] for k in ('trabajo','modo','causa','generacion_llm_real',
                                                                           'estado_revision')}}
        return ({**meta,**extra,**masa_actual,
                 'contenido_masa_seleccionado':meta.get('contenido_masa'),
                 'masa_nativa_seleccionada':meta.get('masa_nativa'),'evidencia_analisis':ev,'revision_resultados':'revisados_declarados' if revision_actual is not None else 'pendiente',
                 **({'revision_resultados_seleccionada':meta['revision_resultados']} if revision_actual is not None else {}),
                 **({'controles_analisis_seleccionados':meta['controles_analisis'],
                     'controles_analisis':{'estado_global':controles_actual['contenido']['estado_global'],
                                           'apto_proyeccion_controlado':controles_actual['contenido']['apto_proyeccion_controlado']}}
                    if controles_actual is not None else {}),
                 **({'relectura_modelo_seleccionada':meta['relectura_modelo'],'relectura_modelo':relectura_actual} if relectura_actual is not None else {}),
                 'conformidad_normativa':'no_evaluada'},report,raw_meta)

    def consultar(self,caso,version,*,expediente_sha256):
        with self.app.lock:
            self._id(version)
            return self._leer_version(caso,version,expediente_sha256)[0]

    def aprobar(self,body):
        fields={'caso','version','expediente_sha256','sha256_informe','revisor_declarado','fecha','motivo','confirmacion_explicita'}
        if not isinstance(body,dict) or set(body)!=fields or body['confirmacion_explicita'] is not True:
            raise ValueError('La aprobación documental requiere campos exactos y confirmación explícita true.')
        with self.app.lock:
            caso=body['caso'];fp=body['expediente_sha256'];version=self._id(body['version'])
            before,report,parent_raw=self._leer_version(caso,version,fp,solo_borrador=True)
            if body['sha256_informe']!=before['archivos']['informe.json']:
                raise ValueError('El informe abierto cambió; vuelve a consultarlo.')
            approved=aprobar_informe(report,revisor_declarado=body['revisor_declarado'],fecha=body['fecha'],motivo=body['motivo'])
            checked,geometry,source,_=self._fuente(caso,before['resultado'],fp,before['analisis'])
            refs=before.get('referencias')
            revision_ref=before.get('revision_resultados_seleccionada')
            revision_source=self._fuente_revision(caso,fp,revision_ref,before['analisis'])
            controles_ref=before.get('controles_analisis_seleccionados')
            controles_source=self._fuente_controles(caso,fp,controles_ref,before['analisis'])
            relectura_ref=before.get('relectura_modelo_seleccionada')
            relectura_source=self._fuente_relectura(caso,fp,relectura_ref,before['analisis'])
            seleccion_masa={}
            if before.get('contenido_masa_seleccionado') is not None:seleccion_masa['contenido_masa']=before['contenido_masa_seleccionado']
            if before.get('masa_nativa_seleccionada') is not None:seleccion_masa['masa_nativa']=before['masa_nativa_seleccionada']
            masa_sources=self._fuentes_masa(caso,fp,seleccion_masa,before['analisis'])
            refs_data=self._referencias(caso,fp,before['resultado'],checked['huella'],refs) if refs else None
            folder=self._caso(caso,fp);base=self._seguro(folder/'informes');ident=uuid4().hex;target=base/ident
            with tempfile.TemporaryDirectory(prefix='.informe-',dir=base) as temp:
                stage=Path(temp).resolve()
                if stage.parent!=base:raise ValueError('Temporal fuera del caso.')
                bundle=stage/'paquete'
                exportar_informe(approved,bundle,geometria_archivo=geometry,corpus=refs_data['corpus'] if refs_data else None,
                                 evidencia_analisis=source,fuente_revision_resultados=revision_source,fuente_controles_analisis=controles_source,fuente_relectura_modelo=relectura_source,**masa_sources)
                hashes={name:hashlib.sha256(self._seguro(bundle/name).read_bytes()).hexdigest() for name in ('informe.json','informe.html','informe.pdf')}
                if self._leer_version(caso,version,fp,solo_borrador=True)!=(before,report,parent_raw):
                    raise ValueError('El padre cambió durante la aprobación.')
                current,_,_,_=self._fuente(caso,before['resultado'],fp,before['analisis'])
                if current!=checked:raise ValueError('Las fuentes cambiaron durante la aprobación.')
                if refs and self._referencias(caso,fp,before['resultado'],checked['huella'],refs)['firma']!=refs_data['firma']:
                    raise ValueError('El contexto cambió durante la aprobación.')
                meta={'id':ident,'caso':caso,'resultado':before['resultado'],'huella_resultados':before['huella_resultados'],
                    'analisis':before['analisis'],'expediente_sha256':fp,'archivos':hashes,
                    'creado_utc':datetime.now(timezone.utc).isoformat(),'estado':'aprobado','aprueba_resultados':False,
                    'padre':{'id':version,'sha256_informe':body['sha256_informe'],'sha256_paquete':hashlib.sha256(parent_raw).hexdigest()}}
                if refs:meta['referencias']=refs
                if revision_ref is not None:meta['revision_resultados']=revision_ref
                if controles_ref is not None:meta['controles_analisis']=controles_ref
                meta.update(seleccion_masa)
                if relectura_ref is not None:meta['relectura_modelo']=relectura_ref
                (bundle/'paquete.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
                _,staged_report,_=self._leer_version(caso,ident,fp,ruta=bundle)
                if staged_report!=approved:raise ValueError('El informe aprobado cambió en staging.')
                if os.path.lexists(target):raise ValueError('Destino existente; no se sobrescribe.')
                bundle.rename(target)
            return self.consultar(caso,ident,expediente_sha256=fp)

    def archivo(self,caso,version,formato,*,expediente_sha256):
        if formato not in ('pdf','html','json'):raise ValueError('Formato no permitido.')
        with self.app.lock:
            meta=self.consultar(caso,version,expediente_sha256=expediente_sha256)
            path=self._seguro(self._caso(caso,expediente_sha256)/'informes'/version/('informe.'+formato))
            raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=meta['archivos']['informe.'+formato]:raise ValueError('Informe cambiado.')
            self.consultar(caso,version,expediente_sha256=expediente_sha256)
            return raw
