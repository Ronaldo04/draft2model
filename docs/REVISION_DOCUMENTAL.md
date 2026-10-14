# Revisión documental y caso provisional

El módulo abre los originales registrados, comprueba su SHA256 y genera un inventario de páginas y vistas previas locales. No realiza OCR ni valida geometría o seguridad estructural.

## Preparar el entorno

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Las versiones comprobadas son PyMuPDF 1.28.2 y Pillow 12.3.0. El código usa el renderizado de [PyMuPDF](https://pymupdf.readthedocs.io/en/latest/recipes-images.html) y la apertura/verificación de [Pillow](https://pillow.readthedocs.io/en/stable/reference/Image.html).

## Registrar una muestra fuera del alcance

```powershell
.\.venv\Scripts\python.exe -m draft2model ingresar --caso provisional-001 --archivos "RUTA_LOCAL.pdf" --uso-autorizado --provisional-fuera-alcance
```

La bandera conserva la declaración de que el sistema constructivo y el número de pisos no corresponden al MVP. Su uso es probar ingreso, páginas, renderizado y procesamiento. No constituye validación del MVP ni amplía la tipología aprobada. No se adopta el proyecto externo como referencia de evaluación estructural automática.

El caso de prueba provisional ya se registró localmente; no repetir su ingreso con el mismo identificador. Para otros casos, usar un identificador nuevo y archivos autorizados.

## Revisar páginas

```powershell
.\.venv\Scripts\python.exe -m draft2model revisar --caso provisional-001
```

Cada ejecución crea una carpeta nueva dentro de `data/private/<caso>/revision_documental/`, con `revision.json` y PNG por página. No altera el manifiesto, los originales ni las ejecuciones anteriores. La salida registra:

- Hash del manifiesto de entrada y correspondencia entre original, página y vista previa.
- Número de páginas PDF y dimensiones en puntos; dimensiones de imágenes en píxeles.
- Rotación declarada del PDF y orientación EXIF aplicada solo a la vista previa de imagen.
- Tamaño del render, DPI aproximado de renderizado y cantidad de caracteres de texto embebido.
- Errores de apertura, documentos protegidos, referencias fuera del expediente o hashes incompatibles.

Las vistas previas tienen un lado máximo de 2400 píxeles por defecto; admite `--max-lado` entre 128 y 4096. Para láminas grandes, la vista general tiene menor DPI. Eso no significa que el original tenga baja resolución: para leer cotas pequeñas se requieren recortes ampliados posteriores. El DPI no acredita escala geométrica.

Abrir y renderizar una página no garantiza su integridad completa ni legibilidad. La legibilidad y la orientación de lectura requieren revisión; no se gira el original ni se detecta inclinación automáticamente. La ausencia de texto embebido se señala para valorar OCR, sin inferir que la lámina sea ilegible.

Código de salida: 0 para revisión sin errores de apertura/render, 2 cuando el informe contiene errores documentales y 1 para una solicitud que no puede completarse. Ningún resultado aprueba datos de ingeniería.

## Privacidad y verificación

`planos_muestra/`, `data/private/`, `.venv/` y `tmp/` están excluidos del versionado. La carga remota se limita al código y documentación de operación; no incluye planos, manifiestos privados ni vistas previas.

Las pruebas cubren PDF con varias páginas, rotación, imagen, límites de render, hashes alterados, PDF dañado y PDF protegido. Ejecutar:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
