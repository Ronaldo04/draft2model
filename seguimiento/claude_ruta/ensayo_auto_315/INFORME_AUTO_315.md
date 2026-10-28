# Ensayo Auto 315: extremos nativos en fixtures sintéticos (ETABS 21.1.0)

Ensayo de software con modelos sintéticos nuevos; no aprueba ingeniería. Ensayo **no ciego** respecto de 314. Cero llamadas remotas. Sin EDB reales, sin Pueblo Libre, sin modelo manual. Producto congelado.

## Ejecución

- Matriz previa `MATRIZ_PREVIA_315.json`, sellada a las 08:06:18 UTC (SHA `5e37f80d…`) antes de ejecutar.
- **Corrida principal** (08:07:38 UTC, PID propio 14212): error del harness en K04 (colisión de variables de PowerShell que no distinguen mayúsculas).
  - `ApplicationExit` = 0 y el proceso salió. No hay EDB.
- **Reparación única** (`REPARACION_315.md`, 08:08:55 UTC, PID propio 44832):
  - **Modelo A** completo: tolerancia de unión por defecto 0,001 m (`GetMergeTol`), análisis con retorno 0, EDB `corrida_reparacion/auto_315_A.EDB`.
  - **Modelo B** (5 × tolerancia mediante `SetMergeTol`, documentado): ETABS abrió un modal «Error in dimensioning Arrays. Check available space on disk.».
    - Hay espacio de sobra (C: 624 GB, D: 318 GB libres), así que el mensaje no se debe al disco.
    - No se pulsó el modal (sin interacción GUI). La llamada COM quedó bloqueada hasta el límite de 900 s (código 124).
    - Al terminar el harness, la instancia propia 44832 ya no existía (`CIERRE_REPARACION_315.json`); no hizo falta terminarla.
    - Las sesiones ajenas 6988, 23928 y 38168 estuvieron presentes antes y después, sin tocar.
  - No se hace una tercera corrida.

## Observación nativa (modelo A; API `GetEndLengthOffset` = tabla «Frame Assignments - End Length Offsets»)

| Caso | Pregunta | Nativo I / J (m) | Coincide con |
|---|---|---|---|
| K01 | control X, columnas inferiores 40×15 | 0,20 / 0,20 | ayuda y cara |
| K02 | viga en Y, columna con 0,40 en X | **0,075 / 0,075** | cara (proyección), no ayuda literal |
| K03 | columna solo superior en J | 0,125 / **0** | ayuda (la superior se ignora) |
| K04 | extremo J en muro, sin columna | 0,30 / **0** | (indeterminado previo) el muro no aporta |
| K05 | extremo J sobre otra viga | 0,125 / **0** | ayuda (otras vigas no cuentan) |
| K06 | L = 0,29, exceso en un extremo | **0,288** / 0, Lc = 0,002 | H_Lc2mm, no 1 % |
| K07 | L = 0,55, sin exceso | 0,30 / 0 | control |
| K08 | L = 0,35, ambos extremos en exceso | **0 / 0** | H_cero |
| K09 | L = 0,50, cada offset (0,30) < L pero la suma > L | **0 / 0** | H_cero, por la suma |
| K10 | L = 0,27, en Y, columna 60×20 | 0,10 / 0 | cara: 0,10 < L, sin exceso (la predicción de la ayuda era errónea) |
| K11 | columna girada 90° (eje local) | **0,10** / 0,125 | cara (orientación por eje local) |

- Los offsets Auto **solo se materializan tras el análisis**. Antes, la lectura difería en los casos con offset distinto de cero.

## Regla propuesta (verificable, aún no universal)

Para una viga horizontal con opción Auto, en ETABS 21.1.0, unidades kN-m:

1. Solo cuentan las **columnas inferiores** del extremo. Las superiores, otras vigas y muros aportan 0.
2. El offset del extremo es la **distancia del joint a la cara** de la mayor columna inferior **a lo largo del eje de la viga**: (T3/2)/|u·e2| o (T2/2)/|u·e3| según los ejes locales de la columna. Es la proyección de 313, **no** la «máxima dimensión» literal de la ayuda.
3. Si la suma es ≥ L:
   - con offset en un solo extremo, queda L − 0,002 m (observado con tolerancia de unión 0,001 m);
   - con offset en ambos extremos, 0/0.

Esta regla es coherente con los 16 casos B2 de 314 en el piloto (13 con Lc = 0,002 y 3 con 0/0) y con los muros de 314 (0). Es una observación, no una calibración sobre el piloto.

## Límites

- Sin modelo B no se sabe si 0,002 m es una constante o 2 × la tolerancia de unión. H_tol queda **abierta**.
- Una sola versión (21.1.0), una unidad y secciones rectangulares; sin diagonales, inserciones, columnas inclinadas ni vigas inclinadas.
- No se integra en el producto ni en el libro.

## Siguiente acción

- Ensayo B aislado en una instancia nueva: solo `SetMergeTol` en un modelo recién creado (sin `InitializeNewModel` sobre un modelo ya analizado en la misma instancia), sospechoso del modal.
- Decide Codex.
