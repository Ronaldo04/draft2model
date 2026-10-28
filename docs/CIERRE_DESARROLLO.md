# Cierre del desarrollo funcional — estado entregado para el ensayo final

- **Corte:** 18 de octubre de 2026 (Lima), encargo consolidado `seguimiento/ENCARGO_CLAUDE_CIERRE_DESARROLLO.md`.
- **Lectura correcta:** este documento describe lo que **existe y se verificó con datos sintéticos**. **No** declara completo el goal ni el piloto: las fixtures, los dobles y las pruebas DOM no acreditan una extracción real, el comportamiento de ETABS sobre el caso, criterios de ingeniería ni conformidad normativa.

Actualización 19-10-2026: las cifras y capacidades de este corte son históricas. Estado vigente en [RETOMAR](RETOMAR.md). Los cuatro protocolos de proveedor ya están integrados localmente (sin API real). Superficies0.2 tienen geometría/conversión/tabular/aprobación declarada y plan de desarrollo; la ejecución integrada todavía está bloqueada. Plano3D0.3 tiene QA165 sintética. Aberturas geométricas0.3 tienen revisión167; ingreso/visualización y representación de aligerados están en desarrollo. Faltan implementación material y validación real, además de los accesos indicados; el título «pendientes externos» inferior no debe interpretarse como ausencia de código pendiente.

## 1. Brechas P1 cerradas en esta etapa (arquitectura funcional)

| Brecha (PENDIENTES_FUNCIONALES_CIERRE §A) | Estado entregado | Guía |
| --- | --- | --- |
| Controles internos postsolver (§5.10; O2.4/O2.13/O5.1, P09/P10) | Núcleo, servicio persistente revalidado, HTTP, UI, selección explícita y opt-in en el informe (JSON/HTML/PDF, aprobación hija y descarga revalidadas). La participación modal y el equilibrio se calculan desde los bytes de una lectura aceptada; las advertencias del solver solo provienen de una fuente **declarada** y se marcan como no verificadas. | [CONTROLES_ANALISIS](CONTROLES_ANALISIS.md) |
| Proximidad a fronteras de sitio (§5.9; O4.4/O4.8, P07) | `limite` = franja incierta según `precision_m` (entrega del subagente, [SITIO_PRECISION](SITIO_PRECISION.md)). Consumidores revisados: el informe explica cada estado y presenta las zonas en `limite` como fronteras, no como asignación; las explicaciones se abstienen de afirmar pertenencia; la UI de contexto añade la aclaración. | [SITIO_PRECISION](SITIO_PRECISION.md) |
| Previsualización geométrica revisable (§5.8; O4.2/O4.3, P06) | Esquema por nivel con la unidad del contrato; correspondencia **declarada** con tres anclas no colineales y transformación afín exacta; versión inmutable revalidada (geometría, original, preview y registro); HTTP/UI con SVG; puntos fuera de imagen listados. | [REVISION_SUPERPOSICION](REVISION_SUPERPOSICION.md) |

Otras entregas ya integradas y aceptadas por Codex, que no se rehicieron:
- revisión declarada de resultados y su opt-in en el informe;
- contingencia tabular CSV/XLSX con HTTP/UI;
- contexto (corpus, reglas y sitio) y explicaciones sustentadas con contingencia;
- proveedor visual con transporte de pruebas.

## 2. Cómo usar los paneles nuevos (resumen)

1. **Superposición:** elegir geometría y nivel. Sin anclas solo se ve el esquema métrico, con la advertencia de que «NO está alineado». Para superponer: original y página, tres anclas (nodo, u, v), revisor, fecha, motivo y confirmación. Cada versión geométrica corregida exige una correspondencia nueva.
2. **Controles postsolver:** elegir una lectura aceptada y vigente.
   - Declarar en JSON las tres familias con aplicabilidad, criticidad, criterio y parámetros. No hay tolerancias por defecto.
   - La fuente de avisos del solver es opcional; si se deja vacía, ese control queda `sin_datos`.
   - Registrar con confirmación, elegir la versión manualmente y revisar estados, base, verificación, fórmulas, valores, faltantes críticos y avisos.
   - `apto_proyeccion_controlado` requiere que todos los controles aplicables sean satisfactorios y que al menos uno se calcule desde la lectura.
3. **Informe:** con el resultado y el análisis explícitos, activar por separado contexto, explicación, revisión declarada o **controles** (estos últimos solo con el mismo análisis, ID y SHA). Generar, descargar y aprobar la versión documental. Cualquier fuente que cambie invalida el informe, su aprobación y su descarga.

## 3. Verificación de esta etapa

Se hicieron pruebas focales por fase y una pasada global con `scripts/verificar_proyecto.py` usando el Python aislado 129 y Node. Ver §5 de este documento y el marcador `seguimiento/ENTREGA_CLAUDE_CIERRE_DESARROLLO.json` para comandos, logs, códigos y omisiones exactos. Una prueba Node obsoleta se actualizó: afirmaba que el informe aún no consumía contexto ni explicación. El cambio queda registrado en el marcador.

## 4. Pendientes externos (no son código faltante de esta etapa)

1. **Ensayo real con los planos de referencia:** seguir [PLAN_ENSAYO_REFERENCIA](PLAN_ENSAYO_REFERENCIA.md).
   - Lo que hay preparado no es una extracción.
   - Hace falta la credencial y el modelo locales de **un** proveedor, que no deben compartirse en el chat. OpenAI Responses, Gemini generateContent, Anthropic Messages y Chat Completions compatible están integrados localmente, todos sin ensayo API real en este corte. Ver [accesos y proveedores](ACCESOS_Y_PROVEEDORES.md).
   - El paquete detallado vigente para el ensayo es el **135** (`bfda0ef3570049b1bc4dca02f11848c6`: 3 vistas generales y 7 recortes, 10 imágenes), preparado sin envío.
   - Las decisiones físicas (unidades, escala, cargas, materiales) deben revisarse; no se inventan.
2. **ETABS real sobre la configuración revisada del caso:** construcción, análisis y lectura. Las pruebas web usan dobles.
   - Las tablas reales de participación modal, reacciones y cargas determinarán qué selectores de control son aplicables.
   - El log del solver no lo extrae el lector: o se aporta una fuente declarada, o el control queda `sin_datos`.
3. **Criterios revisados:** tolerancias y mínimos de controles, reglas, corpus y capa de sitio aplicables al caso, declarados por quien revisa. No hay valores por defecto.
4. **Revisión visual del recorrido real** con el caso. QA143/145 de Codex comprobaron en el navegador, con datos sintéticos, el registro de controles y el informe; el resto del recorrido real sigue pendiente.
5. **Copia limpia: realizada por Codex** (146/148, `tmp/c146/copia_limpia.json`: `completa: true`, 850 Python y 26 Node correctos, sin omisiones y con fuentes estables). Hará falta repetirla tras los cambios de proveedores (Gemini y modo compatible).
6. **Comparación manual con ETABS**, aplazada por decisión del usuario, y la medición de tiempos y costo del flujo completo.

## 5. Resultado de las pasadas globales (`scripts/verificar_proyecto.py`, Python aislado 129 y Node)

| Pasada | Python | Node TAP | PowerShell `-File` / pip / CLI | Estabilidad | `validacion_local_completa` |
| --- | --- | --- | --- | --- | --- |
| 133 (`tmp/verificacion_cierre_claude_133.json`) | 848 pruebas, **1 fallo** | 26/26 | OK / OK / OK | **No**: Codex modificó tres archivos de `seguimiento/` durante la ejecución | `false` |
| 138 (`tmp/verificacion_cierre_claude_138.json`), tras las correcciones | **850 OK**, sin omisiones | **26/26**, 0 skip y 0 todo | OK / OK / OK | **No**: Codex creó cuatro archivos nuevos `seguimiento/*_14x.json` durante la ejecución. Ningún archivo de `draft2model/`, `tests/`, `scripts/` ni `examples/` cambió. | `false` |

**Fallo de la pasada 133:** `test_informe_revision_resultados` era intermitente. Al extraer texto, el PDF convierte «ff» en la ligadura U+FB00 dentro de IDs hexadecimales aleatorios, así que falla aproximadamente una vez de cada nueve. Se corrigió normalizando con NFKC en la prueba.

**Limitación visible:** al copiar un ID desde el PDF puede aparecer el glifo de ligadura. JSON y HTML conservan el ID exacto.

**Correcciones entre pasadas:**
- Integración de la corrección 137 de Codex (revalidación final de los controles).
- Revalidación final análoga en la superposición.
- Esa prueba de ligaduras.

**Qué no acredita:** como la estabilidad la rompieron archivos de otro actor, ninguna de estas dos pasadas locales se presenta como validación completa. La evidencia global vigente es la copia limpia 146/148 de Codex (ver §4.5).

## 6. Contraste con la referencia (`seguimiento/REFERENCIA_LEGIBILIDAD_134.json`)

Las láminas muestran aligerados hasta el cuarto nivel, columnas, placas, vigas, muro portante típico, escalera, cisterna y tanque. El texto extraíble del PDF es insuficiente, así que hace falta evidencia visual localizada.

- **Niveles:** el contrato geométrico admite niveles sin límite artificial.
- **Sin representación en el contrato ni en el plan:** losas aligeradas, aberturas, escalera, cisterna y tanque.
- **Columnas y vigas:** solo como frames rectangulares desde la configuración.
- **Superposición:** solo dibuja muros.

No se afirma soporte del modelo completo; la representación debe decidirse con la referencia revisada (PENDIENTES §A, condicional).
