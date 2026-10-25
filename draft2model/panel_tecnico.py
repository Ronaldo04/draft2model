"""Panel técnico autónomo desde contratos validados; no ejecuta motores ni red."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from .resultados_estructurales import cargar_json, exigir_resultados, huella_resultados
from .evaluacion_estructural import evaluar_resultados, validar_reglas
from .validacion_geometria import validar_geometria


def crear_panel(resultados: Path, reglas: Path | None, salida: Path, *, geometria: Path | None = None,
                evidencia_analisis: dict | None = None):
    """`evidencia_analisis` (opcional): {"raiz","caso","resultado","corrida"}; se revalida desde sus ficheros."""
    result=cargar_json(resultados)
    exigir_resultados(result)
    evidence=None
    if evidencia_analisis is not None:
        from .evidencia_analisis import validar_evidencia, verificar_fuente
        evidence=verificar_fuente(evidencia_analisis)
        validar_evidencia(evidence,result)
    evaluation=None
    if reglas is not None:
        rules=cargar_json(reglas)
        checked=validar_reglas(rules)
        evaluation=evaluar_resultados(result,rules,huella_resultados_esperada=huella_resultados(result),
                                     huella_reglas_esperada=checked['huella'])
    walls=None
    if geometria is not None:
        raw=Path(geometria).read_bytes(); geo=cargar_json(geometria)
        valid=validar_geometria(geo)
        if not valid.consistente or hashlib.sha256(raw).hexdigest()!=result['geometria']['sha256']:
            raise ValueError('Geometría no consistente o distinta de la referencia de resultados.')
        walls=len(geo['muros'])
    data={'resultados':result,'evaluacion':evaluation,'numero_muros':walls,
          'huella_resultados':huella_resultados(result)}
    if geometria is not None:
        from .resumen_geometria import resumen_geometria
        resumen=resumen_geometria(geo)
        if resumen is not None:data['resumen_geometria']=resumen   # 0.2/0.3 (hallazgo 283); 0.1 conserva su forma
    if evidence is not None:  # el snapshot de evidencia no contiene rutas locales
        data['evidencia_analisis']=evidence
    encoded=json.dumps(data,ensure_ascii=False,allow_nan=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    html=_HTML.replace('__DATA__',encoded)
    with Path(salida).open('x',encoding='utf-8') as stream:stream.write(html)
    return Path(salida)


_HTML='''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Draft2Model · Resultados</title>
<style>body{font:16px system-ui;background:#eef3f4;color:#18343f;margin:0}header{background:#142e38;color:white;padding:25px 5%}main{max-width:1120px;margin:35px auto;padding:0 22px}h1{font-size:32px}h2{font-size:21px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}.card,section{padding:22px;background:white;border:1px solid #dce4e7;border-radius:10px;margin-bottom:20px}.card b{display:block;font-size:24px;margin-top:10px}.badge{background:#fff0c7;padding:12px;border-radius:6px}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px;border-bottom:1px solid #ddd}select{font:inherit;padding:8px;margin:8px 20px 16px 0}code{overflow-wrap:anywhere;font-size:12px}label{display:inline-block}li{margin:8px 0}.muted{color:#58717a}footer{padding:20px 0;font-size:13px}@media(max-width:650px){.tablewrap{overflow:auto}h1{font-size:26px}}</style>
<header><strong>D2M · Draft2Model</strong><div>Panel técnico · resultados trazables</div></header><main><h1 id="titulo"></h1><p class="badge" id="modo"></p>
<div class="cards"><div class="card">Generación y análisis<b id="estado"></b></div><div class="card">Geometría y muros<b id="muros"></b></div><div class="card">Condición del sitio<b>No disponible</b><small>Sin consulta de capa vinculada a este panel.</small></div></div>
<section><h2>Periodos, derivas y cortante basal</h2><label>Caso <select id="caso"><option value="">Todos</option></select></label><label>Dirección <select id="direccion"><option value="">Todas</option></select></label><label>Indicador <select id="variable"><option value="">Todos</option><option value="periodo">Periodo</option><option value="deriva">Deriva</option><option value="cortante">Cortante</option></select></label><div class="tablewrap"><table><thead><tr><th>Indicador</th><th>Caso</th><th>Dirección</th><th>Ubicación</th><th>Valor</th><th>Unidad</th></tr></thead><tbody id="filas"></tbody></table></div><p id="vacio" hidden>No hay resultados para esta selección.</p></section>
<section><h2>Reglas configuradas</h2><p class="muted">Satisfacer una regla configurada no es un juicio de seguridad estructural.</p><div id="reglas"></div></section><section id="evidencia" hidden><h2>Evidencia de análisis</h2><ul id="evidencia_lista"></ul><p class="muted" id="evidencia_aviso"></p></section><section><h2>Advertencias e inconsistencias</h2><ul id="avisos"></ul></section><section><h2>Versiones y procedencia</h2><p id="corrida"></p><p>Geometría: <code id="geometria"></code></p><p>Configuración: <code id="config"></code></p><p>Huella de resultados: <code id="huella"></code></p><p class="muted">El panel es una instantánea. Volver a generarlo tras cambiar entradas, resultados o reglas. La declaración del motor no autentica una ejecución real.</p></section><footer>Draft2Model · Informe preliminar sujeto a revisión</footer></main>
<script type="application/json" id="datos">__DATA__</script><script>
'use strict';const d=JSON.parse(document.getElementById('datos').textContent),r=d.resultados,$=id=>document.getElementById(id);
function texto(id,value){$(id).textContent=value}function item(parent,value){const p=document.createElement('p');p.textContent=value;$(parent).append(p)}
texto('titulo','Resultados · '+r.caso_id);texto('modo',(r.datos_sinteticos?'DATOS SINTÉTICOS · ':'')+'Motor declarado: '+r.motor.tipo+' / '+r.motor.nombre+' '+r.motor.version);
const ev=d.evidencia_analisis||null;
texto('estado',ev?'Cálculo completado verificado ('+ev.analisis.casos.map(c=>c.id+'='+c.estado_csi).join(', ')+'); resultados sin revisar':(r.motor.tipo==='simulacion'?'Simulación explícita':'Resultados declarados'));
if(ev){$('evidencia').hidden=false;for(const value of ['Modelo '+ev.modelo.modelo_id+' con revisión declarada '+ev.modelo.aprobacion_id+' (identidad no verificada)','Análisis '+ev.analisis.corrida_id+' aceptado · modo '+ev.analisis.modo+' · ETABS '+ev.analisis.version_etabs+' · '+ev.analisis.casos.map(c=>c.id+': estado CSI '+c.estado_csi).join(', '),'Resultado '+ev.resultado.id+' leído del mismo EDB analizado (SHA256 '+ev.analisis.sha256_edb_analizado+')','Revisión de resultados: '+ev.estados.revision_resultados+' · Conformidad normativa: '+ev.estados.conformidad_normativa]){const li=document.createElement('li');li.textContent=value;$('evidencia_lista').append(li)}texto('evidencia_aviso',ev.aviso)}texto('muros',d.resumen_geometria?('Superficies: '+d.resumen_geometria.superficies+' ('+Object.entries(d.resumen_geometria.superficies_por_papel).map(([k,v])=>k+': '+v).join(' · ')+') · niveles de piso '+d.resumen_geometria.niveles_piso.length+' (base '+d.resumen_geometria.base+' + '+d.resumen_geometria.pisos_sobre_base+' pisos) · auxiliares '+d.resumen_geometria.niveles_auxiliares.length+'. '+d.resumen_geometria.nota):d.numero_muros===null?'No disponible':String(d.numero_muros)+' muros');texto('corrida',r.corrida_id+' · '+r.creado_utc);texto('geometria',r.geometria.id+' / '+r.geometria.sha256);texto('config',r.configuracion.id+' / '+r.configuracion.sha256);texto('huella',d.huella_resultados);
for(const id of ['caso','direccion'])for(const value of [...new Set(r.resultados.map(row=>row[id]))]){const opt=document.createElement('option');opt.value=value;opt.textContent=value;$(id).append(opt)}
function render(){$('filas').replaceChildren();let count=0;for(const row of r.resultados){if(['caso','direccion','variable'].some(k=>$(k).value&&$(k).value!==row[k]))continue;count++;const tr=document.createElement('tr');for(const value of [row.variable,row.caso,row.direccion,row.ubicacion,row.valor===null?'No disponible':String(row.valor),row.unidad]){const td=document.createElement('td');td.textContent=value;tr.append(td)}$('filas').append(tr)}$('vacio').hidden=count>0}
for(const id of ['caso','direccion','variable'])$(id).addEventListener('change',render);render();
if(d.evaluacion===null)item('reglas','Evaluación pendiente: no se han proporcionado reglas revisadas. No se declara cumplimiento.');
else for(const ev of d.evaluacion.evaluaciones)item('reglas',ev.regla_id+' · '+ev.caso+'/'+ev.direccion+'/'+ev.ubicacion+' · '+ev.estado+(ev.estado==='evaluado'?' · '+ev.relacion_limite+' del límite configurado '+ev.limite+' '+(ev.unidad_resultado||ev.unidad)+' (entrada en '+ev.unidad+')':'')+' · '+ev.fuente.titulo+' / '+ev.fuente.edicion+' / '+ev.fuente.apartado);
for(const value of [...r.advertencias,...r.omisiones]){const li=document.createElement('li');li.textContent=value;$('avisos').append(li)}
</script></html>'''


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--resultados',type=Path,required=True);p.add_argument('--reglas',type=Path,help='Reglas revisadas; sin ellas se muestra evaluación pendiente')
    p.add_argument('--salida',type=Path,required=True);p.add_argument('--geometria',type=Path)
    p.add_argument('--analisis-raiz',type=Path);p.add_argument('--analisis-caso');p.add_argument('--analisis-resultado')
    p.add_argument('--analisis-corrida',type=Path)
    args=p.parse_args(argv)
    from .evidencia_analisis import fuente_desde_argumentos
    fuente=fuente_desde_argumentos(args.analisis_raiz,args.analisis_caso,args.analisis_resultado,args.analisis_corrida)
    print(crear_panel(args.resultados,args.reglas,args.salida,geometria=args.geometria,evidencia_analisis=fuente))


if __name__=='__main__':main()
