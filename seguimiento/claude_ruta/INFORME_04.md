# Etapa 04 — piloto con los planos adjuntos (ruta 201): **bloqueado (solo piloto)**

## Estado observado

- **Autorización** (`seguimiento/AUTORIZACION_API_211.json`): OpenAI hasta 5 USD y 5 peticiones; Gemini solo gratuito. **Ejecutor exclusivo: Codex.** Claude no hace llamadas a la API.
- **Petición real 1**, ejecutada por Codex:
  - modelo `gpt-5.4-2026-03-05`, paquete 135 (10 imágenes);
  - 30 174 tokens de entrada y 2 198 de salida;
  - respuesta `8888d1f3…` pendiente de revisión.

## Revisión y medición (Claude; **asistida, no es referencia humana**)

- **Candidatos:** 34 (14 cotas, 13 etiquetas y 7 elementos).
- **Muestra de 10 contrastada con la página original:**
  - valor correcto en 8;
  - 2 incorrectos o sin respaldo (C004 «1.3 m», donde se lee «.80»; C024 «0.15 m»);
  - cajas: 4 ajustadas, 4 desplazadas y 2 vacías.
- **Datos reales útiles:** aligerado e = 17 cm; S/C 200 kg/m² (nivel 1) y 150 kg/m² (nivel 4); viga VS 0,15×0,30; identificadores de placas y columnas.
- **Faltan para modelar:** ejes y distancias, niveles y alturas de entrepiso, dimensiones de placas y columnas, losas de los niveles 2–3, escalera, cisterna y materiales. **No se construye geometría ni configuración inventando estos datos.**

Detalle en `logs/medicion_211.json` de la entrega.

## Corrección del sistema

- **Causa:** las instrucciones de visión no pedían cobertura exhaustiva ni las categorías necesarias para modelar. El modelo devolvió una muestra (2 198 de 8 192 tokens): fue una parada temprana, no un truncamiento.
- **Corrección** en `entrada_vision._prompt`:
  - objetivo de cobertura exhaustivo y priorizado (ejes, niveles, elementos, S/C, materiales, escalera, cisterna);
  - `texto_fuente` literal y caja ajustada a ese texto;
  - se conservan intactas las reglas contra la inferencia.
  - Pruebas de visión y proveedor: 58 OK.
- **Paquete nuevo:** `ace03b8b…` (mismos recortes) y plan **sin envío** `planes_openai/2617a919…`. Solicitud concreta a Codex en `seguimiento/claude_ruta/SOLICITUD_PILOTO_04.json` (petición 2 de 5).

## Bloqueo (externo a Claude)

1. Ejecución de la petición 2 por Codex, dentro del límite autorizado.
2. Después: los datos técnicos que los planos no documenten. Se preguntarán **una sola vez** en una lista concreta, tras revisar la segunda extracción.

Mientras tanto continúo con la etapa 05. La comparación manual sigue aplazada por el usuario.
