# Registro de avances

## 13 de octubre de 2026: contrato geométrico publicado

- Contrato geométrico v0.1, validador, ejemplo sintético, documentación y 22 pruebas geométricas incorporados al estado del proyecto.
- Verificaciones: unidades explícitas y normalización a metros, referencias e identificadores, valores finitos, faltantes, longitudes/alturas positivas y aprobación registrada vinculada a la huella del contenido.
- Suite completa: 35 pruebas unittest pasan. El ejemplo sintético es consistente y permanece no disponible para modelado por faltantes y estado borrador.
- Alcance: consistencia interna de una propuesta de geometría; no verifica competencia del declarante de aprobación ni certifica seguridad estructural. Materiales, cargas y traducción ETABS pendientes.
- Publicación limitada a código, ejemplo sintético y Markdown. Planos de muestra y expedientes privados no se publican.
- Recortes ampliados y extracción con evidencia siguen previstos, no implementados.


## 13 de octubre de 2026: revisión documental y muestra provisional

- Muestra autorizada por el usuario para pruebas locales de procesamiento, declarada fuera del sistema constructivo y cantidad de pisos del MVP. No amplía el alcance ni constituye validación estructural.
- Tres PDF registrados como provisional-001; tres páginas abiertas y renderizadas sin errores. Originales y copias preservados y contrastados mediante SHA256.
- Inventario de dimensiones, rotación, texto embebido y vistas previas. Una página declara rotación PDF de 270 grados; el render respeta su orientación. Las cotas pequeñas requieren ampliación por recortes.
- Módulo revision_documental.py, comando revisar y dependencias reproducibles implementados. Trece pruebas de ingreso y revisión pasan.
- Planos, expediente y PNG permanecen locales en carpetas excluidas; solo código y documentación sin datos del proyecto se publican.
- OCR, extracción geométrica, modelo de referencia y análisis ETABS siguen pendientes. Una apertura correcta no aprueba legibilidad ni datos de ingeniería.
- Instrucciones en [REVISION_DOCUMENTAL.md](REVISION_DOCUMENTAL.md).


## 13 de octubre de 2026: base de ingreso implementada

- El usuario informó que aún no dispone de los planos piloto y solicitó continuar con los componentes independientes.
- Módulo draft2model.ingreso y CLI local disponibles para PDF/JPG/PNG autorizados. Originales preservados, SHA256 contrastados, archivos duplicados e identificadores inválidos rechazados; sin sobrescribir expedientes.
- Expedientes en data/private, excluidos del seguimiento; no se envía contenido a proveedores ni al repositorio por el comando de ingreso.
- Siete pruebas unittest ejecutadas correctamente con archivos sintéticos. Ayuda del comando comprobada.
- Alcance comprobado: registro, copia, trazabilidad y estado borrador. La firma de archivo no valida integridad completa o legibilidad; datos de ingeniería y aprobación permanecen ausentes.
- Contrato de ingreso v0.1.0; contratos de geometría, modelado, resultados, evaluación e informe pendientes. No se ejecutó ETABS ni cálculo estructural.
- Instrucciones en [INGRESO_EXPEDIENTES.md](INGRESO_EXPEDIENTES.md). O1/O2 permanecen abiertos hasta completar sus criterios técnicos.


## 13 de octubre de 2026: inicio de O1

- Entorno Python 3.10.5 de 64 bits aislado en .venv, excluido del versionado.
- ETABS 21.1.0.3261, ejecutable, biblioteca API y ayuda local detectados. Clases COM CSI.ETABS.API.ETABSObject y ETABSv1.Helper registradas.
- Script reproducible [diagnosticar_entorno.py](../scripts/diagnosticar_entorno.py) ejecutado correctamente; informe local en tmp/diagnostico_entorno.json, excluido del remoto. No se leyeron archivos de licencia ni secretos.
- [Preparación O1](O1_PREPARACION.md) documenta datos del piloto, referencia de ingeniería y secuencia de verificación.
- No se encontraron modelos ni dibujos piloto en la carpeta del proyecto. Licencia, conexión API y lectura de resultados todavía no verificadas; O1 sigue abierto.
- El usuario informó haber concedido acceso a un colaborador. No se ha auditado el permiso concreto ni la aceptación; esta información no se presenta como comprobación de solo lectura.

## 13 de octubre de 2026: repositorio y carga verificados

- URL: [Ronaldo04/draft2model](https://github.com/Ronaldo04/draft2model). Propietario: cuenta personal Ronaldo04.
- Visibilidad privada, rama predeterminada main e Issues habilitado comprobados por el plugin GitHub.
- 23 archivos publicados: README, seis documentos de docs, dos plantillas de .github, .gitignore, dos PDF fuente y once entregables. Carpetas preservadas; tmp y credenciales fuera del árbol remoto.
- Contenido remoto comparado con las copias locales mediante los hashes de los blobs Git: 23 coincidencias, sin diferencias. Los PDF y PNG originales se conservaron.
- Seguimiento creado: [O0 #1](https://github.com/Ronaldo04/draft2model/issues/1), [O1 #2](https://github.com/Ronaldo04/draft2model/issues/2), [O2 #3](https://github.com/Ronaldo04/draft2model/issues/3), [O3 #4](https://github.com/Ronaldo04/draft2model/issues/4), [O4 #5](https://github.com/Ronaldo04/draft2model/issues/5), [O5 #6](https://github.com/Ronaldo04/draft2model/issues/6), [O6 #7](https://github.com/Ronaldo04/draft2model/issues/7). Cada Issue contiene objetivos, dependencias y criterios; todavía no acredita implementación técnica.
- Pages desactivado y sin workflows cargados. No se contrataron planes ni se enviaron invitaciones.
- main sin protección. La API de reglas devuelve que se requiere GitHub Pro para el repositorio privado; la lectura detallada de protección no está permitida por la integración. Los controles de integración documentados son convenciones.
- Los hitos O0–O6 se representan con Issues. No se crearon registros Milestone ni tablero Project: el conector disponible no expone esas operaciones.
- Copia local vigente: esta carpeta de proyecto; todavía sin .git. El paquete de carga en tmp es solo una copia de preparación.
- Pendientes: modalidad de consulta, cuentas y verificación de acceso; sincronización mediante Git local cuando se prepare el entorno. O0 permanece abierto.


## 13 de octubre de 2026: preparación documental

### Preparado

- Contexto, plan, guía y plantillas preparados para registrar requisitos, dependencias y verificaciones.
- Criterios de integración sustentados en comprobaciones y evidencia técnica.
- Conservados requisitos, dependencias técnicas, controles y criterios de aceptación del producto.
- Separada la referencia académica histórica; las contribuciones reales quedan por documentar con evidencia.
- Consulta del código por el equipo diferenciada de acceso de escritura en GitHub.

### No ejecutado

- Inicialización Git local y acceso de consulta mediante cuentas autorizadas.
- Implementación o pruebas del prototipo, confirmación de instalación/licencia ETABS o disponibilidad del caso.

### Próximo paso

Continuar con O1 y resolver la modalidad de consulta y las cuentas autorizadas con la [guía](GUIA_GITHUB_PRIVADO.md).

### Antecedente de esta actualización

Los PDF y entregables iniciales se conservan como antecedentes. La planificación y las comprobaciones vigentes se registran en los documentos de trabajo.

## Plantilla de sesión

- Fecha:
- Requisito / Issue / hito:
- Cambio realizado:
- Evidencia / PR / archivos:
- Comprobaciones y resultado:
- Observaciones discutidas en reunión, si existen:
- Decisiones registradas:
- Bloqueo técnico o dato necesario:
- Próximo requisito:

Distinguir realizado, probado, propuesto y pendiente. La reunión o una respuesta de IA no acredita por sí sola una prueba técnica. La evidencia debe permitir verificar la procedencia y el resultado del cambio.
