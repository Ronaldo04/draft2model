# Extremos 314: regla específica de ETABS (ensayo NO ciego)

313 queda intacto. Sin ETABS, APIs ni modelo manual. No se modifican masas, libro, tolerancia, EDB ni resultados.

## Base documental corregida

- 313 usó el *CSI Analysis Reference*, cuya regla automática se refiere a la interfaz de **SAP2000** (p. 128). Queda retirada como base de ETABS.
- 313 sobre denominadores comparables: entre las 41 vigas no abstenidas, R-cara y R-max coinciden en 33 cada una. «37» incluía abstenciones.
- **Fuente ETABS:** ayuda oficial «End Length Offsets», https://docs.csiamerica.com/help-files/etabs/Menus/Assign/Frame/End_Length_Offset.htm (consultada el 2026-10-24; sin versión).
  - El `ETABS.chm` local no se pudo extraer con `hh.exe`; no se verificó la equivalencia con la versión 21.
  - Pertinente:
    - en vigas, el offset se basa en la máxima dimensión de las **columnas** conectadas;
    - controla la **columna inferior** y la superior se ignora;
    - las diagonales no intervienen.
  - No especifica: muros, otras vigas, orientación o inserción, límite cuando los offsets ≥ L, ni la fórmula exacta (se infiere ½·dimensión máxima).
- `REGLA_314.md` declara expresamente que **no es ciega**: se escribió conociendo 313. El sello (`SELLO_REGLA_314.sha256`) acredita integridad, no cronología.

## Regla R-ETABS y abstenciones

- Regla: max(T3, T2)/2 de la mayor columna inferior; otras vigas y columnas superiores no cuentan.
- Abstenciones:
  - B1: columna con inserción;
  - B2: suma ≥ L;
  - B3: extremo sin columna inferior que toca áreas;
  - B4: sección o frame no cubierto.
- Variante de sensibilidad «B3cero» (los muros no cuentan): declarada tras clasificar la geometría y antes del contraste. Solo informativa.

## Contraste (misma población: 45 vigas, 90 extremos; ±0,0005 m)

| Regla | Extremos: acuerdo / desacuerdo / abstención | Vigas: acuerdo / desacuerdo / abstención |
|---|---|---|
| R-cara 313 | 75 / 11 / 4 | 33 / 8 / 4 |
| **R-ETABS 314** | **25 / 0 / 65** | 4 / 0 / 41 |
| B3cero (informativa) | 58 / 0 / 32 | 29 / 0 / 16 |

**Conclusión.** La corrección documental **no reduce los desacuerdos convirtiéndolos en aciertos**: los traslada a abstenciones documentadas.
- Donde la documentación de ETABS determina el valor, la predicción coincide al 100 % (25/25 extremos; 58/58 con la variante).
- Los 11 desacuerdos de 313 caen todos en B2 (offsets ≥ L, sin regla documentada).
- La cobertura documentada es baja: 46 de 90 extremos no tienen columna y tocan muros (B3), y 16 vigas son B2. La masa sigue sin poder predecirse de forma independiente al completo.

## Diagnóstico posterior de geometría (`GEOMETRIA_NATIVA_314.json`)

- Plan frente a la geometría nativa archivada (relectura 09d1, mm): |ΔL| máximo 4,4·10⁻¹⁶ m y |Δcoordenada| máximo 4,4·10⁻¹⁶ m. **No hay diferencia de geometría.**
- Las 16 vigas B2 muestran un patrón nativo **solo observado, no adoptado**:
  - con un solo extremo en exceso (13 vigas), ETABS deja una longitud libre de 0,002 m (0,186 → 0,184; 0,107 → 0,105; 0,113 → 0,111);
  - con ambos extremos en exceso (3 vigas, L = 0,313), registra 0/0.
- Convertir ese patrón en regla sería ajustarse a la salida. Hace falta documentación de CSI o una prueba controlada fuera del perímetro.

## Archivos y pruebas

- `predictor_etabs_314.py` reutiliza el lector de plan de 313 sin cambiarlo.
- `test_predictor_etabs_314.py`: 6 pruebas sintéticas:
  - columna inferior frente a superior;
  - otras vigas ignoradas;
  - mayor columna;
  - abstenciones B1/B2/B3;
  - salvedad de muro;
  - independencia estática (sin entradas nativas ni la constante 0,002).
- Además: `contraste_314.py`, `geometria_nativa_314.py`, `PREDICCION_314.json`, `CONTRASTE_314.json`, `GEOMETRIA_NATIVA_314.json`.

## Límites y siguiente acción

- Fuente web sin versión.
- Interpretación ½·dimensión inferida.
- Muros y el tratamiento ≥ L sin documentar.
- La masa no queda verificada; el libro sigue no_coherente.
- **Siguiente acción:** CSI (soporte o notas de versión de ETABS 21) sobre Auto con offsets ≥ L y sobre la intervención de muros, o una prueba controlada autorizada. Codex decide cualquier integración.
