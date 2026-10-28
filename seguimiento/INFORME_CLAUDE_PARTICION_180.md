# Informe Claude — partición de superficies 180

Fecha: 20 de octubre de 2026. Carpeta comprobada: `…/AECODE AI TALENT/PROYECTO FINAL`.

**Restricciones cumplidas:**
- Cero llamadas a API y ninguna credencial leída.
- Sin ETABS real, sin instalaciones ni cambios de políticas, sin suite global.
- Los cuatro archivos del lector quedan liberados y no se editaron.

**Entregables** (solo archivos nuevos):
- `draft2model/particion_superficies.py`
- `tests/test_particion_superficies.py`
- `docs/PARTICION_SUPERFICIES.md`

**Algoritmo:**
- validación 0.3 existente y proyección exacta (`Fraction`, sin escalado) quitando el eje dominante de la normal del host;
- barrido por franjas en todas las abscisas de vértices, con la regla par/impar host-huecos;
- trapecios convexos que incorporan todos los nodos de sus lados verticales (sin nodos colgantes);
- nodos solo sobre aristas fuente, con t exacto y XYZ interpolado.

**Verificación interna previa a publicar:**
- área exacta igual a bruta menos huecos;
- incidencias de aristas, cadenas por arista fuente y ausencia de colgantes;
- orientación según la normal, centroides fuera de los huecos;
- colapso a binary64 y degeneración según el epsilon existente.

Si algo falla se lanza `ErrorParticion` y no hay resultado parcial.

**Pruebas:** `.venv/Scripts/python.exe -m unittest -v tests.test_particion_superficies` (TEMP/TMP = `tmp/claude_particion_180`) → 10 OK, 0 omitidas, log `tmp/claude_particion_180/pruebas.log`.

Los verificadores son independientes: Newell 3D, base propia, Sutherland–Hodgman, incidencias, cadenas, colgantes y trazas. La sensibilidad está probada: omitir los nodos laterales se rechaza, y las salidas defectuosas se detectan.

**Pendientes para Codex:**
1. Asignación de sección o material, ejes, cargas y masa de las piezas, con trazabilidad pieza → host.
2. Compatibilidad interhost: nodos compartidos con superficies vecinas, muros y frames (no acreditada).
3. Revisión de calidad de malla con criterios declarados: franjas alargadas y ángulos de 180° por nodos de conformidad.
4. Transporte ETABS de las piezas sin material sobre los huecos, guardado, reapertura y lectura independiente.

**Lo que no demuestra:** el módulo no demuestra ingeniería ni el efecto en ETABS.
