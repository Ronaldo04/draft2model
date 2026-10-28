# Masa del contenido y masa ensamblada en la interfaz

Estas opciones enlazan el inventario del modelo y una captura de masa con el análisis exacto incluido en el informe. Son optativas: una vivienda sin depósitos conserva el recorrido normal, sin añadir agua ficticia. Abrir la pantalla o marcar una opción no ejecuta ETABS ni envía datos a proveedores.

## Lectura deliberada

1. Seleccionar un análisis aceptado y vigente del expediente.
2. Declarar tablas y casos de ese análisis. La tabla debe tener un campo de caso admitido; por ejemplo, `Base Reactions` con un caso de carga calculado. `Mass Summary by Story` no tiene ese campo y no sustituye esta selección.
3. Marcar **Masa ensamblada** en la lectura, preparar, revisar y confirmar explícitamente su ejecución. Se solicita `AssembledJointMass` además de las tablas, en una instancia nueva del lector.
4. Seleccionar la lectura aceptada. El servicio comprueba la solicitud, respuesta, recibos, unidades, análisis, EDB y huellas. El navegador recibe una referencia compacta; los arrays de masa permanecen en el servidor.

## Informe

Seleccionar el resultado y su análisis correspondiente. **Inventario de contenido** recupera el inventario del plan del modelo analizado; exige que ese plan lo tenga registrado. **Masa nativa** exige una lectura real, vigente y no sintética del mismo expediente, análisis y EDB. Una lectura con dobles no habilita esa sección.

Crear el informe conserva por separado las referencias seleccionadas y los datos derivados. La apertura, aprobación exclusivamente documental y descarga JSON/HTML/PDF vuelven a verificar las fuentes. Si una referencia o sus bytes cambian, la operación se rechaza; no se reemplazan por otra lectura reciente. Cambiar expediente, resultado, análisis o lectura invalida la selección anterior.

El contraste compara la masa global ensamblada con el libro completo de contribuciones; no compara todo el edificio únicamente con el agua. Se conserva el resultado coherente o no coherente. El inventario, por sí solo, no acredita masa nativa, distribución hidrodinámica ni conformidad de ingeniería.

## Alcance de la evidencia267

Los servicios, controles y ciclo documental tienen pruebas con transporte local y fuentes sustituidas explícitamente. Esas pruebas no acreditan el piloto real. La evidencia de ETABS del caso y la revisión visual del recorrido integrado se registran por separado en el seguimiento del proyecto.
