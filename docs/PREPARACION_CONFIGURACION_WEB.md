# Preparar ingeniería dentro de la aplicación

La etapa 4 permite conservar una configuración de trabajo aunque aún falten
datos técnicos. No requiere preparar un archivo JSON fuera de la interfaz.
El registro formal y su aprobación siguen siendo operaciones separadas.

## Preparar y completar

1. Abra una geometría comprobada del expediente en la etapa 3.
2. En la etapa 4, pulse **Preparar desde la geometría abierta**. El sistema
   incorpora sus puntos y superficies. Si la geometría procede de una lectura
   automática conservada, incorpora también sus columnas y vigas propuestas.
3. Seleccione un grupo en **Editar datos de ingeniería** y complete sus datos
   con las fuentes correspondientes. Materiales, secciones, cargas, apoyos y
   decisiones de análisis ausentes permanecen pendientes.
4. Pulse **Guardar borrador de trabajo** para crear otra versión sin sustituir
   la anterior. Puede volver a abrirla mediante **Configuraciones en preparación**.
5. **Validar y registrar configuración** solo incorpora al registro formal una
   preparación consistente. La acción no registra aprobación de ingeniería.

Un borrador incompleto se puede guardar; sus errores se muestran en pantalla.
No se ejecuta ETABS mediante estas acciones. La existencia de una preparación
no demuestra que la geometría incluya todos los elementos del edificio.

## Continuidad entre superficies

**Calcular conexiones propuestas** detecta solapes de longitud positiva entre
aristas exteriores exactamente colineales. Puede proponer una unión cuando
los extremos de las dos aristas son distintos y solo coinciden en parte.
No une por proximidad, por contacto puntual, por cruces interiores ni por
bordes de aberturas. Una superficie completamente duplicada exige revisión.

Revise las superficies y extremos indicados en la lista. Seleccione las uniones
que representan continuidad estructural y excluya juntas o contactos sin
transmisión de esfuerzos. Indique declarante, fecha y alcance y confirme la
selección. **Guardar continuidad revisada** conserva una versión hija con el
documento de conexiones y sus huellas calculados por el programa. Es posible
declarar una selección vacía de manera explícita.

La selección queda ligada al contenido de la preparación y al algoritmo que
generó la propuesta. Cambiar el borrador obliga a calcular y revisar otra vez.
La identidad del declarante no está autenticada. Esta declaración no aprueba
el modelo completo, las propiedades, las cargas ni los resultados.

## Material de concreto desde una lectura conservada

El apartado **Material de concreto desde la lectura del plano** consulta una
versión comprobada del expediente y muestra sus propiedades y cargas. Usa los
valores corregidos cuando existen y excluye lecturas rechazadas y resultados
impresos. La consulta no cambia las revisiones de las lecturas.

Seleccione una resistencia identificada literalmente como f'c. Declare el
identificador del material, peso específico, declarante, fecha y sustento, y
confirme la aplicabilidad de concreto de peso normal sin ensayos confiables
de E o G que sustituyan las fórmulas. El programa calcula Ec según 8.5.2 y
G según 8.5.4 de la [E.060 oficial](https://cdn.www.gob.pe/uploads/document/file/2686419/E.060%20Concreto%20Armado%20DS%20N%C2%B0%20010-2009.pdf).
Poisson se deriva de esas relaciones bajo isotropía; no se presenta como un
valor tabulado por la norma. El peso específico se toma de la declaración,
no se calcula desde f'c.

**Calcular material y guardar borrador** conserva una versión hija con la
lectura, condiciones, fuentes y cálculo. No sustituye materiales existentes,
no asigna automáticamente secciones, no aprueba la lectura ni el modelo y no
ejecuta ETABS. Las cargas consultadas no se asignan a elementos sin establecer
su distribución y alcance.

## Límites actuales

Esta preparación no deduce propiedades mecánicas, suelo o condiciones de apoyo
desde valores predeterminados. Tampoco completa automáticamente los elementos
que la lectura haya omitido ni las políticas de todos los nodos derivados de
la malla. Quedan estructuras avanzadas que requieren ampliar los formularios;
la disponibilidad de la vista JSON no acredita su resolución en la interfaz.
El recorrido automático completo hasta resultados sigue pendiente de validación.
