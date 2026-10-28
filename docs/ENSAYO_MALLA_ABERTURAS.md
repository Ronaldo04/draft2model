# Ensayo real de malla de aberturas179

Ensayo de software del 20-10-2026 en ETABS21.1.0, DLL1.29.0.0. Crea modelos sintéticos nuevos; no abre ni modifica planos o modelos del usuario. Tres orientaciones usan contorno4×3m y abertura interior1×1m. El panel inclinado tiene y=z; sus áreas se multiplican por √2. Son datos de prueba, no hipótesis del proyecto.

## Resultados observados

| Escenario | Elementos asociados a anfitriona | Área de elementos | Área de elementos dentro del hueco | Lectura GetElm |
| --- | ---: | ---: | ---: | --- |
| Piso horizontal | 11 | 11m² | 0m² | Anfitriona0; abertura1 |
| Muro vertical | 0 | No comprobada | No comprobada | Anfitriona1; abertura1 |
| Panel inclinado | 1 | 12√2m², área bruta | √2m² | Anfitriona0; abertura1 |

El panel inclinado conserva material sobre el hueco. El muro no aporta una lectura válida para determinar su malla: cero elementos recibidos con retorno fallido no prueba ausencia de elementos. Tampoco se trata el retorno1 de la abertura del piso como lectura satisfactoria. El piso cumple dos condiciones geométricas necesarias (área neta y ausencia de intersección con el hueco), pero emitió `Warning: Check meshing, At N1 area F1 ( 8.33% Increment)`. No queda aceptado como malla adecuada.

CSI documenta que los muros deben dividirse para incorporar sus aberturas: [Divide Walls for Openings](https://docs.csiamerica.com/help-files/etabs/Menus/Edit/Edit_Shells/Divide_Walls_for_Openings.htm). La reflexión local encontró `cEditArea` sin métodos públicos en esta DLL; no se inventó una llamada de división. Marcar y releer `Opening` no demuestra el efecto en el modelo de análisis.

## Reproducibilidad y evidencia

`scripts/ensayar_malla_aberturas_etabs.ps1` requiere una carpeta absoluta existente y vacía dentro de `tmp` y `-ConfirmarEnsayoSintetico`. Debe ejecutarse bajo el bloqueo compartido `tmp/d2/motor.lock`, sin marca de incertidumbre pendiente. Crea una instancia propia mediante `Helper.CreateObject`, inicializa cada modelo en blanco y unidades explícitas, define un nivel sintético, material y sección, agrega contornos, guarda, llama `CreateAnalysisModel` y lee los elementos y sus puntos. **No ejecuta el solver.** Cierra exclusivamente su objeto de aplicación con `ApplicationExit(false)` en `finally` y registra el retorno.

El ensayo aceptado para diagnóstico es `tmp/malla179_host3/registro.json`, evaluado en `evaluacion.json` por:

```powershell
.venv/Scripts/python.exe scripts/evaluar_malla_aberturas_etabs.py tmp/malla179_host3/registro.json --salida tmp/otra_evaluacion179.json
```

La evaluación calcula área proyectada e intersección con el rectángulo sintético. No prueba calidad, conectividad, rigidez ni cargas. No habilita ejecución de producción ni aprueba ingeniería.

Los intentos anteriores quedaron conservados: el aislamiento impidió ejecutar el script en el primer intento; el primer ensayo del host guardó y cerró, pero faltaba el comando `Get-FileHash` (sustituido por SHA256 de .NET). El segundo cerró tras un retorno1 de GetElm; el tercero conserva cada retorno sin convertirlo en éxito y define un nivel explícito. No se alteraron políticas Windows. Todos los procesos ETABS creados por estos tres ensayos del host confirmaron cierre.

## Siguiente requisito de implementación

Dividir explícitamente superficies con huecos, manteniendo procedencia, orientación, propiedades y cargas, y garantizar conexiones compatibles con las superficies y barras adyacentes. Comprobar la malla generada y su persistencia en ETABS antes de habilitar superficies0.2/aberturas0.3 en el recorrido de producción. Resolver las advertencias; un retorno0 al crear el modelo de análisis no acredita una malla correcta. La relectura de propiedades o la comparación geométrica del objeto no sustituye esta comprobación.
