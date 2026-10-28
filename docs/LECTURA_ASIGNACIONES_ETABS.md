# Lectura independiente de propiedades y asignaciones

`scripts/leer_asignaciones_etabs.ps1` admite IdProceso, ModeloEsperado, Configuracion y Registro. Consulta exclusivamente getters de una lista construida por el propio script desde tipos reconocidos del contrato. Requiere ruta abierta exacta y unidades de presentación kN_m_C; no cambia unidades, abre, guarda, calcula ni aprueba modelos. El registro debe ser nuevo.

Recupera material/peso/masa, secciones, puntos conectados y propiedades de frames/muros, apoyos y diafragmas, cargas puntuales/distribuidas/uniformes, patrones, masa, combinaciones y casos. La ampliación dinámica lee número/parámetros/cargas iniciales Eigen; modal asignado, cargas espectrales, excentricidad, damping/tipo/overrides y combinación modal; pares de las funciones espectrales. No interpreta automáticamente los códigos numéricos no documentados como parámetros normativos.

La salida conserva interfaz, método, nombre, retorno y todos los parámetros recuperados. Retorno no cero o tipo desconocido detienen la lectura sin emitir un registro aparentemente completo. La selección de cargas/casos para resultados es otra operación del puente.

Evidencia actual: el lector ampliado volvió a leer correctamente 28 registros estáticos en el ensayo calculado (`tmp/a5/lectura_asignaciones_ampliada.json`). Las nuevas rutas modales/espectrales requieren el siguiente modelo dinámico construido para comprobarse en real. No atribuirles cobertura real por pasar las lecturas estáticas. Las cargas de frame/muro tampoco se han releído en ese caso, que solo usa carga puntual.

Ejecutar sobre un modelo aislado, sin ediciones concurrentes. El script no impide que otro cliente o una persona modifique ETABS mientras consulta. El flujo de producto deberá envolverlo en la exclusión compartida de la instancia y contrastar el registro con configuración/plan exactos antes de conceder revisión. Ninguna lectura ni el SHA de un archivo autentican identidad o competencia del revisor.

Ampliación real confirmada: tmp/d4/lectura_persistida.json contiene39 getters después de reabrir la copia construida dinámica. comprobacion_dinamica_ampliada.json contrasta27 controles, incluidos overrides de damping vacíos; todos coinciden. La comparación no aprueba resultados ni ingeniería. Las cargas de frame/muro siguen sin ejercicio real en esta fixture puntual.
