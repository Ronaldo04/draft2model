# Revisión del guion de transporte09T — 256

Hallazgo reproducido sin ejecutar el guion ni ETABS: el predicado de salida original devuelve éxito para construcción con cierreFalse/error_cierre y relectura discrepante/incompleta. `REPRODUCCION_SALIDA_09T_255.json` conserva cinco contrastes del AST real (cuatro falsos éxitos y un error explícito reconocido).

El subagente preparó una corrección aislada y alcanzó un límite de uso. Codex comprobó después `ordinaryUsageAllowed=true` (ventana5h0%, semanal94%) y terminó la revisión directamente, sin reiniciar al agente ni repetir pruebas nativas. Ese error del agente no prueba un bloqueo global vigente.

## Candidato y verificación propia

`tmp/recorrido_seguro_255/` contiene el runner candidato, `validacion_etapas_255.py`, pruebas, fuentes congeladas255/256 y `candidato_256.patch`. **16 pruebas propias offline OK0.300s**. Usan el main candidato con dependencias/etapas simuladas y las funciones de aprobación con un doble que detiene antes de cualquier llamada nativa; nunca se importa/ejecuta el runner original ni se crean aprobaciones privadas reales.

Cambios propuestos:

- Éxito de construcción requiere estadoOK, cierre propio confirmado y plantilla con huella esperada/anterior/posterior idénticas.
- Relectura exige construcción válida, estadoverificado y cero discrepancias/incompletos; sus estados negativos ya no producen exit0.
- Análisis exige relectura y revisión explícita de los cinco controles existentes, por actor/fecha/alcance y evidencias con hashes ligadas al modelo. No convierte automáticamente todos los controles enTrue por existir relectura ni asigna al usuario una revisión propia no observada.
- El sidecar de revisión se lee una sola vez a bytes, su hash corresponde a esos mismos bytes y un cambio durante la comprobación impide aprobar.
- El directorio de trabajo absoluto o relativo se resuelve antes de exigir contención en tmp; no admite tmp/../data ni reutilizar una construcción existente.
- `etabs_real` solo pasa aTrue cuando se observa apertura real; no constituye por sí mismo prueba de análisis completo.

## Integración pendiente, preservación de Claude

El runner vivo **cambió durante la revisión**: Claude corrigióMODAL→MODAL-E030 en parámetros y consultas. SHA observado de esa versión:`3f28c4787b49c44c49f70a251d6faecad9d4b83bb9903cd9f88224eea409dcc9`. El candidato conserva ambas correcciones. Los mensajes dañados de codificación introducidos en la preparación se repararon en el candidato.

**No se sobrescribió el runner vivo ni su configuración.** `CANDIDATO_RECORRIDO_256.json` conserva la base y huella del candidato. Claude debe integrar el parche contra sus fuentes más recientes, incorporando el helper y sus pruebas; no aplicar ciegamente a un hash distinto. La corrección aún no está activa en su runner ni ha pasado una prueba nativa integrada. No declarar el fallo resuelto en producción hasta esa integración.

No se ejecutaron proveedorLLM, plan/malla/solver, nuevas instanciasETABS ni un modelo de referencia. La aprobación profesional y el cierre general del piloto permanecen fuera de estas pruebas de software.
