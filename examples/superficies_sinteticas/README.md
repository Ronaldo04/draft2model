# Superficies sintéticas reproducibles

Ejemplo local del contrato geométrico0.2: tres contornos planos comparten algunos vértices físicos. `SH` es horizontal (12m²,Z2.6); `SI` inclinado y `SV` vertical. Los puntos inferiores no crean niveles de piso ficticios. No representa un edificio, los planos de referencia, losa aligerada, escalera completa ni depósito.

Desde la raíz del proyecto, genere un archivo NUEVO de plan; el comando no abre ETABS ni envía datos:

```powershell
.\.venv\Scripts\python.exe -m draft2model.plan_modelado examples/superficies_sinteticas/geometria.json --salida tmp/plan_superficies_nuevo.json
```

Compare el JSON resultante con `plan.json`. Ambos deben conservar tres contornos, coordenadas y procedencia; cobertura geométrica completa no significa representación física completa. `ejecutable_en_etabs=false` y los bloqueos se conservan. Si el archivo de salida existe, elija otro nombre: no se reemplaza automáticamente.

La geometría está en borrador y no tiene aprobación. El ejemplo no incluye materiales, secciones, cargas, masa, apoyos, diafragmas ni decisiones de idealización. Esos datos requieren configuración propia y revisión, no valores predeterminados.

Para importar al historial necesita un expediente autorizado cuyo ID sea `superficies-sinteticas`, registrado con sus propios originales sintéticos. No cambie el ID para atribuirlo a otro expediente ni lo presente como extraído de planos reales.

Contrato: [geometría de superficies](../../docs/GEOMETRIA_SUPERFICIES.md). Migración y conversión: [guía](../../docs/MIGRACION_SUPERFICIES.md). La vista horizontal tiene QA sintético160; la vista 3D y las operaciones estructurales están en integración y necesitan su propia verificación antes de usarlas.
