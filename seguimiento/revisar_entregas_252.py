"""Aceptación incremental09D: hashes, fuentes y evidencias; no cierra piloto09E."""
import hashlib
import json
from pathlib import Path
root=Path(__file__).resolve().parent.parent
snap=root/'tmp/revision_codex_251'
logs=root/'entregas/04-5b8365a8989f4fb7bc6574a730de2596/logs'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
checks=[]
def check(name, ok): checks.append({'caso':name,'pasa':bool(ok)})
for proof in ('CAPTURA_RENDIMIENTO_247.json','PORTADO_MASA_250.json'):
    p=json.loads((root/'seguimiento'/proof).read_text(encoding='utf-8'))
    for name,h in p['sha256'].items():
        check('fuente revisada '+name,sha(snap/name.replace('\\','/'))==h)
fixture=json.loads((snap/'tests/fixtures/columna_l_etabs21_246.json').read_text(encoding='utf-8'))
native=json.loads((logs/'registro.json').read_text(encoding='utf-8'))
check('fixture liga recibo nativo',fixture['sha256_registro_original']==sha(logs/'registro.json'))
for f in native['fases']:
    key='secciones_construccion' if f['fase']=='construccion' else 'secciones_reapertura'
    check('secciones '+f['fase'],fixture[key]==f['secciones'])
check('resultados fixture no alterados',fixture['resultados_tope']==native['resultados_tope'])
check('recibo nativo igual al auditado249',sha(logs/'registro.json')==json.loads((root/'seguimiento/REVISION_C1_NATIVA_CODEX_249.json').read_text(encoding='utf-8'))['recibo_sha256'])
read=json.loads((logs/'relectura_resultado.json').read_text(encoding='utf-8'))
check('relectura sintética verificada',read['estado']=='verificado' and not read['discrepancias'] and not read['incompletos'])
check('EDB sintético coincide relectura',sha(root/'tmp/columna_l_plan_246a/modelo.edb')==read['sha256_edb'])
norm=json.loads((logs/'normativa246.json').read_text(encoding='utf-8'))
check('fragmentos normativos conservados',len(norm['resultados'])==32 and all(x['encontrado'] for x in norm['resultados']))
for name,h in norm['huellas'].items():
    check('texto fuente normativa '+name,sha(root/'seguimiento/normativa_229'/name)==h)
check('focales declaradas182', 'Ran 182 tests' in (logs/'focos246_hito.log').read_text(encoding='utf-8') and 'OK' in (logs/'focos246_hito.log').read_text(encoding='utf-8'))
check('focales declaradas53', 'Ran 53 tests' in (logs/'focos247.log').read_text(encoding='utf-8') and (logs/'focos247.log').read_text(encoding='utf-8').rstrip().endswith('OK'))
receipt=json.loads((root/'tmp/plantilla_validacion_251/registro.json').read_text(encoding='utf-8'))
check('validación negativa plantilla sin instancia',receipt['status']=='failed' and receipt['stage']=='validation' and not receipt['own_instance_created'] and not receipt['file_saved'])
result={'estado':'revisado_incremental_con_limites' if all(c['pasa'] for c in checks) else 'fallo',
 'integridad':'seguimiento/INTEGRIDAD_ENTREGAS_251.json','snapshot':str(snap.relative_to(root)),
 'comprobaciones':checks,
 'ejecuciones_propias':{'contrato_L_plan_CLI': '5OK7.182s en host tras cuota restablecida', 'normativa_fixtureL':'7OK0.001s en aislamiento', 'despacho_CLI':'10contrastes purosOK','plantilla':'Entrada inválida devuelve1 yJSON; sin instancia/EDB'},
 'entorno':'Primer auto-reviewHOST no ejecutado por cuota. ordinaryUsageAllowed volviótrue/primary9% y nueva revisión automática autorizó5pruebas. Restauración de bytes local no ejecutó código. Tres pruebas CLI con fixtures fallaron por WinError5 en aislamiento; se conservan como fallos de entorno, no éxito ni fallo funcional.',
 'limites':['No es piloto completo ni aceptación de09E','Masa deagua solo biblioteca sin consumidores; R249-02abierta','Escalera y escenarios siguen pendientes','AcoplamientoIxy no probado; acotar lenguaje generalETABS','No se repitió suite general ni solver nativo']}
(root/'seguimiento/REVISION_ENTREGAS_252.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'estado':result['estado'],'comprobaciones':len(checks),'fallos':[c for c in checks if not c['pasa']]},ensure_ascii=False))
if result['estado']=='fallo': raise SystemExit(1)
path=root/'seguimiento/claude_ruta/REVISIONES.json'
reviews=json.loads(path.read_text(encoding='utf-8'))
for ident in ('5b8365a8989f4fb7bc6574a730de2596','cd20a685e89b42b1888d5ec1d83d8095'):
    if ident not in reviews['revisadas']: reviews['revisadas'].append(ident)
if not any(o['id']=='R252-01' for o in reviews['observaciones']):
    reviews['observaciones'].append({'id':'R252-01','prioridad':'revision_incremental','etapas':['04','06'],
      'hallazgo':'09D revisado con integridad24/546fuentes y6/1logs; cinco pruebas propias contrato/plan/CLI, siete normativa/fixture y diez contrastes despacho. Plantilla rechazo seguro confirmado. R249-02ygeometría09E siguen abiertos.',
      'evidencia':'seguimiento/REVISION_ENTREGAS_252.json','criterio_aceptacion':'Aceptar avance de software, continuar modelo completo, masa y recorrido real. No sustituir con sintéticos ni cerrar por0errores mientras haya faltantes.'})
path.write_text(json.dumps(reviews,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
