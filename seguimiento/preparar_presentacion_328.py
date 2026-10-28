"""Entrega académica compuesta: software325 intacto, caso303 y anexo asistido328."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,html,json,re,shutil,zipfile

root=Path(__file__).resolve().parents[1];out=root/'entregas/AECODE_PRESENTACION_328'
assert not out.exists(), 'No sobrescribir una entrega preparada.'
out.mkdir();bench=root/'seguimiento/revision_antigravity_328';soft=root/'entregas/AECODE_ENTREGA_325';case=root/'entregas/COMPLEMENTO_CORREGIDO_303'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((soft/'MANIFIESTO.json').read_bytes());validation=json.loads((soft/'VALIDACION.json').read_bytes())
assert validation['global']=={'python':1471,'interfaz':36} and validation['fuentes_estables']
assert sha(soft/'Draft2Model.zip')==manifest['zip_sha256']
assert all(sha(root/n)==h for n,h in manifest['archivos'].items() if not n.startswith('wheels/'))
benchmark=json.loads((bench/'BENCHMARK_ASISTIDO_328.json').read_bytes())
repro=json.loads((bench/'REPRODUCCION_UTF8_328.json').read_bytes())
assert len(repro['evaluaciones_reproducidas'])==4 and all(c['codigo']==0 and c['salida_identica'] for c in repro['evaluaciones_reproducidas'])
def copy(src,relative):
 dest=out/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest);assert sha(src)==sha(dest)
for name in ('Draft2Model.zip','MANIFIESTO.json','VALIDACION.json','AUDITORIA_P01_P14.json','AUDITORIA_P01_P14.md'):
 copy(soft/name,'software/'+name)
copy(soft/'REFERENCIA_DATOS_Y_NORMATIVA.md','DATOS_Y_NORMATIVA.md')
copy(case/'Complemento.zip','caso/Complemento.zip');copy(case/'MANIFIESTO_COMPLEMENTO.json','caso/MANIFIESTO_COMPLEMENTO.json')
with zipfile.ZipFile(case/'Complemento.zip') as z:
 for name in ('resultados/informe/informe.html','resultados/informe/informe.json','resultados/informe/informe.pdf','resultados/panel.html'):
  dest=out/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(name))
for name in ('informe.html','informe.json','informe.pdf'):
 copy(soft/'ANEXO_QA_AUTO'/name,'masa_auto/'+name)
for name in ('referencia_asistida_328.json','referencia_asistida_328.csv','REFERENCIA_FIJADA_328.json','CAMBIOS_328.json',
             'BENCHMARK_ASISTIDO_328.json','REPRODUCCION_UTF8_328.json','EXPOSICION_328.json','REVISION_328.json'):
 copy(bench/name,'benchmark/'+name)
shutil.copytree(bench/'evaluaciones',out/'benchmark/evaluaciones')
for n in range(1,4):copy(bench/f'corregido-{n}.png',f'benchmark/evidencia_visual-{n}.png')
for i in range(1,4):
 copy(root/'seguimiento/ANTIGRAVITY_REFERENCIA_327/entradas/originales'/f'lamina-{i:04d}.pdf',f'benchmark/originales/lamina-{i:04d}.pdf')
copy(root/'seguimiento/ANTIGRAVITY_REFERENCIA_327/salidas/referencia_propuesta_ia.json','benchmark/propuesta_antigravity_original.json')
copy(root/'seguimiento/ANTIGRAVITY_REFERENCIA_327/salidas/MARCADOR_FINAL.json','benchmark/marcador_antigravity_original.json')
for p in sorted((soft/'EVIDENCIAS').iterdir()):
 if p.is_file():copy(p,'evidencias_software/'+p.name)
def ratio(v):
 return 'no evaluable' if not v or v['denominador']==0 else f"{v['numerador']}/{v['denominador']} ({100*v['proporcion']:.1f} %)"
rows=[]
for c in benchmark['cohortes']:
 m=c.get('metricas')
 rows.append([c['cohorte'],', '.join(c.get('laminas_enviadas',[])) or 'fallida',str(c.get('candidatos') or '—'),ratio((m or {}).get('cobertura')),ratio((m or {}).get('lecturas_completas_sobre_legibles'))])
table='| Cohorte | Láminas recibidas | Candidatos | Cobertura tipo/región | Lectura completa |\n|---|---|---:|---:|---:|\n'+'\n'.join('| '+' | '.join(row)+' |' for row in rows)
method='''# Benchmark experimental asistido328

Referencia de33observaciones:11por cada lámina;15cotas,10etiquetas y8elementos;32legibles y1ambigua. Antigravity propuso los datos y Codex revisó las33contra los originales. Se corrigieron12localizaciones, una descripción y transcripciones específicas; el registro conserva antes/después. Se fijó la referencia antes de consultar los candidatos evaluados. El usuario solicitó expresamente completar esta tarea mediante IA.

**No hubo revisión humana independiente.** Estos datos no certifican exactitud general, ingeniería ni seguridad. La muestra no es un censo de los planos ni una selección estadística representativa. No existe un umbral comercial aprobado.

Las cohortes recibieron imágenes distintas. Por eso los denominadores se limitan a las láminas de contexto efectivamente enviadas:33/11/22/11observaciones, con una ambigua excluida cuando corresponde. No se suman ni comparan directamente como si fueran la misma tarea. Se conservan6peticiones originales:4con extracción válida y2fallidas; no se hicieron nuevas llamadas.

'''+table+'''

La cobertura exige mismo tipo y ubicación física revisada. La lectura completa exige además valor, unidad y evidencia correctos; las omisiones cuentan como fallo. En esta taxonomía, identificadores estructurales se anotaron como elemento, ejes/títulos como etiqueta. Otras clasificaciones reducen los emparejamientos aunque exista texto reconocible. Unidades inferidas como metros no se acreditan si la nota de unidad no respalda esa afirmación. Las observaciones ambiguas no entran en exactitud.

Varios candidatos tienen texto correcto pero cajas desplazadas o recortadas. La exactitud de valor condicionada a los pocos emparejados no demuestra buena cobertura. Los candidatos no cubiertos por esta referencia parcial se conservan sin clasificar, no se declaran automáticamente falsos positivos.

Este resultado identifica un límite de la extracción inicial, **anterior a las correcciones del modelo final**. El sistema necesita revisión supervisada de entradas; no está acreditada una operación autónoma con cualquier plano.

Cada carpeta de cohorte incluye referencia acotada, extracción original, correspondencias declaradas de CodexIA y métricas. Con el programa instalado se reproduce sin APIs:

```powershell
python -X utf8 -m draft2model.evaluacion_vision --referencia <cohorte>/referencia.json --extraccion <cohorte>/extraccion_original.json --correspondencias <cohorte>/correspondencias.json --salida <salida_nueva>.json
```

Las cuatro ejecuciones se reprodujeron por la CLI oficial y sus resultados JSON coinciden. Los cambios de la referencia, los hashes, la exposición de imágenes y las decisiones de pares están incluidos. Las imágenes de evidencia permiten revisar las regiones corregidas.
'''
(out/'benchmark/INFORME_BENCHMARK.md').write_text(method,encoding='utf-8')
thead=['Cohorte','Láminas','Candidatos','Cobertura tipo/región','Lectura completa']
html_table='<table><thead><tr>'+''.join('<th>'+html.escape(x)+'</th>' for x in thead)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>'
page='''<!doctype html><html lang="es"><meta charset="utf-8"><title>Benchmark asistido328</title><style>body{font:16px/1.55 system-ui;max-width:1100px;margin:40px auto;padding:0 20px;color:#173746}table{border-collapse:collapse;width:100%}td,th{padding:10px;border:1px solid #ccd5da;text-align:left}th{background:#edf2f5}img{max-width:100%}.notice{background:#fff3d6;padding:16px}</style><h1>Benchmark experimental asistido por IA</h1><p class="notice">33 observaciones revisadas por Codex sobre propuesta de Antigravity. Sin revisión humana independiente, sin aprobación de ingeniería y sin precisión universal acreditada.</p>'''+html_table+'''<p>Denominadores por láminas realmente enviadas. No sumar cohortes de tareas distintas. La cobertura exige tipo y región; una lectura completa exige valor, unidad y evidencia. Los resultados son anteriores a las correcciones del modelo final.</p><p><a href="INFORME_BENCHMARK.md">Metodología, límites y reproducción</a></p>'''+''.join(f'<h2>Evidencia visual {i}</h2><img src="evidencia_visual-{i}.png" alt="Regiones revisadas {i}">' for i in range(1,4))+'</html>'
(out/'benchmark/INFORME_BENCHMARK.html').write_text(page,encoding='utf-8')
status='''# Estado real del proyecto para presentación AECODE

## Disponible y verificado

- Software325:1471pruebas Python y36de interfaz, cinco comprobaciones correctas, sin omisiones y609fuentes estables. Entorno offline303reutilizado con el mismo lock y wheels; no se afirma una instalación nueva325.
- Primer proyecto: ingreso de planos, revisión/configuración, geometría, construcción real en ETABS21.1, análisis, relectura y13indicadores conservados. Modelo analizado SHA25642371308a03d4f1bac8f5ed3aa5daf0421cdf3de27ff823f8f582c13ad2af394.
- Resultados reales: T1/T2/T3=1,339/0,358/0,224s; cortantes X/Y=672,5354/528,1533kN. El informe técnico tiene18comparaciones:8satisfactorias y10no satisfactorias. Mostrar fallos del edificio no es un fallo del software; no se alteraron para obtener aprobación.
- Informes JSON/HTML/PDF y panel conservados. La estimación independiente opcional de masa es548,727337frente a548,726729observada; el contraste bruto549,426989continúa no_coherente. Se mantiene la tolerancia y un residuo CM de aproximadamente0,0069kN sin atribuir.
- Referencia asistida328:33observaciones revisadas,13con ajustes, cuatro evaluaciones originales reproducidas y dos peticiones fallidas conservadas. El código325y el EDB siguen intactos. Sin nuevas APIs.

## Qué falta para afirmar que todo está terminado para cualquier proyecto

1. **Robustez y generalización de la entrada automática.** La muestra experimental revela errores de localización, taxonomía y unidades. Hoy sigue siendo necesaria revisión supervisada de planos y configuración. No hay evidencia para prometer modelado autónomo de cualquier construcción.
2. **Validación de otros proyectos y tipologías.** Los proyectos segundo y tercero permanecen sin procesar por la instrucción previa del usuario. Un único piloto no prueba generalización. Las tipologías y operaciones fuera de las capacidades documentadas requieren tratamiento o rechazo explícitos, no una promesa universal.
3. **Validación independiente de ingeniería, si se usa en obra real.** No hay EMS: suelo/sistema son escenarios declarados. La comparación con el modelo ETABS manual está aplazada por el usuario y no se solicita para bloquear esta entrega de software. Los resultados no constituyen diseño ejecutivo aprobado.
4. **Rendimiento interactivo del expediente grande.** La regeneración y comprobación siguen siendo lentas. Una consulta bajo perfil pasó de205,39a195,45s; no es un SLA ni tiempo total de modelado. El recorrido QA322, que incluyó varias verificaciones e incidencia de un guion, tardó aproximadamente59minutos. Los informes archivados pueden consultarse directamente sin repetirlo.

## Para presentar hoy

La entrega actual permite presentar un **sistema operativo supervisado y un caso real trazable**, con sus pruebas, modelo, resultados y límites. No presentarlo como automatización universal, referencia humana independiente ni edificio aprobado por normativa. El benchmark asistido ya está completado; no se está esperando que el usuario termine el anotador.

No faltan claves nuevas para consultar la entrega. ETABS usa licencia y API locales; las claves de OpenAI/Google solo se usan para lecturas autorizadas de planos y no están incluidas. No se publicó ni envió nada a AECODE automáticamente.
'''
(out/'REPORTE_ESTADO.md').write_text(status,encoding='utf-8')
guide='''# Draft2Model: entrega para revisión académica

**Software325 verificado + caso real + benchmark asistido328.** La entrega es operativa con supervisión; no acredita automatización de cualquier construcción ni aprobación de ingeniería.

## Abrir primero

1. [Estado real y pendientes](REPORTE_ESTADO.md).
2. [Informe técnico del primer proyecto](resultados/informe/informe.html), [PDF](resultados/informe/informe.pdf) y [panel](resultados/panel.html).
3. [Benchmark asistido](benchmark/INFORME_BENCHMARK.html):33observaciones, referenciaIA corregida, métricas y límites. No es revisión humana.
4. [Anexo de estimación de masa](masa_auto/informe.html): evidencia QA322, separada del informe técnico con18comparaciones.
5. [Datos de entrada y normativa implementada](DATOS_Y_NORMATIVA.md).

## Modelo ETABS

Extraer `caso/Complemento.zip` y después `caso_archivado/Caso.zip` a una carpeta nueva. El modelo analizado es:

```text
pueblo-libre-002/analisis_etabs/7203c79a3ece4438b36d267ba80f3c4b/analizado.EDB
```

SHA256: `42371308a03d4f1bac8f5ed3aa5daf0421cdf3de27ff823f8f582c13ad2af394`. Abrirlo para inspección no equivale a aprobarlo. Guardar/recalcular cambia el archivo; conservar el archivo archivado y producir una nueva ejecución si se desea recalcular. Los recibos históricos conservan sus rutas originales: moverlos no demuestra una nueva corrida en otro equipo.

## Instalar el programa

Descomprimir `software/Draft2Model.zip` en una carpeta nueva. Requisitos: Windowsx64 y Python3.10x64; ETABS/licencia/API locales para el flujo nativo. Los wheels están incluidos y deben coincidir con el lock.

```powershell
python -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install --no-index --find-links wheels --require-hashes -r requirements-win-py310.lock
.\\.venv\\Scripts\\python.exe -m pip check
.\\.venv\\Scripts\\python.exe -m draft2model --help
.\\.venv\\Scripts\\python.exe -m draft2model.revision_visual --raiz data/private --puerto 8766
```

Abrir la URL local indicada. La guía `docs/GUIA_REPRODUCIBLE.md` del software detalla uso, ingreso, configuración y confirmaciones. Arrancar la interfaz no envía planos ni ejecuta ETABS. No incluir credenciales en la entrega. Las llamadas a modelos son exclusivamente para lectura autorizada de planos; no se consumen APIs para estas métricas.

El programa ofrece también una demo integrada sin red ni ETABS, identificada como sintética; no sustituye el caso real de esta entrega. Node.js permite repetir las pruebas de interfaz. Las pruebas globales y logs corresponden al ZIP325exacto; no se repitieron por añadir este anexo de datos.

## Integridad

`MANIFIESTO_ENTREGA.json` identifica cada archivo exterior. El programa y complemento conservan además sus manifiestos propios y hashes internos. `software/VALIDACION.json` y `evidencias_software/` conservan las pruebas. El anexo328se reprodujo por cuatro ejecuciones de la CLI oficial con resultados idénticos; el modelo, los informes anteriores y el código no se modificaron.
'''
(out/'LEER_PRIMERO.md').write_text(guide,encoding='utf-8')
# Control de secretos en los datos nuevos legibles; los ZIP previos conservan sus manifiestos revisados.
for p in (out/'benchmark').rglob('*'):
 if p.suffix.lower() in ('.json','.csv','.md','.html'):
  text=p.read_text(encoding='utf-8');assert not re.search(r'AIza[A-Za-z0-9_-]{25,}|sk-[A-Za-z0-9_-]{24,}',text),str(p)
files={p.relative_to(out).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(out.rglob('*')) if p.is_file()}
bundle={'contrato':'draft2model.entrega_academica','fecha_utc':datetime.now(timezone.utc).isoformat(),
 'software_huella':manifest['huella_fuentes'],'validacion_software':validation['global'],
 'estado':'operativo_supervisado_con_limitaciones','revision_humana_benchmark':False,
 'codigo_o_edb_modificados':False,'publicacion_externa_realizada':False,'archivos':files,'goal_completo':False}
(out/'MANIFIESTO_ENTREGA.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8')
archive=root/'entregas/AECODE_PRESENTACION_328.zip';assert not archive.exists()
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(out.rglob('*')):
  if p.is_file():z.write(p,'AECODE_PRESENTACION_328/'+p.relative_to(out).as_posix())
with zipfile.ZipFile(archive) as z:
 for name,item in files.items():assert hashlib.sha256(z.read('AECODE_PRESENTACION_328/'+name)).hexdigest()==item['sha256']
summary={'paquete':str(archive.relative_to(root)),'sha256':sha(archive),'bytes':archive.stat().st_size,'archivos':len(files),
         'referencia_asistida':33,'cohortes_reproducidas':4,'software325_intacto':True,'edb_intacto':True,'goal_completo':False}
(root/'seguimiento/ENTREGA_ACADEMICA_328.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
