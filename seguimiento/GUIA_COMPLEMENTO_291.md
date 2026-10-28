# Complemento del caso y resultados externos

Responsable: Codex. Herramienta de entrega local, independiente del producto y del paquete de fuentes de Claude. No ejecuta ETABS ni proveedores. Su manifiesto acredita bytes estables y un caso seleccionado; no acredita ingeniería ni aceptación funcional.

El exportador268 solo conserva `data/private/<caso>`. Los informes, panel, reglas, contexto y registros de las continuaciones están en `tmp/<trabajo>` y requieren esta selección adicional. Los hashes del informe y panel deben coincidir con el registro. Se comprueba también el caso y resultado de la evidencia del informe. Las rutas y recibos originales se conservan.

## Crear después de revisar la entrega

Seleccionar explícitamente la continuación aceptada; no asumir que09d2 sigue siendo la final. Desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m seguimiento.exportar_complemento_291 --raiz data/private --caso pueblo-libre-002 --trabajo tmp/CONTINUACION_REVISADA --salida entregas/COMPLEMENTO_NUEVO --referencias-publicas seguimiento/normativa_229
.\.venv\Scripts\python.exe -m seguimiento.exportar_complemento_291 --salida entregas/COMPLEMENTO_NUEVO --verificar
```

El destino debe ser nuevo. No se reemplaza una entrega anterior. Se conservan los fallos como `FALLO.json` y ese destino queda rechazado. La utilidad rechaza fuentes fuera del trabajo, enlaces/junctions, diferencias con el registro, patrones de credenciales y cambios durante la copia. El corpus público es optativo y debe elegirse deliberadamente: incluye PDF/textos/manifiesto, no renders PNG; verifica hashes de los documentos originales declarados. Conservar esta carpeta permite consultar referencias como `seguimiento/normativa_229/E030_RM183_2026.txt`.

## Contenido y uso

- `Complemento.zip` y `MANIFIESTO_COMPLEMENTO.json`: inventario y hashes externos para contrastar el transporte.
- `caso_archivado/Caso.zip` y su manifiesto: únicamente el expediente elegido, incluidos originales y versiones históricas.
- `resultados/`: informe JSON/HTML/PDF, panel y, si existen, reglas/contexto/libro de masa del trabajo seleccionado.
- `evidencias/`: registro de resultados y los archivos locales disponibles de configuración, registro del runner y diagnóstico por pisos.
- `seguimiento/normativa_229/`: fuentes públicas elegidas, con sus rutas conservadas.

Extraer el complemento en una carpeta nueva. Abrir el PDF o HTML para consultar las salidas archivadas. El panel HTML conserva filtros locales y no necesita red. Para reconstruir, instalar la distribución de fuentes validada y seguir su guía, aportando los originales y entradas revisadas; generar nuevas corridas/recibos en la ubicación de destino. Copiar el archivo EDB o modificar sus rutas históricas no acredita una reconstrucción o relectura nueva.

La instantánea mantiene hipótesis, incumplimientos, revisión pendiente y contrastes no coherentes. No se entrega una nueva aprobación por empaquetar. Una entrega completa para AECODE debe acompañar este complemento con el paquete de fuentes final y la evidencia de validación ligada a su huella.

## Evidencia de esta herramienta

`seguimiento.test_exportar_complemento_291`: diez pruebas de integridad, exclusión de otros casos, alteraciones, escape de rutas, credenciales, no sobrescritura, cambios concurrentes y corpus público. Son fixtures de transporte; no prueban modelado ni normativa del piloto. El candidato291 usa09d2 para comprobar transporte real, pero conserva los defectos de presentación detectados290 y NO es entrega final.
