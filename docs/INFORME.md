# Informe preliminar JSON, HTML y PDF

El módulo `draft2model.informe` construye un informe documental en borrador desde los contratos de resultados y reglas existentes. Reutiliza `exigir_resultados`, `validar_reglas` y `evaluar_resultados`: la evaluación se recalcula con las huellas vigentes. Si se proporciona una evaluación ajena, debe coincidir exactamente con la recalculada. No ejecuta ETABS ni LLM; utiliza explicación determinística, contempla ausencia de corpus y no inventa indicadores, cifras ni citas.

Sin `--reglas` se exporta un borrador de resultados con `reglas:null` y contrato `draft2model.evaluacion_pendiente`, estado pendiente y lista de evaluaciones vacía. No declara cumplimiento ni inventa fuentes. La huella del campo ausente es SHA256 del JSON null; el documento lo identifica como reglas pendientes. La validación recalcula también ese estado, por lo que no admite cambiarlo a evaluado por edición. Aprobar el documento sigue siendo una declaración documental limitada, sin aprobar ingeniería.

Se corrigió pérdida de contenido PDF al paginar tablas dentro de otras tablas: las secciones usan bloques de flujo, conservando tablas y títulos. Se revisó visualmente con Poppler el informe calculado sintético `tmp/informe_etabs_estatico_006/informe.pdf`, dos páginas con todos los indicadores, faltantes y trazabilidad. El intento anterior `_005` se conserva como evidencia del defecto y no debe entregarse. Pruebas de informe/panel: 18 OK (`tmp/pruebas_pdf_corregido_013.log`). La regresión normaliza ligaduras Unicode para comparar texto extraído sin confundir tipografía con ausencia de contenido; la inspección visual sigue siendo necesaria.

## Ejecución reproducible

Desde la raíz del proyecto y el entorno con PyMuPDF ya instalado:

```powershell
.\.venv\Scripts\python.exe -m draft2model.informe --resultados examples/resultados_estructurales_sinteticos.json --reglas examples/reglas_estructurales_sinteticas.json --contexto examples/informe_sintetico/contexto.json --salida tmp/informe_sintetico
```

El padre de salida debe existir y la carpeta destino debe ser nueva. Se crean `informe.json`, `informe.html` e `informe.pdf`; no se sobrescriben carpetas previas. Validación, renderizado y serialización preceden a crear la carpeta. Un error de escritura en disco puede dejar una carpeta parcial para inspección: repetir requiere otro destino.

El ejemplo es una simulación con valores fabricados para probar software. Sus reglas y referencias sintéticas no acreditan cálculo ETABS, aprobación de ingeniería, vigencia normativa ni seguridad. La geometría y sitio aparecen no disponibles si no se aportan sus datos vinculados. El JSON conserva los contratos originales y la evaluación recalculada para comprobar la concordancia de presentación.

Opciones adicionales: `--evaluacion archivo.json`, `--geometria archivo.json`, `--corpus manifiesto.json`, `--citas citas.json`. Las citas son una lista de objetos `{"fragmento_id":"F1","texto":"texto exacto del corpus"}`. Se rechazan citas sin corpus, inexistentes, duplicadas o con texto alterado. La carga y verificación reutilizan `draft2model.fuentes`; el corpus debe tener aprobación declarada vigente y archivos con hashes correctos. Su edición, página, apartado y título se muestran en la salida. Las fuentes declaradas de reglas se distinguen de esas citas verificadas; si el contrato no aporta página, se muestra no disponible.

## Contexto explícito

El archivo de contexto requiere exactamente estas cuatro claves:

```json
{
  "titulo": "Informe preliminar del caso",
  "hipotesis": ["Hipótesis documentadas y alcance de su revisión."],
  "faltantes": ["Información que todavía no está disponible."],
  "sitio": null
}
```

Si se aporta sitio, debe ser una salida declarada del contrato `draft2model.sitio` v0.1.0 de `consultar_sitio`. Se conserva su estado dentro/límite/ambiguo/sin cobertura, zonas, fuente/edición/referencia, fecha, precisión y naturaleza sintética. El generador lo identifica como **declaración contextual**: no recomputa la intersección espacial ni autentica la capa desde ese snapshot. No asigna perfil normativo, parámetros geotécnicos o capacidad portante. Sin sitio se muestra no disponible. No se usa corpus/sitio sintético para sustentar un informe de resultados declarados reales.

## Siete resultados y ausencias

1. **Generación y análisis:** el contrato de resultados no contiene estado del solver ni acta de aprobación del modelo. Sin más datos, ambos estados se muestran no disponibles: la presencia de valores no demuestra ejecución real.

   Con la opción `evidencia_analisis` (CLI: `--analisis-raiz`, `--analisis-caso`, `--analisis-resultado` y `--analisis-corrida`, las cuatro juntas) se adjunta evidencia revalidada desde sus ficheros; ver [EVIDENCIA_ANALISIS.md](EVIDENCIA_ANALISIS.md). La sección muestra entonces:

   - el modelo construido con revisión declarada;
   - los casos con estado CSI 4 en la corrida aceptada;
   - el vínculo con el mismo EDB analizado;
   - por separado, **revisión de resultados pendiente** y **conformidad normativa no evaluada**.

   El informe añade la clave `evidencia_analisis` y su huella. Sin evidencia, conserva exactamente la forma anterior, y un informe sin esa clave sigue validando. Al exportar, la evidencia exige la misma fuente y se revalida.
2. **Geometría y muros:** cuando se aporta `--geometria`, su validador debe aceptar consistencia y su SHA256 de bytes debe ser idéntico a la referencia de resultados. El conteo proviene del archivo, incluidos sus faltantes explícitos. No se infiere aprobación ni número de pisos habitables a partir del número de niveles geométricos.
3. **Periodos:** filas originales, con caso, dirección, ubicación y segundos.
4. **Derivas:** filas originales, por caso, dirección, ubicación y unidad adimensional `1`.
5. **Cortante basal:** únicamente filas `cortante` cuya ubicación sea exactamente `base`; no se relabelan cortantes de un nivel como basales. Las demás filas se preservan en el JSON original.
6. **Advertencias y reglas:** omisiones, parámetros de fórmula, entradas/valores evaluados, unidades, límites y satisfacción de la regla configurada. No se convierte satisfacción en un juicio global de seguridad.
7. **Sitio:** declaración referencial con fuente o ausencia explícita, bajo las condiciones anteriores.

Un valor `null` se presenta como no disponible con su motivo. Las categorías sin filas no se rellenan con cero. La naturaleza sintética y el tipo de motor real/simulación se muestran por separado: un motor real puede usar datos de prueba sintéticos. El productor y su declaración no quedan autenticados por validar JSON.

## API, revisión propia y vigencia

```python
from draft2model.informe import crear_informe, exportar_informe, aprobar_informe

informe = crear_informe(resultados, reglas, contexto,
                        geometria_archivo=ruta_geometria, corpus=ruta_corpus, citas=citas)
paquete = exportar_informe(informe, carpeta_nueva,
                           geometria_archivo=ruta_geometria, corpus=ruta_corpus)

# Solo después de una revisión documental efectiva y explícita:
revisado = aprobar_informe(informe, revisor_declarado="Responsable que revisó",
                           fecha="2026-10-16", motivo="Revisión documental realizada.")
```

`crear_informe` devuelve una copia en borrador; no hereda la aprobación de geometría, modelo o reglas. `validar_informe` recalcula evaluación/secciones y verifica cifras/huellas. `aprobar_informe` produce una nueva copia con aprobación **documental** propia ligada a la huella del informe; no autentica al revisor ni certifica la estructura. Modificar el contenido invalida esa aprobación.

`exportar_informe` vuelve a comprobar el archivo geométrico y corpus originales; si el informe los contiene, deben aportarse nuevamente. Cambios de fuentes o geometría provocan rechazo. La validación del snapshot no sustituye comprobar los archivos originales al exportar. La CLI genera borradores; la aprobación documental se expone como función explícita para integración posterior.

El HTML escapa textos de entrada; no interpreta HTML aportado por planos, fuentes o contexto. El PDF usa PyMuPDF Story con Unicode español, tamaño A4, márgenes y numeración de páginas; no añade dependencias. Las huellas largas se agrupan visualmente para evitar desbordamiento y se conservan completas en JSON. Límites: 10 MB para contratos de resultados/reglas, 2000 filas de resultados, 5000 evaluaciones, 200 páginas; textos de contexto hasta 20000 caracteres y listas de hasta 1000 entradas.

## Comprobación

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_informe.py -v
```

Las pruebas verifican cifras/contratos equivalentes, ausencia de mutaciones y aprobaciones heredadas, rechazo de alteraciones, fuentes con hash y citas exactas, geometría vinculada, escape HTML, faltantes, cortante solo basal, preservación de original/salida previa y CLI. La comprobación PDF incluye texto Unicode, siete secciones, cifras, pie de página, rasterización y caso de múltiples páginas. Debe añadirse inspección visual del PDF representativo antes de aceptar la presentación; estas comprobaciones documentales no sustituyen la validación de ingeniería y del flujo ETABS real.
# Consulta del historial sin comprobaciones implícitas (306)

La interfaz solicita un inventario de informes con `modo=inventario`: solo enumera candidatos asociados al resultado seleccionado. Las filas muestran «sin comprobar»; el inventario no acredita vigencia, estado documental ni vínculo del análisis y no habilita descarga o aprobación. Seleccionar una versión ejecuta la comprobación completa de sus archivos y fuentes antes de habilitar esas acciones. La descarga y la aprobación conservan su propia revalidación. La API sin ese parámetro mantiene el listado verificado anterior.

El tiempo del inventario no representa el de abrir o descargar un informe. Las comprobaciones completas de geometría y evidencias del caso real siguen siendo costosas.

