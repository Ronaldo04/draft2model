# Superficies 3D: configuración y operaciones ETABS — Claude

Encargo sustancial autónomo; mantener alcance hasta terminar fases locales. Anthropic ya revisado/integrado por Codex,21focalesOK sin API real. Usuario exige también que se puedan modelar los planos de referencia; aceptar solo muros no basta. Nuevo núcleo geométrico0.2 entregado por subagente: leer docs/GEOMETRIA_SUPERFICIES.md y docs/PLAN_REPRESENTACION_REFERENCIA.md. Codex integra gestión, plan geométrico y UI; NO los edites.

## Propiedad exclusiva

Puedes editar SOLO draft2model/modelo_estructural.py, draft2model/operaciones_etabs.py, scripts/ejecutar_plan_etabs.ps1, nuevos tests/test_modelo_superficies.py, tests/test_operaciones_superficies.py y docs/MODELADO_SUPERFICIES_ETABS.md. Marcador final seguimiento/ENTREGA_CLAUDE_SUPERFICIES_ETABS.json. No editar geometria_superficies/contratos/validacion_geometria ni otros archivos existentes/tests/fixtures/UI, proveedores, originales o catálogos. Codex posee el resto. Si otra dependencia exige edición, explica y prepara recomendación, sin invadir propiedad. Puedes leer todo el código necesario.

## Contrato y fases

1. Mantener configuración0.1 y operaciones0.1 intactas. Añadir configuración0.2 explícita con asignaciones_superficies y puntos que puedan referenciar un vertice_geometria XYZ de geometría0.2, además de puntos nodo+nivel heredados. Cada tipo de punto usa campos exactos de su alternativa, sin coordenadas inferidas. En0.2 mantener fuentes/hipótesis/revisión/huellas, cobertura completa de superficies/asignaciones, conexiones, cargas, masa, apoyos y diafragmas. VERSION0.1 permanece; constante adicional/despacho. Derivar coordenadas físicas desde geometria_m, no píxeles. Un vértice puede estar a cota intermedia sin crear Story ficticio. Evitar duplicar puntos coincidentes silenciosamente; requerir conectividad explícita.

2. Sección nueva explícita de prueba shell_losa_homogenea (isótropa lineal, espesor_m y fuente); NO afirmar equivalente a losa aligerada. Conserva shell_muro y frames. Asignaciones de superficie con fuente y sección compatible; papel_geometrico no elige rigidez/sección automáticamente. Cargas uniformes sobre superficie con unidades/componentes explícitos; masa por patrones sin doble peso; no habilitar masa puntual escalar rechazada. Diafragmas/exclusiones explícitos y coplanaridad por coordenada z real, también para puntos XYZ. Áreas sin sección, puntos huérfanos, conexión ausente, material incompatible y falsos diafragmas se rechazan.

3. Compilar operaciones0.2 para puntos XYZ y AreaObj.AddByPoint con contorno exacto, propiedad Slab mediante firma local ETABSv1 contrastada, y cargas uniformes sobre área. Ampliar juntas FIRMAS y lista blanca PowerShell. Usa DLL/documentación LOCAL si hay dudas de firma, sin abrir/ejecutar ETABS ni instalar. No suponer firmas. Etiquetas, ID devuelto, listas de nombres/propiedades y parámetros verificados deben cubrir también superficies nuevas, sin omisión silenciosa. Operaciones0.1 se conservan byte a byte para entradas anteriores cuando corresponda. Coordenadas/ejes geométricos no se declaran ejes locales de ETABS.

4. Pruebas focales propias y regresiones pertinentes de modelo/operaciones/lista blanca; ninguna suite global ni llamada API ni ETABS real. Dobles de transporte no acreditan solver. Casos válidos: piso homogéneo sintético y panel inclinado con cota intermedia, geometría+configuración revisada por fuente declarada, huecos/aligerado todavía NO implementados. Casos inválidos: referencias/cobertura/cotas/retornos/fallo parcial. No cambiar expectativas existentes para ocultar regresiones. TEMP/TMP en tmp proyecto.

El núcleo0.2 conserva BLOQUEO_INTEGRACION y disponible_para_modelado=false. NO retires ese bloqueo ni lo eludas globalmente. Para validar nueva configuración distingue consistencia y aprobación geométrica por huella de la disponibilidad del adaptador; la compilación nueva sigue sin autorización para ejecución real hasta que Codex revise todo el recorrido. Marca plan0.2 como desarrollo/no ejecutable si consumidor todavía lo rechaza; documenta precisamente qué falta integrar. No desactivar verificaciones antiguas ni fabricar aprobación.

No representan componentes completos todavía: aberturas, aligerados con nervios/equivalencia revisada, acciones de agua/hidrodinámica/apoyos de tanque y escalera completa. Esta base debe permitir continuar esos incrementos, no redefinir la meta. No inferir cargas/propiedades de los planos ni valores normativos.

## Entrega

Termina autónomamente fases y corrige fallos focales dentro de tu propiedad. Hasta10líneas de resumen más documentación. Última escritura marcador tarea=superficies_etabs, estado=entregado (o bloqueado con causa), archivos={rutas:SHA256} con TODOS los editados autorizados, comandos/resultados/logs, firmas contrastadas, límites y conflictos. Codex revisa, integra consumidores/lectura/UI y ejecutará pruebas reales posteriormente; no declarar goal completo.
