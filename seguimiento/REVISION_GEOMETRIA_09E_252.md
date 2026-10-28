# Revisión focal de geometría 09E - 252

2026-10-22. Lectura y álgebra sobre copias congeladas; sin importar/ejecutar guiones del piloto, sin generar malla, plan ni modelo, sin API/ETABS/GUI/red. No es aprobación ni rechazo global del proyecto. No repite las auditorías248: contrasta su traslado a la representación09E.

## Dictamen

**El ajuste de tanque para obtener cero nodos colgantes cambia su separación entre apoyos y la huella de la caja; no es solo una traslación.** El cambio está parcialmente declarado mediante coordenadas ajustadas y la frase de INFORME09§8, por lo que no es oculto. Sin embargo falta una transformación fuente→modelo cuantificada o conexión excéntrica que preserve la geometría física: se sustituyen directamente coordenadas medidas por líneas conformes. Cero colgantes no demuestra que esa sustitución sea fiel a la fuente.

La cisterna conserva, salvo redondeo milimétrico, los claros y altura interior de248. C6/PL10 conservan las discrepancias/hipótesis indicadas. **No todo el modelo queda invalidado por una aproximación:** el tanque sigue siendo una alternativa de modelación pendiente, con un cambio específico que debe justificarse/corregirse; los escenarios de agua aún constan preparados y no aplicados.

## Congelación e identidad

Carpeta `tmp/revision_geo09e_252/`, con rutas relativas originales y `manifest.json`: fuentes09C, INFORME09, MARCADOR09E, inventario/muros, auditorías de depósitos y C6/PL10, geometría generada y versiones privadas3905c919, padre7c84de15 y referencia posterior b145a29d. Solo se copiaron archivos geométricos/declarativos concretos, sin credenciales. Se conserva también E03 original y un único recorte focal de sus apoyos nuevos.

Coinciden con el MARCADOR09E: `geometria_09c.py`, `GEOMETRIA_09C.json`, `DEPOSITOS_09C.json`, `INFORME_09.md` y geometría privada3905c919. SHA256 de esta última: `249401dbcdd7a92c2f14bf145e211961c7d90d783fb510cb96f68407ab7b4c9d`, idéntica a la copia generada congelada.

**Límite temporal:** al congelar, `configuracion_09c.py`, `CONFIGURACION_CASO_09C.json` y `tmp/ruta201/configuracion09c.json` ya diferían de los hashes publicados09E; el script actual incluye rama TRANSPORTE09T. Sus bytes quedaron registrados, no atribuidos retroactivamente a09E. El informe09C actual dice validación pendiente, no una repetición del recibo144.3s publicado. No se ejecutó para regenerar esa evidencia ni se juzga aquí el trabajo09T. Los contrastes de caras/normales usan la geometría09E inmutable y el DEPOSITOS09C que sí coincide con el marcador; espesores de configuración se leen como confirmación del contrato declarado, con esta salvedad.

## 1. Tanque: ajuste geométrico no equivalente a conexión explícita

Referencias congeladas: `geometria_09c.py:318–328`; `DEPOSITOS_09C.json.tanque`; `INFORME_09.md§8`.

- Fuente declarada en DEPOSITOS: «NACE C-2» x≈11.315/13.59, y≈3.09/5.02, más C2 existente del eje2.
- Modelo: x=[11.335,13.748], y=[3.118,5.018]. Se genera una caja con esas líneas y se recolocan **también los cuatro frames** en sus esquinas; no se conservan por separado centros originales y centros de conexión.
- Frente a los números fuente del propio DEPOSITOS: desplazamientos X de +.020 y +.158m; la luz entre líneas cambia2.275→2.413m (+.138m). El lado derecho no se explica por el ajuste de2cm al eje C2 izquierdo.
- Contraste focal independiente con E03: apoyos superiores NACE C2 en regiones visuales `[1248.24,603.56,1280.04,615.44]` y `[1428.96,603.56,1460.76,615.44]`pt. El primero se reconstruye de cierres verticales/plano rayado; el segundo es un quad cerrado. Página1, sin rotación. Distancia de centros180.72pt. Con escala .012595m/pt documentada en AUDITORIA_C6_PL10_248, separación≈**2.2761684m**; modelo**2.413m**, diferencia**.1368316m (+6.01%)**. Este contraste de separación no depende del origen XY. El registro por lámina/escala definitiva todavía debe quedar explícito: los números absolutos citados en DEPOSITOS tienen unos2cm de diferencia respecto a esta calibración, sin eliminar el cambio de luz.
- E03 original SHA256 `fb4284e82b7a55f4faeb4e9917269b37e94336c0788562873385e7e21c67a134`; `E03_apoyos_focal.png` renderiza `[1170,570,1490,800]`pt e incluye las tres etiquetas NACE y C2 existente. No se reauditaron todas las láminas.

El procedimiento asigna procedencia `tipo=plano` a los vértices/superficies y describe «líneas de modelación», pero no guarda el vector individual de alteración ni la incertidumbre/razón independiente para cambiar la distancia entre apoyos. Tampoco se localiza en los datos congelados una inserción/desplazamiento de los cuatro frames nuevos: conectan nudos de techo y esquina de fondo ajustados por identidad. La configuración actual tiene inserciones para C1; ninguna para COL-0/1/2/3-P1.

Hay además un residuo documental: `geometria.faltantes` describe apoyosE03 «2.58×1.90 entre ejes», mientras las líneas almacenadas dan2.413×1.900 y las coordenadas fuente citadas en DEPOSITOS dan2.275×1.930. Ninguna de esas frases debe usarse indistintamente como dimensión fuente confirmada.

**Acción concreta:** conservar los centros/contorno de fuente y cuantificar cada desplazamiento; decidir entre partición del techo en posiciones medidas o una conexión/offset físicamente justificada. Separar huella de recipiente, apoyo medido y nudo de modelo. No mover todo para hacer desaparecer colgantes y luego presentar la nueva dimensión como lectura del plano. No es necesario desechar el resto del edificio para resolver este punto.

## 2. Caras físicas, cotas y volúmenes

Los shells se dibujan en planos medios. Los siguientes claros se obtienen restando semiespesores: no son nuevas dimensiones medidas ni niveles operativos aprobados.

| Cantidad | Cisterna09E | Tanque alternativaE03-apoyos09E |
| --- | ---: | ---: |
| Líneas medias X(m) |14.938…17.115|11.335…13.748|
| Líneas medias Y(m) |2.449…4.798|3.118…5.018|
| Planos medios fondo/tapaZ(m) |−2.500 / −.105|12.500 /14.250|
| Espesores fondo/tapa(m) |.20/.15|.20/.20|
| Caras interiores fondo/tapaZ(m) |−2.400 /−.180|12.600 /14.150|
| Claro interiorXYZ(m) |2.002×2.149×2.220|2.213×1.700×1.550|
| Nivel libre de escenario(m) |−.180|13.700|
| Lámina sobre cara superior del fondo(m) |2.220|1.100|
| Volumen de ese escenario sobre claro(m³) |9.55110156|4.13831|

**Cisterna:** claro2.002×2.149, próximo al2.00×2.15 de248; volumen9.5511 frente9.546m³ ilustrativo, diferencia≈.0051m³ de redondeo/vectorización (≈.053%). No se identifica aquí un error material de dimensión. La tapa conserva un acceso .55×.55 por omisión de la celda central correspondiente; la segunda dimensión es representación derivada, como ya se advertía en248. La hipótesis NFC−2.65→solado.05→fondo−2.60/−2.40 y tapa−.18/−.03 está declarada. Patines/fundación no se modelan y la subestructura independiente/base empotrada en plano medio−2.50 es una hipótesis, no apoyo real verificado.

**Tanque:** mantiene interior1.55 y cadena de caras compatible con usar baseN4+10.40: intradós fondo12.40, cara superior12.60, intradós tapa14.15 y cara superior14.35. Es la cadenaE03 desplazada+.05m de datum, declarada; faltan resalto y cierre de diferencia respectoA03+14.60. Muros.20 son hipótesis explícita. La plantaA03≈2.82×3.92 queda como alternativa no modelada; no se debe mezclar esa superficie con el volumen de la alternativaE03-apoyos.

Los frames nuevos van deZ10.40 a12.50, longitud nodal2.10m, mientras H-DEPOSITOS actual dice apoyos hasta12.40. Puede explicarse por la llegada al plano medio del fondo de.20, pero debe distinguirse longitud física2.00 y conexión al plano medio (+.10) de una columna física2.10. El archivo no contiene ese offset como transformación individual. No se afirma un fallo de solver: no se ejecutó ninguno.

## 3. Normal correcta, pero presión preparada sobre plano medio

El orden de vértices y `sentido_normal` de DEPOSITOS fueron contrastados por producto cruzado local, sin usar calculadores del producto. **Ambos depósitos:** fondos hacia−Z, muros x0/x1 hacia−X/+X y y0/y1 hacia−Y/+Y. No se encontró error de signo.

Sí existe una inconsistencia geométrica reproducible si se aplica sin corrección la presión declarada a esas superficies: la declaración selecciona fondos y muros en **plano medio**, con el nivel libre físico usado en el relato. La fórmula p=gamma(h−z) obtiene .10m extra de lámina al evaluar el fondo en su plano medio y la superficie del fondo llega a ejes de muro, no a caras interiores. Sin transporte/offset equivalente se calcula otra resultante que la del volumen claro.

| Control algebraico, gamma10 | Cisterna | Tanque |
| --- | ---: | ---: |
| Peso de claro de escenario(kN) |95.5110156|41.3831|
| gamma×área del fondo medio×(nivel−Zmedio)(kN) |118.6395336|55.0164|
| Exceso respecto al claro |24.21555%|32.94412%|

Esto **no es una reejecución de masa/ledger249 ni resultado de malla/ETABS**: solo dimensiones, caras seleccionadas y fórmula publicada. No contradice que los escenarios figuren no aplicados. Localiza lo que debe resolverse antes de trasladarlos: cara mojada e integración/transporte conservativo a shell medio, preservando fuerza y momento, sin sumar además otro peso de contenido. No basta corregir el signo (ya es correcto) ni imponer factor1. El agente de masa revisa su alcance por separado.

## 4. C6 y PL10: representación frente a248

- **C6:** centro(15.388,4.798), lado largo dibujado enX; sección.20×.75, discrepancia con cuadro.15×.75 conservada; tres framesN0–N3 sin prolongar aN4. Los cuatro nudos del eje no pertenecen a ninguna superficie; solo baseN0 empotrada. Por tanto representa un voladizo independiente provisional, **no** una conexión ya resuelta de escalera/cisterna/edificio. Está declarado en H-C6/faltantes, coherente con el límite de248. No se considera resuelto el apoyo real ni el extremo vertical por añadir el frame.
- **PL10:** dos superficies con X15.043…20.017, Y.050/9.947, Z−.05…2.35 y espesor.10. Respeta los contornos y coronación derivada248; f'c175 conservado. Base empotrada/independencia son hipótesis declaradas. No se extruyen aN4 ni se pegan aN1 por redondeo. No se halló aquí una alteración geométrica no declarada equivalente a la del tanque.
- «0 colgantes» es una comprobación local de vértices sobre aristas de superficies en el guion; no comprueba fidelidad a fuente, toda conectividad física de frames, apoyo del tanque o continuidad de C6. No reemplaza esas verificaciones.

## Reproducción y cierre de alcance

| Prioridad | Corrección propuesta | Evidencia que debe producir |
| --- | --- | --- |
| P1, antes de integrar tanque | Separar centros fuente/nudos de modelo; resolver cambio de luz+.137m y conservar huella física, mediante partición o conexión explícita justificada. | Tabla fuente→modelo por apoyo, incertidumbre de registro y transformación/offset por elemento. Cero colgantes es solo una comprobación adicional. |
| P1, antes de aplicar agua | Definir cara mojada y transferir presión conservando resultante/momento al shell medio. | Coincidencia de gammaV del claro y fuerza vertical, sin carga de peso duplicada; no basta factor de masa ni normales correctas. |
| P2, antes de afirmar geometría completa | Resolver longitud física de apoyos frente a plano medio y conexiones de C6/cisterna/escalera. | Cotas/encuentros declarados, sin inferir conexión por cercanía. Las idealizaciones actuales se pueden conservar como alternativas. |
| P2, antes de congelar siguiente entrega | Limpiar dimensiones textuales2.58/2.275/2.413 y emitir nuevo recibo para configuración posterior. | Un único manifiesto versionado coherente; no reusar hashes/validación09E para bytes09T. |

`python -B tmp/revision_geo09e_252/contraste_local.py` lee únicamente las copias y reproduce claros, volúmenes condicionales, comparación de fórmula en planos medios, normal por host y separación de apoyos; todas sus aserciones pasan. No importa módulos del proyecto ni ejecuta geometria_09c/configuracion_09c. La lectura focalPDF solo obtuvo vectores/render del área de apoyos, sin repetir248.

Los hallazgos concisos están en `seguimiento/REVISION_GEOMETRIA_09E_252.json`. Requieren revisar el ajuste individual del tanque y la cara de aplicación de presión antes de integración; los datos cisterna/C6/PL10 y las alternativas explícitas siguen siendo utilizables con sus hipótesis y faltantes. No se otorga aprobación de modelo ni se interpreta aproximación como invalidez de todo el proyecto.
