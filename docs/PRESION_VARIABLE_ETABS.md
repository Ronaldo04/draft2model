# Presión hidrostática variable: preparación y ensayos185/186

La DLL21.1 no expone setters de presión superficial variable en `cAreaObj`; sí existe la tabla importable `Area Load Assignments - Non-uniform`, versión1. La inspección nativa en copia propia confirmó los campos importables `UniqueName, LoadPattern, Dir, A, B, C, D, Restriction`. A/B/C tienen dimensión fuerza/longitud³ y D fuerza/longitud²; la tabla admite restricciones de signo.

La [documentación CSI sobre cargas no uniformes](https://wikicsiamerica.atlassian.net/wiki/spaces/etabs/pages/1474784/Applying%2BNon-Uniform%2Bloads%2Bto%2BShell%2BElements) describe la ecuación global y advierte que las restricciones se aplican durante el análisis. Eso no demuestra por sí solo la distribución integrada en una malla concreta.

## Preparación

`cargas_liquidos_etabs.preparar_cargas_no_uniformes(geometria, declarada, fuentes)` reproduce la derivación hidrostática y sus hashes. Produce coeficientes de presión `p=gamma·max(0,h-z)` en kN_m_C, por componente de la normal declarada. Usa Global-X, Global-Y y Gravity (signo Z invertido); elige Zero Negative Values o Zero Positive Values según el signo del componente. No sustituye la presión por resultantes puntuales ni por intensidad uniforme.

La propuesta conserva `ejecutable=false` y `aplicado=false`: falta ligar el patrón revisado y el mapa completo de piezas del plan vigente, importar, releer y comprobar su efecto. No define masa de agua ni hidrodinámica por esta presión. Para superficies que atraviesan h, registra `cortes_obligatorios_z_m`.

## Hallazgo decisivo del ensayo real

Muro sintético4×3m en XZ, hueco interior1×1m entre x1–2/z1–2, gamma10kN/m³, nivel libre1.5m, presión hacia−Y y nodos de borde inferior empotrados explícitamente para esta prueba. El patrón HIDRO tiene peso propio0. No son condiciones del proyecto del usuario.

| Variante | Importación | Fuerza de reacción Y | Momento de reacción X / Z, respecto al origen | Balance analítico |
| --- | --- | ---: | --- | --- |
| Malla12triángulos sin corte en h | 12registros,0errores/avisos | 62.5kN | −47.9166667 /127.0833333kN·m | **Falla** |
| Malla22triángulos con corte en h | 22registros,0errores/avisos | 43.75kN | −21.0416667 /88.125kN·m | Pasa en este ensayo |

Integrales cerradas: F=45−1.25=43.75kN; Mx de reacción=−(22.5−35/24)=−505/24kN·m; Mz=90−1.875=705/8kN·m. El caso sin corte demuestra que importar/releer los coeficientes y la restricción no basta: los elementos atraviesan el cambio de ley en el nivel libre. **El refinamiento en h es obligatorio antes de aceptar esta carga parcial.** No se modifica la tolerancia para hacer pasar el ensayo.

`cortes_superficies.cortar_malla_por_niveles(nodos, triangulos, niveles_z_m)` conserva ambos lados del plano Z, interpola nodos compartidos con parámetros racionales sobre sus aristas y triangula las regiones. No crea niveles de piso ni cambia material, sección o hipótesis de apoyo. Mantiene procedencia y verifica área y ausencia de triángulos que atraviesen un corte. Los nuevos nodos requieren políticas de apoyo/diafragma/vínculo en el flujo de configuración revisada.

## Evidencia y límites

Ensayo185 negativo: `tmp/presion185c/registro.json` y `equilibrio.json`. Ensayo186: `tmp/particion186/registro.json`, `evaluacion.json`, `tmp/presion186/registro.json` y `equilibrio.json`. Los residuos positivos de fuerza/momento son del orden1e−12 con umbral computacional1e−7 en kN/kN·m, no tolerancia de diseño. Todas las instancias propias confirmaron cierre; hashes originales iguales. El log del motor confirma análisis completado y contiene HIDRO más el caso interno ~LLRF. Al abrir copias sin auxiliares se emitió un aviso de archivo Y_; el nuevo análisis generó esos auxiliares y los resultados se comprobaron independientemente.

Los primeros intentos185 y185b conservaron errores de nombre de enum y arrays por referencia, corregidos contrastando la DLL; cerraron sin analizar ni alterar el original. No se presentan como ensayos satisfactorios.

El catálogo, importación y equilibrio son reales sobre datos sintéticos. Los tests con fixtures conservadas solo prueban regresión del software. Falta integrar estas cargas y los cortes con el plan/configuración registrados, la relectura independiente y el informe del caso real. No prueba tensiones, deformaciones, convergencia, seguridad, normativa ni suficiencia de una cisterna/tanque real.

## Relectura dimensional de asignaciones (188)

`draft2model.relectura_presion.normalizar_tabla_no_uniforme` recibe una tabla v1 con `campos`, `datos` planos, `registros` y `unidades` observadas. Convierte ABC (fuerza/longitud³) y D (fuerza/longitud²) a kN/m³ y kN/m². Por ejemplo C=0.00001N/mm³ es10kN/m³ y D=-0.015N/mm² es-15kN/m². Admite N/kN y m/cm/mm; rechaza unidades desconocidas, columnas repetidas, datos incompletos y asignaciones duplicadas.

`comparar_tabla_no_uniforme(esperada, observada, patrones=[...], tolerancia_absoluta=...)` exige patrones y tolerancia computacional explícitos. Detecta ausencias, extras del mismo patrón, cambios de dirección/signo/coeficientes. Cuenta los registros de otros patrones sin acreditarlos. La tabla esperada debe derivarse del plan revisado; comparar una observación consigo misma no acredita construcción. Resultado de asignaciones no concede ingeniería ni verifica equilibrio. Seis pruebas propias incluyen22filas nativas186, seis sistemas de unidades, reordenación de columnas y casos negativos. Evidencia: seguimiento/RELECTURA_PRESION_188.json. Pendiente conectar a la captura normal del modelo registrado.
