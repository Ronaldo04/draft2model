# Resolución focal de escalera - 255

2026-10-22. Se reutilizan AUDITORIA_ESCALERA_248, AUDITORIA_C6_PL10_248, sus recortes y palabras extraídas. **No se abrió nuevamente ningún PDF**, ni producto, malla, ETABS, API/red o GUI. Salidas limitadas a este informe/JSON y `tmp/escalera_resolucion_255/`. No se otorga aprobación ni se convierte una hipótesis en hecho.

## Resultado

Los niveles **0/2.60/5.20/7.80/10.40 m ya están confirmados por el usuario** en DECISION_USUARIO_246. Cada entrepiso tiene por tanto2.60m; deja de ser faltante la altura total. Eso no fija número de contrahuellas, cotas de descansos o conexión de cada rampa.

La U del último entrepiso es **compatible geométricamente** con4+8+4 contrahuellas de.1625m y huellas.25, pero esa es una reconstrucción condicionada: A03 imprime15 números(50–64), no16. Requiere interpretar una frontera de arranque sin número como49. No hay base para copiar automáticamente ese reparto al primer piso recto ni a todos los intermedios.

## Evidencia reutilizada y estados

- **Confirmado por usuario:** niveles, fuente DECISION_USUARIO_246, sin aprobación de diseño.
- **Leído/acotado en plano:** trazado, etiquetas y cotas impresas; no equivale a comprobar obra.
- **Derivado:** aritmética o registro métrico sobre ese dibujo, con convención indicada.
- **Condicional:** depende del significado de las etiquetas/arranque o de una continuidad no acotada.
- **Conflicto condicionado:** dos lecturas incompatibles bajo una convención específica; no se declara que todo el plano sea erróneo.

Localizadores página1, bbox visualpt de248: A01/S1 `[1478.1,488.4,2002.6,976.7]`; A02/S2 y A03/S3 `[1525.8,488.4,1907.2,943.0]`; E02/S4 detalle `[2123.1,953.6,2999.3,1835.7]`; E02/S5 planta `[1415.4,1454.2,1752.4,1859.5]`; E02/S8 cortes `[2123.1,155.0,3066.7,762.9]`. No mezclar texto nativo sin rotar con bbox visuales.

SHA256 originales, conservados en el manifiesto248: A01 `1f2e8d9c2507cc85bbcd6d6cc9fc217baf4d272c6620417c1985eeb3d4b8be54`; A02 `f63d63ce7674c21b3437145cfde2f6ab66abe814c445c5c65873db99067b87bf`; A03 `ead656045a3c95739e2bd7cab3c5daddb6d1e42ebaa7aaf9afb6c34be07dce4a`; E02 `d655e6c5f2c8998a2049b300b83a65a62962c5de03a622bfd9978fd4a8f074fa`.

## Tabla por entrepiso

Las cotas de descanso «no definidas» no se sustituyen por media altura1.30m. El detalleE02 presenta dos esquemas TRAMO1/TRAMO2, sin asignación inequívoca a los tres recorridos de la U ni a cada piso.

| Entrepiso | Orden y cantidad que puede fijarse | Descansos/cotas | Espesores utilizables | Apoyos y conexión |
| --- | --- | --- | --- | --- |
| **0→2.60** | A01 muestra arranque recto1–9 hasta corte; A02 representa la llegada recta1–15. La cantidad total de contrahuellas depende de si la llegada agrega la16ª o si15 es ya el último desnivel. No se completa el conteo desde la porción cortadaA01. | Extremos confirmados0/2.60. No aparece un descanso intermedio claramente acotado para este recto; no inventarlo. Si15 desniveles: r=.173333m; si16: r=.1625m. | GargantaE02 .15m como detalle típico leído; no asignación de sección a cada extremo todavía. Horizontal .20m solo donde lo acotaS4. | Inicio y llegada al hall/franja juntoH reconocibles en planta; apoyo inicial a cimentación y nudo final exactos no cerrados por el detalle. No se deriva empotramiento. |
| **2.60→5.20** | A02 es planta típica de2.º/3.º/4.º: U visible con salida superior16–19, exterior20–22 y continuación cortada. Se fija orden de recorridos superior→exterior→inferior, **no** total de risers por este piso. | Extremos confirmados2.60/5.20. Dos giros/descansos de laU reconocibles en planta; Z pendiente. Si se ensayara4+8+4:3.25/4.55, exclusivamente candidato. | .15m de garganta como detalle típico; ancho1.20 y huella.25 acotados en laU. .20m horizontal local no generalizado. | Franja de llegada juntoH/C3 y proximidad aC6 en ojo; unión del tramo exterior aC6 no especificada por cota/conectividad. Llamadas2-2/3-3 no bastan para fijar cada nodo. |
| **5.20→7.80** | Misma tipicidad de plantaA02; no existe numeración independiente legible de este entrepiso en estos insumos. Reutilizar trazado proyectado no prueba igual conteo que el piso anterior. | Extremos confirmados5.20/7.80. Z de descansos pendiente. Bajo candidato4+8+4:5.85/7.15, sin asignación real. | Mismos datos del detalle típico, con límites anteriores. | C6 aparece en plantasE02, pero sus extremos verticales/contactos no están acotados. No conectar por coincidencia deXY o por «nivel típico». |
| **7.80→10.40** | A03 muestra50–52 superior,53–60 exterior,61–64 inferior. Completando el borde inicial no rotulado como49, resulta candidato4+8+4. **Los16 no están impresos como conteo.** | Extremos confirmados7.80/10.40. Candidato: primer descanso8.45, segundo9.75. Sin la interpretación del arranque49, esas cotas siguen pendientes. | .15m de garganta típico; ancho1.20/huella.25 deA03. Polígonos de giros compatibles con1.20×1.20, derivados de las cadenas. | A03 llega al techo; E03 no prolonga la escalera exterior. C6 no aparece en la plantaE03; no inventar C6 hasta estos descansos. Conectar afranjaH/techo requiere identificar encuentros de detalle, no prolongar columna automáticamente. |

## Comprobación geométrica de16×.1625 y huellas.25

Para un tramo recto entre dos planos horizontales, n contrahuellas suele producir n−1 intervalos de huella entre sus líneas extremas. Esta es la convención de la reconstrucción siguiente; las etiquetas del plano por sí solas no la certifican.

### Última U: reconstrucción local que sí cabe en las cotas

Con origen local sobre la llegada superior junto al edificio; u hacia la franja exterior y v hacia la llegada inferior:

- Primer recorrido: **4 contrahuellas**,3 intervalos×.25=.75m. Se completa la sucesión como49(no impreso),50,51,52. Cota candidata tras4r:7.80+.65=**8.45**.
- Primer descanso: cuadrado candidato u=.75…1.95, v=0…1.20, cota8.45.
- Recorrido exterior: **8 contrahuellas**,7 intervalos×.25=1.75m; etiquetas53–60. Cota candidata tras12r:7.80+1.95=**9.75**.
- Segundo descanso: u=.75…1.95, v=2.95…4.15, cota9.75.
- Recorrido inferior: **4 contrahuellas**,3 intervalos×.25=.75m en retorno;61–64. Llega a**10.40**.
- Envolvente local candidata: **1.95×4.15m**; ojo u=0….75, v=1.20…2.95, esto es.75×1.75. No se amplía el ojo para resolver una columna ni se rellena la U como hueco vacío.

Esta construcción es dimensionalmente coherente con las cotas impresas y niveles confirmados; no prueba la posiciónZ de cada superficie real, la convención de peldaños, el perfil exacto de garganta ni su apoyo. Las coordenadas globales de DEPOSITOS09C (por ejemplo x≈14.94, y≈3.00 para el origen y las franjas5.99/7.17) son registro/modelación aproximados, **no** cotas independientes que sustituyan las cadenas. No ajustar las cotas locales para hacerlos idénticos sin registrar la transformación.

### Por qué no confirma16 idénticas en los cuatro entrepisos

1. **A03 tiene15 números impresos.**50–52=3,53–60=8,61–64=4:3+8+4=15. La inferencia16 requiere el límite inicial49 sin rótulo; «suma literal16» sería un error de conteo.
2. A02 yA03 sitúan exactamente en las mismas coordenadasX de extracción las parejas17↔50,18↔51,19↔52,20↔53,21↔54,22↔55. La diferencia es **33**, no32. Si ambas numeraciones fueran acumuladas, de la misma fase de tramo y separadas por dos entrepisos de16, deberían diferir32. Por tanto **esas tres premisas juntas** no son compatibles; no se decide por cuenta propia cuál falla. Puede ser convención/omisión de llegada, numeración de planta típica o reparto real distinto.
3. El primer rectoA02 contiene15 marcas numeradas y14 intervalos entre ellas; si su paso se toma.25, representan**3.50m** entre marcas extremas. Una escalera recta de16 contrahuellas con15 huellas a.25 desarrolla**3.75m**: requiere identificar la huella/llegada adicional, no contarla de oficio. La cadena.25 explícita pertenece a laU; su aplicación al primer recto es una comprobación de compatibilidad, no una nueva cota impresa.
4. Los niveles confirmados y una numeración final64 no demuestran4×16. Por ejemplo,15+16+17+16=64 también cierra aritméticamente; contrahuellas correspondientes serían.173333/.1625/.152941/.1625m. Es **contraejemplo de no unicidad**, no propuesta de escalera real ni reparto a modelar. Las huellas/descansos de unaU con17 tendrían que comprobarse y no se inventan a partir de esa suma.

## Apoyos: qué se puede localizar sin inventar un enlace

De248 se conserva C6 de planta, centro derivado≈(15.388,4.798)m, huella larga enX≈.748m y espesor dibujado≈.20 frente cuadro.15; C3 delimita los bordes juntoH y la franja rayada de losa contigua. La escalera pasa por fuera deH y C6 aparece en la zona del ojo/adyacente al borde interior del recorrido exterior. **Una proyección en planta no asigna la altura de contacto ni demuestra unión de todas las rampas a C6.**

E02 detalla encuentro izquierdo3-3 (TRAMO2:3-3 ó10-10), derecho2-2 con cota local.50; el corte general2-2 admite.50 ó.40. No se localizó10-10 en248. No adjudicar automáticamente estos cortes a «descanso1/descanso2/C6» solo por ser un esquema típico. El número de gradas dibujado esquemáticamente en el detalle no es un conteo entre niveles.

En09E C6 es una idealizaciónN0–N3 como voladizo independiente, no un apoyo ya resuelto de escalera. Si se adoptara esa terminación7.80, no alcanzaría por sí misma los descansos candidatos8.45/9.75 del último tramo; haría falta una conexión físicamente definida por otro elemento. Tampoco se prolonga aN4 para cerrar ese punto sin fuente. Esta observación no decide la longitud física real de C6.

## Qué queda listo y qué sigue irreducible

**Listo para representación con procedencia:** cuatro pares de cotas extremas y desnivel2.60; trazado distinto del primer recto frenteU superior; ancho/huella acotados deU; garganta típica.15; posición en planta de ojo/giros/franjaH/C6 y los encuentros de detalle como referencias. Puede conservarse una entidad escalera con este trazado, separada del ojo vacío.

**Pendiente real:** convención de numeración y conteo de desniveles en la llegada del primer piso; reparto independiente de los dos intermedios; aceptación/confirmación de49 en el arranque deA03 y cotas de descansos; correspondencia3D de apoyos/encuentros. La confirmación de niveles elimina una incógnita importante, pero no autoriza inventar las otras. No se calculó peso ni masa para este encargo.

## Una sola pregunta concreta propuesta para el usuario

**En la escalera del primer entrepiso0→+2.60m, los números1–15 deA02, ¿son15 huellas y la llegada al piso forma la16.ª contrahuella, o son ya15 contrahuellas en total?**

- **A:**16 contrahuellas totales; r=16.25cm y15 huellas antes de la llegada. Identificar la llegada que no está diferenciada por su número en el recorte.
- **B:**15 contrahuellas totales; r≈17.333cm y14 intervalos de huella entre sus extremos. No extrapolar r al resto.
- **C:**No hay un conteo real verificado; conservar pendiente y consultar **solo ese detalle/conteo de escalera**, sin solicitar nuevamente el juego completo de planos.

Evidencia para mostrar junto a la pregunta: recorteA02 (1–15) yA01 (corte tras1–9), ya copiados bajo `tmp/escalera_resolucion_255/tmp/auditoria_escalera_248/`. La respuesta reduce la ambigüedad concreta del primer tramo; **no aprueba**4+8+4 en todos los pisos ni los empotramientos/conexiones. El últimoA03 puede mostrarse como contraste si se explica que49 no está rotulado.

## Reproducción

`python -B tmp/escalera_resolucion_255/contraste_conteos.py` usa únicamente las palabras extraídas248 y aritmética racional: comprueba15 etiquetasA03, las seis parejas de posiciones con diferencia33, el cierre condicional4+8+4 y cotas8.45/9.75/10.40. Aserciones OK. Es una comprobación de lectura/compatibilidad, no prueba de geometría real ni de modelo.

El JSON conciso está en `seguimiento/RESOLUCION_ESCALERA_255.json`; manifiesto y copias reutilizadas en `tmp/escalera_resolucion_255/`. No se cambian producto, configuración ni archivos de Claude.
