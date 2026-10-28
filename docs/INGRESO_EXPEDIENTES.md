# Ingreso de expedientes: primera implementación

El módulo registra originales PDF/JPG/PNG de manera local, crea copias sin cambiar sus bytes y genera un `expediente.json` en estado **borrador**. No extrae geometría, cuenta páginas, evalúa la estructura ni conecta a ETABS.

Desde la carpeta del proyecto:

```powershell
.\.venv\Scripts\python.exe -m draft2model ingresar --caso piloto-001 --archivos "RUTA_LOCAL_DEL_PLANO.pdf" --uso-autorizado
```

Reemplazar la ruta por un archivo real y autorizado. La opción `--uso-autorizado` registra una declaración de uso; no es una aprobación de ingeniería.

Los archivos quedan en `data/private/piloto-001/originales/` y el manifiesto en `data/private/piloto-001/expediente.json`. Esta carpeta está excluida por `.gitignore`. El comando no envía archivos a GitHub ni a proveedores de IA.

## Controles implementados

- Identificador limitado a letras, números, guion y guion bajo; sin rutas ni nombres reservados de Windows.
- Rechazo de archivos ausentes, vacíos, extensiones no admitidas y firmas incompatibles.
- Rechazo de duplicados por contenido SHA256 y de expedientes existentes.
- Copias con identificadores de lámina para conservar archivos cuyos nombres coincidan.
- Contraste SHA256 entre original y copia; un cambio durante la copia impide registrar el expediente.
- Preparación temporal y publicación local del expediente después de copiar todos los archivos.
- Datos de ingeniería y aprobación técnica permanecen ausentes.

Una firma compatible no demuestra que un PDF o imagen esté íntegro o sea legible. Esa comprobación, el inventario de páginas y las vistas previas se implementarán en la siguiente etapa. Los campos del manifiesto son la primera versión del registro de ingreso, no un contrato de modelado ETABS ya aprobado.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Las pruebas usan fragmentos sintéticos para comprobar preservación, hashes, estados, rechazos y ausencia de sobrescritura. No acreditan interpretación de planos ni validación estructural.
