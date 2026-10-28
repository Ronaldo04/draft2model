# Configuración y plan de aberturas0.3

La geometría0.3 exige un contorno anfitrión y contornos interiores coplanares, simples, contenidos y sin intersecciones. La configuración0.3 conserva la fuente geométrica y su revisión por huella. Los puntos de los huecos deben aparecer explícitamente, igual que apoyos o exclusiones justificadas de diafragma; no se inventan conexiones por proximidad.

`operaciones_etabs.generar_plan_aberturas` produce un plan de desarrollo0.3. Crea cada hueco con `AreaObj.AddByPoint`, propiedad `None` y nombre propio; aplica `SetOpening(true)` y comprueba `GetOpening`, puntos y propiedad. La anfitriona se declara no abertura y se relee. Ninguna carga de área se asigna al hueco. Las trazas conservan superficie, procedencia y áreas bruta, de huecos y neta.

El plan continúa con `ejecutable=false`; su generación no habilita automáticamente el ejecutor de producción. La configuración mantiene el bloqueo de integración. El efecto de `Opening`, la compatibilidad del mallado y el corte de rigidez/carga requieren ensayo real y revisión antes de habilitar el recorrido completo. Una bandera persistida y un dibujo con hueco no prueban ese efecto físico.

Revisión local178: tres pruebas de configuración y tres de plan pasan (incluida reflexión de firmas en DLL local). Los escenarios de transporte PowerShell existentes todavía no están aceptados en este corte: el diagnóstico de fallos del puente está encargado a Claude. La relectura independiente de aberturas también está en su encargo176. No se afirma un ensayo ETABS real por estas pruebas.
