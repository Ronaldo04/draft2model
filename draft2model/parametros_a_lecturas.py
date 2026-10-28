"""Puente de parámetros tipados a la revisión de lecturas ya existente.

Reutiliza la adaptación y comprobación de evidencia del paquete original.
No cambia estados de revisión ni declara cobertura completa del plano.
"""
from __future__ import annotations
import hashlib

from .entrada_vision import cargar_paquete, adaptar_respuesta
from .extraccion_preliminar import UNIDADES_POR_TIPO


def id_lectura(clave):
    return 'P'+hashlib.sha256(clave.encode()).hexdigest()[:24]


def materiales_para_revision(lectura_validada):
    """Correspondencia de IDs, sin calcular ni aprobar propiedades mecánicas."""
    return [{'lectura':id_lectura('material.'+material['id']+'.'+str(i)),
             'material_id':material['id'],'nombre':material['nombre']}
            for material in lectura_validada['datos']['materiales']
            for i,q in enumerate(material['propiedades']) if q['nombre']=='fc']


def _evidencia_en_recorte(evidence,images):
    for image in images:
        if (not image['admite_evidencia'] or image['archivo_id']!=evidence['archivo_id']
                or image['pagina']!=evidence['pagina']):continue
        if image['original_sha256']!=evidence['original_sha256']:raise ValueError('Evidencia de otro original.')
        matrix=image.get('pixel_a_pagina_visible')
        if not isinstance(matrix,list) or len(matrix)!=6 or image.get('tipo_fuente')=='raster_preprocesado':continue
        a,b,c,d,e,f=matrix;det=a*d-b*c
        if det==0:continue
        width,height=image['dimensiones_px'];pw,ph=image.get('pagina_visible_px',image.get('pagina_visible_pt'))
        box=evidence['bbox_normalizada'];points=[]
        for u,v in ((box[0],box[1]),(box[2],box[1]),(box[2],box[3]),(box[0],box[3])):
            x,y=u*pw-e,v*ph-f
            points.append(((d*x-c*y)/det/width,(-b*x+a*y)/det/height))
        bbox=[min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)]
        if 0<=bbox[0]<bbox[2]<=1 and 0<=bbox[1]<bbox[3]<=1:
            return {'imagen_id':image['id'],'bbox_imagen_normalizada':bbox}
    return None


def convertir_a_lecturas(expediente,solicitud,lectura_validada,*,proveedor,modelo,simulado=False):
    request,request_sha,_,_=cargar_paquete(expediente,solicitud);data=lectura_validada['datos']
    if data['caso']!=request['caso']:raise ValueError('Parámetros de otro expediente.')
    table={row['id']:row for row in data['evidencias']};rows=[];pending=[]
    def append(key,kind,value,unit,refs,symbol):
        if unit not in UNIDADES_POR_TIPO[kind]:
            pending.append(key+': unidad no admitida en la revisión de lecturas.');return
        evidence=[]
        for ref in refs:
            match=_evidencia_en_recorte(table[ref],request['imagenes'])
            if match is None:
                pending.append(key+': evidencia sin correspondencia afín en un recorte enviado.');return
            evidence.append(match)
        rows.append({'id':id_lectura(key),'tipo':kind,'valor_propuesto':value,
                     'unidad':unit,'texto_fuente':' | '.join(table[r]['texto'] for r in refs),
                     'simbolo':symbol,'evidencia':evidence})
    for material in data['materiales']:
        for i,q in enumerate(material['propiedades']):
            kind='parametro' if q['nombre']=='poisson' else 'propiedad'
            symbol={'fc':"f'c",'fm':"f'm"}.get(q['nombre'],q['nombre'])
            append('material.'+material['id']+'.'+str(i),kind,q['valor'],q['unidad'],q['evidencias'],symbol)
    for section in data['secciones']:
        for i,q in enumerate(section['parametros']):
            kind='cota' if q['unidad'] in ('m','cm','mm') else 'parametro'
            append('seccion.'+section['id']+'.'+str(i),kind,q['valor'],q['unidad'],q['evidencias'],q['nombre'])
    for load in data['cargas']:
        append('carga.'+load['id'],'carga',load['valor'],load['unidad'],load['evidencias'],load['nombre'])
    used={e['imagen_id'] for row in rows for e in row['evidencia']}
    coverage=[{'imagen_id':image['id'],'estado':'parcial' if image['id'] in used else 'sin_lecturas',
               'observacion':'Lectura dirigida de parámetros; no acredita cobertura completa de esta lámina.'}
              for image in request['imagenes'] if image['admite_evidencia']]
    response={'contrato':'draft2model.respuesta_vision','version_contrato':request['version_contrato'],
              'solicitud_id':request['id'],'solicitud_sha256':request_sha,'candidatos':rows}
    if request['version_contrato']=='0.2.0':response['cobertura']=coverage
    extracted=adaptar_respuesta(expediente,solicitud,response,proveedor=proveedor,modelo=modelo,modo_prueba=simulado)
    return extracted,pending
