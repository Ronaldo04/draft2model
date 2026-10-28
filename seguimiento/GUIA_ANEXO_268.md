# Anexo candidato del expediente para AECODE

Estado: archivo local verificado por bytes; **no entrega final ni aprobación de ingeniería**.

El candidato `entregas/ANEXO_CASO_CANDIDATO_268/` contiene `Caso.zip` y `MANIFIESTO.json`:274 miembros, incluido un texto de límites. ZIP de37.413.577bytes, SHA256 `41ff53dce55bedec9678243611616e284a29ada74b4a94fec84e0de3c1704ffe`. Se seleccionó únicamente el expediente autorizado `pueblo-libre-002`, no la carpeta privada completa ni sus credenciales. No se modificaron originales, rutas históricas ni recibos.

Desde la raíz del proyecto:

```powershell
.venv/Scripts/python.exe seguimiento/exportar_caso_268.py --verificar --salida entregas/ANEXO_CASO_CANDIDATO_268
.venv/Scripts/python.exe seguimiento/test_exportar_caso_268.py -v
```

Para generar otra copia, usar un destino nuevo; el exportador rechaza reemplazar uno existente. Compara conjuntos y hashes antes de publicar éxito; si observa cambios, registra `FALLO.json` y esa copia no se puede presentar como íntegra.

```powershell
.venv/Scripts/python.exe seguimiento/exportar_caso_268.py --raiz data/private --caso pueblo-libre-002 --salida entregas/ANEXO_CASO_VERSION_NUEVA
```

El ZIP conserva todos los archivos de ese caso, incluidas versiones históricas e intentos fallidos. Su presencia no constituye aceptación. El manifiesto acredita correspondencia de bytes, no autenticidad del productor ni calidad del modelado. Las credenciales se configuran por separado y nunca se distribuyen.

Se extrajo una copia nueva en `tmp/anexo_reubicado_268/`: las seis láminas originales conservaron tamaños y hashes. La respuesta nativa de masa conserva coherencia formal con su solicitud histórica; el validador rechaza presentarla como una captura de una ruta nueva. Esa protección es correcta. **No se acreditó abrir el EDB ni reconstruir todo el caso en otra ubicación.** No corregir rutas dentro de evidencias firmadas por hash para simular ese resultado: una nueva corrida debe tener nuevas identidades y recibos.

Evidencia: `seguimiento/REVISION_ANEXO_268.json`. Exportador nuevo independiente en seguimiento, todavía no integrado en el ZIP de fuentes del producto. Los informes finales que Claude genere en `tmp/recorrido_09d1/resultados/` no están incluidos en esta copia del expediente: requieren complemento final, con hashes y revisión del panel/JSON/HTML/PDF. También siguen pendientes el desfase de masa, el criterio de peso sísmico y los demás criterios de cierre registrados en RETOMAR. Este archivo no los reduce ni los da por cumplidos.

## Revalidación de evidencia desde otra carpeta (269)

`seguimiento/REUBICACION_CASO_269.json` conserva dos verificaciones exitosas: análisis aceptado y vínculo de resultado normalizado con ese análisis. Runtime fijo de581archivos, huella8b4edeecf42001287149d86bf3d7a21043a58a8e1f843b402c5bcac8cdc95656. Expediente y fuentes sin cambios; sesión42258 terminó0. Primer paso687,944s; segundo127,842s, con1miss/2hits de malla. Estos son tiempos de revalidación completa; no extrapolar el tiempo caliente de malla al recorrido entero. Se usaron las dependencias instaladas existentes; no es instalación nueva, reconstrucción ni relectura nativa de la ruta nueva.
