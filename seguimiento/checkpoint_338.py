"""Punto de continuación por cuota, sin dejar procesos ni integrar cambios en331."""
import hashlib
import json
from pathlib import Path
from datetime import datetime,timezone,timedelta

root=Path(__file__).resolve().parents[1]
folder=root/'seguimiento'
now=datetime.now(timezone.utc).isoformat()
state=json.loads((folder/'RETOMAR_CODEX_336.json').read_text(encoding='utf-8'))
state.update(fecha_utc=now,anterior='seguimiento/RETOMAR_CODEX_336.json',
 estado_hito='Generador de borradores337 implementado y probado focalmente; flujo338 sintético integrado correcto.331 inmutable.')
state['desarrollo_geometria337']={
 'carpeta':'tmp/desarrollo_geometria_337',
 'base':'tmp/validacion_ocr_335/Fuentes_OCR_335.zip (335 validado, no publicado)',
 'archivos':{n:hashlib.sha256((root/'tmp/desarrollo_geometria_337'/n).read_bytes()).hexdigest() for n in
             ['draft2model/propuesta_trazos.py','tests/test_propuesta_trazos.py','docs/PROPUESTA_TRAZOS.md']},
 'pruebas':'tmp/propuesta_337_tests.log:13correctas; no suite completa del árbol337.',
 'flujo':'seguimiento/FLUJO_PROPUESTA_338.json; última ejecución usa tmp/g338c (g338falló por procedencia y g338b fue ensayo anterior, conservarlos).',
 'alcance':'Cotas revisadas+anclajes de dimensión+trazos PDF→calibración afín→propuesta ortogonal de una planta→plantilla pendiente→conversión versionada/importación existentes.',
 'evidencia':'4nodos y4muros, ninguna coordenada individual de nodo declarada, todo SINTÉTICO, ninguna aprobación real, plantilla null bloqueada y alteración de fuente detectada.',
 'faltantes':'Piloto real no probado con esta propuesta; no UI nueva de anclajes; faltan columnas/vigas/superficies/vanos/oblicuos/múltiples plantas/raster y validación integrada.',
 'nota_niveles':'Alturas externas configuradas con unidad; no se infieren de cotas horizontales. Justificación independiente obligada en revisión.',
 'no_publicado':True,'no_modifica331':True}
state['cuota']={'restante_5h_observado':4,'restante_semanal_observado':22,
                'reset_5h_lima':datetime.fromtimestamp(1792879790,timezone(timedelta(hours=-5))).isoformat(),
                'reset_manual':'Disponible; no usado ni autorizado automáticamente.',
                'politica':'Con≤5%no iniciar tareas largas; con≤1%conservar estado y terminar; no prometer trabajo durante suspensión.'}
state['procesos_vivos_criticos']=[]
state['siguiente']=[
 'Primero consultar cuota y este checkpoint.331FINAL y anexo334 son la entrega presentada; no modificarlos.',
 '93306/global335 terminó0:1515Python+36interfaz,620fuentes estables, snapshot conservado. No repetirlo.',
 'En337, ejecutar regresión focal de propuesta_trazos y consumidores existentes (conversion_geometria,gestion_geometria,validacion_geometria,revision_conversion), usando TEMP/TMP en carpeta del proyecto y PYTHONPATH de tests cuando proceda. No interpretar13focales como suite completa337.',
 'El flujo338 ya terminó0 con src337 actual. Se ensayó bloqueo de plantilla null, declaración SINTÉTICA, conversión gestionada, importación borrador y alteración/restauración exacta de bytes de fixture. No sustituirlo por aprobación humana real.',
 'Siguiente mejora sustancial: proponer anclajes de escala desde OCR/vector con unidad explícita y contrastar geometría contra planos antes del solver; completar tipologías/registro de plantas sin hardcodear el piloto. No limitarse a añadir avisos.',
 'Antes de distribuir337: integración y revisión visual, trazabilidad de propuestas, pruebas de consumidores, revisión de documentación histórica y validación de huella exacta. No publicar otra FINAL antes de garantizarla.',
 'Respetar veto a proyectos2/3, comparación manual aplazada, sin nuevas APIs/credenciales, Claude/subagentes ni ETABS. Objetivo global activo, no completo.'
]
for name,value in [('RETOMAR_CODEX_338.json',state),('RETOMAR_ACTUAL.json',
 {'checkpoint':'seguimiento/RETOMAR_CODEX_338.json','fecha_utc':now,'goal_completo':False})]:
 (folder/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Checkpoint338 guardado. No hay procesos críticos pendientes;331 intacto.')
