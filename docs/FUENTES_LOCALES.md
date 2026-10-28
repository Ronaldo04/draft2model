# Corpus local y citas

`draft2model.fuentes` implementa recuperación léxica determinística sobre un corpus local explícitamente revisado. No llama un LLM ni completa umbrales. `recuperar(manifiesto, consulta)` devuelve fragmentos identificados y se abstiene si no encuentra coincidencias. `verificar_citas` exige texto exacto del fragmento y la misma huella de corpus.

El manifiesto v0.1 contiene contrato `draft2model.corpus`, versión, naturaleza sintética, documentos con id/título/edición/ruta relativa/SHA256, fragmentos con id/documento/página/apartado/texto y aprobación declarada de huella/fecha/revisor/alcance. Ver ejemplo completo en tests/test_fuentes.py. `huella_corpus` excluye solo el bloque de aprobación. No se aprueba automáticamente ningún documento ni se incorpora normativa no revisada.

Se comprueban los bytes de las fuentes antes de recuperar y se rechazan rutas externas, documentos alterados, páginas inválidas y referencias inexistentes. La revisión declarada debe contrastar manualmente cada transcripción con el documento y su página: el software no demuestra por sí mismo la exactitud semántica de un fragmento ni vigencia normativa. La búsqueda es léxica, sin embeddings; no garantiza cobertura conceptual. Un cambio en fuente o corpus invalida la explicación derivada. Las huellas no autentican al revisor frente a reescritura deliberada coherente.
