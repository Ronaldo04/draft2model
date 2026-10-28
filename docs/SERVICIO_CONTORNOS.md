# Lectura y calibración automática de contornos

El servicio `ServicioContornos` conecta la lectura visual de planos con la calibración y la incorporación geométrica. Reutiliza originales verificados, cuota, consentimiento de envío, conservación de respuestas y transporte de reconstrucción. Una petición consume una solicitud del proveedor; calibrar, comprobar y recuperar una respuesta guardada son operaciones locales.

La entrada es una preparación de ingeniería conservada con su SHA256, proveedor/modelo, límite de salida y nueve criterios computacionales explícitos de calibración. El contexto se obtiene de su geometría comprobada, vértices y barras existentes. Solo se catalogan planos cartesianos con cotas presentes y tres referencias no colineales; el modelo no puede inventar niveles ni enviar coordenadas métricas como respuesta. Los criterios son computacionales, editables y no representan una tolerancia normativa o aprobación humana.

El proveedor propone dibujos, correspondencias normalizadas y topología con evidencia. El servidor valida esa respuesta, obtiene las referencias métricas desde la geometría y ejecuta `ServicioDigitizacion` localmente por dibujo. `incorporar_contornos` reproduce los cálculos, contrasta sus vínculos y valida conjuntamente caras y aberturas. Un conflicto impide incorporar todo el lote; se conservan la lectura y los diagnósticos. Las correspondencias visuales siguen siendo propuestas, incluso cuando el cálculo numérico es reproducible.

Una incorporación consistente conserva una geometría nueva en borrador y una preparación derivada de la anterior. Mantiene los datos técnicos y las asignaciones existentes, añade los puntos y barras nuevos y deja sus secciones sin completar cuando falta información. Invalida la malla y las conexiones que dependían de la geometría anterior; las decisiones previas quedan conservadas en el padre. El resultado registra el vínculo entre geometrías, trabajo, calibraciones y preparación. La nueva geometría se registra como importación automática, con la relación al origen conservada en el trabajo; no es una revisión técnica declarada por una persona.

El resultado nunca aprueba ingeniería, borra observaciones anteriores ni ejecuta ETABS. Una geometría parcial con nuevas caras continúa siendo parcial. Un doble de proveedor no puede incorporar información a una geometría real: las pruebas conservan su naturaleza sintética.

Rutas del servidor local, con sus controles habituales de origen y sesión:

- `GET /api/contornos/historial`: trabajos del expediente.
- `GET /api/contornos/estado`: estado y resultados conservados.
- `POST /api/contornos/preparar`: preparación local de páginas y contexto.
- `POST /api/contornos/ejecutar`: un envío confirmado, sin reintento automático.
- `POST /api/contornos/recuperar`: reprocesar la respuesta guardada, sin proveedor.

Verificación focal: `python -B -m unittest tests.test_revision_contornos`. Incluye originales sintéticos, transporte doble sin red, calibración real, conservación de versiones, recuperación sin otro envío y rutas HTTP con preparación y confirmación. No acredita planos reales ni ETABS. La interfaz se integra por el encargo359; su existencia o sus pruebas no equivalen a aceptación del edificio completo.

Límites actuales: una lectura admite hasta ocho páginas; aún falta el recorrido entre lotes mayores. Los planos oblicuos o cotas ausentes requieren ampliación del contexto. Ninguna de estas condiciones se sustituye por una escala o un valor supuesto. El formulario y la prueba real de este nuevo servicio están pendientes de integración y revisión.
