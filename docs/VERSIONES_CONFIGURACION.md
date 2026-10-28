# Configuraciones estructurales versionadas

`python -m draft2model configuracion --raiz data/private --caso CASO importar --entrada config.json` conserva una configuración en borrador dentro de `configuraciones_estructurales/<uuid>/`. Consultar con `consultar --version UUID`. `revisar` exige propuesta JSON completa en borrador, revisor/fecha/motivo; `aprobar` exige además --huella-esperada y --alcance. La ayuda de cada operación muestra los argumentos.

Las funciones importar/consultar/revisar/aprobar de draft2model.gestion_configuracion reutilizan comprobar_configuracion y la evidencia geométrica vigente. Cada operación publica una carpeta nueva: configuracion.json, version.json y, solo en importaciones, los bytes exactos de fuente_importada.json. Los metadatos contienen huellas de datos y de contenido, registro de operación y vínculo al padre por SHA256 de configuración y metadatos. La consulta recorre la cadena completa y vuelve a contrastar la geometría y originales actuales. No se reescriben las versiones anteriores.

Importar no acepta una aprobación externa como autorización. Una aprobación propia se registra como hija y no modifica parámetros. Una revisión posterior conserva identidad/naturaleza y vuelve a borrador sin heredar aprobación. Se bloquea aprobar con faltantes, con otra huella o con geometría sin aprobación vigente. Una aprobación de configuración no aprueba el modelo generado ni el informe. Revisor y competencia son declaraciones no autenticadas.

Las huellas detectan alteraciones parciales; no protegen contra reescritura deliberada coherente de toda la evidencia. No hay bloqueo de un editor externo entre comprobación y publicación: los consumidores deben recomprobar antes de aplicar y al terminar. La plantilla y fuentes de la configuración siguen siendo referencias declaradas; el ejecutor comprobará sus bytes al consumirlos.

Pruebas: cinco recorridos de versiones/aprobación/revisión, faltantes, huella incorrecta, importación aprobada, metadatos/padres alterados y originales cambiados. Son ensayos sintéticos sin operación ETABS.
