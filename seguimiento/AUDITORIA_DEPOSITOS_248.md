# Depósitos del piloto: lectura local248

2026-10-22. Lectura propia de Codex, sin llamadasAPI ni modificaciones del producto/caso. Sirve como insumo de implementación, no aprobación de ingeniería. Originales conservados. Imágenes obtenidas con Poppler144dpi y comprobadas visualmente; `tmp/auditoria_depositos_248/indice.json` registra hashes/páginas.

## Fuentes y regiones

- E03: `planos_muestra/proyecto_pueblo_libre/Estructuras_Pueblo Libre1.pdf`, página1, SHA256 `fb4284e82b7a55f4faeb4e9917269b37e94336c0788562873385e7e21c67a134`, página3370×2384pt.
- Corte tanque: regiónPDF aproximada[320,1360,1020,2070]pt, captura `tmp/auditoria_depositos_248/tanque.png`.
- Corte cisterna completo: región[1060,1390,1955,2095]pt, captura `cisterna_completa.png`. El primer recorte más estrecho no contiene todas las cotas; no usarlo como prueba de ausencia.
- Techo cisterna: región[2010,1720,2560,2275]pt, captura `techo_cisterna.png`.
- A03: `planos_muestra/proyecto_pueblo_libre/Arquitectura-Model3.pdf`, página1, SHA256 `ead656045a3c95739e2bd7cab3c5daddb6d1e42ebaa7aaf9afb6c34be07dce4a`, vista2384×1684pt, MediaBox1684×2384pt y rotación270°. Planta de techo, tanque a la izquierda de escalera, entre ejes3/2 yB/D. Rotulación tanque en coordenadas de extracción SIN rotar[980.47,1320.92,993.68,1411.91]pt; en vista rotada[1320.92,690.32,1411.91,703.53]pt. **Aplicar rotation_matrix a puntos/bbox de extracción antes de comparar con píxeles de vista**; no mezclar estos sistemas. Inspección visual confirma N.T.T.+14.60 y techo+10.40.

## Tanque elevado: confirmado y derivado

El corte E03 imprime NT=+10.35m en la base de apoyos y cadena vertical ascendente:2.00m de apoyo, .20m de fondo,1.10m de tramo interior inferior,.45m de tramo interior superior,.20m de tapa y .10m de resalto/acceso. También aparecen .30 «típico» como longitud de detalle de acero: **no confundir esa longitud de anclaje con espesor del muro**.

Derivación aritmética exclusiva del corte estructural, si la cadena se interpreta respecto a las caras dibujadas:

| Plano físico | Cota derivada E03(m) |
|---|---:|
| Base de apoyo |10.35|
| Intradós fondo |12.35|
| Cara superior fondo/interior inferior |12.55|
| División1.10/.45 del interior |13.65|
| Intradós tapa |14.10|
| Cara superior tapa |14.30|
| Resalto/acceso |14.40|

La altura interior derivada es1.55m. La división1.10+.45 es compatible con un escenario de agua1.10m y borde libre.45m; **no encontré rótulo explícito de N.A./nivel de operación en el corte revisado**, por lo que esa interpretación debe conservarse como hipótesis, no dato confirmado. No elevar automáticamente a1.55m ni afirmar operación con1.10m.

La arquitectura imprime techo+10.40 y tanque+14.60: discrepancias.05m en base y.20m respecto del resalto estructural. El usuario confirmó niveles principales hasta10.40, **no** resolvió cotas del depósito ni la interpretación del rótulo14.60. No desplazar todos los nodos del tanque para satisfacer ambos documentos silenciosamente. Se pueden preparar alternativas claramente etiquetadas preservando qué fuente fija cada cota.

No hay cota horizontal de ancho/largo del tanque en este corte. La plantaA03 tiene un contorno rectangular; usar vectorización calibrada y límites de incertidumbre para dimensiones derivadas, no estimación visual de píxeles ni caja de toda el área tanque+acceso contigua. Espesor de muros y sección/ubicación de apoyos requieren cotejo de planta/detalles; el corte aislado no los confirma por anotación.

## Cisterna: datos utilizables

- TechoE03 acota un claro2.00×2.15m; bordes derechos/superior/inferior.20m, borde con C3/C6 marcado.15m. No convertir sin más los2.35×2.55m externos en dimensión interior.
- Hueco de acceso cuadrado dibujado en esquina inferior izquierda; cota.55m en una dirección. No certificar su segunda dimensión solo por apariencia cuadrada: el contorno vectorial puede medirla. Conservar hueco en la tapa; no crear masa/rigidez sobre él.
- Techo muestra C3 arriba y C6 abajo, en el borde izquierdo. Vincular con coordenadas de esas instancias del inventario para posición/apoyos reales; no crear una cisterna en una ubicación arbitraria.
- CorteE03: espesor de tapa.15m, muros.20m, fondo.20m, solado.05m; refuerzo se rotula por cara. No modelar el solado como concreto armado resistente sin justificación.
- **La altura interior impresa es2.22m**, leída en el recorte completo, no2.32m. Debe conservarse la captura para evitar transcripción errónea.
- Corte muestra .20m adicionales en la zona inferior y engrosamientos/patines bajo muros de.35+.20m horizontales. No sustituir todo el fondo por una caja plana con volumen macizo hasta la base del patín; separar lámina/fundación si el análisis los distingue.
- NFC=−2.65m se refiere a la línea inferior de cimentación/solado junto al patín. **No equipararlo automáticamente a cota de la cara superior interior del fondo**, que está por encima. Faltan correspondencias de caras/niveles respecto al NPT del edificio para fijar un únicoZ global sin hipótesis.
- Borde de planta izquierdo.15m(C3/C6) y muros.20m del corte requieren interpretación de encuentro columna/muro; no eliminar el conflicto por redondeo. Revisar posición/ejes con auditoríaC6/PL10.

## Ensayos y cantidades de control condicionadas

Estas expresiones solo fijan valores de referencia para casos que declaren explícitamente su geometría/nivel. No establecen nivel operativo ni prueba nativa. Con el peso10kN/m³ ya representado por `normativa_rne.peso_especifico('agua_dulce')`, para un muro vertical con nivelh: presión en fondo10h(kPa), fuerza por metro de longitud5h²(kN/m), brazo de la resultanteh/3 desde fondo. El peso y carga del fondo son la misma acción física vista en representaciones distintas; no duplicarlos. Masa sísmica del contenido debe ser trazable al100% de contenido elegido y sin doble conteo de masas por carga/masa adicional.

| Escenario ilustrativo, NO operación confirmada | h(m) | p_fondo(kPa) | F_por_m(kN/m) |
|---|---:|---:|---:|
| Tanque, división inferior del corte |1.10|11|6.05|
| Cisterna, límite interior sin borde libre |2.22|22.2|24.642|

Si se adopta claro cisterna2.00×2.15m y altura2.22, volumen geométrico máximo9.546m³ y peso95.46kN. No representa volumen útil autorizado, ni valida que el corte corresponda a toda la planta sin desniveles/encuentros. Escenario vacío también debe poder representarse sin presiones ni masa de agua ficticia. Edificios que no tengan depósitos requieren ausencia confirmada; la arquitectura de software no debe exigirlos.

## Para integración

1. Implementar lo confirmado y registrar cada medición derivada con región/calibración, sin aprobar automáticamente lecturas pendientes.
2. Resolver posición con C3/C6 e inventario, eje de apoyos del tanque y contornos en planta antes de añadir elementos al modelo global.
3. Separar alternativas de niveles/operación y acciones de suelo de hechos del plano. SinEMS, no afirmar comprobación de empujes, flotación ni capacidad portante real.
4. Verificar normales/cara de presión, fondo/tapa con formulación de flexión, cortes en nivel de agua y continuidad/nodos. Guardado/relectura y equilibrio nativo propios son necesarios; los ensayos sintéticos anteriores no acreditan estos depósitos.
