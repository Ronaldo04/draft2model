# Encargo314: contrastar la regla específica de ETABS

Codex revisó313: hashes de10archivos correctos, siete pruebas correctas y45predicciones regeneradas idénticas desde el plan. No se integra aún en el libro ni se declara verificada la masa.

Dos hallazgos de revisión que cambian el siguiente paso:

1. La página128 del manual CSI instalado dice explícitamente que la regla automática descrita corresponde a la interfaz de **SAP2000**. No prueba que ETABS21 implemente exactamente esa regla.
2. Los37acuerdos de R-max incluyen las cuatro abstenciones. Sobre las41vigas no abstenidas coinciden33, exactamente como la regla primaria. No comparar37contra33con denominadores distintos ni seleccionar la variante mirando el resultado.

Fuente primaria específica localizada por Codex:
https://docs.csiamerica.com/help-files/etabs/Menus/Assign/Frame/End_Length_Offset.htm

La ayuda de ETABS distingue vigas/columnas/diagonales: para extremos de vigas utiliza columnas conectadas; indica que controla la columna inferior y no la superior. Esto difiere de sumar contribuciones de otras vigas en el predictor313. No presupongas que esta diferencia explica automáticamente los ocho desacuerdos.

## Trabajo autónomo

- Conserva313 íntegro. Lee la ayuda primaria específica, o su equivalente local instalado. Conserva URL/título y sección pertinente, sin copiar la página entera. Señala límites de versión y lo que no especifica.
- Antes del nuevo contraste, define claramente una regla314 basada en esa documentación y una clasificación geométrica de miembros. Declara que no es un ensayo ciego: ya conocemos los resultados313. Una huella no autentica un prerregistro cronológico.
- Implementa prototipo aislado y pruebas sintéticas pertinentes. Separa elementos no cubiertos por documentación (incluidas secciones, orientaciones o límites de longitud) y abstente allí. No uses pesos/offsets nativos como entradas ni constantes ajustadas a esas salidas.
- Contrasta después por extremo con lectura archivada. Informa acuerdos/desacuerdos/abstenciones de ambas reglas sobre la misma población y denominadores. En las vigas cortas compara también, solo como diagnóstico posterior, coordenadas/longitudes del plan con cualquier geometría nativa archivada: podría existir una diferencia de geometría o de tratamiento Auto; no dar por hecho ninguna causa.
- Entrega conclusión sobre si esta corrección documental reduce realmente los desacuerdos, sin prometer que lo hará. No modificar masas, libro, tolerancia, EDB, resultados ni fuentes públicas. No ejecutar ETABS ni APIs ni leer el modelo manual o credenciales. No proyectos2/3.

Solo escritura: `seguimiento/claude_ruta/extremos_etabs_314/` y marcador final `seguimiento/claude_ruta/MARCADOR_EXTREMOS_314.json`, tarea exacta `extremos_314`, estado `entrega_candidata` o `bloqueo_declarado`, mapa `archivos_permitidos_sha256`. Codex conserva integración y revisión. La fuente312 sigue congelada y su suite está ejecutándose. Respeta tu cuota; un parcial con límites es preferible a una conclusión fabricada.
