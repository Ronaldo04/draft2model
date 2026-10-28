# Contexto técnico versionado (corpus, sitio y reglas)

- **Ruta:** `D:/RONALDO CUCHILLA/1. RONALDO CUCHILLA/2. INGENIERÍA CIVIL DOCS AND PROJECTS/AECODE CURSOS/AECODE AI TALENT/PROYECTO FINAL`.
- **Servicio:** `draft2model/revision_contexto.py`, clase `ServicioContexto(app)`. Codex conecta la parte HTTP, la UI y la integración con el informe.
- **Archivos sin tocar:** `fuentes.py`, `sitio.py`, `evaluacion_estructural.py`, proveedor, respuestas y HTTP/UI.

## Qué reutiliza

| Núcleo | Uso |
|---|---|
| `fuentes.cargar_corpus` y `recuperar` | Validación completa del corpus (rutas relativas, SHA-256 de documentos y aprobación declarada con huella vigente) y ranking léxico con abstención. |
| `sitio.consultar_sitio` | Validación de la capa y consulta de cobertura. El núcleo solo valida al consultar, así que al registrar se le pasa el punto (0, 0) para ejercitar su validador; ese resultado se descarta. |
| `evaluacion_estructural.validar_reglas` y `evaluar_resultados` | Validación de las reglas, exigencia de aprobación vigente, huellas exactas y evaluación debajo/en/sobre. |
| `app.resultados.consultar_resultado` | Resultado normalizado vigente, con su verificación completa. |

**No se añaden umbrales, normativa, cartografía, aprobaciones ni conversiones.**
- Solo se registran contratos que **ya traen** su revisión declarada y pasan el validador nativo.
- Un borrador de reglas se rechaza.
- La proyección marca `identidad_revisor: declarada_no_verificada`, `verificacion_profesional: false`, `aprueba_resultados: false` y `aprueba_informe: false`.

## Almacenamiento

Todo queda en `<caso>/contexto/`:
- `corpus/<uuid>/`: `corpus.json`, los documentos con su nombre simple y `version.json`.
- `sitio/<uuid>/`: `capa.json` y `version.json`.
- `reglas/<uuid>/`: `reglas.json` y `version.json`.
- `derivados/<uuid>/`: `salida.json` y `version.json`, con la solicitud, las fuentes `{id, huella}`, el resultado `{id, huella}` y `sha256_salida`.

**Reglas de escritura:**
- Cada registro o consulta crea una carpeta nueva mediante staging en `.ctx-*` y `rename` atómico, sin sobrescribir.
- Los bytes del contrato se guardan tal como se recibieron.
- `version.json` contiene el SHA-256 de cada archivo, la huella nativa y `datos_sinteticos`.
- Todas las operaciones usan `app.lock`. Se rechazan enlaces y junctions en la raíz, el caso y las carpetas de contexto y de versión.
- Ninguna proyección contiene rutas privadas.

## Contratos (cuerpos exactos)

| Método | Cuerpo |
|---|---|
| `registrar_corpus` | `{caso, expediente_sha256, manifiesto_json, archivos:[{nombre, contenido_base64}]}` |
| `registrar_sitio` | `{caso, expediente_sha256, capa_json}` |
| `registrar_reglas` | `{caso, expediente_sha256, reglas_json}` |
| `recuperar` | `{caso, expediente_sha256, corpus, consulta, limite (1–20), resultado (uuid o null)}` |
| `consultar_sitio` | `{caso, expediente_sha256, sitio, longitud, latitud, resultado (uuid o null)}` |
| `evaluar` | `{caso, expediente_sha256, resultado, reglas, huella_resultados, huella_reglas}` |
| Lectura | `consultar(caso, tipo, version, expediente_sha256=)`, `consultar_derivado(...)`, `listar(caso, expediente_sha256=)` |

**Límites:**
- JSON de contrato: 1 MiB como máximo. Se parsea en modo estricto: sin claves repetidas ni NaN.
- Corpus: de 1 a 20 documentos, 4 MiB cada uno decodificado y 16 MiB en total.
  - El base64 se valida de forma estricta.
  - El nombre debe ser simple (`[A-Za-z0-9][A-Za-z0-9._-]{0,99}`), sin `..` y distinto de los nombres reservados.
  - Los nombres adjuntos deben coincidir exactamente con los `archivo` declarados en el manifiesto.
- Consulta: de 1 a 500 caracteres.
- Longitud y latitud: numéricas y finitas. El núcleo aplica además los rangos de EPSG:4326.
- Identificadores: UUID de 32 caracteres hexadecimales en minúscula. Huellas: 64 caracteres hexadecimales en minúscula.
- No se aceptan rutas absolutas, URL, comandos, claves ni transporte.
- Los errores se lanzan como `ErrorContexto` (`ValueError`) con un mensaje genérico sin rutas.

## Revalidación y derivados

- **Lectura de contexto:** comprueba el conjunto exacto de archivos, sus SHA-256, el validador nativo y que la huella y la naturaleza coincidan con `version.json`. Después vuelve a leer los bytes para detectar cambios durante la consulta.
- **Consulta derivada:** se calcula dos veces desde fuentes revalidadas, antes y después de preparar el staging. Si el resultado cambia, la consulta se rechaza.
  - Si la solicitud incluye resultado, este se verifica antes y después.
- **`consultar_derivado`:** reproduce la salida desde las fuentes actuales y exige igualdad exacta con la salida y las fuentes guardadas. Si se altera el corpus, la capa, las reglas, el resultado o la propia salida, el derivado deja de ser vigente. `listar` lo muestra con `vigente:false`.
- **Recuperación:** la abstención (`abstencion: true` y lista vacía) se conserva como un derivado válido.
- **Sitio:** nunca devuelve parámetros geotécnicos ni capacidad portante; esos campos salen como `null`, igual que en el núcleo.

## Mezcla de datos sintéticos y reales

| Combinación | Comportamiento |
|---|---|
| Reglas frente a resultado | Deben tener la misma naturaleza. Lo impone el núcleo `evaluar_resultados`. |
| Corpus o sitio sintético con resultado real | Se rechaza, igual que en `informe.py`. |
| Corpus o sitio real con resultado sintético | Se permite y queda marcado en `datos_sinteticos` de la salida, de nuevo igual que en `informe.py`. |
| Consultas sin resultado (`resultado: null`) | Se permiten. Devuelven la naturaleza declarada por el contexto. |

## Pruebas

Comando:

```bash
TEMP=$PWD/tmp TMP=$PWD/tmp python -m unittest tests.test_revision_contexto tests.test_fuentes tests.test_sitio tests.test_evaluacion_estructural
```

Resultado: 24 OK. De ellas, 8 son nuevas, y en todas están bloqueados `Popen`, `urlopen` y `socket.create_connection`.

Qué cubren:
- Recorrido completo del corpus: recuperación, abstención, listado y consulta tras reinicio.
- Documento alterado: invalida corpus y derivado, se restablece al restaurar el documento, y una salida alterada se rechaza.
- Rechazos en el registro:
  - Sin aprobación, con aprobación obsoleta, con hash erróneo o con documentos que no coinciden con el manifiesto.
  - Nombres `../`, reservados o ajenos; base64 inválido; JSON duplicado; ruta absoluta; tamaño excesivo; expediente cambiado.
  - Reglas en borrador, capa inválida y capa mayor de 1 MiB.
- Sitio dentro, en el límite y sin cobertura, sin inferencias; tipos de coordenada inválidos.
- Reglas debajo, en y sobre el límite, con huellas exactas; huellas erróneas; reglas alteradas.
- Mezcla de datos sintéticos y reales.
- Cambio durante la consulta y resultado alterado que invalida la evaluación.
- Carpeta enlazada (junction).

## Límites

- `version.json` no tiene una huella propia. Su contenido se valida semánticamente y se contrasta con los archivos y con las huellas nativas.
- Cada consulta crea un derivado nuevo: no hay clave de idempotencia.
- La capa de sitio solo admite lo que admite `sitio.py` (Polygon en EPSG:4326, sin cruzar el antimeridiano).
- **Pendiente para Codex:** las rutas HTTP, la UI y el uso del contexto al generar o aprobar el informe.
- **No ejecutado:** red, LLM, API, ETABS, Computer Use y la suite completa.
