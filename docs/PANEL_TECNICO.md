# Panel técnico de resultados

Generar instantánea interactiva local: `python -m draft2model.panel_tecnico --resultados resultados.json --reglas reglas.json --salida panel_nuevo.html`. Opcional `--geometria geometria.json` exige contrato consistente y SHA256 exacto de la referencia de resultados para mostrar número de muros; si no se proporciona, aparece no disponible.

El HTML autónomo filtra por caso, dirección e indicador, conserva cifras/unidades, reglas con fuente, huellas y advertencias. Distingue simulaciones de resultados declarados reales; no autentica la procedencia de estos últimos. No usa red ni llama motores. Se validan resultados y se recalcula evaluación con reglas de aprobación vigente antes de generar. No acepta evaluación externa sin comprobar ni sustituye resultados previos.

`--reglas` es opcional: al omitirlo, conserva resultados y advertencias y muestra evaluación pendiente, sin cumplimiento ni reglas inventadas. Un archivo de reglas proporcionado sigue exigiendo validación y revisión vigente. Ejemplo calculado con ETABS real sobre datos sintéticos: `tmp/panel_etabs_estatico_real_005.html`; no se ha inspeccionado visualmente ese HTML en esta entrega.

Las opciones `--analisis-raiz`, `--analisis-caso`, `--analisis-resultado` y `--analisis-corrida` (todas o ninguna; en Python, `evidencia_analisis={...}`) adjuntan evidencia de análisis revalidada desde sus ficheros. Están descritas en [EVIDENCIA_ANALISIS.md](EVIDENCIA_ANALISIS.md). Con ellas:

- la tarjeta indica "Cálculo completado verificado (EST=4); resultados sin revisar";
- una sección enumera el modelo con revisión declarada, la corrida aceptada, el EDB analizado y los estados separados de revisión de resultados y conformidad normativa;
- los datos incrustados no contienen rutas locales.

Sin evidencia, el panel no incluye esa clave. Una evidencia alterada se rechaza sin crear el archivo. Ejemplo con evidencia real sintética: `tmp/panel_evidencia_analisis_001.html`, revisado en el navegador integrado sin errores de consola.

Es una instantánea que debe regenerarse al cambiar fuentes. El sitio aparece no disponible porque esta primera integración no vincula una capa a los resultados. Se conserva esa ausencia en vez de inferir condición del terreno. El informe preliminar y su aprobación siguen su flujo independiente.
