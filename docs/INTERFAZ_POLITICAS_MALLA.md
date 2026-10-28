# Políticas de malla en preparación de ingeniería

`ServicioPoliticasMalla(app)` conecta el motor puro existente `politicas_malla_automatica.py` con preparaciones persistentes. La integración del servidor debe instanciarlo y registrar POST `/api/politicas-malla/previsualizar` → `previsualizar(body)` y `/api/politicas-malla/aplicar` → `aplicar(body)`, utilizando la protección de origen/token del servidor. Este módulo no registra rutas, reinicia procesos ni modifica archivos compartidos.

## Servicio

Ambas solicitudes exigen exactamente `caso`, `expediente_sha256`, `version`, `sha256_configuracion`, `reglas`, `declaracion`. `reglas` usa el contrato cerrado del motor; la vista previa admite su plantilla vacía o `null` para mostrar pendientes sin inventar políticas. `declaracion` es `{declarado_por, fecha, alcance}`; fecha ISO y textos explícitos, sin autor ni fecha automática. Puede ser `null` en una vista sin fuente de formulario.

Aplicar añade tres campos obligatorios: `confirmacion_explicita: true`, `huella_propuesta` y `sha256_algoritmo`, exactamente como se recibieron de la vista previa. Siempre exige una declaración completa. La vista no exige confirmar aceptación.

El servicio opera bajo `app.lock`, usa `app.preparacion_configuracion._cargar/_guardar` y comprueba la geometría vigente. La huella enlaza solicitud, bytes del registro padre, geometría canónica, reglas efectivas, declaración, propuesta del motor y huellas del servicio/algoritmo/dependencias geométricas. Al aplicar reproduce el cálculo y rechaza cambios. Comprueba también que los archivos de código sigan iguales a los observados al importar el servicio: un cambio exige actualizar el proceso servidor.

El sentinel **`DECISION-FORMULARIO`** solo puede sustituirse en un campo `fuente`. Cuando se usa, el servicio añade a la copia una fuente `DECISION-MALLA-<hash>`, cuyo SHA256 identifica la decisión canónica con reglas, declaración e identidad `declarada_no_verificada`. No representa una norma ni un dato de plano. La decisión completa se conserva en `registro.json#origen.decision` del hijo creador. Su referencia incluye el hash y señala la cadena inmutable de padres, para conservar el significado cuando otro hijo herede la fuente; no supone que la decisión esté en el registro del último descendiente. Las fuentes anteriores permanecen intactas. Las demás fuentes elegidas deben existir en la configuración.

La vista devuelve `propuesta`, `huella_propuesta`, `sha256_algoritmo`, huellas de código, `malla_calculable`, `politicas_completas`, `validacion` y `otros_faltantes_tecnicos`. Una malla calculable puede tener reglas pendientes, y políticas completas pueden coexistir con materiales, líquidos u otros datos pendientes. `configuracion_completa` siempre es falso: esta etapa no acepta el modelo completo.

Aplicar rechaza errores, conflictos o pendientes del motor; publica un hijo con padre exacto `{id, sha256_registro, sha256_configuracion}`. Conserva naturaleza y datos técnicos, registra decisiones/código/huellas, deja revisión en borrador sin aprobación y nunca ejecuta ETABS. No publica una versión formal ni reintenta automáticamente una aplicación.

## Formulario y eventos

El servidor debe cargar `draft2model/revision_web/politicas_malla.js` después de habilitar `window.D2MEtapas.containers.get('ingenieria')` y el helper `api`. El script añade un formulario real, sin archivo JSON obligatorio, para:

- Restricciones por plano Z o borde entre puntos existentes, hosts opcionales y seis elecciones explícitas UX/UY/UZ/RX/RY/RZ.
- Diafragma existente o exclusión motivada por plano Z.
- Resto libre y resto sin diafragma únicamente por selección expresa y motivada.
- Autorización expresa de las subdivisiones calculadas, fuente y declaración responsable.

No precarga cotas, restricciones, fuente, responsable ni fecha. Una cota vacía no equivale a cero. Las reglas actúan sobre nodos derivados; no editan apoyos de los puntos originales. La vista muestra cantidades, condiciones propuestas por nodo, barras a subdividir, pendientes, conflictos, errores y otros faltantes técnicos. La interfaz básica no anuncia selectores avanzados de entidades/nodos ni autorización individual por frame; esos pertenecen al contrato del motor.

Evento de entrada `d2m-preconfig-opened`: `detail` es la respuesta de preparación con `id`, `caso`, `expediente_sha256`, `sha256_configuracion`, `datos` y `validacion`. Reinicia decisiones/confirmación para esa versión. `d2m-case` limpia todo. `d2m-preconfig-edited` con `{caso, expediente_sha256, id, sin_guardar: true}` invalida la propuesta y bloquea previsualizar/aplicar hasta otro `opened` de versión conservada. Cada cambio del formulario invalida también huella y confirmación.

Salida tras guardar: `d2m-preconfig-created` con `{caso, expediente_sha256, configuracion_preparacion, sha256_configuracion, preparacion_origen}`. El origen es la versión enviada al backend. Una aplicación que termina después de abrir otra rama del mismo caso solo notifica el hijo disponible; el receptor debe abrirlo automáticamente únicamente cuando **no haya ediciones sin guardar** y la versión actual sea el origen o no exista una abierta. Una respuesta de otro caso se descarta. Las vistas previas tardías no reactivan formularios de otra versión ni pisan cambios.

## Verificación y límites

Pruebas focales: `.venv/Scripts/python.exe -B -m unittest tests.test_revision_politicas_malla -v` y `node tests/politicas_malla_351_frontend.cjs`. Backend usa cadena real de expedientes/geometry/configuración sintéticos temporales; frontend usa DOM simulado, sin GUI. Windows sandbox bloqueó `rename` con WinError5 antes de ejecutar el servicio; las pruebas de disco se ejecutaron después en el host, sin alterar validaciones.

Recibo y hashes: `seguimiento/INTEGRACION_POLITICAS_352.json`. No acredita planos reales, recorrido visual en navegador, rutas HTTP integradas, normativa, suite completa ni ETABS. Los archivos algorítmicos originales y los compartidos de servidor/preparación permanecen fuera de este cambio.
