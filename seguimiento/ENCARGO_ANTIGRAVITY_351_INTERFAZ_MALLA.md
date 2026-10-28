# Encargo351: integrar políticas automáticas de malla dentro de la interfaz

Codex revisó el encargo350: hashes correctos y10pruebas focales propias OK. Tu módulo puro queda aceptado para integración, sin acreditar piloto ni normativa. Ejecuta ahora esta ruta completa sin esperar instrucciones entre hitos.

Raíz exacta: D:/RONALDO CUCHILLA/1. RONALDO CUCHILLA/2. INGENIERÍA CIVIL DOCS AND PROJECTS/AECODE CURSOS/AECODE AI TALENT/PROYECTO FINAL

## Reparto y contexto
Codex modifica preparacion_configuracion.py, revision_visual.py y revision_web/preparacion_configuracion.js/parametros.js para conectar lectura dirigida de parámetros, materiales y secciones. Otro agente terminó digitizacion_calibrada.py y parametros_a_configuracion.py; no modificar esos archivos. No leas historiales de chat/SQLite. Consulta solo módulos que necesites.

## Escritura permitida: lista cerrada
1. draft2model/revision_politicas_malla.py NUEVO
2. draft2model/revision_web/politicas_malla.js NUEVO
3. tests/test_revision_politicas_malla.py NUEVO
4. tests/politicas_malla_351_frontend.cjs NUEVO
5. docs/INTERFAZ_POLITICAS_MALLA.md NUEVO
6. seguimiento/ANTIGRAVITY_351_INTERFAZ_MALLA_INFORME.md
7. seguimiento/ANTIGRAVITY_351_INTERFAZ_MALLA_ENTREGA.json (escribir AL FINAL)
No tocar ningún otro archivo, tampoco registro ANTIGRAVITY_ESTADO.json ni servidor, Git, claves, datos privados, planos ni modelos reales. Temporales solo tmp/antigravity351/. No APIs ni ETABS. No instalar dependencias.

## Hito1: servicio persistente
Implementa clase ServicioPoliticasMalla(app), con métodos previsualizar(body) y aplicar(body). Usa app.preparacion_configuracion._cargar(caso,fp,version) para comprobar el borrador inmutable y app.preparacion_configuracion._guardar(...) para publicar copia hija con padre exacto (id,sha256_registro,sha256_configuracion), como hace revision_parametros.py. Usa gestion_geometria.consultar_version para geometría vigente y tus funciones puras previsualizar_politicas_malla/aplicar_politicas_malla. No publiques versiones formales ni aprobaciones.
Solicitudes incluyen caso,expediente_sha256,version,sha256_configuracion,reglas y declaración explícita del ingeniero (declarante,fecha,alcance) con confirmación. Previsualizar no exige confirmación de aceptación, pero no debe inventar reglas; muestra pendientes/conflictos aun con documento vacío. Aplicar requiere confirmación y huella exacta de la propuesta vista; rechaza fuente/geometría/preparación/código/propuesta cambiados, reglas incompletas y conflictos.
Para reglas formuladas aquí puedes crear fuente documental de la declaración (hash de su contenido, referencia al origen de registro.json que conserva reglas/declaración), sin presentarla como norma ni dato del plano. No inventes nombre de revisor ni fecha aprobatoria. La identidad es declarada, no verificada. Si se necesita usar esa fuente en reglas, documenta un sentinel consistente DECISION-FORMULARIO que solo el servicio sustituye por el ID derivado del hash y que añade antes del cálculo. No alteres fuentes existentes. Las otras fuentes elegidas deben existir en configuración.
El resultado de vista previa debe distinguir malla calculable de completa y conservar otros faltantes técnicos. Aplicar conserva naturaleza sintética/real y revisión en borrador; no ejecuta ETABS. El módulo puro ya controla reglas/nodos; no reimplementarlo.

## Hito2: interfaz comprensible, sin JSON obligatorio
Crear IIFE en politicas_malla.js que use window.D2MEtapas.containers.get('ingenieria'). Escucha evento window 'd2m-preconfig-opened' con detail igual respuesta de preparación {id,caso,expediente_sha256,sha256_configuracion,datos,validacion,...}; Codex emitirá este evento al abrir/crear/guardar. Si otro caso se abre, limpiar y deshabilitar datos y respuestas tardías.
Usa api(path,body), docs, $('...') globales existentes SOLO cuando haga falta; no exponer claves. Rutas acordadas POST /api/politicas-malla/previsualizar y /api/politicas-malla/aplicar; Codex las registrará en revision_visual.py y cargará tu script, no editarlo tú.
Formulario con reglas editables y explicaciones breves: apoyo en plano Z o borde entre puntos (con lista de hosts opcional), seis restricciones; reglas de diafragma por plano Z con ID existente o exclusión motivada; políticas de resto libre/sin diafragma SOLO con elección explícita; autorización explícita de subdivisiones calculadas. No valores de ingeniería por defecto: no asumir z=0/apoyo/diafragmas/restricciones del resto. Evita que usuario escriba listas de nodos derivados o JSON externo. Opciones avanzadas pueden omitirse de UI si no son necesarias para reglas básicas, pero no anuncies su cobertura.
Mostrar resumen de nodos/subdivisiones, pendientes, conflictos y errores. Campos de declarante/fecha/alcance y confirmación final diferenciados. Tras aplicar, emitir evento 'd2m-preconfig-created' con detail {caso,expediente_sha256,configuracion_preparacion:<id>,sha256_configuracion}; Codex abrirá automáticamente el hijo. Un cambio de formulario invalida huella de vista previa/confirmación. No cambiar estados de etapas a terminado ni aprobar datos.

## Hito3: pruebas y entrega
Backend: cadena real con fixtures sintéticas en disco y _cargar/_guardar, origen/huella/fuentes, previsualizar sin reglas no muta, aplicar reglas explícitas genera hijo sin aprobación, rechazo a fuente/geometría/código/huella alterados. Probar no mezclar transportes sintéticos en reales ni cambiar naturaleza. Frontend: formularios sin archivo externo, limpiar caso, respuestas tardías, cambio de regla invalida aceptación, confirmación necesaria y eventos de aplicación.
Solo pruebas focales necesarias, no suite completa. Si Windows sandbox impide rename/socket, diagnosticarlo; puedes ejecutar comprobación autorizada fuera de ese aislamiento cuando herramienta lo permita. No modificar pruebas/validaciones para ocultar fallos.
Escribe informe <=1página y marcador final con misma forma que350, tarea='351_interfaz_malla', estado entregado/bloqueado, raíz, archivos+sha256, pruebas+alcance sintético, limitaciones, apis_usadas=0,etabs_usado=false. Excluir marcador de sus propios hashes. Responde <=10líneas. Si hay una duda de contrato, elige opción conservadora documentada y continúa en archivos propios; no te detengas por una consulta rutinaria. No reiniciar servidores ni integrar archivos compartidos: Codex lo hará.
