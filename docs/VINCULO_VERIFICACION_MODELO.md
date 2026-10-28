# Relectura ligada al modelo construido

`draft2model.vinculo_verificacion_modelo` integra el lector independiente con un modelo conservado en `modelos_construidos`. Lee su snapshot `modelo.edb`, cuyo SHA procede de la aceptación del constructor; conserva el plan/configuración originales y exige la huella del modelo seleccionado. No usa una ruta EDB arbitraria aportada por el navegador.

Antes de leer y antes de publicar se revalida el modelo completo, su configuración, geometría y originales. El modo debe coincidir: un modelo fabricado con transporte doble nunca se abre con un lector real. El lector conserva sus propias guardas de copia privada, instancia nueva, cierre sin guardar y bloqueo compartido.

La publicación crea una versión inmutable en `verificaciones_modelo`, con solicitud, expectativa, criterios, respuesta, resultado y registro de hashes. Se conservan tanto discrepancias como resultados incompletos; no se sustituyen por éxito. Consultar vuelve a validar la fuente, regenera expectativas desde el plan conservado y recalcula la comparación desde las observaciones. Rehacer hashes de una respuesta cambiada no basta para mantener el resultado anterior.

La relectura **no aprueba el modelo ni autoriza análisis**. `estado`, `verificado`, `verificacion_global_del_plan`, `cobertura_plan` y controles no afirmados deben leerse conjuntamente. No acredita la autoría de un archivo importado ni la calidad de una idealización estructural.

## API

```python
from draft2model import vinculo_verificacion_modelo as vinculo
from draft2model import verificacion_modelo_guardado as lector

verificador = lector.VerificadorModeloGuardado(
    lector.configuracion_real(trabajo, bloqueo_compartido))
version = vinculo.verificar(
    raiz, caso, modelo_id, huella_modelo=huella_modelo,
    verificador=verificador, criterios=criterios_declarados,
    confirmar_lectura=True,
    ejes_locales_area=ejes_declarados_o_none)
evidencia = vinculo.consultar(raiz, caso, version.name)
```

Los criterios siguen [VERIFICACION_MODELO_GUARDADO](VERIFICACION_MODELO_GUARDADO.md): lector0.2 exige 13 magnitudes explícitas. No se añaden tolerancias ni valores físicos por defecto. El directorio de trabajo debe existir. El bloqueo debe ser exactamente el compartido con construcción/análisis/lectura del mismo entorno, nunca un bloqueo nuevo para evadir una operación pendiente.

## CLI

```powershell
.venv/Scripts/python.exe -m draft2model.vinculo_verificacion_modelo --raiz RUTA_CASOS --caso CASO --modelo ID_MODELO --huella-modelo SHA256_MODELO --criterios CRITERIOS.json --trabajo RUTA_TRABAJO --bloqueo BLOQUEO_COMPARTIDO --confirmar-lectura
```

Para ejes explícitos puede añadirse `--ejes-locales-area EJES.json`. Sin confirmación, huella vigente o coincidencia de modo no se lanza el lector. La CLI usa exclusivamente transporte real; el doble se inyecta solo desde pruebas y conserva su marca.

## Evidencia y límites

Incremento168:22 pruebas del lector ampliado y6 del vínculo, **28 OK,0 omisiones,20.880s** en host autorizado. Log `tmp/revision_cobertura_vinculo_168.log`. Los seis casos propios comprueban snapshots reales en disco, confirmación/huella/modo antes de lanzar, conservación de discrepancias, cambio del modelo después de leer, respuesta alterada con hashes rehechos y geometría fuente alterada. El transporte de esas seis pruebas es Python fabricado; el lector se comprueba además con PowerShell y ensamblado ETABS falso. Ninguno acredita ETABS real ni los planos de referencia.

Pendiente: servicio web/trabajos persistentes, presentación en UI/informe, política de aceptación de cobertura y ensayo real. Los nuevos tipos de losa y aberturas requieren sus propios lectores y recorrido integrado. El modelo0.2 de desarrollo permanece no ejecutable; esta integración no elimina ese bloqueo.
