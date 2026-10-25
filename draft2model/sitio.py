"""Consulta referencial de cobertura declarada; no deduce parámetros geotécnicos."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

from .gestion_extraccion import json_desde_bytes

# Constantes del elipsoide WGS84 (NGA). El cribado usa cotas inferiores,
# no una conversión uniforme de grados a metros ni distancia catastral.
SEMIEJE_WGS84_M = 6378137.0
ACHATAMIENTO_WGS84 = 1 / 298.257223563
EXCENTRICIDAD_2 = ACHATAMIENTO_WGS84 * (2 - ACHATAMIENTO_WGS84)
RADIO_MERIDIANO_MIN_M = SEMIEJE_WGS84_M * (1 - EXCENTRICIDAD_2)
LATITUD_MAXIMA = 60.0
EXTENSION_CAPA_MAX_GRADOS = 10.0
PRECISION_MAX_M = 50_000.0
RESGUARDO_REDONDEO_M = 1e-6


def _escalas_cribado(latitud, radio_m):
    """Cotas de la métrica elipsoidal en toda trayectoria de longitud <= radio.

    M(phi)>=a(1-e²). Una trayectoria tan corta no puede alejarse en latitud
    más de radio/M_min; en esa banda N(phi)cos(phi)>=a*cos(phi_max).
    Si un borde está a distancia real <= radio, su distancia en este plano
    no es mayor. Un positivo es conservador, no una distancia medida.
    """
    phi_max = abs(math.radians(latitud)) + radio_m / RADIO_MERIDIANO_MIN_M
    return SEMIEJE_WGS84_M * math.cos(phi_max), RADIO_MERIDIANO_MIN_M


def _distancia_segmento_origen(ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    norma2 = dx * dx + dy * dy
    if norma2 == 0:
        return math.hypot(ax, ay)
    t = max(0.0, min(1.0, -(ax * dx + ay * dy) / norma2))
    return math.hypot(ax + t * dx, ay + t * dy)


def _cerca_frontera(longitud, latitud, anillo, escalas, radio_m):
    sx, sy = escalas
    # Traslación al punto consultado antes de escalar: evita coordenadas
    # proyectadas grandes y conserva segmentos lon/lat lineales del GeoJSON.
    puntos = [(math.radians(x - longitud) * sx, math.radians(y - latitud) * sy)
              for x, y in anillo]
    return any(_distancia_segmento_origen(*a, *b) <= radio_m
               for a, b in zip(puntos, puntos[1:]))


def _validar_dominio(puntos, longitud):
    longitudes = [p[0] for p in puntos]
    latitudes = [p[1] for p in puntos]
    if any(abs(y) > LATITUD_MAXIMA for y in latitudes):
        raise ValueError('Cribado de precisión admite latitudes entre -60 y 60 grados.')
    if max(longitudes) - min(longitudes) > 180 or any(abs(x - longitud) > 180 for x in longitudes):
        raise ValueError('Cribado de precisión no admite cruce del antimeridiano.')
    if (max(longitudes) - min(longitudes) > EXTENSION_CAPA_MAX_GRADOS
            or max(latitudes) - min(latitudes) > EXTENSION_CAPA_MAX_GRADOS):
        raise ValueError('Cribado de precisión requiere capa local de hasta 10 grados por eje.')


def huella_capa(capa):
    return hashlib.sha256(json.dumps({k:v for k,v in capa.items() if k!='aprobacion'},
                                    ensure_ascii=False,sort_keys=True,allow_nan=False,
                                    separators=(',', ':')).encode()).hexdigest()


def _numero(x):
    try:
        return type(x) in (int,float) and math.isfinite(x)
    except (OverflowError, ValueError):
        return False


def _punto(point):
    return (isinstance(point,list) and len(point)==2 and all(_numero(v) for v in point)
            and -180<=point[0]<=180 and -90<=point[1]<=90)


def _ubicacion_en_anillo(x, y, ring):
    inside = False
    for a,b in zip(ring,ring[1:]):
        cross = (x-a[0])*(b[1]-a[1])-(y-a[1])*(b[0]-a[0])
        if abs(cross) <= 1e-12 and min(a[0],b[0])-1e-12 <= x <= max(a[0],b[0])+1e-12 and min(a[1],b[1])-1e-12 <= y <= max(a[1],b[1])+1e-12:
            return 'limite'
        if (a[1]>y)!=(b[1]>y):
            xi = (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]
            if x<xi: inside = not inside
    return 'dentro' if inside else 'fuera'


def consultar_sitio(archivo: Path, longitud: float, latitud: float) -> dict:
    if not _punto([longitud,latitud]):
        raise ValueError('Ubicación requiere longitud/latitud finitas en EPSG:4326.')
    if abs(latitud) > LATITUD_MAXIMA:
        raise ValueError('Cribado de precisión admite latitudes entre -60 y 60 grados.')
    raw = Path(archivo).read_bytes()
    layer = json_desde_bytes(raw,'capa de sitio')
    if not isinstance(layer,dict) or set(layer)!={'contrato','version','crs','fuente','fecha','precision_m','datos_sinteticos','zonas','aprobacion'}:
        raise ValueError('Capa de sitio inválida.')
    if layer['contrato']!='draft2model.capa_sitio' or layer['version']!='0.1.0' or layer['crs']!='EPSG:4326':
        raise ValueError('Contrato o CRS no soportados.')
    if (type(layer['datos_sinteticos']) is not bool or not _numero(layer['precision_m'])
            or not 0 < layer['precision_m'] <= PRECISION_MAX_M):
        raise ValueError('Naturaleza o precisión inválidas.')
    from datetime import date
    date.fromisoformat(layer['fecha'])
    if not isinstance(layer['fuente'],dict) or set(layer['fuente'])!={'titulo','edicion','referencia'} or not all(isinstance(v,str) and v.strip() for v in layer['fuente'].values()):
        raise ValueError('Fuente completa requerida.')
    approval = layer['aprobacion']
    if not isinstance(approval,dict) or set(approval)!={'huella','revisor_declarado','fecha','alcance'} or approval['huella']!=huella_capa(layer):
        raise ValueError('Capa sin aprobación declarada vigente.')
    for key in ('revisor_declarado','fecha','alcance'):
        if not isinstance(approval[key],str) or not approval[key].strip():
            raise ValueError('Aprobación incompleta.')
    date.fromisoformat(approval['fecha'])
    if not isinstance(layer['zonas'],list) or not layer['zonas']:
        raise ValueError('Capa sin zonas.')
    radio_m = layer['precision_m'] + RESGUARDO_REDONDEO_M
    escalas = _escalas_cribado(latitud, radio_m)
    ids=set(); matches=[]; puntos_capa=[]
    for zone in layer['zonas']:
        if not isinstance(zone,dict) or set(zone)!={'id','etiqueta','geometria'} or not all(isinstance(zone[k],str) and zone[k].strip() for k in ('id','etiqueta')) or zone['id'] in ids:
            raise ValueError('Zona inválida o duplicada.')
        ids.add(zone['id'])
        geometry=zone['geometria']
        if not isinstance(geometry,dict) or set(geometry)!={'type','coordinates'} or geometry['type']!='Polygon':
            raise ValueError('Se requiere Polygon GeoJSON explícito.')
        rings=geometry['coordinates']
        if not isinstance(rings,list) or not rings:
            raise ValueError('Polígono vacío.')
        for ring in rings:
            if not isinstance(ring,list) or len(ring)<4 or not all(_punto(p) for p in ring) or ring[0]!=ring[-1]:
                raise ValueError('Anillo abierto o inválido.')
            area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(ring,ring[1:]))
            if abs(area)<1e-12 or max(p[0] for p in ring)-min(p[0] for p in ring)>180:
                raise ValueError('Anillo degenerado o cruza antimeridiano.')
            puntos_capa.extend(ring)
        positions=[_ubicacion_en_anillo(longitud,latitud,ring) for ring in rings]
        if 'limite' in positions or any(_cerca_frontera(longitud,latitud,ring,escalas,radio_m) for ring in rings):
            state='limite'
        elif positions[0]=='dentro' and not any(p=='dentro' for p in positions[1:]):
            state='dentro'
        else: state='fuera'
        if state!='fuera': matches.append({'id':zone['id'],'etiqueta':zone['etiqueta'],'posicion':state})
    _validar_dominio(puntos_capa, longitud)
    state='sin_cobertura' if not matches else ('limite' if any(m['posicion']=='limite' for m in matches) else ('ambiguo' if len(matches)>1 else 'dentro'))
    return {'contrato':'draft2model.sitio','version':'0.1.0','ubicacion':{'longitud':longitud,'latitud':latitud,'crs':'EPSG:4326'},
            'estado':state,'zonas':matches,'fuente':layer['fuente'],'fecha_fuente':layer['fecha'],
            'precision_m':layer['precision_m'],'datos_sinteticos':layer['datos_sinteticos'],
            'sha256_capa':hashlib.sha256(raw).hexdigest(),'huella_capa':huella_capa(layer),
            'parametros_geotecnicos':None,'capacidad_portante':None,
            'aviso':'Cobertura referencial. limite incluye borde o franja conservadora de precision_m con resguardo de 1 micrometro; puede aparecer a ambos lados, fuera o en huecos. No es distancia medida ni confianza estadística. No asigna perfil de suelo, parámetros normativos ni capacidad portante.'}
