# Continuación267 — integración revisada y cierre del recorrido

Mantén el mismo proyecto/carpeta y el proceso de resultados actual. No reinicies un proceso vivo por falta de salida ni abras otra corrida. El registro conserva errores históricos; Codex observó Python27864 (creado17:41:43) y una lectura posterior real b8d0f12e93ce4014b57fb3008623a682 con respuesta escrita18:05:19, todavía sin aceptación al último corte.

## Cambios de Codex listos para integrar

Acuerdo267 confirmado anteriormente: archivos de servicios e interfaz de masa separados del trabajo nativo/CLI. `seguimiento/REVISION_WEB_MASA_267.json` conserva hashes y pruebas. Se añadió además `docs/FLUJO_MASA_WEB.md`.

- Opt-in `resultados_api`, revalidación completa y puente web de captura real en `revision_lecturas.py`.
- Referencias optativas exactas de inventario y masa en creación, consulta, descarga y aprobación documental en `revision_entregables.py`.
- Puente de fuente web en `informe._masa_nativa`, con misma contabilidad numérica; se rechaza doble como masa nativa.
- Se corrigió un fallo observado de exportación HTML: `renderizar_html` reutilizaba `c` para el contraste de masa y fallaba con `KeyError: titulo`. Ahora usa `contraste_masa`. No revertir.
- Controles de lectura/informe e invalidación de selecciones en la UI; no arrays de masa en eventos públicos.

Pruebas propias:22previasOK,3ciclo documental nuevoOK,2puente/rechazoOK,1persistencia de lecturaOK y4NodeOK. QA web real con fixture: resultado→análisis→crear→descargarJSON/PDF, bytes idénticos y siete categorías; inventario habilitado y masa nativa bloqueada para sintéticos. No es validación del piloto. Evidencia `QA_WEB_MASA_267.json/png`.

## Evidencia real ya contrastada, sin repetir ensayos

`REVISION_ANALISIS_267.json`: candidata cbfdd041 íntegra,7/7 hashes del marcador, análisis7203… aceptado real/no sintético/6casosCSI4. Fix de booleanos revisado separadamente con6casosOK. `REVISION_LECTURAS_09D1_267.json`: treslecturas y recibos coinciden con ese análisis/EDB; reacciones CAGUA de fuerza y momento coinciden6/6 con contraste analítico264, usando misma configuración operativa (difiere solo revisión). No acredita masa ensamblada ni hidrodinámica.

## Continuar automáticamente por dependencias

1. Concluir la misma cadena de lectura/masa y su aceptación; conservar fallos como evidencia y corregir su causa si termina con error. No sustituir evidencia nativa con JSON armado ni aflojar tolerancias para obtener coherencia.
2. Normalizar, controles, reglas condicionales de escenarios identificados e informes. Las derivas elásticas máximas observadas son SX0.001402/SY0.005976 enN3: los factores inelásticos y eventuales incumplimientos deben mostrarse, no ajustar el modelo para hacer pasar una regla. No son revisión de ingeniería.
3. Publicar resultado y referencias en los servicios habituales; probar panel y generación/descarga del caso por interfaz. La CLI no sustituye este enlace. Conservar fuentes normativas, abstención de sitio sin capa/EMS, incertidumbres geométricas y siete categorías.
4. Actualizar guía/matriz y producir la entrega final con fuentes estables y evidencias. La copia `AECODE_CANDIDATO_267` NO es final: su verificación completa está en proceso, sesión propia de Codex16058; no duplicarla ni atribuir su resultado a bytes posteriores. No APIs.

## Rendimiento observado, sin debilitar verificación

La consulta pura `verificar_analisis_aceptado` tardó más de300s y recorre `consultar_aprobacion→consultar→_validar→generar_plan_malla`. Es coste de regeneración del plan, no solver. Los servicios vuelven a consultarlo varias veces por operación. Codex estudia una reutilización acotada de la preparación PURA de malla en archivos nuevos; no editar su reserva ni reiniciar la cadena actual para aplicarla. Conservar lectura de fuentes y verificación de huellas; nunca cachear una aprobación o vigencia solo por nombre/mtime.

Al cerrar cada dependencia, conservar logs/identidades/hashes y continuar la siguiente. Marca final solo cuando todos los requisitos estén demostrados; el goal sigue abierto.

## Incidente nativo comunicado por Claude

Tu respuesta observada en la ventana informó que analizar_modelo_etabs.ps1 no cierra su instancia propia; el runner aplica un cierre externo verificado. Corrige esa brecha en el flujo GENERAL, con pruebas focales y propiedad/PID/modelo exactos, sin tocar instancias ajenas ni reinterpretar registros históricos como cierres acreditados. El parche del runner no sustituye cerrar o declarar correctamente la instancia desde el adaptador/servicios del producto. Hazlo en paralelo seguro a la espera actual, preservando contratos y evidencia previa. Evita reiniciar el proceso de resultados por esta corrección; integrará el arreglo en las ejecuciones posteriores.
