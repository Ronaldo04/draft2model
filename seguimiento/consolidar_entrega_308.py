"""Índice y auditoría explícita; no declara aprobado el objetivo global."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

root=Path(__file__).resolve().parents[1]
out=root/'entregas/AECODE_ENTREGA_308'
rows=[
 ('P01','Instalación y conexión Python–ETABS','software y cálculo nativo observados',
  'Instalación offline303, suite306, arranque308 con datos vacíos; EDB analizado y leído del piloto conservado. No nueva ejecución nativa308 ni otro equipo.'),
 ('P02','Ingreso y calidad de imágenes','software probado; originales preservados',
  'Ingreso/validadores y revisión documental cubiertos por suite; seis originales del piloto íntegros. Calidad insuficiente se informa; esto no acredita precisión de visión.'),
 ('P03','Perspectiva, escala y recortes','parcial en el piloto',
  'Transformaciones y coordenadas probadas; calibración y datos confirmados del caso. No existe una referencia humana completa para contrastar toda la geometría de los planos.'),
 ('P04','Benchmark visual','pendiente de referencia humana',
  'Hay respuestas reales y contabilidad de errores/cuarentena. El anotador308 está vacío; el usuario aceptó completar la referencia, pero todavía no entregó el JSON. No hay precisión ni cobertura global acreditadas.'),
 ('P05','Contratos y unidades','software verificado',
  '1424 pruebas Python y36 de interfaz en306, sin omisiones; código/pruebas/dependencias idénticos en308. No equivale a aprobación profesional de los valores de entrada.'),
 ('P06','Revisión humana e invalidación','infraestructura verificada; revisión declarada',
  'Versiones, hashes, ediciones, aprobación declarada e invalidaciones probadas; confirmaciones puntuales del usuario preservadas. No autentica una revisión integral de ingeniería.'),
 ('P07','Sitio','software probado; aplicación real limitada',
  'Cruce, límites y ausencia de cobertura tienen pruebas; la ubicación y fuentes son referenciales. El escenario de suelo no sustituye EMS ni demuestra cartografía geotécnica correcta del edificio.'),
 ('P08','Modelo y controles','nativo con observaciones',
  'Modelo construido, relectura y cargas/masa contrastadas. La masa oficial conserva no_coherente (aprox.0,12745% frente a0,1%); extremos efectivos explican la mayor parte, sin reconciliación independiente completa.'),
 ('P09','Cálculo y referencia manual','aplazado por el usuario',
  'No se utilizó el modelo manual ni se pide para desbloquear infraestructura. Su comparación no es condición del cierre actual; no se declara realizada.'),
 ('P10','Motor de reglas','verificado para reglas y escenario revisados',
  '18 comparaciones reales contrastadas:8 satisfactorias y10 no satisfactorias. Se conserva el resultado; no certifica cumplimiento normativo integral.'),
 ('P11','Recuperación y citas','software probado y fuentes conservadas',
  'Recuperación/abstención y separación de fuentes probadas; complemento con20fuentes públicas normativas. Sin API para explicar resultados; no se infiere cobertura de todo el RNE.'),
 ('P12','Informe','contenido contrastado; compatibilidad PDF pendiente',
  'Informe técnico09d3: JSON/HTML/PDF/panel revisados y18evaluaciones conservadas. Apertura306 observada. PDF QA descargado en Chrome303 por el usuario:117212bytes y SHA coincidente. Persisten diferencias de renderizado en algunas páginas del informe técnico; HTML alternativo y encargo309 preparado.'),
 ('P13','Fallos y recuperación','software probado y fallos reales conservados',
  'Pruebas de exclusión, recuperación, huellas e invalidación; se preserva el intento API truncado y no se reenvía automáticamente. No se acredita cada fallo posible de cualquier estación ETABS.'),
 ('P14','Flujo completo','piloto supervisado y distribución reproducible; aceptación global abierta',
  'Existe cadena de planos/revisión/modelo/análisis/13indicadores/informe y paquete verificado. No es una ejecución completa de todas las pantallas en un equipo nuevo ni demuestra automatización de cualquier construcción. P04 y la salvedadP12 siguen abiertos.')
]
audit={'fecha_utc':datetime.now(timezone.utc).isoformat(),
       'fuente_requisitos':'SismoVivienda_AI_Desarrollo_Tecnico.pdf, página12; decisiones posteriores del usuario conservadas',
       'fuente_requisitos_sha256':hashlib.sha256((root/'SismoVivienda_AI_Desarrollo_Tecnico.pdf').read_bytes()).hexdigest(),
       'criterios':[dict(zip(('id','criterio','estado','evidencia_y_limite'),r)) for r in rows],
       'fuentes_evidencia':['seguimiento/VALIDACION_DISTRIBUCION_306.json',
         'seguimiento/REVISION_DOCUMENTACION_ENTREGA_308.json','seguimiento/QA_DESCARGA_Y_306_307.json',
         'seguimiento/REVISION_INFORME_302.json','seguimiento/REVISION_REGLAS_REALES_286.json',
         'seguimiento/REVISION_ANALISIS_267.json','seguimiento/REVISION_METRICAS_265.json',
         'seguimiento/REVISION_REMOTO_307.json','seguimiento/QA_ANOTADOR_308.json'],
       'repo':'Repositorio privado e issue1 consultables. No se publicó308 ni se auditó aceptación de otro colaborador.',
       'goal_completo':False,'no_calcular_porcentaje':'No convertir54coincidencias automáticas del catálogo histórico en porcentaje de terminación del proyecto.'}
assert all((root/p).is_file() for p in audit['fuentes_evidencia'])
text=json.dumps(audit,ensure_ascii=False,indent=2)
(root/'seguimiento/AUDITORIA_P01_P14_308.json').write_text(text,encoding='utf-8')
(out/'AUDITORIA_P01_P14.json').write_text(text,encoding='utf-8')
lines=['# Auditoría P01–P14 de la entrega','',
 'Fuente: desarrollo técnico, página12, y decisiones posteriores del usuario. La comparación manual está aplazada. Esta auditoría no declara aprobado el objetivo global.','',
 '| Prueba | Estado observado | Evidencia y límite |','|---|---|---|']
for ident,title,status,limit in rows:
    lines.append(f'| {ident} · {title} | {status} | {limit} |')
lines += ['', 'No existe un porcentaje único de terminación acreditado. Las pruebas de software, la corrección física del piloto y la generalización son afirmaciones distintas. No se presentan los candidatos de IA como referencia humana ni se llama a las observaciones estructurales errores ocultos del programa.']
(out/'AUDITORIA_P01_P14.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('Auditoría de14pruebas preservada; aceptación global abierta.')
