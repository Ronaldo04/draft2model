"""Análisis deliberado en una instancia nueva, desde un modelo revisado exacto."""
from __future__ import annotations
import argparse
import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4
from . import adaptador_etabs as ad
from . import revision_modelo as rm

SCRIPT = Path(__file__).resolve().parents[1]/'scripts'/'analizar_modelo_etabs.ps1'


@dataclass
class PreparacionAnalisis:
    solicitud: ad.SolicitudPreparada
    raiz: Path
    caso: str
    aprobacion: str
    estado: dict
    bytes_solicitud: bytes
    argv: tuple


class AnalizadorEtabs(ad.AdaptadorEtabs):
    def __init__(self, config):
        super().__init__(config)
        self._preparaciones = {}

    def preparar_analisis(self, raiz, caso, aprobacion):
        state = rm.consultar_aprobacion(raiz, caso, aprobacion)
        if state['origen']['modo'] != self.config.modo:
            raise ValueError('El modo del modelo no coincide con el analizador.')
        config = rm._json(rm._leer(state['ruta']/'configuracion.json'))
        cases = config['analisis']['casos_ejecutar']
        if not cases or len(set(cases)) != len(cases):
            raise ValueError('Se requieren casos explícitos, sin duplicados.')
        ident = uuid4().hex; folder = self.config.trabajo/ident; folder.mkdir()
        raw = rm._leer(state['ruta']/'modelo.edb')
        if rm._sha(raw) != state['origen']['sha256_modelo']:
            raise ValueError('Modelo distinto del revisado.')
        ad._escribir_nuevo(folder/'entrada.edb',raw)
        request = {'contrato':ad.CONTRATO_SOLICITUD,'version_contrato':ad.VERSION_CONTRATO,
            'id':ident,'operacion':'analizar_modelo','modo_configurado':self.config.modo,
            'entrada':str(folder/'entrada.edb'),'sha256_entrada':rm._sha(raw),
            'destino':str(folder/'analizado.edb'),'casos':list(cases),
            'modelo_id':state['modelo_id'],'huella_modelo':state['huella_modelo'],
            'aprobacion_id':aprobacion,'sha256_aprobacion':state['sha256_aprobacion'],
            'datos_sinteticos':state['origen']['datos_sinteticos'],
            'dll':str(self.config.dll or ad.DLL_ETABS)}
        request_raw=rm._bytes(request); path=folder/'solicitud.json'
        ad._escribir_nuevo(path,request_raw)
        argv=[*self.config.comando,'-Solicitud',str(path),'-Respuesta',str(folder/'respuesta.json'),
              '-Sha256Solicitud',rm._sha(request_raw)]
        prepared=ad.SolicitudPreparada(ident,'analizar_modelo',folder,path,folder/'respuesta.json',argv,request)
        context=PreparacionAnalisis(prepared,Path(raiz).resolve(),caso,aprobacion,copy.deepcopy(state),request_raw,tuple(argv))
        self._preparaciones[ident]=context
        self._revalidar(context)
        return context

    def _revalidar(self, context):
        request=context.solicitud
        if (tuple(request.argv)!=context.argv or rm._leer(request.solicitud)!=context.bytes_solicitud
                or request.contenido!=rm._json(context.bytes_solicitud)):
            raise ad.ErrorEvidenciaEtabs('Solicitud preparada alterada.')
        state=rm.consultar_aprobacion(context.raiz,context.caso,context.aprobacion)
        if state!=context.estado:
            raise ad.ErrorEvidenciaEtabs('La revisión del modelo cambió.')
        if rm._sha(rm._leer(request.carpeta/'entrada.edb'))!=request.contenido['sha256_entrada']:
            raise ad.ErrorEvidenciaEtabs('Copia de entrada alterada.')

    def ejecutar_analisis(self, prepared, *, confirmar_analisis=False):
        if self.config.modo=='real' and confirmar_analisis is not True:
            raise ad.ErrorAdaptador('Confirmar explícitamente el análisis real.')
        if self._preparaciones.get(prepared.solicitud.id) is not prepared:
            raise ad.ErrorAdaptador('Preparación ajena al analizador.')
        return super().ejecutar(prepared.solicitud)

    def _lanzar(self, request):
        context=self._preparaciones[request.id]
        # Toda la validación/fallo/aceptación se hace bajo el lock del adaptador.
        self._revalidar(context)
        ad._escribir_nuevo(self.estado_incierto,rm._bytes({'corrida':request.id,
            'operacion':'analizar_modelo','estado':'operacion_no_confirmada',
            'fecha_utc':datetime.now(timezone.utc).isoformat()}))
        try:
            response=super()._lanzar(request)
            data=response.datos; expected=request.contenido
            saved=data.get('guardado') or {}
            target=request.carpeta/'analizado.edb'
            if (saved.get('ruta')!=str(target) or not target.is_file()
                    or saved.get('sha256')!=rm._sha(rm._leer(target))
                    or data.get('casos_ejecutados')!=expected['casos']
                    or data.get('estados_casos')!={name:4 for name in expected['casos']}
                    or data.get('sha256_entrada')!=expected['sha256_entrada']
                    or data.get('analisis_ejecutado') is not True or data.get('aprueba_resultados') is not False):
                raise ad.ErrorEvidenciaEtabs('Análisis sin salida y estados de casos verificables.')
            # Modo real: el puente declara el cierre de SU instancia nueva (PID e inicio propios); sin él no se acepta.
            if self.config.modo=='real' and (data.get('instancia_cerrada') is not True or type(data.get('id_proceso')) is not int
                                             or not isinstance(data.get('inicio_proceso_utc'),str) or not data['inicio_proceso_utc']):
                raise ad.ErrorEvidenciaEtabs('Instancia propia de análisis no cerrada o no identificada; no se acepta el análisis.')
            self._revalidar(context)
            acceptance={'aceptada':True,'modo':self.config.modo,'modelo_id':expected['modelo_id'],
                'huella_modelo':expected['huella_modelo'],'aprobacion_id':context.aprobacion,
                'sha256_aprobacion':expected['sha256_aprobacion'],'datos_sinteticos':expected['datos_sinteticos'],
                'guardado':saved,'casos_ejecutados':expected['casos'],'estados_casos':data['estados_casos'],
                'analisis_ejecutado':True,'aprueba_resultados':False,'fecha_utc':datetime.now(timezone.utc).isoformat()}
            ad._escribir_nuevo(request.carpeta/'estado_motor_resuelto.json',self.estado_incierto.read_bytes())
            self.estado_incierto.unlink()
            ad._escribir_nuevo(request.carpeta/'aceptacion_analisis.json',rm._bytes(acceptance))
            return response
        except Exception as error:
            if not self.estado_incierto.exists():
                ad._escribir_nuevo(self.estado_incierto,rm._bytes({'corrida':request.id,
                    'operacion':'analizar_modelo','estado':'aceptacion_no_confirmada',
                    'fecha_utc':datetime.now(timezone.utc).isoformat()}))
            ad._escribir_nuevo(request.carpeta/'analisis_no_aceptado.json',rm._bytes({
                'aceptada':False,'error':str(error),'motor_incierto':True}))
            raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raiz',type=Path,required=True);parser.add_argument('--caso',required=True)
    parser.add_argument('--aprobacion',required=True);parser.add_argument('--trabajo',type=Path,required=True)
    parser.add_argument('--bloqueo',type=Path);parser.add_argument('--timeout',type=float,default=900)
    parser.add_argument('--ejecutar',action='store_true')
    args=parser.parse_args(argv)
    try:
        args.trabajo.mkdir(parents=True,exist_ok=True)
        config=ad.ConfiguracionPuente.real(args.trabajo,args.bloqueo,timeout_s=args.timeout,script=SCRIPT)
        analyzer=AnalizadorEtabs(config);prepared=analyzer.preparar_analisis(args.raiz,args.caso,args.aprobacion)
        if args.ejecutar:
            result=analyzer.ejecutar_analisis(prepared,confirmar_analisis=True)
            output={'modo':result.modo_ejecucion,'datos':result.datos,'corrida':str(result.corrida)}
        else:output={'modo':'preparado','ejecuto_etabs':False,'solicitud':str(prepared.solicitud.solicitud)}
        print(json.dumps(output,ensure_ascii=False,indent=2));return 0
    except (ValueError,RuntimeError,OSError,KeyError,TypeError) as error:
        import sys
        print('Análisis no aceptado: '+str(error),file=sys.stderr);return ad.codigo_salida(error)


if __name__=='__main__':raise SystemExit(main())
