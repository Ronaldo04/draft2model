# 03 — cubrir documentación y recorrido de la referencia completa

Objetivo: cerrar implementación necesaria para TODOS los componentes de los planos adjuntos y para viviendas con/sin recipientes, no reducir a ejemplo simple de un muro.

Lee requisitos/documentación vigentes y contrasta contra código. Crea matriz requisito→módulo/recorrido→criterio verificable→evidencia/pendiente. Expón discrepancias y corrige implementación/documentos actuales sin eliminar requisitos para facilitar cierre. Referencia conocida: hasta4niveles, losas aligeradas, frames/placas, escaleras, muros, cisterna/tanque. Geometría/huecos/compatibilidad/topología/ejes/propiedades/materiales/masas/cargas/apoyos/diafragmas/casos/combinaciones/análisis/lectura/normalización/controles/informe deben estar integrados. No sustituir aligerada por maciza ni eliminar escalera/recipiente para pasar pruebas. Ingeniería que no esté definida debe quedar faltante real, sin defaults inventados.

Comprueba que el ingreso de planos, lectura por Google/OpenAI, revisión explícita y conversión a geometría/configuración puedan conducir a modelo completo sin que un usuario programe funciones internas. Mantén edición/revisión necesarias, errores accionables y trazas. Las declaraciones profesionales no son identidad autenticada ni certificación. Modelos proveedores diferentes se eligen explícitamente; no fallback automático ni APIs fuera de revisión de planos. Ocultar/deshabilitar opciones no autorizadas de proveedor en el recorrido actual sin romper lectura histórica.

Validar casos representativos de componentes y sus conexiones, nivel y unidades, incluyendo vivienda sin cisterna. Añade validación de instalación/configuración/rutas/permisos y errores de ETABS/localAPI. Resuelve falta de soporte del código; no confundirla con dato técnico pendiente del usuario.

Aceptación: matriz cubre alcance completo sin requisitos omitidos, funciones conectadas UI/CLI/servicios, pruebas focales/integración y revisión visual pertinente. Diferenciar implementado/probado en doble/probado nativo/pendiente de dato o piloto. Entrega y continuar04.
