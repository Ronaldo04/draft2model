# Interfaz de Draft2Model por etapas — revisión344

La aplicación principal organiza las operaciones en siete espacios. Cambiar de
etapa permite consultar otra parte del trabajo; no ejecuta una API, no aprueba
un modelo ni marca automáticamente un proceso como terminado.

| Etapa | Qué se consulta o realiza | Revisión del ingeniero |
|---|---|---|
| Proyecto y planos | Registro y comprobación documental de originales | Totalidad de las láminas y autorización de uso |
| Lectura de planos | Plano, datos detectados y evidencia de cada lectura | Lecturas dudosas, datos omitidos y unidades |
| Geometría y modelo3D | Versiones geométricas, vista interactiva y editor | Posiciones, conexiones, niveles y aberturas |
| Revisión de ingeniería | Configuración, materiales, secciones, cargas e hipótesis | Datos técnicos ausentes y representación estructural |
| Construcción en ETABS | Construcción, archivo conservado y relectura | Correspondencia con la configuración revisada |
| Análisis y comprobaciones | Casos, tablas y controles implementados | Advertencias y alcance de las comprobaciones |
| Informe y entrega | Informe y panel de resultados | Conclusiones, hipótesis y limitaciones |

Cada espacio muestra el propósito del procesamiento, la intervención técnica
necesaria y el resultado esperado. Las herramientas adicionales se despliegan
cuando se necesitan. Los estados del menú describen lo que está abierto, sin
usar la mera existencia de un archivo como prueba de aceptación funcional.

## Corregir datos dentro de la aplicación

En geometría o configuración, abrir una versión conservada y elegir un grupo
en «Editar datos de ingeniería». Seleccionar el registro y corregir los campos.
Se pueden preparar registros nuevos o duplicar uno para editarlo; sus valores
deben revisarse. Quitar un registro afecta al borrador del formulario.

Los cambios se preparan sin sobrescribir el expediente. Para conservarlos hay
que completar la identidad declarada, fecha y motivo de revisión y guardar
una nueva versión. La validación del servidor sigue comprobando referencias,
coherencia y datos pendientes. Las aprobaciones no se trasladan al contenido
modificado. La vista JSON queda como opción técnica avanzada.

El editor cubre campos presentes en las versiones y plantillas básicas para
crear datos. Faltan formularios especializados para algunas estructuras de
configuración avanzadas; no se acredita todavía que cualquier configuración
pueda crearse íntegramente mediante formularios. No se sustituye ese pendiente
por una afirmación de interfaz terminada.

## Vista3D

El visor representa los vértices y superficies de la versión geométrica,
incluidas sus aberturas. Permite girar, acercar y cambiar a planta. Puede añadir
columnas y vigas de una configuración abierta cuando corresponde a esa misma
versión geométrica. Normaliza m/cm/mm a metros y no modifica los archivos.

Una edición del formulario se identifica como borrador sin guardar. La vista
del sistema no es una captura nativa de ETABS ni prueba de su relectura. El
expediente3, con lecturas pero sin geometría generada, muestra ese estado vacío;
no reutiliza el modelo de otro proyecto.

## Estado del procesamiento autónomo

La organización visual no completa la reconstrucción automática. El proyecto3
produjo130lecturas pendientes, con cobertura parcial de las cuatro láminas.
Todavía no produjo geometría ni análisis ETABS.

La revisión345 incorpora un recorrido nuevo en la etapa3: preparación automática
de los originales, lectura de relaciones mediante OpenAI o Google, resolución
de coordenadas y registro de una geometría en borrador cuando los datos son
suficientes. La interfaz muestra el avance sin consultar a Codex. Conserva cada
intento, cuenta también los fallidos y no reenvía un trabajo ya iniciado.

El solucionador detecta componentes sin medidas, unidades desconocidas y cadenas
contradictorias. Unifica puntos que las medidas sitúan exactamente en la misma
posición; no acerca puntos por una tolerancia inventada ni rellena dimensiones.
Las simulaciones conservan su marca y no se importan como geometría real.

El primer intento real de este recorrido en proyecto3 recibió HTTP503 de Gemini.
No produjo lectura ni geometría y no se reintentó automáticamente. Las pruebas
sintéticas positivas no sustituyen esa verificación real. Falta procesar proyectos
de más de8páginas mediante lotes enlazados, completar la configuración automática
y conectar la continuación tras la revisión técnica hasta el informe.

La entrega331 ya archivada se conserva sin modificaciones. La interfaz344 se
integra en las fuentes principales con comprobaciones focales, no con una nueva
afirmación de validación total del sistema.
