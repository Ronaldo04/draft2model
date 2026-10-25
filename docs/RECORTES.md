# Recortes PDF y evidencia de origen

El comando `recortar` genera una imagen ampliada y un `recorte.json` local. No modifica el original, interpreta geometría ni establece escala estructural.

```powershell
.\.venv\Scripts\python.exe -m draft2model recortar --caso provisional-001 --archivo L0002 --pagina 1 --bbox 0.05 0.02 0.60 0.48 --dpi 150 --etiqueta planta-superior
```

## Convención de coordenadas

`bbox` es `[x0, y0, x1, y1]` con valores entre 0 y 1 y área positiva. Se mide sobre la **página visible**, con la rotación PDF aplicada, origen en la esquina superior izquierda, X hacia la derecha e Y hacia abajo. Página comienza en 1. No son coordenadas CAD ni medidas en metros.

El registro identifica caso, archivo, página, SHA256 del original y manifiesto, ID del recorte, PNG y hash de imagen. Conserva la declaración de alcance del expediente. El estado inicial es `pendiente_revision` y `escala_geometrica` es `null`.

Campos para integrar datos candidatos:

| Campo | Significado |
| --- | --- |
| `sistema_coordenadas` | `pagina_visible_normalizada`. |
| `bbox_normalizada` | Región seleccionada en la página visible. |
| `pagina_visible_pt` | Ancho y alto de la página visible en puntos. |
| `bbox_pagina_visible_pt` | Región seleccionada en puntos de página visible. |
| `pixel_a_pagina_visible` | Matriz afín `[a,b,c,d,e,f]` del píxel del PNG a puntos de página visible. |
| `pagina_visible_a_sin_rotacion` | Matriz afín para transformar puntos visibles a espacio PyMuPDF sin rotación. No es el espacio PDF nativo de origen inferior izquierdo. |
| `bbox_pagina_sin_rotacion_pt` | Rectángulo de origen en espacio PyMuPDF sin rotación. |
| `dimensiones_px` | Ancho y alto del PNG. |
| `dpi_solicitado`, `dpi_render_aproximado` | Resolución solicitada y efectiva. No acreditan escala. |

Para la matriz afín: `X=a*x+c*y+e`, `Y=b*x+d*y+f`. `punto_a_pagina(metadata, x, y)` implementa la primera transformación. Después dividir X/Y por el ancho/alto de `pagina_visible_pt` para obtener coordenadas normalizadas. Los bordes del raster pueden diferir menos de un píxel del rectángulo solicitado por redondeo; usar la matriz guardada, no recalcularla desde el tamaño del PNG.

## Límites y persistencia

- Primera versión para PDF; recortes de imágenes raster pendientes.
- DPI solicitado entre 72 y 300. Se reduce automáticamente si el render superaría 8 millones de píxeles; la resolución efectiva queda registrada.
- Archivos protegidos, hashes incompatibles, página inexistente y regiones fuera de la página se rechazan.
- Cada recorte se guarda en un directorio único en `data/private/<caso>/recortes/`. No sobrescribe regiones anteriores.
- La etiqueta organiza regiones seleccionadas manualmente; no representa detección automática de plantas o elementos.
- PNG y JSON privados no se publican en GitHub.

Las pruebas verifican el contenido visual correcto y la posición para las cuatro rotaciones, transformación de una región desplazada, entradas inválidas y rechazo de originales alterados. La documentación de coordenadas y renderizado está en [PyMuPDF Page](https://pymupdf.readthedocs.io/en/latest/page.html).
