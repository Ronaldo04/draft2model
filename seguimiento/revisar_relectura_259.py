"""Recomparar evidencia persistida09t4 sin abrir ETABS ni modificar sus archivos."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from draft2model import verificacion_modelo_guardado as v

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT/'tmp/recorrido_09t4/lectura/071d9ec46d9843d4b17e00adfc8d3b44'
OUT = ROOT/'tmp/revision_relectura_259'


def main():
    OUT.mkdir(exist_ok=False)
    names = ('solicitud.json','respuesta.json','expectativa.json','criterios.json','registro.json',
             'resultado_verificacion.json','modelo_lectura.edb')
    raw = {name: (SRC/name).read_bytes() for name in names}
    hashes = {name: hashlib.sha256(value).hexdigest() for name,value in raw.items()}
    (OUT/'huellas.json').write_text(json.dumps(hashes,indent=2)+'\n',encoding='utf-8')
    data = {name: json.loads(value) for name,value in raw.items() if name.endswith('.json')}
    request, response = data['solicitud.json'], data['respuesta.json']
    observed = response['datos']
    previous = data['resultado_verificacion.json']
    checks = {}
    def check(name, value):
        checks[name] = bool(value)
        if not value:
            raise ValueError(name)
    check('proceso_terminal_correcto', data['registro.json']['estado']=='ok' and data['registro.json']['codigo_proceso']==0)
    check('modo_real', request['modo_configurado']=='real' and response['modo_ejecucion']=='real')
    check('misma_solicitud', response['id_solicitud']==request['id']==previous['id_lectura'])
    check('solicitud_respuesta_expectativa_inmutables',
          hashes['solicitud.json']==previous['sha256_solicitud'] and
          hashes['respuesta.json']==previous['sha256_respuesta'] and
          hashes['expectativa.json']==request['sha256_expectativa']==previous['sha256_expectativa'])
    check('edb_lectura_mismos_bytes', hashes['modelo_lectura.edb']==request['sha256_edb']==
          observed['sha256_antes']==observed['sha256_despues']==previous['sha256_edb'])
    check('lectura_instancia_nueva_cerrada_sin_modificaciones', observed['instancia']=='nueva' and
          observed['instancia_cerrada'] is True and observed['guardado'] is False and observed['modificaciones']==[])
    check('consulta_y_lector_coinciden', observed['consulta']==request['consulta'] and observed['version_lector']==request['version_lector'])
    comparison = v.comparar(data['expectativa.json'],observed['lecturas'],data['criterios.json'])
    (OUT/'comparacion.json').write_text(json.dumps(comparison,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    check('recomparacion_verificada', comparison['estado']=='verificado' and not comparison['discrepancias'] and not comparison['incompletos'])
    check('comparacion_persistida_igual', all(previous[key]==value for key,value in comparison.items()))
    check('fuentes_sin_cambios_durante_revision', all(hashlib.sha256((SRC/name).read_bytes()).hexdigest()==digest for name,digest in hashes.items()))
    record = {'fecha_utc':datetime.now(timezone.utc).isoformat(),'responsable':'Codex',
        'comprobaciones':checks,'origen':str(SRC.relative_to(ROOT)),'huellas':hashes,
        'estado':'relectura_recomparada_verificada','operaciones':comparison['cobertura_plan']['operaciones'],
        'cobertura':comparison['cobertura'],'controles_no_afirmados':comparison['controles_no_afirmados'],
        'piloto_completo':False,'analisis_verificado':False,'apis_remotas':0,'etabs_abierto_por_esta_revision':False,
        'limites':['Se verifican lecturas conservadas, no se repite ejecución nativa',
                   'No acredita suelo real, geometría fuente completa ni correcciones09d posteriores',
                   'No sustituye análisis, controles de resultados ni informe final']}
    (ROOT/'seguimiento/REVISION_RELECTURA_259.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'estado':record['estado'],'comprobaciones':len(checks),'operaciones':record['operaciones'],'piloto_completo':False}))


if __name__=='__main__':
    main()
