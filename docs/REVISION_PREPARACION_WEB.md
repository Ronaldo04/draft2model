# Preparación visual local

La revisión local permite: registrar originales autorizados → seleccionar revisión documental → declarar archivo/página y región normalizada → conservar recorte PDF/JPG/PNG → seleccionar recortes → preparar y consultar paquete local. No interpreta el plano, no deduce escala física ni transmite a proveedores.

ServicioPreparacion y rutas POST `/api/visual/revisar`, `/api/visual/recortar`, `/api/visual/preparar`; GET `/api/visual/historial`, `/api/visual/revision`, `/api/visual/recorte`, `/api/visual/imagen`, `/api/visual/paquete`. Cada operación se liga a caso y expediente_sha256; consulta de versión exige UUID32. El cliente no proporciona rutas. La generación usa las APIs públicas existentes y conserva nuevas versiones.

Recorte: cuerpo caso/expediente_sha256/archivo/pagina/bbox/dpi/etiqueta. Bbox se declara normalizado de0a1 sobre página visible. PDF usa puntos de render; raster usa píxeles orientados EXIF, sin campos de puntos PDF ni DPI físico inferido. Ver RECORTES_RASTER.md para transformaciones y límites. El visor muestra el recorte para contraste humano.

Preparar: caso/expediente_sha256/revision/recortes (1–40 UUID distintos). Se comprueban render, transformaciones y todas las fuentes contra originales mediante preparar_paquete/cargar_paquete. La consulta previa del recorte conserva estado pendiente: hash correcto no equivale a transformación contrastada ni a aprobación de ingeniería. El paquete conserva transmision_externa:false y estado preparado_sin_envio. UUID del contenedor e ID de solicitud son identidades diferentes por contrato; no deben confundirse.

Historial inválido se muestra sin vigencia. Cambiar caso limpia datos/imagen/evento; respuestas y errores tardíos se descartan. Seleccionar revisión y recortes es explícito. Cada preparación crea otro UUID; una repetición tras fallo de conexión puede conservar otra versión, sin sobrescritura ni envío externo.

Verificación:45 pruebas raster/PDF/entrada y servicio web correctas en18.553s, tmp/raster_preparacion_codex_093.log. Integridad ingreso/preparación:11 correctas en3.233s, tmp/preparacion_integridad_094.log. Node preparación13/13. Navegador095 registró imagen sintética y creó recorte; se pulsó preparar, pero la lectura/captura final fue impedida por límite de revisión automática. Comprobación posterior de archivos mediante API pública correcta: tmp/ingreso_paquete_095.json. No atribuir captura visual final ni proveedor real. El servidor temporal10446 fue cerrado.

Pendientes materiales: imágenes derivadas con perspectiva/contraste no están conectadas a esta cadena original; la integración de respuesta visual/proveedor y conversión a geometría revisada siguen separadas. Ninguna prueba sintética acredita precisión sobre planos del usuario.
