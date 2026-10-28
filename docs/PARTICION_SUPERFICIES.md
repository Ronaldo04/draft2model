# Partición geométrica de superficies con huecos

Estado al 20 de octubre de 2026. Módulo nuevo: [`draft2model/particion_superficies.py`](../draft2model/particion_superficies.py). Pruebas: [`tests/test_particion_superficies.py`](../tests/test_particion_superficies.py).

Divide de forma **geométrica, explícita y conforme** una superficie plana de la geometría 0.3 con todos sus huecos. El objetivo es transportar después piezas sin material sobre los vacíos.

**Motivo:** ETABS 21.1 mostró que el panel inclinado rellena el hueco (`seguimiento/MALLA_ABERTURAS_179.json`, `docs/ENSAYO_MALLA_ABERTURAS.md`). La DLL no ofrece división pública en `cEditArea`.

**Qué no hace este módulo:**
- No es una malla de ingeniería ni decide tamaño de elemento o calidad.
- No asigna sección, material, ejes, cargas ni masa.
- No prueba ETABS y no es ejecutable.

## API

```python
from draft2model.particion_superficies import particionar_superficie, ErrorParticion
resultado = particionar_superficie(geometria_0_3, "S1")   # dict JSON determinista; ErrorParticion(ValueError) si no
```

**Entrada:**
- La geometría debe ser `version_contrato == "0.3.0"` y consistente según `validacion_geometria.validar_geometria`; otra versión se rechaza.
- Se usan las coordenadas en metros de `geometria_m`, de modo que m, cm y mm son equivalentes.
- La entrada no se modifica y la función no tiene efectos.

## Contrato de salida (`draft2model.particion_superficie` 0.1.0)

Campos exactos:

| Campo | Contenido |
|---|---|
| `contrato`, `version_contrato`, `ejecutable: false`, `aprueba_ingenieria: false`, `aviso` | identidad y límites |
| `origen` | `contrato_geometria`, `version_geometria` (0.3.0), `sha256_geometria_canonica` (JSON canónico completo de la entrada), `huella_contenido` (de `validar_geometria`), `unidad_longitud_fuente`, `datos_sinteticos` |
| `superficie` | `id`, `vertices`, `papel_geometrico`, `procedencia`, `normal_unitaria`, `area_bruta_m2` |
| `huecos` | lista **completa** de las aberturas del host, en el orden fuente: `id`, `vertices`, `procedencia`, `area_m2` |
| `proyeccion` | `eje_descartado`, `ejes_proyectados`, `origen_m`, `signo_orientacion` y `aritmetica` («racional exacta desde binary64») |
| `nodos` | `id`, `xyz_m` y `traza`. La traza es `{"tipo":"original","vertice"}` o `{"tipo":"sobre_arista","contorno","arista","desde","hasta","t","t_aprox","origen_calculo"}`, con `t` racional exacto en texto `num/den` |
| `celdas` | `id`, `nodos` (orientados según la normal del host), `tipo` (`triangulo`/`convexa`), `franja`, `area_m2` y `pieza_de` (ID del host) |
| `cadenas_contorno` | por cada arista fuente (host y huecos, en orden): `contorno` (`superficie:ID`/`hueco:ID`), `arista`, `desde`, `hasta` y `nodos` (cadena ordenada) |
| `cobertura` | `area_bruta_m2`, `area_huecos_m2`, `area_neta_m2`, `area_celdas_m2`, `igualdad_exacta_proyectada`, `area_proyectada_exacta` (doble área racional) y `factor_area_real` |
| `comprobaciones` | recuentos de celdas, nodos, nodos originales, aristas interiores y de frontera, `nodos_colgantes: 0`, aristas fuente conservadas y orientación |
| `compatibilidad_interhost` | siempre «pendiente» |
| `pendientes` | lista de integración |
| `huella_particion` | SHA256 del JSON canónico del resultado sin este campo |

**Identificadores:**
- Un nodo original conserva el ID del vértice fuente.
- Un nodo calculado se nombra `S1#n<k>` y una celda `S1#c<k>`. El carácter `#` no existe en los IDs geométricos, así que no hay colisiones.
- El orden es determinista.

## Algoritmo

1. **Proyección exacta:**
   - traslación al primer vértice del host y descarte del eje dominante de su normal, el mismo criterio que `_poligono`;
   - sin escalado, en `fractions.Fraction` a partir de los binary64 de entrada;
   - dentro del plano no hay tolerancias.
2. **Barrido por franjas** en todas las abscisas de vértices del host y de los huecos:
   - en cada franja, las aristas no verticales activas se ordenan exactamente en el punto medio;
   - la regla par/impar (host y huecos) da los trapecios interiores.
3. **Conformidad:**
   - antes de cerrar una celda se añaden **todos** los nodos de sus lados verticales: vértices sobre esa recta y cortes de aristas que la atraviesan;
   - así, un trapecio no puede saltarse el nodo de inicio o fin de un hueco ni un nodo de la franja vecina;
   - las celdas son convexas y pueden tener ángulos de 180° en esos nodos.
4. **Nodos:**
   - todo nodo calculado está sobre exactamente una arista fuente, con parámetro t racional;
   - su XYZ se interpola en 3D sobre esa arista con un único redondeo, por lo que los nodos no se desplazan fuera de su arista;
   - no hay puntos de Steiner interiores.
5. **Verificación previa a publicar:** si cualquiera falla, `ErrorParticion` y ningún resultado.
   - la suma **exacta** de áreas proyectadas de las celdas es igual a la bruta menos los huecos;
   - cada celda tiene área positiva, es convexa, está orientada según la normal del host, su centroide está dentro del host y fuera de los huecos;
   - aristas dirigidas únicas: interior con dos incidencias opuestas, frontera con una;
   - cada arista fuente es una cadena ordenada de segmentos de frontera, y la frontera es exactamente la unión de esas cadenas;
   - ningún nodo está dentro de una arista de celda (sin colgantes);
   - nodos distintos siguen siendo distintos en binary64;
   - área de Newell positiva y mayor que el criterio computacional existente (`epsilon_relativo_computacional` del host · escala²).

**Casos rechazados con causa** (no se redondean ni se fusionan):
- vértices que coinciden en la proyección;
- un punto calculado sobre dos aristas;
- paridad impar o aristas superpuestas en una franja;
- colapso a binary64;
- celdas degeneradas tras el redondeo;
- entradas que `validar_geometria` no acepta (inestabilidad numérica, huecos exteriores, cruzados o no coplanares, etc.).

Los epsilon son criterios de representabilidad binary64, **no tolerancias de ingeniería**.

## Pruebas (independientes del algoritmo)

```powershell
$env:TEMP=(Resolve-Path tmp/claude_particion_180).Path; $env:TMP=$env:TEMP
.venv/Scripts/python.exe -m unittest -v tests.test_particion_superficies
```

**Verificadores propios** (no usan funciones del módulo):
- áreas de Newell 3D;
- base ortonormal propia del plano, distinta de la proyección por eje;
- recorte Sutherland–Hodgman para intersecciones de celdas con huecos y solapes entre celdas;
- incidencias de aristas, cadenas monótonas sobre cada arista fuente, nodos colgantes en XYZ y trazas (cada nodo calculado sobre su arista en `t_aprox`);
- entrada intacta y determinismo.

**Casos:**
- horizontal, vertical e inclinado, con el host o los huecos invertidos;
- equivalencia m, cm y mm;
- cóncavos sin hueco (L, peine, estrella) en tres orientaciones;
- cuatro huecos de formas distintas (triángulo, rectángulo, hueco cóncavo en L, pentágono), con abscisas de barrido compartidas con el host y entre huecos;
- vértices colineales, y otra superficie sin vínculos;
- traslaciones de 1e5 y 1e6 m, y el rechazo de una inestable (1e12 m con extensión milimétrica);
- cambio de vértice o de procedencia (cambian SHA, huella y huella de partición);
- entradas inválidas: versión 0.2, superficie inexistente, ID no textual, hueco exterior, cruzado o no coplanar, no objeto, nulo;
- **sensibilidad:** si se omiten los nodos laterales, el módulo rechaza la partición; los verificadores detectan un nodo colgante, una orientación invertida, una celda omitida y un nodo fuera de su arista.

Resultado: **10 OK, 0 omitidas**. Log en `tmp/claude_particion_180/pruebas.log`.

## Límites y pendientes para Codex

- **Conformidad intrahost solamente:** la compatibilidad de nodos con superficies vecinas, muros y frames está pendiente; el módulo no inventa vínculos.
- **Integración:** asignación de sección o material, ejes locales, cargas y masa de las piezas; trazabilidad pieza → host en la configuración y las operaciones.
- **Calidad de malla:** proporciones, ángulos de 180° por conformidad y tamaño máximo, según criterios declarados. Las franjas pueden ser alargadas.
- **ETABS:** transporte de las piezas (`AddByPoint` por celda, sin material sobre los huecos), guardado, reapertura y relectura independiente.
- **Lo que no demuestra:** ni efecto estructural, ni rigidez, ni mallado ETABS, ni ingeniería.
