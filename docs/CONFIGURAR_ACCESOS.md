# Configurar accesos del proyecto

Preferencia vigente del usuario,20-10-2026: trabajar SOLO con Google y OpenAI. Completar únicamente GEMINI_API_KEY y OPENAI_API_KEY; los demás adaptadores quedan como capacidad opcional del código, sin contratación ni uso autorizado por esta preferencia.

Comprobado el 19-10-2026. Basta **un proveedor multimodal** para visión y explicaciones. No hace falta comprar todas las APIs. Tener una clave no garantiza acceso al modelo, saldo, cuota, imágenes o salida estructurada: eso se comprobará con una petición acotada cuando se declare modelo y presupuesto.

| Acceso | Variable | Cómo obtenerlo | Necesidad |
|---|---|---|---|
| Google Gemini | GEMINI_API_KEY | Entrar en Google AI Studio, seleccionar/crear proyecto, abrir API Keys y crear la clave vigente. Revisar el plan y límites de ese proyecto. | Una opción para comenzar; no obligatorio si se usa otro. |
| OpenAI | OPENAI_API_KEY | Entrar en OpenAI Platform, seleccionar/crear proyecto y crear una clave para ese proyecto; habilitar facturación/saldo y acceso al modelo cuando corresponda. No se requiere clave de administrador. | Alternativa o comparación. |
| Anthropic | ANTHROPIC_API_KEY | Entrar en Claude Console, Settings → API keys → Create key; clave personal para desarrollo o cuenta de servicio para cargas compartidas, con acceso y saldo necesarios. | Alternativa para visión/explicaciones. Delegar programación por API requiere integración adicional. |
| Chat Completions compatible | COMPATIBLE_API_KEY y D2M_COMPATIBLE_ENDPOINT | Clave y URL exacta del servicio elegido. Debe aceptar imágenes y JSON Schema por este protocolo; endpoint HTTPS público terminado en /chat/completions. | Opcional; no se necesita contratar un cuarto proveedor. |
| ETABS | Sin clave de servicio externo | Instalación local, licencia válida, DLL compatible y ejecución local del puente. | Necesario para los ensayos del motor. Ya hay instalación y ensayo sintético previo; aún falta validar las nuevas capacidades. |

No se necesitan para el alcance local actual APIs de OCR, embeddings, Pinecone, Supabase, Google Maps, correo ni almacenamiento en nube. Corpus/reglas/sitio usan archivos locales. Si aparece una dependencia material nueva se documentará antes de contratarla.

## Fuentes oficiales

- [Gemini: claves API](https://ai.google.dev/gemini-api/docs/api-key), [facturación](https://ai.google.dev/gemini-api/docs/billing), [cuotas](https://ai.google.dev/gemini-api/docs/rate-limits).
- [OpenAI: crear/exportar una clave](https://developers.openai.com/api/docs/quickstart).
- [Anthropic: obtener clave](https://platform.claude.com/docs/en/get-api-key), [cuotas](https://platform.claude.com/docs/en/api/rate-limits).
- [Condiciones de datos de Gemini](https://ai.google.dev/gemini-api/terms): el tratamiento difiere entre servicios gratuitos y de pago. Revisarlo antes de transmitir planos privados; no confundir gratuidad con confidencialidad o ausencia de límites.

## Archivo privado preparado

Completar `data/private/credenciales.local.md` en el único bloque `env`. Las líneas son `NOMBRE=valor`; no se evalúan scripts, sustituciones ni órdenes. Las claves vacías no sobrescriben el entorno. Los modelos, presupuestos y permiso de transmisión se registran debajo sin secretos. No se necesitan contraseñas de cuentas ni claves de administrador.

`data/private/` está excluido de Git y de la copia limpia del proyecto. No colocar claves en `docs/`, `seguimiento/`, README ni en el chat. Esta opción de archivo privado se añade por petición explícita del usuario; la carga temporal por Read-Host de ACCESOS_Y_PROVEEDORES sigue disponible.

Comprobar **solo presencia**, sin mostrar valores, autenticar ni gastar:

```powershell
.venv/Scripts/python.exe scripts/usar_credenciales_locales.py --comprobar
```

Arrancar servidor heredando claves en su propio proceso:

```powershell
.venv/Scripts/python.exe scripts/usar_credenciales_locales.py --raiz data/private --puerto 8777
```

Se puede indicar otro expediente raíz o `--archivo` privado. El `.cmd` de arranque anterior no carga este Markdown por sí solo. Reiniciar el proceso mediante este cargador después de completar claves; no basta editar el archivo mientras sigue funcionando un servidor anterior. No hay llamadas, importaciones, envío de planos ni ejecución ETABS automáticos al cargar credenciales.

## Límites que estas claves no resuelven

Las APIs conservan límites de solicitudes/tokens/saldo. No amplían automáticamente las cuotas de esta conversación, de los subagentes de Codex o de Claude Desktop. No cambian permisos de Windows ni licencias ETABS, y no corrigen el código pendiente. El desarrollo por API sería otro flujo, con saldo y presupuesto propios, no una continuación ilimitada de esta sesión.

El modelo ETABS manual del usuario permanece reservado para comparación posterior a producir los resultados finales del sistema; no se requiere entregarlo para configurar accesos.


## Restricción vigente20-10-2026: consumo exclusivo para planos

El usuario declara haber completado las claves de Google y OpenAI. No se leyeron sus valores ni se validó autenticación mediante llamadas. No falta otraAPI para el alcance actual.

Su uso real queda limitado a revisión de imágenes de los planos y devolución de la extracción estructurada exigida por el sistema. No se autorizan APIs para desarrollo/delegación de programación, explicaciones de resultados, documentación, pruebas genéricas ni otras finalidades. El backend de explicaciones conserva salida determinística sin tocar la red incluso con claves presentes. Los transportes inyectados de pruebas son dobles sin claves reales. Los planes de visión mantienen autorización explícita, huella y protección contra reenvíos. No se cambian modelos/proveedores ni se hacen reintentos como forma de evitar un fallo o cuota. ETABS sigue usando API local y licencia, sin clave externa.
