# Preprocesamiento trazable de fotografías

El módulo `draft2model.preprocesamiento` prepara PNG/JPEG mediante cuatro esquinas explícitas, rotación horaria múltiplo de 90 grados y contraste declarado. Usa Pillow existente, sin OCR, detección automática, red o dependencias nuevas. No infiere escala en metros, datos estructurales ni mejora de precisión: esta última requiere evaluación separada de visión contra una referencia humana.

## Configuración y ejecución

Guardar esta configuración como un archivo JSON UTF-8, sustituyendo esquinas y dimensiones por las de la imagen concreta. Este ejemplo describe una imagen original de 1200 × 800 píxeles y rectifica un cuadrilátero elegido por el revisor:

```json
{
  "rotacion_grados": 0,
  "contraste": 1.0,
  "perspectiva": {
    "esquinas_px": [[100, 50], [1100, 100], [1000, 750], [200, 700]],
    "dimensiones_salida_px": [1000, 600]
  }
}
```

```powershell
.\.venv\Scripts\python.exe -m draft2model.preprocesamiento --entrada ruta/foto.jpg --config ruta/config.json --salida tmp/foto_preparada
```

El padre de la carpeta de salida debe existir y la carpeta destino debe ser nueva. El módulo crea `imagen.png`, `config.json` y `registro.json`. Rechaza una carpeta existente, incluidos destinos con trabajo previo. Los originales permanecen intactos. Si un error de disco interrumpe la escritura, la carpeta parcial se conserva para inspección; repetir exige una nueva carpeta. Una configuración inválida o imagen ilegible no crea salida.

Para aplicar solo rotación y contraste, declarar `"perspectiva": null`. Para conservar ambos, usar `"rotacion_grados": 0` y `"contraste": 1`. Se requieren las tres claves, sin extras. Rotaciones admitidas: 0, 90, 180, 270 como enteros. Contraste: número finito mayor que cero y hasta 5; 1 conserva el contraste. La operación puede saturar valores al aumentarlo: conservar y comparar siempre el original.

El orden es **perspectiva -> rotación horaria -> contraste**. Las dimensiones explícitas son las de la imagen rectificada antes de rotar; 90/270 grados intercambian ancho y alto finales. Los puntos de referencia pertenecen siempre a la imagen original almacenada, antes de cualquier operación. La orientación EXIF se registra y no se aplica automáticamente: el revisor elige la rotación explícita sobre esos píxeles. Las imágenes se convierten a RGB; se descarta el canal alfa si existe. No es un editor de transparencia.

## Coordenadas y trazabilidad

La unidad es `px`. El origen `(0,0)` es el borde exterior superior izquierdo, `x` crece hacia la derecha, `y` hacia abajo. Para una imagen de ancho W y alto H, sus bordes son `(0,0)`, `(W,0)`, `(W,H)`, `(0,H)`; el centro del píxel de índice `(i,j)` está en `(i+0.5,j+0.5)`. Usar esta convención evita desfases de un píxel al superponer evidencias.

Las esquinas se declaran en orden **superior izquierda, superior derecha, inferior derecha, inferior izquierda** y deben formar un cuadrilátero estrictamente convexo, sin cruces ni repeticiones y contenido en los bordes del original. La rectificación envía esos cuatro puntos a los bordes del rectángulo explícito. Usa interpolación bicúbica; el remuestreo puede modificar píxeles, y no convierte la fotografía en una medición métrica.

`registro.json` conserva:

- SHA256 de los bytes originales, del PNG de salida y del archivo de configuración efectivamente guardado.
- Ruta original, archivos derivados, dimensiones originales, rectificadas y finales en píxeles; modo de salida y versión de Pillow.
- Matrices homogéneas 3 × 3 `origen_a_salida` y `salida_a_origen`, además de `origen_a_rectificada`.
- Convención de coordenadas, orden de operaciones y orientación EXIF sin aplicación automática.
- `escala_metrica: null` y `mejora_precision_vision: "no_evaluada"`.

Para transformar coordenadas, multiplicar `[x,y,1]` por la matriz y dividir los dos primeros componentes por el tercero. El helper lo hace y rechaza coordenadas no finitas o polos:

```python
from draft2model.preprocesamiento import transformar_punto

u, v = transformar_punto(registro["origen_a_salida"], x, y)
x_original, y_original = transformar_punto(registro["salida_a_origen"], u, v)
```

La transformación geométrica es reversible dentro del dominio útil con tolerancia numérica; los píxeles perdidos por recorte/remuestreo o contraste no se recuperan mediante la inversa. Para escala métrica sigue siendo necesaria una referencia dimensional explícita revisada y su conversión posterior al contrato geométrico. Este módulo no modifica ingreso, recortes ni expedientes, y no enlaza automáticamente su resultado al proveedor visual.

## Límites y comprobaciones

Se admiten PNG/JPEG de una única imagen, con dimensiones de 2 a 16000 píxeles por lado y hasta 20 millones de píxeles, tanto al abrir como al rectificar. El original tiene límite de 100 MB y la configuración CLI de 64 KiB. Se rechazan formatos distintos, animaciones, datos no finitos, booleanos como números, claves extra/duplicadas en configuración JSON, dimensiones imposibles, cuadriláteros degenerados y sistemas numéricamente inestables. No se reducen silenciosamente las dimensiones pedidas para hacerlas caber.

Las pruebas generan patrones sintéticos en carpetas temporales. Verifican identidad, recorte/rectificación, rotaciones y centros de píxel, perspectiva real seguida de rotación, ida/vuelta de coordenadas, contraste explícito, hashes, conservación del original, EXIF, límites y rechazo sin sobrescritura. No son una evaluación de legibilidad o precisión sobre planos reales.
