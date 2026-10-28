# Vista declarada de superficies en un plano 3D

La superposición v0.3 permite contrastar visualmente paneles inclinados y verticales, además de horizontales, usando una base física **declarada** y tres correspondencias vértice→página. La geometría fuente sigue siendo v0.2. No se infieren ejes o escala desde imagen, no se reparan bases, no se asignan ejes locales ETABS y no se aprueba ingeniería. Los cuerpos/consultas v0.1 de muros y v0.2 de cota horizontal conservan sus formatos.

## Cuerpo y base exactos

Se reutilizan las rutas existentes. `POST /api/superposicion/crear` acepta los mismos campos exactos de superficies v0.2, con `version_contrato="0.3.0"`. El único esquema de plano admitido en esta modalidad es:

```json
{
  "tipo":"base_ortonormal_3d",
  "origen_m":[10,20,2],
  "eje_u":[1,0,0],
  "eje_v":[0,0.7071067811865476,0.7071067811865476]
}
```

`origen_m` son tres coordenadas físicas finitas en metros. `eje_u` y `eje_v` son tres componentes adimensionales de cada eje orientado. Los tres vectores deben declararse explícitamente; no hay campos opcionales, ni tolerancia física elegida por el usuario. La normal de vista es **U×V**: el orden y signo de los ejes determinan el sentido; invertirlos no se normaliza a una orientación preferida.

Los campos raíz exactos son `caso`, `expediente_sha256`, `geometria`, `huella_geometria`, `sha256_geometria`, `archivo`, `pagina`, `version_contrato`, `plano`, `superficies`, `anclas`, `revisor_declarado`, `fecha`, `motivo`, `confirmacion_explicita`. No hay `nivel` ni Story nuevo. `superficies` sigue siendo una lista explícita no vacía de IDs distintos.

Cada ancla usa exactamente `vertice` y `punto=[u,v]` normalizado de página. Se requieren tres vértices distintos pertenecientes a las superficies seleccionadas y tres puntos distintos dentro de la página, bien separados. Un vértice de otra superficie no seleccionada se rechaza, aunque pertenezca a la misma geometría o plano; los IDs no se interpretan como nodos históricos.

## Criterio numérico reproducible

Se exige `abs(norm(U)-1)<=1e-12`, `abs(norm(V)-1)<=1e-12` y `abs(dot(U,V))<=1e-12`. Se rechazan ejes nulos, no finitos, no unitarios o no ortogonales; no se normalizan ni aplica Gram-Schmidt. Esta banda es consistencia de cálculo binary64, **no tolerancia de ingeniería**.

Para cada contorno, `escala` es la máxima componente absoluta de desplazamiento desde su primer vértice, en metros. `magnitud` es la mayor coordenada absoluta entre sus vértices y el origen declarado. La banda computacional es:

```text
tolerancia_computacional_m = max(1e-12 * escala, 64 * ulp(magnitud))
```

Si la escala no es positiva o la banda no es finita, se rechaza. Si `tolerancia/escala>1e-6`, se rechaza la referencia numéricamente inestable. Para todos los vértices debe cumplirse `abs(dot(X-origen,U×V))<=tolerancia`. Fuera de esa condición, el panel no pertenece al plano declarado y **no se aplana**. La UI previsualiza con el mismo criterio; la comprobación autoritativa es la del servidor.

Las coordenadas de vista son `U_m=dot(X-origen,U)` y `V_m=dot(X-origen,V)`. Se conservan los XYZ originales y la geometría fuente sin desplazarlos, redondearlos ni sustituirlos por la proyección. La afín exacta de tres anclas actúa después sobre esos UV físicos y los vincula con la página normalizada. Un resultado no representable o una afín inestable se rechazan.

Este procedimiento determina si la proyección puede calcularse de manera consistente; no establece que el plano, sus ejes, dimensiones o fuentes sean técnicamente apropiados para el edificio.

## Persistencia, reproducción y vigencia

El registro usa `version="0.3.0"` y conserva el plano exacto, selección, geometría v0.2/huella/SHA, original/página/hash de vista previa y declaración del operador. Agrega:

```text
huella_plano = SHA256(serialización JSON canónica persistida del objeto plano)
base_vista = {
  normal_u_cruz_v: [nx,ny,nz],
  epsilon_ortonormalidad: 1e-12,
  criterios_coplanaridad: {
    superficie_id: {escala_contorno_m: ..., tolerancia_computacional_m: ...}
  }
}
```

La serialización usada por el servicio ordena claves, usa UTF-8, indentación de dos espacios y salto final, y rechaza NaN/Infinity. No se infiere equivalencia entre bases distintas para conservar una huella anterior.

Cada consulta vuelve a validar la geometría, reconstruye la base/coplananidad/UV/anclas/afín y compara la huella y los derivados registrados. La selección, el plano y las referencias no se toman de memoria de la interfaz. Tras renderizar la página se revalida la geometría y los bytes del registro. La fuente original y su vista previa deben seguir coincidiendo. Un hash de paquete rehecho no evita estos contrastes semánticos; esto no es una firma ni autentica al declarante.

La consulta devuelve `version_contrato="0.3.0"`, `plano`, `huella_plano`, `base_vista` y las superficies con `vertices_plano_m` adicionales. Conserva XYZ, área geométrica y procedencia. La proyección de cada vértice queda en `proyeccion`; los puntos fuera de página se declaran y no se recortan. `nivel=null` sigue siendo compatibilidad de lectura, no un piso ficticio. El historial muestra la base 3D declarada.

## Interfaz e integración

Controles a montar por el coordinador en `index.html`:

- Opción `superficies_plano3d` en `supTipo`.
- `supOrigen3d`: texto «Origen físico XYZ (m)».
- `supEjeU3d`: texto «Eje U declarado (unitario)».
- `supEjeV3d`: texto «Eje V declarado (unitario)».

Cada campo recibe una terna numérica separada por comas, inicialmente vacía. La nota visible debe explicar «U×V define el sentido de vista; no son ejes locales ETABS». La modalidad deshabilita cota horizontal/nivel y habilita estas tres entradas. No se completa una base desde el panel ni a partir de la página.

Cambiar la base o superficie elimina la correspondencia abierta, invalida respuestas de imagen pendientes y consume la confirmación. La UI muestra el contorno en UV metros antes de la calibración, con aviso de falta de alineación; luego muestra el original únicamente con una correspondencia registrada vigente. Reabrir un registro restaura base y selección exactas; se comparan sus componentes, sin depender del orden textual de claves JSON.

## Evidencia y límites

Focal ejecutado con TEMP/TMP del proyecto: `python -m unittest tests.test_superposicion_plano3d tests.test_superposicion_superficies tests.test_revision_superposicion`: **20 pruebas correctas, 8.795 s**. Casos nuevos: panel inclinado y vertical, base orientada, área/XYZ/UV/proyección, recreación del servicio desde archivos, ejes inválidos, miembro fuera del plano, ancla de otra superficie, huella/base/afín alteradas con hash rehecho y mutación de geometría tras render. La batería DOM preexistente pasó **7 casos**; los nuevos casos DOM y QA navegador corresponden a la integración del coordinador y no se presuponen acreditados.

Datos sintéticos y página local, sin proveedor real, red ni ETABS. Esta capacidad visual cubre un plano explícito por registro; no es reconstrucción automática de cualquier vista, perspectiva fotográfica o proyección no afín. Tampoco prueba representación física de aligerados, mallado/conectividad, cargas, rigidez, cisterna/tanque o seguridad estructural; esas puertas siguen abiertas en el proyecto.
