"""Preparación explícita de fotografías con coordenadas y hashes trazables."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import sys
import warnings
from pathlib import Path

from PIL import Image, ImageEnhance, __version__ as PILLOW_VERSION

MAX_PIXELES = 20_000_000
MAX_LADO = 16_000
MAX_BYTES = 100_000_000
IDENTIDAD = [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]]


def _numero(valor):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError("Se requiere un número finito, excluido bool.")
    try:
        numero = float(valor)
    except OverflowError as error:
        raise ValueError("Número fuera de rango.") from error
    if not math.isfinite(numero):
        raise ValueError("Se requiere un número finito.")
    return numero


def _dimensiones(valor):
    if (not isinstance(valor, (list, tuple)) or len(valor) != 2
            or any(isinstance(v, bool) or not isinstance(v, int) for v in valor)):
        raise ValueError("Dimensiones deben ser dos enteros en píxeles.")
    ancho, alto = valor
    if not (2 <= ancho <= MAX_LADO and 2 <= alto <= MAX_LADO) or ancho * alto > MAX_PIXELES:
        raise ValueError(f"Dimensiones fuera de límites: lado 2–{MAX_LADO}, área <= {MAX_PIXELES} px.")
    return ancho, alto


def _resolver(matriz, vector):
    """Eliminación con pivote parcial para sistemas pequeños normalizados."""
    n = len(vector)
    filas = [list(map(float, fila)) + [float(valor)] for fila, valor in zip(matriz, vector)]
    for columna in range(n):
        pivote = max(range(columna, n), key=lambda f: abs(filas[f][columna]))
        if abs(filas[pivote][columna]) < 1e-12:
            raise ValueError("Transformación degenerada o numéricamente inestable.")
        filas[columna], filas[pivote] = filas[pivote], filas[columna]
        factor = filas[columna][columna]
        filas[columna] = [v / factor for v in filas[columna]]
        for fila in range(n):
            if fila != columna:
                factor = filas[fila][columna]
                filas[fila] = [v - factor * p for v, p in zip(filas[fila], filas[columna])]
    solucion = [fila[-1] for fila in filas]
    if not all(math.isfinite(v) for v in solucion):
        raise ValueError("Transformación no finita.")
    return solucion


def _producto(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def invertir_matriz(matriz):
    columnas = [_resolver(matriz, [float(i == j) for i in range(3)]) for j in range(3)]
    return [[columnas[j][i] for j in range(3)] for i in range(3)]


def transformar_punto(matriz, x, y):
    """Coordenadas px continuas desde el borde exterior superior izquierdo."""
    x, y = _numero(x), _numero(y)
    valores = [sum(fila[k] * [x, y, 1.][k] for k in range(3)) for fila in matriz]
    if not all(math.isfinite(v) for v in valores) or abs(valores[2]) < 1e-12:
        raise ValueError("Punto fuera del dominio finito de la transformación.")
    resultado = (valores[0] / valores[2], valores[1] / valores[2])
    if not all(math.isfinite(v) for v in resultado):
        raise ValueError("Coordenada transformada no finita.")
    return resultado


def preparar_transformacion(dimensiones_px, config):
    """Validar configuración y producir matrices; no lee ni modifica imágenes."""
    ancho, alto = _dimensiones(dimensiones_px)
    if not isinstance(config, dict) or set(config) != {"rotacion_grados", "contraste", "perspectiva"}:
        raise ValueError("Config requiere exactamente rotacion_grados, contraste y perspectiva.")
    rotacion = config["rotacion_grados"]
    if isinstance(rotacion, bool) or not isinstance(rotacion, int) or rotacion not in (0, 90, 180, 270):
        raise ValueError("rotacion_grados debe ser 0, 90, 180 o 270, en sentido horario.")
    contraste = _numero(config["contraste"])
    if not 0 < contraste <= 5:
        raise ValueError("contraste debe ser mayor que 0 y como máximo 5; 1 conserva contraste.")
    perspectiva = config["perspectiva"]
    proyeccion = [fila[:] for fila in IDENTIDAD]
    ancho_rect, alto_rect = ancho, alto
    if perspectiva is not None:
        if not isinstance(perspectiva, dict) or set(perspectiva) != {"esquinas_px", "dimensiones_salida_px"}:
            raise ValueError("perspectiva requiere esquinas_px y dimensiones_salida_px.")
        ancho_rect, alto_rect = _dimensiones(perspectiva["dimensiones_salida_px"])
        esquinas = perspectiva["esquinas_px"]
        if not isinstance(esquinas, (list, tuple)) or len(esquinas) != 4:
            raise ValueError("Se requieren cuatro esquinas ordenadas SI, SD, ID, II.")
        puntos = []
        for punto in esquinas:
            if not isinstance(punto, (list, tuple)) or len(punto) != 2:
                raise ValueError("Cada esquina requiere x,y.")
            x, y = map(_numero, punto)
            if not (0 <= x <= ancho and 0 <= y <= alto):
                raise ValueError("Esquina fuera de los bordes de la imagen original.")
            puntos.append((x / ancho, y / alto))
        for i in range(4):
            a, b, c = puntos[i], puntos[(i + 1) % 4], puntos[(i + 2) % 4]
            cruz = (b[0]-a[0])*(c[1]-b[1]) - (b[1]-a[1])*(c[0]-b[0])
            if cruz <= 1e-10:
                raise ValueError("Esquinas degeneradas, cruzadas, cóncavas o en orden incorrecto.")
        sistema, valores = [], []
        destinos = ((0., 0.), (1., 0.), (1., 1.), (0., 1.))
        # Resolver rectángulo -> cuadrilátero: su origen siempre es una esquina
        # finita, incluso si la prolongación del plano original tiene un polo.
        for (x, y), (u, v) in zip(destinos, puntos):
            sistema += [[x,y,1,0,0,0,-u*x,-u*y], [0,0,0,x,y,1,-v*x,-v*y]]
            valores += [u, v]
        h = _resolver(sistema, valores)
        normalizada = invertir_matriz([h[:3], h[3:6], h[6:] + [1.]])
        denominadores = [normalizada[2][0]*x + normalizada[2][1]*y + normalizada[2][2] for x, y in puntos]
        if not (min(denominadores) > 1e-10 or max(denominadores) < -1e-10):
            raise ValueError("Perspectiva singular dentro del cuadrilátero.")
        proyeccion = _producto([[ancho_rect,0,0],[0,alto_rect,0],[0,0,1]],
                              _producto(normalizada, [[1/ancho,0,0],[0,1/alto,0],[0,0,1]]))
    rotaciones = {
        0: IDENTIDAD,
        90: [[0,-1,alto_rect],[1,0,0],[0,0,1]],
        180: [[-1,0,ancho_rect],[0,-1,alto_rect],[0,0,1]],
        270: [[0,1,0],[-1,0,ancho_rect],[0,0,1]],
    }
    directa = _producto(rotaciones[rotacion], proyeccion)
    inversa = invertir_matriz(directa)
    dimensiones_final = [alto_rect, ancho_rect] if rotacion in (90,270) else [ancho_rect, alto_rect]
    return {"origen_a_salida": directa, "salida_a_origen": inversa,
            "origen_a_rectificada": proyeccion, "dimensiones_rectificada_px": [ancho_rect,alto_rect],
            "dimensiones_salida_px": dimensiones_final}


def procesar_imagen(entrada: Path, config: dict, salida: Path) -> Path:
    """Conservar original; escribir PNG/config/registro en una carpeta nueva."""
    entrada, salida = Path(entrada), Path(salida)
    if salida.exists():
        raise ValueError("La carpeta de salida ya existe; no se sobrescribe.")
    with entrada.open("rb") as fuente:
        original = fuente.read(MAX_BYTES + 1)
    if len(original) > MAX_BYTES:
        raise ValueError(f"Original supera el límite de {MAX_BYTES} bytes.")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(original)) as imagen:
            if imagen.format not in ("PNG", "JPEG") or getattr(imagen, "n_frames", 1) != 1:
                raise ValueError("Solo PNG/JPEG de una imagen; no PDF ni animaciones.")
            transformacion = preparar_transformacion(imagen.size, config)
            dimensiones_origen = list(imagen.size)
            orientacion_exif = imagen.getexif().get(274, 1)
            preparada = imagen.convert("RGB")
    if config["perspectiva"] is not None:
        inversa_rect = invertir_matriz(transformacion["origen_a_rectificada"])
        normalizador = inversa_rect[2][2]
        if abs(normalizador) < 1e-12:
            raise ValueError("Perspectiva inversa no representable para el rasterizador.")
        coef = tuple(v/normalizador for fila in inversa_rect for v in fila)[:8]
        preparada = preparada.transform(tuple(transformacion["dimensiones_rectificada_px"]),
                                        Image.Transform.PERSPECTIVE, coef,
                                        resample=Image.Resampling.BICUBIC, fillcolor="white")
    operaciones = {90: Image.Transpose.ROTATE_270, 180: Image.Transpose.ROTATE_180,
                   270: Image.Transpose.ROTATE_90}
    if config["rotacion_grados"]:
        preparada = preparada.transpose(operaciones[config["rotacion_grados"]])
    preparada = ImageEnhance.Contrast(preparada).enhance(config["contraste"])
    # Los píxeles ya representan la configuración explícita. No propagar EXIF:
    # navegadores y lectores podrían volver a orientarlos automáticamente.
    preparada.info.clear()
    buffer = io.BytesIO()
    preparada.save(buffer, format="PNG")
    contenido = buffer.getvalue()
    configuracion = json.dumps(config, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    registro = {
        "contrato": "draft2model.preprocesamiento", "version": "0.1.0",
        "original": str(entrada.resolve()), "original_sha256": hashlib.sha256(original).hexdigest(),
        "imagen": "imagen.png", "imagen_sha256": hashlib.sha256(contenido).hexdigest(),
        "config": "config.json", "config_sha256": hashlib.sha256(configuracion.encode("utf-8")).hexdigest(),
        "dimensiones_origen_px": dimensiones_origen, **transformacion,
        "unidad_coordenadas": "px", "convencion": "bordes continuos; centros de píxel i+0.5,j+0.5; x derecha, y abajo",
        "orden_operaciones": ["perspectiva", "rotacion_horaria", "contraste"],
        "exif_orientacion_original": orientacion_exif, "exif_aplicado_automaticamente": False,
        "modo_salida": "RGB", "alpha": "descartado si existe", "pillow_version": PILLOW_VERSION,
        "escala_metrica": None, "mejora_precision_vision": "no_evaluada",
    }
    registro_bytes = (json.dumps(registro, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    salida.mkdir()  # Exclusiva; el padre debe existir. Una carrera tampoco sobrescribe.
    (salida / "imagen.png").write_bytes(contenido)
    (salida / "config.json").write_bytes(configuracion.encode("utf-8"))
    (salida / "registro.json").write_bytes(registro_bytes)
    return salida / "registro.json"


def _sin_duplicados(pares):
    objeto = {}
    for clave, valor in pares:
        if clave in objeto:
            raise ValueError(f"Clave duplicada en config: {clave}")
        objeto[clave] = valor
    return objeto


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrada", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--salida", required=True, type=Path, help="Carpeta nueva")
    args = parser.parse_args(argv)
    try:
        with args.config.open("rb") as archivo:
            texto = archivo.read(65_537)
        if len(texto) > 65_536:
            raise ValueError("Config supera 64 KiB.")
        config = json.loads(texto.decode("utf-8-sig"), object_pairs_hook=_sin_duplicados)
        registro = procesar_imagen(args.entrada, config, args.salida)
    except (OSError, ValueError, TypeError, OverflowError, RecursionError,
            Image.DecompressionBombWarning, Image.DecompressionBombError) as error:
        print(f"Preprocesamiento no completado: {error}", file=sys.stderr)
        return 1
    print(f"Imagen y transformación trazables: {registro}")
    print("Escala métrica y mejora de precisión de visión no determinadas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
