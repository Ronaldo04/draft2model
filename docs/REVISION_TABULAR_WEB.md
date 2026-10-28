# Contingencia tabular web (CSV/XLSX) hacia geometría borrador

- **Ruta:** `D:/RONALDO CUCHILLA/1. RONALDO CUCHILLA/2. INGENIERÍA CIVIL DOCS AND PROJECTS/AECODE CURSOS/AECODE AI TALENT/PROYECTO FINAL`.
- **Servicio:** `draft2model/revision_tabular.py`, clase `ServicioTabular(app)`. Codex conecta HTTP/UI después.
- **Archivos sin tocar:** los núcleos, el informe y HTTP/UI.

## Qué reutiliza

| Núcleo | Uso |
|---|---|
| `importacion_tabular.convertir_tablas` | Cabeceras exactas, números finitos, unidad declarada (m, cm o mm), revisión borrador y `validar_geometria`. |
| `lectura_xlsx.leer_tablas_xlsx` | Se le pasa un `BytesIO`. Aplica sus propios límites: ZIP de 500 entradas y 32 MiB, XML de 8 MiB, sin DOCTYPE ni ENTITY, sin macros, vínculos externos, hojas ocultas, fórmulas, celdas combinadas ni formatos de fecha, y exactamente las hojas niveles, nodos y muros. |
| `gestion_geometria.importar_geometria` / `consultar_version` | Traslado al historial geométrico como versión raíz en borrador, y comprobación posterior. |
| `app.expediente` / `app._original` | Huella del expediente y SHA-256 de cada original, comprobados antes y después de cada operación. |

## API (cuerpos exactos)

**`crear(body)`**

Cuerpo: `{caso, expediente_sha256, metadatos_json, formato: "csv"|"xlsx", archivos: [{nombre, contenido_base64}]}`.
- **`metadatos_json`:**
  - JSON estricto de hasta 256 KiB, con todos los campos raíz del contrato `draft2model.geometria` excepto las tres colecciones.
  - `id` debe ser **igual al caso**.
  - La revisión debe ser `{"estado":"borrador","aprobacion":null}`. Una aprobación en los metadatos se **rechaza**: nunca se eleva.
  - No se infieren unidades, campos ni faltantes.
- **CSV:** exactamente `niveles.csv`, `nodos.csv` y `muros.csv`, en UTF-8 estricto y de hasta 4 MiB cada uno.
- **XLSX:** exactamente un libro `.xlsx` de hasta 16 MiB. Se guarda como `libro.xlsx` y el nombre original se conserva en los metadatos.
- **Formato de las entradas:**
  - Nombres simples (`[A-Za-z0-9][A-Za-z0-9._-]{0,99}`), sin `..`.
  - Base64 validado de forma estricta.
  - No se aceptan campos extra, rutas, URL, comandos ni secretos.

**Lectura y traslado**

| Llamada | Qué hace |
|---|---|
| `consultar(caso, version, expediente_sha256=)` | Devuelve la proyección de una versión. |
| `listar(caso, expediente_sha256=)` | Devuelve `{versiones:[{id, vigente, formato, estado, importacion}]}`. |
| `importar({caso, expediente_sha256, version, huella_tabular, confirmacion_explicita:true})` | Traslada la versión al historial geométrico. |

Los errores se lanzan como `ErrorTabular` (`ValueError`) con mensajes genéricos, sin rutas.

## Almacenamiento

Cada versión vive en `<caso>/tabulares/<uuid>/` con estos archivos:
- `metadatos.json`: los bytes recibidos.
- Los originales: los tres CSV o `libro.xlsx`, con sus bytes exactos.
- `geometria.json`: la salida canónica.
- `version.json`: contrato `draft2model.tabular_web`, caso, `expediente_sha256`, formato, `nombre_original`, `procedencia: contingencia_tabular_supervisada`, el SHA-256 de cada archivo y la fecha de creación.

**Reglas de escritura:**
- Se publica mediante staging en `.tab-*`, reconversión dentro de la etapa y `rename` atómico. Nunca se sobrescribe.
- `huella_tabular` es el SHA-256 de `version.json`.
- Al importar solo se añaden dos archivos nuevos: `importacion_pendiente.json` (reserva) e `importacion.json` (recibo).

## Revalidación

En cada consulta se comprueba:
1. El expediente y sus originales.
2. Que no haya enlaces.
3. El conjunto exacto de archivos y sus hashes.
4. Que la versión sea del mismo caso y del mismo `expediente_sha256`.
5. **La reconversión desde los originales**, cuya salida debe coincidir byte a byte con `geometria.json`. Así se detecta una alteración coherente de la geometría aunque se rehagan su hash y `version.json`.
6. Una relectura final para detectar cambios durante la consulta.

**Proyección:** id, formato, nombre original, hashes, huella, resumen (unidad, conteos, faltantes, procedencia declarada), `estado:"borrador"`, `aprobacion:null` y estado de la importación. Además, `disponible_para_modelado`, `aprueba_geometria` y `aprueba_ingenieria` valen siempre `false`. No incluye rutas ni bytes grandes.

## Importación separada e idempotente

- **Requisitos:** versión, `huella_tabular` exacta y `confirmacion_explicita:true`. Se toma un bloqueo exclusivo en `<caso>/tabular_web.lock`.
- **Primera vez:**
  1. Se escribe la reserva `importacion_pendiente.json`.
  2. Se ejecuta `importar_geometria`.
  3. Se verifica con `consultar_version` que la versión sea correcta, idéntica a la tabla y en borrador.
  4. Se vuelve a cargar la versión tabular y se escribe el recibo.
- **Replay:** el recibo se revalida contra el historial y devuelve la misma geometría, sin duplicar.
- **Interrupción:** si existe la reserva pero no el recibo (por ejemplo, porque `importar_geometria` publicó y después hubo un corte), se rechaza con «importación interrumpida». La evidencia se conserva y no se repite automáticamente.
- Nunca se aprueba la geometría ni la ingeniería.

## Pruebas

Comando:

```bash
TEMP=$PWD/tmp TMP=$PWD/tmp python -m unittest tests.test_revision_tabular tests.test_importacion_tabular tests.test_lectura_xlsx tests.test_gestion_geometria
```

Resultado: 53 OK, de las cuales 6 son nuevas. `Popen`, `urlopen` y `socket` están bloqueados.

Qué cubren las nuevas:
- CSV y XLSX equivalentes a `examples/geometria_sintetica.json`.
- Proyección sin rutas.
- Importación: falta de confirmación, huella errónea, UUID inválido, importación correcta, replay idéntico y una sola versión geométrica en el historial.
- Importación interrumpida: queda una sola versión y se bloquea el reintento.
- 17 entradas inválidas que no publican nada:
  - unidad `ft`, unidad ausente, aprobación en los metadatos, id de otro caso;
  - columna extra, tabla faltante, ruta `../`, JSON con clave duplicada, formato mezclado, campo extra, base64 inválido;
  - un archivo que no es ZIP, una extensión incorrecta, una fórmula, una hoja oculta, un vínculo externo y un expediente cambiado.
- Fórmula con el mismo valor.
- Alteraciones rechazadas: fuente modificada, geometría alterada de forma coherente con hash rehecho, versión copiada a otro caso y original del expediente alterado (rechaza consulta e importación).

## Límites

- La prueba de enlaces no se repitió aquí: en el sandbox de Codex no se pueden crear enlaces. El servicio sí rechaza enlaces y junctions mediante `lstat`, `resolve` y el atributo de reparse point.
- **Posible fallo de sincronización:** si el proceso muere entre la reserva y la llamada a `importar_geometria`, también queda «interrumpida», aunque no haya versión geométrica. La resolución es manual: no hay endpoint de recuperación.
- **No verificado:** HTTP/UI, red, API, ETABS, Computer Use y la suite completa.
