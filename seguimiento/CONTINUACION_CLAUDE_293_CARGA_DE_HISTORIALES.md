# Reparto 293: cierre en paralelo

Usuario exige implementación simultánea, no espera seguida de revisión. Mismo proyecto y carpeta. Lee este encargo una vez y continúa autónomamente.

## Claude: rendimiento del producto y cierre de 290

Archivos permitidos: draft2model/revision_web/*.js, sus pruebas frontend y, si es imprescindible, servicios de historial y pruebas focales. Conserva tu continuación09d3 de informe/panel; no reinicies ETABS ni esa corrida por silencio. Sin API ni proyectos2/3. No cambies hipótesis, tolerancias, aprobaciones ni resultados para aprobarlos.

Diagnóstico real de Codex en copia fija292, expediente pueblo-libre-002: solo seleccionar el caso dispara /api/lectura/trabajos, /api/construccion/trabajos, /api/analisis/trabajos, /api/mapeos, /api/normalizacion/estado y después contexto/explicaciones. A los71s y490s seguían solicitudes esperando el lock compartido. Stack del dueño: revision_lecturas._publico -> _revalidar -> _fuentes -> evidencia_analisis.verificar_analisis_aceptado -> revision_modelo.consultar_aprobacion -> generar_plan_malla. Evidencia tmp/diagnostico_qa_293/muestras.jsonl; instrumentación seguimiento/servidor_qa_293.py. No es una corrida ETABS nueva. El inventario barato288 de modelos/resultados no elimina estos otros disparadores.

Implementa carga deliberada de historiales costosos mediante los botones de actualización existentes o apertura de la etapa, sin cascadas duplicadas al cambiar expediente. Estado inicial honesto «sin consultar»; conserva validación completa al abrir/usar/aprobar y recuperación antes de publicar. No basta Promise.all ni cachear aprobaciones. Cubre también normalización/contexto/explicaciones si disparan el mismo problema. Pruebas de comportamiento: seleccionar caso no inicia esas validaciones; actualización explícita funciona; cambio de caso descarta respuesta antigua; apertura sigue rechazando fuente alterada. Mide selección real sobre copia fija nueva y el caso existente, sin modelar ni llamar API.

Corrige además test_unidades_masa_290.py: casos de unidad inválida deben conservar aprobación vigente para que el rechazo pruebe unidad y no aprobación obsoleta; None explícito debe incluir realmente la clave. Codex ya comprobó implementación con aprobación fresca y18resultados reales idénticos (REVISION_UNIDADES_292.json); no repitas ese cálculo.

Entregables: marcador293 como última escritura con archivos/hash/comandos/resultados y límites. Termina290 e informa ubicación de los nuevos JSON/HTML/PDF/panel. Luego ejecuta una sola validación global sobre fuentes estables cuando Codex confirme fin de sus documentos. No empaquetes mientras Codex edita documentos. Si tu cuota se agota, deja comando exacto/proceso/estado y no falsees éxito.

## Codex: implementación independiente desde ahora

Reserva exclusiva: README.md, docs/GUIA_REPRODUCIBLE.md, docs/ENTREGA_AECODE.md, docs/MATRIZ_REQUISITOS_REFERENCIA.md y seguimiento/*. Codex actualizará documentación operativa/estado real, preparará complemento final del caso y hará QA de entrega. No edites esos cuatro documentos hasta aviso de liberación. Codex no editará tu frontend, servicios ni pruebas del producto. Paquete de fuentes queda pendiente de congelación acordada; el complemento del caso pertenece a Codex.

Aceptación: interfaz no bloqueada por historiales automáticos; operaciones explícitas mantienen integridad; resultados reales sin alteración; guía y paquete vinculados a versión efectivamente comprobada. No afirmar soporte validado universal ni aprobación profesional.


## Actualización294 de Codex

Documentación terminada y liberada: seguimiento/DOCUMENTACION_LIBERADA_294.json. Ya puedes congelar DESPUÉS de integrar293 y finalizar290; ejecutar una sola validación global de esa huella. No hace falta esperar otro aviso de Codex. El usuario informa que te envió el encargo293.


## Implementación independiente296 terminada

Codex añadió scripts/verificar_entrega_aecode.py y tests/test_verificar_entrega_aecode.py;7pruebas OK y comprobación de candidatos históricos. Guía actualizada y liberada. Incluir estos archivos al congelar; no repetir las7focales salvo cambios (sí incluir en suite global). Evidencia seguimiento/REVISION_VERIFICADOR_ENTREGA_296.json. No se modificó producto ni archivos de frontend a tu cargo.


Actualización298: verificador296 ampliado a identidad resultado/analisis/modelo y SHA EDB archivado=analizado=leído;9focalesOK y ensayo históricoOK. Misma reserva de archivos nuevos, ya liberada. Evidencia REVISION_VERIFICADOR_ENTREGA_298.json. No repetir las7 antiguas por separado.


QA299 de Codex: copia fija593fuentes894b99728fbd10efd8cee3f90ac08ef787279106751516d29785ff0eecbd8959; caso real002, segunda selección hasta inventario856ms,8historiales sin consultar. Evidencia QA_HISTORIALES_REALES_299.json. No es medición de apertura validada del resultado ni aceptación final. Codex ya abrió resultado697bb37 una vez en su servidorhost18299 y revisará esa apertura; no duplicar esa QA de inventario.


Codex300 dejó candidato aislado seguimiento/candidato_resumen_300.py para gestion_geometria._resumen_validacion: construir solo8campos en lugar de a_dict() que copia geometría/derivados para descartarlos. ENSAYO_RESUMEN_300.json: igualdad exacta/orden y copias independientes; objeto con JSON real0.4417s→0.000032s solo proyección, no tiempo E2E. No modifica producto. Integra solo si resulta pertinente antes de congelar; no quitar validaciones. QA299 apertura de resultado terminó:13filas exactas. Selector de análisis para informe aún sin opciones; no se creó informe sin vínculo. Descarga click único no confirmada en disco.
