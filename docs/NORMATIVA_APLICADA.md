# Normativa aplicada (RNE vigente) y calibración por cotas

Decisión del usuario (229): aplicar las normas vigentes del RNE. Las ediciones las acredita Codex en `seguimiento/NORMATIVA_OFICIAL_229.md`:

| Norma | Texto aplicado |
|---|---|
| E.030 | RM 183-2026 (transitoria modificada por RM 217-2026) |
| E.060 | DS 010-2009 |
| E.070 y E.020 | DS 011-2006, con fe de erratas |

## Qué está implementado y verificado

- **`draft2model.normativa_e030`** (E.030 2026):
  - Z (Tabla 1 y anexo: Lima → zona 4);
  - U (Tabla 7);
  - S, TP y TL (Tablas4/5); para Vs30, el recorrido explícito incorporado en el encargo09 se describe más abajo. El perfil es declarado y no se clasifica automáticamente;
  - C (Tabla 6, cuatro tramos);
  - R = R0·Ia·Ip (Tabla 10, art. 26);
  - espectro Sa = ZUCS/R·g (art. 41);
  - análisis estático:
    - peso sísmico P (art. 31);
    - V con C = 2,5 si T ≤ TP y la comprobación C/R ≥ 0,11 (art. 34);
    - distribución en altura con k (art. 35);
    - T = hn/CT (art. 36);
  - desplazamientos 0,75R / 0,85R y límites de la Tabla 14 (arts. 50–51);
  - cortante mínimo dinámico (art. 44);
  - excentricidad 0,05 (art. 45).
- **`draft2model.normativa_rne`:**
  - E.060 8.5.2 (Ec = 4700√f'c en **MPa**, con conversión explícita desde kgf/cm²) y 8.5.4 (G = Ec/2,3);
  - E.070 24.7 (Em = 500/600/700 f'm según la unidad; Gm = 0,4 Em);
  - E.020: pesos del anexo 1, carga viva de vivienda 2,0 kPa y techo 1,0 kPa.
- Cada función devuelve el valor junto con la **cita**: norma, dispositivo, artículo y tabla.
- **`scripts/verificar_normativa_e030.py`** comprueba cada constante contra el texto oficial registrado: 26 fragmentos.
  - E.070 24.7 es una imagen: se verificó visualmente en la p. 21.
  - Uso: `python scripts/verificar_normativa_e030.py` (devuelve 0 solo si todo coincide).

## Qué NO hace

- No clasifica el sistema estructural, el perfil de suelo, la categoría ni las irregularidades: son **entradas declaradas** con su fuente.
- No declara cumplimiento. Un control solo cuenta como «verificado» cuando se evalúa con resultados del modelo; antes es «no evaluado».

## Calibración por cotas y registro entre láminas

`draft2model.calibracion_ejes`:
- **`ejes_desde_texto`:** obtiene los ejes por sus globos de texto vectorial. Un rótulo ambiguo se rechaza; se declara con `fijar` y la declaración queda registrada.
- **`calibrar_cadena`:** calcula k por tramo a partir de una fila de cotas impresas, con residuos. Los tramos sin cota quedan «sin_referencia».
- **`registrar`:** a partir de correspondencias declaradas entre láminas, obtiene la escala, el sentido, los residuos y la posición derivada de cada eje.

La escala nominal del rótulo no se usa, y que una distancia resulte redonda no prueba la escala.

## Encargo 09

### E.030: correcciones y Vs30

- **Cortante estático (art. 34):** se informa el coeficiente bruto (`C_R`, `V_bruto_kN`) y el aplicado, `max(C/R, 0,11)`; `V_kN` es el valor utilizable.
- **Dominios:** se valida siempre 0 < TP < TL, y Z, U, S, R y P deben ser > 0.
- **Interpolación por Vs30** (Tabla 3 y nota de las Tablas 4/5):
  - S2 para 350 ≤ Vs30 < 550 m/s y S3 para 200 ≤ Vs30 < 350 m/s;
  - t = (máx − Vs)/(máx − mín), con el extremo rígido emparejado con el primer valor de cada intervalo (continuidad con el perfil más rígido);
  - fuera del intervalo del perfil declarado se rechaza: no se extrapola ni se cambia de perfil.

### `draft2model.configuracion_normativa`

Convierte decisiones explícitas `{valor, estado, fuente}` (estado: `declarada_usuario`, `hipotesis_piloto` o `lectura_expediente`) en registros de configuración:

- **Materiales:** Ec por E.060 y Em por E.070, con pesos de E.020. Sin tipo de unidad de albañilería → faltante.
- **Espectro:** en m/s², con g y R incluidos. Se añade la hipótesis de escala del caso = 1.
- **Fuentes oficiales:** URL pública y SHA-256 del PDF (`FUENTES_OFICIALES`). Se pueden comprobar descargándolas y calculando su SHA.
- **Faltantes:** uno por cada puerta no satisfecha.

Las puertas son distintas: sin perfil o sistema no hay espectro, pero los materiales se completan igual.

`scripts/verificar_normativa_e030.py` contrasta 29 fragmentos con los textos oficiales registrados por Codex.
