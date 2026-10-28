# Auditoría C-1 en L y capacidades nativas - 246

Fecha: 2026-10-22. Solo lectura focal de originales, configuración/geometría 09B y metadatos .NET locales. Sin instanciar ETABS, sin llamadas COM, sin API LLM, sin credenciales ni Computer Use. No se ejecutaron scripts de producto, planes, ensayos ni análisis. No se modificaron archivos de Claude.

## Conclusión para la continuación 10

**C-1 es una sección en L de envolvente .40 x .40 m y dos brazos de .15 m, no una sección rectangular .15 x .40 equivalente.** El detalle acota independientemente ambas dimensiones exteriores y ambos espesores; la planta repite el contorno de seis lados y la etiqueta C-1 en dos esquinas. Las dos instancias están reflejadas en Y. La configuración 09B asigna a ambas `COL-1-X` rectangular, y además sus puntos de frame no son los centroides de la L real.

La DLL local **sí expone SetConcreteL y GetConcreteL**, además de SetAngle/SetAngle_1, SetGeneral/GetGeneral y GetSectProps. La existencia y firmas están confirmadas por reflexión; no se ha probado su ejecución ni interpretado por intuición el convenio geométrico de T3/T2/Tf/TwC/TwT, espejos e inserción. Es una vía nativa disponible para preservar la forma, pendiente de vincular parámetros y ejes según documentación y relectura posterior por el dueño de implementación.

## Evidencia geométrica y ubicación

Fuente E01/L0001: `planos_muestra/proyecto_pueblo_libre/Estructuras_Pueblo Libre1-Cimentación.pdf`, página 1, SHA-256 ff669f23633b7c355bc7d89ea60809856df7e29a5b4019204307f7deef9ba8f5. Rotación PDF **0°**, tamaño 3370 x 2384 pt; las coordenadas siguientes son visuales, origen arriba-izquierda, X derecha/Y abajo. No rotarlas.

- Detalle C-1: región `(340,1300)-(700,1630)` pt. Se lee `.40` exterior horizontal, `.40` exterior vertical, `.15` del brazo horizontal y `.15` del vertical. La silueta visible es una L con esquina entrante; también se lee 8 barras de 1/2 pulgada. Estos datos se observan en el detalle, independientemente del nombre C-1.
- Instancia superior, A/3 = `L0001-E1`: región `(325,205)-(505,390)` pt; brazos hacia +X y +Y. El contorno de seis lados y rótulo C-1 corroboran la forma del detalle.
- Instancia inferior, A/1 = `L0001-E27`: región `(325,925)-(505,1115)` pt; brazos hacia +X y -Y. El rótulo y contorno reflejado corroboran que no debe reutilizarse la misma orientación sin transformación.

Vértices del contorno, pt (último cierra con primero):

| Instancia | Secuencia |
|---|---|
| E1 superior | (364.20,260.48); (396.00,260.48); (396.00,272.36); (376.08,272.36); (376.08,292.28); (364.20,292.28) |
| E27 inferior | (364.20,1055.12); (396.00,1055.12); (396.00,1043.12); (376.08,1043.12); (376.08,1023.32); (364.20,1023.32) |

Calibración compatible con inventario 09: `x=(xPDF-364.2)*.012595`; `y=(yPDF-260.48)*.012581`. Las envolventes vectoriales derivan aproximadamente .401 x .400 m, espesores próximos a .15; esto corrobora las cotas nominales del detalle. Para propiedades de sección se usa la geometría nominal **acotada**, no las pequeñas desviaciones de dibujo/calibración. La correspondencia con arquitectura 3↔A continúa siendo hipótesis de piloto; la ubicación A/3 versus A/1 aquí se expresa en ejes estructurales y no depende de resolverla.

## Propiedades realmente deducibles

Idealización geométrica explícita: unión de dos rectángulos .40 x .15 y .15 x .40 menos el cuadrado común .15 x .15, esquinas rectas, sección bruta homogénea, sin descontar acero ni fisuración ni radios no acotados. Coordenadas locales de la L superior: `(0,0),(.40,0),(.40,.15),(.15,.15),(.15,.40),(0,.40)`.

| Propiedad | L nominal bruta |
|---|---|
| Área A | .097500 m² |
| Centroide desde esquina exterior, brazos positivos | x̄ = ȳ = .151923077 m |
| Ix = ∫(y-ȳ)²dA | .001230889423 m⁴ |
| Iy = ∫(x-x̄)²dA | .001230889423 m⁴ |
| Ixy = ∫(x-x̄)(y-ȳ)dA | -.000576923077 m⁴, para brazos +X/+Y |
| Momentos principales | .000653966346 y .001807812500 m⁴ |

La sección tiene simetría respecto de la bisectriz, con ejes principales a ±45° de los lados. La reflexión inferior conserva A/Ix/Iy/momentos principales y cambia el signo de Ixy en los ejes globales del plano. La convención de signo de Ixy aquí es la integral geométrica escrita, no una presunta convención interna de ETABS.

Las fórmulas verificadas son A=2bt-t² y x̄=ȳ=[bt(b/2)+bt(t/2)-t²(t/2)]/A, con b=.40, t=.15; los momentos proceden de integrar los dos rectángulos y restar su solape. Resultado reproducible en `tmp/auditoria_c1_246/propiedades_geometricas.json`.

**No se deducen solo de estas cotas** la constante de torsión de Saint-Venant, áreas efectivas de cortante, centro de cortante, propiedades fisuradas, rigidez efectiva con acero o factores de modificación. Ix+Iy es momento polar geométrico, no sustituye la constante torsional. No se propone llenar SetGeneral con valores arbitrarios de estos campos.

## Diferencia respecto de 09B

Fuentes consultadas: `seguimiento/claude_ruta/configuracion_09b.py`, `geometria_09b.py`, `GEOMETRIA_09B.json`, `INFORME_09.md` §6 y `tmp/ruta201/configuracion09b.json`.

- `COL_DIM['C-1']=(.15,.40)` y `seccion_columna` producen `COL-1-X`, `frame_rectangular`, ancho .15/alto .40, para ambas L porque sus cajas casi cuadradas tienen dx ligeramente mayor que dy. Esta comparación no codifica la orientación de una L.
- `SECCION_COLUMNA` de geometría también contiene esa simplificación. El punto de columna se elige entre líneas dentro de la caja, más cerca de su centro; el código usa **centro de caja**, no centroide de área de la L.
- Los puntos guardados de E1/E27 son respectivamente `(.075,.094)` y `(.075,9.943)` m, para cada cadena vertical N0–N4. La esquina exterior inferior del dibujo está aproximadamente en y=9.997 m. Con dimensión nominal, los centroides ideales serían aproximadamente `(.151923,.151923)` y `(.151923,9.845077)` m. Las diferencias punto actual menos centroide son aproximadamente `(-.076923,-.057923)` y `(-.076923,+.097923)` m; son diagnóstico geométrico, **no una orden de mover nodos**: antes hay que decidir inserción/excentricidades y conservar las conexiones de losas/muros.

Comparación bruta con el rectángulo .15 x .40:

| Magnitud | Rectángulo | L |
|---|---|---|
| Área | .060000 m² | .097500 m² |
| Momentos centroidales según sus lados | .000112500 / .000800000 m⁴ | .001230889 / .001230889 m⁴, con Ixy distinto de cero |
| Momentos principales | .000112500 / .000800000 m⁴ | .000653966 / .001807813 m⁴ |

El rectángulo pierde **38.46% del área bruta** de la L. Para igual longitud y densidad, también representa esa fracción menos de peso/masa propios de esa columna, antes de cargas y modificadores. Altera inercias y orientación/coupling de flexión; su producto de inercia en ejes propios es cero. No se infiere de ello un porcentaje de cambio de deriva, cortante o comportamiento del edificio: eso exige el modelo completo y análisis.

## Reflexión de la DLL instalada: métodos confirmados

Archivo: `C:/Program Files/Computers and Structures/ETABS 21/ETABSv1.dll`.

- SHA-256: `6B9170EF7100B99C42F387AB8FDC7E83939027AD3452763C0BF329757A9608C0`.
- Assembly: `ETABSv1, Version=1.0.0.0, Culture=neutral, PublicKeyToken=453d728ef24c6f5e`.
- FileVersion/ProductVersion: **1.29.0.0**. Es la versión de la DLL; no atribuirla a versión de programa ETABS.
- Se usó Windows PowerShell .NET Framework con `ReflectionOnlyLoadFrom`, `GetType`, `GetMethods`, `GetParameters`. El intento inicial en PowerShell moderno no admitía ReflectionOnly; el registro definitivo procede del proceso Windows PowerShell. No se ejecutó ningún constructor/método de ETABS ni se obtuvo una instancia COM.

Firmas confirmadas en `ETABSv1.cPropFrame` (retorno **Int32** en todos los casos; `ref` indica ByRef real de metadatos):

```csharp
int SetConcreteL(string Name, string MatProp,
  double T3, double T2, double Tf, double TwC, double TwT,
  bool MirrorAbout2, bool MirrorAbout3,
  int Color=-1, string Notes="", string GUID="");

int GetConcreteL(string Name, ref string FileName, ref string MatProp,
  ref double T3, ref double T2, ref double Tf, ref double TwC, ref double TwT,
  ref bool MirrorAbout2, ref bool MirrorAbout3,
  ref int Color, ref string Notes, ref string GUID);

int SetAngle(string Name, string MatProp,
  double T3, double T2, double Tf, double Tw,
  int Color=-1, string Notes="", string GUID="");
int SetAngle_1(string Name, string MatProp,
  double T3, double T2, double Tf, double Tw, double FilletRadius,
  int Color=-1, string Notes="", string GUID="");

int SetGeneral(string Name, string MatProp,
  double T3, double T2, double Area, double As2, double As3, double Torsion,
  double I22, double I33, double S22, double S33, double Z22, double Z33,
  double R22, double R33,
  int Color=-1, string Notes="", string GUID="");

int GetGeneral(string Name, ref string FileName, ref string MatProp,
  ref double T3, ref double T2, ref double Area, ref double As2, ref double As3,
  ref double Torsion, ref double I22, ref double I33, ref double S22,
  ref double S33, ref double Z22, ref double Z33, ref double R22, ref double R33,
  ref int Color, ref string Notes, ref string GUID);

int GetSectProps(string Name,
  ref double Area, ref double As2, ref double As3, ref double Torsion,
  ref double I22, ref double I33, ref double S22, ref double S33,
  ref double Z22, ref double Z33, ref double R22, ref double R33);
```

GetAngle y GetAngle_1 también existen con FileName/MatProp/dimensiones por referencia; la variante `_1` añade FilletRadius. Las firmas completas y opcionalidad están en `tmp/auditoria_c1_246/firmas_reflection.txt`. SetRectangle/GetRectangle también existen. No se confunde `SetConcreteL` con `SetAngle`: son métodos distintos; el nombre de un método y tipos de parámetros no establecen por sí solos semántica de sección/rebar/convenciones.

Complementos **confirmados, no invocados**, en `cFrameObj`: SetLocalAxes/GetLocalAxes y SetInsertionPoint/GetInsertionPoint. En cPropFrame: SetRebarColumn/GetRebarColumn y SetModifiers/GetModifiers. Sus parámetros exactos están en `firmas_ejes_insercion.txt`. En particular SetInsertionPoint recibe CardinalPoint, Mirror2, StiffTransform, dos arrays Offset1/Offset2 por referencia, CSys opcional="Local" e ItemType opcional; no contiene un espejo denominado MirrorAbout3. **No intercambiar esos parámetros con los espejos de SetConcreteL.**

No hay parámetro I23 en la firma SetGeneral inspeccionada. Por tanto no basta cargar Ix/Iy de la L en ejes paralelos a los brazos y suponer que se preserva el producto de inercia; una representación general requiere documentar sus ejes principales y todos los demás términos. La candidata nativa directa es SetConcreteL, con su relectura correspondiente, antes de recurrir a una propiedad general incompleta.

## Incertidumbres y siguiente paso concreto

1. Dimensiones/forma/ubicaciones de ambas L: resueltas por detalle acotado y contorno en planta, confianza alta. No falta pedir una sección al usuario.
2. Conversión a parámetros SetConcreteL y correspondencia local/global: requiere documentación de los parámetros y espejos, seguida de verificación posterior por lectura nativa; la sola reflexión no autoriza asignar T3/T2/Tf/TwC/TwT por conjetura.
3. Inserción y excentricidades respecto de puntos actuales: definición de implementación necesaria para preservar huella y conectividad. No desplazar automáticamente frames al centroide sin revisar muros/losas.
4. Armado: detalle visible 8 barras de1/2, pero esta auditoría geométrica no traduce a un patrón rectangular de SetRebarColumn ni verifica diseño; el patrón debe representar la L si se incluye.
5. Continuidad vertical: 09B la extiende por N0–N4; E01 es cimentación y sección. No se declara certificada una continuidad/armado vertical completo solo con esta lámina.

Archivos auxiliares adicionales: C1_contornos.json (seis vértices de cada instancia en PDF/m), propiedades_geometricas.json, C1_detalle.png, C1_superior.png y C1_inferior.png. **Ninguna salida modifica el inventario o sustituye decisiones de ingeniería.**
