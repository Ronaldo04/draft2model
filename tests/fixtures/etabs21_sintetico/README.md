# Evidencia sintética portable

Reproducción de archivos capturados por Codex en ETABS 21.1 el 17 de octubre de 2026. Toda geometría, cargas y aprobaciones son de ensayo, inventadas. No contiene planos de obra reales ni credenciales y no acredita seguridad estructural.

`evidencia.zip` conserva 69 archivos: expediente sintético y versiones necesarias, modelo construido/revisión, resultado estático, dos corridas de análisis para comprobar rechazo de mezcla, informe histórico y esquema CSI/fallo de tabla inexistente. Los EDB se leen como bytes para comprobar sus huellas; las pruebas no los abren en ETABS ni ejecutan cálculo. No son una referencia manual ni una validación independiente de ingeniería.

`manifest.json` identifica origen, naturaleza sintética, SHA256 del ZIP y SHA256/tamaño de cada archivo. `tests.fixture_etabs.extraer_evidencia` valida todo antes de extraer en un destino nuevo. Una fixture ausente o alterada produce fallo; no se omiten pruebas por ausencia de temporales de sesión.

Las rutas Windows de las capturas son declaraciones históricas conservadas para comprobar vínculos. Las pruebas usan copias extraídas, sin acceder a las ubicaciones históricas. Flujo verificado en Windows x64/CPython 3.10; no se afirma compatibilidad de las capturas Windows en otras plataformas.

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_fixture_etabs tests.test_esquema_csi_real tests.test_evidencia_analisis -v
```

El script de lectura CSI está conservado como `scripts/leer_vocabulario_dinamico_etabs.ps1`. Su prueba inspecciona el texto y las llamadas permitidas; no conecta con ETABS.

No actualizar este paquete desde un expediente real. Una nueva captura sintética requiere comprobar su cadena completa, documentar procedencia y regenerar inventario/ZIP de forma deliberada. Conservar las evidencias originales de la captura fuera del paquete de pruebas.
