from pathlib import Path
import hashlib,json,re,shutil,zipfile
from urllib.parse import unquote,urlparse
root=Path(__file__).resolve().parents[1];out=root/'entregas/AECODE_PRESENTACION_328'
bench=root/'seguimiento/revision_antigravity_328';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for i in range(1,4):shutil.copyfile(bench/f'corregido-{i}.png',out/f'benchmark/evidencia_visual-{i}.png')
clarification='Los porcentajes describen correspondencias confirmadas bajo el criterio estricto de tipo y región de esta muestra. No estiman la precisión global del OCR ni implican que una cohorte con0emparejamientos no haya leído ningún texto. Quedan propuestas sin clasificar y puede haber lecturas fuera de la muestra o con otra taxonomía.'
p=out/'benchmark/INFORME_BENCHMARK.md';p.write_text(p.read_text(encoding='utf-8')+'\n\n'+clarification+'\n',encoding='utf-8')
p=out/'benchmark/INFORME_BENCHMARK.html';p.write_text(p.read_text(encoding='utf-8').replace('</html>','<p>'+clarification+'</p></html>'),encoding='utf-8')
p=out/'REPORTE_ESTADO.md';p.write_text(p.read_text(encoding='utf-8')+'\n## Cómo interpretar las métricas\n\n'+clarification+'\n',encoding='utf-8')
talk='''# Guion breve para presentar el trabajo

1. **Problema:** pasar de planos a un modelo estructural exige transcribir datos, configurar cargas, comprobar unidades y controlar errores.
2. **Solución implementada:** propuestas de lectura con evidencia, revisión supervisada, geometría/configuración versionadas, malla y operaciones ETABS, análisis y relectura, reglas y resultados trazables.
3. **Demostración real:** abrir resultados/informe/informe.html y resultados/panel.html. Mostrar los tres periodos, derivas y cortantes. El modelo analizado está en el caso archivado. Se conservan8comparaciones satisfactorias y10no satisfactorias; se muestran los resultados tal como salieron.
4. **Validación del software:**1471pruebas Python y36de interfaz de la versión325, ZIP y dependencias identificados por hashes, prueba real ETABS conservada. Estas pruebas no certifican ingeniería.
5. **Evaluación de visión:** referencia asistida de33observaciones y cuatro cohortes reproducidas, sin nuevasAPIs. Explicar errores de localización, clasificación y unidades; no presentar una exactitud condicionada alta como cobertura general ni la referenciaIA como humana.
6. **Límites y continuidad:** operación supervisada, un piloto, escenarios de suelo/sistema sinEMS, otros proyectos aún sin probar y latencia alta. La comparación con el modelo manual está aplazada. La evidencia actual no respalda automatización universal.

La exposición puede realizarse consultando los artefactos archivados. No hace falta recalcular ETABS ni reenviar planos a proveedores para mostrar los resultados existentes. Para demostrar el programa en otro equipo, seguir LEER_PRIMERO.md y la guía incluida en el ZIP de software.
'''
(out/'PRESENTACION_5_MINUTOS.md').write_text(talk,encoding='utf-8')
# Revisar enlaces de los documentos nuevos, no resolver rutas históricas de recibos.
missing=[];links=0
for p in [out/'LEER_PRIMERO.md',out/'benchmark/INFORME_BENCHMARK.html']:
 text=p.read_text(encoding='utf-8')
 targets=re.findall(r'\]\(([^)]+)\)',text) if p.suffix=='.md' else re.findall(r'(?:src|href)="([^"]+)"',text)
 for target in targets:
  url=urlparse(target)
  if url.scheme or target.startswith('#'):continue
  links+=1
  if not (p.parent/unquote(url.path)).is_file():missing.append([str(p.relative_to(out)),target])
assert not missing,missing
integrity=json.loads((root/'tmp/integridad_presentacion_328.json').read_text(encoding='utf-8-sig'))
check={'enlaces_comprobados':links,'enlaces_rotos':missing,'integridad_programa_y_caso':integrity,
       'cuatro_evaluaciones_cli_identicas':True,'revision_humana_realizada':False,'codigo_y_edb_modificados':False}
(out/'VALIDACION_PAQUETE.json').write_text(json.dumps(check,ensure_ascii=False,indent=2),encoding='utf-8')
manifest_path=out/'MANIFIESTO_ENTREGA.json';manifest=json.loads(manifest_path.read_bytes())
files={p.relative_to(out).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(out.rglob('*')) if p.is_file() and p!=manifest_path}
manifest['archivos']=files;manifest['revision_paquete']='Final: encabezados visuales y aclaración del alcance de métricas'
manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
archive=root/'entregas/AECODE_PRESENTACION_328_FINAL.zip';assert not archive.exists()
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(out.rglob('*')):
  if p.is_file():z.write(p,'AECODE_PRESENTACION_328/'+p.relative_to(out).as_posix())
with zipfile.ZipFile(archive) as z:
 for name,info in files.items():assert hashlib.sha256(z.read('AECODE_PRESENTACION_328/'+name)).hexdigest()==info['sha256']
summary={'archivo':str(archive.relative_to(root)),'sha256':sha(archive),'bytes':archive.stat().st_size,
         'archivos_sin_manifiesto':len(files),'validacion':check,'goal_completo':False}
(root/'seguimiento/ENTREGA_ACADEMICA_328_FINAL.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
