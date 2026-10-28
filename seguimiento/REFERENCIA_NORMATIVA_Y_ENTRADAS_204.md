# Normativa peruana y datos de entrada de Draft2Model

Documento referencial solicitado por el usuario. Fecha de revisión: 21 de octubre de 2026. Describe el estado observado, no añade exigencias ni cambia el alcance del producto. El código está en desarrollo y bajo implementación de Claude; las incorporaciones aún no entregadas se identifican expresamente.

## 1. Respuesta directa: qué estamos haciendo con las normas

**Todavía no está acreditada una adaptación integral y validada del proyecto al Reglamento Nacional de Edificaciones (RNE).** Tenemos infraestructura para registrar fuentes, parámetros, hipótesis, reglas y revisiones; eso permite aplicar criterios seleccionados y documentados. No equivale a tener implementadas automáticamente todas las disposiciones peruanas.

En concreto:

- El modelo recibe materiales, cargas, masa, apoyos, espectros y combinaciones explícitos. Comprueba forma, referencias, unidades y coherencia de ciertos datos; no selecciona por sí solo todos sus valores normativos.
- El espectro se recibe como una tabla de periodo/aceleración. No se acreditó un generador completo de espectros E.030 que determine automáticamente todos los parámetros del proyecto.
- La evaluación disponible trabaja con periodo, deriva y cortante, mediante reglas configuradas. No trae límites normativos de fábrica: el límite y su aplicabilidad se aportan con su fuente.
- La recuperación documental es local y léxica: puede encontrar y citar fragmentos de un corpus revisado. No demuestra que estén incorporados todos los artículos aplicables ni que su interpretación sea correcta.
- Los controles posteriores al análisis comprueban participación modal, equilibrio y avisos con criterios declarados. Sus tolerancias tampoco son umbrales normativos automáticos.
- No se ha acreditado, en las entregas revisadas, un corpus oficial completo ni un conjunto de reglas peruanas aprobado y aplicado al caso real de referencia de principio a fin. Esto es evidencia pendiente, no una afirmación de que no exista ningún PDF normativo en la carpeta.

**Por tanto, no sería transparente decir que hoy el programa ya verifica E.020, E.030, E.050, E.060 y E.070 en su totalidad.** Son referencias pertinentes para definir y revisar los datos según el sistema estructural; su cobertura automatizada aún debe demostrarse.

## 2. Normas pertinentes y para qué servirían

El catálogo oficial del [MVCS — RNE](https://www.gob.pe/institucion/vivienda/informes-publicaciones/2309793-reglamento-nacional-de-edificaciones-rne) y el de [SENCICO](https://www.gob.pe/institucion/sencico/informes-publicaciones/887225-normas-del-reglamento-nacional-de-edificaciones-rne) identifican estas normas. La columna «uso» es la relación técnica con este proyecto; no significa implementación completa.

| Norma | Uso pertinente en el modelado y revisión | Estado real que podemos afirmar |
| --- | --- | --- |
| E.020 — Cargas | Definir acciones por uso y componentes, y las condiciones de carga aplicables. | Hay patrones, cargas explícitas y multiplicadores de peso propio. No se acredita selección automática completa de cargas por uso ni de todas las acciones exigibles. |
| E.030 — Diseño sismorresistente | Definir acción sísmica, hipótesis del sistema, espectro y criterios para revisar la respuesta. | Hay entradas de sitio, masa, espectro tabulado, análisis modal/espectral, resultados y reglas declaradas. Falta acreditar su configuración normativa específica para el caso real y la cobertura de todos los controles aplicables. |
| E.050 — Suelos y cimentaciones | Fundamentar condiciones geotécnicas y la idealización de la base. | Hay restricciones nodales declaradas y consulta geográfica referencial. No reemplazan el estudio de suelos ni acreditan dimensionamiento de cimentaciones o interacción suelo-estructura. |
| E.060 — Concreto armado | Sustentar propiedades e idealización de elementos de concreto y su posterior diseño/verificación. | Hay materiales y secciones para representar elementos. No está acreditado un diseño integral de armaduras, resistencia y detallado conforme a esta norma. |
| E.070 — Albañilería | Definir la representación y comprobaciones propias de la albañilería, incluido el confinamiento cuando corresponda. | Una pared shell y columnas no demuestran equivalencia con albañilería confinada. Esa equivalencia y las verificaciones específicas no están acreditadas para un caso real. |

No todas las normas aplican del mismo modo a todos los proyectos. Acero, aislamiento, madera u otros sistemas requieren revisar otras normas y el soporte efectivo del programa; no se incorporan por inferencia. Este documento no afirma que esas tipologías estén cubiertas.

### Edición y vigencia

Hay que registrar **norma + edición/modificatoria + artículo o tabla + motivo de aplicabilidad al expediente**. No basta escribir «E.030 vigente».

En la consulta oficial se identificó una modificación de E.030 mediante la RM 183-2026-VIVIENDA y una modificación de su disposición transitoria mediante la RM 217-2026-VIVIENDA. Fuentes: [MVCS, publicaciones legales de abril](https://www.gob.pe/institucion/vivienda/normas-legales?sheet=12) y [MVCS, publicaciones legales de junio](https://www.gob.pe/institucion/vivienda/normas-legales?sheet=7). Esto hace especialmente necesario verificar qué texto corresponde al expediente. Esta consulta no constituye una revisión jurídica exhaustiva de todas las modificaciones posteriores ni adopta automáticamente una edición en el software.

## 3. Cómo leer el inventario de entradas

Este inventario cubre las familias de datos del flujo actual y señala entradas de ingeniería que el sistema aún no resuelve. **No promete modelar cualquier proyecto ni supone que todos los campos estén automatizados en pantalla.** Los contratos exactos cambian por versión; las versiones antiguas y sus ejemplos no representan todas las capacidades nuevas.

Las entradas tienen cuatro orígenes distintos:

1. **Documentos:** planos, detalles, memorias, especificaciones y estudios.
2. **Extracción revisada:** lectura manual o multimodal con evidencia sobre la página. Una propuesta del modelo no es un dato de ingeniería aprobado.
3. **Definición técnica:** decisiones y parámetros aportados o revisados por el responsable de ingeniería, con fuente.
4. **Derivados del programa:** coordenadas normalizadas, partición, operaciones ETABS, resultados leídos y cálculos de control. No se presentan como si el usuario tuviera que inventarlos.

Un dato desconocido no es cero. «No existe», «no aplica» y «no está documentado» tienen significados diferentes. Un faltante crítico debe conservarse y resolverse antes del tramo que depende de él.

## 4. Entradas, de inicio a fin

### A. Expediente y planos

| Datos | Origen y utilización real |
| --- | --- |
| Identificador del proyecto/caso, alcance, uso y procedencia real o sintética | Identificar y separar versiones, expedientes y pruebas. La etiqueta de procedencia no autentica por sí sola el documento. |
| Archivos originales, páginas, láminas y revisiones | Fuente para lectura y trazabilidad. El recorrido de visión preparado usa imágenes renderizadas y recortes de planos. |
| Planos de arquitectura y estructuras disponibles; cortes, elevaciones y detalles | Para obtener dimensiones, elementos, niveles y relaciones. Ninguna categoría sustituye automáticamente información ausente de otra. |
| Memoria, especificaciones de materiales, estudio de suelos y notas técnicas, cuando existan | Fuentes de datos que no se deducen de la forma del plano. No todos estos documentos tienen extracción automática acreditada. |
| Escala, cotas, unidades, orientación y relación entre láminas | Calibrar medidas y ubicar elementos. Los píxeles de una imagen no son metros sin una referencia válida. |
| Recortes seleccionados, página, coordenadas del recorte y SHA de archivo/imagen | Vincular cada lectura con su evidencia exacta. Son datos técnicos del proceso, generados o registrados por la aplicación. |

### B. Servicio multimodal, solo si se utiliza para revisar planos

- Proveedor autorizado: Google o OpenAI; modelo concreto; clave configurada localmente; límites y aprobación de la petición conforme al mecanismo del sistema.
- Selección exacta de imágenes y alcance de extracción. Las claves no deben figurar en este documento ni en los prompts.
- Resultado: candidatos de cotas, etiquetas y elementos, con unidades, evidencia y revisión/corrección humana. No se da por válida una cota por tener confianza alta.
- No se usan esas APIs para calcular estructuras, seleccionar normas, programar ni redactar explicaciones del proyecto. ETABS utiliza su API local y no requiere una API key.

### C. Geometría

| Datos | Qué representa el sistema |
| --- | --- |
| Unidad de longitud y sistema de referencia | Geometría en m/cm/mm, normalizada a metros; origen y orientación deben estar definidos coherentemente. |
| Niveles y cotas; nodos en planta o vértices XYZ | Posiciones del modelo. No se inventan alturas entre pisos. |
| Muros y sus extremos/espesores en el recorrido antiguo | Contrato de muros vinculado a nodos y niveles. No equivale a diseño de albañilería. |
| Contornos ordenados de superficies y papel geométrico | Representación de pisos, paredes, placas, paneles inclinados y demás superficies declaradas. El papel geométrico no asigna automáticamente una sección estructural. |
| Aberturas y su superficie anfitriona | Huecos de puertas, ventanas, escaleras u otros recortes; deben ser coherentes con la superficie. |
| Puntos y extremos de vigas, columnas u otros frames | Conectividad y posición. Un elemento inclinado debe definirse expresamente. |
| Escaleras, descansos y cambios de nivel cuando correspondan | Requieren geometría y representación técnica explícitas. Una superficie inclinada no demuestra por sí sola que toda la escalera esté modelada correctamente. |
| Fuentes y justificación de cada elemento o supuesto | Permiten revisar si el modelo reproduce los planos y qué información fue aportada externamente. |

El programa comprueba consistencia y ciertas propiedades geométricas; no decide que el sistema resistente sea apropiado por pasar esas comprobaciones.

### D. Representación estructural y materiales

- Plantilla/representación elegida, versión, huella, limitaciones y fuente; hipótesis de comportamiento y sistema resistente.
- Materiales del contrato actual: tipo isotrópico lineal, módulo de elasticidad `E_kN_m2`, coeficiente de Poisson y peso específico `peso_kN_m3`, con fuente.
- Secciones: material, dimensiones y asignación completa a los elementos correspondientes. Frames rectangulares: ancho y alto. Shells: espesor y tipo de sección compatibles.
- Losas nervadas: altura total, capa, anchos superior/inferior del nervio, separación, dirección de nervios y ángulo de ejes locales. Casetonadas: separaciones en ambas direcciones y dimensiones correspondientes.
- Orientación de los elementos y de sus ejes locales cuando afecta la representación.

**Diferencia importante:** resistencias `f'c`, `fy`, `f'm`, resistencia al corte, cuantías y detalles de armado pueden ser necesarias para el diseño normativo. No se acreditó que el contrato actual las utilice de forma integral para diseñar/verificar todos los elementos. Admitir `E`, peso y sección no equivale a realizar el diseño E.060/E.070.

No se acreditó soporte integral de no linealidad, P-Delta, historia temporal, resortes de suelo, liberaciones, offsets o modificadores de rigidez de todos los tipos. Si el proyecto los necesita, deben comprobarse y, si faltan, implementarse antes de considerarlo cubierto.

### E. Conexiones, malla, apoyos y diafragmas

- Conexiones explícitas entre superficies; bordes e intersecciones que deben compartir nodos. No se deben fusionar elementos solo porque estén cerca.
- Estrategia de partición, huella de preparación, cortes y subdivisiones de frames. La partición y las posiciones derivadas se calculan; las políticas estructurales se declaran.
- Para nodos originales y derivados: restricciones `[Ux, Uy, Uz, Rx, Ry, Rz]`, con fuente y coherencia con la representación de la base.
- Diafragmas rígidos o semirrígidos, puntos asignados y exclusiones justificadas. La pertenencia no se supone únicamente por estar en el mismo piso.
- Para nodos derivados: posición reproducida y decisión sobre restricciones/diafragma. El programa no hereda silenciosamente una política de un nodo que cambió de posición.

Esta base tiene evidencia sintética de construcción/relectura en ETABS; todavía no prueba que la malla represente correctamente la rigidez de toda la referencia real. La base empotrada de una fixture no es una conclusión geotécnica.

### F. Cargas y masas

| Datos | Uso y límite |
| --- | --- |
| Patrones: identificador, tipo y multiplicador de peso propio | Separar acciones y evitar contribuciones duplicadas. No son una selección normativa automática. |
| Cargas adicionales: valor, unidad, objetivo, componentes, dirección/sistema y fuente | Fuerzas puntuales, distribuidas en frames o sobre superficies según contrato y adaptador. Acabados, tabiquería y equipos requieren valores y distribución justificados. |
| Sobrecargas por uso, techo y otras acciones aplicables | Deben definirse con la fuente técnica correspondiente; no se acredita inferencia completa desde la etiqueta «vivienda». |
| Fuente de masa | Método por patrones o masas puntuales explícitas, factores, inclusión de masa propia y gravedad declarada. |
| Combinaciones y factores | Casos y coeficientes explícitos, tipo lineal o envolvente. No vienen todas las combinaciones peruanas preseleccionadas. |

Viento, empujes de terreno, temperatura, acciones de construcción u otras situaciones no quedan cubiertos automáticamente por existir un patrón llamado «otro». Hace falta representar la acción, transmitirla y verificar su lectura y efecto conforme al alcance.

### G. Cisterna y tanque: únicamente cuando existen

Debe distinguirse ausencia confirmada, presencia e información insuficiente. Sin cisterna ni tanque confirmados, no se deben exigir datos del agua ni crear cargas de agua ficticias.

Cuando hay líquido, la derivación disponible requiere:

- Superficies mojadas y sus huecos, dimensiones y cotas.
- Nivel libre en Z y peso específico del líquido, explícitos y con fuente.
- Sentido de presión sobre cada superficie y origen XYZ para comprobar momentos.
- Declaración revisada y fuentes vinculadas; patrón de carga correspondiente.
- Cortes necesarios en la malla al nivel libre, conservando también el material seco.

La relación física implementada es presión hidrostática `p = gamma · max(0, nivel − z)`; no constituye por sí sola una regla del RNE. Existen pruebas locales y ensayos sintéticos en ETABS. **La integración normal opcional está en desarrollo en la etapa 02; no se acepta como terminada por aparecer código 0.5 en el árbol.**

No se acreditó que ese cálculo estático incluya automáticamente oleaje, componentes hidrodinámicas, interacción suelo-depósito o todas las situaciones lleno/vacío y combinaciones requeridas. Debe definirse qué aplica; no se confunde geometría de un depósito con ingeniería completa del depósito.

### H. Ubicación, suelo y acción sísmica

- Ubicación del proyecto y sistema resistente, con sus fuentes.
- Si se usa la consulta cartográfica: longitud/latitud, capa local revisada, sistema EPSG:4326, edición y precisión de la fuente.
- Parámetros de sitio y sísmicos técnicamente seleccionados para la edición aplicable. Entre los que puede ser necesario justificar están zonificación, categoría/uso, perfil del suelo, parámetros del espectro, reducción, irregularidades y direcciones; no se afirma que el programa calcule automáticamente cada uno.
- Espectro tabulado periodo–aceleración, unidades y fuente; aclaración de qué factores ya están incluidos para no duplicarlos al escalar.
- Caso modal, número de modos, direcciones, factor, amortiguamiento y combinación modal CQC/SRSS según la configuración admitida.

La consulta de un polígono no asigna perfil de suelo, capacidad portante ni espectro. Esos datos requieren su sustento. La plantilla genérica lineal no calibra por sí sola albañilería confinada.

### I. Ejecución y configuración de ETABS

- Instalación y licencia utilizables; versión y biblioteca API compatibles; rutas locales.
- Plantilla exacta y destino nuevo para el modelo; huellas de geometría/configuración, plan y permisos de ejecución del flujo.
- Casos estáticos lineales, modales y de espectro admitidos; casos a ejecutar y combinaciones a leer.
- Instancia propia identificada, registro de operaciones y estado de cierre. Nunca se debe usar o cerrar una instancia desconocida del usuario.

Estos son datos de operación. Una ejecución exitosa no fija materiales ni criterios normativos faltantes. Los ensayos reales revisados son evidencia de funciones concretas, no de la referencia completa.

### J. Relectura, resultados y evaluación

- Modelo exacto construido y su SHA, unidades leídas y plan contra el cual verificarlo.
- Criterios de comparación explícitos por magnitud y orientación/ejes; las tolerancias computacionales no son tolerancias estructurales.
- Selección y correspondencia exacta de tablas/casos/niveles/direcciones/unidades para normalizar resultados.
- Resultados actualmente centrales: periodos, derivas y cortante basal; se conserva lo ausente como faltante.
- Controles: participación modal acumulada, términos de equilibrio, avisos del solver y criterios de aceptación declarados con fuente.
- Reglas: variable, unidad, fórmula admitida, factor/desplazamiento, límite, comparador, aplicabilidad por caso/dirección/ubicación, edición y apartado de la fuente, revisión.

La fórmula genérica de evaluación es `factor · x + desplazamiento`. Eso permite contrastar indicadores contra reglas aportadas; **no implementa por sí solo un reglamento estructural completo**. Hace falta verificar también las reglas que el evaluador no puede representar y las comprobaciones ausentes del modelo.

### K. Informe y comparación posterior

- Selección de versiones exactas de geometría, configuración, construcción, análisis y resultados.
- Fuentes/corpus, reglas, contexto de sitio, controles y revisiones que se quieran incorporar al informe.
- Hipótesis, omisiones, datos pendientes y alcance de cada comprobación. Revisor y fecha declarados no equivalen a autenticación profesional.
- Para la comparación manual posterior: modelo/resultados independientes, equivalencia de hipótesis y casos, unidades y tolerancias acordadas. **El usuario aplazó esta comparación hasta disponer de nuestros resultados; no se necesita entregar ahora su modelo manual para guiar el desarrollo.**

## 5. Datos que el programa no debe inventar

No debe completar sin sustento: alturas/cotas ilegibles, propiedades resistentes, perfil de suelo, apoyos físicos, sistema resistente, parámetros sísmicos, espectros, cargas de uso, factores normativos, niveles de agua, diafragmas, equivalencia de albañilería o tolerancias de ingeniería.

Si no están en los documentos, deben aportarse o definirse con una hipótesis identificada y revisión técnica. Una API key, una respuesta de visión, un hash o que ETABS consiga calcular no sustituye esos datos.

## 6. Qué falta para poder decir «adaptado al RNE» con evidencia

1. Fijar la edición y aplicabilidad normativa del caso; conservar documentos oficiales exactos y citas/artículos pertinentes.
2. Traducir cada requisito aplicable en una entrada, cálculo o comprobación verificable; separar lo automático de lo revisado externamente.
3. Incorporar y revisar parámetros reales; resolver entradas ilegibles y decisiones de idealización sin copiar el modelo manual reservado.
4. Demostrar que el adaptador y los lectores cubren las acciones y elementos exigidos; ampliar lo que falte, sin aproximaciones silenciosas.
5. Ejecutar el piloto real completo y documentar controles y resultados. Mantener como pendientes las verificaciones no realizadas; completar después la comparación independiente acordada.

## 7. Base local examinada y límites de este documento

Archivos leídos: `draft2model/contratos.py`, `modelo_estructural.py`, `extraccion_preliminar.py`, `acciones_liquidos.py`; documentación `MODELO_ESTRUCTURAL.md`, `RESULTADOS_EVALUACION.md`, `FUENTES_LOCALES.md`, `CONTROLES_ANALISIS.md`, `SITIO.md`, `ACCIONES_LIQUIDOS.md`, `INTEGRACION_MALLA_ETABS.md` y ejemplo `examples/modelo_estructural_sintetico.json`. Se contrastaron con la ruta y la entrega 01 y con la evidencia 198/199/200 ya revisada.

Algunos documentos conservan descripciones históricas de versiones anteriores: no se interpretan como descripción exhaustiva del código actual. La aparición de contratos nuevos durante la etapa 02 no demuestra que hayan sido integrados y verificados. Este inventario es referencial, no un esquema JSON para importar, ni una promesa de soporte universal. No se leyeron ni publicaron claves y no se llamó a las APIs de visión para elaborarlo.
