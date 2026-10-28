# Entrega de candidato282 y revisión284

Propietario de integración: Claude. Codex no modificó producto. Candidato: `tmp/candidato_contexto_282/particion_superficies.py`; SHA a51d5fb50018d0b6e4bb10d4499bf762972328418ae85403adb0f7abd30c780b. Base original en ORIGEN.json; comprobar hash actual y rebasar antes de integrar si cambió.

## Evidencia propia

`seguimiento/REVISION_CONTEXTO_284.json`:7pruebasOK, sin omisiones; cinco planes completos idénticos (horizontal/vertical/inclinado/conectados con líquidos y otro con contenido). Se vació la cache antes de cada comparación y se comprobó ejecución efectiva del candidato. Rechaza cambios de tipo/número/metadatos, NaN y ciclos; orden de claves equivalente cae a JSON canónico y se acepta como antes; fallback completo probado; fuente no mutada. Base aislada runtime276, sin ETABS ni proveedores.

Comparación de contexto COMPLETA sobre la geometría real:30llamadas1.25838s→0.22624s, mismo SHA JSON de origen. No es tiempo global de malla/plan/evidencia. Revisar e integrar si corresponde; ejecutar regresiones de contexto/mutación pertinentes y medir una preparación real comparando salida completa/hash antes de anunciar impacto global. No repetir las5pruebas de planes si no se modifica el candidato.

La captura binaria usa SOLO marshal.dumps2 en memoria; no carga ni persiste binarios. Compara toda la fuente con tipos; los bytes originales JSON y su SHA permanecen autoritativos. Cualquier diferencia o tipo no admitido vuelve a la comparación JSON original. No omite verificaciones, no usa identidad/mtime/huella aportada ni guarda aceptación de evidencia. Formato efímero por proceso, sin promesa de compatibilidad entre versiones de Python. Fuente primaria consultada: https://docs.python.org/3.10/library/marshal.html .

## Hallazgo adicional: nueva cache de validación

`seguimiento/REPRODUCCION_ORDEN_CACHE_284.json`: primar cache con una geometría y luego validar los mismos valores con claves reordenadas devuelve el orden de salida de la primera entrada, mientras el original produce el orden de la segunda. Son dicts equivalentes, pero el JSON sin sort_keys es distinto; contradice la equivalencia exacta y conservación de orden declaradas en cache_validacion_geometria.py y sus pruebas. Puede afectar huellas que serialicen sin ordenar. No afirmar corrupción física; es dependencia del historial en la representación devuelta.

Corregir preservando el comportamiento original (p. ej. clave estricta que también distinga orden cuando la salida lo conserva), añadir regresión que prime con una ordenación y consulte otra, y comprobar forma(r)==forma(ORIGINAL(h)) sin sort_keys. No solucionar cambiando el contrato de salidas/huellas históricas para ocultar diferencia. Continúa el coste caliente y el cierre, sin reiniciar39028.

## Revisión283

Codex leyó corrección/resumen y marcador283; falta ejecutar la comprobación focal propia del resumen y generar una nueva versión real con fuentes corregidas en una copia estable. No tocar ni cambiar el runtime276 o informe histórico de QA. No aceptamos el informe viejo como final por conservar hashes válidos.
