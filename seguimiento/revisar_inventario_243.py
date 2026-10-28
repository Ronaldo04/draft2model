"""Contraejemplos independientes del inventario congelado09A; no modifica producto."""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tmp/revision_codex_243'))
from draft2model import inventario_vectorial as v

def seg(p,q):
    return dict(p=p,q=q,largo=((p[0]-q[0])**2+(p[1]-q[1])**2)**.5,grosor=1)

# Dos bordes de franja, sin cierres verticales, no prueban contorno de columna.
r=v.ajustar_rectangulo([seg((0,0),(32,0)),seg((0,12),(32,12))],(16,6),(.15,.4),.0125)
# Extremos separados .84pt son más distantes que tol=.6pt aunque celdas sean vecinas.
c=v.componentes([seg((0,0),(0,2)),seg((.84,0),(.84,-2))],tol_pt=.6)
out=dict(estado='hallazgos_reproducidos',snapshot='tmp/revision_codex_243',api_llamadas=0,
    comprobaciones=[dict(id='R243-01',esperado='no_ajustado',observado=r,pasa=r['estado']=='no_ajustado'),
                    dict(id='R243-02',esperado_componentes=2,observado_componentes=len(c),pasa=len(c)==2)],
    alcance='Fallos de clasificación/conectividad; no demuestra por sí mismo cuántos elementos del caso real resultan afectados. El inventario continúa sin aprobación.')
(ROOT/'seguimiento/REVISION_INVENTARIO_243.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=ROOT/'seguimiento/claude_ruta/REVISIONES.json'
d=json.loads(p.read_text(encoding='utf-8'))
for ident,description,criterion in [
    ('R243-01','ajustar_rectangulo acepta dos horizontales sin cierres: estadoajustado con lados_verticales_confirmados=0. Contraejemplo0..32pt,y0/12,k.0125,dim.15x.40.',
     'Exigir evidencia de cierre real de ambos lados o clasificar como hipótesis incompleta no ajustada; contar lados distintos, no número de segmentos duplicados. Conservar campos observados, no imponer sección esperada por similitud. Probar cero/un/dos lados, duplicados y cierre por segmentos unidos.'),
    ('R243-02','componentes une extremos en celdas vecinas sin comprobar distancia: dos segmentos con puntos(0,0) y(.84,0),tol.6se fusionan aunque distancia>.6.',
     'Usar celdas solo para candidatos y comprobar distancia euclídea entre extremos antes de union. Probar dentro/fuera/frontera y conexión por cadenas; recalcular inventario si cambia y documentar impacto.')]:
    if not any(x['id']==ident for x in d['observaciones']):
        d['observaciones'].append(dict(id=ident,prioridad='P1_geometria_piloto',etapas=['04','06'],hallazgo=description,
            evidencia='seguimiento/REVISION_INVENTARIO_243.json',criterio_aceptacion=criterion))
if '2f1d24d2ad4b4cdfa4ff49f12299268e' not in d['revisadas']:
    d['revisadas'].append('2f1d24d2ad4b4cdfa4ff49f12299268e')
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out,ensure_ascii=True))
