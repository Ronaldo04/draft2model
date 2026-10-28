# Geometría de superficies v0.2

Base geométrica implementada; no define un elemento finito, sección física, diseño de losa aligerada ni ingeniería de cisterna/tanque. La geometría v0.2 permanece bloqueada para modelado estructural hasta verificar sus consumidores de configuración y operaciones ETABS. El plan geométrico puede mostrar propuestas sin habilitar una ejecución.

## Contrato exacto

`contrato="draft2model.geometria"`, `version_contrato="0.2.0"`. Conserva todos los campos raíz de v0.1 y añade dos campos obligatorios: `vertices` y `superficies`. No hay campos raíz opcionales nuevos. `VERSION_GEOMETRIA` sigue siendo `0.1.0`; la constante adicional es `VERSION_GEOMETRIA_SUPERFICIES="0.2.0"`.

- `vertices`: lista de objetos con **exactamente** `id`, `x`, `y`, `z`, `procedencia`. XYZ son números finitos representables, nunca bool/null. Se expresan en la `unidad_longitud` raíz (`m`, `cm` o `mm`), independientes de pisos y de la colección histórica `nodos`.
- `superficies`: lista de objetos con **exactamente** `id`, `vertices`, `papel_geometrico`, `procedencia`. `vertices` contiene al menos tres IDs existentes y distintos, en orden perimetral; no repite el primero al final. `papel_geometrico` es texto declarado no vacío, sin deducción de tipo estructural ni restricciones de vocabulario de ingeniería.
- Cada `procedencia` usa las reglas históricas: obligatorios `tipo`, `descripcion`; opcionales `expediente_id`, `lamina`, `referencias`, `justificacion`. No se mezclan procedencias sintéticas y reales. La declaración de procedencia no comprueba por sí sola el documento original.
- `niveles`, `nodos`, `muros` conservan campos y semántica v0.1. En v0.2 sus listas pueden estar vacías, para representar un contorno sin inventar muros o pisos. Las dos listas nuevas también pueden estar vacías durante migración/borrador. Un ID es único dentro de su colección; los espacios de IDs son distintos.
- No se admiten agujeros embebidos, triangulaciones implícitas, asignaciones de material, espesor ni cargas en este contrato. Una superficie es un solo contorno simple plano; puede ser cóncavo. Esto no promete que un consumidor ETABS acepte toda superficie geométricamente válida.

## API y resultado

`validacion_geometria.validar_geometria(data)` despacha explícitamente por versión. El lector JSON estricto histórico conserva rechazo de claves duplicadas y constantes no finitas. Reetiquetar una v0.1 como v0.2 sin ambas colecciones nuevas produce campos ausentes; no es migración.

El resultado conserva `ResultadoValidacion`, añade `version_contrato` y publica la versión efectiva en `a_dict()`. Cuando es consistente, `geometria_m` contiene una copia normalizada en metros, con referencias/orden/procedencia intactos. `derivados_m['muros']` conserva su forma histórica. La nueva salida es:

```python
derivados_m['superficies'][id] = {
    'vertices_m': [[x, y, z], ...],
    'area_m2': area_positiva,
    'normal_unitaria': [nx, ny, nz],
    'epsilon_relativo_computacional': epsilon,
}
```

No se modifica la entrada, reordena el contorno, fusionan vértices ni reparan cruces. Una normal invertida al invertir el contorno queda visible. Un error de normalización/contorno no publica geometría, derivados ni huella válidos. Una aprobación geométrica vigente no elimina `BLOQUEO_INTEGRACION`: `disponible_para_modelado` continúa falso en v0.2.

## Criterio computacional

Se trasladan los vértices al primero y se dividen por la máxima componente absoluta del desplazamiento (`escala`). Se rechaza extensión nula/no finita. En estas coordenadas se usa `epsilon=max(1e-12,64*ulp(max(abs(coordenadas_m)))/escala)`; si supera `1e-6`, la posición/extensión es numéricamente inestable y se rechaza.

La normal proviene del mayor producto vectorial entre pares de desplazamientos; su módulo debe superar epsilon. La distancia normalizada a ese plano no puede superar epsilon. Se proyecta descartando el eje de mayor componente normal; se comprueban cruces/contactos no adyacentes, retrocesos colineales y aristas degeneradas. El área orientada resulta de la suma de productos vectoriales y debe ser positiva, finita y representable tras volver a m2. Se aceptan puntos intermedios colineales que no retroceden. No se certifica exactitud de levantamiento ni adecuación de una malla por pasar estas verificaciones.

Este criterio es una condición numérica para binary64, **no una tolerancia dimensional, constructiva, normativa o estructural**. Las geometrías demasiado degeneradas para distinguirse de manera fiable se rechazan sin redondear sus coordenadas.

## Revisión y migración

La huella SHA256 incluye todas las colecciones nuevas y su versión; excluye únicamente `revision`, igual que v0.1. Cambiar un vértice, contorno, papel declarado o procedencia invalida la aprobación registrada. La identidad/competencia del revisor no se autentica por este registro.

`geometria_superficies.migrar_a_superficies(data_v01)` exige una geometría v0.1 consistente y devuelve una **copia** v0.2 con `vertices=[]`, `superficies=[]` y revisión `borrador` sin aprobación. Conserva datos originales sin inferir nuevos vértices. El guardado como versión hija y vínculo persistente con su fuente corresponde a gestión de geometría; esta función pura no escribe ni sustituye archivos.

## Comprobación focal

```powershell
$env:TEMP=(Resolve-Path tmp).Path
$env:TMP=$env:TEMP
.venv/Scripts/python.exe -m unittest tests.test_geometria_superficies tests.test_validacion_geometria
```

Casos sintéticos: unidades equivalentes, planta/plano vertical/inclinado/cóncavo, orientación, procedencia, revisión/huella, migración y entrada corrupta; rechazo de cruces, contactos, repetidos, alabeo y problemas de representación. No acredita el caso real ni la ejecución ETABS.
