# Revisión propia del modelo construido

`python -m draft2model revision-modelo --raiz RUTA --caso CASO --help` permite registrar, consultar, aprobar y comprobar una aprobación. No conecta con ETABS ni ejecuta análisis.

## Registro

`registrar --configuracion CONFIG.json --plan PLAN.json --corrida CARPETA_CORRIDA` requiere aceptación de la puerta integrada de construcción. Comprueba configuración/geometría vigentes, plan regenerado exacto, solicitud/respuesta, orden completo de traza, retornos cero, nombres y SHA256 del EDB. Rechaza la corrida si existe revisión de integración fallida. Solo admite transporte doble para datos sintéticos.

Crea `modelos_construidos/<id>` dentro del expediente con copia inmutable del EDB y evidencia. El estado inicial es pendiente, aunque configuración y geometría estén aprobadas. La copia permite conservar el modelo revisado si ETABS modifica posteriormente el archivo de trabajo externo. La consulta sigue comprobando el origen geométrico actual: alterarlo invalida el artefacto.

## Declaración de revisión

`consultar --modelo ID` devuelve la huella exacta del registro. `aprobar --modelo ID --huella-esperada SHA --revisor NOMBRE --fecha AAAA-MM-DD --alcance TEXTO` requiere además las cinco confirmaciones explícitas:

- `--confirmar-geometria-conectividad`
- `--confirmar-materiales-secciones`
- `--confirmar-cargas-masa`
- `--confirmar-apoyos-diafragmas`
- `--confirmar-casos-combinaciones`

La revisión corresponde a una persona que haya comprobado esas materias; la CLI no realiza ni suplanta esa revisión. Crea otro registro inmutable en `aprobaciones_modelo/<id>` y no modifica el modelo. `comprobar-aprobacion --aprobacion ID` verifica nuevamente huella, contenido, origen y confirmaciones antes de devolver estado aprobado. Una modificación exige un nuevo artefacto y una revisión nueva.

El registro declara identidad sin autenticar y autoriza el paso de análisis para ese modelo exacto. No aprueba resultados ni informe ni certifica seguridad estructural. Hashes y trazas no autentican al productor. Toda aprobación de una fixture conserva `datos_sinteticos=true` y su naturaleza de prueba de software.

La consulta histórica admite exclusivamente que evolucione el catálogo informativo `pendientes` del generador: conserva y valida el plan/hash archivados y compara estrictamente todo el contenido operativo regenerado. La ampliación dinámica cambió ese catálogo global aun para modelos estáticos ya construidos. Un cambio de llamadas, argumentos, referencias, configuración, opciones u otra condición sigue invalidando la consulta. Esta compatibilidad solo afecta a revisión de modelos ya capturados; el ejecutor de nuevas solicitudes sigue exigiendo igualdad exacta del plan recibido y regenerado. Regresión adicional y comprobación real de la aprobación sintética anterior: `tmp/pruebas_modelo_historico_015.log`, 12 pruebas pertinentes OK.

## Evidencia

Seis pruebas locales sin ETABS cubren ausencia de herencia de aprobación, conservación inmutable, cambios del EDB/origen, huella/controles/fecha, integración fallida, traza reordenada/retorno distinto de cero y aprobación alterada. Se registró el EDB real del ensayo sintético como modelo pendiente `84280559f06d405eaf779a8ad916b0ad`, dentro de la demo integrada; no se concedió revisión de ingeniería ni se ejecutó análisis por este registro.
