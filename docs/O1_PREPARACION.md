# O1: base de ingeniería y entorno

Estado: en preparación, 13 de octubre de 2026. Seguimiento: [Issue #2](https://github.com/Ronaldo04/draft2model/issues/2).

## Entorno comprobado

| Comprobación | Resultado |
| --- | --- |
| Python disponible para el proyecto | 3.10.5, 64 bits. |
| Entorno aislado | `.venv` creado y diagnóstico ejecutado correctamente. |
| ETABS instalado | 21.1.0.3261; ejecutable y bibliotecas en la carpeta ETABS 21. |
| Registro COM | CSI.ETABS.API.ETABSObject y ETABSv1.Helper presentes. |
| Dependencias Python del prototipo | No instaladas aún en el entorno nuevo; se seleccionarán según la conexión y contratos que se implementen. |
| Licencia y apertura de ETABS | Pendientes de comprobación. |
| Conexión API y lectura de resultados | No ejecutadas. |
| Caso piloto en la carpeta | No se encontraron modelos EDB/E2K ni dibujos DWG/DXF; los PDF presentes son documentación del proyecto. |

El diagnóstico solo inventaría el entorno. No inicia ETABS, modifica el registro, abre modelos ni consulta archivos de licencia. Una clase COM registrada no demuestra que la API funcione.

## Repetir el diagnóstico

Desde la carpeta del proyecto en PowerShell:

```powershell
.\.venv\Scripts\python.exe scripts\diagnosticar_entorno.py --output tmp\diagnostico_entorno.json
```

El entorno `.venv` y el informe JSON permanecen locales y excluidos del repositorio. El Python global encontrado pertenece también a otras herramientas; el proyecto usa su propio entorno para aislar futuras dependencias.

## Datos necesarios del piloto

Registrar la ubicación local de planos y modelo de referencia en una ficha local. No subir automáticamente planos o expedientes: confirmar su autorización y retirar identificadores privados cuando corresponda.

- Planos estructurales legibles, escala y unidades identificables, láminas completas y número de niveles.
- Sistema estructural dentro del alcance: albañilería confinada, uno o dos niveles.
- Alturas, espesores, materiales, cargas e información de sitio, indicando fuente y faltantes.
- Correspondencia entre planos y construcción; información adicional requerida.
- Modelo ETABS manual de referencia, si existe, y versión de ETABS empleada.
- Evidencia de autorización de uso del caso y modalidad de almacenamiento.

## Referencia de ingeniería y tolerancias

Antes de comparar resultados, documentar: geometría y conectividad, materiales y secciones, diafragmas y apoyos, cargas, fuente de masa, unidades, casos de análisis, hipótesis y versión ETABS. Las tolerancias de periodos, derivas y cortantes deben definirse y aprobarse antes del ensayo; no se fijan porcentajes arbitrarios en esta preparación.

## Secuencia de comprobación

1. Confirmar el caso y completar el inventario de láminas, datos y faltantes.
2. Verificar apertura de ETABS con licencia disponible y cerrar la comprobación sin alterar modelos existentes.
3. Verificar la documentación API de la versión instalada y preparar una conexión de lectura sobre un modelo autorizado.
4. Registrar versión, unidades y resultado de las llamadas; solo entonces comprobar lectura de indicadores reales.
5. Construir o revisar el modelo manual de referencia y aprobar hipótesis y tolerancias.

O1 se cierra con un expediente utilizable, referencia revisada y una lectura API real. El inventario de herramientas no cumple por sí solo esos criterios.
