"""Reproducción por CLI oficial de cuatro evaluaciones, sin API ni modificación del programa."""
from pathlib import Path
import argparse,csv,hashlib,json,subprocess,sys
parser=argparse.ArgumentParser();parser.add_argument('--utf8-reparacion',action='store_true');args=parser.parse_args()
root=Path(__file__).resolve().parents[1];base=root/'seguimiento/revision_antigravity_328'
report=json.loads((base/'BENCHMARK_ASISTIDO_328.json').read_bytes());checks=[]
for c in report['cohortes']:
 if c['estado']!='evaluacion_experimental_asistida':continue
 folder=base/'evaluaciones'/c['cohorte'];target=folder/('metricas_reproducidas_utf8.json' if args.utf8_reparacion else 'metricas_reproducidas.json')
 assert not target.exists(), 'No repetir una reproducción ya archivada.'
 cmd=[sys.executable,'-X','utf8','-m','draft2model.evaluacion_vision','--referencia',str(folder/'referencia.json'),
      '--extraccion',str(folder/'extraccion_original.json'),'--correspondencias',str(folder/'correspondencias.json'),'--salida',str(target)]
 run=subprocess.run(cmd,cwd=root,capture_output=True,text=True,encoding='utf-8',timeout=30)
 assert run.returncode==0,run.stderr
 assert run.stdout and 'Evaluación de lecturas' in run.stdout
 assert json.loads(target.read_bytes())==json.loads((folder/'metricas.json').read_bytes())
 checks.append({'cohorte':c['cohorte'],'codigo':0,'salida_identica':True})
ref=json.loads((base/'referencia_asistida_328.json').read_bytes())
with (base/'referencia_asistida_328.csv').open('w',encoding='utf-8',newline='') as f:
 fields=['id','archivo_id','pagina','tipo','x0','y0','x1','y1','valor_json','unidad','legibilidad']
 writer=csv.DictWriter(f,fields);writer.writeheader()
 for o in ref['observaciones']:
  e=o['evidencia'][0];writer.writerow({'id':o['id'],'archivo_id':e['archivo_id'],'pagina':e['pagina'],'tipo':o['tipo'],
     **dict(zip(['x0','y0','x1','y1'],e['bbox_normalizada'])),'valor_json':json.dumps(o['valor'],ensure_ascii=False),'unidad':o['unidad'],'legibilidad':o['legibilidad']})
edb=root/'data/private/pueblo-libre-002/analisis_etabs/7203c79a3ece4438b36d267ba80f3c4b/analizado.EDB'
assert hashlib.sha256(edb.read_bytes()).hexdigest()=='42371308a03d4f1bac8f5ed3aa5daf0421cdf3de27ff823f8f582c13ad2af394'
out={'evaluaciones_reproducidas':checks,'edb_piloto_intacto':True,'llamadas_api_nuevas':0,'revision_humana_realizada':False,'consola_utf8_verificada':True}
(base/('REPRODUCCION_UTF8_328.json' if args.utf8_reparacion else 'REPRODUCCION_328.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out))
