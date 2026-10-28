"""Audita bytes y valores conservados sin importar producto ni llamar servicios."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def read(p):
    return json.loads((ROOT / p).read_text(encoding='utf-8-sig'))

def sha(p):
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()

def canonical(data):
    # Contrato huella_extraccion: contenido canónico, distinto del SHA de bytes.
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()

checks = []
def check(name, ok, **details):
    checks.append(dict(prueba=name, pasa=bool(ok), **details))

# La copia limpia debe acreditar exactamente los miembros publicados, no otro árbol.
delivery = read('entregas/06-c54f77043471420fac2dc2a30cee5749/manifiesto.json')
clean = read('entregas/04-d3de8e4b14fa4ccbbbe7931f0f983c34/logs/copia_limpia_c208.json')
copied = {k.replace('\\', '/'): v for k, v in clean['archivos_copiados'].items()}
missing = [k for k in delivery['archivos'] if k not in copied]
different = [k for k, h in delivery['archivos'].items() if k in copied and copied[k] != h]
check('snapshot_publicado_contra_copia_limpia', not missing and not different,
      miembros=len(delivery['archivos']), faltan=missing, difieren=different)

# La derivación debe conservar contenido y revisión de cada candidato de origen.
der = read('seguimiento/claude_ruta/DERIVACION_PUEBLO_LIBRE_002.json')
destbase = Path('data/private') / der['caso_destino'] / 'extracciones' / der['extraccion_destino']
dest = read(destbase/'extraccion.json')
index = {c['id']: c for c in dest['candidatos']}
check('destino_huella_canonica_registrada', canonical(dest) == der['huella_destino'])
seen = set()
for origin in der['fuentes']:
    base = Path('data/private')/origin['caso']/'extracciones'/origin['version']
    source = read(base/'extraccion.json')
    check('origen_huella_canonica_'+origin['prefijo'], canonical(source) == origin['huella_extraccion'])
    errors = []
    for c in source['candidatos']:
        ident = origin['prefijo']+'.'+c['id']
        seen.add(ident)
        d = index.get(ident)
        if d is None:
            errors.append(dict(id=ident, error='ausente'))
            continue
        for field in ('tipo', 'valor_propuesto', 'unidad', 'metodo', 'revision'):
            if c.get(field) != d.get(field):
                errors.append(dict(id=ident, campo=field))
        # Al no reutilizar recortes del expediente anterior, conservar referencia al original.
        old_ev = [{k:v for k,v in e.items() if k not in ('recorte_id','imagen_sha256')} for e in c['evidencia']]
        if old_ev != d['evidencia']:
            errors.append(dict(id=ident, campo='evidencia_original'))
    check('contenido_derivado_'+origin['prefijo'], not errors, candidatos=len(source['candidatos']), diferencias=errors)
check('inventario_derivado_exacto', seen == set(index) and len(index) == der['candidatos'], cantidad=len(index))

# Recuperación: integridad local del crudo y vínculo fuente/versiones.
base = Path('data/private/provisional-001/vision/respuestas/f51b8418119c4426ab7c5dea231bd81d')
reg = read(base/'registro.json')
check('crudo_recuperado_intacto', sha(base/'respuesta_original.json') == reg['respuesta_sha256'])
check('extraccion_recuperada_registrada', sha(base/'extraccion.json') == reg['extraccion_sha256'])
rec = read(base/'extraccion.json')
check('recuperacion_59_12', len(rec['candidatos']) == 59 and len(rec.get('cuarentena', [])) == 12,
      validos=len(rec['candidatos']), cuarentena=len(rec.get('cuarentena', [])))
out = dict(estado='correcto' if all(c['pasa'] for c in checks) else 'hallazgos',
           comprobaciones=checks, api_llamadas=0, producto_modificado=False,
           alcance='Integridad y conservación de datos; no prueba calidad de lectura, geometría ni cumplimiento normativo.')
(ROOT/'seguimiento/AUDITORIA_PROCEDENCIA_238.json').write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
print(json.dumps(out, ensure_ascii=True))
