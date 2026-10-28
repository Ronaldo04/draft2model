"""Demostración local integrada con datos fabricados, sin red, IA ni ETABS."""
from __future__ import annotations

import argparse
import copy
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import time

import pymupdf

from examples.conversion_sintetica.crear_demo import main as crear_conversion
from draft2model import gestion_geometria as gg
from draft2model import gestion_extraccion as ge
from draft2model import gestion_planes as gp
from draft2model import modelo_estructural as modelo
from draft2model.evaluacion_estructural import evaluar_resultados
from draft2model.conversion_geometria import CARPETA as CARPETA_CONVERSION
from draft2model.fuentes import cargar_corpus, huella_corpus, recuperar, verificar_citas
from draft2model.informe import crear_informe, exportar_informe, validar_informe
from draft2model.orquestacion import RegistroCorridas
from draft2model.resultados_estructurales import (
    cargar_json, exigir_resultados, huella_declaracion, huella_resultados,
)

EXAMPLES = Path(__file__).resolve().parent
FECHA = '2026-10-16'
REVISOR = 'Operador SIMULADO de fixture; identidad no autenticada'
AVISO = ('Demostración de software con datos y aprobaciones fabricados. '
         'No hubo llamada IA, ejecución ETABS ni evaluación de una estructura real.')


def _guardar(path, data):
    path = Path(path)
    with path.open('x', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=2, allow_nan=False)
        file.write('\n')
    return path


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _declarar_aprobacion(data, alcance):
    """Construye una declaración FABRICADA únicamente para estas fixtures."""
    data['revision'] = {'estado': 'aprobado', 'aprobacion': {
        'revisor_declarado': REVISOR, 'fecha': FECHA, 'motivo': AVISO,
        'alcance': alcance, 'huella_contenido': huella_declaracion(data)}}


def _fuentes_demo(folder):
    folder.mkdir()
    source = folder / 'fuente_sintetica.pdf'
    fragments = []
    with pymupdf.open() as pdf:
        for ident, variable, value in [('R-P', 'periodo', '1.0 s'), ('R-D', 'deriva', '0.003 razon'), ('R-V', 'cortante', '150 kN')]:
            text = f'Fixture SIN valor normativo. {variable}: limite fabricado {value}; solo prueba de software.'
            page = pdf.new_page()
            page.insert_textbox((50, 50, 540, 200), text, fontsize=12)
            fragments.append({'id': 'F-'+ident, 'documento': 'FUENTE-DEMO', 'pagina': len(pdf),
                              'apartado': ident, 'texto': text})
        pdf.save(source)
    corpus = {'contrato': 'draft2model.corpus', 'version': '0.1.0', 'datos_sinteticos': True,
              'documentos': [{'id': 'FUENTE-DEMO', 'titulo': 'Fuente SINTETICA sin valor normativo',
                              'edicion': 'fixture 0.1', 'archivo': source.name, 'sha256': _sha(source)}],
              'fragmentos': fragments, 'aprobacion': None}
    corpus['aprobacion'] = {'huella': huella_corpus(corpus), 'revisor_declarado': REVISOR,
                            'fecha': FECHA, 'alcance': 'Corpus fabricado para probar citas, sin uso normativo.'}
    manifest = _guardar(folder / 'corpus.json', corpus)
    recovered = recuperar(manifest, 'periodo deriva cortante fixture', limite=3)
    citations = [{'fragmento_id': f['id'], 'texto': f['texto']} for f in recovered['fragmentos']]
    verificar_citas(manifest, citations, recovered['huella_corpus'])
    _guardar(folder / 'citas.json', citations)
    return manifest, citations, source


def _configuracion(caso, approved, source, template):
    config = cargar_json(EXAMPLES / 'modelo_estructural_sintetico.json')
    config['caso'], config['id'] = caso, 'config-demo-integrada'
    comp = approved.comprobacion
    config['geometria_origen'] = {'version_id': approved.identificador,
        'sha256_geometria': comp.sha256_geometria, 'huella_contenido': comp.huella_contenido}
    # Selección explícita de la fixture de un muro A-B generada por crear_demo.
    ids = {'A0', 'B0', 'A1', 'B1'}
    config['puntos'] = [x for x in config['puntos'] if x['id'] in ids]
    config['apoyos'] = [x for x in config['apoyos'] if x['punto'] in ids]
    config['sin_diafragma'] = [x for x in config['sin_diafragma'] if x['punto'] in ids]
    config['diafragmas'][0]['puntos'] = ['A1', 'B1']
    config['asignaciones_muros'] = [x for x in config['asignaciones_muros'] if x['objetivo'] == 'M1']
    config['fuentes'][0].update(sha256=_sha(source), referencia='demo/fuentes/fuente_sintetica.pdf; datos fabricados.')
    config['plantilla'].update(sha256=_sha(template), representacion=AVISO)
    config['revision'] = {'estado': 'aprobado', 'aprobacion': {
        'revisor_declarado': REVISOR, 'fecha': FECHA,
        'huella_configuracion': modelo.huella_configuracion(config),
        'alcance': 'Configuración fabricada de prueba. No autoriza ETABS ni ingeniería real.',
        'identidad_revisor': 'declarada_no_verificada'}}
    return config


def crear_demo(destino: Path, *, caso='demo-integrada-sintetica') -> dict:
    """Ejecutar en un directorio completamente NUEVO; nunca fusionar ni sobrescribir."""
    if not isinstance(caso, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', caso):
        raise ValueError('Identificador de caso inválido.')
    destination = Path(destino).absolute()
    if destination.resolve() != destination:
        raise ValueError('Destino enlazado o con componentes no normalizados.')
    destination.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    _guardar(destination / 'DEMO.json', {'aviso': AVISO, 'datos_sinteticos': True})
    root = destination / 'private'
    captured = io.StringIO()
    with redirect_stdout(captured):
        crear_conversion(['--raiz', str(root), '--caso', caso])
    initial = json.loads(captured.getvalue())
    initial_elapsed = time.perf_counter() - start
    case = root / caso
    work = case / 'demo'
    work.mkdir()
    registry = RegistroCorridas(root)
    runs, elapsed = {}, {'creacion_y_conversion_inicial_s': initial_elapsed}
    original = case / 'originales' / 'lamina-0001.pdf'
    manifest = case / 'expediente.json'
    evidence = [original, manifest]

    def relative(path):
        return Path(path).relative_to(case).as_posix()

    def files(folder):
        if not Path(folder).is_dir():
            raise ValueError('La carpeta generada no existe: '+str(folder))
        return sorted(Path(folder).glob('*.json'))

    def stage(name, inputs, task):
        inputs = list(dict.fromkeys(evidence + list(inputs)))
        ident = registry.crear(caso, name, [relative(p) for p in inputs])
        runs[name] = ident
        registry.iniciar(ident)
        clock = time.perf_counter()
        try:
            outputs = task(ident)
            registry.finalizar(ident, [relative(p) for p in outputs])
        except Exception as exc:
            registry.fallar(ident, 'Fallo de demo sintética: '+type(exc).__name__)
            raise
        elapsed[name+'_s'] = time.perf_counter() - clock

    extraction_folder = case / 'extracciones' / initial['extraccion_id']
    conversion_folder = case / CARPETA_CONVERSION / initial['conversion_id']
    initial_geo = case / 'geometrias' / initial['geometria_id']
    # El helper inicial ya creó estos archivos; esta corrida registra su comprobación posterior.
    extraction_files = sorted((case / 'extracciones').rglob('*.json'))
    stage('preparacion', [], lambda _: extraction_files + files(conversion_folder) + files(initial_geo))
    evidence += extraction_files + files(conversion_folder)
    versions = {}

    def geometry_task(_):
        proposal = copy.deepcopy(gg.consultar_version(root, caso, initial['geometria_id']).geometria)
        proposal['revision'] = {'estado': 'borrador', 'aprobacion': None}
        reviewed = gg.revisar_geometria(root, caso, initial['geometria_id'], proposal,
            motivo='Revisión SIMULADA de contrato convertido. '+AVISO, fecha=FECHA, revisor_declarado=REVISOR)
        approved = gg.aprobar_geometria(root, caso, reviewed.identificador,
            huella_esperada=reviewed.comprobacion.huella_contenido, revisor_declarado=REVISOR,
            fecha=FECHA, motivo=AVISO, alcance_revision='Solo flujo sintético de software; aprobación fabricada.')
        plan = gp.generar_plan_version(root, caso, approved.identificador)
        gp.comprobar_plan(root, caso, plan.name)
        versions.update(revision=reviewed.identificador, aprobada=approved.identificador, plan=plan.name)
        return files(reviewed.ruta) + files(approved.ruta) + files(plan)

    stage('geometria', files(initial_geo), geometry_task)
    approved = gg.consultar_version(root, caso, versions['aprobada'])
    geometry_path = approved.ruta / 'geometria.json'
    for ident in approved.comprobacion.cadena:
        evidence += files(case / 'geometrias' / ident)
    corpus_path, citations, source = _fuentes_demo(work / 'fuentes')
    evidence += [source, corpus_path, corpus_path.parent / 'citas.json']
    template = _guardar(work / 'plantilla_fixture.json', {
        'id': 'shell-frame-lineal-sintetica', 'version': '0.1.0', 'datos_sinteticos': True,
        'descripcion': 'Fixture declarativa sin modelo ETABS, malla ni solver.', 'aviso': AVISO})
    evidence.append(template)
    configuration_path = work / 'configuracion.json'

    def model_task(_):
        config = _configuracion(caso, approved, source, template)
        check = modelo.comprobar_configuracion(root, config)
        if not check.consistente or not check.apto_para_adaptador or check.a_dict()['ejecutable_en_etabs']:
            raise ValueError('La configuración sintética no supera su comprobación: '+str(check.a_dict()))
        _guardar(configuration_path, config)
        check_path = _guardar(work / 'comprobacion_configuracion.json', check.a_dict())
        return [configuration_path, check_path]

    stage('modelo', [template], model_task)
    config = cargar_json(configuration_path)
    evidence += [configuration_path, work / 'comprobacion_configuracion.json']
    results_path, rules_path, evaluation_path = (work / name for name in ('resultados_simulados.json', 'reglas_sinteticas.json', 'evaluacion.json'))

    def analysis_task(ident):
        data = cargar_json(EXAMPLES / 'resultados_estructurales_sinteticos.json')
        data.update(corrida_id=ident, caso_id=caso, creado_utc=datetime.now(timezone.utc).isoformat(),
            geometria={'id': approved.identificador, 'sha256': approved.comprobacion.sha256_geometria},
            configuracion={'id': config['id'], 'sha256': modelo.huella_configuracion(config)})
        data['motor'] = {'tipo': 'simulacion', 'nombre': 'fixture-estatica-sin-motor', 'version': '0.1.0'}
        data['casos'] = [{'id': x['id'], 'tipo': x['tipo'], 'descripcion': 'Valores fabricados para caso configurado; no ejecutado.'}
                         for x in config['casos'] if x['id'] in {'MOD', 'EX'}]
        for row in data['resultados']:
            row['caso'] = 'MOD' if row['variable'] == 'periodo' else 'EX'
        data['advertencias'] = [AVISO]
        data['omisiones'] = ['No se ejecutaron EST, MOD, EX ni COMB1; solo se fabrican tres indicadores para pruebas.',
                            'No se generaron modelo ETABS, masas modales, equilibrio, esfuerzos ni envolventes.']
        exigir_resultados(data, referencias_esperadas={'geometria': data['geometria'], 'configuracion': data['configuracion']})
        _guardar(results_path, data)
        return [results_path]

    stage('analisis', [configuration_path], analysis_task)
    results = cargar_json(results_path)

    def evaluation_task(_):
        rules = cargar_json(EXAMPLES / 'reglas_estructurales_sinteticas.json')
        for rule in rules['reglas']:
            rule['aplicabilidad']['casos'] = ['MOD' if rule['variable'] == 'periodo' else 'EX']
            rule['fuente'] = {'titulo': 'Fuente SINTETICA sin valor normativo', 'edicion': 'fixture 0.1',
                'apartado': rule['id'], 'referencia': 'demo/fuentes/fuente_sintetica.pdf; fragmento F-'+rule['id']}
        _declarar_aprobacion(rules, 'Solo reglas de prueba, sin valor normativo. '+AVISO)
        _guardar(rules_path, rules)
        evaluation = evaluar_resultados(results, rules, huella_resultados_esperada=huella_resultados(results),
            huella_reglas_esperada=huella_declaracion(rules), referencias_esperadas={
                'geometria': {'id': approved.identificador, 'sha256': approved.comprobacion.sha256_geometria},
                'configuracion': {'id': config['id'], 'sha256': modelo.huella_configuracion(config)}})
        _guardar(evaluation_path, evaluation)
        return [rules_path, evaluation_path]

    stage('evaluacion', [results_path], evaluation_task)
    report_folder = work / 'informe_borrador'
    summary_path = case / 'resumen_demo.json'
    summary = {}

    def report_task(_):
        context = {'titulo': 'Demostración integrada SINTETICA · borrador de software',
            'hipotesis': [x['descripcion'] for x in config['hipotesis']] + [AVISO],
            'faltantes': results['omisiones'] + ['Sin ubicación ni estudio de sitio real.'], 'sitio': None}
        _guardar(work / 'contexto_informe.json', context)
        report = crear_informe(results, cargar_json(rules_path), context, evaluacion=cargar_json(evaluation_path),
            geometria_archivo=geometry_path, corpus=corpus_path, citas=citations)
        exportar_informe(report, report_folder, geometria_archivo=geometry_path, corpus=corpus_path)
        artifacts = [geometry_path, configuration_path, results_path, rules_path, evaluation_path,
            source, corpus_path, work / 'contexto_informe.json'] + list(report_folder.iterdir())
        summary.update(contrato='draft2model.demo_integrada', version='0.1.0', caso=caso,
            datos_sinteticos=True, aviso=AVISO, extraccion_id=initial['extraccion_id'],
            conversion_id=initial['conversion_id'], geometria_inicial=initial['geometria_id'],
            geometria_revision=versions['revision'], geometria_aprobada=versions['aprobada'], plan_id=versions['plan'],
            configuracion_id=config['id'], corrida_analisis_id=runs['analisis'], corridas=copy.deepcopy(runs),
            motor=results['motor'], artefactos={relative(p): _sha(p) for p in artifacts},
            metricas_software={'tiempos_s': copy.deepcopy(elapsed),
                'tiempo_hasta_exportacion_s': time.perf_counter()-start, 'llamadas_ia_reales': 0,
                'ejecuciones_etabs': 0, 'ahorro_validado': None, 'costo_ia_real_medido': None},
            fase_inicial='creación y conversión por helper; corrida preparacion registra comprobación posterior',
            informe_revision=report['revision'])
        _guardar(summary_path, summary)
        return list(report_folder.iterdir()) + [work / 'contexto_informe.json', summary_path]

    stage('informe', [results_path, rules_path, evaluation_path], report_task)
    verificar_demo(destination, caso=caso)
    return summary


def verificar_demo(destino: Path, *, caso='demo-integrada-sintetica') -> dict:
    """Revalidar originales, corpus, contratos y hashes SQLite antes de reutilizar salidas."""
    root = Path(destino).resolve() / 'private'
    case = root / caso
    summary = cargar_json(case / 'resumen_demo.json')
    registry = RegistroCorridas(root)
    runs = [registry.consultar(ident) for ident in summary['corridas'].values()]
    if any(not run['vigente'] or run['estado'] != 'completada' for run in runs):
        raise ValueError('Corridas con evidencia alterada o estado no completado; regenerar en carpeta nueva.')
    for relative, expected in summary['artefactos'].items():
        path = case / relative
        if path.resolve() != path or not path.resolve().is_relative_to(case.resolve()) or _sha(path) != expected:
            raise ValueError('Artefacto de demo ausente, enlazado o alterado.')
    check = gg.comprobar_version(root, caso, summary['geometria_aprobada'])
    if not check.correcta:
        raise ValueError('Geometría o evidencia de origen no vigente.')
    if not ge.validar_version(root, caso, summary['extraccion_id']).correcta:
        raise ValueError('Lecturas o ascendencia sin vigencia.')
    gp.comprobar_plan(root, caso, summary['plan_id'])
    config = cargar_json(case / 'demo/configuracion.json')
    if not modelo.comprobar_configuracion(root, config).apto_para_adaptador:
        raise ValueError('Configuración sin vigencia.')
    corpus = cargar_corpus(case / 'demo/fuentes/corpus.json')
    citations = cargar_json(case / 'demo/fuentes/citas.json')
    verificar_citas(case / 'demo/fuentes/corpus.json', citations, huella_corpus(corpus))
    validar_informe(cargar_json(case / 'demo/informe_borrador/informe.json'))
    return {'correcta': True, 'caso': caso, 'corridas_completadas': len(runs), 'datos_sinteticos': True, 'aviso': AVISO}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida', required=True, type=Path)
    parser.add_argument('--caso', default='demo-integrada-sintetica')
    parser.add_argument('--verificar', action='store_true')
    args = parser.parse_args(argv)
    result = verificar_demo(args.salida, caso=args.caso) if args.verificar else crear_demo(args.salida, caso=args.caso)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
