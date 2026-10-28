"""Integración del ejecutor con vigencia y validación bajo una única exclusión."""
from __future__ import annotations
import copy
import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime,timezone
from . import adaptador_etabs as ad
from . import ejecutor_etabs as ej
from . import operaciones_etabs as op
from .ingreso import file_hash


@dataclass
class _Contexto:
    raiz: Path
    configuracion: dict
    plan: dict
    preparada: ej.EjecucionPreparada
    solicitud_bytes: bytes
    argv: tuple
    resultado: object = None


class _AdaptadorIntegrado(ad.AdaptadorEtabs):
    def __init__(self,config,supervisor):
        super().__init__(config);self.supervisor=supervisor

    def _lanzar(self,solicitud):
        # AdaptadorEtabs.ejecutar ya adquirió el bloqueo. No volver a adquirirlo.
        context=self.supervisor._contextos[solicitud.id]
        respuesta=None
        try:
            self.supervisor._revalidar(context)
            # Permanece si Python o el puente terminan de forma abrupta. Otro
            # cliente no presume que liberar el lock detuvo al servidor COM.
            ej._escribir_nuevo(self.estado_incierto,ej._json_bytes({'corrida':solicitud.id,
                'estado':'operacion_no_confirmada','modo':self.config.modo,'operacion':ej.OPERACION,
                'fecha_utc':datetime.now(timezone.utc).isoformat()}))
            respuesta=super()._lanzar(solicitud)
            context.resultado=self.supervisor._verificar(context.preparada,respuesta)
            self.supervisor._revalidar(context,final=True)
            resolved=context.preparada.carpeta/'estado_motor_resuelto.json'
            ej._escribir_nuevo(resolved,self.estado_incierto.read_bytes())
            self.estado_incierto.unlink()
            acceptance=context.preparada.carpeta/'aceptacion_integracion.json'
            ej._escribir_nuevo(acceptance,ej._json_bytes({'aceptada':True,'modo':self.config.modo,
                'huella_plan':context.preparada.huella_plan,'guardado':context.resultado.guardado,
                'origen':context.plan['origen'],'analisis_ejecutado':False,'aprueba_modelo':False,
                'fecha_utc':datetime.now(timezone.utc).isoformat()}))
            context.resultado.extra['aceptacion_integracion']=str(acceptance)
            return respuesta
        except Exception as error:
            self.supervisor._registrar_fallo(context,error,respuesta is not None)
            raise


class EjecutorVerificado(ej.EjecutorPlanEtabs):
    """Puerta de construcción: entradas vigentes, exclusión y salida comprobada."""
    def __init__(self,configuracion):
        super().__init__(configuracion)
        self._contextos={};self.adaptador=_AdaptadorIntegrado(self.config,self)

    def preparar(self,raiz,configuracion,plan,**options):
        prepared=super().preparar(raiz,configuracion,plan,**options)
        self._contextos[prepared.solicitud.id]=_Contexto(Path(raiz).resolve(),copy.deepcopy(configuracion),
            copy.deepcopy(plan),prepared,prepared.solicitud.solicitud.read_bytes(),tuple(prepared.solicitud.argv))
        return prepared

    def _revalidar(self,context,final=False):
        prepared=context.preparada
        if tuple(prepared.solicitud.argv)!=context.argv or prepared.solicitud.solicitud.read_bytes()!=context.solicitud_bytes:
            raise ad.ErrorEvidenciaEtabs('La solicitud preparada cambió; no se usa ni reintenta.')
        try:regenerated=op.generar_plan_por_version(context.raiz,context.configuracion,**context.plan['opciones']).datos
        except (ValueError,OSError) as error:raise ad.ErrorEvidenciaEtabs('Configuración o geometría dejaron de estar vigentes.') from error
        if ej._canonico(regenerated)!=ej._canonico(context.plan):
            raise ad.ErrorEvidenciaEtabs('El plan ya no corresponde al expediente/configuración.')
        if file_hash(prepared.copia)!=prepared.solicitud.contenido['sha256_copia']:
            raise ad.ErrorEvidenciaEtabs('La copia de plantilla cambió.')
        if not final:ad._destino_nuevo(prepared.destino)

    def _registrar_fallo(self,context,error,respuesta_exitosa):
        try:trace=ej.leer_traza(context.preparada.carpeta)
        except (OSError,ValueError):trace=[{'ilegible':'No se pudo leer la traza.'}]
        trace=[line if isinstance(line,dict) else {'ilegible':str(line)} for line in trace]
        uncertain=self.estado_incierto.exists() or respuesta_exitosa or isinstance(error,ad.ErrorTiempo) or ej._mutacion_iniciada(trace)
        if uncertain and not self.estado_incierto.exists():
            ej._escribir_nuevo(self.estado_incierto,ej._json_bytes({'corrida':context.preparada.solicitud.id,
                'operacion':ej.OPERACION,'modo':self.config.modo,'estado':'motor_incierto',
                'motivo':'Fallo o resultado final no verificable; revisar motor y conservar artefactos.',
                'fecha_utc':datetime.now(timezone.utc).isoformat()}))
        error.incierto=uncertain;error.traza=trace;error.corrida=context.preparada.carpeta
        ej._escribir_nuevo(context.preparada.carpeta/'revision_integracion_fallida.json',ej._json_bytes({
            'aceptada':False,'incierto':uncertain,'error_tipo':type(error).__name__,
            'mensaje':str(error),'huella_plan':context.preparada.huella_plan}))

    def ejecutar(self,preparada,*,confirmar_mutacion=False):
        if self.config.modo=='real' and confirmar_mutacion is not True:raise ad.ErrorAdaptador('Confirmar explícitamente la mutación real.')
        context=self._contextos.get(preparada.solicitud.id)
        if context is None or context.preparada is not preparada:raise ad.ErrorAdaptador('Preparación ajena a este ejecutor.')
        if preparada.modo!='preparado':raise ad.ErrorAdaptador('La preparación ya se consumió.')
        self.adaptador.ejecutar(preparada.solicitud)
        if context.resultado is None:raise ad.ErrorEvidenciaEtabs('La ejecución no produjo una salida verificada.')
        return context.resultado


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('raiz','configuracion','plan','copia'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--trabajo',type=Path,default=Path('tmp/etabs'))
    parser.add_argument('--bloqueo',type=Path);parser.add_argument('--id-proceso',type=int)
    parser.add_argument('--timeout',type=float,default=900)
    parser.add_argument('--ejecutar',action='store_true',help='Aplicar realmente el plan a la copia abierta, sin analizar')
    args=parser.parse_args(argv)
    from .gestion_extraccion import leer_json
    try:
        args.trabajo.mkdir(parents=True,exist_ok=True)
        executor=EjecutorVerificado(ej.configuracion_real(args.trabajo,args.bloqueo,timeout_s=args.timeout))
        prepared=executor.preparar(args.raiz,leer_json(args.configuracion),leer_json(args.plan),
                                   copia=args.copia.absolute(),modelo_esperado=args.copia.absolute(),id_proceso=args.id_proceso)
        if not args.ejecutar:
            output={'modo':'preparado','ejecuto_etabs':False,'solicitud':str(prepared.solicitud.solicitud),
                    'huella_plan':prepared.huella_plan,'operaciones':prepared.operaciones_totales}
        else:
            result=executor.ejecutar(prepared,confirmar_mutacion=True)
            output={'modo':result.modo_ejecucion,'guardado':result.guardado,'huella_plan':result.huella_plan,
                    'operaciones_ejecutadas':result.operaciones_ejecutadas,'analisis_ejecutado':False,
                    'aprueba_modelo':False,'aceptacion_integracion':result.extra['aceptacion_integracion']}
        print(json.dumps(output,ensure_ascii=False,indent=2));return 0
    except (ValueError,RuntimeError,OSError) as error:
        import sys
        print('Construcción no aceptada: '+str(error),file=sys.stderr);return ad.codigo_salida(error)


if __name__=='__main__':raise SystemExit(main())
