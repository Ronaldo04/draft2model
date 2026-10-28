# Informe Claude — relectura final 176

Fecha: 20 de octubre de 2026. Carpeta comprobada: `…/AECODE AI TALENT/PROYECTO FINAL`.

**Restricciones cumplidas:**
- Cero llamadas a API y ninguna clave leída.
- ETABS real sin tocar (ni el PID 39368 ni `tmp/d2/motor.lock`).
- Sin instalaciones ni cambios de políticas, sin suite global y sin archivos ajenos editados.

## 1. Fallo focal de la revisión 176: entorno, aislado y reproducible

**Síntoma:** 14 errores «El puente no publicó respuesta (salida 1)» y 1 fallo (`codigo_proceso` 1 en lugar de 42), todos en las pruebas del script real. Es el mismo patrón que el primer intento restringido de la revisión 163.

**Causa demostrada:** la directiva de ejecución efectiva impide `-File`, así que `verificar_modelo_guardado.ps1` no se carga.
- Reproducción sin cambiar políticas: `-ExecutionPolicy Restricted` solo en el proceso hijo devuelve salida 1, ninguna respuesta y stderr «cannot be loaded because running scripts is disabled» (`tmp/claude_relectura_176/reproduccion_restricted_stderr.txt`).
- El ensamblado falso sí compila porque usa `-EncodedCommand`, que no está sujeto a la directiva.
- En este host: directiva RemoteSigned (CurrentUser) y sin `Zone.Identifier` (`directiva_efectiva.txt`, `flujos_alternos.txt`). Aquí las 9 pruebas del script pasaban (`reproduccion_script.log`).

**Corrección, sin debilitar nada:**
- **Python:** diagnostica el puente sin respuesta (`ErrorPuente(tipo="entorno")`, causa `directiva_de_ejecucion_impide_file`, stderr sin rutas). Conserva `codigo_proceso` y la marca de incertidumbre.
- **Pruebas del script real:** se omiten con la causa si la sonda `-File` la bloquea.
- **`DiagnosticoEntornoTests`:** reproduce siempre el bloqueo.
- **Simulación** con `PSExecutionPolicyPreference=Restricted` (variable de proceso): 25 OK y 1 omitida con causa (`simulacion_restringida.log`).

## 2. Unidades (bloqueo real de d4)

- **EDB:** `tmp/d4/ensayo/modelo.edb`, con SHA `c71d19cff0c891021787c95d01bd0a0464279cc38821e1b5a1dda49d8e1fa305` (contrastado). Reabre en N_mm_C.
- **Lector 0.4.0:** registra las unidades presentes y devuelve los valores brutos. Python normaliza con factores racionales exactos por magnitud; los sistemas admitidos son `(N|kN)_(mm|cm|m)_C`.
- **Lo que queda incompleto:**
  - una unidad no admitida;
  - el SF espectral (aceleración), cuya conversión por la API no está comprobada.
- **Plan real d4:** su expectativa es válida, con 69 operaciones y ninguna sin lector (`expectativa_plan_d4.txt`).
- **Pruebas:**
  - equivalencia física N_mm_C frente a kN_m_C, con una escala independiente escrita en la prueba;
  - factor erróneo (cm declarados como mm) y valores sin reexpresar dan discrepancias;
  - kip_in_F da incompleto;
  - una lectura parcial da incompleto;
  - en el plan dinámico, el SF queda incompleto;
  - con el script real, N_mm_C persistido se verifica y lb_in_F da incompleto.

## 3. Aberturas (plan 0.3 en revisión de Codex; solo leído)

- **Expectativa:** acepta `validar_plan_aberturas`. Cada `SetOpening` es expectativa exacta (host `False` y `ABERTURA.HUECO1` `True`).
- **Lector:** `GetOpening(String Name, Boolean& IsOpening)`, firma reflejada en la DLL 1.29.0.0. Total: 61 firmas.
- **Contorno y propiedad del hueco:** se comparan como cualquier área (propiedad `None`).
- **Discrepancias detectadas:** host marcado como hueco, hueco no marcado, contorno, sección inventada, carga al hueco y hueco ausente.
- **Incompleto:** `GetOpening` con retorno distinto de 0.
- **Inventario:** retirar `SetOpening` del inventario deja el resultado incompleto, sin verificación global.
- **No afirmado:** `efecto_estructural_de_aberturas`. La persistencia no demuestra corte de rigidez, malla ni cargas netas.

## 4. Resultados

| Comando (TEMP/TMP = `tmp/claude_relectura_176`) | Resultado | Log |
|---|---|---|
| `.venv/Scripts/python.exe -m unittest -v tests.test_verificacion_modelo_guardado` | 35 OK, 0 omitidas | `pruebas_focales.log` |
| ídem con `PSExecutionPolicyPreference=Restricted` | 25 OK, 1 omitida (script real, con causa) | `simulacion_restringida.log` |
| `.venv/Scripts/python.exe -m unittest -v tests.test_vinculo_verificacion_modelo` (sin editar) | 6 OK | `vinculo_codex.log` |

**Cambios de expectativas, por contrato y no para ocultar regresiones:**
- `SetOpening` ahora tiene lector real (antes se exigía que no estuviera inventariado).
- Unas unidades distintas ya no son un error del script, sino incompleto o normalización.
- El caso de «esquema inválido» usa un nombre de unidad mal formado.
- La mutación «área ausente» retira también `areas.aberturas`.

## 5. Dependencias para Codex

1. **Ensayo real en copia propia:**
   - leer el EDB d4 en N_mm_C con este lector (`configuracion_real`) y comprobar la normalización;
   - confirmar si el SF espectral usa unidades presentes; hasta entonces queda incompleto;
   - Ribbed y Waffle, y alto total;
   - convenio de `GetLocalAxes`;
   - persistencia de `GetOpening` y de la propiedad `None`;
   - tablas de visualización, centinela de `GetValues`, `Disconnect` y orden de `GetPoints`.
2. **Host de revisión:** ejecutar las pruebas del script real donde la directiva permita `-File` sin `Bypass`; si no, quedarán omitidas con la causa.
3. **Vínculo y UI:** el vínculo lee `VERSION` y `VERSION_LECTOR` de forma dinámica (6 OK). Para la UI y el informe, conviene presentar `resultado.unidades` y `controles_no_afirmados` (incluye el efecto de las aberturas).
4. **Compilador 0.3:** si cambian sus operaciones (nombres `ABERTURA.*`, propiedad `None`, `SetOpening` en hosts), revisar `expectativa_desde_plan`. No se flexibilizó ningún validador.
