# Masa del agua: contraste nativo sintético253

Resultado observado: corrida `tmp/ensayo_masa_contenido_251/runs/codex253f`, estado final **verified**, proceso terminal código0. Revisión propia independiente `revisar_masa_nativa_253.py`: **39 comprobaciones satisfactorias**, recibo y huellas en `REVISION_MASA_NATIVA_253.json`. No ejecutar otra corrida por este resultado.

Prisma matemático2×2.15×2.22m, gamma10kN/m³, W95.46kN, presión descendente22.2kPa en un fondo horizontalZ3, material estructural sin peso/masa, cuatro columnas y diafragma rígido. Misma carga estática en los tres controles; cambia solo la fuente de masa.

| Fuente | MasaX/MasaY observada(kN·s²/m) | Reacción vertical(kN) |
| --- | ---: | ---: |
| NEUTRO1, sinAGUA |0|95.46|
| AGUA0.25 |2.433552692738806|95.46|
| AGUA1 |9.734210770955224|95.46|

g nativa9.806650199606521m/s² se obtuvo **antes** de ensamblar masas, mediante W/M de un material no asignado con dos densidades distintas. No se ajustó g a la masa observada. Total positivo del fondo tiene centroide observado(1,1.075,3)m. Se verificaron matrices crudas, coordenadas y ejes de puntos, retornos0, fuente antes/después, deltas0/25/100 y hashes de los tresEDB.

Instancia nueva propia: cierreApplicationExit0 y PIDcandidato37892 ausente. PIDs existentes6988/23928/38168 conservados; no se adjuntó ni cerró ninguna instancia ajena. Script ejecutado SHA256`00cfb5296009c0021cbc4e7e5be05b4561667766afaaf8c780462a2c601f683e`.

## Correcciones observadas durante el ensayo

Las corridasa…e fallaron y **se conservan como fallidas**, con cierre propio verificado. No se incluyen como controles satisfactorios de masa. El verificador253 enumera sus recibos/hashes.

- `File.Replace` con `$null` fallaba por enlace de argumento de WindowsPowerShell; ahora usa respaldo nuevo explícito. Prueba local de sustitución atómica y conservación del anterior satisfactoria.
- DefinirD1 antes de crear objetos devolvió1. Se creó geometría primero y se releyóD1 existente rígido con retorno0; no se acepta retorno1. La necesidad general de ese orden no se afirma como restricción documentada del programa.
- SetLoadUniformDir6/valor−22.2 se releyó como Dir10/valor+22.2. La normalización usa la equivalencia documentada gravedadpositiva=−Z; conserva los crudos.
- AssembledJointMass_1 retornóNumberResults14 con matrices15 y última posiciónnull/0. Se procesan las primerasN y se exige que la posición extra sea neutra; no sumar fuente/punto nulo ni ignorar datos extra no vacíos.
- Se corrigió el agrupamiento aritmético de las tres coordenadas del centroide en PowerShell.

## Lo acreditado y lo pendiente

La ruta carga vertical→fuente por patrones→masa ensamblada lateral funciona en **este montaje sintético** con factor1 y controles negativos/parciales. Los getters de fuente por sí solos no sustituirían esa prueba.

La masa se distribuye en el plano del fondoZ3, **no** en el centro volumétrico real del líquidoZ4.11; no prueba distribución vertical real, hidrodinámica, impulsivo/convectivo ni un tanque completo. Tampoco acredita las caras mojadas/geometría09E, la conexión al edificio, el modelo real ni ingeniería. En el producto sigue pendiente ligar inventario/volumen/estado/peso a configuración, plan, lector, UI y resultados. R249-02 permanece abierto hasta esa integración y su verificación en el alcance real.

No hubo peticiones de OpenAI/Gemini. La cuota autorizada sigueOpenAI4/5,Gemini2/5.
