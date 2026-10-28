# Partición de superficies planas con huecos — Claude180

Confirma primero carpeta PROYECTO FINAL, no su padre. Lee instrucciones locales. Tu entrega176 está recibida (archivos_finales en lugar de archivos; Codex adaptó la sonda y revisa hashes/pruebas). Libera tus cuatro archivos del lector: Codex los integra y prueba con ETABS. No vuelvas a editarlos en este encargo.

## Problema real y objetivo
Codex ejecutó ETABS21.1/DLL1.29 sobre modelos sintéticos propios. Evidencia seguimiento/MALLA_ABERTURAS_179.json y docs/ENSAYO_MALLA_ABERTURAS.md. Piso: área neta pero advertencia mallado8.33%; inclinado: área bruta/material sobre hueco; muro: GetElm no legible. GetOpening no demuestra efecto físico. cEditArea no ofrece método público de división en DLL. No habilitar producción ni repetir ensayo.

Implementa división GEOMÉTRICA explícita de una superficie plana con todos sus huecos, para después transportar las piezas sin material sobre vacíos. Necesitamos un algoritmo general para contornos simples cóncavos/convexos y varios huecos interiores válidos, en cualquier orientación XYZ y unidades geométricas admitidas; no limitar el producto a rectángulos ni rellenar/omitir lo difícil silenciosamente. La entrada ya pasa validar_geometria0.3. No decide dimensiones máximas de elementos ni calidad/criterios de ingeniería.

## Propiedad exclusiva
NUEVOS archivos únicamente: draft2model/particion_superficies.py, tests/test_particion_superficies.py, docs/PARTICION_SUPERFICIES.md. Auxiliares/logs en tmp/claude_particion_180/. Informe seguimiento/INFORME_CLAUDE_PARTICION_180.md; marcador final seguimiento/ENTREGA_CLAUDE_PARTICION_180.json con tarea particion_superficies_180, estado entregado/bloqueado y mapa archivos:{ruta:sha256} de los tres nuevos archivos. Incluye comandos/resultados/limitaciones. Última escritura del encargo; después no editar entregados. NO tocar módulos existentes ni sus tests/contratos/config/modelo/operaciones/ejecutor/lector/UI; Codex conserva integración.

## Contrato acordado
API pura particionar_superficie(geometria, superficie_id), error ErrorParticion(ValueError). Resultado JSON determinista versionado, no ejecutable, sin aprobación de ingeniería; vínculo SHA canónico completo y huella de contenido geométrico; ID host, lista completa de huecos; nodos XYZ metros y celdas triangulares o convexas con IDs y orientación coherente con normal del host. Traces de nodos originales vs calculados (arista/intersección y parámetros), piezas→host/fuentes y cobertura de áreas bruta/huecos/neta. No modificar entrada. Campos exactos documentados.

Compartir nodos es esencial: dos celdas vecinas deben usar mismos IDs/coordenadas; no dejar puntos interiores de una arista de un vecino sin dividir esa arista (nodos colgantes). Cada arista interior debe tener exactamente dos incidencias opuestas; contornos exteriores/huecos una. Cada arista del contorno fuente debe conservarse como cadena ordenada de segmentos de la partición. No inventar vínculos entre superficies distintas: salida solo acredita partición intrahost y declara compatibilidad interhost pendiente.

Puedes usar barrido por bandas en proyección local estable (cortes por todos los vértices, regla par/impar de host y huecos) seguido de triangulación conforme. Si lo haces, agrega todos los puntos sobre fronteras compartidas antes de triangular: un trapezoide vecino no puede saltarse el nodo de inicio de un hueco. Alternativa robusta sin dependencias adicionales también válida. No instalar bibliotecas ni depender de SciPy/Shapely (no están instaladas). No redondear/ fusionar casi-coincidencias silenciosamente: casos numéricamente ambiguos se rechazan con causa conservando alcance pendiente. Reutilizar validación estricta y criterios numéricos; no inventar tolerancias de ingeniería.

## Aceptación verificable
Pruebas analíticas y negativas: horizontal/vertical/inclinado, reversión de contornos, m/cm/mm, cóncavo sin hueco, varios huecos de formas distintas, vértices colineales, huecos con coordenadas de barrido compartidas, cambio de fuente y entradas no válidas, grandes traslaciones representables y rechazos de inestabilidad. Comprueba independientemente áreas, orientación, ausencia de intersección positiva de celdas con huecos, no solapes, conectividad/aristas/cadenas y determinismo. No limitarse a igualdad con salida del propio algoritmo. Mantener fuentes/entrada intactas. Todo resultado no verificable se rechaza, no se publica como partición válida.

Al terminar registra pendientes para Codex: asignaciones/material/ejes/cargas/masa de las piezas, conexiones interhost/frame y revisión de calidad/mallado, prueba ETABS y reapertura/lectura. Tu módulo NO demuestra eso ni ingeniería.

## Límites de uso
Cero llamadas API de cualquier proveedor, no leer credenciales. Google/OpenAI reservados exclusivamente por usuario para planos. No ETABS real ni bloqueo motor ni instancia usuario. No políticas Windows, instalaciones ni suite global. Usa .venv/Scripts/python.exe con TEMP/TMP en tmp del proyecto. Si falta cuota conserva estado y marcador bloqueado con causa; no declarar finalización falsa.
