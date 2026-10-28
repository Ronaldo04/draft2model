# Explicaciones sustentadas y contingencia determinística

- **Ruta:** `D:/RONALDO CUCHILLA/1. RONALDO CUCHILLA/2. INGENIERÍA CIVIL DOCS AND PROJECTS/AECODE CURSOS/AECODE AI TALENT/PROYECTO FINAL`.
- **Servicio:** `draft2model/revision_explicaciones.py`, clase `ServicioExplicaciones(app, transporte=None)`. Codex lo integra con el informe, HTTP y UI.
- **Archivos sin tocar:** contexto, informe, el cliente del proveedor y HTTP/UI.

## Qué reutiliza

- **Resultado vigente:** `app.resultados.consultar_resultado`, comprobando que la huella coincida exactamente.
- **Derivados de contexto:** `consultar_derivado` y `consultar(corpus)` de `ServicioContexto` (se usa `app.contexto` si existe; si no, se crea una instancia). Los derivados aceptados son de tipo `recuperacion`, `evaluacion` y `sitio`.
  - La evaluación debe estar ligada al mismo resultado y a su huella.
  - Cualquier otro derivado ligado a un resultado distinto se rechaza.
- **Citas:** `fuentes.verificar_citas`, contra el `corpus.json` de la versión de corpus vigente que usó la recuperación.
- **Transporte HTTP:** en modo real se usa `proveedor_openai._http`, con su endpoint fijo y sin redirecciones, y `leer_respuesta_api`, que exige una única salida JSON completada. El endpoint no se amplía ni se acepta en el cuerpo público.
- **Persistencia:** `<raiz>/.explicaciones_web/trabajos.sqlite3`.
  - Hay una restricción UNIQUE sobre `(caso, clave)`, con el SHA-256 del payload, y un índice único sobre el estado `en_ejecucion`.
  - Cada trabajo tiene una carpeta con `deterministico.json`, `peticion.json`, `preparacion.json`, `intento.json`, `respuesta_api.json`, `salida.json` y un `evento_*.json` por transición. Todos se crean una sola vez y nunca se sobrescriben.
  - Las conexiones SQLite se cierran siempre.
- **Exclusión:** el control propio `.explicaciones_web/llm.lock`. No es el bloqueo de ETABS ni el de visión.

## Contratos (cuerpos exactos)

| Operación | Cuerpo |
|---|---|
| `preparar` | `{caso, expediente_sha256, resultado, huella_resultados, derivados:{recuperacion, evaluacion, sitio} (uuid o null), modelo, opciones:{max_tokens 256–16384, timeout_s 1–180}, clave_solicitud}` |
| `ejecutar` | `{caso, trabajo, huella_preparacion, expediente_sha256, confirmacion_explicita:true}` |
| `recuperar` | `{caso, trabajo, huella_preparacion, confirmacion_explicita:true, resolucion:"cerrar_sin_reintento"}` |
| Lectura | `consultar(caso, trabajo)` y `listar(caso)`. Un trabajo `en_ejecucion` sin worker se marca `incierto`. |

**Reglas del contrato:**
- No hay modelo predeterminado: `modelo` es el identificador declarado por quien prepara.
- Los errores se lanzan como `ErrorExplicaciones(codigo)`. Ningún error, proyección ni archivo contiene rutas, encabezados, endpoint ni la clave.
- `OPENAI_API_KEY` se lee solo en el momento del envío real. El transporte de pruebas recibe `(payload, timeout)`, sin la clave.

## Composición determinística

Se genera siempre a partir de los datos verificados, sin importar lo que responda el LLM:
- **`indicadores`:** una entrada por fila del resultado, con `ref` `R:<id>` y valor, unidad, caso, dirección, ubicación y motivo de omisión exactos.
- **`evaluaciones`:** con `ref` `E:<regla>:<caso>:<dir>:<ubic>`, más el estado, el valor evaluado, el límite configurado, el comparador, la relación y la fuente de la regla.
- **`fragmentos`:** el ID, documento, página, apartado, texto, título, edición y SHA-256 de cada fragmento recuperado.
- **`sitio`:** el estado y las zonas, con `parametros_geotecnicos` y `capacidad_portante` siempre en `null`.
- **`tabla`:** líneas de texto con las cifras exactas.
- **`abstenciones`:** se declaran cuando falta corpus, cuando la búsqueda no tuvo coincidencias, o cuando no hay reglas ni sitio.
- **`limites_verificables`:** la lista de lo que el software puede y no puede comprobar.

La petición incluye solo esos datos, junto con un esquema estricto que limita `indicador` a las referencias existentes y `fragmento_id` a los fragmentos recuperados.

## Contrato `draft2model.explicacion_llm` y su validación

Formato:

```
{contrato, version:"0.1.0",
 declaraciones:[{id, texto, indicadores:[ref], cifras:[{indicador, valor, unidad}], citas:[{fragmento_id, texto}]}],
 abstenciones:[{tema, motivo}]}
```

Que el JSON se pueda parsear **no basta**. Se rechaza la declaración cuando:
- No tiene ningún indicador ni ninguna cita.
- Usa una referencia inexistente.
- Una cifra no es igual al valor del indicador, o la unidad no coincide exactamente.
- Aparece en el texto un número que no figura en las cifras de esa declaración.
- Cita un fragmento que no está en la recuperación, o la cita no pasa `verificar_citas`. Las citas deben coincidir literalmente con el fragmento y con la huella del corpus.
- Afirma certificación o conformidad. Esto se detecta con un patrón acotado que busca expresiones como «certific», «cumple la norma» o «es seguro».

Si hay cualquier error, la salida pasa a contingencia. Si todo pasa, cada declaración queda como `propuesta_pendiente_revision_humana`; **nunca** se presenta como conclusión aprobada.

## Estados y contingencia

| Estado | Cuándo | Salida |
|---|---|---|
| `preparado` | Petición local y huellas listas, sin clave ni red. | Ninguna |
| `en_ejecucion` | Worker vivo con el control tomado. | Ninguna |
| `completado_llm_verificado` | Respuesta válida y sustentada, con las fuentes revalidadas después del envío. | `modo:"llm_verificado"`. `generacion_llm_real` solo vale `true` en modo `real`. |
| `contingencia` | Causas posibles: `clave_ausente` (sin envío), `rechazo_llm` (HTTP definitivo), `respuesta_llm_invalida` o `contenido_no_sustentado` (con `errores_validacion`). | `modo:"contingencia_deterministica"`, con tabla, citas verificadas y abstenciones. `generacion_llm_real:false`. |
| `incierto` | Timeout o pérdida después de `intento.json`, o huérfano tras un reinicio. | Bloquea el caso. No se reenvía y no sirve una clave nueva para evitarlo. |
| `incierto_resuelto` | `recuperar` explícito, sin reintento. | Contingencia con causa `envio_incierto_cerrado`. |
| `fallido_sin_envio` | Las entradas no estaban vigentes antes de enviar. | Ninguna |
| `fallido_fuentes_cambiadas` | Las fuentes cambiaron durante el envío. | Ninguna aceptada |

**Vigencia:**
- Toda consulta revalida el resultado, los derivados (`sha256_salida` y sus fuentes), la composición determinística, la petición y el SHA-256 de la salida.
- Si cambian los resultados, las reglas, el corpus o el sitio, queda `vigente:false` y `salida:null`.
- Las proyecciones siempre incluyen `aprueba_resultados:false`, `aprueba_informe:false` y `conformidad_normativa:"no_evaluada"`.

## Pruebas

Comando:

```bash
TEMP=$PWD/tmp TMP=$PWD/tmp python -m unittest tests.test_revision_explicaciones
```

Resultado: 10 OK.
- En todas las pruebas, `_http`, `Popen`, `urlopen` y `socket.create_connection` lanzan `AssertionError`, y la clave está vacía.
- La única excepción es una prueba que sustituye `_http` por un doble con una clave falsa. Esa prueba comprueba que la clave no aparece en ningún archivo.

Qué cubren:
- Preparación sin clave, idempotente y consultable tras reinicio.
- Contingencia por clave ausente.
- Respuesta válida sin reenvío, con el esquema limitado a los fragmentos recuperados.
- Siete variantes de contenido no sustentado: cita falsa, cifra alterada, unidad alterada, número sin respaldo, indicador inexistente, declaración sin sustento y afirmación de conformidad.
- Respuesta inválida y rechazo HTTP.
- Incierto que bloquea una clave nueva, sin reenvío tras reinicio y con recuperación explícita.
- Huérfano tras reinicio.
- Fuentes alteradas antes y durante el envío.
- Modo real con HTTP sustituido.

## Límites

- **Texto libre:** el sentido técnico no se verifica, por eso queda como propuesta para revisión humana. El filtro de afirmaciones prohibidas es heurístico.
- **Números en el texto:** se exige respaldo para cualquier número. Esto incluye los que aparecen dentro de identificadores con guion, lo que puede provocar rechazos conservadores.
- **Rechazo definitivo:** se distingue por el mensaje `OpenAI devolvió HTTP` del cliente existente. Cualquier otra excepción del transporte se trata como `incierto`.
- **Ruta del corpus:** se obtiene desde `<caso>/contexto/corpus/<id>/corpus.json`, después de validarlo mediante la API pública de contexto.
- **No verificado:** API real, red, ETABS, Computer Use, la suite completa y la integración con informe/HTTP/UI.

## Refuerzo de integración Codex

Se reprodujo TypeError ante referencias de indicador/cifra/cita que fueran listas u objetos en lugar de IDs de texto. El validador comprueba sus tipos antes de buscar en índices; una respuesta recibida malformada produce contingencia determinística, sin simular incertidumbre del envío ni bloquear el caso. Regresión con tres respuestas malformadas: tests/test_explicaciones_respuesta_malformada.py, tmp/explicaciones_tipos_118.log, 1 prueba con3subcasos OK7.495s. No red real. Esto modifica el backend respecto a la huella histórica de la entrega de Claude; es una corrección posterior de Codex.
