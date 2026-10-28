"""Reanudar solo la consulta del informe ya publicado; nunca relanzar ETABS ni crear informe."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,inspect,json
from draft2model.revision_visual import RevisionLocal
from draft2model.revision_entregables import ServicioEntregables

root=Path(__file__).resolve().parents[1]
p=root/'seguimiento/FLUJO_AUTO_322.json';s=json.loads(p.read_bytes())
assert s['estado']=='fallo' and s.get('informe')=='5fbeb92275eb4dfbb3d3457f6c4abee5'
assert s['estado_lectura']=='aceptado'
# Probar la firma antes de entrar en la comprobación costosa.
inspect.signature(ServicioEntregables.consultar).bind(None,'pueblo-libre-002',s['informe'],expediente_sha256='f'*64)
original=dict(s)
history=root/'seguimiento/INCIDENCIA_GUION_322.json'
assert not history.exists(), 'No repetir la reanudación; consultar el proceso existente.'
history.write_text(json.dumps(original,ensure_ascii=False,indent=2),encoding='utf-8')
def save():p.write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
s.update(estado='verificando_informe',incidencia_guion=str(history.relative_to(root)),error=None);save()
app=RevisionLocal(root/'data/private');case='pueblo-libre-002'
fp=app.expediente(case)[2]
try:
    checked=app.entregables.consultar(case,s['informe'],expediente_sha256=fp)
    mass=checked['masa_nativa'];auto=mass['estimacion_auto']
    assert mass['contraste']['estado']=='no_coherente'
    assert auto['estado']=='estimado' and auto['contraste_estimado']['estado']=='coherente'
    assert checked['masa_nativa_seleccionada']['estimar_auto'] is True
    edb=root/'data/private'/case/'analisis_etabs/7203c79a3ece4438b36d267ba80f3c4b/analizado.EDB'
    s.update(bruto=mass['libro']['masa_total_kn_s2_m'],estimado=auto['masa_estimada_kn_s2_m'],
             observado=mass['contraste']['masa_observada_U1'],descuento_kn=auto['descuento_peso_kn'],
             sha_edb_despues=hashlib.sha256(edb.read_bytes()).hexdigest())
    assert s['sha_edb_antes']==s['sha_edb_despues']
    s.update(estado='terminado',fin_utc=datetime.now(timezone.utc).isoformat());save()
except Exception as error:
    s.update(estado='fallo_consulta',error=str(error));save();raise
print(json.dumps(s,ensure_ascii=False))
