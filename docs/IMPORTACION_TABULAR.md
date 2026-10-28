# Contingencia CSV y XLSX supervisada

El importador produce `draft2model.geometria` v0.1.0 desde tres tablas CSV UTF-8 o un libro XLSX y metadatos JSON explícitos. No interpreta planos, define parámetros de ingeniería ni registra aprobación. Es ingreso manual supervisado; no debe presentarse como extracción multimodal. XLSX se lee mediante ZIP/XML de la biblioteca estándar, sin nuevas dependencias.

Para Excel: `python -m draft2model importar-tablas --metadatos metadatos.json --xlsx tablas.xlsx --salida geometria_nueva.json`. El libro debe tener exactamente las hojas visibles niveles, nodos y muros, con los mismos nombres de columnas que CSV. No mezclar --xlsx y las opciones de CSV. Se leen texto compartido/inline y valores numéricos explícitos; fórmulas (aunque tengan valores cacheados), vínculos externos, macros, errores, fechas, porcentajes, hojas ocultas, celdas combinadas y extensiones se rechazan. Usar General, número decimal o texto; no hay recálculo ni interpretación del aspecto visual como unidad. Los metadatos siguen siendo JSON separado.

Límites del lector XLSX: 32 MiB descomprimidos totales, 8 MiB por XML, 500 entradas ZIP, 100000 celdas por hoja, 10000 filas y 128 columnas. Se rechazan duplicados, rutas externas y declaraciones DTD/entidades. No es un lector general de todas las funciones de Excel; el contenido debe ser un intercambio tabular explícito. Pruebas adicionales: `python -m unittest discover -s tests -p test_lectura_xlsx.py -v`.

## Ejemplo reproducible

Desde la raíz del proyecto, usando el entorno existente:

```powershell
.\.venv\Scripts\python.exe -m draft2model.importacion_tabular --metadatos examples/tabular_sintetico/metadatos.json --niveles examples/tabular_sintetico/niveles.csv --nodos examples/tabular_sintetico/nodos.csv --muros examples/tabular_sintetico/muros.csv --salida tmp/geometria_tabular.json
```

La carpeta de salida debe existir y el archivo debe ser nuevo. Se rechaza sobrescribir archivos, incluidas las entradas. El ejemplo conserva exactamente los datos de `examples/geometria_sintetica.json`, incluido su carácter sintético y espesor M4 desconocido. No representa una vivienda real ni habilita por sí solo modelado o análisis. Puede pasarse el JSON resultante al comando `plan-modelado` existente para generar una propuesta geométrica, que tampoco ejecuta ETABS.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_importacion_tabular.py -v
```

## Formato y restricciones

Los metadatos requieren exactamente `contrato`, `version_contrato`, `id`, `unidad_longitud`, `procedencia`, `faltantes` y `revision`. Las colecciones se proporcionan como CSV o mediante las tres hojas XLSX. Se exige unidad `m`, `cm` o `mm`; todos los números se interpretan en esa unidad y no se infiere escala ni se convierten píxeles. La salida conserva la unidad de entrada; el validador existente proporciona la normalización a metros.

La revisión debe ser exactamente `{"estado":"borrador","aprobacion":null}`. Se rechazan aprobaciones aportadas mediante tablas o metadatos. El responsable debe revisar el contrato resultante mediante el flujo de geometría antes de aprobarlo.

| Tabla | Columnas obligatorias | Columnas opcionales |
| --- | --- | --- |
| niveles | id,cota | nombre,procedencia |
| nodos | id,x,y | procedencia |
| muros | id,nodo_inicio,nodo_fin,nivel_inferior,nivel_superior,espesor | procedencia,observaciones |

Se emplean coma como separador, punto decimal y comillas dobles según CSV estándar. Cabeceras exactas y únicas; columnas extra o ausentes y filas de longitud distinta se rechazan. Se admite BOM UTF-8. Una línea vacía se omite; una fila con datos incompletos no se rellena. Los espacios exteriores de las celdas se eliminan. No se ejecutan fórmulas.

Solo `cota` y `espesor` admiten celda vacía para representar `null`. Debe existir un faltante correspondiente con colección, identificador, campo y descripción en los metadatos; no se inventa la justificación. Las coordenadas x/y vacías se rechazan. `NaN`, infinitos, desbordamiento, números inválidos, identificadores repetidos y referencias rotas se rechazan antes de guardar. Se delega toda consistencia geométrica al mismo validador utilizado para JSON.

Si se aporta la columna opcional `procedencia`, cada celda no vacía contiene un objeto JSON del contrato, codificado como campo CSV entrecomillado. La procedencia global y por elemento se conserva; no se transforma automáticamente un dato sintético en observado. Las celdas opcionales vacías se omiten. No se aceptan claves JSON duplicadas.

## API sin efectos laterales

```python
from draft2model.importacion_tabular import convertir_tablas

geometria = convertir_tablas(metadatos, {
    "niveles": texto_csv_niveles,
    "nodos": texto_csv_nodos,
    "muros": texto_csv_muros,
})
```

La función recibe objetos/textos, no lee ni escribe archivos y no modifica sus entradas. Devuelve una copia consistente del contrato o lanza `ErrorImportacionTabular`. Consistencia permite faltantes declarados: no implica aprobación, completitud estructural ni disponibilidad para modelado. El módulo CLI devuelve 0 en éxito y 1 si falla lectura, validación o escritura; una entrada inválida no crea salida.
