# Encargo350: políticas automáticas de nodos y subdivisión de barras

Responsable: Antigravity. Coordinación e integración: Codex. Usuario autoriza trabajo autónomo conjunto. Trabaja únicamente en:
D:/RONALDO CUCHILLA/1. RONALDO CUCHILLA/2. INGENIERÍA CIVIL DOCS AND PROJECTS/AECODE CURSOS/AECODE AI TALENT/PROYECTO FINAL

Comprueba primero que esa es la carpeta real del proyecto; no uses otra copia. No leas el historial de Codex/SQLite/JSONL ni todas las carpetas. Lee este encargo y solo los archivos necesarios. Las instrucciones locales aplicables siguen vigentes. No solicites aprobación para tareas rutinarias dentro de este alcance.

## Contexto mínimo y reparto
Draft2Model procesa planos PDF/JPG/PNG, conserva lecturas/evidencias, genera geometría y configuración versionadas, construye/analiza en ETABS e informa resultados. La autonomía aún es parcial. El usuario exige que el código automatice los procesos, y que las decisiones de ingeniería se introduzcan en la interfaz, sin depender de Codex ni de editar JSON externo.
El corte actual es349 (seguimiento/RETOMAR_ACTUAL.json). El caso3 tiene una geometría parcial, no un edificio completo, sin configuración técnica terminada. No lo proceses para este encargo.
Codex trabaja en lectura automática de parámetros/secciones/cargas y su integración web. Otro agente ES DUEÑO EXCLUSIVO de digitizacion_calibrada.py y sus pruebas/documentación. No dupliques esos trabajos.

## Archivos permitidos de escritura (lista cerrada)
- draft2model/politicas_malla_automatica.py (nuevo)
- tests/test_politicas_malla_automatica.py (nuevo)
- docs/POLITICAS_MALLA_AUTOMATICA.md (nuevo)
- seguimiento/ANTIGRAVITY_350_MALLA_ENTREGA.json (marcador final)
- seguimiento/ANTIGRAVITY_350_MALLA_INFORME.md (máximo una página)
No modificar ningún otro archivo. Usa tmp/antigravity350/ exclusivamente para temporales si hacen falta. No sobrescribir archivos del resto del equipo, no reiniciar servidores, no hacer commits/push, no tocar entregas, claves ni datos privados. No llamar APIs ni abrir ETABS. No abrir/construir modelos de los proyectos1/2/3. Solo fixtures sintéticas existentes y ejemplos propios sintéticos.

## Objetivo y ruta consecutiva
Completa los tres hitos siguientes, uno tras otro, sin esperar a Codex entre ellos. Es una implementación real y reutilizable, no solo un informe.

1. Estudia draft2model/malla_preparacion.py, plantilla_configuracion.py, modelo_estructural.py y tests/test_integracion_malla.py. Identifica cómo se exponen nodos derivados, intersecciones/subdivisiones de frames y políticas faltantes. Implementa una función pura que prepare una propuesta de políticas desde geometría/configuración y REGLAS EXPLÍCITAS del ingeniero. Reutiliza la preparación de malla; no reimplementes triangulación. Expón un contrato de reglas cerrado y documentado.

2. Automatiza la enumeración de todos los registros nodos_derivados y subdivision_frames que el programa puede calcular. Para apoyos/diafragmas permite reglas declaradas por planoZ o entidades, fuente y motivo. NO asumas z=0 como apoyo; NO asumas diafragmas por todos los niveles, restricciones de nodos nuevos ni que los extremos fijados implican continuidad física. Toda regla de herencia o política de resto libre/sin diafragma debe ser explícita, con alcance y fuente. Si faltan reglas, devuelve pendientes concretos sin inventarlos. Si dos reglas se contradicen, no elijas la primera: señala conflicto y no declares listo. Las subdivisiones geométricas pueden generarse automáticamente con los IDs/orden devueltos por el algoritmo. La aplicación al diccionario debe devolver una COPIA en borrador, nunca modificar la entrada ni heredar aprobaciones. Propón API para vista previa y otra para aplicar decisiones explícitas a la copia; el módulo no hace I/O persistente ni llamadas de red.

3. Prueba el recorrido con fixtures sintéticas: nodos de borde/hueco, superficies conectadas, cortesZ, barra que se subdivide, regla faltante, reglas contradictorias, coordenadas/unidades incorrectas, geometría o configuración origen incompatible, fuentes inexistentes, identidad/estado sintético preservados y entradas no mutadas. Incluye un caso con suficientes nodos para demostrar que una regla evita escribirlos individualmente. No requieren pruebas nativas ETABS ni suite completa. Si el sandbox Windows impide renombrar temporales, explica el fallo de entorno y ejecuta únicamente la comprobación autorizada fuera de ese aislamiento si tu herramienta lo permite; no debilites validaciones ni borres pruebas para ponerlas verdes.

## Criterios de aceptación
- Sin reglas suficientes: pendientes visibles y ningunos apoyos/diafragmas inventados.
- Con reglas explícitas suficientes: registros derivados y subdivisiones reproducibles que el validador de configuración/malla actual pueda consumir. No maquillar otros datos incompletos.
- Fuente/origen y unidades coherentes; no unir nodos por cercanía no declarada.
- Ninguna función registra aprobación, ejecuta ETABS o cambia archivos del expediente.
- Sintético sigue siendo sintético. Pruebas no equivalen a validación del piloto ni a cumplimiento normativo.

## Entrega y supervisión económica
Escribe ANTIGRAVITY_350_MALLA_ENTREGA.json SOLO AL FINAL, después de cerrar todos tus archivos. Formato: {"tarea":"350_malla","estado":"entregado" o "bloqueado","raiz":"ruta absoluta","archivos":[{"ruta":"...","sha256":"..."}],"pruebas":[{"comando":"...","resultado":"...","alcance":"sintetico"}],"limitaciones":[...],"apis_usadas":0,"etabs_usado":false}. No incluyas el hash del marcador dentro de sí mismo. Un bloqueo debe explicar lo que falta, sin alterar datos ni inventar éxito.
En el chat confirma al empezar carpeta real y archivos asignados. Al terminar responde máximo10líneas: lo implementado, pruebas, limitaciones y marcador. Codex revisará cambios y una prueba focal y hará la integración. No necesitas observar la interfaz de Codex ni responder a actualizaciones rutinarias.
