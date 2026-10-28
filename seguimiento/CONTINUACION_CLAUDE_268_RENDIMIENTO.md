# Continuación268 — rendimiento medido y prueba de rutas

El ensayo puro terminó; no es propuesta de reiniciar tu cadena. Conserva su mismo handle hasta resultado terminal.

## Preparación de malla

Codex revisó el candidato `tmp/candidato_cache_malla_267/cache_malla_pura.py`, probó9casos propiosOK y lo envolvió alrededor de la función REAL sin modificar producto. `seguimiento/ENSAYO_CACHE_MALLA_267.json` conserva fuentes estables del modelo0f372713 y geometría25ef9467:

- Primera preparación:352.2943865s.
- Segunda, mismos inputs completos:0.480874s.
- Igualdad completa de dict y SHA de salida:39635dbc…bdef2 en ambas.
- Entrada retenida6.749.689bytes;1miss/1hit. No hubo ETABS ni API.

Integra este candidato en el producto, revisándolo: módulo dentro de `draft2model`, import relativo y decorador sobre `malla_preparacion.preparar_malla`; ningún import desde tmp. Portar pruebas al árbol normal. No decorar aprobación, lectura de archivos, evidencia, EDB ni planes con dependencias externas. Mantener todas las comprobaciones de fuentes/huellas y la revisión262; solo se reutiliza una función pura con igualdad de TODO el JSON de geometría y configuración (revisión incluida), antes/después, bytes sellados y copia independiente. Errores/valores noJSON no se cachean. LRU acotado, sin estado persistido, TTL ni confianza por mtime.

El candidato tiene2entradas/64MiB; el caso conserva3modelos históricos, por lo que un listado que los recalcula podría expulsar el primero repetidamente. Puedes ajustar justificadamente el número de entradas dentro del mismo presupuesto de64MiB, con pruebas de expulsión; no confundir ese presupuesto con RSS total. Primero mide y preserva valores. No declarar aceleración de todo el recorrido por el tiempo de esta función.

Pruebas de integración: planes completos iguales antes/después (horizontal/inclinado/vertical/conectado y líquido), invalidez tras cambio geométrico/configuración/revisión, aislamiento de consumidores y regresiones. Las pruebas que parchean internals para mutar DURANTE cálculo deben forzar explícitamente cache frío para ejercitar esa rama; conservar sus aserciones. Revisa `tests/test_malla_rendimiento_246.py`. No omitir pruebas ni relajar validaciones para hacer pasar cache.

## Copia267

La verificación completa sobre fuentes congeladas terminó:1335Python en1359.901s, un único error de `os.path.relpath` entre TEMP C: y cwd D:,1334 restantes sin error/omisión;32archivosNode pasaron sin omisiones, pipcheck/CLI/sondaPSOK, fuentes estables. La misma prueba fallida pasó separadamente con TEMP/TMP en D: existente (1OK0.320s). `seguimiento/REVISION_COPIA_267.json` conserva ambos resultados; no reetiquetar la suite original como verde ni repetirla ahora.

Corrige la portabilidad de `tests/test_adaptador_etabs.py::DobleTests.test_trabajo_relativo_no_rompe_rutas_del_subproceso`: su fixture relativa debe estar en la misma unidad del cwd, aunque TEMP general sea otra. Mantener el propósito de probar rutas relativas reales, sin mockear os.path.relpath ni convertirlo en skip. Ejecutar solo esa prueba focal en condiciones C:/D:. Esta es corrección del harness, no fallo observado del producto.

Mantén las tareas de cierre267 (incluido cierre propio del analizador general), luego piloto completo/panel/informes/guía/entrega. No nuevas APIs. No duplicar el análisis ya aceptado ni los contrastes de agua ya hechos. Codex sigue revisión; candidato268 queda entregado para que tú seas responsable de integración en archivos existentes.

## Hallazgo posterior de revisión independiente

Antes de aceptar reglas de cortante, revisar `seguimiento/HALLAZGO_PESO_SISMICO_268.json`: el runner describe P desde masa por piso N1–N4, pero toma el registro calculado filtrando coordenadas de nudos de AssembledJointMass. La nueva tabla nativa por pisos da488,7375 kN·s²/m y4792,8776kN; el registro usa534,1606 y5238,3261kN. Con diafragmas rígidos, la cota del nudo al que ETABS informa la masa no demuestra su piso físico (tu propio hallazgo). Vincular la tabla aceptada al mismo análisis/EDB y usar selección explícita, o abstener la regla afectada; no aumentar tolerancias. La diferencia total0,127% del libro sigue abierta aparte.

Codex verificó también igualdad completa de planes del candidato puro:2pruebas/4geometrías y líquidos en9,528s. `seguimiento/ANEXO_CASO_268_PLAN.json` identifica un pendiente de entrega: ZIP fuente excluye caso privado; solicitudes históricas usan rutas absolutas. No reescribir recibos para hacerlos portables. Codex prepara el anexo por separado y no toca tus archivos.

Actualización: Codex creó el anexo candidato274miembros, verificó6originales reubicados y13indicadores normalizados desde filas CSI (`REVISION_ANEXO_268.json`, `REVISION_NORMALIZACION_268.json`). Falta informe final y reproducción funcional. El balance propio `BALANCE_MASA_GRAVEDAD_268.json` localiza el desfase en CM (peso propio+D): libro4998,092712kN vsETABS4991,2246kN, diferencia6,868112kN. Masa nativa*g5381,170973kN vsCM+0,25CV+CAGUA5381,169300kN, delta0,001673kN; no igualdad exacta ni causa demostrada. Investigar libro/geometría/cargasD/transporte, sin relajar tolerancias ni repetir API remotas. No tocar seguimiento/exportar_caso_268.py ni su test/guía: reserva Codex independiente hasta revisión.
