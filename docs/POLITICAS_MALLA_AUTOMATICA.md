# Políticas Automáticas de Nodos Derivados y Subdivisión de Barras (`0.1.0`)

Módulo: `draft2model/politicas_malla_automatica.py`

## 1. Propósito y fronteras de ingeniería

Al mallar superficies con aberturas, bordes conectados y cortes por nivel $Z$ en configuraciones `0.4.0` y `0.5.0`, `draft2model.malla_preparacion.preparar_malla` genera de forma determinista:

- Nodos derivados de partición y compatibilidad (`MN_<host>_<k>`).
- Nodos derivados por cortes explícitos de nivel (`MC_<k>`).
- Subdivisiones conformes requeridas sobre barras que atraviesan nodos interiores de malla (`frames_subdivision_requerida`, con subframes `<frame>_S1..<frame>_Sn`).

El validador `draft2model.modelo_estructural` exige declarar explícitamente cada entrada de `nodos_derivados` y `subdivision_frames`. Para evitar la edición manual nodo por nodo desde JSON externo sin introducir heurísticas ocultas, este módulo evalúa **reglas explícitas declaradas por el ingeniero** (por ejemplo, desde la interfaz web) sobre la preparación de malla existente:

- **Reutiliza íntegramente `preparar_malla`:** no reimplementa partición por franjas, compatibilidad de bordes, triangulación ni cortes $Z$.
- **Cero supuestos estructurales implícitos:**
  - **No** asume `z = 0` como apoyo empotrado o articulado.
  - **No** asume diafragmas rígidos o semirrígidos en todos los niveles.
  - **No** asume que extremos fijados (`W1`, `W2`) implican continuidad física de apoyo en los nodos intermedios del segmento, salvo que una regla explícita (`borde_entre_puntos` o `plano_z`) lo declare con fuente y motivo.
  - **No** asume `[False]*6` ni exclusión de diafragma para los nodos restantes si no se declaran `resto_restricciones` y `resto_diafragma`.
  - **No** fusiona ni empareja nodos por cercanía o tolerancias no declaradas.
- **Puro y sin efectos secundarios:** no lee ni escribe expedientes en disco, no realiza llamadas de red ni APIs, no invoca ETABS, no muta los diccionarios de entrada, no maquilla faltantes ajenos a la malla y siempre entrega copias en `estado = "borrador"` (`aprobacion = None`).

---

## 2. Contrato cerrado de reglas (`draft2model.reglas_politica_malla` `0.1.0`)

Cualquier clave adicional o faltante es rechazada por `validar_reglas_politica(reglas)`.

```json
{
  "contrato": "draft2model.reglas_politica_malla",
  "version_contrato": "0.1.0",
  "unidad_longitud": "m",
  "reglas_restricciones": [
    {
      "id": "APOYO_BASE_MURO",
      "selector": {
        "tipo": "borde_entre_puntos",
        "inicio": "W1",
        "fin": "W2",
        "hosts": ["S2"]
      },
      "restricciones": [true, true, true, true, true, true],
      "fuente": "F-PLANO-CIM",
      "motivo": "Cimentación corrida explícita bajo muro S2 entre W1 y W2."
    }
  ],
  "resto_restricciones": {
    "restricciones": [false, false, false, false, false, false],
    "fuente": "F-CRITERIO-MALLA",
    "motivo": "Nodos interiores y superiores sin vínculo externo a tierra."
  },
  "reglas_diafragma": [
    {
      "id": "DIAFRAGMA_LOSA_Z26",
      "selector": {
        "tipo": "plano_z",
        "z_m": 2.6
      },
      "accion": "asignar",
      "diafragma": "DIA1",
      "motivo_sin_diafragma": null,
      "fuente": "F-PLANO-LOSA"
    }
  ],
  "resto_diafragma": {
    "accion": "excluir",
    "diafragma": null,
    "motivo_sin_diafragma": "Nodos fuera de la cota del diafragma declarado.",
    "fuente": "F-CRITERIO-MALLA"
  },
  "subdivision_frames": {
    "modo": "autorizar_calculadas",
    "fuente": "F-PLANO-LOSA",
    "motivo": "Compatibilidad geométrica de barras con malla conforme de superficie."
  }
}
```

### 2.1 Tipos de `selector` admitidos (contrato cerrado)

1. **`plano_z`**
   - Claves obligatorias: `tipo: "plano_z"`, `z_m` (número finito en metros; igualdad exacta con `xyz_m[2]` normalizado a metros en `geometria_m`).
   - Claves opcionales: `hosts` (`list[str]` no vacía de superficies malladas), `solo_corte` (`bool`, filtra exclusivamente nodos `MC_*` o `MN_*`).
2. **`borde_entre_puntos`**
   - Claves obligatorias: `tipo: "borde_entre_puntos"`, `inicio` (`str`), `fin` (`str`, distinto de `inicio`, ambos existentes en `configuracion.puntos` con distancia positiva).
   - Claves opcionales: `hosts` (`list[str]`).
   - Selecciona los nodos derivados situados estrictamente en el interior del segmento abierto `(inicio, fin)` bajo el mismo criterio exacto en `Fraction` empleado por `malla_preparacion`.
3. **`entidades`**
   - Clave obligatoria: `tipo: "entidades"`, más al menos un filtro explícito no nulo entre:
     - `hosts`: `list[str]` de superficies host malladas.
     - `aberturas`: `list[str]` de aberturas pertenecientes a hosts mallados (detecta tanto nodos de barrido `MN_*` como cortes `MC_*` sobre aristas del hueco).
     - `conexiones_borde`: `list[str]` de conexiones declaradas en `conexiones_borde` (incluye nodos `MN_*` compartidos y cortes `MC_*` sobre la arista conectada).
     - `nodos_corte`: `bool`.
   - Si se combinan varios filtros dentro de un mismo selector `entidades`, se evalúa su intersección lógica (`AND`).
4. **`nodos`**
   - Claves exactas: `tipo: "nodos"`, `nodos` (`list[str]` de nombres CSI existentes en `prep["nodos_derivados"]`; rechaza puntos originales de configuración o identificadores inexistentes).

### 2.2 Modos de `subdivision_frames`

- `null`: sin política declarada; cualquier barra en `frames_subdivision_requerida` queda reportada en `pendientes`.
- `{"modo": "autorizar_calculadas", "fuente": "...", "motivo": "..."}`: genera automáticamente todas las entradas `subdivision_frames` con el orden exacto de `nodos` y los IDs deterministas `<frame>_S1..Sk` calculados por `preparar_malla`.
- `{"modo": "por_frame", "reglas_frames": [{"id": "...", "frames": ["..."], "accion": "autorizar" | "bloquear", "fuente": "...", "motivo": "..."}]}`: control individual por barra; rechaza barras inexistentes o barras sin nodos interiores de malla, señala `pendientes` si falta alguna barra requerida o si se bloquea explícitamente, y señala `conflictos` si dos reglas se contradicen sobre la misma barra.

---

## 3. Semántica de pendientes, conflictos y fuentes

- **Pendientes (`pendientes`):** todo nodo derivado sin regla de restricción (ni `resto_restricciones`), todo nodo derivado sin regla de diafragma (ni `resto_diafragma`) y toda barra subdividida sin regla de autorización generan registros concretos en `pendientes`. No se inventan valores por defecto.
- **Conflictos (`conflictos`):** si dos o más reglas específicas seleccionan el mismo nodo derivado (o la misma barra) con prescripciones distintas, **no se elige la primera regla**: se registra un conflicto explícito listando las reglas involucradas y `listo_para_aplicar` permanece en `False`.
- **Resolución de `fuente` única del registro CSI:** cada elemento de `configuracion["nodos_derivados"]` exige una única clave `fuente` registrada en `configuracion["fuentes"]`:
  - Si restricción y diafragma comparten `fuente`, se usa dicha `fuente`.
  - Si una decisión proviene de una regla específica (`reglas_*`) y la otra de una política general de resto (`resto_*`), el registro CSI adopta la fuente específica mientras `trazabilidad_nodos` conserva ambas fuentes y orígenes.
  - Si ambas provienen del mismo nivel de especificidad (dos reglas específicas o dos políticas `resto_*`) con fuentes distintas, se reporta `conflicto_fuentes_nodo_derivado` sin escoger arbitrariamente una.
- **Coplanaridad de diafragmas:** asignar un diafragma a un nodo derivado cuya coordenada $z$ difiere de la cota de los puntos de ese diafragma produce un error explícito en `errores`.

---

## 4. API pública de integración (interfaz web / Etapa 4)

- `plantilla_reglas_vacia() -> dict`: devuelve un esqueleto válido en contrato `0.1.0` sin reglas asumidas.
- `validar_reglas_politica(reglas) -> list[dict]`: valida sintaxis, tipos booleanos/numéricos finitos, unidad `"m"` y claves cerradas.
- `previsualizar_politicas_malla(geometria, configuracion, reglas=None) -> dict`:
  - Función pura de vista previa (`contrato = "draft2model.propuesta_politicas_malla"`).
  - Expone `inventario_nodos_derivados` (con coordenadas, cota $z$, hosts, aberturas, bordes de superficie, conexiones de borde y marca `es_nodo_corte`), `inventario_subdivision_frames` (con secuencia exacta de nodos y nombres `<frame>_Sk`), `nodos_derivados_propuestos`, `subdivision_frames_propuesta`, `trazabilidad_nodos`, `pendientes`, `conflictos`, `errores`, `listo_para_aplicar` y `huella_propuesta`.
- `aplicar_politicas_malla(geometria, configuracion, reglas) -> dict`:
  - Si `listo_para_aplicar` es `False` o `reglas is None`, lanza `ErrorPoliticaMalla` adjuntando `.propuesta`.
  - Si `listo_para_aplicar` es `True`, devuelve una copia profunda de `configuracion` con `nodos_derivados` y `subdivision_frames` poblados y `revision = {"estado": "borrador", "aprobacion": None}`, preservando intactos `datos_sinteticos`, `geometria_origen` y cualquier otro faltante ajeno a la malla.

## 5. Limitaciones explícitas

- La validación de reglas y de configuración prueba consistencia algorítmica y contractual sobre fixtures sintéticas; **no** sustituye el criterio del ingeniero estructural, **no** implica cumplimiento normativo ni equivale a validación del piloto en ETABS real.
