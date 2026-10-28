# Auditoría final de guía, comandos, cobertura y pendientes — Claude

- **Ruta:** `D:/RONALDO CUCHILLA/1. RONALDO CUCHILLA/2. INGENIERÍA CIVIL DOCS AND PROJECTS/AECODE CURSOS/AECODE AI TALENT/PROYECTO FINAL`.
- **Fecha:** 18–19 de octubre de 2026.
- **Método:** solo lectura de `README.md`, `docs/GUIA_REPRODUCIBLE.md`, `docs/CIERRE_DESARROLLO.md`, `docs/MATRIZ_CIERRE_VIGENTE.md`, `docs/PLAN_ENSAYO_REFERENCIA.md`, `docs/CONEXION_OPENAI.md`, `Abrir revision de planos.cmd` y los módulos citados, más `--help` del CLI.
- **No se ejecutó:** suites, red, API, ETABS, instalaciones ni Computer Use.
- **No se leyeron** secretos ni datos del cajetín.
- **Alcance de las conclusiones:** esta auditoría **no prueba ejecución real**. Lo «verificado» aquí es una correspondencia entre documentación y código.

**Evidencia de verificación global reciente:** `tmp/c146/copia_limpia.json`, con `completa: true`, `codigo: 0` y `sin_red: true`, fecha 2026-10-19T02:13Z, usando Python aislado 129. Codex informa 850 Python y 26 Node OK, sin omisiones y con fuentes estables.

## A. Errores documentales (efecto en la reproducción y corrección propuesta)

**D1 · README desactualizado** (`README.md:32`, `:35` y `:36`).
- Afirma tres cosas ya superadas:
  - la cadena de imágenes derivadas está «en desarrollo», cuando la guía §4.2 la describe integrada;
  - la «UI de esa aprobación [documental] en desarrollo; contexto técnico… pendiente HTTP/UI/informe; explicaciones candidatas en revisión», cuando todo está integrado (guía §4.9; `informes.js`, `contexto.js` y `explicaciones.js` están montados);
  - «la copia100 falló», sin mencionar que la copia 146/148 terminó completa.
- Además omite los paneles de controles postsolver, superposición y tabular.
- **Efecto:** quien empieza por el README cree que funciones entregadas no existen y que no hay verificación global vigente.
- **Corrección:** actualizar la tabla de capacidades con los estados de `docs/CIERRE_DESARROLLO.md` §1, citar `tmp/c146/copia_limpia.json` como verificación vigente y conservar copia100 solo como antecedente.

**D2 · La guía mantiene como última evidencia global una copia fallida y una instalación antigua** (`docs/GUIA_REPRODUCIBLE.md:127` y `:24`).
- La línea 127 dice «La copia limpia068 aceptada precede… La copia100 falló…» sin la copia 146.
- La línea 24 cita como instalación aceptada `tmp/inst19/verificacion.json` y no la instalación 129 (`docs/VERIFICACION_INSTALACION_ACTUAL.md`).
- **Corrección:** añadir la copia 146 (`completa: true`, 850 Python y 26 Node) y la instalación 129 como evidencia vigente, y mover 068, 100 e inst19 a antecedentes.

**D3 · `docs/CIERRE_DESARROLLO.md` quedó desactualizado tras la copia 146** (`:45` y `:64`; documento propio de esta sesión).
- Sigue presentando la copia limpia completa como pendiente.
- **Corrección:** marcarla como realizada por Codex con su ruta. Mantener pendiente solo la revisión visual del recorrido que no cubrieron QA143/145, y el ensayo real.

**D4 · La credencial no llega al servidor si se usa el `.cmd`.**
- `Abrir revision de planos.cmd:3` lanza `python -m draft2model.revision_visual` desde `cmd.exe`.
- `docs/CONEXION_OPENAI.md:31-34` indica fijar `$env:OPENAI_API_KEY` «dentro de la misma consola que ejecutará el cliente».
- `docs/GUIA_REPRODUCIBLE.md:77` solo dice «usando la credencial local del servidor», sin nombrar la variable ni el requisito de herencia.
- `revision_proveedor.py:80` y `revision_explicaciones.py:87-88` leen `OPENAI_API_KEY` del **proceso servidor**.
- **Efecto:** al abrir la UI con doble clic, el proveedor web responde `clave_ausente_sin_envio` y las explicaciones quedan en contingencia `clave_ausente`, aunque la clave exista en otra consola.
- **Corrección:** documentar en la guía §3 y §4.3 que, para el envío real, el servidor debe iniciarse desde la misma consola de PowerShell 7 donde se fijó la variable (`python -m draft2model.revision_visual …`), no con el `.cmd`. Sin mostrar ni guardar la clave.

**D5 · Afirmación falsa de exclusividad** (`docs/CONEXION_OPENAI.md:41`).
- Dice que el comando CLI `proveedor_openai ejecutar` es «el único comando que puede transmitir imágenes». `POST /api/proveedor/ejecutar` (`revision_proveedor.py`) también transmite. Además, `revision_explicaciones.py:548` envía a la API texto derivado de resultados, fragmentos y sitio, aunque no imágenes.
- **Corrección:** enumerar las tres vías de transmisión externa: CLI de visión, proveedor web y explicaciones web.

**D6 · El envío CLI no figura en la tabla de comandos** (`docs/GUIA_REPRODUCIBLE.md` §5, fila «Visión»).
- `draft2model --help` solo ofrece `preparar-openai` (`cli_vision.py:12`, `:20`). La ejecución CLI existe únicamente como módulo `python -m draft2model.proveedor_openai ejecutar …` (`CONEXION_OPENAI.md:44`).
- **Corrección:** añadir esa línea de módulo, o el enlace a CONEXION_OPENAI, en la fila de visión.

**D7 · El plan de ensayo no incluye las capacidades nuevas** (`docs/PLAN_ENSAYO_REFERENCIA.md`).
- Entre §6 (lectura) y §7 (informe) falta el paso de **controles postsolver** (`/api/controles/crear` sobre la lectura aceptada, con criterios revisados) y su opt-in en el informe.
- El cuerpo de `/api/informe/crear` (línea 160) no menciona los campos opcionales `revision_resultados:{id, sha256_revision}` ni `controles_analisis:{id, sha256_controles}`.
- Tampoco aparece la superposición geometría↔plano como puerta de revisión espacial antes de aprobar la geometría (§3).
- **Corrección:** añadir los pasos y campos con sus puertas: controles con `apto_proyeccion_controlado` y sus faltantes críticos visibles; superposición con tres anclas declaradas, solo de muros.

**D8 · Requisito de PowerShell 7 no destacado en la guía** (`docs/CONEXION_OPENAI.md:34`).
- `Read-Host -MaskInput` solo existe en PowerShell 7. En Windows PowerShell 5.1, que es el entorno del puente ETABS, ese comando falla.
- **Corrección:** indicarlo en la guía o dar la alternativa 5.1 con `-AsSecureString` y conversión local. No es un fallo de código.

**Sin hallazgos en (cobertura exacta revisada):**
- Comandos de arranque y demo (`README:12-15,23`; guía §1–§3) frente al CLI: existen `demo-integrada`, `--verificar`, `revision_visual --raiz --puerto --sin-navegador`, `scripts/verificar_instalacion_limpia.py`, `scripts/renderizar_informe.py`, `requirements-win-py310.lock` y `tmp/wheels_clean_001` (dos wheels).
- El `.cmd` usa la raíz por defecto `data/private` (`gestion_extraccion.py:36`).
- Requisito de Node para las pruebas de interfaz y flag `--node` (guía §6).
- Orden de selección en la UI de la guía §4.1–§4.12, contrastado con la existencia de los paneles y eventos. No se verificó visualmente.

## B. Código faltante fundado (no implementado en esta auditoría)

**C1 · Gemini no está soportado.**
- Hoy solo existe OpenAI Responses, acoplado en:
  - `proveedor_openai.py:27` (ENDPOINT fijo);
  - `:83-121` (payload: `input_image` con data URL, rol `developer`, `max_output_tokens`, `store:false` y `text.format.json_schema` estricto);
  - `:139-158` (`Authorization: Bearer`);
  - `:161-184` (`leer_respuesta_api`: `output` → `message` → `output_text`);
  - `:205-211` (`OPENAI_API_KEY`);
  - `:128` y `:131`/`:225` (contrato `plan_vision_openai` y carpetas `planes_openai`/`intentos_openai`);
  - `:248` (`proveedor='openai'`);
  - `:61-80` (esquema con `additionalProperties:false` y `anyOf` con null).
- `revision_proveedor.py:80,143,157,163,322,345,376,394,451` depende de esas rutas, del contrato y de la variable.
- `revision_explicaciones.py:87-88,279-283,548,552,574` usa `cliente._http` y `leer_respuesta_api`, y clasifica el rechazo definitivo por el **texto** `'OpenAI devolvió HTTP'`.
- `cli_vision.py:12,20` (`preparar-openai`) y `revision_web/proveedor.js:8` (detalle `low/high/auto`, propio de OpenAI).

**Impacto concreto de incorporar Gemini (API generateContent), sin declararlo soportado:**

1. **Transporte nuevo y fijo por proveedor.**
   - Endpoint `…/v1beta/models/{modelo}:generateContent` con cabecera `x-goog-api-key`.
   - Imágenes como `inline_data{mime_type:'image/png', data}` en `contents[].parts`; instrucción del sistema en `systemInstruction`; `generationConfig.maxOutputTokens`.
   - Salida JSON mediante `responseMimeType:'application/json'` y esquema.
   - No hay equivalente de `store:false` ni de `detail`; la resolución se controla con otro parámetro.
2. **Esquema.** El subconjunto de esquema de Gemini difiere del JSON Schema estricto actual (`additionalProperties`, `anyOf` con null y tipos nulos). Habría que traducir `esquema_respuesta` y el de explicaciones.
   - La garantía real seguiría siendo la validación local existente (`entrada_vision.adaptar_respuesta` y `ServicioExplicaciones.validar_llm`), que no debe relajarse.
3. **Lectura de respuesta.**
   - `candidates[0].content.parts[].text` y `finishReason`.
   - Bloqueo en `promptFeedback.blockReason`.
   - Uso en `usageMetadata` (`promptTokenCount` y `candidatesTokenCount`).
   - Haría falta un `leer_respuesta_gemini` con las mismas exigencias: respuesta completa, un solo JSON, sin rechazo ni herramientas.
4. **Persistencia y contratos.** Un contrato de plan con `proveedor` explícito (o `plan_vision_gemini`) y carpetas o campo por proveedor. `ServicioProveedor._revalidar` y `_verificar_salida` hoy fijan `plan_vision_openai`, `planes_openai` y `proveedor_declarado:'openai'`. `entrada_vision.registrar_respuesta` ya admite `proveedor` libre.
5. **Clasificación de errores.** Sustituir el prefijo de texto `'OpenAI devolvió HTTP'` (`revision_explicaciones.py:552`) por un tipo o código de error estructurado: definitivo (4xx) frente a incierto (timeout o pérdida). Esto preserva el bloqueo de reenvío.
6. **Credencial.** Otra variable de proceso, por ejemplo `GEMINI_API_KEY`, con la misma regla: solo presencia, nunca persistida ni mostrada. Le aplica también D4 (herencia en el proceso servidor).
7. **Privacidad y uso autorizado.** En el nivel **gratuito**, las condiciones de Google para servicios no pagados han permitido usar el contenido enviado para mejorar productos y someterlo a revisión humana.
   - Debe verificarse en las condiciones vigentes antes de enviar planos privados: el expediente declara uso `pruebas_procesamiento` y la autorización de transmitir a un tercero es una decisión del usuario.
   - El límite de petición *inline* es menor que el límite local de 40 MiB; imágenes mayores exigirían la Files API, lo que implica otra transmisión y almacenamiento temporal en el proveedor.
   - Límites de cuota y frecuencia del nivel gratuito.
8. **UI y CLI.** Selector de proveedor, mapeo de «detalle» y comando o plan CLI por proveedor. Pruebas con un transporte Python doble con forma de respuesta Gemini; no sustituyen un ensayo real.
9. **Documentación.** Nueva guía de conexión y actualización de PLAN_ENSAYO §1 («Modelo visual», hoy específico de Responses).

**Responsable propuesto:** implementación por quien Codex asigne, sobre archivos exclusivos. Evidencia de cierre: pruebas con transporte doble Gemini y, al final, un ensayo real autorizado con la puerta `llamada_real_acreditada:true` del proveedor web.

**C2 · El lector no extrae el log del solver.** Ya documentado en `CONTROLES_ANALISIS.md`: el control de advertencias depende de una fuente declarada; sin ella queda `sin_datos`. Si el criterio exige advertencias reales, hace falta una extracción del log o los mensajes de ETABS en el puente, con evidencia real.

**C3 · Representación física limitada** (`contratos.py` COLECCIONES; `plan_modelado.py`; `operaciones_etabs.py`).
- Representado: nodos en planta, niveles sin límite y muros rectangulares verticales.
- Columnas y vigas solo como frames rectangulares desde la configuración.
- Sin representación: losas aligeradas, aberturas, escalera, cisterna ni tanque.
- `seguimiento/REFERENCIA_LEGIBILIDAD_134.json` confirma láminas hasta el cuarto nivel con esos elementos.
- Ampliar el contrato **solo** si la representación revisada del caso lo exige. No es un fallo, pero impide afirmar un modelo completo.

## C. Decisiones y datos externos pendientes (inventario con responsable y evidencia de cierre)

| # | Requisito material | Responsable | Evidencia que lo cerraría |
| --- | --- | --- | --- |
| E1 | Elegir el proveedor (OpenAI o Gemini) y su modelo, y autorizar la transmisión de los planos privados a ese tercero, incluidas las condiciones del nivel gratuito si se usa Gemini. | Usuario, con Codex | Decisión registrada sin secretos; si es Gemini, implementar C1 antes. |
| E2 | Credencial local en el proceso servidor (D4). | Usuario | Trabajo del proveedor en `completado_verificado` con `modo:real` y `llamada_real_acreditada:true`. |
| E3 | Extracción visual real del paquete `b7f15fc…` y revisión humana de cotas y etiquetas. | Codex (operación) + revisor | Extracción con candidatos revisados y evidencia localizada (PLAN §2). |
| E4 | Manifiesto físico, geometría aprobada y superposición declarada. | Revisor del caso | Geometría aprobada vigente y correspondencia de superposición vigente. |
| E5 | Configuración estructural: materiales, cargas, masa, apoyos, casos, sitio y plantilla EDB. | Revisor de ingeniería | `apto_para_adaptador:true` sin faltantes inventados (PLAN §4). |
| E6 | Construcción, análisis y lectura ETABS reales. | Codex en el host autorizado | Trabajos aceptados en modo real con CSI 4 y lectura verificada (PLAN §5–§6). |
| E7 | Criterios de controles postsolver, reglas, corpus y capa de sitio del caso. | Revisor | Controles registrados con criterios declarados; reglas, corpus y sitio con aprobación declarada. |
| E8 | Revisión declarada de resultados y aprobación documental del informe. | Revisor | Revisión vigente seleccionada y aprobación documental hija. |
| E9 | Revisión visual del recorrido real completo, más allá de QA143/145 con datos sintéticos. | Codex | Capturas del recorrido con el caso. |
| E10 | Benchmark de precisión visual y comparación manual con ETABS (aplazados por el usuario); tiempos y costo con tarifa fechada. | Usuario y revisor, al final | Métricas con referencia humana; comparación con tolerancias justificadas. |

## D. Límites de esta auditoría

- **Lo revisado:** documentos y líneas citados, el CLI con `--help` y la búsqueda de dependencias de OpenAI en `draft2model/`.
- **Lo no revisado:** todas las guías específicas (`REVISION_*`, `CLI_*`) línea a línea, y la UI de forma visual.
- **Gemini:** el análisis se basa en conocimiento general de la API, no verificado contra su documentación ni sus condiciones vigentes (no se usó red). Debe contrastarse antes de implementarlo.
- **Nada modificado salvo este archivo y el marcador.** No se declara soporte de Gemini ni cierre del goal o del piloto.
