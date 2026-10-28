# Cotas auxiliares sin pisos ficticios — ensayo257

**Resultado nativo verificado:** ETABS aceptó geometría auxiliar fuera de0…10.4m manteniendo únicamente base0 y pisosN1/N2/N3/N4=2.6/5.2/7.8/10.4m. Guardado y reapertura del EDB propio conservaron coordenadas y conectividad. `ENSAYO_COTAS_AUXILIARES_257.json` contiene las comprobaciones independientes; `tmp/ensayo_cotas_auxiliares_257/runs/codex257a/registro.json` conserva98 llamadas con retorno0 y hashes. No repetir este ensayo sin un fallo o cambio que lo justifique.

Se crearon12puntos, dos triángulosShellThin (Z−2.5 y14.25) y dos barras (−2.5→0 y10.4→14.25), con ocho cotas distintas:−2.5/−.105/−.05/0/10.4/12.5/13.7/14.25. Los puntos se marcaronSpecialPoint, no se agregaron plantas, diafragmas ni restricciones deducidas. Puntos inferiores se releyeron con asociaciónStory=Base; superiores, conStory=N4, conservandoZglobal. El nombre deStory no se interpretó como sustitución de su coordenada ni como nueva planta física.

Instancia creada mediante objetoAPI nuevo, nunca adjuntada a una instancia previa. CierreApplicationExit0, candidatoPIDausente y cuatroPIDs previos conservados. Solo se guardó/reabrió el EDB nuevo de la corrida. No hubo análisis ni solicitudesOpenAI/Gemini.

## Aplicación al rechazo del plan

El rechazo anterior en `_motivos_superficies` deriva de una limitación del software del proyecto, no de una prohibición demostrada de ETABS para estas cotas. La corrección debe conservar controles de geometría finita, asignaciones, restricciones/diafragmas explícitos, fuentes y malla; separar el intervalo de **pisos** de las coordenadas de elementos auxiliares. No añadir pisos de uso ni modificar altura sísmica para esquivar la guarda.

Permitir únicamente lo que la opción/contrato declare como geometría auxiliar revisada; validar el origen y las referencias de puntos/frames/superficies. Los puntos de malla derivados deben conservar la política explícita de apoyo/diafragma ya existente. No inferir cimentación rígida, conexión de cisterna o apoyo del tanque por estar por debajo/encima de un nivel.

Esto no prueba el piloto ni elimina los problemas de caras mojadas, masa, escalera o conectividad. Tampoco acredita tensiones, modos, derivas ni cumplimiento normativo. Es la comprobación acotada necesaria para extender el transporte sin deformar el edificio.

## Aviso conservado

Durante la reapertura, ETABS imprimió «Cannot open file / BufferFileIn» para el auxiliar `modelo.Y_`. `OpenFile` devolvió0 y se releyeron correctamente todos los puntos, elementos y plantas. No hubo solver: no se convierte ese mensaje en un aviso de un análisis ejecutado, ni se afirma su causa sin evidencia. El ensayo mantiene ese límite explícito.
