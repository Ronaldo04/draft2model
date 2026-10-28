# Compatibilidad entre particiones con conexiones de borde explícitas

Estado al 20 de octubre de 2026. Módulo: [`draft2model/compatibilidad_particiones.py`](../draft2model/compatibilidad_particiones.py). Pruebas: [`tests/test_compatibilidad_particiones.py`](../tests/test_compatibilidad_particiones.py).

Hace conformes las particiones del módulo 180 de superficies **distintas** en los bordes que un documento declara explícitamente como conectados. Un nodo que un hueco genera en un borde compartido aparece también en la superficie contigua: ningún vecino se salta un nodo del borde compartido.

**Qué no hace:**
- Sin declaración no hay unión, aunque los bordes coincidan visualmente.
- No es ejecutable ni tiene aprobación de ingeniería.
- No acredita frames, apoyos, diafragmas, ejes, material, cargas, masa, calidad de malla ni rigidez.

## API

```python
from draft2model.compatibilidad_particiones import compatibilizar_particiones, huella_conexiones, ErrorCompatibilidad
resultado = compatibilizar_particiones(geometria_0_3, particiones, documento_conexiones)
```

- **`geometria`:** JSON geométrico 0.3 consistente. Las coordenadas se toman en metros de `geometria_m`, por lo que m, cm y mm son equivalentes.
- **`particiones`:** lista de resultados completos de `particion_superficies.particionar_superficie`, uno por host del mismo JSON. Cada uno se **reproduce** desde la fuente y se exige igualdad canónica exacta. Se rechazan copias alteradas, de otra fuente, duplicadas, una lista vacía y la falta de una partición que alguna conexión necesita.
- **Pureza:** sin red, archivos ni ETABS. Las entradas no se modifican y el resultado es determinista.

## Documento de conexiones (`draft2model.conexiones_borde` 0.1.0)

Campos exactos (cualquier campo extra se rechaza):

```json
{"contrato": "draft2model.conexiones_borde", "version_contrato": "0.1.0", "id": "CX1",
 "geometria": {"sha256_geometria_canonica": "<SHA256 del JSON canónico completo>", "huella_contenido": "<huella de validar_geometria>"},
 "conexiones": [{"id": "C1", "a": {"superficie": "S1", "desde": "VA", "hasta": "VB"},
                 "b": {"superficie": "S2", "desde": "VB", "hasta": "VA"}, "fuente": "F1"}],
 "fuentes": [{"id": "F1", "descripcion": "...", "referencia": "...", "sha256": "<64 hex>"}],
 "declaracion": {"declarado_por": "...", "fecha": "AAAA-MM-DD", "identidad": "declarada_no_verificada",
                 "alcance": "...", "huella_conexiones": "<huella_conexiones(documento)>"}}
```

- **`huella_conexiones`:** SHA256 del JSON canónico del documento sin `declaracion`. Cualquier cambio posterior invalida la declaración.
- **Aristas:** cada una es superficie + par **consecutivo** de vértices de su contorno **exterior**, en cualquier orientación (se informa `directa` / `inversa`). Las aristas de huecos no se conectan.
- **Se rechazan:**
  - una superficie inexistente o un segmento que no es arista;
  - la misma superficie en ambos lados;
  - un par de caras repetido;
  - IDs repetidos, una fuente inexistente o un SHA de fuente inválido;
  - NaN, una fecha inválida o una identidad distinta de `declarada_no_verificada`;
  - un documento no ligado a la geometría.

## Coincidencia y unión

**Criterio de coincidencia:** es el criterio computacional existente, `epsilon = max(1e-12, 64·ulp(coordenada_máxima)/escala)`, con escala igual a la mayor distancia entre los cuatro extremos. Se rechaza si `epsilon > 1e-6`.
- Se evalúa en **aritmética racional exacta**: distancia² de los extremos de b a la recta de a ≤ (ε·escala)².
- El solape es el intervalo paramétrico sobre a con longitud > ε·escala.
- Se rechazan el contacto en un punto, el cruce puntual, las aristas no colineales y las disjuntas.

**Unión:**
- Solo se unen nodos de las cadenas de contorno situados en el solape declarado.
- Dos nodos con el mismo parámetro exacto se unifican (alias; representante = ID menor), solo si su distancia XYZ ≤ ε·escala.
- Dos puntos distintos más cercanos que el criterio se **rechazan como ambiguos**: no se fusionan.
- Un vértice fuente común a dos superficies es el mismo nodo por identidad de fuente, no por proximidad.

**Propagación:**
- Hasta un punto fijo, todo nodo del solape se inserta en la cadena y en la celda frontera de la otra superficie. Esto incluye cadenas de tres o más hosts; por ejemplo, de S1 a S3 a través de S2 sin conexión directa.
- La inserción es colineal, conserva área y orientación, y la celda pasa a `convexa`, con nodos colineales admitidos.

**Verificación antes de publicar:** cualquier fallo lanza `ErrorCompatibilidad` sin resultado parcial.
- Por superficie: aristas dirigidas únicas, como mucho dos incidencias, frontera igual a la unión de las cadenas, área y orientación de cada celda conservadas.
- Por conexión: ambas cadenas contienen **la misma lista ordenada** de nodos en el solape.

## Contrato de salida (`draft2model.compatibilidad_particiones` 0.1.0)

| Campo | Contenido |
|---|---|
| `contrato`, `version_contrato`, `ejecutable: false`, `aprueba_ingenieria: false`, `aviso` | identidad y límites |
| `origen` | `sha256_geometria_canonica`, `huella_contenido`, `conexiones` (`id`, `sha256_documento`, `huella_conexiones`, `declaracion`) y `particiones` (`superficie`, `huella_particion`) |
| `nodos` | `id` global, `xyz_m`, `fuentes` (`particion`, `nodo`, `traza` del módulo 180), `alias` (IDs unificados) e `insertado_en` (`particion`, `contorno`, `arista`, `conexion`, `entre`) |
| `piezas` | por superficie: `celdas` (`id`, `nodos`, `tipo`, `franja`, `area_m2`, `pieza_de`) y `cadenas_contorno` (`contorno`, `arista`, `desde`, `hasta`, `nodos`) |
| `conexiones` | `id`, `fuente`; `a` y `b` con `arista_indice` y `orientacion`; `solape` (`inicio`, `fin`, `t_a` racional, `longitud_m`); `nodos_compartidos` ordenados; `criterio_coincidencia` |
| `bordes_no_conectados` | tramos de aristas exteriores sin conexión y todas las aristas de huecos (`segmentos_libres`) |
| `comprobaciones` | recuentos de superficies, conexiones, nodos, insertados y alias; `nodos_colgantes_en_conexiones: 0`; `areas_conservadas` |
| `limites`, `pendientes` | alcance y dependencias |
| `huella_compatibilidad` | SHA256 del JSON canónico del resultado sin este campo |

**Para conectar configuración y frames en el siguiente incremento:**
- usar `nodos[].id` / `xyz_m` como puntos únicos;
- `piezas[].celdas` (con `pieza_de`) para las áreas;
- `conexiones[].nodos_compartidos` para barras o vínculos de borde;
- `bordes_no_conectados` para los bordes libres o con apoyo declarado.

## Pruebas (independientes)

```powershell
$env:TEMP=(Resolve-Path tmp/claude_compatibilidad_182).Path; $env:TMP=$env:TEMP
.venv/Scripts/python.exe -m unittest -v tests.test_compatibilidad_particiones
```

**Verificador propio en XYZ:**
- los nodos sobre cada solape son exactamente los compartidos;
- ningún nodo compartido está dentro de una arista de celda de ninguna de las dos superficies;
- incidencias y frontera igual a las cadenas;
- áreas de Newell frente a la partición original y frente al área neta fuente;
- entradas intactas y determinismo.

**Casos:**
- coplanares con un lado cortado por un hueco y el otro sin cortes;
- ortogonales piso-muro con orientación directa e inversa;
- solape parcial (inicio/fin `WD`/`VB`, tramo libre);
- tres hosts con propagación y una cuarta conexión;
- m, cm y mm, y traslación de 1e6 m;
- sin declaración no hay unión;
- 18 rechazos (superficie o segmento ajeno, cruce puntual, contacto en un extremo, no coincidentes, misma superficie, par repetido, declaración alterada, campo extra, fuente alterada, NaN, identidad verificada, geometría distinta, partición alterada, omitida, duplicada, de otra fuente, sin particiones);
- puntos ambiguos dentro del solape, con un control válido;
- el verificador detecta el colgante si se omite la propagación.

Resultado: **8 OK, 0 omitidas**. Log en `tmp/claude_compatibilidad_182/pruebas.log`.

## Límites y dependencias (Codex)

- Celdas con nodos colineales: la calidad de malla no se evalúa.
- Conexiones solo entre contornos exteriores; las aristas de huecos quedan libres.
- **Dependencias:**
  - frames o barras en bordes y nodos compartidos;
  - apoyos, diafragmas, ejes, material, cargas y masa de las piezas;
  - calidad de malla;
  - transporte ETABS, guardado, reapertura y relectura independiente;
  - verificación real de la unión estructural.
