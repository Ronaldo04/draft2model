# Informe de Entrega: Referencia Visual Asistida (Tarea 327)

## 1. Declaración de origen y estado
- **Anotador**: Antigravity (IA), actuando exclusivamente como asistente de lectura y anotación visual documental.
- **Naturaleza del entregable**: Propuesta asistida por IA, pendiente de revisión y validación independiente por Codex.
- **Revisión humana**: No realizada (`revision_humana_realizada: false`). No constituye aprobación de ingeniería ni peritaje técnico.
- **Métricas**: No se calcularon métricas de precisión, cobertura, correspondencias con extracciones previas ni conformidad normativa, conforme a las instrucciones de parada.
- **Consultas previas**: No se consultaron respuestas anteriores de modelos ni resultados previos del pipeline (`respuestas_previas_consultadas: false`).

## 2. Archivos consultados e integridad de entradas
Se consultaron exclusivamente los archivos del caso `provisional-001` especificados en el manifiesto:
- `entradas/originales/lamina-0001.pdf` (SHA256: `ff669f23633b7c355bc7d89ea60809856df7e29a5b4019204307f7deef9ba8f5`)
- `entradas/originales/lamina-0002.pdf` (SHA256: `d655e6c5f2c8998a2049b300b83a65a62962c5de03a622bfd9978fd4a8f074fa`)
- `entradas/originales/lamina-0003.pdf` (SHA256: `fb4284e82b7a55f4faeb4e9917269b37e94336c0788562873385e7e21c67a134`)
- `entradas/imagenes/archivo-0001-pagina-0001.png` (SHA256: `0436282238faf2cf4521950e40b36fe5f6447ed2332a23f88aae847ee414fd12`)
- `entradas/imagenes/archivo-0002-pagina-0001.png` (SHA256: `569efb41677be4ddc8504916461f8c28757acac007df307f4710a9387f3e77d4`)
- `entradas/imagenes/archivo-0003-pagina-0001.png` (SHA256: `4f0c30d7b4193856ce77f79f3f8be1dafa842f8c80c1a91941cb4c68fe347d6e`)
- `entradas/fuentes.json` y `INSTRUCCIONES.md`.

Los hashes SHA256 de todas las entradas permanecen íntegros e idénticos a los registrados en `MANIFIESTO_ENTRADAS.json`.
Dimensiones canónicas de referencia: 2399 x 1698 px para las tres imágenes PNG.

## 3. Resumen cuantitativo de observaciones
- **Total observaciones**: 33 observaciones respaldadas con recortes independientes.
- **Distribución por lámina**:
  - `L0001` (Cimentación): 11 observaciones (`AG-0001` a `AG-0011`).
  - `L0002` (Aligerados 1-3): 11 observaciones (`AG-0012` a `AG-0022`).
  - `L0003` (Aligerado 4): 11 observaciones (`AG-0023` a `AG-0033`).
- **Distribución por clase**:
  - `cota`: 15 observaciones.
  - `etiqueta`: 10 observaciones.
  - `elemento`: 8 observaciones.
- **Distribución por legibilidad**:
  - `legible`: 32 observaciones.
  - `ambigua`: 1 observación (`AG-0018`, cota dual/alternativa con `valor: null`).
  - `ilegible`: 0 observaciones.

## 4. Método visual y herramientas empleadas
- Inspección visual de las láminas PNG y confirmación complementaria sobre trazados PDF vectoriales.
- Calibración y delimitación precisa de cajas envolventes en píxeles sobre las imágenes canónicas.
- Extracción de recortes individuales de evidencia espacial guardados en `salidas/recortes/<id>.png`.
- Conversión al sistema `pagina_visible_normalizada`: `[x0/2399, y0/1698, x1/2399, y1/1698]`, con `0 <= x0 < x1 <= 1` y `0 <= y0 < y1 <= 1`.
- Herramientas locales ejecutadas: entorno Python (Pillow, OpenCV headless, hashlib, json, csv).

## 5. Criterios de transcripción, dudas y limitaciones
- **Alineación estricta de unidades**: Conforme a la regla de no inferencia, las cotas aisladas sin texto de unidad se etiquetaron como `unidad: "desconocida"`. Solo se asignó `m` cuando la evidencia textual lo acreditó directamente (`AG-0010` en `RESUMEN : SUELOS` con `1.50 m.` y `AG-0030` en tabla de empalmes con encabezado `T m.`). Etiquetas y elementos usan `no_aplica`.
- **Caso ambiguo real (`AG-0018`)**: En la sección CORTE 1-1 de vigas (`L0002`), la cota vertical de peralte indica `"0.40 ó 0.50"`. Debido a la multiplicidad de valores válidos en la fuente, se transcribió como `valor: null`, `legibilidad: "ambigua"` y nota explicativa.
- **Alcance geométrico**: No se completaron dimensiones no acotadas ni se calcularon alturas o ejes por suposición estructural.

## 6. Comprobaciones ejecutadas y resultado
1. **Verificación de integridad de entradas**: Hashes SHA256 coincidentes antes y después de la tarea.
2. **Coherencia JSON / CSV**: Comprobación campo a campo de las 33 observaciones entre `referencia_propuesta_ia.json` y `observaciones.csv`.
3. **Revisión en orden inverso (Segunda pasada)**: Ejecutada de `AG-0033` a `AG-0001` validando correspondencia entre imagen, recorte, coordenadas y tipología.
4. **Validación de bboxes**: Verificado cumplimiento estricto de límites normales `[0, 1]` y orientación canónica.
