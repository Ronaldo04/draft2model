# Lecturas semánticas (contrato visual y de extracción 0.2.0)

Encargo 07 de la ruta 201. El piloto real mostró varios problemas:
- cantidades de barras (6, 8) y sobrecargas (200, 150) clasificadas como «cota» con unidad desconocida;
- f'c, fy y f'm leídos como texto sin magnitud;
- resultados previos impresos mezclados con datos de entrada;
- bboxes desplazadas o vacías.

El contrato 0.2.0 corrige esto **sin invalidar** los paquetes ni las extracciones 0.1.0 guardados.

## Tipos y unidades

| Tipo | Valor | Unidades admitidas |
|---|---|---|
| `cota` | Número: **solo longitud geométrica** | m, cm, mm, desconocida |
| `cantidad` | Entero ≥ 0 (barras, piezas) | no_aplica |
| `carga` | Número | kgf/m2, kgf/m, kgf, kN/m2, kN/m, kN, tf/m2, tf/m, tf, desconocida |
| `propiedad` | Número (f'c, fy, f'm, σt, pesos específicos) | kgf/cm2, kgf/m2, MPa, kN/m2, kgf/m3, kN/m3, tf/m3, desconocida |
| `parametro` | Número (Z, U, S, C, R, Tp) | adimensional, s, desconocida |
| `resultado_impreso` | Número o texto | Cualquiera de las anteriores |
| `texto`, `etiqueta`, `elemento` | Texto | no_aplica |

- «Kg/cm2» impreso es kgf/cm2.
- No se convierte ninguna unidad.
- Ninguna magnitud se vuelve parámetro de ingeniería por haberse leído.
- `resultado_impreso` se conserva como lectura, pero **nunca se exporta como entrada** (`excluidos.resultados_impresos`) ni sirve para calibrar.

## Paquete y respuesta 0.2.0

`preparar_paquete(..., version="0.2.0")` es el valor predeterminado. El prompt exige:
- `texto_fuente` literal;
- `simbolo` (o null);
- la `cobertura` de **cada** recorte: `completa`, `parcial` o `sin_lecturas`, con una observación.

El esquema estricto de OpenAI/Gemini incluye `texto_fuente`, de modo que ya no se pide omitirlo. Así se resuelve la incoherencia de la 0.1.

`sin_lecturas` exige cero candidatos y, a la inversa, un recorte sin candidatos debe declararse `sin_lecturas`. Una cobertura `parcial` genera la advertencia `cobertura_incompleta`. **Un JSON válido no prueba que la lectura sea suficiente.**

Los paquetes 0.1.0 siguen cargándose y adaptándose con su esquema y su prompt de origen.

## Revisión (encargo 08)

- **Reclasificar:** `corregir-extraccion --tipo …` (UI: «Tipo de lectura») en una entrada `revisado`. El valor y la unidad se validan contra el tipo revisado.
- **Reubicar evidencia:** `reubicar-extraccion --candidato … --bbox X0 Y0 X1 Y1 --motivo … --fecha … --revisor …`. En la UI, sección «Reubicar evidencia»: primero se previsualiza la región y luego se guarda.
  - Crea una versión nueva con la región corregida sobre el mismo original y página. Conserva `historial_evidencia` (región anterior, región nueva, autor declarado y motivo).
  - **No** cambia el valor, el tipo ni el estado: la lectura sigue pendiente (R232).
- **Lectura manual omitida:** `lectura-manual-extraccion --tipo … --valor-json … --unidad … --texto-fuente "…" --archivo L000n --pagina n --bbox …`. En la UI, sección «Agregar lectura omitida», con previsualización.
  - Recibe un ID `M###` nuevo y procedencia `manual` («no proviene de un modelo de IA»), y queda pendiente.
  - Exige el texto literal y una evidencia en el original con hash comprobado. No sirve para declarar E, alturas o apoyos que no constan.
- **Vigencia:** `vigencia-extraccion` (y la cabecera de la versión en la UI) lista las versiones posteriores y marca como «superada» toda exportación cuyos candidatos cambiaron después. Los derivados no heredan la vigencia de una versión nueva.
- **Migrar 0.1.0 a 0.2.0:** `migrar-extraccion --extraccion <0.1.0> --origen "…" --propuestas p.json`. Las lecturas quedan intactas y cada `clasificacion_propuesta` queda pendiente.
- **Auditar evidencias:** `python -m draft2model auditar-evidencia …`.
  - «vacia» **prueba** que la región no tiene trazos.
  - «con_trazos» **no** confirma el valor: no hay OCR.

## Recuperación con cuarentena (R235)

Si una respuesta 0.2.0 trae candidatos inválidos (bbox invertida, unidad ajena al tipo…), la respuesta completa se rechaza por defecto.

`registrar-respuesta-vision … --cuarentena` (o `adaptar_respuesta(..., cuarentena=True)`) es una **decisión explícita** que funciona así:
- importa los candidatos válidos;
- aparta los inválidos en `cuarentena` con sus errores, sus recortes y el **objeto original íntegro**, sin recortar, reordenar ni corregir nada;
- conserva tal cual la cobertura declarada y añade las advertencias `candidatos_en_cuarentena` y `cobertura_con_cuarentena`;
- registra la cuarentena en `registro.json`;
- no repite ninguna llamada a la API.

El esquema estricto 0.2.0 usa una variante por grupo de tipos, con sus unidades y su clase de valor, así que no admite «elemento» con «m». El orden x0 < x1 lo exige el prompt y lo valida la adaptación.

Nada de lo anterior aprueba ingeniería.

## Cobertura efectiva y cuarentena en la web (encargo 09)

Con cuarentena, cada recorte conserva la cobertura **declarada** por el proveedor (`estado`) y añade `efectiva`:

- `candidatos_declarados`, `recuperados` y `en_cuarentena`;
- un estado que nunca es `completa` si hay apartados;
- el motivo.

El validador rechaza una efectiva elevada o unos conteos incoherentes.

El panel «Respuestas» ofrece la casilla **«Recuperar con cuarentena explícita»**, desmarcada por defecto. El estado de la respuesta muestra los candidatos en cuarentena y la cobertura efectiva por recorte.
