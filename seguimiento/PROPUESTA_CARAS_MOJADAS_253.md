# Propuesta253: cara mojada a shell medio con fuerza y momento conservados

2026-10-22. **Propuesta matemático-contractual aislada**, no feature integrada ni prueba nativa. Insumos09E copiados desde `tmp/revision_geo09e_252`; códigos actuales se copiaron únicamente para lectura del contrato en `tmp/propuesta_caras_mojadas_253/contrato_actual_lectura`. No se importó producto, ejecutó malla/plan, alteró configuración ni llamó ETABS/API/red/GUI. El sistema estructural y la masa ensamblada quedan fuera del encargo.

## 1. Geometría física y carga: distinguirlas de la superficie resistente

Sean Xm0/Xm1 y Ym0/Ym1 los ejes de los muros; Zf/Zt, los planos medios del fondo/tapa. Con espesores positivos t:

```text
x0 = Xm0 + tx0/2       x1 = Xm1 - tx1/2       Lx = x1-x0
y0 = Ym0 + ty0/2       y1 = Ym1 - ty1/2       Ly = y1-y0
a  = Zf + tf/2        b  = Zt - tt/2
H: nivel libre declarado, a <= H <= b
h = H-a               V = Lx*Ly*h            W = gamma*V
xc=(x0+x1)/2          yc=(y0+y1)/2            zcp=a+h/3
```

La caja rectangular es una hipótesis geométrica explícita. No permite inferir que un depósito real tenga ese volumen, que su llenado sea operativo o que las posiciones ajustadas de09E hayan quedado resueltas. Se preserva la distinción de252 entre fuente, aproximación de apoyos y conexión de modelo.

La presión física es **p(z)=gamma(H-z)** solo sobre las caras mojadas: fondo en z=a y paredes entre a yH. No actúa sobre el hormigón bajo el fondo ni sobre las bandas tangenciales correspondientes a espesores de muros transversales. La tapa por encima del nivel libre no recibe esta presión. Para vacíoH=a, fuerza/momento0 y sin centro de presión ficticio.

La representación en shell medio conserva todo el material; se modifica **el dominio de carga**, no la geometría estructural para hacerla coincidir con el líquido.

## 2. Transferencia distribuida y par de offset

Para cada punto físico rw, su destino rm en el shell y dF=p n dA:

```text
F_destino = integral(dF)
C_offset = integral((rw-rm) x dF)
M_fisico(O) = integral((rw-O) x dF)
M_destino(O) = integral((rm-O) x dF) + C_offset
```

Por tanto M_destino=M_fisico para cualquier origenO. Si el offset es constante, C_offset=(rw-rm)×F. Con offset variable debe integrarse; no usar el promedio geométrico del offset sin ponderación por presión.

**En esta caja plana y con presión puramente normal, la proyección a shell medio es por la normal y C_offset=0 exactamente.** La diferencia cara→medio de fondo es vertical y su fuerza es vertical; en cada pared es normal al muro y paralela a la fuerza. No corresponde inventar un par adicional solo por existir semiespesor. Esto no elimina la obligación de recortar la carga a su dominio físico.

Si se coloca la resultante en otro nudo/centroide con desplazamiento tangencial, sí aparece par. Ejemplo independiente: rw=(1,2,3), rm=(0,0,0), F=(0,0,−10)kN exige C=(−20,+10,0)kNm. Sin ese par se conserva la fuerza pero no el momento. También puede representarse C mediante un sistema de pares de fuerzas con suma0 y suma(r×f)=C sobre puntos declarados apropiados; no crear puntos/constraints ni elegir palancas arbitrarias automáticamente.

### Dominios exactos proyectados

| Cara | Plano del shell | Dominio de carga en el shell | Presión/vector |
| --- | --- | --- | --- |
| Fondo | z=Zf | x0≤x≤x1, y0≤y≤y1 | gamma*h hacia−Z; constante, evaluada con cara físicaz=a |
| x0 | x=Xm0 | y0≤y≤y1, a≤z≤H | gamma(H−z) hacia−X |
| x1 | x=Xm1 | y0≤y≤y1, a≤z≤H | gamma(H−z) hacia+X |
| y0 | y=Ym0 | x0≤x≤x1, a≤z≤H | gamma(H−z) hacia−Y |
| y1 | y=Ym1 | x0≤x≤x1, a≤z≤H | gamma(H−z) hacia+Y |

Fuera del dominio la carga es0, **pero el shell/material permanece**. En las paredes no se cambia gamma niH; se retira la banda inferiorZf…a y las bandas laterales de hormigón. En el fondo no se utiliza gamma(H−Zf), porque la presión se calcula en la cara superior físicaa.

## 3. Resultantes y momentos analíticos de control

Para h>0, las resultantes por cara son:

```text
Ffondo = (0,0,-W)               rfondo=(xc,yc,a)
Fx0 = (-gamma*Ly*h²/2,0,0)      rx0=(x0,yc,zcp)
Fx1 = (+gamma*Ly*h²/2,0,0)      rx1=(x1,yc,zcp)
Fy0 = (0,-gamma*Lx*h²/2,0)      ry0=(xc,y0,zcp)
Fy1 = (0,+gamma*Lx*h²/2,0)      ry1=(xc,y1,zcp)
M_cara(O)=(r_cara-O) x F_cara
```

Las paredes opuestas cancelan fuerza y momento entre sí, y la caja completa equivale estáticamente al peso del volumen claro:

```text
Ftotal=(0,0,-W)
Mtotal(O)=(-(yc-Oy)*W, +(xc-Ox)*W, 0)
```

Se exige controlar **cada cara y el conjunto**. Un cierre global podría ocultar errores compensados de paredes. Estas igualdades son de estática de carga, no de masa ensamblada, respuesta modal o hidrodinámica.

### Valores09E condicionados al escenario y geometría congelados

Gamma10kN/m³; origen globalO=(0,0,0). De252: espesores y planos medios producen claros distintos de su área entre ejes. El delta milimétrico de claro cisterna respecto2.00×2.15 es redondeo de esa representación. No se ha aprobado ninguna dimensión, nivel operativo ni transformación de apoyos.

| Control | Cisterna09E | Tanque09E, alternativaE03-apoyos |
| --- | ---: | ---: |
| x0…x1(m) |15.013…17.015|11.435…13.648|
| y0…y1(m) |2.549…4.698|3.218…4.918|
| a / H(m) |−2.400 /−.180|12.600 /13.700|
| h(m) |2.220|1.100|
| Vclaro(m³) |9.55110156|4.13831|
| p_fondo(kPa) |22.2|11.0|
| Fx por pared, magnitud(kN) |52.955658|10.285|
| Fy por pared, magnitud(kN) |49.333284|13.38865|
| zcp de paredes(m) |−1.660|12.966666667|
| Ftotal(kN) |(0,0,−95.5110156)|(0,0,−41.3831)|
| Mtotal(kNm) |(−346.084165027,1529.513403818,0)|(−168.3464508,519.00614865,0)|

`VALORES_09E.json` contiene F/M por cara, centro de presión, par0 y equivalentes nodales abstractos. Es un resultado algebraico, no archivo de plan ni datos aplicados al motor.

**No sirve una escala global de presión.**252 cuantificó valores de fondo entre ejes118.6395336/55.0164kN. Corregirlos con un factor no corrige simultáneamente áreas tangenciales, profundidad de las paredes y centros de presión. Por ejemplo, cisterna tiene centro físicoX16.014 frente al centro de fondo medioX16.0265: una carga uniforme sobre todo ese fondo, aunque se escale para darW95.5110156, altera My en≈1.193887695kNm. En paredes, la altura incorrecta2.32 en vez2.22 desplaza zcp de−1.66 a−1.726666667. No basta conservar una sola fuerza vertical total.

## 4. Dos opciones contractuales defendibles, pendientes de integrar

### A. Subdominio interior / recesión de carga sobre shell conservado

Conservar las superficies/materiales originales; distinguir un parche mojado proyectado y sus bandas sin presión. Partir/identificar el dominio de carga y exigir que ninguna pieza cargada atraviese su borde, a oH. En cada parche de pared se conserva p(z) afín; en el fondo p es la constante física gamma*h. Añadir el par por offset general si la transferencia tiene componente tangencial; para esta caja por proyección normal,0.

La partición completa debe conservar área/peso/rigidez de la superficie estructural original, incluidas bandas sin carga; **no crear shells duplicados ni retirar hormigón para representar agua**. La geometría de carga puede ser auxiliar, sin masa/material/rigidez propios, pero el contrato actual no la distingue: requiere un modo/parche explícito, no editar el significado del host silenciosamente.

### B. Fuerzas nodales estáticamente equivalentes sobre conectividad existente

Para funciones de interpolación traslacionalNi de la superficie destino:

```text
fi = integral_D(Ni(rm) * p(rw) * n dA)
ci = integral_D(Ni(rm) * ((rw-rm) x p(rw)n) dA)   [si se admite ese reparto del par]
```

Con sumaNi=1 y reproducción de coordenadas sumaNi*ri=rm, las fuerzas conservan F y el momento de la carga proyectada; los pares agregan el offset general. Para caja normal,ci=0. Las fuerzas van sobre los **nodos existentes** del elemento destino, integrando solo la intersección con el parche mojado; no concentrar todo en un apoyo ni repartir por igual sin verificar momento.

Para triángulo matemáticoT3 completamente cubierto y presión afín con valorespi:

```text
fi = (A/12)*(2*pi+pj+pk)*n
```

Para recorte parcial, la integral se calcula sobreD sin cambiar Ni del triángulo destino. Si se subdivide analíticamente el dominio en subtriángulos con valoresNk ypk en sus tres vértices:

```text
integral_subtri(Ni*p) = (A/12) * ((sum_k Ni_k)*(sum_k p_k) + sum_k Ni_k*p_k)
```

La prueba aisladaQ4 usa Gauss2×2 exacto para Ni bilineal y presión afín sobre rectángulo mojado. Sus cuatro esquinas son un **elemento matemático abstracto**, no nuevos nudos de09E: el integrador debe usar la conectividad real de sus piezas. Conservar F/M no prueba equivalencia de tensiones, deformaciones ni la interpolación de flexión del elemento nativo; la palabra «consistente» se refiere aquí al espacio traslacional elegido, sin afirmar consistencia con todos los grados de libertad de un shellETABS.

## 5. Qué soporta hoy el contrato/API por lectura

Fuentes actuales congeladas para lectura, con hashes en `tmp/propuesta_caras_mojadas_253/manifest.json`. No se comprobó capacidad nativa mediante ejecución.

| Capacidad observada en código | Disponible / límite |
| --- | --- |
| Tabla `Area Load Assignments - Non-uniform`, columnas UniqueName/LoadPattern/Dir/A/B/C/D/Restriction | Transporta presión afín en una **pieza completa** y restricción de signo. No tiene en el contrato actual polígono de carga interior, cota inferiora ni offset de aplicación. El corteH ya es requisito; no resuelve por sí solo las bandas de semiespesor. |
| `acciones_liquidos` y `liquidos_malla` | La superficie seleccionada es la de geometría/malla resistente; reproducen su contorno menos huecos. No aceptan una cara física distinta y un mapa conservativo a host medio. Sus fuentes/huellas y pruebas deben ampliarse para conservar esa distinción. |
| Parches como piezas con carga0/física | La tabla podría expresar ecuaciones sobre piezas que ya cubran exactamente esos parches, pero **no hay hoy una función de contrato que recorte esos dominios y los vincule conservativamente**. No basta usar Restriction como recorte arbitrarioXYZ. No se ejecutó ni propone ejecutar malla aquí. |
| `cPointObj.SetLoadForce` en lista blanca | El método recibe un array Value. El generador actual para carga puntual construye `[Fx,Fy,Fz,0,0,0]`; el modelo exige exactamente3 componentes traslacionales. Los momentos nodales no están habilitados como entrada actual. Eso no prueba que el motor no los soporte: distingue contrato actual de capacidad por verificar. |
| Cargas nodales equivalentes | Hay transporte genérico de fuerzas puntuales y su relectura, pero **el patrón líquido0.5 debe estar dedicado** y el validador rechaza SetLoadForce/Uniform/Distributed añadidos a ese mismo patrón. La ruta líquida vigente no se puede cambiar a nodales por un atajo manteniendo las mismas afirmaciones. |
| Pares de fuerzas / momentos por offset | Exigen destino, fuentes, DOF/conectividad y comprobación de F/M explícitos. No existe aquí un modo de transferencia de cara mojada que los genere y relea. En caja plana no se necesitan pares normales, pero sí el dominio correcto. |

Propuesta de entrada futura, **no implementada**: por cara, sourceSHA/estado, contorno físico3D y normal, ley de presión, host/piezas destino, mapa de proyección, dominio proyectado, método A/B, par calculado, F/M esperados por cara/origen y cobertura sin duplicación. Rechazar caras sin mapeo, dominios fuera del host, piezas cargadas dos veces, normales/volúmenes incompatibles y modos mezclados. Mantener fuentes geométricas y esquema/huellas separados. No inferir el método, no sustituir geometría para lograr conformidad y no aplicar simultáneamente presión y su equivalente nodal.

## 6. Pruebas analíticas y límites

```powershell
python -B -m unittest discover -s tmp/propuesta_caras_mojadas_253 -p test_transferencia_rectangular.py -v
```

**9 pruebas OK**, sin módulos del producto: prisma independiente2×2.15×h2.22 (V9.546, W95.46) con oráculo racional por cara; vacío; llenados parciales/origen desplazado; casos09E y rechazo de escala global; dominio recedido conservando host; par0 normal y par tangencial no nulo con origen arbitrario; pared sin carga fuera de[a,H]; dominios inválidos; fórmulaT3 contra integrales polinómicas racionales independientes. Fuerza y momento se contrastan por cara y globalmente. La admisión del nivel superior usa solo margen aritmético1e−12m por semiespesores decimales, sin recortar ni reajustar niveles de entrada.

No se generó la malla real, no se verificó interpolación nativa ni se ensayó transporte/relectura/aplicación de estos parches o equivalentes. No se arreglan en esta propuesta posiciones/alternativas de apoyo del tanque, fundaciones, hipótesis de sección, sistema estructural ni masa ensamblada. Esta propuesta permite revisar el contrato con Claude antes de reservar archivos de producto; no autoriza integración automática ni una nueva ejecución del modelo.
