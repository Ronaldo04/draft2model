# Representación del proyecto de referencia

Corte: 19-10-2026. Auditoría estática acotada; sin pruebas, red, Computer Use ni ETABS. Propuesta pendiente de implementación y revisión técnica. Mantiene el objetivo completo y la comparación manual aplazada.

## Evidencia vigente

- `RETOMAR.md`, sección «Ensayo real»: tres láminas, hasta cuarto nivel, aligerados, columnas/placas/vigas, escalera, cisterna/tanque; no hay dimensiones/materiales/cargas/escala física aprobados. Esto describe la inspección previa, no una nueva extracción.
- `PENDIENTES_FUNCIONALES_CIERRE.md`, A/P08-P09: exige inventario físico→objetos/idealizaciones/omisiones y ampliación cuando la capacidad existente no basta. Sus estados de sitio/controles/superposición son históricos; no reabrirlos por esa tabla.
- `contratos.py:53` (`COLECCIONES`): niveles con cota, nodos XY y muros entre dos nodos/dos niveles. Sin límite artificial de cuatro niveles; sin superficies generales ni aberturas.
- `conversion_geometria.py:83` (`_construir`): manifiesto exacto de niveles/nodos/muros; medidas físicas declaradas o cotas revisadas; conectividad con evidencia comprobada. Los píxeles/bbox no se convierten en dimensiones físicas.
- `plan_modelado.py:197` (`_superficie`): produce exclusivamente cuatro vértices de muro vertical y área bruta. No produce piso, hueco, malla ni volumen.
- `modelo_estructural.py:160-317`: configuración exacta; material isotrópico lineal; secciones `shell_muro`/`frame_rectangular`; puntos ligados a nodo+nivel; frames viga/columna/otro. Columna vertical, viga horizontal, otro puede inclinarse. Puntos sin muro/frame se rechazan.
- `modelo_estructural.py:331-398`: cargas globales de tres componentes sobre punto/frame/muro; masa desde patrones o escalar puntual declarada; diafragma/exclusión obligatorios por punto, con miembros coplanares.
- `operaciones_etabs.py:418-447`: masa puntual escalar se rechaza por falta de grados de libertad; masa desde patrones sí tiene implementación, sin duplicar peso propio. Cargas coincidentes en objetivo/patrón/dirección se rechazan.
- `operaciones_etabs.py:623-700`: SetWall/SetRectangle, puntos, frames y muros de cuatro esquinas; cargas uniformes y masa/puntos/diafragmas. No SetSlab/SetOpening en la lista blanca inspeccionada. `scripts/ejecutar_plan_etabs.ps1:54` replica esa lista: ambas deben evolucionar juntas.
- `revision_superposicion.py:160-168,216-259`: planta muestra muros que nacen en el nivel; anclas limitadas a sus nodos. No acredita visualmente los demás objetos.

## Tres capas que deben permanecer separadas

1. **Geometría y trazabilidad:** coordenadas, contornos, conectividad, cotas y referencias documentales; sin asignar por defecto rigidez, resistencia, carga o función resistente.
2. **Configuración revisada:** secciones/materiales/ejes/mallado, representación del aligerado, acciones, masa, diafragmas, vínculos y apoyos; cada decisión con fuente, hipótesis, unidades y revisión vinculada a huella.
3. **Datos externos:** parámetros de suelo/sismo, condiciones de agua/operación, normativa y criterios/tolerancias aplicables. La visión, el catálogo de modelos IA y una fixture no los suministran con autoridad.

## Inventario de capacidades y necesidad del caso

| Componente | Capacidad actual aprovechable | Representación todavía necesaria |
| --- | --- | --- |
| Cuatro niveles y columnas/vigas rectangulares | Niveles sin tope, frames explícitos y secciones rectangulares | Extraer dimensiones/conectividad y configurar; otros perfiles requieren extensión solo si aparecen. |
| Placas/muros | Shell vertical rectangular isotrópico lineal | Revisar idealización; placas compuestas pueden componerse si conexiones/solapes son explícitos. Huecos, recortes y geometría no rectangular necesitan superficies nuevas. |
| Losas aligeradas | No hay objetos de piso; un diafragma solo no define rigidez fuera del plano, carga ni masa de losa | Geometría de piso/huecos y alternativa técnica revisada: nervios+capa o propiedad equivalente con dirección, rigidez y peso documentados; nunca losa maciza isotrópica automática. |
| Escalera y descansos | Frame inclinado `otro` solo cubre una idealización de barra declarada | Superficies inclinadas/descansos, nodos a cotas intermedias y vínculo con piso; no crear pisos estructurales ficticios para cada vértice. |
| Cisterna/tanque | Paredes rectangulares pueden usar shell actual | Fondos/tapas y aberturas; acciones de agua y apoyos/terreno según revisión. Estado vacío/lleno y eventual efecto hidrodinámico requieren decisión técnica, no una masa arbitraria. |

## Siguiente incremento: superficies planas 3D con recorrido completo

Implementar primero una extensión versionada de geometría y configuración que admita **vértices XYZ independientes de los niveles de piso y superficies planas con contorno ordenado**, y una sección de losa homogénea explícita para pruebas de transporte. Es un fundamento para pisos/descansos/fondos, no prueba de representación suficiente del aligerado ni de la referencia completa.

- Mantener lectura intacta de contratos v0.1; despachar por versión, sin reinterpretar versiones antiguas ni modificar aprobaciones/archivos guardados. La migración crea versión hija pendiente y conserva origen/huellas.
- Nuevos vértices: ID, XYZ físicos, procedencia; nivel asociado opcional para revisión, sin equivaler automáticamente a un Story de ETABS. Superficies: ID, lista ordenada de IDs, papel geométrico declarado y evidencia. Sin material/espesor/rigidez en el contrato geométrico.
- Validar finitud/unidades, identidad, referencias, puntos repetidos, planitud, área positiva, cruces del contorno y conectividad compartida; tolerancias numéricas explícitas, distintas de tolerancias de ingeniería. Primer transporte puede exigir polígonos convexos y rechazar otros con motivo; la geometría restante sigue pendiente del objetivo.
- Configuración: asignación completa de secciones a superficies, tipo/formulación/ejes explícitos, cargas de área con unidades y masa desde patrones. Extender cobertura de puntos para superficies y conservar justificación de diafragmas/exclusiones. Nunca reutilizar la clave `muro` para ocultar un piso.
- Geometría general no decide por sí sola dónde necesita malla/conexión compatible el solver: declarar estrategia y comprobar nodos compartidos en bordes con frames/muros. No aceptar objetos que coincidan visualmente pero estén desconectados físicamente.
- Exportación: reflejar primero firmas/enum de los métodos requeridos de losa y lectura posterior en la DLL instalada; ampliar `FIRMAS`, ENUMS y lista PowerShell conjuntamente. Reusar AddByPoint con cantidad real de vértices, nuevas referencias/tipos y cargas; verificar efecto mediante getters/tablas, guardado y reapertura, sin afirmar métodos aún no comprobados.
- Aberturas: siguiente corte sobre esta base, con contorno contenido/coplar y no intersecante; exportación explícita o partición revisada y trazada. Hasta entonces un piso que requiere huecos no puede pasar por un polígono relleno silenciosamente.

## Mapa de implementación y dependencias

| Orden | Archivos/puntos de extensión | Entregable verificable |
| --- | --- | --- |
| 1 | `contratos.py`, `validacion_geometria.py`, `gestion_geometria.py`, `plan_modelado.py` | Contrato versionado, validador y propuesta geométrica; migración hija sin aprobaciones heredadas. |
| 2 | `conversion_geometria.py::_construir`, `revision_conversion.py`, `revision_web/conversion.js` | Manifiesto nuevo con medidas/conectividad de superficie referenciadas; no escala inferida. Los candidatos genéricos de `extraccion_preliminar.py` permiten evidencia de elemento sin inventar clase física. |
| 3 | `modelo_estructural.py::_Validador`, `gestion_configuracion.py`, `revision_configuracion.py` | Secciones/asignaciones/cargas y fuentes completas; faltantes bloquean aptitud, cambios invalidan revisión. |
| 4 | `operaciones_etabs.py::generar_plan/validar_plan/FIRMAS`, `ejecutor_etabs.py`, `scripts/ejecutar_plan_etabs.ps1` | Plan y ejecución con superficies, IDs, trazas, lectura de efecto y rechazo integral de lo no soportado; plantilla original preservada. |
| 5 | `revision_superposicion.py`, `revision_web/superposicion.js`, `revision_web/configuracion.js` | Proyección de contornos/IDs por vista declarada con anclas existentes; superficies inclinadas requieren vista/sección pertinente, no aparente validación en planta. |
| 6 | Lectura/análisis/controles/informe existentes y sus pruebas | Propagar nuevas huellas y límites a todo el flujo; distinguir «motor terminó» de modelo controlado. |

Codex conserva integración. Delegar por módulos liberados y contrato acordado; no editar simultáneamente montaje compartido ni archivos de Claude multiproveedor.

## Verificación necesaria y puertas posteriores

- Pruebas focales nuevas: normalización m/cm/mm; polígono horizontal/inclinado/vertical válido; repetidos, colinealidad, alabeo, autointersección, referencias ausentes, números no finitos y superficie sin asignación rechazados; conservación de procedencia.
- Regresiones: contratos v0.1, geometría corregida invalida configuración/plan/revisión/informe; no heredar aprobación; exclusión de punto sin razón y doble peso propio rechazados; nodo solo de superficie se admite con conectividad válida.
- Pruebas de operaciones/doble: número/orden de vértices, asignación y carga exactos, igualdad de listas blancas, fallo parcial impide cierre, ID devuelto incorrecto rechazado. Un doble no prueba ETABS.
- Prueba local ETABS en copia: superficie maciza homogénea sintética y panel inclinado con bordes compartidos; leer coordenadas, conectividad, sección, ejes, cargas y fuente de masa tras reapertura; solver/controles por criterios declarados. No extrapolar equivalencia con aligerado.
- Luego implementar aberturas y representación revisada de aligerados; después escalera y contenedores con sus acciones/condiciones pertinentes. Si se elige representación equivalente, conservar justificación y datos verificables; si no basta, extender constitutiva/cargas/mallado requeridos.
- Finalmente ensayar planos reales con IA elegida, revisión de lecturas, manifiesto/configuración completos y ETABS/controles/informe. Conservar lista de cada componente físico y su objeto o idealización revisada. Todo pendiente material queda visible; un rechazo explícito evita error pero no completa el requisito de modelarlo.
- Comparación contra modelo ETABS manual queda diferida por instrucción del usuario; no confundir esta postergación con permiso para omitir el recorrido real ni para certificar seguridad estructural.
