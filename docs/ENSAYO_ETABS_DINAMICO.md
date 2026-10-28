# Ensayo dinámico sintético en ETABS 21.1

Codex, 17 de octubre de 2026. No es un edificio real ni una revisión de ingeniería. Se reutiliza la geometría sintética estática y se agregan MOD (Eigen, tres modos), EX (U1, CQC, damping 0.05, excentricidad cero) y ESP-PRUEBA del ejemplo. Los parámetros son inventados para comprobar software.

## Construcción y persistencia comprobadas

La instancia nueva propia 23848 se creó con `scripts/crear_plantilla_etabs_vacia.ps1`; registro `tmp/d2/instancia.json`. Se abrió una copia con SHA comprobado de la plantilla vinculada a la configuración. Nunca se usó un modelo del usuario.

La corrida aceptada es `tmp/d4/construccion/e3d9cd05f79545fb8370c9b7d673307c`, con 69 operaciones y `aceptacion_integracion.json`. Modelo `tmp/d4/ensayo/modelo.edb`, SHA256 `c71d19cff0c891021787c95d01bd0a0464279cc38821e1b5a1dda49d8e1fa305`. Plan `5fae6c57529bbc6d21b501e1a24cf30dedec7421d1dbd3f99536105b9b48a935`.

Se reabrió una copia idéntica en `tmp/d4/copia_persistida/modelo.edb`. El lector independiente recuperó 39 registros (`lectura_persistida.json`). `comprobacion_dinamica.json` contrasta 24 controles: modos y parámetros Eigen, ausencia de cargas iniciales, modal asociado, función/dirección/factor/sistema/ángulo, excentricidad, amortiguamiento y combinación CQC, respuesta rígida desactivada y pares de la función. Sin faltantes ni discrepancias. No autentica el productor ni verifica respuesta física.

`controles_estaticos/comprobacion_asignaciones.json` aporta 55 contrastes de propiedades, conectividad, cargas, masa, apoyos, diafragmas, caso estático y combinación. Su configuración es deliberadamente un subconjunto de diagnóstico sin casos dinámicos; no se presenta como la configuración aprobada completa. `lectura_objetos.json` y el script de preparación de análisis contrastan coordenadas del plan y puntos guardados.

## Fallos reales conservados y correcciones

- `tmp/d1`: clave de tabla inexistente (-96), antes de mutaciones. Claude corrigió esquema de caso y separación de damping; Codex verificó 47 pruebas en host, `tmp/revision_claude_csi_host_023.log`.
- `tmp/d2/construccion/47ae2012d3ff4dc9afeb1958477a8408`: operación45 falló al releer la función. CSI devuelve DampRatio solo en su primera fila; las siguientes son vacías. Evidencia `tmp/d2/lectura_postfallo.json`. El ejecutor expande exclusivamente ese campo agrupado para comparar, sin omitir el valor inicial. Los dobles reproducen el formato real.
- `tmp/d3/construccion/e9e8b98c7aa64df0a4a1aebe5bf782e6`: operación55 falló en GetValues. NumberItems=3, MyTime=[0,0,1,2], Value=[0,0.1,0.1,0.05]. Evidencia `lectura_parcial.json`; se omiten combinaciones todavía no creadas, por lo que no es lectura completa. El ejecutor conserva crudos en traza y reconoce solo arrays N+1 con centinela inicial (0,0); compara luego los N pares completos. No trunca arbitrariamente.
- El archivado ordena claves JSON; validar_plan exigía orden de inserción de claves en cada registro. Se compara ahora el conjunto exacto de campos; la lista de columnas y operaciones mantiene su orden. Regresión de serialización canónica añadida.

Las copias parciales se descartaron tras diagnóstico de solo lectura y retorno terminal del puente, archivando las recuperaciones bajo el mismo bloqueo `tmp/d2/motor.lock`. No se continuó ningún plan en un modelo parcial. No reutilizar modelos/corridas fallidas como entregables.

## Cálculo y límites

Modelo inmutable registrado `f2fb9ada805d4c7aae6abb89dc9a02ab`; aprobación `0c81af8c60e845e1bed3ee2f782c58c7`, explícitamente sintética y de software. El análisis deliberado se lanzó desde esa versión exacta, en instancia nueva: `tmp/ad1/bcd0c0b7b407496b88976ddc3f23b7a9`. Consultar aceptación y estado terminal; el lanzamiento por sí mismo no acredita cálculo completado.

No hay todavía resultados dinámicos normalizados ni comparación física/manual, planos reales procesados o conformidad normativa acreditada por este ensayo. La lectura independiente aún es un script de diagnóstico; su envoltura de producto con exclusión compartida y revisión permanece pendiente.

Pruebas posteriores a correcciones: 18 correctas (`tmp/pruebas_getvalues_029.log`), siete del comprobador (`tmp/pruebas_centinela_030.log`) y veinte de archivado/comprobador/revisión (`tmp/pruebas_archivado_dinamico_032.log`). Son comprobaciones locales específicas, no sustituyen la suite integrada estable ni el cálculo real.

Actualización de cálculo: corrida terminada correctamente; aceptación presente, EST/MOD/EX=4 tras reabrir, propia29788. EDB SHA256 `74fa99fe2c1188659f4e9f8828c2589f898476c92d4c62b75625abc332ecade9`. Tablas en `lectura/72cab2fb1c544e49a25ea20d2d35367b/respuesta.json`. Sus periodos mostrados tienen menos decimales que el LOG; conservar esa precisión y procedencia. EX: FX0.1136kN y derivaX1e-6. No hay fila de derivaY. La normalización modal necesita admitir explícitamente el campo Case observado; no inventar OutputCase ni atribuir direcciónX al primer modo (predomina Y).

Resultados normalizados publicados en la demo: `994e298b81b9435fbf9fde9f3eba2f30`. La verificación de evidencia enlaza aprobación de modelo, análisis aceptado y EDB leído exacto. Informe `tmp/informe_dinamico_039` inspeccionado en sus tres páginas con Poppler; copia final `output/pdf/ensayo_dinamico_preliminar.pdf`. Panel `tmp/panel_dinamico_040.html` generado sin revisión visual de HTML. La comprobación dinámica ampliada27 controles incluye ausencia de overrides de amortiguamiento, todos coincidentes. Esto amplía los24 controles históricos sin sobrescribirlos.

Suite integrada041:532 pruebas, un error de limpieza de un descendiente de prueba al cerrar temporal; archivos estables. Se corrigió sincronización de proceso exacto, prueba focal042 correcta; repetición043 pendiente de resultado. No atribuir éxito global a041.
