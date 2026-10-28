# Versiones y conversión de superficies

La geometría v0.2 añade vértices XYZ y contornos planos sin alterar el contrato v0.1. Cada versión conserva originales, procedencia y huellas; las coordenadas son físicas, no píxeles. Ver [contrato y límites](GEOMETRIA_SUPERFICIES.md) y [conversión de lecturas](CONVERSION_SUPERFICIES.md).

## Crear una versión hija

Abra una geometría v0.1 comprobada, complete revisor declarado, fecha y motivo, y pulse **Crear borrador con superficies 3D**. Los cambios del JSON deben guardarse antes. Se conserva la fuente y se crea una hija v0.2 con `vertices=[]`, `superficies=[]`, revisión borrador y aprobación null. Una aprobación del padre no se transfiere. La operación no añade componentes físicos ni habilita ETABS.

Puede completar el JSON de la hija con coordenadas/contornos/procedencia revisados y guardar otra revisión. Se exige un contorno simple plano: los huecos no se representan como un polígono autointersectado.

Por CLI, sustituya los marcadores por el caso, ID y huella exactos consultados:

```powershell
.\.venv\Scripts\python.exe -m draft2model migrar-geometria-superficies --caso CASO --geometria ID_PADRE --huella-esperada SHA256_CONTENIDO --revisor 'Operador declarado' --fecha 2026-10-19 --motivo 'Añadir contornos físicos revisados'
```

La ruta HTTP `POST /api/geometria/migrar-superficies` exige las mismas identidades/huellas/fecha/motivo del panel de geometría; rechaza campos adicionales y fuentes que cambiaron. No aprueba geometría, resultados ni ingeniería.

## Desde lecturas revisadas

El panel de conversión acepta un manifiesto0.2 completo con vértices y superficies, además del formato0.1. Cada medida debe proceder de una cota revisada o de una declaración física justificada con referencias revisadas. La conectividad necesita referencias propias: la IA no fija por sí sola escala ni relaciones estructurales.

Crear la conversión conserva el manifiesto, exportación, geometría y correspondencias. Consultar o importar vuelve a reconstruir exactamente la geometría y las correspondencias desde el manifiesto y la exportación vigentes, además de contrastar hashes y fuentes. Recalcular hashes de un derivado manipulado no basta. Importar sigue siendo una acción separada y produce un borrador.

## Verificación y pendientes

Pruebas sintéticas:3correctas de migración/CLI/HTTP,9correctas del lector/conversión HTTP (incluye regresión0.1) y12comprobaciones Node de cliente/conversión/migración y respuesta tardía. Logs: `tmp/migracion_superficies_158_final.log`, `tmp/conversion_http_superficies_159.log`, `tmp/migracion_conversion_frontend_159_final.log`. No fueron llamadas API ni ETABS ni revisión visual de navegador.

La configuración/operaciones ETABS0.2 están encargadas a Claude; la superposición de superficies está en desarrollo separado. El bloqueo de integración sigue vigente. Losas aligeradas, huecos, escaleras y depósitos completos necesitan representación y acciones revisadas; aceptar un contorno no acredita esas funciones ni completa el proyecto.
