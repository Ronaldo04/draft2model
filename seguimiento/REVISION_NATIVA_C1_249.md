# Revisión independiente del ensayo nativo C-1 - 249

Fecha: 2026-10-22. Solo lectura de `tmp/columna_l_246b/registro.json`, `scripts/ensayar_columna_l_etabs.ps1` y propiedades analíticas de auditoría246. Sin ejecutar el ensayo, ETABS, API, red o GUI. Sin editar producto ni archivos de Claude. Los cálculos auxiliares operan únicamente sobre el JSON conservado y fórmulas elásticas; no son un nuevo ensayo nativo.

## Conclusión

**El recibo acredita definición/persistencia de parámetros de una L nativa, área e inercias diagonales correctas, y efectos de inserción/excentricidad. No acredita acoplamiento flector por el producto de inercia de la L.** El caso C10 centrado da Uy=0 y se reproduce con rigidez diagonal desacoplada; los Uy de C1/C10G se reproducen por torsión de cargas excéntricas, sin introducir Ixy. Por tanto el comentario del script «lateral load reveals the product of inertia» no está sustentado por este resultado.

Esta conclusión se limita al montaje, datos y resultados conservados. **No demuestra que ETABS carezca de capacidad para representar flexión no simétrica**, ni identifica por sí sola qué opción, convención de ejes o representación de sección produce la respuesta. No habilita afirmar fidelidad completa de la C-1 real del piloto.

## Cobertura efectiva y persistencia

- Cuatro secciones: MirrorAbout2/MirrorAbout3=(false,false),(true,false),(false,true),(true,true), con T3=T2=.40 y Tf=TwC=TwT=.15.
- Cuatro variantes por sección: C1(cardinal1), C10(cardinal10), C11(cardinal11), C10G(cardinal10 más offsets Global[.10,.05,0] en ambos extremos). Son **16frames**, no cuatro inserciones geométricamente independientes: en el resultado C10 y C11 son equivalentes.
- Los16 retornos SetInsertionPoint guardados son0. Todos los frames releídos tienen mirror2=false en la **inserción**, stiff_transform=true, ángulo0 y avanzado=false. No confundir este mirror2 de objeto con los dos espejos de **sección**.
- GetConcreteL relee material/dimensiones/espejos. GetSectProps relee área, áreas cortantes, torsión, inercias y módulos. GetInsertionPoint/GetLocalAxes/GetSection/GetPoints releen asignación, inserción y eje. Hay16frames y4secciones tanto en construcción como reapertura.
- Las fases usan unidades distintas: **kN_m_C** en construcción, **N_mm_C** al reabrir. Las diferencias crudas .4→400, .15→150, A.0975→97500 e I.001230889→1230889423 son conversiones dimensionales, no corrupción. Tras normalizar longitudes/áreas/módulos/inercias con potencias1/2/3/4 de1000, error relativo máximo observado≈**3.53e−16**; etiquetas/espejos/cardinales/ejes/puntos permanecen iguales, y offsets.10/.05m reaparecen100/50mm.
- Ambas cadenas SHA **declaradas** antes de reabrir y final son `e9169a3f956084235c8d70c625da81efb99bb77ecf02a4edac9af72fe39dd29f`. Esta revisión no duplica la verificación física de hash/archivo que coordina root. Los dos cierres figuran confirmados y error=null.
- Los desplazamientos se extraen **solo durante construcción**. Reapertura verifica definiciones y asignaciones, **no vuelve a analizar ni relee resultados**; no afirmar persistencia independiente de la respuesta analítica posterior por este recibo.

El script inicializa nu=.20 y E=25000000kN/m² en SetMPIsotropic; H=3m, FX=10kN, PZ=−1000kN, base con seis restricciones. Separa16 columnas por8m sin conexiones entre ellas. SetInsertionPoint se almacena en retorno_insercion pero no pasa por Check; en este recibo todos0, así que no explica el hallazgo. Para robustez futura debe tratarse como el resto de llamadas verificadas, sin alterar ahora el producto.

## Contraste con la sección de auditoría246

L nominal: dos rectángulos .40x.15 y .15x.40 menos solape .15x.15, sección bruta homogénea de aristas rectas.

| Magnitud | Analítica246 | GetSectProps en m |
|---|---|---|
| Área | .097500m² | .09749999999999999m² |
| Ix=Iy centroidales paralelos a brazos | .001230889423076923m⁴ | I22/I33≈.001230889423076923m⁴ |
| Ixy=∫(x−x̄)(y−ȳ)dA, brazos+x/+y | −.000576923076923077m⁴ | No está en la salida GetSectProps usada |
| Inercias principales | .000653966346153846/.001807812500m⁴ | Los I22/I33 devueltos **no** son esos valores |
| Centroide desde esquina exterior, brazos+x/+y | (.151923076923077,.151923076923077)m | No existe salida de centroide en ReadSection del ensayo |

A e inercias diagonales coinciden con la L real, y difieren del rectángulo.15x.40 (.060m²). Pero cuatro espejos de una L de lados iguales conservan exactamente esas diagonales: **su coincidencia no puede acreditar orientación de flexión ni el signo/efecto de Ixy**. Tampoco los ángulos0 de GetLocalAxes explican, sin evidencia adicional, una conversión a los ejes principales±45°.

La PZ centrada de C10 produce Uz=−.001230769230769m, igual a PH/(EA), con Ux=Uy=0; confirma la respuesta axial compatible con A. No confirma rigidez no simétrica.

## La prueba discriminante: C10 centrada con FX

Para L_M20_M30_C10, FX guardado:

`[Ux,Uy,Uz,Rx,Ry,Rz]=[.002968776496387488,0,0,0,.0014623571916805,0]`.

Tomando los parámetros del recibo, G=E/[2(1+nu)]=10416666.666667kN/m², I=.001230889423076923m⁴ y As2=.06536227616384951m²:

- Flexión **desacoplada**: FL³/(3EI)=**.002924714383361m**.
- Cortante: FL/(GAs2)=**.000044062113026487m**.
- Suma=**.002968776496387487m**, coincide con el Ux conservado a≈1e−18m.
- Giro flector FL²/(2EI)=**.0014623571916805rad**, coincide con Ry.

Por tanto el recibo se explica sin Ixy y con Uy=0. Usar solo la fórmula Euler-Bernoulli diagonal y atribuir su diferencia de44micras a Ixy también sería incorrecto: esa diferencia ya la explica el cortante nativo.

Para una viga homogénea no simétrica, con ejes globales paralelos a los brazos de la L y carga centrada sin excentricidad torsional, el bloque de flexión exige invertir la matriz de momentos centroidales. Definiendo D=IxIy−Ixy², los módulos Euler-Bernoulli son:

`|Ux|=FL³/(3E)·Ix/D`, `|Uy|=FL³/(3E)·|Ixy|/D`.

Con Ix=Iy de246 resultan **UxEB=.003748113692940m** y **|UyEB|=.001756756735291m**. El signo de Uy depende del espejo y de la orientación local/global; su módulo no es cero. Añadir una pequeña deformación diagonal de cortante no convierte ese desplazamiento transversal en cero. No hace falta suponer área cortante de la L para que el contraste de acoplamiento sea discriminante: la comparación anterior se refiere explícitamente al término de flexión.

Los C10 de los cuatro espejos conservan Uy=0 y esencialmente el mismo Ux. Los espejos individuales deberían cambiar el signo de la componente acoplada cuando la geometría se expresa en ejes paralelos a los brazos; el recibo no muestra esa señal. No se ha ensayado una sección de lados desiguales ni una rotación explícita de45° o una representación mediante inercias principales: este montaje no discrimina esos convenios.

## Por qué los Uy de C1/C10G no prueban Ixy

Se hizo una comprobación independiente con el modelo **diagonal** anterior, rigidez torsional GJ y transformación de inserción rígida; J es el valor **nativo guardado** .0006074298280700685m⁴, no una constante deducida de la figura.

De los desplazamientos bajo PZ, el mismo modelo permite inferir ex/ey mediante `Ux=P·ex·H²/(2EI)` y `Uy=P·ey·H²/(2EI)` en los signos del recibo. Esto es una **inferencia condicionada al modelo diagonal**, no una relectura directa del centroide. Da:

| Espejos(M2,M3) | ex/ey inferidos para C1, m |
|---|---|
| false,false | .151923077 / .248076923 |
| true,false | .151923077 / .151923077 |
| false,true | .248076923 / .248076923 |
| true,true | .248076923 / .151923077 |

Las magnitudes .151923 y .248077=.40−.151923 son compatibles con el centroide de la L dentro de la caja de.40 y sus espejos, medido desde la esquina de inserción correspondiente. Esto respalda que **los espejos cambian la relación sección–punto de inserción**. No fija por sí mismo el signo de Ixy en el operador flector.

C10/C11 dan ex=ey=0; C10G da ex=.100000000000000/ey=.050000000000000m, iguales a los offsets pedidos. Bajo FX:

`theta_z=F·ey·H/(GJ)`

`Ux=Ux_centrado+ey·theta_z`, `Uy=−ex·theta_z`.

Con esos términos se reproducen **los16 resultados FX**: residuos máximos≈2.2e−18m en Ux,8.2e−19m en Uy y2.7e−18rad en Rz. Por ejemplo C10G sin espejos produce theta_z=.000237064420194rad, Uy=−.0000237064420194m y Ux=.002980629717397m, iguales al recibo. La componente Uy surge de torsión por brazo ey y del desplazamiento del punto de lectura respecto del eje, **aunque Ixy sea cero en el modelo de flexión usado**.

C1 tiene brazos excéntricos distintos al cambiar espejos; por eso sus Uy cambian de magnitud. No debe presentarse esta variación como evidencia del cambio de signo de producto de inercia: en los cuatro C1 el signo de Uy es el mismo y Rz es distinto de cero. El centro de cortante físico de una L no se identifica con este ajuste; tampoco se ha probado alabeo o torsión no uniforme. Solo se demuestra que una transformación rígida con los offsets inferidos explica los resultados conservados.

## Alcance de lo acreditado y cierre necesario

**Acreditado por el recibo:** SetConcreteL/GetConcreteL funcionales en este ensayo; A e I22/I33 brutos de L correctos; almacenamiento de4espejos y16asignaciones; inserciones/cardinales/offsets y giros0 persistentes tras normalizar unidades; respuesta axial de A; desplazamientos coherentes con rigidez diagonal, cortante nativo y transformación rígida/torsión de offsets.

**No acreditado:** restitución del Ixy de la L, acoplamiento flector y su signo por espejo, orientación de ejes principales de rigidez, equivalencia C10/C11 fuera de este ensayo, centro de cortante/alabeo, correspondencia final de las dos L reales A/3 y A/1, o respuesta fiel del edificio. El hash declarado igual y la relectura de propiedades no convierten una respuesta sin acoplamiento en una prueba positiva de él.

Antes de usar el ensayo como validación de fidelidad C-1, hace falta una comparación mecánica que discrimine el bloque completo de flexión: referencia no simétrica centrada, fuerzas independientes X/Y, control de giros/excentricidad y relectura de ejes/propiedades de análisis. Alternativamente una representación por inercias principales y transformación explícita debe contrastarse con el mismo operador analítico. Esto describe el criterio de validación pendiente; **no se desarrolló ni ejecutó otro ensayo** y no presupone limitación general de ETABS.

Auxiliar `tmp/revision_nativa_c1_249/contraste_analitico.json`: términos Euler-Bernoulli/cortante, diferencias crudas de reapertura y comprobación diagonal+torsión por variante. Las diferencias crudas del JSON auxiliar deben interpretarse con las unidades de cada fase; este informe normaliza antes de dictaminar persistencia.
