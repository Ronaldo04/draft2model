# Tarea independiente: plan de modelado geométrico sin ejecutar ETABS

Estado: propuesta no asignada. El usuario decidió no encargar esta tarea; se conserva únicamente como antecedente, fuera de las tareas activas.

## Encargo para Claude Code

Trabaja en Draft2Model. Implementa un módulo que transforme el contrato geométrico existente en una propuesta explícita de geometría tridimensional para un futuro adaptador ETABS, sin abrir ETABS ni llamar a su API. El objetivo es probar la traducción de niveles, nodos en planta y muros antes de incorporar materiales, cargas y análisis.

Primero lee README.md, docs/CONTRATO_GEOMETRIA.md, draft2model/contratos.py, draft2model/validacion_geometria.py, examples/geometria_sintetica.json y sus pruebas. Revisa AGENTS.md si existe. Usa el contrato real del repositorio; no inventes otro ni modifiques el existente.

### Archivos permitidos

Crear exclusivamente:

- draft2model/plan_modelado.py
- tests/test_plan_modelado.py
- examples/plan_modelado_sintetico.json
- docs/PLAN_MODELADO.md

No modificar CLI, extracción, gestión de extracción, evaluación de visión, README, AVANCES, dependencias ni contratos existentes. Otras tareas se desarrollan en paralelo. Si un requisito exige modificar un archivo ajeno, describir el bloqueo y proponer el cambio en la entrega.

### Función y comportamiento

Implementar `preparar_plan_modelado(geometria)` como función pura: devuelve un objeto JSON serializable y no modifica la entrada, archivos ni estado externo.

1. Usar validar_geometria() y su normalización a metros. No duplicar el validador ni interpretar píxeles de planos como metros.
2. Distinguir entrada inválida, geometría consistente con faltantes, geometría consistente completa y aprobación registrada vigente. Incorporar errores y bloqueos del validador sin convertir consistencia en aprobación.
3. Para cada muro con todos sus datos disponibles, construir cuatro vértices 3D en metros a partir de sus nodos inicial/final y niveles inferior/superior. Orden: inicio inferior, fin inferior, fin superior, inicio superior. Son superficies geométricas propuestas; no afirmar que son elementos ETABS ni que su orientación define ejes locales de ETABS.
4. Registrar ID del muro, nodos y niveles fuente, espesor en metros, longitud, altura y área geométrica bruta rectangular. No descontar aberturas ni inferir elementos de confinamiento. Explicar que el área bruta no define peso, masa o resistencia.
5. Si un muro carece de cota o espesor, omitir su superficie de la colección completa y listar explícitamente el muro y sus faltantes; no inventar datos ni omitirlo silenciosamente. Si la entrada es inconsistente, no emitir superficies que parezcan utilizables.
6. Devolver contrato/version propios del plan, ID del caso, huella del contenido geométrico, unidades explícitas, procedencia preservada, superficies, omisiones y bloqueos. El plan es un artefacto derivado: no copiar una aprobación geométrica como aprobación del plan.
7. Mantener `ejecutable_en_etabs: false` y explicar los pendientes: definición de materiales, secciones/objetos ETABS, representación estructural, cargas, condiciones de borde y verificación del adaptador. No usar `disponible_para_modelado` de geometría para afirmar disponibilidad de análisis.
8. No inferir tipología, número admisible de pisos, materiales, cargas o parámetros sísmicos. No incluir recomendaciones normativas ni fórmulas de diseño.

### Pruebas y documentación

Usar unittest y biblioteca estándar. Incluir casos que comprueben coordenadas y orden de vértices con valores esperados escritos explícitamente, equivalencia entre m/cm/mm, referencias inválidas, altura o longitud no positivas, cotas negativas válidas, faltantes, aprobación ausente/vigente/desactualizada, entrada no modificada, salida JSON estricta y determinista. Usar fixtures sintéticos. No usar planos privados ni solicitar ETABS instalado.

El ejemplo versionado debe ser inequívocamente sintético y reproducible a partir de una entrada identificada, preferentemente el ejemplo geométrico existente. Documentar limitaciones y cómo reproducirlo. Ejecutar la suite completa y registrar número de pruebas, comando y resultado real; no asumir que el conteo inicial sigue siendo 56.

### Entrega y GitHub

Trabajar en una copia clonada propia del repositorio privado Ronaldo04/draft2model, nunca en la carpeta compartida de otro desarrollador. Crear rama `feat/plan-modelado-geometrico` desde main actualizado. Si ya existe, inspeccionarla antes de continuar; no sobrescribirla ni usar force push.

Versionar únicamente los cuatro archivos permitidos. Revisar diff y estado para excluir planos, data/private, credenciales y archivos generados. No usar `git add .`.

Si hay autenticación GitHub disponible y el usuario autorizó esta entrega, subir la rama y abrir una pull request hacia main. Título: `Agrega plan geométrico previo al adaptador ETABS`. Describir comportamiento, pruebas realmente ejecutadas y limitaciones. No fusionar ni hacer push directo a main. Si GitHub no está autenticado, dejar commit local y explicar el paso pendiente; nunca pedir que se peguen tokens en el chat.

Al terminar entregar enlace a la PR (si se creó), SHA del commit, archivos cambiados, pruebas y pendientes. No atribuir trabajos ajenos ni declarar completado el adaptador ETABS o el análisis estructural.
