# CLI de extracciones: importar, validar, corregir y exportar

Integración local del [registro de extracción preliminar](EXTRACCION_PRELIMINAR.md) con el expediente privado. Recibe candidatos producidos fuera de esta herramienta (lectura manual o, más adelante, visión multimodal), comprueba su evidencia y registra la revisión de cada candidato en versiones nuevas.

**No** ejecuta OCR, visión ni llamadas a proveedores, no genera geometría, no abre ETABS y no aprueba datos de ingeniería. Revisar un candidato solo confirma o corrige lo leído.

Implementación: [`draft2model/gestion_extraccion.py`](../draft2model/gestion_extraccion.py) y los subcomandos de [`draft2model/__main__.py`](../draft2model/__main__.py). Pruebas: [`tests/test_gestion_extraccion.py`](../tests/test_gestion_extraccion.py) y [`tests/test_cli_extraccion.py`](../tests/test_cli_extraccion.py).

## Comandos

Desde la carpeta del proyecto, en PowerShell. La raíz habitual es `data/private/`, excluida del versionado.

```powershell
.\.venv\Scripts\python.exe -m draft2model importar-extraccion --caso CASO --entrada extraccion.json
.\.venv\Scripts\python.exe -m draft2model validar-extraccion --caso CASO --extraccion VERSION_ID
.\.venv\Scripts\python.exe -m draft2model corregir-extraccion --caso CASO --extraccion VERSION_ID --candidato C001 --estado revisado --valor-json 2.65 --unidad m --motivo "Se lee 2.65 en el recorte" --fecha 2026-10-15 --revisor "Nombre declarado"
.\.venv\Scripts\python.exe -m draft2model exportar-extraccion --caso CASO --extraccion VERSION_ID
```

| Comando | Qué hace |
| --- | --- |
| `importar-extraccion` | Lee el JSON con el lector estricto, comprueba la evidencia y guarda una versión nueva solo si todo es consistente. Exige `procedencia.tipo = expediente` y que el `caso` coincida. No reescribe valores, unidades, alcance ni referencias. |
| `validar-extraccion` | Vuelve a comprobar una versión guardada con la evidencia vigente. No escribe nada. |
| `corregir-extraccion` | Aplica `corregir()` sobre una versión comprobada y guarda el resultado como versión hija. La versión padre no cambia. |
| `exportar-extraccion` | Aplica `exportar_revisados()` con el inventario comprobado y guarda una exportación nueva, sin sobrescribir las anteriores. |

`--estado` admite `pendiente`, `revisado` o `rechazado`. Para `revisado` se indican `--valor-json` y `--unidad`, aunque repitan lo propuesto. Para `pendiente` y `rechazado` se omiten.

`--valor-json` acepta un número JSON (`2.65`) o una cadena JSON (`'"EJE A"'` en PowerShell). Se analiza con `json.loads`, sin `eval`. Una cadena no se convierte en número: `'"2.65"'` para una cota se rechaza. Se rechazan `true`, `NaN`, listas y texto que no sea JSON.

`--revisor` es una declaración: no se autentica a quien revisa.

## Comprobación de la evidencia

Antes de importar, validar, corregir o exportar se comprueba lo siguiente. No se generan vistas ni se llama a la revisión documental.

1. **Estructura:** el registro supera `validar_extraccion`.
2. **Expediente:** `expediente.json` es legible y de este caso, y cada entrada de `archivos` tiene `id`, `archivo` y `sha256` de tipo texto, sin identificadores repetidos.
3. **Originales citados:** cada `archivo_id` existe en el expediente, su ruta queda dentro del caso tras resolver enlaces, y el SHA256 **calculado** del archivo coincide con el registrado.
4. **Recortes citados:** `recortes/<id>/recorte.json` se valida antes de usarse:
   - `id` y `caso` coinciden;
   - `sistema_coordenadas` es exactamente `pagina_visible_normalizada`. Si es otro, falta o tiene otro tipo, se rechaza: las coordenadas no se convierten y los metadatos no se reescriben;
   - corresponde al expediente vigente (`expediente_sha256`) y al original (`archivo_id` y `origen_sha256`);
   - `pagina` es un entero positivo; `bbox_normalizada` es finita, está entre 0 y 1 y tiene área positiva; `imagen_sha256` es un SHA256 válido e `imagen` está indicada;
   - su imagen queda dentro de la carpeta del recorte y su SHA256 calculado coincide con `imagen_sha256`.
5. **Revisiones documentales** (`revision_documental/*/revision.json`):
   - deben ser legibles, del mismo caso y generadas con el expediente vigente;
   - `documentos` debe ser una lista de objetos cuyo `id` y `archivo` coincidan con el expediente;
   - si están presentes, `error` es texto o `null` y `paginas_declaradas` es un entero positivo.

   Una revisión inválida **rechaza la operación** e indica la carpeta de la revisión y la causa; no se ignora ni se degrada a advertencia. Solo las revisiones válidas aportan el número de páginas.
6. **Inventario:** con lo anterior se construye `inventario_desde()` y se vuelve a validar. Así se detectan archivo, página, recorte, hash o alcance incompatibles.
7. **Versiones guardadas:**
   - la huella de `extraccion.json` coincide con `version.json`;
   - la cadena de versiones padre es coherente;
   - el expediente no cambió desde el registro;
   - `operacion` es `importacion` (sin padre) o `correccion` (con padre).
8. **Fuente importada:** se comprueba en la versión validada y en cada versión de importación alcanzada al recorrer los padres. Debe existir `fuente_importada.json`, sin ser un enlace. El SHA256 se calcula sobre sus **bytes exactos** y debe coincidir con `fuente.sha256`. Además, su JSON debe corresponder a `extraccion.json`; se compara por huella canónica, porque `extraccion.json` puede tener otro formato. Las versiones de corrección no guardan fuente y no se les exige.

Si falta algo, está alterado, malformado o es contradictorio, la operación falla con la lista de problemas y **no se guarda nada**. Si ninguna revisión documental registra páginas, la referencia queda `parcial` y se informa como advertencia: no se presenta como `comprobada`.

### Destinos de escritura

Antes de crear temporales o escribir, se comprueba que `extracciones/` y `extracciones_exportadas/` sean carpetas reales del caso: su ruta resuelta debe coincidir exactamente con `<caso>/<carpeta>`. Esta comprobación se aplica a la importación, la corrección y la exportación.

Si alguna es un enlace simbólico o una junction de Windows, se rechaza con código 1 sin crear directorios ni archivos en el destino. Esto vale tanto si el enlace apunta fuera del caso como si apunta a otra carpeta interna. La misma comprobación protege la lectura de versiones.

## Estructura guardada

```
data/private/<caso>/
  extracciones/<version_id>/          # una carpeta por versión, 32 hexadecimales
    extraccion.json                   # registro de extracción (JSON estricto)
    reporte.json                      # comprobación: problemas, archivos verificados, validación
    version.json                      # metadatos y vínculo con la versión padre
    fuente_importada.json             # solo en importaciones: bytes exactos recibidos
  extracciones_exportadas/<export_id>/
    exportacion.json                  # draft2model.extraccion_revisada + bloque "origen"
```

`version.json` registra:

- `id`, `caso` y `operacion` (`importacion` o `correccion`);
- `creado_utc`, `huella_extraccion` (SHA256 canónico del registro) y `expediente_sha256`;
- `archivos_verificados`: tipo, id y SHA256 calculado de cada original e imagen;
- `padre: {id, huella_extraccion}`, o `null` en una importación;
- `fuente: {nombre, sha256, archivo}` en una importación;
- `correccion: {candidato, estado, revisor_declarado, identidad_revisor: "declarada_no_verificada"}` en una corrección;
- `revision_tecnica: "pendiente"` y `aprobacion_ingenieria: null`.

Las versiones forman un árbol: cada corrección crea una hija del padre indicado. Dos correcciones del mismo padre crean ramas, que no se fusionan. El historial lógico de cada candidato está en `revision.historial` dentro de `extraccion.json`.

La exportación añade `origen: {extraccion_id, huella_extraccion, expediente_sha256, archivos_verificados, exportado_utc}`. Conserva `alcance`, `procedencia`, `excluidos` y `aprobacion_ingenieria: null`, y no contiene nodos, muros ni niveles.

**Escritura atómica:** cada versión o exportación se escribe en un temporal `.tmp-*` dentro de la misma carpeta y se publica con un único `rename` al terminar. Ante un fallo, el temporal se elimina y no queda una carpeta incompleta visible.

Las huellas detectan cambios accidentales o parciales. **No protegen contra una edición deliberada** de los archivos locales que también rehaga las huellas.

## Códigos de retorno

| Código | Significado |
| --- | --- |
| 0 | Operación completada. En `validar-extraccion`: la versión supera todas las comprobaciones. |
| 1 | Solicitud que no puede completarse: identificador de caso o versión inválido, ruta fuera de la raíz, carpeta de versiones o exportaciones enlazada (symlink o junction), caso o versión inexistente, JSON de entrada ilegible o con claves repetidas, `--valor-json` inválido, error de E/S. |
| 2 | Registro o evidencia rechazados: evidencia ausente, alterada, malformada o contradictoria; revisión o recorte inválidos; sistema de coordenadas incompatible; fuente importada ausente o alterada; versión guardada ilegible; registro inconsistente o corrección inválida. En `validar-extraccion`: la versión ya no supera la comprobación. No se guarda nada. |

Además, `argparse` termina con código 2 ante opciones obligatorias ausentes o desconocidas, y muestra `usage:`.

## Ejemplo sintético reproducible

Usar un caso nuevo y sintético, nunca el piloto real. Crea archivos locales en `data/private/sintetico-demo/`, que pueden borrarse después.

```powershell
.\.venv\Scripts\python.exe -c "import pymupdf; d=pymupdf.open(); d.new_page(width=400,height=300).draw_rect((50,50,350,250)); d.save('tmp/plano_sintetico.pdf')"
.\.venv\Scripts\python.exe -m draft2model ingresar --caso sintetico-demo --archivos tmp\plano_sintetico.pdf --uso-autorizado --provisional-fuera-alcance
.\.venv\Scripts\python.exe -m draft2model revisar --caso sintetico-demo --max-lado 256
.\.venv\Scripts\python.exe -m draft2model recortar --caso sintetico-demo --archivo L0001 --pagina 1 --bbox 0 0 0.5 0.5 --dpi 72
```

Después, preparar `tmp/extraccion.json` con:

- `procedencia.tipo = "expediente"`;
- el bloque `alcance` copiado de `expediente.json`;
- en cada evidencia: `archivo_id` `L0001`, `pagina` 1, el `sha256` del expediente como `original_sha256` y, si se cita el recorte, su `id` e `imagen_sha256` tomados de `recorte.json`.

La estructura completa está en [EXTRACCION_PRELIMINAR.md](EXTRACCION_PRELIMINAR.md) y en la función `extraccion()` de `tests/test_gestion_extraccion.py`. Luego:

```powershell
.\.venv\Scripts\python.exe -m draft2model importar-extraccion --caso sintetico-demo --entrada tmp\extraccion.json
.\.venv\Scripts\python.exe -m draft2model validar-extraccion --caso sintetico-demo --extraccion <id impreso>
.\.venv\Scripts\python.exe -m draft2model corregir-extraccion --caso sintetico-demo --extraccion <id> --candidato C001 --estado revisado --valor-json 2.65 --unidad m --motivo "Se lee 2.65" --fecha 2026-10-15 --revisor "Revisor sintético"
.\.venv\Scripts\python.exe -m draft2model exportar-extraccion --caso sintetico-demo --extraccion <id de la versión nueva>
```

Este flujo se ejecutó el 15 de octubre de 2026 en una copia aislada del paquete: los cuatro comandos devolvieron 0, se comprobaron los SHA256 del original y de la imagen, y la exportación incluyó solo el candidato revisado.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Cubren, con PDF sintéticos en carpetas temporales:

- flujo importar, corregir y exportar, por funciones y por CLI;
- estados pendiente y rechazado, y su exclusión de la exportación;
- conservación de `fuera_mvp_declarado` y de la procedencia;
- inmutabilidad de versiones anteriores, expediente, originales e imágenes;
- valores y unidades desconocidos;
- JSON con claves repetidas o `NaN`, entradas sintéticas o de otro caso;
- identificadores y rutas que escapan, incluido un enlace simbólico de imagen que sale del caso;
- originales e imágenes alterados o ausentes, expediente modificado y versión guardada editada;
- fallo de escritura sin versión parcial;
- códigos de retorno y ayuda de los comandos;
- los comandos `ingresar`, `revisar` y `recortar` siguen funcionando.

Regresiones de la auditoría del 15 de octubre de 2026 (`RegresionAuditoriaTests` y tres pruebas de CLI):

| Defecto | Pruebas |
| --- | --- |
| 1. Escritura fuera del caso mediante enlaces | `extracciones/` enlazada fuera del caso (importación y corrección), enlazada a otra carpeta interna, y `extracciones_exportadas/` enlazada fuera (exportación). Se comprueba que el destino externo queda vacío. CLI: código 1. |
| 2. Sistema de coordenadas incompatible | Importación con `pixeles_sin_rotacion`, ausente, `null`, número o lista; versión guardada cuyo recorte se vuelve incompatible bloquea validación, corrección y exportación. CLI: código 2. |
| 3. Fuente importada alterada | Fuente vacía, reformateada o ausente; hash rehecho con contenido distinto; detección desde una versión hija. CLI: código 2. |
| 4. Revisión malformada | `documentos` con `[null]`, texto, número u objeto; `id`, `archivo`, `paginas_declaradas` o `error` con tipos incompatibles; revisión ilegible; recortes con campos malformados. CLI: código 2 sin traceback. |

Las pruebas de enlaces crean junctions de Windows, que no requieren privilegios. Si no es posible, recurren a enlaces simbólicos de carpeta, y solo se omiten si el sistema no permite ninguno de los dos. En la ejecución del 15 de octubre de 2026 no se omitió ninguna.

## Limitaciones

- Las evidencias sobre imágenes raster dependen de que los recortes las admitan; hoy los recortes solo cubren PDF.
- Las referencias sin número de páginas inventariado quedan `parcial`: conviene ejecutar `revisar` antes de importar.
- No hay bloqueo entre procesos: dos correcciones simultáneas del mismo padre crean ramas independientes.
- No existe una orden para listar versiones ni para borrar ramas; se consultan las carpetas.
- La comprobación de enlaces se hace inmediatamente antes de escribir. Un proceso local que sustituya la carpeta por un enlace entre esa comprobación y el `rename` final no se detecta: no hay bloqueo de sistema de archivos.
- Las revisiones documentales se validan en los campos que consume esta integración. El resto de su contenido, como vistas previas y advertencias, no se audita aquí.
- La identidad del revisor es declarada. La aprobación técnica y la transformación a geometría siguen pendientes.
