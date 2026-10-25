"""Lectura deliberada en instancia nueva de un EDB analizado en su carpeta original."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
from uuid import uuid4

from . import adaptador_etabs as ad
from .evidencia_analisis import verificar_analisis_aceptado
from .gestion_extraccion import carpeta_caso, json_desde_bytes

SCRIPT = Path(__file__).resolve().parents[1]/'scripts'/'leer_analisis_etabs.ps1'
RESULTADOS_API = ('BaseReact', 'AssembledJointMass', 'ConfiguracionAuto')
_DECIMAL = re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?')
CAMPOS_MASA_API = {'unidades','retorno','numero_resultados','point_elements','mass_sources','U1','U2','U3','R1','R2','R3','observaciones'}
UNIDADES = 'kN_m_C'  # unidades explícitas del analizador soportado; no se cambian al leer
TABLAS_CASE = {'Modal Periods And Frequencies', 'Modal Participating Mass Ratios'}
# Tablas de modelo/masa sin campo de caso admitidas explícitamente (se leen completas; el script tiene la misma lista).
TABLAS_SIN_CASO = {'Mass Summary by Story', 'Centers Of Mass And Rigidity', 'Material List by Object Type', 'Material List by Section Property', 'Material List by Story',
                   'Frame Assignments - End Length Offsets'}  # nombres reales ETABS 21 (tmp/cargas185)


def _bytes(data):
    return (json.dumps(data,ensure_ascii=False,sort_keys=True,allow_nan=False,indent=2)+'\n').encode('utf-8')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _seguro(path):
    info=path.lstat()
    if (path.resolve()!=path or stat.S_ISLNK(info.st_mode)
            or getattr(info,'st_file_attributes',0)&stat.FILE_ATTRIBUTE_REPARSE_POINT):
        raise ad.ErrorEvidenciaEtabs('Archivo o directorio enlazado no permitido.')
    return path


def _nuevo(path,raw):
    with path.open('xb') as stream:stream.write(raw)


def _validar_masa_api(masa, unidades):
    """Forma de la captura AssembledJointMass_1; la coherencia de masas la decide masa_ensamblada (sin recortes aquí)."""
    if not isinstance(masa,dict) or set(masa)!=CAMPOS_MASA_API or masa['unidades']!=unidades or type(masa['retorno']) is not int \
            or type(masa['numero_resultados']) is not int or not isinstance(masa['observaciones'],list):
        raise ad.ErrorEvidenciaEtabs('AssembledJointMass tipado incompleto o en otras unidades.')
    for clave in ('point_elements','mass_sources','U1','U2','U3','R1','R2','R3'):
        if not isinstance(masa[clave],list) or len(masa[clave]) not in (masa['numero_resultados'],masa['numero_resultados']+1):
            raise ad.ErrorEvidenciaEtabs('AssembledJointMass con longitudes incoherentes: '+clave)
        textual = clave in ('point_elements','mass_sources')
        # El script emite identificadores str y números como texto 'R'; null solo como posible cola. Nunca bool ni números JSON.
        if any(not (v is None or (type(v) is str and (textual or _DECIMAL.fullmatch(v)))) for v in masa[clave]):
            raise ad.ErrorEvidenciaEtabs('AssembledJointMass con valores no textuales/decimales o booleanos: '+clave)
    if len(masa['observaciones'])!=masa['numero_resultados']:
        raise ad.ErrorEvidenciaEtabs('Observaciones de coordenadas distintas del número de resultados de masa.')
    campos_obs={'point_element','mass_source','global_xyz','point_axes_deg','U1','U2','U3','R1','R2','R3'}
    for o in masa['observaciones']:
        if (not isinstance(o,dict) or set(o)!=campos_obs or type(o['point_element']) is not str or type(o['mass_source']) is not str
                or any(not isinstance(o[k],list) or len(o[k])!=3 for k in ('global_xyz','point_axes_deg'))
                or any(type(v) is not str or not _DECIMAL.fullmatch(v)
                       for v in [*o['global_xyz'],*o['point_axes_deg'],*(o[k] for k in ('U1','U2','U3','R1','R2','R3'))])):
            raise ad.ErrorEvidenciaEtabs('Observación de masa con campos, tipos o números inválidos (booleanos incluidos).')


def _utc(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,7})?(?:Z|\+00:00)',value):
        raise ad.ErrorEvidenciaEtabs('Timestamp UTC de lectura inválido.')
    normalized=re.sub(r'\.(\d{1,7})(?=Z|\+00:00)',lambda m:'.'+m[1][:6].ljust(6,'0'),value)   # 3.10: exactamente 6
    try:datetime.fromisoformat(normalized.replace('Z','+00:00'))
    except ValueError:raise ad.ErrorEvidenciaEtabs('Timestamp UTC de lectura inválido.') from None


def configuracion_real(trabajo, bloqueo=None, *, timeout_s=180, dll=None):
    return ad.ConfiguracionPuente.real(trabajo,bloqueo,timeout_s=timeout_s,dll=dll,script=SCRIPT)


@dataclass
class PreparacionLectura:
    solicitud: ad.SolicitudPreparada
    raiz: Path
    caso: str
    corrida_analisis: Path
    evidencia: dict
    bytes_solicitud: bytes
    argv: tuple


class LectorAnalisis(ad.AdaptadorEtabs):
    def __init__(self, config):
        super().__init__(config)
        self._preparaciones={}

    def preparar_lectura(self, raiz, caso, corrida_analisis, *, tablas, casos, resultados_api=None):
        if resultados_api is not None and (not isinstance(resultados_api,list) or not resultados_api or len(set(resultados_api))!=len(resultados_api)
                                           or not set(resultados_api)<=set(RESULTADOS_API)):
            raise ad.ErrorAdaptador("resultados_api admite BaseReact, AssembledJointMass y ConfiguracionAuto.")
        root=Path(raiz).absolute();run=Path(corrida_analisis).absolute()
        evidence=verificar_analisis_aceptado(root,caso,run)
        if evidence['modo']!=self.config.modo:
            raise ad.ErrorEvidenciaEtabs('Modo de lectura distinto del análisis aceptado.')
        if self.config.modo=='doble' and evidence['datos_sinteticos'] is not True:
            raise ad.ErrorEvidenciaEtabs('Solo datos sintéticos admiten transporte doble.')
        for values in (tablas,casos):
            if (not isinstance(values,list) or not values or not all(isinstance(v,str) and v.strip() for v in values)
                    or len(set(values))!=len(values)):
                raise ad.ErrorAdaptador('Tablas y casos requieren listas explícitas no vacías, sin duplicados.')
        if not set(casos)<=set(evidence['casos']):
            raise ad.ErrorEvidenciaEtabs('Los casos no pertenecen al análisis aceptado.')
        work=Path(self.config.trabajo)
        case=carpeta_caso(root,caso)
        if not work.is_relative_to(case) or work==case:
            raise ad.ErrorAdaptador('El trabajo de lectura debe estar dentro del caso.')
        current=case
        for part in work.relative_to(case).parts:
            current=_seguro(current/part)
        if not work.is_dir():raise ad.ErrorAdaptador('Trabajo de lectura ausente.')
        candidate=work/('0'*32)/'solicitud.json'
        if os.name=='nt' and (len(str(candidate))>=260 or len(str(run/'analizado.edb'))>=260):
            raise ad.ErrorAdaptador('Ruta del lector demasiado larga; use una raíz de expedientes más corta.')
        ident=uuid4().hex;folder=work/ident;folder.mkdir()
        request={'contrato':ad.CONTRATO_SOLICITUD,'version_contrato':ad.VERSION_CONTRATO,
            'id':ident,'operacion':'leer_tablas','modo_configurado':self.config.modo,
            'corrida_analisis_id':run.name,'modelo_esperado':str(run/'analizado.edb'),
            'sha256_edb':evidence['sha256_edb_analizado'],'sha256_aceptacion_analisis':evidence['sha256_aceptacion'],
            'version_etabs_esperada':evidence['version_etabs'],'unidades_esperadas':UNIDADES,
            'tablas':list(tablas),'casos':list(casos),'combinaciones':[],
            'dll':str(self.config.dll or ad.DLL_ETABS)}
        if resultados_api is not None:
            request['resultados_api']=list(resultados_api)
        raw=_bytes(request);path=folder/'solicitud.json';_nuevo(path,raw)
        _nuevo(folder/'evidencia_analisis.json',_bytes(evidence))
        argv=[*self.config.comando,'-Solicitud',str(path),'-Respuesta',str(folder/'respuesta.json'),
              '-Sha256Solicitud',_sha(raw)]
        prepared=ad.SolicitudPreparada(ident,'leer_tablas',folder,path,folder/'respuesta.json',argv,request)
        context=PreparacionLectura(prepared,root,caso,run,evidence,raw,tuple(argv))
        self._preparaciones[ident]=context;self._revalidar(context)
        return context

    def _revalidar(self, context):
        request=context.solicitud
        if (tuple(request.argv)!=context.argv or _seguro(request.solicitud).read_bytes()!=context.bytes_solicitud
                or request.contenido!=json_desde_bytes(context.bytes_solicitud,'solicitud')):
            raise ad.ErrorEvidenciaEtabs('Solicitud de lectura alterada.')
        if verificar_analisis_aceptado(context.raiz,context.caso,context.corrida_analisis)!=context.evidencia:
            raise ad.ErrorEvidenciaEtabs('El análisis o sus fuentes cambiaron.')
        if _seguro(request.carpeta/'evidencia_analisis.json').read_bytes()!=_bytes(context.evidencia):
            raise ad.ErrorEvidenciaEtabs('Snapshot del análisis alterado.')
        if _sha(_seguro(context.corrida_analisis/'analizado.edb').read_bytes())!=context.evidencia['sha256_edb_analizado']:
            raise ad.ErrorEvidenciaEtabs('El EDB analizado cambió.')

    def ejecutar_lectura(self, context, *, confirmar_lectura=False):
        if confirmar_lectura is not True:raise ad.ErrorAdaptador('Confirmación explícita de lectura requerida.')
        if self._preparaciones.get(context.solicitud.id) is not context:
            raise ad.ErrorAdaptador('Preparación ajena al lector.')
        return super().ejecutar(context.solicitud)

    @staticmethod
    def _comprobar_datos(request,data):
        if not isinstance(data,dict):raise ad.ErrorEvidenciaEtabs('Datos de lectura inválidos.')
        expected=request.contenido;states=data.get('estado_casos')
        if (data.get('modelo')!=expected['modelo_esperado'] or data.get('version_etabs')!=expected['version_etabs_esperada']
                or data.get('unidades')!=expected['unidades_esperadas'] or data.get('casos')!=expected['casos']
                or data.get('combinaciones')!=[] or data.get('corrida_analisis_id')!=expected['corrida_analisis_id']
                or data.get('sha256_modelo_verificado')!=expected['sha256_edb']
                or data.get('instancia')!='nueva' or type(data.get('id_proceso')) is not int or data['id_proceso']<=0
                or not isinstance(data.get('inicio_proceso_utc'),str) or not data['inicio_proceso_utc']
                or data.get('instancia_cerrada') is not True
                or data.get('analisis_ejecutado') is not False or data.get('aprueba_resultados') is not False
                or not isinstance(states,dict) or set(states)!=set(expected['casos'])
                or any(type(v) is not int or v!=4 for v in states.values())):
            raise ad.ErrorEvidenciaEtabs('Instancia, fuentes, unidades o estados de lectura no verificables.')
        _utc(data['inicio_proceso_utc'])
        pedido=expected.get('resultados_api')
        if pedido is None:
            if 'resultados_api' in data:raise ad.ErrorEvidenciaEtabs('Resultados API no solicitados.')
        else:
            api=data.get('resultados_api')
            if not isinstance(api,dict) or set(api)!=set(pedido):
                raise ad.ErrorEvidenciaEtabs('Resultados API distintos de los solicitados.')
            if 'AssembledJointMass' in pedido:
                _validar_masa_api(api['AssembledJointMass'], expected['unidades_esperadas'])
            if 'ConfiguracionAuto' in pedido:
                from .estimacion_extremos_auto import validar_captura_configuracion
                try:
                    validar_captura_configuracion(api['ConfiguracionAuto'], expected['unidades_esperadas'], expected['version_etabs_esperada'])
                except ValueError:
                    raise ad.ErrorEvidenciaEtabs('Configuración Auto no verificable.') from None
        if pedido is not None and 'BaseReact' in pedido:
            br=api.get('BaseReact')
            if (not isinstance(br,dict) or set(br)!={'unidades','punto_reaccion','casos_seleccionados','filas'}
                    or br['unidades']!=expected['unidades_esperadas'] or br['casos_seleccionados']!=expected['casos']
                    or not isinstance(br['punto_reaccion'],list) or len(br['punto_reaccion'])!=3 or not isinstance(br['filas'],list)):
                raise ad.ErrorEvidenciaEtabs('BaseReact tipado incompleto o en otras unidades/casos.')
            claves={'LoadCase','StepType','StepNum','FX','FY','FZ','MX','MY','MZ'}
            for valor in br['punto_reaccion']+[v for f in br['filas'] if isinstance(f,dict) for k,v in f.items() if k not in ('LoadCase','StepType')]:
                try:
                    if not isinstance(valor,str) or not math.isfinite(float(valor)):raise ValueError
                except ValueError:
                    raise ad.ErrorEvidenciaEtabs('BaseReact con valor no finito o no textual.') from None
            if any(not isinstance(f,dict) or set(f)!=claves or f['LoadCase'] not in expected['casos'] for f in br['filas']):
                raise ad.ErrorEvidenciaEtabs('Fila BaseReact de otro caso o esquema incoherente.')
        tables=data.get('tablas')
        if not isinstance(tables,list) or len(tables)!=len(expected['tablas']):
            raise ad.ErrorEvidenciaEtabs('Tablas solicitadas no coincidentes.')
        seen=set()
        for table in tables:
            if not isinstance(table,dict) or table.get('clave') not in expected['tablas'] or table['clave'] in seen:
                raise ad.ErrorEvidenciaEtabs('Tabla inesperada o repetida.')
            seen.add(table['clave']);fields=table.get('campos');rows=table.get('filas')
            if (not isinstance(fields,list) or not fields or not all(isinstance(f,str) and f for f in fields)
                    or len(set(fields))!=len(fields) or not isinstance(rows,list)):
                raise ad.ErrorEvidenciaEtabs('Campos o filas de tabla inválidos.')
            case_field='OutputCase' if 'OutputCase' in fields else ('Case' if table['clave'] in TABLAS_CASE and 'Case' in fields else None)
            if case_field is None and table['clave'] not in TABLAS_SIN_CASO:raise ad.ErrorEvidenciaEtabs('Tabla sin campo de caso admitido.')
            if case_field is None and table.get('registros_descartados_por_caso') not in (0,None):
                raise ad.ErrorEvidenciaEtabs('Tabla sin caso no puede descartar filas.')
            for row in rows:
                if (not isinstance(row,dict) or set(row)!=set(fields)
                        or any(value is not None and not isinstance(value,str) for value in row.values())
                        or (case_field is not None and row[case_field] not in expected['casos'])):
                    raise ad.ErrorEvidenciaEtabs('Fila de otro caso o esquema incoherente.')

    def _lanzar(self, request):
        context=self._preparaciones[request.id];self._revalidar(context)
        _nuevo(self.estado_incierto,_bytes({'corrida':request.id,'operacion':'leer_tablas',
            'estado':'lectura_no_confirmada','fecha_utc':datetime.now(timezone.utc).isoformat()}))
        try:
            result=super()._lanzar(request)
            _utc(result.respuesta.get('fin_utc'))
            if not isinstance(result.respuesta.get('avisos'),list) or not all(isinstance(v,str) and v.strip() for v in result.respuesta['avisos']):
                raise ad.ErrorEvidenciaEtabs('Avisos canónicos de lectura inválidos.')
            self._comprobar_datos(request,result.datos)
            self._revalidar(context)
            receipt={'aceptada':True,'operacion':'leer_tablas','modo':self.config.modo,
                'lectura_id':request.id,'corrida_analisis_id':context.evidencia['corrida_id'],
                'sha256_aceptacion_analisis':context.evidencia['sha256_aceptacion'],
                'sha256_edb':context.evidencia['sha256_edb_analizado'],'sha256_solicitud':_sha(context.bytes_solicitud),
                'sha256_respuesta':_sha(_seguro(request.respuesta).read_bytes()),'casos':list(request.contenido['casos']),
                'instancia_nueva_cerrada':True,'analisis_ejecutado':False,'aprueba_resultados':False}
            _nuevo(request.carpeta/'aceptacion_lectura.json',_bytes(receipt))
            _nuevo(request.carpeta/'estado_motor_resuelto.json',self.estado_incierto.read_bytes())
            self.estado_incierto.unlink()
            return result
        except Exception as error:
            if not self.estado_incierto.exists():
                _nuevo(self.estado_incierto,_bytes({'corrida':request.id,'estado':'lectura_no_confirmada'}))
            _nuevo(request.carpeta/'lectura_no_aceptada.json',_bytes({'aceptada':False,'error':str(error),'motor_incierto':True}))
            raise
