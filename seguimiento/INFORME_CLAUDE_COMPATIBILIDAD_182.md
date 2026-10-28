# Informe Claude — compatibilidad de particiones 182

Fecha: 20 de octubre de 2026. Carpeta comprobada: `…/AECODE AI TALENT/PROYECTO FINAL`.

**Restricciones cumplidas:**
- Cero llamadas a API y ninguna credencial leída.
- Sin ETABS real, sin instalaciones ni cambios de políticas, sin suite global.
- La partición 180 no se editó (SHA `fcb0ee3f…` intacto).

**Entregables** (solo archivos nuevos):
- `draft2model/compatibilidad_particiones.py`
- `tests/test_compatibilidad_particiones.py`
- `docs/COMPATIBILIDAD_PARTICIONES.md`

**Método:**
- **Particiones:** se reproducen desde la fuente con igualdad canónica.
- **Documento de conexiones** versionado (`draft2model.conexiones_borde` 0.1.0), con campos exactos, ligado a la geometría y con fuentes y declaración por huella.
- **Coincidencia:** aristas exteriores colineales con solape de longitud positiva, según el criterio ε existente evaluado en aritmética racional.
- **Unión:** solo en solapes declarados. Los puntos ambiguos se rechazan.
- **Propagación:** hasta un punto fijo, a cadenas y celdas (incluidos varios hosts).
- **Verificación antes de publicar:** incidencias, frontera igual a cadenas, áreas y orientación conservadas, y cadenas compartidas idénticas.

**Pruebas** (TEMP/TMP = `tmp/claude_compatibilidad_182`):

| Comando | Resultado | Log |
|---|---|---|
| `.venv/Scripts/python.exe -m unittest -v tests.test_compatibilidad_particiones` | 8 OK, 0 omitidas | `pruebas.log` |
| `.venv/Scripts/python.exe -m unittest tests.test_particion_superficies` | 10 OK | `regresion_particion.log` |

**Ajustes durante las pruebas** (de las pruebas, no del módulo):
- El primer caso «ambiguo» quedaba fuera del solape; ahí no unir es lo correcto, y el caso se replanteó dentro del solape.
- Un control con una arista disjunta fue rechazado correctamente; se corrigió el control.

**Dependencias para Codex:**
1. Frames o barras sobre `conexiones[].nodos_compartidos` y bordes libres.
2. Apoyos, diafragmas, ejes, material, cargas y masa de las piezas.
3. Calidad de malla con criterios declarados.
4. Transporte ETABS de piezas y nodos únicos, guardado, reapertura y relectura.
5. Verificación real de la unión estructural.

**Lo que no acredita:** esta conformidad geométrica no acredita ninguna de esas dependencias.
