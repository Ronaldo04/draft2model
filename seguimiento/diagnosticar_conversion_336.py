"""Diagnóstico de la brecha entre lectura y geometría, sin inferir metros ni modelar."""
import hashlib
import json
from pathlib import Path
import pymupdf
from draft2model.calibracion_ejes import ejes_desde_texto,calibrar_cadena
from draft2model.inventario_vectorial import segmentos

root=Path(__file__).resolve().parents[1]
source=root/'data/private/provisional-001/originales/lamina-0001.pdf'
raw=source.read_bytes()
report={'fuente_sha256':hashlib.sha256(raw).hexdigest(),'api_calls':0,'geometria_generada':False,
        'unidad_longitud': 'no_deducida_por_este_diagnostico',
        'conversion_actual':'conversion_geometria exige correspondencias/ejes/coordenadas del operador; no interpreta píxeles ni conectividad.',
        'pasos':{}}
for direction,labels in [('x',list('ABCDEFGHI')),('y',['1','2','3'])]:
    item={}
    try:
        axes=ejes_desde_texto(source,1,labels,direction)
        item['ejes_detectados']=axes
        try:
            # Solo comprobar si existen referencias numéricas vectoriales;
            # no aceptar una escala como metros sin unidad explícita revisada.
            chain=calibrar_cadena(source,1,axes)
            item['referencias_numericas_vectoriales']=chain['referencias']
            item['escala_aceptada']=False
        except ValueError as error:
            item['calibracion_vectorial']=str(error)
    except ValueError as error:
        item['ejes_vectoriales']=str(error)
    report['pasos'][direction]=item
with pymupdf.open(source) as doc:
    bounds=doc[0].rect
    report['palabras_vectoriales']=len(doc[0].get_text('words'))
    report['segmentos_vectoriales']=len(segmentos(source,1,tuple(bounds)))
report['siguiente_criterio']=[
 'Proponer referencias de escala desde cotas con evidencia OCR/vectorial y unidad declarada; abstenerse si falta unidad.',
 'Asociar rótulos a primitivas y proponer conectividad/geometría borrador sin coordenadas codificadas para este piloto.',
 'Medir el borrador contra geometría revisada de planos, antes del cálculo ETABS; no calibrar contra resultados del solver.'
]
assert source.read_bytes()==raw
(root/'seguimiento/DIAGNOSTICO_CONVERSION_336.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ['palabras_vectoriales','segmentos_vectoriales','pasos']},ensure_ascii=False))
