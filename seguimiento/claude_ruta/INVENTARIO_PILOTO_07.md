# Inventario trazable del caso real `provisional-001` (encargo 07)

Fecha: 21 de octubre de 2026.

**Fuentes**
- Láminas originales L0001 (E-01 Cimentación), L0002 (E-02 Aligerados 1.º a 3.º) y L0003 (E-03 Aligerado 4.º, tanque y cisterna). Las tres tienen SHA comprobado y están fechadas en «ABRIL 2005».
- Extracciones reales registradas: OpenAI 1 (`6379ec06`), 3 (`dcdf242b`) y 4 (`df4b88d3`), y Gemini 1 (`1cde498b`). La petición 2 se truncó y no se importó.

**Reglas aplicadas**
- Las lecturas siguen pendientes.
- Las clasificaciones propuestas viven en las versiones 0.2.0 derivadas:

  | Versión 0.2.0 | Versión de origen | Propuestas |
  |---|---|---|
  | `fe3eb621` | `6379ec06` | 3 |
  | `3bc8d0fd` | `dcdf242b` | 31 |
  | `bcd21202` | `df4b88d3` | 50 |
  | `9099a5c1` | `1cde498b` | 4 |

- Ninguna lectura está aprobada. Los valores impresos son **declaraciones del expediente**, no parámetros vigentes ni normativa revisada.
- Los resultados impresos de L0001 (Vx, Vy = 0.166 Peso; Δx = 11.741 mm; Δy = 13.464 mm) quedan clasificados como `resultado_impreso`. Se excluyen de entradas y calibración.

## 1. Calidad de las extracciones contra los originales

| Extracción | Candidatos | Valores | Bbox (auditoría de tinta, `draft2model.auditoria_evidencia`) | Omisiones comprobadas en el original |
|---|---|---|---|---|
| OpenAI 1 | 34 | Muestra asistida 8/10 (informe 04) | 2 vacías | REC0002 y REC0004 sin lecturas (R213) |
| OpenAI 3 | 60 | Correctos en lo revisado (REC0001 a REC0003) | 8 vacías. Desplazamiento sistemático de aproximadamente una línea en REC0002 y REC0003 | Ver la lista de omisiones de OpenAI 3 bajo esta tabla |
| OpenAI 4 | 102 | **C033 erróneo**: el original dice «NFC=-2.65m» y se leyó -2.6 m | **30 vacías** | Ver la lista de omisiones de OpenAI 4 bajo esta tabla |
| Gemini 1 | 32 | Los leídos son correctos | 4 vacías | Ver la lista de omisiones de Gemini 1 bajo esta tabla |

**Omisiones de OpenAI 3**
- Patas .40/.15 de C-1.
- Estribos.
- Toda la tabla de placas PL-1 a PL-9 (vertical, horizontal y esquinas).
- Traslapes de 50 y 60 cm.
- «POBREMENTE GRADUADA».

**Omisiones de OpenAI 4**
- Contrapasos y pasos de la escalera.
- Planta del tanque (no se halló en E-01 a E-03).

**Omisiones de Gemini 1**
- f'm = 35, σt = 4.00 y todos los parámetros sísmicos (R224).
- REC0003: solo leyó 1.5 m.

Que el JSON sea válido no prueba cobertura. La auditoría de tinta solo demuestra regiones **sin trazos**: una bbox «con_trazos» puede seguir desplazada.

## 2. Datos documentados (existen; no se piden al usuario)

| Dato | Valor impreso | Fuente (lámina · zona) | Candidato o estado |
|---|---|---|---|
| f'c concreto | 210 kgf/cm² | L0001 · especificaciones | OpenAI3 C031, Gemini C025 (propuesta: propiedad) |
| f'c de los muros de concreto de los cortes 2-2 y 5-5 (e = .10, altura de 2.40 sobre NFP, malla ø3/8" @ .25) | 175 kgf/cm² | L0001 · cortes de cimientos | **No extraído**: Claude lo comprobó visualmente en el original. Falta su lectura con evidencia. No se sabe qué muros son (¿cerco?) |
| fy | 4200 kgf/cm² | L0001 · especificaciones | OpenAI3 C030, Gemini C024 |
| f'm (King-Kong a máquina) | 35 kgf/cm² | L0001 · especificaciones | OpenAI3 C035 |
| Presión admisible σt | 4.00 kgf/cm² | L0001 · especificaciones y resumen de suelos | OpenAI3 C038 y C058 |
| Profundidad de cimientos; tipo de suelo | 1.50 m; GP, grava arenosa pobremente graduada | L0001 · resumen de suelos | OpenAI3 C059, C060 |
| S/C | 200 kgf/m² en pisos 1.º a 4.º; azotea 150; escalera 200 | L0001 · especificaciones; L0002 y L0003 · títulos | OpenAI3 C043 y C044; OpenAI4 C074 y C101 |
| Losas | Aligerado e = 17 cm en los niveles 1, 2–3 y 4; detalle con capa .05, ladrillo .12 y viguetas .10 cada .40 | L0002 y L0003 · títulos; L0003 · detalle típico | OpenAI1 C018 y C027; OpenAI4 C100–C102 y C066–C071 |
| Parámetros sísmicos declarados | Z = 0.40, U = 1.00, S = 1.00, Tp = 0.40, Rx = Ry = 6, C = 2.50 | L0001 · parámetros sísmicos | OpenAI3 C047–C053 |
| Columnas | C-1 en L (.40 × .40, patas .15); C-2 .15 × .40; C-3 .15 × .60; C-4 .15 × .40; C-5 .15 × .30; C-6 .15 × .75 | L0001 · cuadro de columnas | OpenAI3, Gemini |
| Placas PL-1 a PL-10 | Armado en tabla; longitudes en planta **sin cota** | L0001 · cuadro de placas | No extraído (tabla) |
| Vigas | VS 0.15 × 0.30 (chatas); cortes 1-1 a 6-6 (.40/.50 de peralte) | L0002 · cortes de vigas | Parcial (OpenAI1 C011 y C020) |
| Cisterna (existe) | Interior 2.00 × 2.15 en planta; altura interior 2.22; muros .20; techo .15; fondo .20; NFC = -2.65 m | L0003 · corte y techo de cisterna; L0001 · planta | OpenAI4 C022–C033 y C050–C056 (C033 corregido en propuesta) |
| Tanque elevado (existe) | Alturas .10/.20/.45/1.10/.20; apoyos de 2.00; NT = +10.35 m | L0003 · corte del tanque | OpenAI4 C002–C010 |
| Escalera | Dos tramos con descanso; cotas .80, .50, .70, .60, .40 y .20; S/C 200 | L0002 · escalera típica | OpenAI4 C073–C099 (con bbox débiles) |
| Ejes | A a I y 1 a 3, como texto vectorial con posición | L0001, L0002 y L0003 | Extraídos por Claude del PDF vectorial |

## 3. Derivable con procedimiento explícito (pendiente de aceptación)

- **Distancias entre ejes y contornos en planta.** Las láminas estructurales **no imprimen** cotas entre ejes.
  - Hipótesis de calibración por referencias impresas en `CALIBRACION_L0001_07.json`: k = 0.012558 m/pt ± 0.25 %.
  - Los tramos quedan dentro de un intervalo. Ejemplo: A–I mide 19.89–19.99 m y 1–3 mide 9.95–9.99 m.
  - La escala nominal 1/50 **no** sirve: el PDF no está a escala real (con 1/50, el 1.20 mediría 1.69).
  - Que H–I y 1–2 den ≈ 5.0 m no prueba la escala.
  - Hay una discrepancia: el eje F está desplazado ≈ 0.50 m entre L0001 y L0003.
- **Posición de muros, placas y columnas** a partir de la geometría vectorial, con la misma calibración. Está sin ejecutar: depende de que se acepte la hipótesis anterior.
- **Peldaños**, contando los escalones del corte. Exige además la altura de entrepiso.

## 4. Lista mínima de decisiones o datos que solo el usuario puede aportar

Está en `FALTANTES_USUARIO_07.json`, con un formato que permite responder punto por punto.

1. **Alturas de entrepiso y NPT de los niveles 1 a 4.** No están impresas en E-01 a E-03. Solo constan NFP = -0.05, NFC = -1.50 y NT = +10.35 (base de los apoyos del tanque). Se necesita la lámina de arquitectura o la cifra declarada.
2. **Cotas entre ejes.** Hay dos opciones: aportar las láminas de arquitectura o cotas, o aceptar expresamente la calibración derivada con su incertidumbre. Además, aclarar la posición del eje F (L0001 frente a L0003).
3. **Sobrecarga del 4.º nivel.** Las especificaciones dicen «1er al 4to piso = 200; azotea = 150», pero el título de L0003 dice «4TO NIVEL S/C: 150». Hay que decidir cuál rige y si el 4.º nivel es la azotea.
4. **Edición normativa sísmica.** Los planos (2005) declaran Z, U, S, Tp, R y C. Hay que decidir si se modela con esos valores como declaración del expediente o con la E.030 vigente (RM 183-2026 y 217-2026), indicando edición y artículo.
5. **Idealización de los muros portantes de albañilería confinada** (King-Kong, f'm = 35) y módulos E de concreto y albañilería. E no está impreso: derivarlo con una fórmula normativa es una decisión técnica con fuente.
6. **Cargas muertas no impresas:** acabados, tabiquería y pesos específicos.
7. **Líquidos.** La cisterna y el tanque existen, así que la aplicabilidad es `presente`. Falta el nivel de agua operativo de cada recipiente y si se modelan lleno y vacío. Las alturas interiores están impresas; el nivel libre no.
8. **Condición de apoyo**, con cimiento corrido a NFC = -1.50: empotramiento u otra idealización.

## 5. Pendientes que NO son del usuario

- Evidencias con bbox vacías o desplazadas. El revisor debe reubicarlas o rechazarlas. **Falta en el código** la operación de reubicar una evidencia en la revisión (hoy solo se corrigen valor, unidad y tipo).
- Lecturas omitidas, pero visibles en los originales (tabla de placas, f'c 175, peldaños, patas de C-1). Hay dos vías: una petición focal adicional, que ejecutaría Codex (queda 1 de 5 en OpenAI), o la lectura manual del revisor con evidencia.
- La conversión a geometría 0.3 y la configuración 0.5 (líquidos `presente`) se prepararán cuando existan cotas aceptadas. **No se construyen borradores geométricos con distancias no aceptadas.** Se usa como sustituto el borrador de configuración generado por `plantilla_configuracion`, con sus faltantes explícitos.
