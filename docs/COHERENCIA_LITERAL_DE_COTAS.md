# Comprobación local de cotas y unidades

El validador de extracción señala discrepancias entre una cota propuesta y el
`texto_fuente` que declara el lector. No hace llamadas a modelos ni lee claves.
Los avisos aparecen en `validacion.advertencias` de la comprobación de extracción
y en la salida del validador. Cada aviso identifica la ruta del candidato.
La lista de lecturas muestra estos avisos junto al candidato correspondiente,
con el prefijo «Revisar evidencia». Mostrar un aviso no guarda ni envía datos.

- `valor_sin_correspondencia_literal`: el valor propuesto no coincide con los
  números reconocibles en ese texto. Por ejemplo, leer `260 cm` y proponer
  `2.6 m` mezcla lectura y conversión; debe revisarse conservando el original.
- `unidad_sin_respaldo_literal`: se propuso una unidad de longitud que no aparece
  en el texto declarado. Puede existir en un encabezado separado: debe comprobarse
  esa evidencia, sin atribuir al aviso una prueba de error del plano.
- `unidad_sin_texto_fuente`: una lectura automática heredada propone una unidad
  definida sin aportar texto literal. Se conserva, pero se señala para revisión.

Los avisos no cambian números, unidades, regiones, estados de revisión ni hashes
de documentos guardados. Tampoco rechazan por sí solos una lectura histórica.
Una lectura pendiente continúa pendiente; la revisión técnica sigue siendo
necesaria antes de configurar el modelo. No se deduce una longitud métrica a
partir de coordenadas normalizadas de imagen.

Se comparan decimales con punto o coma y signo. No se interpretan fracciones,
notación científica ni posibles separadores de miles. Las unidades de superficie,
volumen o velocidad no respaldan una unidad de longitud. No se clasifican ejes,
elementos, cargas ni propiedades mediante esta comprobación.

Este control verifica coherencia entre declaraciones, no su veracidad visual.
Una respuesta puede declarar un texto correcto y situar su región en blanco:
la revisión de evidencia o un reconocimiento independiente sigue siendo necesaria.
No acredita automatización universal ni conformidad normativa.

La distribución académica congelada `AECODE_PRESENTACION_328_FINAL.zip` conserva
su contenido. Este cambio posterior se prueba por separado antes de publicar
una nueva distribución; no se presenta como incluido en aquel ZIP.
