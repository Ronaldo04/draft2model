# Triángulos conformes y ensayo ETABS183

`triangular_particion(geometria, particion)` reproduce la partición desde su fuente y exige igualdad canónica completa. Convierte cada celda convexa en triángulos mediante corte de orejas, conservando todos los vértices, incluidos los colineales de los bordes compartidos. El cálculo de orientación y conservación de área proyectada usa fracciones exactas de los valores binary64. Cada segmento del contorno tiene una incidencia y cada diagonal interior dos opuestas; una celda no triangulable sin omisiones se rechaza.

La salida `draft2model.triangulacion_particion 0.1.0` conserva nodos XYZ, trazas, cadenas de contorno, huella de partición y fuente; añade triángulos con referencia a celda y anfitriona. Permanece no ejecutable y sin aprobación de ingeniería. No decide apoyos, tamaño o calidad de elementos, ejes, sección ni cargas.

## Ensayo real183

Se generaron las tres orientaciones del ensayo179, ahora con12nodos y12triángulos explícitos por superficie. `scripts/ensayar_malla_aberturas_etabs.ps1 -ParticionesJson ...` creó nodos CSI únicos y cada triángulo mediante `AddByPoint`, sin agregar una anfitriona llena ni un objeto Opening superpuesto. El EDB de cada caso se guardó antes de generar el modelo de análisis; no se ejecutó el solver. Instancia propia36380, cierre confirmado con retorno0.

| Caso sintético | Elementos nativos | Área neta nativa | Área de elementos dentro del hueco |
| --- | ---: | ---: | ---: |
| Piso horizontal | 34 | 11m² | 0 |
| Muro vertical | 12 | 11m² | 0 |
| Panel inclinado y=z | 12 | 11√2m² | 0 |

Todas las lecturas GetElm respondieron0. El diagnóstico de coordenadas, planos, orientación y topología de los elementos nativos no encontró solapes positivos, bordes interiores sin pareja, nodos colgantes, nombres distintos en una misma coordenada, elementos invertidos ni no convexos. No se observó archivo WRN en esta carpeta. Esto resuelve las comprobaciones geométricas fallidas del ensayo179; **no demuestra calidad de malla, comportamiento estructural, cargas ni conformidad entre anfitrionas diferentes**.

Evidencias: `seguimiento/MALLA_PARTICION_183.json`, `tmp/particion183/registro.json`, `evaluacion_geometrica_completa.json` y `tmp/triangulaciones183.json`. Los controles negativos del diagnóstico detectan bordes abiertos, nodos colgantes, solapes, inversión y coordenadas contradictorias; seis pruebas focales combinadas con triangulación pasan. La evaluación puede repetirse con `scripts/evaluar_malla_aberturas_etabs.py`, usando otra ruta de salida para conservar resultados previos.

## Integración pendiente

El ensayo es sintético y usa sección/material de prueba. Falta conectar configuración revisada, compatibilidad entre hosts, apoyos/diafragmas de nodos calculados, barras, propiedades/ejes/cargas/masa, ejecutor normal y registro del modelo. Ese bloque está asignado a Claude en el encargo184; Codex conserva revisión, ensayo real y cierre. El módulo por sí solo no habilita el recorrido de producción ni prueba el proyecto de referencia.
