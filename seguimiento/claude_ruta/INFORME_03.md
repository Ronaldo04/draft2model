# Etapa 03 — integración de la referencia completa (ruta 201)

## Hecho

- **Matriz de requisitos** (`docs/MATRIZ_REQUISITOS_REFERENCIA.md`): cada requisito con módulo, criterio, evidencia y estado (implementado / doble / nativo sintético / pendiente de dato o piloto / pendiente de código). No se elimina ningún requisito.
- **Edificio de referencia sintético con todos los componentes** (`tests/test_referencia_ruta201.py`, driver `--escenario referencia`):
  - 4 niveles;
  - losas aligeradas nervadas (techo macizo);
  - placas conectadas a cada losa;
  - 8 columnas y 4 vigas;
  - escalera (descanso más tramo inclinado) conectada;
  - cisterna con corte Z = 1,2.
  - **Nativo** (`tmp/r3`): 320 operaciones, cierre propio confirmado, relectura verificada (0 discrepancias, 0 incompletos), análisis completo y **equilibrio estricto** con `BaseReact` (residuos ≤ 1,8e-12). Resultado global: aceptado. Es sintético y no constituye ingeniería.
- **Proveedores** (R202-03): solo Google y OpenAI son operativos en la UI, la CLI y el servicio real. Los adaptadores Anthropic y compatible quedan solo para la historia y las pruebas con dobles.
  - Una prueba antigua esperaba `clave_ausente` en las explicaciones, pero la política vigente devuelve `api_restringida_a_revision_planos`; actualicé la expectativa.
- **Validación de entorno** (`python -m draft2model.preflight`): instalación, DLL y versión, PowerShell y directiva, permisos, presupuesto de rutas frente a 260 caracteres e incertidumbre del motor, con acciones concretas. En el host: listo, con aviso de rutas de 244 caracteres.
- **Autoría sin programar** (`plantilla_configuracion`):
  - borrador 0.4/0.5 sin datos inventados (líquidos = `informacion_insuficiente`; conexiones null hasta declararlas);
  - documento `conexiones_borde` ligado a la geometría con las huellas calculadas.
- **Documentación** (R202-01/02/03): README, CONTEXTO y MATRIZ_CIERRE (marcada como histórica). La comparación manual consta como aplazada y no como condición; las copias limpias 100/146/148 constan como históricas.

## Pruebas

Ver `etapa03_pruebas.log`: 127 OK, 0 omitidas, en 17 módulos; 4 scripts Node OK.

## Límites

- No hubo QA visual en navegador (etapa 05).
- No hubo piloto con los planos reales (etapa 04).
- Las escaleras se idealizan como losa de garganta, sin peldaños; la representación la declara el revisor.
- En el equilibrio nativo solo se contrastó el caso CHIDRO; las reacciones del caso EST no tienen expectativa analítica independiente en esta etapa.
