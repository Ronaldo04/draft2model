# Reanudar el trabajo

En el repositorio de desarrollo, leer primero `seguimiento/RETOMAR_ACTUAL.json` y después el checkpoint que indique. Ese registro contiene estado, responsables, procesos, evidencias, restricciones y el siguiente paso exacto. No reconstruir el historial ni repetir pruebas aceptadas sin cambios relevantes.

Este documento se mantiene estable para no cambiar la huella de distribución durante pruebas o empaquetado. Registrar avances en `seguimiento/`; actualizar el puntero allí. Las revisiones históricas se conservan aparte.

Antes de continuar consultar cuota y ejecutar `.venv/Scripts/python.exe seguimiento/estado_claude.py`. Revisar componentes nuevos solo cuando existan; Computer Use únicamente para coordinación necesaria. Un marcador no prueba calidad: contrastar archivos y una comprobación focal.

Con≤5%de cuota no iniciar tareas pesadas. Con≤1%guardar novedades y terminar sin GUI/pruebas/delegaciones. No usar reset manual automáticamente ni prometer un corte porcentual exacto. Al recuperar margen seguir el checkpoint, conservando los procesos existentes hasta verificar su estado real. No relanzar por reinicio de cuota ni declarar goal completo por agotamiento.

Si se consulta una distribución archivada sin los registros internos de seguimiento, usar [ENTREGA_AECODE.md](ENTREGA_AECODE.md) y [GUIA_REPRODUCIBLE.md](GUIA_REPRODUCIBLE.md). La presencia de fuentes o manifiestos no acredita por sí sola aceptación funcional ni ingeniería.
