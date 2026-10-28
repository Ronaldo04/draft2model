# Encargo 09 — integración del piloto y correcciones verificadas

Continúa en este mismo proyecto y carpeta. Usuario mantiene objetivo íntegro y autoriza tareas consecutivas sin esperar revisión entre cada una. Codex revisa entregas; no es una aprobación de ingeniería. No declarar cierre por pruebas sintéticas.

## Responsabilidad y restricciones

Claude implementa `draft2model/`, `scripts/`, `tests/`, `examples/`, `docs/` y sus entregables en `seguimiento/claude_ruta/`. Codex conserva coordinación/revisión; auditor independiente trabaja SOLO en `seguimiento/AUDITORIA_ORIENTACION_237.md` y `tmp/auditoria_orientacion_237`. No editar esos archivos. Evitar duplicar esa auditoría; avanzar con tareas independientes y consultar su resultado cuando aparezca.

Sin llamadas API, sin leer/divulgar credenciales. Consumos conservados: OpenAI4/5, Gemini2/5; solo Codex ejecuta llamadas autorizadas para planos. No modificar crudos ni históricos. No usar modelo manual del usuario. ETABS: instancias propias, sin cerrar ni modificar sesiones ajenas. Revisar instrucciones locales aplicables antes de editar.

## Secuencia automática, una tarea a la vez

1. **Corregir hallazgos R236.** Evidencia independiente en `seguimiento/REVISION_NORMATIVA_RECUPERACION_236.json`, fuente congelada `tmp/revision_codex_236`.
   - `cortante_basal_estatico` devuelve V=1.40625kN con Z=.45,U=1,S=1,R=8,T=10,TP=.4,TL=2.5,P=1000 aun cuando señala C/R<.11. Aplicar mínimo al valor utilizable conforme al texto oficial ya conservado o impedir su uso como V aplicable; conservar coeficiente bruto y aplicado separados. Verificar todos los consumidores. El ejemplo mínimo es49.5kN. No afirmar que el piloto ya usó ese valor.
   - Valida siempre 0<TP<TL, incluso rama estática T<=TP: T=.1,TP=.4,TL=.2 hoy es aceptado. Verificar dominios positivos/finítos relevantes y pruebas de frontera independientes.
   - Recuperación Gemini real mantiene59 candidatos y12 en cuarentena. Sus advertencias existen, pero REC2/REC3 conservan cobertura original completa. Preservar declaración original del proveedor y calcular cobertura efectiva de lo recuperado con cantidades/exclusiones, sin mostrar lote derivado como completo. Añadir indicador/opción de cuarentena en formulario web y QA focal con respuesta real conservada, sin otra API.

2. **Inventario geométrico real completo.** Aprovechar calibración08 y seis láminas de `pueblo-libre-002`; localizar placas/columnas, vigas, muros, losas aligeradas, huecos, escaleras, cisterna y tanque con fuente/posición/unidad. Evitar quedarse en los9rectángulos detectados. Identificar técnicas vectoriales y revisión visual necesarias; no confundir texto de sección con ubicación en planta. Consultar auditoría237 al aparecer. Resolver correspondencias por rasgos asimétricos, conservar discrepancias F/tanque y no sustituir una decisión material por una certeza falsa.

3. **Geometría0.3/configuración0.5 del caso real por flujo normal.** Crear artefactos versionados trazables con elementos confirmados y pendientes explícitos. Alturas5.20/7.80 son derivadas de uniformidad, no impresas: preparar alternativa técnica explícita, no darla por aceptada por el usuario. No bloquear inventario/exportación preliminar por EMS, Ia/Ip o perfil de suelo: son puertas distintas de configuración/análisis. No aprobar automáticamente lecturas pendientes. Las hipótesis técnicas ordinarias deben explicitarse; si una decisión material realmente requiere usuario, formular pregunta concreta y continuar demás tareas.

4. **Cargas y normativa integrada.** Verificar conexión real de módulos normativos al plan/configuración y resultados, no solo funciones aisladas. Fuentes oficiales y límites en `seguimiento/NORMATIVA_OFICIAL_229.md`. Distinguir espectro y estático, masas/pesos/presiones del agua, aligeradas y masa efectiva, apoyos/EMS, irregularidades derivables de resultados. Nada de declarar cumplimiento por tener citas. Vs30 válido: revisar la interpolación aún no implementada frente a la fuente oficial; implementar donde corresponda y validar sus fronteras. Mantener fuentes normativas reproducibles o guía verificable para recuperarlas desde URLs/hashes públicos, sin dependencia oculta de archivos no empaquetados.

5. **Recorrido nativo del piloto cuando sus puertas estén satisfechas.** Plan→instancia propia ETABS→EDB→relectura comparada→análisis→resultados→informe, conservando hashes/unidades/modelo/casos. Si falta dato que invalida análisis, completar construcción/relectura de lo autorizado y dejar explícita la puerta pendiente; no producir resultados aparentes de un modelo incompleto. No sustituir por r3 sintético. Las presiones de agua requieren parámetros válidos y no deben duplicar peso/masa. Ningún edificio sin depósito recibe agua ficticia.

6. **Reproducción y cierre documental.** Guía y matriz de requisitos con evidencia por requisito, funciones operativas/simuladas/pendientes. Pruebas focales primero; una suite amplia al hito con fuentes estables, no reiterar1195pruebas por cada subpaso. Incluir instalación/configuración/arranque y recorrido principal. Registrar limitaciones materiales restantes, sin quitar alcance para cerrar.

## Entregables y aceptación

Publicar entregas intermedias sustanciales con manifiesto/hash/logs, actualizar `estado.json` y seguir el siguiente paso independiente automáticamente; no detenerse esperando revisión de Codex. No publicar duplicados por recordatorios. Actualizar `INFORME_09.md` con matriz requisito→archivo→comprobación→resultado y estado real del piloto. Marcador final solo tras archivos/logs cerrados y hashes verificados. Preservar versiones08 y crudos235. Nunca marcar proyecto completo hasta recorrido real íntegro y reproducible; comparación con ETABS manual sigue aplazada por usuario.

Si contexto o cuota limitan, dejar punto exacto para retomar y secuencia pendiente; no inventar procesos vivos ni éxito.

## Evidencia adicional237 disponible después del envío

- Auditoría entregada: `seguimiento/AUDITORIA_ORIENTACION_237.md`. La asimetría concreta de la escalera favorece3↔A,2↔C,1↔E; no deducir orientación por ajuste de ejes simétricos. Cisterna/tanque no aportan corroboración independiente suficiente. Registrar confianza/residual y revisar recortes originales; no imponer arbitrariamente dos objetos como nueva condición de producto. Alturas siguen hipótesis uniforme, no cotas impresas.
- Codex preguntó al usuario únicamente confirmación de niveles uniformes y existencia/ruta de EMS; respuestas pendientes. No interpretar silencio como confirmación. Continuar inventario y artefactos preliminares independientes.
- Texto oficial E030 conservado, Tabla3: S2 Vs30≥350 y<550m/s; S3≥200 y<350. NotaTablas4/5 exige interpolación lineal conVs30. Referencias aritméticas independientes: S2,Z4,Vs450→t=.5,S1.05,TP.5,TL2.25; S3,Z4,Vs275→t=.5,S1.15,TP.75,TL1.8. Fórmulas t=(550−Vs)/200 paraS2 y(350−Vs)/150 paraS3; aumenta S/TP y disminuyeTL al disminuirVs. Respetar intervalos/cambio de perfil en límites y no extrapolar. SinVs se aplica nota explícita, no promedio. Contrastar tabla oficial antes de implementar, referencias no sustituyen fuente.
- Codex ejecutó19pruebas semánticas/reubicación/cuarentena sobre snapshot236:OK6.458s; no suiteamplia repetida. R236 conserva hallazgos abiertos pese a esas pruebasverdes.

### Control documental239 para el paso6

`docs/RETOMAR.md` y `MATRIZ_REQUISITOS_REFERENCIA.md` todavía afirman una llamada real y plan2pendiente/sinenvío: incorrecto frente a seis recibos existentes. R239-01 enREVISIONES y DESFASE_DOCUMENTAL_239.json. Plan2 ya fue enviado y falló portruncamiento; no repetirAPI. Actualizar guías al cerrar09. Usuario ya eligióRNEvigente yentregóarquitectura; no tratarlos como decisiones ausentes. Codex verificó por separado instalaciónoffline nueva de08en tmp/instalacion_codex_238:6pasosOKsinred; esto no valida cambios09.

Comprobación independiente del registroweb34528ff1: coberturaefectiva32/38,14/19,13/14parcial coherentecon12cuarentena ycontenido original intacto; evidencia COBERTURA_REAL_239.json. Es contraste deartefacto cerrado, no aceptación de implementación09 ni prueba deinteracción visual. No repetir la operaciónweb solo por estarevisión.

Revisión240: Codex capturó normativa_e030.py SHA850f2573… sineditarlo y ejecutó18comprobaciones independientes delcortante mínimo/dominios/distinción espectroestático:OK. Resultado `seguimiento/REVISION_MINIMO_ESTATICO_240.json`. No requiere reejecutar suite por ese aviso. InterpolaciónVs30 e integración siguenpendientes; aceptación de09 solo con entregacompleta trazable y puertasdelpiloto explícitas.

### Integración normativa241: idealización por función

Revisar `seguimiento/BRECHA_IDEALIZACION_241.md` antes del piloto. Snapshot08solo admite `tipo_shell_losa`global para pisos/aligerados yotrosfondos/tapas. Resolver capacidad de expresar idealizaciones distintas simultáneamente cuando procedan, vinculando selección explícita aplan/relectura. E03030.8 se refierealosaspiso; no basta elegirmembrana global y asumirdepósito válido. Prueba focal piso+fondo con distinta elección, sinabrirETABSajeno. No implica que ya haya modelorealerróneo; es brechadecapacidad/sustentotécnico que puedeafectar piloto. Si09ya resolvió, documentarevidencia envezdeduplicar.

### Revisión del hito09A — correcciones243 antes de consolidar geometría

Entrega04-2f1d24d2ad4b4cdfa4ff49f12299268e revisada:12fuentes/3logs íntegros,418Python enlog, Codex4pruebas inventarioOK yNode12/12OK, móduloestático coincideconcaptura240. Doscontraejemplos independientes FALLAN: `seguimiento/REVISION_INVENTARIO_243.json`, reproducción `seguimiento/revisar_inventario_243.py` contra snapshot243.

- R243-01: dos horizontales sin cierres laterales producen estadoajustado con0ladosverticales. No usarlos comocolumna confirmada. Exigir cierres laterales distintos verificables oestado incompleto. Contar segmentos duplicados del mismo lado no equivaleadoslados. Contornosconladospartidospuedenadmitirse sisepruebacobertura.
- R243-02: componentes une celdasvecinas sin distanciamétrica; extremos separados.84pt seunen contol.6. Celdas soníndice, debencomprobarse distancias antesdeunion. Conservar conexiónporcadenasválidas.

Corregir con pruebasfocales adversas y regenerar inventarioreal sihayimpacto, informando diferencias. Continúalasdemás tareasautomáticamente; no repetir418pruebas por elavisodeCodexniusarAPI. Inventariorevisado conhallazgos no esgeometríaaprobada.

### Coordinación paralela244 — interfaz losas

Codex reprodujo en snapshot243que `revision_web/construccion.js` noenvíatipo_shell_losa yrechazadeclararloenopcionesadicionales. BRECHA_UI_LOSAS_244.json; DOM/API dobles,sinred. Propuesta de reserva para subagenteCodex: **solo** `draft2model/revision_web/construccion.js`, `draft2model/revision_web/index.html`, `tests/revision_construccion_frontend.cjs`. No tocar estosarchivos enparalelo tras confirmar coordinación; Claudeconservanúcleo R241/243 yrestode09. Codexconfirmaráfinaldeintegración yhashes antesde suiteamplia. Agente244iniciósololectura hastareserva confirmada.

### Evidencia245 lista para continuación geométrica después de cerrar c209

- UI244 terminada/revisada/reservaliberada y avisoenhistorial; QA_INTERFAZ_LOSAS_244.json. Las3fuentescopiadasenc209 coincidenexactamenteconhashes244 (UI_EN_COPIA209_245.json). No iniciarnuevaspruebas por esteaviso.
- Codex38comprobacionesVs30sobreSHAfa1b0677…:OK; REVISION_VS30_245.json. No determinaelperfilreal; no acepta09Bglobal.
- Auditorindependienteterminado: `seguimiento/AUDITORIA_DIAGONALES_245.md`; auxiliar `tmp/auditoria_diagonales_245/PL4_vertices_derivados.json`. **Dosramasinclinadas pertenecenaPL4E8/E19yaexistentes**, no dosmurosde albañileríanuevos. Extremos/contornos10vérticesycalibracióntrazados;E19preservaaristabrutasuperpuestacomoadvertencia. CodexvioimagenE01yrecalculóáreasindependientemente:≈.312/.315m²frenteacajas≈3.39m²;REVISION_DIAGONALES_245.json. **Noextruircajaenvolventecomoplaca.** Convertirhuellaa panelesverticales planos/ejes/espesoresconjustificación ynodosdeencuentro; no extruircontornoplanoahuecocomofachada nicrocrearcarasdobles.
- El detalle5-5respaldaespesorlocal.10m ycimiento.50m;fc175noresuelvexsísolo alcance muro vsnota210: conservarambigüedad. ContinuidadgráficaenambasplantasE02;consultarE03antesdeextenderazotea. No usar raízde cimiento comomuro sinexcentricidad/verificación.
- No editarfuentes mientrasc209validafuentesestables;usar evidenciaen la continuaciónyaasignada09 traspublicarhito. Preguntas dealturas/EMSsiguenpendientes;geometríapuedeseguirborradorcon hipótesis explícitas, sinaprobacionesheredadas.
