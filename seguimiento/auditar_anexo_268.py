"""Inventario local de entrega; no copia, modifica ni acredita el expediente."""
from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / 'data/private/pueblo-libre-002'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    groups = []
    for group in sorted(p for p in CASE.iterdir() if p.is_dir()):
        files = [p for p in group.rglob('*') if p.is_file()]
        groups.append({'grupo': group.name, 'archivos': len(files),
                       'bytes': sum(p.stat().st_size for p in files)})
    reads = []
    for ident in ('b8d0f12e93ce4014b57fb3008623a682', '9b1080d1f35d4007aef5fd92f527cea0'):
        folder = CASE / 'lecturas_analisis' / ident
        request = json.loads((folder / 'solicitud.json').read_text(encoding='utf-8-sig'))
        receipt_path = folder / 'aceptacion_lectura.json'
        response_path = folder / 'respuesta.json'
        receipt = json.loads(receipt_path.read_text(encoding='utf-8-sig')) if receipt_path.exists() else {}
        reads.append({'id': ident, 'sha256_solicitud': sha(folder/'solicitud.json'),
                      'sha256_respuesta': sha(response_path) if response_path.exists() else None,
                      'recibo_presente': receipt_path.exists(),
                      'huella_respuesta_coincide_recibo': response_path.exists() and receipt.get('sha256_respuesta') == sha(response_path),
                      'ruta_absoluta_declarada': Path(request['modelo_esperado']).is_absolute(),
                      'limite': 'Consistencia de bytes; no revalidación completa del análisis ni cierre de instancia.'})
    sources = ('draft2model/revision_lecturas.py', 'draft2model/lectura_analisis.py',
               'draft2model/evidencia_analisis.py', 'scripts/crear_paquete_aecode.py')
    report = {'fecha_utc': datetime.now(timezone.utc).isoformat(), 'caso': CASE.name,
              'estado': 'plan_de_anexo_no_exportado_no_validado_en_otra_carpeta',
              'grupos': groups, 'lecturas': reads,
              'fuentes_inspeccionadas_sha256': {s: sha(ROOT/s) for s in sources},
              'hallazgos': [
                  'El ZIP de fuentes excluye data/private: necesita complemento separado del caso autorizado.',
                  'No exportar toda data/private: contiene credenciales.local.md y otros casos.',
                  'Las solicitudes y respuestas históricas declaran rutas absolutas. El lector compara la ruta actual con la declarada; no basta copiar archivos para acreditar relectura portable.',
                  'Conservar bytes y hashes históricos. No reescribir rutas/recibos para simular aceptación tras mover.',
                  'Separar apertura del EDB, consulta de resultados archivados y reconstrucción con nuevas corridas.',
                  'La selección mínima necesita el cierre transitivo de geometría, configuración, plantilla, originales, modelo, aprobación, análisis, lecturas y resultado/informe finales.',
                  'El inventario agregado no prueba cierre transitivo ni valida calidad. No se copiaron archivos ni se usó ETABS o APIs.'
              ], 'goal_completo': False}
    out = ROOT / 'seguimiento/ANEXO_CASO_268_PLAN.json'
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'informe': str(out.relative_to(ROOT)), 'grupos': len(groups),
                      'bytes_caso_completo': sum(g['bytes'] for g in groups), 'lecturas': reads}, ensure_ascii=False))

if __name__ == '__main__':
    main()
