# Claude182 — conformidad entre superficies conectadas explícitamente

Tu partición180 fue revisada:3hashes coinciden y10pruebas independientes OK0omisiones0.725s, log tmp/revision_particion182.log. Codex toma tus tres archivos de partición para integración/ensayo; no volver a editarlos.

Carpeta exacta PROYECTO FINAL, verificar antes de editar. Nuevo bloque sustancial: compatibilizar las particiones de superficies diferentes que tienen conexiones de borde EXPLÍCITAMENTE declaradas. Un piso/panel/muro no puede dejar un nodo generado por el hueco sin nodo compartido en la superficie contigua. Sin una declaración de conexión, coincidir visualmente no autoriza unir.

## Archivos exclusivos nuevos
draft2model/compatibilidad_particiones.py, tests/test_compatibilidad_particiones.py, docs/COMPATIBILIDAD_PARTICIONES.md. Auxiliares tmp/claude_compatibilidad_182/. Informe seguimiento/INFORME_CLAUDE_COMPATIBILIDAD_182.md. Última escritura seguimiento/ENTREGA_CLAUDE_COMPATIBILIDAD_182.json: tarea compatibilidad_particiones_182, estado entregado/bloqueado, archivos mapaexacto de esos3archivos con SHA256 y evidencia. No editar otros archivos, configuración/operaciones/partición/lector/UI, registros Codex ni fuentes.

## API pura y contrato
compatibilizar_particiones(geometria, particiones, conexiones) -> JSON versionado no ejecutable/sin aprobación de ingeniería; ErrorCompatibilidad(ValueError). Documentar campos exactos. Particiones son resultados completos del módulo180 para hosts del mismo JSON geométrico. Reproducirlos contra sus fuentes (no confiar solo en huella recalculada) y rechazar copias alteradas, omitidas o duplicadas.

Conexiones: documento versionado con ID, lista explícita de pares de aristas fuente de dos superficies distintas, fuentes JSON revisadas y declaración ligada a geometría. Diseña campos exactos coherentes con el proyecto, fechas/identidad declarada no verificada y hashes de todo contenido. No usa red ni archivos. Referencias de aristas mediante superficie+par ordenado de vértices fuente que debe existir en contorno; permitir orientación inversa. La conexión debe ser geométricamente coincidente en un segmento de longitud positiva: conservar puntos de inicio/fin y división de ambos lados, incluidos solapes parciales. Rechazar aristas cruzadas solo en un punto, no colineales, caras repetidas, campos extra y vínculos ambiguos.

Unir únicamente nodos sobre segmentos declarados coincidentes y propagar todos los puntos de corte a todas las celdas/cadenas implicadas. Insertar puntos en las aristas correspondientes; conservar celda→pieza→host, orientación, áreas y fuentes. Nodos globales compartidos e IDs deterministas sin colisiones, trazas de alias fuente y nuevos cortes, metadatos de particiones originales y del documento de conexiones. Celdas convexas con puntos colineales son admisibles aquí: todavía no es criterio de calidad de malla. Ningún vecino puede saltarse un nodo del borde compartido. Revalidar incidencias/cadenas intrahost y coincidencia de cadenas en conexiones; dejar explícitos los bordes no conectados y límites. No crear unión mecánica entre superficies distintas sin declaración ni unir por redondeo/proximidad.

Todo se calcula en m, preserva entradas y es determinista. Reutiliza criterios computacionales existentes; aritmética exacta cuando proceda. No inventar tolerancias de ingeniería. Si dos representaciones por binary64 no acreditan coincidencia bajo criterio numérico declarado, rechazar con causa. No reparar silenciosamente ni producir compatibilidad parcial como exitosa.

## Pruebas y aceptación
Dos hosts coplanares y ortogonales con borde compartido, orientación inversa, un lado partido por cortes de un hueco y otro sin cortes, solape parcial, cadena de3hosts con propagación, varias conexiones, m/cm/mm, grandes traslaciones representables. Verificador independiente de nodos/cadenas/celdas/área, sin comparar solo con la propia implementación. Negativos: superficie/segmento ajeno, cruce puntual, aristas que no coinciden, fuente/declaración/partición alterada, duplicados/NaN/campoextra, falta de declaración nunca auto-unión. Probar determinismo y ninguna mutación.

## Integración y restricciones
Codex continúa transporte de piezas a ETABS y pruebas reales. Las barras/frame, apoyos, diafragmas, ejes, materiales/cargas/masa, calidad de malla y rigidez siguen como dependencias de integración; no decir que esta conformidad acredita eso. Registra el contrato de salida preciso para conectar configuración y frames en el siguiente incremento.

Cero API IA, cero lectura de claves, cero ETABS real ni bloqueo motor, sin instalaciones/políticas ni suite global. Tus nuevos módulos no dependen de bibliotecas no instaladas. TEMP/TMP dentro tmp. Si falta cuota guarda estado y bloqueo explícito, no éxito falso.
