# Revisión 249: contenido líquido, presión y fuente de masa

Fecha: 2026-10-22. Fuente de producto: snapshot congelado `tmp/revision_codex_246`. Solo lectura de producto/test/configuración; único archivo escrito: este informe. Sin GUI, API, ETABS, red, plan generado ni nueva corrida de 206/210r3.

## Dictamen

**La declaración hidrostática 0.5 no asegura que se incluya el 100% del contenido como masa.** Tampoco lo promete: `liquidos_malla.py:117` devuelve `no_afirma` con `masa_del_liquido`, y `operaciones_etabs.py:1574` añade el pendiente «Hidrodinámica, geotecnia, flotación y masa del líquido no se modelan ni afirman».

La presión estática, el peso de los elementos sólidos y la fuente de masa son recorridos diferentes. Hay guardas útiles contra ciertas duplicaciones, pero **no existe enlace semántico por depósito entre inventario/volumen, peso de contenido, patrones de presión y masa objetivo**. Esto es una brecha respecto del objetivo de integración «contenido 100%», no una contradicción del alcance hidrostático declarado por el producto actual.

## Recorrido y guardas existentes

| Capa congelada | Qué transporta/comprueba | Qué no demuestra |
| --- | --- | --- |
| `acciones_liquidos.py:77–131` | Declaración exacta con id, nivel libre, peso específico, origen de momentos, selección de superficies y sentido de normal; fuentes revisadas y SHA de contenido/geométría. | No exige volumen, capacidad, recinto cerrado, fondo completo ni fracción de contenido para masa. El campo `fuentes[].contenido` es contenido documental JSON, no inventario físico del depósito. |
| `acciones_liquidos.py:234–269` | Integra presión sobre cada anfitriona menos aberturas y produce fuerza/momento. | La integral sobre una pared seleccionada no determina el peso total del agua ni la masa del recipiente completo. La declaración puede seleccionar solo una pared. |
| `cargas_liquidos_etabs.py:15–45` | `p = gamma*max(0,h-z)`; componentes globales X/Y y Gravity según normal explícita; coeficientes y restricción de signo para tabla no uniforme. | No crea masa explícita ni peso volumétrico de contenido. No verifica que una selección de caras cierre el volumen. |
| `modelo_estructural.py:1055–1117` | Aplicabilidad presente/ausente/insuficiente; presente requiere declaraciones. Patrón líquido dedicado con multiplicador de peso propio 0; no admite otras cargas declaradas en ese patrón, patrón compartido ni superficie repetida entre declaraciones. Exige cortes de nivel libre interiores. | No exige que el patrón aparezca en `masa.factores_patrones`, ni fija su factor, ni impide que otro patrón de distinto nombre represente otra vez el mismo peso físico. |
| `liquidos_malla.py:55–120` | Correspondencia a piezas; prohíbe pieza/patrón repetidos, triángulo que cruce el nivel libre y filas objeto/patrón/dirección duplicadas; conserva fuerzas/momentos de cada host. | La conservación es de la presión seleccionada, no del inventario volumétrico ni de una suma global de masas. |
| `modelo_estructural.py:325–347` | Fuente de masa por patrones o explícita, única y no vacía; referencias a patrones; no permite simultáneamente patrones y masas puntuales. Rechaza `incluir_masa_propia=true` con patrón ponderado que también incluye peso propio. | No clasifica la contribución física de cada carga; no vincula factores con tipo de depósito/contenido; no detecta dos patrones distintos que modelen la misma contribución. |
| `modelo_estructural.py:665–667`; `operaciones_etabs.py:534–543` | Masa puntual escalar explícita no habilitada en el recorrido de superficies y no soportada por el adaptador; gravedad de configuración debe concordar con gravedad del programa declarada por el usuario. | No se puede cerrar el pendiente introduciendo masas puntuales como si la ruta ya las soportara; tampoco se observa/fija automáticamente la gravedad interna del programa. |
| `operaciones_etabs.py:828–832` | `SetMassSource_1`: IncludeElements según `incluir_masa_propia`, IncludeAddedMass=False, IncludeLoads=True, lista/factores exactamente desde configuración. | No calcula `gamma*V/g`, no añade el contenido automáticamente y no valida factor 1 por depósito. |
| `operaciones_etabs.py:1619–1623` | Getter del plan compara booleanos y número de patrones; registra listas LoadPat/sf. | Esta comprobación inmediata no demuestra por sí sola igualdad de todos los factores ni masa total. |
| `verificacion_modelo_guardado.py:1286–1297` | Relectura independiente compara booleanos, conjunto de patrones y cada factor contra lo esperado del plan. | Demuestra fidelidad de fuente configurada, no que esa configuración contenga el 100% del agua ni que su masa física total sea correcta. |

El peso propio de concreto/elementos mallados se conserva sobre la superficie material neta (`operaciones_etabs.py:1466–1515`), evitando host completo más triángulos y relleno ficticio de huecos. Esa conservación del **sólido** no equivale a masa del **líquido**.

## Brecha reproducible, sin modificar configuración en disco

Se utilizó el código congelado y una configuración **sintética archivada**, ya existente en `tmp/l2/configuracion.json`, junto a su geometría versionada. La configuración es la misma fuente SHA citada en el registro 206; su líquido HIDRO se aplica a una pared, mientras la masa original solo pondera D=1 y L=0.25.

- Configuración archivada SHA256: `0a30b0722cef7f2a003d05a05100ad2c99c6481a2ce251afc87395619bb91c38`.
- Geometría `tmp/l2/fuentes/private/sintetico-001/geometrias/f1cb882a86794f779020db0e63054dc6/geometria.json`, SHA256: `8280e8ba4ec46fdfbb38986e7623f68a965221180beb38c78444a3dea18d9656`.
- Variantes **solo en memoria**: HIDRO omitido, o incluido en fuente de masa con factor 0, 0.25, 1 y 2.
- Las cinco variantes resultaron `consistente=true`, `faltantes=[]`, aprobación de huella sintética vigente y ningún error. No se exige así ni pertenencia de HIDRO ni factor de contenido 1.
- `apto_para_adaptador=false` en este ensayo es correcto: `validar_configuracion` no comprueba evidencia versionada en disco ni concede aptitud operativa. No se ejecutó `comprobar_configuracion`, no se generó plan y no se afirma aprobación real de ninguna variante.

Reproducción desde la raíz del proyecto:

```powershell
@'
import sys,json,copy,hashlib
from pathlib import Path
sys.path.insert(0,str(Path('tmp/revision_codex_246').resolve()))
from draft2model import modelo_estructural as m
p=Path('tmp/l2/configuracion.json')
assert hashlib.sha256(p.read_bytes()).hexdigest()=='0a30b0722cef7f2a003d05a05100ad2c99c6481a2ce251afc87395619bb91c38'
base=json.loads(p.read_text(encoding='utf8'))
gp=Path('tmp/l2/fuentes/private/sintetico-001/geometrias')/base['geometria_origen']['version_id']/'geometria.json'
assert hashlib.sha256(gp.read_bytes()).hexdigest()=='8280e8ba4ec46fdfbb38986e7623f68a965221180beb38c78444a3dea18d9656'
geo=json.loads(gp.read_text(encoding='utf8'))
for factor in [None,0,.25,1,2]:
    c=copy.deepcopy(base)
    if factor is not None:
        c['masa']['factores_patrones'].append({'patron':'HIDRO','factor':factor})
    # Huella sintética renovada SOLO en memoria, para aislar el control semántico.
    c['revision']['aprobacion']['huella_configuracion']=m.huella_configuracion(c)
    r=m.validar_configuracion(c,geo)
    print(factor,r.consistente,r.faltantes,r.aprobacion_configuracion_vigente,r.apto_para_adaptador)
    assert r.consistente and not r.faltantes and r.aprobacion_configuracion_vigente
print('5 variantes consistentes; sin escritura de configuración ni plan')
'@ | python -B -
```

Esto prueba ausencia de la guarda «contenido100%» en la validación, no la masa que un solver produciría. Aun imponer factor1 a un patrón hidrostático sería insuficiente: las superficies pueden ser solo paredes o incompletas. No se debe equiparar una suma de presiones normales con `gamma*V` sin balance y geometría del volumen.

## Qué acreditan 206 y 210r3, y qué no

Se leyeron los registros; **no se repitieron** las pruebas ni se abrió el modelo.

- `seguimiento/COMPROBACION_ANALITICA_LIQUIDOS_206.json`: integra independientemente una pared rectangular 5×2.6 menos hueco, gamma10 y nivel1.5; obtiene F=[53.8,0,0] kN y M=[0,25.593333333333334,-135.725] kNm. Contrasta la carga fuente y una relectura guardada. El propio registro deja pendiente equilibrio de reacciones. No calcula volumen ni masa del contenido.
- `seguimiento/EQUILIBRIO_ESTRICTO_LIQUIDOS_210.json`: contrasta la reacción de la respuesta sintética archivada con esa fuerza/momento aplicada, residuo máximo 6.821210263296962e-13; conserva el fallo original de la tabla redondeada 208 y no relaja umbral. Eso acredita equilibrio estático del caso sintético descrito, no masa modal, inventario100%, dos depósitos reales ni ausencia de duplicación semántica en otros patrones.
- La configuración fuente archivada de 206 omite HIDRO de su fuente de masa. Por ello, un resultado hidrostático correcto en esa prueba no es evidencia de inclusión del contenido como masa.

Los tests de código `tests/test_liquidos_ruta201.py` cubren patrones dedicados, peso propio prohibido, presión con hueco/cortes, fondo/inclinado/dos declaraciones y fidelidad de filas; sus dobles no acreditan ETABS real ni un inventario de masa de agua. Solo se inspeccionaron sus aserciones.

## Contrato mínimo pendiente para integrar depósitos sin doble conteo

1. Inventario por depósito/estado de llenado: identidad, recinto/volumen o volumen medido revisado, nivel libre, gamma y gravedad; establecer `W_contenido=gamma*V`, `M_contenido=W_contenido/g` y coeficiente de inclusión declarado 1.00 cuando el requisito sea contenido100%. Distinguir volumen máximo, operativo y nivel usado en cada caso.
2. Libro de contribuciones físicas: peso propio del recipiente sólido; peso estático de contenido; presión en muros/fondo; contribución de contenido a masa. Relacionar cada una con patrones/casos y evidencia. Duplicar un ID físico mediante dos nombres de patrón debe detectarse.
3. Elegir **una** representación de contenido para masa y verificar su total contra el inventario. Si se usa un patrón gravitacional dedicado solo para alimentar masa, excluirlo de las combinaciones estáticas que ya reciben el peso mediante presión de fondo; excluir el patrón hidrostático de esa misma contribución de masa. No sumar ambos silenciosamente. Esto es una propuesta de contrato pendiente, no una configuración implementada/validada en esta auditoría.
4. Para cada fondo y muros comprobar cierre geométrico, normal, presión/fuerza/momento, y balance de peso estático del contenido. No tratar fondos y tapas como membranas sin resistencia normal; esa elección es asunto del contrato R241, distinto de la masa.
5. Añadir negativas de omisión, inclusión parcial, factor distinto del requerido, doble representación física, mezcla peso propio/presión/masa y volumen incompleto. La relectura debe acreditar tanto fuente/factores como masa física total por depósito/estado; conservar pruebas estáticas 206/210 como evidencia separada.

No se resolvió por inferencia una regla normativa ni se propuso que la presión estática represente hidrodinámica. Si todavía no existe este enlace inventario-masa, la integración debe mantener **pendiente explícito de contenido100%** y no aprobarlo por el solo hecho de disponer de presión y equilibrio estático.

## Identidad de archivos leídos

SHA256 de fuentes congeladas en `tmp/revision_codex_246/draft2model/`:

| Archivo | SHA256 |
| --- | --- |
| acciones_liquidos.py | `2C2FEB7E80A7C4AE373A748A69927A6C0A96B00773B0F89AE6B3E891601597B9` |
| liquidos_malla.py | `6352E9D68C2A8D89678739A1B910FEDC01627D08ED59276166A9086BEE4F94F6` |
| cargas_liquidos_etabs.py | `5B2FF5525793455224FC21AA57027534E8CC8DFC30E1243D7D797F11A1EE7922` |
| operaciones_etabs.py | `8270CC423C0D463507A9B641CB8E83BEEE0378AF02814F730F49825B74AFFDC1` |
| modelo_estructural.py | `07D51A99D499092D85E1C0F6B2D08863B16B14EBFEF4AAB8C2666BE4C6A055B2` |

Registros leídos: 206 SHA256 `AF7EB89C6CEA39C8BEF218E11AF0B08B05C0BDA9C406C3AEBC374068EE6D8201`; 210 SHA256 `538787C5E1B2FACCBA25913FB882C5110B73B8BF8949C97B884AFBC61A8C91BB`. El snapshot es el alcance de este dictamen; no se atribuye el hallazgo a futuras ediciones de Claude sin revisarlas.
