# Importación tabular de superficies v0.2

El ingreso CSV/XLSX existente admite geometría `0.1.0` y `0.2.0`. La versión se declara en `metadatos.json` mediante `version_contrato`; no se infiere del número de archivos, de sus nombres ni de las coordenadas. La conversión no aprueba geometría ni ingeniería ni habilita ETABS.

## Formato

Los metadatos contienen exactamente los campos raíz del contrato geométrico excepto sus colecciones. Deben declarar unidad `m`, `cm` o `mm` y `revision={"estado":"borrador","aprobacion":null}`. Se conservan las coordenadas/unidad declaradas; el validador produce por separado la normalización física en metros.

- `0.1.0`: exactamente `niveles`, `nodos`, `muros`, como antes.
- `0.2.0`: exactamente `niveles`, `nodos`, `muros`, `vertices`, `superficies`. Las colecciones históricas pueden tener únicamente cabecera, sin inventar pisos/nodos/muros.

En CSV son archivos UTF-8 llamados `<coleccion>.csv`, delimitados por coma con las comillas CSV habituales. Se admite BOM. En XLSX son los nombres exactos de las hojas visibles de un único libro. No se admite una hoja extra aunque esté vacía. La cabecera de cada tabla mantiene los campos obligatorios/opcionales del contrato, sin nombres desconocidos ni columnas duplicadas. Las dos colecciones nuevas no tienen columnas opcionales:

| Archivo/hoja | Cabecera exacta, orden recomendado |
| --- | --- |
| vertices | `id,x,y,z,procedencia` |
| superficies | `id,vertices,papel_geometrico,procedencia` |

El orden de columnas puede variar, pero los nombres son exactos. XYZ son números finitos explícitos; `procedencia` es un objeto JSON estricto en cada fila nueva. `superficies.vertices` es una lista JSON de IDs en orden perimetral. No se repite el primer ID al final. Ejemplo CSV:

```csv
id,x,y,z,procedencia
A,0,0,2,"{""tipo"":""sintetico"",""descripcion"":""Ejemplo""}"
B,4,0,2,"{""tipo"":""sintetico"",""descripcion"":""Ejemplo""}"
C,0,3,2,"{""tipo"":""sintetico"",""descripcion"":""Ejemplo""}"
```

```csv
id,vertices,papel_geometrico,procedencia
S,"[""A"",""B"",""C""]",contorno declarado,"{""tipo"":""sintetico"",""descripcion"":""Ejemplo""}"
```

En XLSX esas celdas contienen literalmente `{"tipo":"sintetico","descripcion":"Ejemplo"}` y `["A","B","C"]`, sin escapes CSV. No son expresiones Python ni fórmulas. El lector rechaza claves JSON duplicadas, NaN/Infinity y sintaxis no JSON. El validador geométrico comprueba referencias, IDs, procedencias, planitud y contornos simples; no los repara ni reordena. Una superficie no declara materiales, espesores, cargas, aberturas ni propiedades estructurales.

## Límites y controles

CSV: máximo 4 MiB por tabla y 10000 líneas físicas consumidas, incluyendo cabecera; las celdas cuyo texto comienza por `=` se rechazan como fórmulas. Nunca se evalúa el contenido. XLSX conserva las guardas del lector: 16 MiB en el servicio web, 500 miembros ZIP/32 MiB descomprimidos, 8 MiB por XML, 100000 celdas por hoja, 128 columnas y 10000 filas; sin fórmulas, macros, cifrado, vínculos externos, hojas ocultas, combinaciones ni formatos de fecha. No requiere Excel ni una instalación adicional.

La API pública conserva `/api/tabular/crear`, `/api/tabular/version`, `/api/tabular/historial` y `/api/tabular/importar`, con sus cuerpos existentes. La consulta añade `version_contrato`; el resumen v0.2 incluye `vertices` y `superficies`. El manifiesto de almacenamiento tabular conserva su versión histórica `0.1.0`: su formato no cambia; la versión geométrica explícita reside en los metadatos originales, protegidos por SHA256.

Crear una versión conserva bytes originales, geometría propuesta y hashes. Consultarla reconvierte las fuentes y compara la geometría, además de verificar el expediente y hashes. Importar al historial geométrico es una acción separada que exige versión, huella tabular y `confirmacion_explicita=true`; produce un borrador. El recibo permite reproducir la misma importación sin duplicarla y detecta interrupciones. No se heredan aprobaciones.

## Uso Python/CLI

`convertir_tablas(metadatos, tablas)` conserva la firma; el mapa de tablas debe tener las tres o cinco claves de la versión declarada. `leer_tablas_xlsx(entrada, colecciones=(...))` admite únicamente las tres claves históricas o las cinco v0.2, en ese orden; su valor por defecto conserva las tres hojas estrictas.

```powershell
.venv/Scripts/python.exe -m draft2model.importacion_tabular --metadatos meta.json --niveles niveles.csv --nodos nodos.csv --muros muros.csv --vertices vertices.csv --superficies superficies.csv --salida nueva.json
.venv/Scripts/python.exe -m draft2model.importacion_tabular --metadatos meta.json --xlsx tablas.xlsx --salida nueva.json
```

La salida debe ser nueva: no se sobrescribe. En v0.1 no se aceptan los dos argumentos nuevos. No se mezclan CSV y XLSX.

Pruebas focales reproducibles: `tests.test_tabular_superficies` (7 casos sintéticos) junto con la regresión `tests.test_importacion_tabular`, `tests.test_revision_tabular`, `tests.test_lectura_xlsx`, `tests.test_revision_tabular_http`: 36 pruebas correctas. El cliente conserva sus cinco comprobaciones existentes; dos adicionales ejecutadas en `tmp/tabular_superficies_frontend.cjs` verifican carga de cinco CSV y rechazo de mezcla de versión/cantidad antes de leer sus bytes. Logs `tmp/tabular_superficies_final.log` y `tmp/tabular_superficies_frontend02.log`. Esto verifica el flujo local y fixtures, no una extracción real ni ejecución estructural.
