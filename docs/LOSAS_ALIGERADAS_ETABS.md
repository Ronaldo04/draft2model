# Losas nervadas y casetonadas explícitas: plan de desarrollo

Corte actualizado181. Configuración0.2; contrato0.1 intacto. Este incremento **no habilita ejecución** ni demuestra representación suficiente del proyecto de referencia. Hay ensayo real de persistencia de propiedades y ejes en dos instancias propias, descrito abajo; no prueba malla ni solver. La propiedad homogénea existente conserva su significado. No se convierte automáticamente una losa aligerada en una maciza.

## Contrato

Secciones con campos exactos existentes `id,tipo,material,dimensiones,fuente`. Tipos nuevos:

- `shell_losa_nervada_v1`: dimensiones exactas `alto_total_m,capa_m,ancho_nervio_superior_m,ancho_nervio_inferior_m,separacion_m,direccion_nervios,angulo_ejes_locales_grados`.
- `shell_losa_casetonada_v1`: dimensiones exactas `alto_total_m,capa_m,ancho_nervio_superior_m,ancho_nervio_inferior_m,separacion_1_m,separacion_2_m,angulo_ejes_locales_grados`.

Longitudes finitas positivas en metros. Capa menor que alto total; cada ancho de nervio menor que cada separación. `direccion_nervios` es entero1/2 (no booleano), eje local al que son paralelos los nervios; la separación nervada se mide perpendicular a ellos. Ángulo finito en[-180,180) grados respecto a ejes por defecto de ETABS; no es automáticamente un azimut global. Waffle usa separaciones de direcciones locales1/2. La fuente y el material se resuelven y revisan por huella, igual que otras secciones. No se infieren propiedades de `papel_geometrico` ni píxeles.

El incremento v1 exige superficies horizontales con normal+Z (contorno antihorario visto desde+Z); no invierte el contorno en silencio. Compara separación con extensión del contorno proyectado en las direcciones locales y alto total con sus extensiones; no valida dimensionamiento estructural ni que exista un número entero de casetones. La conectividad a apoyos y los vértices compartidos conservan sus comprobaciones existentes; no crea barras explícitas ni malla compatible por mera coincidencia visual. Para huecos, nervios interrumpidos o zonas macizas diferenciadas se necesita representar explícitamente su configuración; esta propiedad no los inventa.

Material isótropo lineal declarado: E, Poisson y peso por volumen con fuente. Peso propio deriva de propiedad geométrica/material y multiplicador del patrón existente. La masa desde patrones mantiene los controles heredados para no duplicar peso propio. **No incluye ladrillos, bloques, casetones permanentes, acabados ni agua**: sus acciones deben declararse con fuente en cargas, sin volver a agregar como carga el peso propio estructural ya incluido. No se crea una capa o viga superpuesta para volver a contabilizar el concreto. Cargas uniformes existentes kN/m² por área real, no proyectada.

## API y evidencia

Reflexión de ETABSv1.dll local1.29.0.0 (ETABS21.1.0), sin iniciar ETABS. `tmp/firmas_aligeradas.json` conserva la inspección inicial de nombres ausentes SetRibbed/SetWaffle; los nombres correctos se verifican con `verificar_firmas_dll()`.

- SetSlab(Name,eSlabType.Ribbed=3 o Waffle=4,eShellType explícito,MatProp,Thickness=capa_m,color,notes,GUID). El setter específico posterior determina el alto total y la capa por separado.
- SetSlabRibbed(Name,OverallDepth,SlabThickness,StemWidthTop,StemWidthBot,RibSpacing,RibsParallelTo).
- SetSlabWaffle(Name,OverallDepth,SlabThickness,StemWidthTop,StemWidthBot,RibSpacingDir1,RibSpacingDir2).
- GetSlabRibbed/GetSlabWaffle: mismos parámetros de dimensiones por referencia.
- SetLocalAxes(Name,Ang,eItemType.Objects); GetLocalAxes(Name,ref Ang,ref Advanced).

Todos retornan Int32 y solo cero se acepta. Dimensiones Double; RibsParallelTo Int32. La lista Python y la lista PowerShell se amplían conjuntamente. Formulación explícita `tipo_shell_losa` sigue siendo obligatoria.

Después de crear cada objeto se fija ángulo local y se relee ángulo y Advanced=false. Después se comprueba GetSlab: material, espesor, **tipo de losa y formulación**; los enumerados nuevos se comparan por tipo/nombre/valor. GetSlabRibbed/Waffle compara todos los parámetros. Comparaciones numéricas relativas1e-12 son computacionales, no tolerancias de ingeniería. Un retorno incorrecto, tipo de losa alterado o dimensión releída distinta interrumpe antes de guardar. La traza conserva sección completa, fuente, unidades y peso volumétrico declarado. Los getter tras asignación son transporte; no sustituyen la lectura independiente del EDB guardado/reabierto.

### Ensayo real181: corrección de Thickness

`scripts/ensayar_aligerados_etabs.ps1` construyó un modelo nuevo sintético con ambos tipos, guardó y cerró la instancia; una segunda instancia propia reabrió el EDB y leyó sin guardar ni cambiar unidades. ETABS21.1/DLL1.29 devolvió **GetSlab.Thickness=0.05m (capa), no OverallDepth=0.25m**. En la reapertura N_mm_C devolvió50mm y250mm respectivamente; nervada conservó separación600mm y dirección1; casetonada600mm y699.9999999999999mm. Ambos ejes conservaron30° y Advanced=false. Hash del EDB idéntico antes/después de reabrir; ambos cierres confirmados, sin solver.

El compilador y sus getters ahora usan `capa_m` para Thickness; el lector aplica el efecto final de SetSlabRibbed/Waffle incluso cuando SetSlab de un plan anterior pasó el alto total. El doble de transporte se corrigió para reproducir este efecto. `tests/fixtures/aligerados_etabs21_181.json` conserva las lecturas nativas y hash de procedencia: evita que un doble construido únicamente desde la expectativa vuelva a ocultar el fallo. La evidencia completa está en `seguimiento/ALIGERADOS_REALES_181.json` y `tmp/aligerados181/registro.json`.

Fuentes oficiales CSI contrastadas con la DLL instalada:

- [GetSlabRibbed y ejemplo SetSlabRibbed](https://docs.csiamerica.com/help-files/etabs-api-2016/html/7f73f83f-0106-87ab-a394-905492a42f64.htm).
- [SetSlabRibbed](https://docs.csiamerica.com/help-files/etabs-api-2015/html/5a543d88-c979-2c24-a8cc-e19f4a3093f4.htm).
- [Convención ejes locales shell](https://docs.csiamerica.com/help-files/etabs/Menus/Assign/Shell/Local_Axes_Shell_Objects.htm).

Se localizó el manual CHM instalado; no se descompiló ni se atribuye lectura de su contenido. Las páginas oficiales antiguas documentan semántica; las firmas aceptadas proceden de la DLL local actual.

## Pruebas y límites

`tests/test_losas_aligeradas.py`: configuraciones y planes sintéticos en las dos direcciones/tipos, parámetros exactos, trazabilidad, faltantes/desconocidos/valores no finitos/unidades/fuente/espesores/separaciones/dirección/inclinación inválidos. Ensamblado falso con persistencia, ejecutado mediante script PowerShell real: asignación y relectura, retorno fallido, relectura dimensional alterada y tipo incorrecto. El doble no acredita el solver ni un EDB real. Prueba de firmas por reflexión, sin motor.

Ejecutar con TEMP y TMP en carpeta local tmp:

```powershell
$env:TEMP=(Resolve-Path tmp).Path; $env:TMP=$env:TEMP
.venv/Scripts/python.exe -m unittest tests.test_losas_aligeradas
```

Pendientes materiales: lector independiente de estas propiedades tras reapertura, verificación real en copia ETABS, rigidez/peso/mallado del sistema elegido, piezas de relleno cuando correspondan, regiones especiales y revisión física del caso de referencia. No se retiran BLOQUEO_SUPERFICIES ni BLOQUEO_INTEGRACION. La comparación manual ETABS permanece diferida por el usuario.

## Evidencia de entrega

- Nuevas cuatro pruebas completas: `tmp/losas_entrega_final.log`,4OK22.032s, código0, sin omisiones. Tras reforzar el rechazo de referencias no textuales,3pruebas puras OK1.251s en `tmp/losas_puro_entrega.log`.
- Regresión específica del script homogéneo tras comparar enums: `tmp/losas_regresion_script_final.log`,2OK12.495s, sin omisiones.
- Regresión de configuración/planes0.1/superficies: corrida `tmp/losas_final.log` tuvo42pruebas,40heredadas sin fallo y2nuevas fallidas por validación de enums; esos2fallos se corrigieron y están incluidos en las4nuevas verdes. No se presenta aquella corrida completa como verde.
- Primeras corridas conservadas (`losas_primer.log`, `losas_pruebas.log`, `losas_validacion.log`): errores de expectativa, ejecución de PowerShell restringida y codificación Windows, corregidos. La codificación UTF8 actual fue reparada; no se borran esas evidencias.
- `tmp/firmas_losas_final.json`:68firmas reflejadas, cero diferencias. La prueba nueva compara lista blanca PowerShell/Python y enum Slab0,Ribbed3,Waffle4.
- El test ajeno `tests/test_operaciones_superficies.py:232` conserva una expectativa histórica de catálogo Slab0 exclusivamente; Codex autorizó actualizarla tras revisar esta entrega. No se editó el test ajeno.
