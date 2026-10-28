# Precisión y cercanía conservadora a fronteras

`draft2model.sitio.consultar_sitio` utiliza ahora `precision_m` para evitar una clasificación puntual «dentro» o «sin cobertura» cuando la separación al borde puede estar dentro de la precisión declarada. Incluye bordes exteriores, vértices, huecos y fronteras de zonas solapadas. Es un cribado geométrico local sobre una capa revisada; no genera parámetros normativos, perfil de suelo ni capacidad portante.

## Compatibilidad y significado

Se conservan contrato `draft2model.sitio` versión `0.1.0`, campos y estados existentes. **No se añade un estado nuevo ni campos al objeto público.**

| Estado | Significado tras esta ampliación |
| --- | --- |
| `limite` | Borde o franja de incertidumbre conservadora compatible con `precision_m`; también puede corresponder a un punto exterior o dentro de un hueco próximo al borde. No confirma pertenencia a la zona. |
| `dentro` | Pertenencia puntual a una zona sin que el cribado encuentre frontera próxima con la precisión declarada; no significa ubicación segura, estudio de suelos o certeza territorial. |
| `ambiguo` | Pertenencia puntual a varias zonas, lejos de sus fronteras según el cribado. |
| `sin_cobertura` | Fuera de las zonas y de sus franjas de proximidad. No se asigna una zona por cercanía. |

`limite` tiene prioridad sobre `ambiguo`, igual que antes. `zonas` puede incluir una zona con `posicion:limite` aunque la coordenada puntual esté fuera de ella: esa entrada identifica una frontera que impide clasificación concluyente, no una asignación territorial. `aviso` explica la distinción. Fuente, fecha, ubicación, precisión, naturaleza sintética y huellas se preservan. `parametros_geotecnicos` y `capacidad_portante` siguen siendo null.

Los consumidores actuales aceptan esos estados y campos; esta tarea no modifica HTTP, UI, contexto ni informe. El coordinador debe contrastar la nueva semántica visible. Los derivados reconstruidos con la función actual pueden diferir de snapshots previos de sitio: revalidar/regenerar sus dependientes explícitamente; no reparar huellas ni actualizar citas/aprobaciones silenciosamente.

## Dominio geográfico y precisión admitidos

- Consulta y vértices entre latitudes -60 y +60 grados, inclusive.
- Capa local cuya extensión total no exceda 10 grados de longitud ni de latitud. Los límites son de aplicación computacional, no umbrales normativos.
- Sin cruces del antimeridiano; se rechaza también una consulta que necesite otra rama de longitud respecto de algún vértice. No se aplica un wrap implícito a la capa.
- `0 < precision_m <= 50000`; se rechazan booleanos, no finitos y valores no representables.
- GeoJSON Polygon, segmentos lineales en longitud/latitud y topología previamente revisada. Se conservan las restricciones existentes: no es un validador completo de cartografía arbitraria.

La consulta puede estar lejos de la capa: se conserva, en particular, la consulta `(0,0)` utilizada por el servicio de contexto para ejercitar el validador de una capa de Lima. Solo la extensión de la **capa** está limitada a 10 grados; no se exige que el punto esté en su bounding box. Latitudes altas/antimeridiano o capas mayores requieren otro método revisado, no una aproximación silenciosa.

`precision_m` se emplea como radio declarado de cribado, sin convertir una exactitud de origen desconocido en confianza estadística ni absorber incertidumbre de ubicación no documentada. Una clasificación fuera de la franja no certifica la calidad de los datos de entrada.

## Método y fundamento

Las constantes del elipsoide WGS84 `a=6378137 m` y `1/f=298.257223563` proceden de la [definición primaria de NGA](https://earth-info.nga.mil/?action=wgs84&dir=wgs84). La [IOGP Guidance Note 7-2, edición septiembre 2019](https://www.iogp.org/wp-content/uploads/2019/09/373-07-02.pdf) documenta coordenadas elipsoidales, radios de curvatura y límites de aplicación de proyecciones. Se consultaron únicamente fuentes primarias para ese fundamento; no se incorpora cartografía ni una decisión normativa.

La siguiente **derivación conservadora pertenece a esta implementación**; no se presenta como una proyección oficial EPSG ni como un solucionador de distancia geodésica exacta:

1. `e²=f(2-f)` y `M_min=a(1-e²)` es una cota inferior del radio de curvatura meridiano WGS84. El radio del primer vertical satisface `N >= a`.
2. Para una trayectoria de longitud no mayor que `r`, el cambio absoluto de latitud no supera `r/M_min` radianes. Tomamos la banda `phi_max=abs(phi_consulta)+r/M_min`.
3. En esa banda, la métrica elipsoidal tiene cotas inferiores `M_min` para latitud y `a*cos(phi_max)` para longitud. Ambas coordenadas angulares se convierten primero a radianes. La escala longitudinal depende de la latitud y del radio; **no se usa una cantidad uniforme de metros por grado en EPSG4326**.
4. Se trasladan los segmentos respecto del punto consultado y se escalan con esas dos cotas. La distancia euclídea mínima al segmento en ese plano es una cota inferior para detectar cualquier frontera alcanzable por una trayectoria elipsoidal de longitud `<=r`.
5. Una distancia de cribado `<=r` marca `limite`. El radio empleado es `precision_m + 0.000001 m`, con comparación inclusiva: ese micrómetro es resguardo de redondeo, no precisión física prometida.

La contracción puede marcar algunos puntos cuyo borde real esté algo más lejos del radio: es un positivo conservador deliberado. No se publica esa cota como una distancia medida. El dominio local y la ausencia de wraps hacen explícita la rama de coordenadas; la latitud/radio máximos mantienen la banda lejos del polo. No se infiere seguridad ni valor sísmico de un resultado geométrico.

## Comprobación focal y regresión

```powershell
.\.venv\Scripts\python.exe -B -m unittest tests.test_sitio_precision tests.test_sitio -v
```

Las pruebas nuevas usan capas sintéticas y comprueban interior/fuera lejanos, ambos lados próximos, vértices con distancia radial, huecos, solape, variación de escala con latitud, umbral inclusivo en ecuador, rechazo de dominios/precisiones no admitidos, preservación del archivo y del esquema público. La referencia analítica del umbral ecuatorial usa `a*delta_longitud`, sin copiar los helpers del algoritmo. Se repiten las pruebas existentes de sitio sin debilitarlas; no se abre un proveedor ni ETABS.

Resultado de la única pasada focal del 18 de octubre de 2026: **16 pruebas correctas en 0.253 s, sin omisiones** (12 nuevas de precisión y 4 regresiones existentes). No se ejecutó suite completa ni integración HTTP/UI; la compatibilidad conservada de campos/estados requiere contraste del coordinador con sus consumidores.
