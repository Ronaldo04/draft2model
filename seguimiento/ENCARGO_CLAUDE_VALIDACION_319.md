# Encargo319: corregir validación del candidato antes de integrar

317 queda intacto. Codex verificó8hashes y repitió8pruebas. Encontró cuatro entradas sintéticas que se aceptan indebidamente con totales (`seguimiento/REVISION_PREDICTOR_318.json`):

- `vigas=['VIGA','FANTASMA']`: omiteFANTASMA, declara pedidas1y cobertura completa.
- Punto declarado dos veces: registra problema pero sigue produciendo totales.
- Operación `cFrameObj.SetEndLengthOffset` con AutoOffsetFalse y longitudes explícitas: se ignora y prediceAuto.
- Peso volumétrico−25: produce descuento−1kN y total completo.

Además Codex confirmó configuración del piloto en **copia verificada** sin solver/Save: `tmp/configuracion_318_reparacion/registro.json`, versión aplicación21.1.0, kN_m_C, GetMergeTol.001m, SHA original antes/después y copia idénticos42371308…, ApplicationExit0/PID17340salió. El primer intento318falló antes de iniciarETABS por Get-FileHash ausente; se reparó conSHA256.NET. Fuente312 intacta.

## Objetivo

Entregar un módulo puro autónomo319, con validación conservadora, pruebas negativas y predicción/contraste separados. No integrar ni editar producto/libro. Sin ETABS, APIs, claves, modelo manual ni proyectos2/3.

1. Copia317en carpeta319y corrige los cuatro defectos. Ninguna solicitud desconocida/duplicada o inválida puede desaparecer del denominador. Distingue listas vacías de selección ausente; prohíbe strings usados como listas. Puntos/frames/argumentos duplicados o referencias inválidas requieren rechazo o abstención explícita, sin totales aparentes. Entradas mal formadas deben producir un resultado diagnóstico o error de dominio claro.
2. Valida dimensiones positivas y pesos no negativos finitos (peso0puede ser válido si se declara). No emitir pesos/descuentos negativos o no finitos. Aplica esas comprobaciones al miembro objetivo, no solo a columnas conectadas.
3. No ignorar opciones de extremos/peso que contradigan los supuestosAuto. Rechaza como no cubiertas operaciones explícitas de extremos no interpretadas; trata modificadores de masa/peso de sección o de objeto y cambios de sección/material/ejes relevantes. No pretendas soportarlos por defecto. Inserción/ejes avanzados del miembro objetivo también requieren abstención si no cubiertos. Mantén los casos válidos existentes.
4. Si el plan declara `unidades_etabs`, debe coincidir con config. Config ausente, versión desconocida, tolerancia inválida o procedencia inválida se resuelven antes de analizar un plan mal formado. El predictor sigue sin leer archivos, recibos, offsets ni resultados del solver.
5. Añade pruebas que reproduzcan los cuatro fallos y otros casos pertinentes: selección mal formada, referencia/argumento duplicado, dimensión negativa y modificador de peso no unitario. Las pruebas deben comprobar ausencia de totales/cobertura falsa, no solo que exista un mensaje. Repite las8pruebas anteriores sobre319con cambios mínimos de importación, conservando317.
6. Ejecuta el plan del piloto como otra comprobación, con cfg explícita y referencia a la configuración318ya verificada. Guarda predicción319antes del contraste separado, conserva exposición previa declarada (no ensayo ciego), compara90extremos y determina qué puede integrarse sin cambiar el libro bruto histórico. No afirmar masa oficialmente coherente.

## Perímetro

Solo `seguimiento/claude_ruta/predictor_auto_319/` y marcador final `seguimiento/claude_ruta/MARCADOR_PREDICTOR_319.json`, tarea exacta `predictor_319`, estado `entrega_candidata` o `bloqueo_declarado`, mapa `archivos_permitidos_sha256`. Codex conserva integración.317/318/315/316y la entrega312 son de solo lectura. Tu cuota estaba98%: prioriza módulo y pruebas; si limita, conserva parcial y marcador, sin intentar eludirla.
