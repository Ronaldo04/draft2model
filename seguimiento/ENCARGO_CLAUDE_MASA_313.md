# Encargo313: predicción independiente de extremos y masa

Responsable: Claude. Proyecto/carpeta: PROYECTO FINAL, esta raíz. Codex revisó311: nueve pruebas e inventario regenerado idéntico; la referencia humana aún no fue entregada. No medir precisión sin ella.

Codex tiene congelada la distribución312 y ejecuta su validación global. No editar producto, tests públicos, docs ni entregas. No entrar en otra carpeta de proyecto.

## Objetivo y secuencia autónoma

Resolver técnicamente, hasta donde permitan las fuentes existentes, la diferencia de masa del piloto mediante una predicción independiente de los extremos efectivos. Este encargo no pide otro ajuste al peso nativo observado. Trabaja los pasos consecutivamente y entrega una sola conclusión comprobable.

1. Lee seguimiento/REVISION_EXTREMOS_278.json, BALANCE_MASA_GRAVEDAD_268.json, REVISION_MATERIALES_272.json y sus fuentes locales necesarias. Distingue la conciliación retrospectiva ya hecha de una predicción previa al solver. El libro conserva548,7267285730835 nativo frente a549,4269889710316 independiente; diferencia principal de CM6,8681120841357kN. No cambiar tolerancia0,001.
2. Usa únicamente geometría, secciones, orientación y configuración declarada del plan para intentar predecir extremos de las45vigas VS, con un procedimiento genérico y explícito. No introducir longitudes equivalentes obtenidas de pesos, offsets nativos o números del recibo como entradas del predictor. Esas capturas sirven solo como contraste posterior.
3. Si las fuentes permiten una regla defendible, construye un prototipo aislado y pruebas representativas: orientación, intersección sin soporte, casos ambiguos y sección distinta. Emite por viga entradas geométricas, regla, longitud bruta, descuento predicho y trazabilidad. Contrasta después contra los offsets archivados e identifica desacuerdos. Si no se puede determinar Auto de forma independiente, abstén el predictor en esos casos y explica el dato/regla faltante sin fabricar una equivalencia.
4. Separa además el residuo global restante del descuento por VS. No atribuirlo a redondeo sin cotas de error comprobadas. Puedes determinar que los datos no bastan; esa es una conclusión válida con evidencia concreta.
5. Entrega informe breve con propuesta de integración, condiciones necesarias y límites. No ejecutar ETABS, modificar resultados originales ni marcar ingeniería aprobada. No abrir el modelo manual del usuario. No nuevas APIs, OCR ni proyectos2/3; nunca leer credenciales.

## Escritura autorizada

Solo `seguimiento/claude_ruta/prediccion_masa_313/` y, como última escritura, `seguimiento/claude_ruta/MARCADOR_MASA_313.json`. Puedes leer archivos públicos del programa y el expediente del primer piloto para este análisis; no modificar ninguno. No tocar carpetas309/310/311 ni kit humano.

Marcador: tarea exacta `masa_313`, estado `entrega_candidata` o `bloqueo_declarado`, responsable, resultado y límites, y mapa `archivos_permitidos_sha256` con rutas relativas y SHA256 de cada archivo de entrega. Una falta de datos no autoriza inventarlos ni ampliar perímetro. Responde hasta10líneas; el detalle va a archivos. Codex conserva integración y aceptación.

## Criterio de aceptación

El predictor, si existe, no recibe evidencia de salida nativa como entrada ni oculta abstenciones. Las fórmulas y casos de prueba permiten revisar independencia y alcance. Toda comparación con el solver está separada de la predicción. Un diagnóstico de imposibilidad especifica exactamente las fuentes revisadas, el impedimento y qué información permitiría continuar. No se exige que el resultado pase por construcción.
