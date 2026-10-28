from pathlib import Path
import fitz
root=Path(__file__).resolve().parents[1];dest=root/'seguimiento/revision_antigravity_328'
regions=[(2,'plan-arriba-izq',(.10,.045,.20,.18)),(2,'plan-arriba-der',(.37,.14,.49,.30)),
         (2,'corte1',(.68,.085,.77,.205)),(3,'pl7',(.37,.23,.46,.40)),(3,'tabla',(.78,.35,.87,.405))]
for i,name,box in regions:
 doc=fitz.open(root/'seguimiento/ANTIGRAVITY_REFERENCIA_327/entradas/originales'/f'lamina-{i:04d}.pdf');p=doc[0];r=p.rect
 rect=fitz.Rect(box[0]*r.width,box[1]*r.height,box[2]*r.width,box[3]*r.height)
 p.get_pixmap(matrix=fitz.Matrix(5,5),clip=rect).save(dest/(name+'.png'))
