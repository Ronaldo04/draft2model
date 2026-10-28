"""Una consulta conservada bajo perfil: sin ETABS, red, edición ni publicación."""
from pathlib import Path
from time import perf_counter
import argparse,cProfile,json,pstats
from draft2model.revision_modelo import consultar

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--despues',action='store_true');parser.add_argument('--corregido324',action='store_true');parser.add_argument('--cache325',action='store_true');args=parser.parse_args()
suffix='_cache325' if args.cache325 else ('_corregido324' if args.corregido324 else ('_despues' if args.despues else ''))
target=root/('seguimiento/PERFIL_MODELO_323'+suffix+'.json')
assert not target.exists(), 'No sobrescribir ni repetir un perfil ya conservado.'
profile=cProfile.Profile();start=perf_counter()
result=profile.runcall(consultar,root/'data/private','pueblo-libre-002','0f37271307b6449c89c458c60a1640c7')
elapsed=perf_counter()-start
profile.dump_stats(str(root/('tmp/perfil_modelo_323'+suffix+'.prof')))
stats=pstats.Stats(profile)
top=[]
for (file,line,name),(primitive,total,own,cumulative,callers) in sorted(stats.stats.items(),key=lambda kv:kv[1][3],reverse=True)[:22]:
    top.append({'archivo':Path(file).name,'linea':line,'funcion':name,'llamadas':total,'propio_s':round(own,4),'acumulado_s':round(cumulative,4)})
evidence={'consulta_unica':True,'etabs_abierto':False,'red':False,'pared_s':elapsed,'modelo':result['modelo_id'],
          'estado':result['estado'],'perfil':top,'no_prueba':'No repite instalación, suite, cálculo ni benchmark.'}
target.write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(evidence,ensure_ascii=False))
