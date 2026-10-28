"""Recortes PDF/raster con coordenadas trazables; sin inferir escala estructural."""

from __future__ import annotations

import hashlib
from io import BytesIO
import json
import math
import stat
from pathlib import Path
from uuid import uuid4

import pymupdf
from PIL import Image, ImageOps

from .ingreso import file_hash

MAX_BYTES_RASTER = 128 * 1024 * 1024
MAX_PIXELES_RASTER = 40_000_000
MAX_PIXELES_RECORTE = 8_000_000
ESPACIO_RASTER = 'raster_px_exif_orientado'


def _sin_enlace(path):
    info = path.lstat()
    if (path.resolve() != path or stat.S_ISLNK(info.st_mode)
            or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)):
        raise ValueError('Archivo o directorio enlazado no permitido.')
    return path


def cargar_raster_orientado(origen: Path):
    """RGB EXIF-orientado y matrices de bordes de píxel; el llamador cierra la imagen."""
    origen = _sin_enlace(Path(origen).absolute())
    with origen.open('rb') as stream:
        raw = stream.read(MAX_BYTES_RASTER + 1)
    if len(raw) > MAX_BYTES_RASTER:
        raise ValueError('El original raster excede 128 MiB.')
    with Image.open(BytesIO(raw)) as image:
        if (image.format not in {'JPEG', 'PNG'} or image.width * image.height > MAX_PIXELES_RASTER
                or getattr(image, 'n_frames', 1) != 1):
            raise ValueError('Raster no admitido: JPEG/PNG estático de hasta 40 millones de píxeles.')
        width, height = image.size
        orientation = image.getexif().get(274, 1)
        if type(orientation) is not int or orientation not in range(1, 9):
            raise ValueError('Orientación EXIF no admitida.')
        dpi = image.info.get('dpi')
        image.load()
        visible = ImageOps.exif_transpose(image).convert('RGB')
    matrices = {1:[1,0,0,1,0,0], 2:[-1,0,0,1,width,0],
        3:[-1,0,0,-1,width,height], 4:[1,0,0,-1,0,height],
        5:[0,1,1,0,0,0], 6:[0,1,-1,0,height,0],
        7:[0,-1,-1,0,height,width], 8:[0,-1,1,0,0,width]}
    a,b,c,d,e,f = matrices[orientation]; det = a*d-b*c
    inverse = [d/det,-b/det,-c/det,a/det,(c*f-d*e)/det,(b*e-a*f)/det]
    return visible, {'tipo_fuente':'raster','espacio_pagina_visible':ESPACIO_RASTER,
        'pagina_visible_px':list(visible.size),'dimensiones_original_px':[width,height],
        'orientacion_exif':orientation,'dpi_original_declarado':list(dpi) if dpi else None,
        'original_a_pagina_visible_px':matrices[orientation], 'pagina_visible_a_original_px':inverse}


def renderizar_recorte_raster(origen: Path, bbox):
    """Render determinista para generar/verificar un recorte en píxeles visibles."""
    image, metadata = cargar_raster_orientado(origen)
    try:
        return _renderizar_imagen_raster(image, metadata, bbox)
    finally:image.close()


def _renderizar_imagen_raster(image, metadata, bbox):
    """Único core de recorte/reducción para raster original y derivado."""
    if (not isinstance(bbox, (list,tuple)) or len(bbox) != 4
            or any(type(v) not in (int,float) or not math.isfinite(v) for v in bbox)
            or not (0 <= bbox[0] < bbox[2] <= 1 and 0 <= bbox[1] < bbox[3] <= 1)):
        raise ValueError('Región raster normalizada inválida.')
    width, height = image.size
    box = [math.floor(bbox[0]*width),math.floor(bbox[1]*height),
           math.ceil(bbox[2]*width),math.ceil(bbox[3]*height)]
    crop = image.crop(box)
    try:
        if crop.width*crop.height > MAX_PIXELES_RECORTE:
            factor = math.sqrt(MAX_PIXELES_RECORTE/(crop.width*crop.height))
            w,h = max(1,math.floor(crop.width*factor)),max(1,math.floor(crop.height*factor))
            if w*h > MAX_PIXELES_RECORTE:  # imágenes extremadamente estrechas
                if h >= w:h = max(1,MAX_PIXELES_RECORTE//w)
                else:w = max(1,MAX_PIXELES_RECORTE//h)
            resized = crop.resize((w,h),Image.Resampling.LANCZOS); crop.close(); crop = resized
        metadata.update({'bbox_pagina_visible_px':box,'dimensiones_px':list(crop.size),
            'pixel_a_pagina_visible':[(box[2]-box[0])/crop.width,0,0,(box[3]-box[1])/crop.height,box[0],box[1]],
            'remuestreo':'LANCZOS_si_reduccion','escala_geometrica':None})
        output = BytesIO(); crop.save(output,format='PNG')
        return output.getvalue(), metadata
    finally:crop.close()


def renderizar_recorte_preprocesado(expediente, identificador, bbox):
    """Recorte de derivado verificado, mapeado al ORIGINAL EXIF sin orientarlo otra vez."""
    from .revision_preprocesamiento import consultar_preprocesamiento
    from .preprocesamiento import _producto, invertir_matriz, transformar_punto
    consulta = consultar_preprocesamiento(expediente, identificador)
    with Image.open(BytesIO(consulta['imagen_bytes'])) as image:
        # El PNG contiene píxeles explícitos y no conserva EXIF. Nunca exif_transpose.
        data, crop = _renderizar_imagen_raster(image, {}, bbox)
    original = consulta['registro']['exif_original']
    a,b,c,d,e,f = original['original_a_pagina_visible_px']
    exif = [[a,c,e],[b,d,f],[0,0,1]]
    a,b,c,d,e,f = crop['pixel_a_pagina_visible']
    pixel_a_derivado = [[a,c,e],[b,d,f],[0,0,1]]
    homografia = _producto(exif, _producto(consulta['transformacion']['salida_a_origen'], pixel_a_derivado))
    width, height = crop['dimensiones_px']
    poligono = [list(transformar_punto(homografia,x,y)) for x,y in ((0,0),(width,0),(width,height),(0,height))]
    pw,ph = original['pagina_visible_px']
    normalizado = [min(p[0] for p in poligono)/pw,min(p[1] for p in poligono)/ph,
                   max(p[0] for p in poligono)/pw,max(p[1] for p in poligono)/ph]
    if any(x < -1e-9 or x > 1+1e-9 for x in normalizado):
        raise ValueError('La región preprocesada sale del dominio del original.')
    normalizado = [min(1.,max(0.,x)) for x in normalizado]
    # La reproducción anterior no acredita que la fuente siguiera igual al
    # terminar el recorte/reducción. Volver a comprobar la versión exacta.
    consultar_preprocesamiento(expediente, identificador)
    return data, {**original, 'tipo_fuente':'raster_preprocesado',
        'preprocesamiento_archivo_id':consulta['registro']['archivo_id'],
        'preprocesamiento_id':identificador, 'preprocesamiento_registro_sha256':identificador,
        'preprocesamiento_imagen_sha256':consulta['registro']['imagen_sha256'],
        'bbox_normalizada':normalizado, 'bbox_derivado_normalizada':list(bbox),
        'dimensiones_derivado_px':consulta['transformacion']['dimensiones_salida_px'],
        'bbox_derivado_px':crop['bbox_pagina_visible_px'],
        'pixel_a_derivado_px':crop['pixel_a_pagina_visible'],
        'pixel_a_pagina_visible':homografia, 'pagina_visible_a_pixel':invertir_matriz(homografia),
        'poligono_pagina_visible_px':poligono,
        'dimensiones_px':crop['dimensiones_px'], 'remuestreo':crop['remuestreo'],
        'escala_geometrica':None, 'tipo_transformacion':'homografia_3x3'}


def punto_a_pagina(metadata: dict, x: float, y: float) -> tuple[float, float]:
    """Píxel de recorte a página visible: puntos PDF o px EXIF, declarados en metadata."""
    if metadata.get('tipo_fuente') == 'raster_preprocesado':
        from .preprocesamiento import transformar_punto
        return transformar_punto(metadata['pixel_a_pagina_visible'],x,y)
    a, b, c, d, e, f = metadata["pixel_a_pagina_visible"]
    return a * x + c * y + e, b * x + d * y + f


def generar_recorte(
    manifest_path: Path,
    archivo_id: str,
    pagina: int,
    bbox: list[float],
    *,
    dpi: int = 150,
    etiqueta: str = "region",
    preprocesamiento_id: str | None = None,
) -> Path:
    """bbox=[x0,y0,x1,y1] normalizada sobre la página visible (rotación aplicada)."""
    if isinstance(pagina, bool) or not isinstance(pagina, int) or pagina < 1:
        raise ValueError("Página debe ser un entero positivo, empezando en 1.")
    if isinstance(dpi, bool) or not isinstance(dpi, int) or not 72 <= dpi <= 300:
        raise ValueError("DPI debe ser un entero entre 72 y 300.")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4 or any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in bbox
    ):
        raise ValueError("bbox requiere cuatro números finitos.")
    x0, y0, x1, y1 = bbox
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise ValueError("bbox debe tener área positiva y permanecer entre 0 y 1.")
    if not isinstance(etiqueta, str) or not etiqueta.strip():
        raise ValueError("Etiqueta debe ser texto no vacío.")
    manifest_path = _sin_enlace(Path(manifest_path).absolute())
    case_dir = manifest_path.parent
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    entries = [e for e in manifest["archivos"] if e["id"] == archivo_id]
    if len(entries) != 1:
        raise ValueError("Identificador de archivo ausente o ambiguo.")
    entry = entries[0]
    source = _sin_enlace(case_dir / entry["archivo"])
    if not source.is_relative_to(case_dir):
        raise ValueError("El original sale del expediente.")
    if file_hash(source) != entry["sha256"]:
        raise ValueError("Hash del original incompatible con el registro.")
    if preprocesamiento_id is not None and source.suffix.lower() not in {'.png','.jpg','.jpeg'}:
        raise ValueError('Preprocesamiento solo admite original raster registrado.')
    if source.suffix.lower() in {'.png','.jpg','.jpeg'}:
        if pagina != 1:
            raise ValueError('Un original raster tiene una única página.')
        if preprocesamiento_id is None:
            image_bytes, raster = renderizar_recorte_raster(source,bbox)
        else:
            from .revision_preprocesamiento import consultar_preprocesamiento
            consulta = consultar_preprocesamiento(manifest_path, preprocesamiento_id)
            if consulta['registro']['archivo_id'] != archivo_id:
                raise ValueError('Derivado de otro original.')
            image_bytes, raster = renderizar_recorte_preprocesado(manifest_path,preprocesamiento_id,bbox)
        region_id = uuid4().hex
        metadata = {'version':'0.1.0','id':region_id,'caso':manifest['id'],
            'archivo_id':archivo_id,'pagina':1,'etiqueta':etiqueta,'origen_sha256':entry['sha256'],
            'expediente_sha256':hashlib.sha256(manifest_bytes).hexdigest(),
            'alcance':manifest.get('alcance',{'estado':'pendiente_verificar'}),
            'sistema_coordenadas':'pagina_visible_normalizada','bbox_normalizada':list(bbox),
            **raster,'imagen':'recorte.png','imagen_sha256':hashlib.sha256(image_bytes).hexdigest(),
            'estado':'pendiente_revision'}
    elif source.suffix.lower() == '.pdf':
      with pymupdf.open(source) as doc:
        if doc.needs_pass:
            raise ValueError("PDF protegido; no se desbloquea automáticamente.")
        if pagina > doc.page_count:
            raise ValueError("La página solicitada no existe.")
        page = doc.load_page(pagina - 1)
        bounds = page.rect
        clip = pymupdf.Rect(x0 * bounds.width, y0 * bounds.height, x1 * bounds.width, y1 * bounds.height)
        zoom = dpi / 72
        max_pixels = 8_000_000
        while (math.ceil(clip.width * zoom) + 2) * (math.ceil(clip.height * zoom) + 2) > max_pixels:
            zoom *= 0.9
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip, alpha=False)
        if not pix.width or not pix.height:
            raise ValueError("La región no produce un recorte utilizable.")
        pix.set_dpi(max(1, round(72 * zoom)), max(1, round(72 * zoom)))
        image_bytes = pix.tobytes("png")
        region_id = uuid4().hex
        metadata = {
            "version": "0.1.0",
            "id": region_id,
            "caso": manifest["id"],
            "archivo_id": archivo_id,
            "pagina": pagina,
            "etiqueta": etiqueta,
            "origen_sha256": entry["sha256"],
            "expediente_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "alcance": manifest.get("alcance", {"estado": "pendiente_verificar"}),
            "sistema_coordenadas": "pagina_visible_normalizada",
            "bbox_normalizada": list(bbox),
            "pagina_visible_pt": [bounds.width, bounds.height],
            "bbox_pagina_visible_pt": list(clip),
            "bbox_pagina_sin_rotacion_pt": list(clip * page.derotation_matrix),
            "pagina_visible_a_sin_rotacion": list(page.derotation_matrix),
            "rotacion_pdf_grados": page.rotation,
            "dpi_solicitado": dpi,
            "dpi_render_aproximado": 72 * zoom,
            "dimensiones_px": [pix.width, pix.height],
            "pixel_a_pagina_visible": [1 / zoom, 0, 0, 1 / zoom, pix.x / zoom, pix.y / zoom],
            "imagen": "recorte.png",
            "imagen_sha256": hashlib.sha256(image_bytes).hexdigest(),
            "estado": "pendiente_revision",
            "escala_geometrica": None,
        }
    else:
        raise ValueError('Formato de original no admitido.')
    if file_hash(source) != entry["sha256"] or manifest_path.read_bytes() != manifest_bytes:
        raise ValueError("El original cambió durante el renderizado.")
    group = case_dir / 'recortes'
    if group.exists() or group.is_symlink():
        _sin_enlace(group)
    else:group.mkdir()
    output = group / region_id
    output.mkdir(parents=True, exist_ok=False)
    with (output / 'recorte.png').open('xb') as stream:
        stream.write(image_bytes)
    json_path = output / "recorte.json"
    with json_path.open('x',encoding='utf-8') as stream:
        stream.write(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
    if preprocesamiento_id is not None:
        consultar_preprocesamiento(manifest_path,preprocesamiento_id)
        if file_hash(source) != entry['sha256'] or manifest_path.read_bytes() != manifest_bytes:
            raise ValueError('Las fuentes cambiaron durante la publicación del recorte.')
    return json_path
