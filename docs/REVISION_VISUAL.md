# Revisión local de lecturas y geometría

La interfaz local permite consultar un expediente, ver la página completa con regiones de evidencia, contrastar candidatos y registrar correcciones. Usa las versiones de `gestion_extraccion`; guardar crea una hija de la versión abierta, sin sobrescribir el original ni las revisiones anteriores.

## Abrir

En la carpeta del proyecto, ejecutar **Abrir revision de planos.cmd**, o:

```powershell
.\.venv\Scripts\python.exe -m draft2model.revision_visual
```

El proceso abre `http://127.0.0.1:8766` en el navegador del equipo. Mantener la terminal abierta. Para otra raíz privada o puerto:

```powershell
.\.venv\Scripts\python.exe -m draft2model.revision_visual --raiz data/private --puerto 8767 --sin-navegador
```

No se requiere clave API, ETABS ni dependencias adicionales. La pantalla no ejecuta extracción ni llamadas externas.

## Flujo

1. Seleccionar un expediente registrado con autorización de uso. Se conserva su alcance; la muestra provisional permanece fuera del MVP.
2. Elegir lámina y página. Se pueden consultar planos cuando todavía no existen lecturas. Las páginas se renderizan desde los originales comprobados, sin confiar en vistas previas editables.
3. Abrir una versión o importar un JSON de extracción mediante el selector de archivos. La importación pasa por las comprobaciones de evidencia del flujo CLI. El texto original se conserva como fuente importada; las claves JSON duplicadas se rechazan. Límite de archivo en pantalla: 1.5 MiB; solicitud HTTP: 2 MiB.
4. Seleccionar una lectura en la lista o en el plano. Los botones de evidencia permiten recorrer todas sus referencias, incluso en otras páginas. La vista admite ajuste y ampliaciones de 150 %, 200 % y 300 %.
5. Confirmar/corregir, rechazar o dejar pendiente. Registrar motivo, fecha y revisor declarado. Para cotas se usa un número finito con punto decimal y una unidad explícita; para etiquetas y elementos se conserva texto.
6. Guardar una nueva versión. La interfaz abre la hija guardada. Elegir una versión anterior deliberadamente crea otra rama de revisión, sin fusionar ramas automáticamente.
7. Exportar revisados genera un archivo nuevo dentro del expediente y muestra su ruta relativa. No descarga ni publica el expediente. Las lecturas pendientes y rechazadas quedan excluidas mediante el exportador existente.

El historial y la propuesta original siguen visibles. Revisar lecturas no aprueba geometría ni produce automáticamente datos estructurales.

## Geometría versionada

La sección **Geometría versionada** utiliza directamente `gestion_geometria`. Mantiene las operaciones geométricas separadas de las lecturas y conserva el alcance declarado en el expediente.

1. Seleccionar el expediente e importar un contrato `draft2model.geometria` JSON con su mismo `id`. La importación puede tener faltantes declarados consistentes, pero no puede declarar una aprobación. El selector envía contenido, nunca una ruta del equipo. Se conserva la fuente exacta en una versión nueva.
2. Elegir una versión geométrica. Se comprueban originales, expediente, fuente importada y cadena de padres antes de mostrar el contrato completo. El detalle incluye procedencia, marca sintética, metadatos, validación, faltantes, bloqueos y cadena de versiones. El listado solo identifica versiones: su existencia no acredita vigencia.
3. Editar el JSON completo y completar revisor, fecha y motivo. Para guardar una revisión debe contener `revision.estado: "borrador"` y `revision.aprobacion: null`. Se crea una versión hija sin modificar ni aprobar su padre. Para revisar una versión aprobada, esos campos deben cambiarse explícitamente a borrador/null en el editor.
4. **Comprobar evidencia** vuelve a consultar y comprobar la versión guardada; recarga su JSON, por lo que se deben guardar antes las ediciones que se quieran conservar.
5. La aprobación es otra operación: completar motivo, revisor, fecha y alcance, comprobar la huella visible y marcar la declaración explícita. **Registrar aprobación explícita** permanece deshabilitado mientras falten esos campos o la declaración, existan faltantes o cambios pendientes, la versión ya esté aprobada o no haya una comprobación válida; un texto explica la condición pendiente. El servidor vuelve a exigir confirmación booleana `true`, huella exacta y SHA256 de los bytes de la versión; el gestor rechaza faltantes o evidencia inválida. Registrar crea otra hija, conservando la marca sintética y el alcance del expediente.

El revisor y su competencia son declarados y no autenticados. Este registro no certifica seguridad estructural ni aprueba planes, modelos o resultados derivados. No hay conversión automática de lecturas a geometría, visualización métrica 3D ni ejecución de ETABS. El editor JSON está destinado a usuarios que conocen el contrato; sus comprobaciones no sustituyen la revisión técnica del proyecto.

API de la misma sesión local: `GET /api/geometrias?caso=…`, `GET /api/geometria?caso=…&version=…` y `POST /api/geometria/importar`, `/api/geometria/revisar`, `/api/geometria/aprobar`. Las escrituras reciben el mismo expediente y su huella; revisión/aprobación requieren además identificador, huella de contenido y SHA256 de geometría. No existe operación que apruebe al importar o revisar.

## Integridad y acceso

- Antes de mostrar una página se comprueban los bytes del original y la huella del expediente abierto. PDF: página visible, incluida rotación y CropBox. Imágenes: orientación EXIF corregida. Las regiones son coordenadas normalizadas de página, no metros.
- Antes de corregir o exportar se vuelven a comprobar la versión, ascendencia, fuentes y evidencia. La huella enviada por la pantalla debe coincidir; una evidencia alterada bloquea la operación.
- Servicio enlazado exclusivamente a `127.0.0.1`, con comprobación de Host, Origin y contexto de navegación. Las API requieren una clave aleatoria de sesión; las escrituras además requieren Origin de la propia aplicación. No hay CORS ni rutas para descargar archivos arbitrarios.
- Páginas, respuestas y HTML llevan `Cache-Control: no-store`. No se registran solicitudes con nombres o contenidos privados. El token vive durante el proceso y no se introduce en la URL ni en archivos del caso.
- Renderizado limitado a unos 2400 píxeles por lado; originales de hasta 128 MiB. No hay medidas inferidas del DPI. No se envían documentos a servicios externos.
- El revisor es una identidad declarada, no autenticada. Las huellas no protegen frente a un proceso local que edite archivos y recalcule todas las huellas. No hay bloqueo del sistema de archivos frente a otros procesos.

## Comprobaciones y límites

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_revision_visual.py -v
```

Las pruebas cubren importar/corregir/exportar lecturas y el recorrido HTTP geométrico importar → revisar borrador → aprobar explícitamente. Comprueban conservación de versiones, estados y alcance, marca sintética, datos y huellas obsoletos, evidencia alterada, rechazo de aprobación con faltantes o confirmación inválida, rutas, solicitudes ajenas y renderizado con rotaciones 0/90/180/270 y orientación EXIF. Se usa el parser y manejador HTTP reales con transporte de bytes en memoria: el entorno restringe conexiones de sockets locales. Estas pruebas no acreditan una sesión de navegador ni una auditoría de accesibilidad. En Windows el sandbox puede bloquear la publicación atómica por renombrado; la misma suite se ejecutó correctamente fuera del sandbox con carpetas temporales sintéticas (24 pruebas).

La validación operativa de la interfaz en navegador sigue pendiente y se distingue del servicio probado en el controlador. El piloto todavía no tiene una extracción real importada; abrir sus planos no crea candidatos. La carga inicial de PDF/JPG/PNG continúa usando el comando de ingreso existente.

Archivos: `draft2model/revision_visual.py`, `draft2model/revision_web/` y `tests/test_revision_visual.py`.
