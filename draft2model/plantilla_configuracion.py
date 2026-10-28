"""Ayudas de autoría SIN programar para configuraciones 0.4/0.5 a partir de una geometría 0.3 versionada.

- `documento_conexiones`: liga una declaración revisada de bordes conectados a la geometría exacta
  (SHA canónico + huella de contenido) y calcula `huella_conexiones`; valida con el módulo de compatibilidad.
- `borrador`: configuración en BORRADOR con identidad, origen geométrico, un punto por vértice, asignación de cada
  superficie SIN sección y listas técnicas vacías. No inventa materiales, secciones, cargas, apoyos ni diafragmas:
  el validador enumera lo que falta y la preparación de malla lista las políticas de nodos.

CLI:
  python -m draft2model.plantilla_configuracion borrador --raiz data/private --caso C --geometria V [--version 0.4.0|0.5.0] --salida cfg.json
  python -m draft2model.plantilla_configuracion conexiones --raiz data/private --caso C --geometria V --entrada bordes.json --salida cx.json
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

from . import compatibilidad_particiones as cp
from . import gestion_geometria as gg
from . import modelo_estructural as m
from . import particion_superficies as ps
from .validacion_geometria import validar_geometria


class ErrorPlantilla(ValueError):
    pass


def documento_conexiones(geometria: dict, conexiones: list, fuentes: list, declaracion: dict, ident: str = "CX1") -> dict:
    """`declaracion` = {declarado_por, fecha, alcance}; identidad declarada_no_verificada. Valida reproduciendo la compatibilidad."""
    vg = validar_geometria(copy.deepcopy(geometria))
    if not vg.consistente:
        raise ErrorPlantilla("Geometría inconsistente; no se ligan conexiones.")
    if not isinstance(declaracion, dict) or set(declaracion) != {"declarado_por", "fecha", "alcance"}:
        raise ErrorPlantilla("declaracion requiere exactamente declarado_por, fecha y alcance.")
    doc = {"contrato": "draft2model.conexiones_borde", "version_contrato": "0.1.0", "id": ident,
           "geometria": {"sha256_geometria_canonica": cp._sha(geometria), "huella_contenido": vg.huella_contenido},
           "conexiones": copy.deepcopy(conexiones), "fuentes": copy.deepcopy(fuentes),
           "declaracion": {**declaracion, "identidad": "declarada_no_verificada"}}
    doc["declaracion"]["huella_conexiones"] = cp.huella_conexiones(doc)
    hosts = sorted({lado["superficie"] for c in conexiones for lado in (c["a"], c["b"])}) if conexiones else []
    try:
        partes = [ps.particionar_superficie(geometria, h) for h in hosts]
        if partes:
            cp.compatibilizar_particiones(geometria, partes, doc)
    except (ps.ErrorParticion, cp.ErrorCompatibilidad, KeyError, TypeError) as exc:
        raise ErrorPlantilla(f"Conexiones no reproducibles con esta geometría: {exc}") from None
    return doc


def borrador(raiz: Path, caso: str, version_geometria: str, *, version_contrato: str = m.VERSION_MALLA) -> dict:
    if version_contrato not in (m.VERSION_MALLA, m.VERSION_LIQUIDOS):
        raise ErrorPlantilla("Borrador disponible para configuraciones 0.4.0 o 0.5.0.")
    consulta = gg.consultar_version(Path(raiz), caso, version_geometria)
    geo, comp = consulta.geometria, consulta.comprobacion
    if geo.get("version_contrato") != "0.3.0":
        raise ErrorPlantilla("Se requiere geometría 0.3.0 (superficies y aberturas).")
    data = {
        "contrato": m.CONTRATO, "version_contrato": version_contrato, "id": caso + "-config", "caso": caso,
        "datos_sinteticos": geo.get("datos_sinteticos") is True,
        "unidades": {"longitud": "m", "fuerza": "kN", "tiempo": "s", "temperatura": "C"},
        "geometria_origen": {"version_id": version_geometria, "sha256_geometria": comp.sha256_geometria, "huella_contenido": comp.huella_contenido},
        "plantilla": None, "fuentes": [], "hipotesis": [], "sitio": None, "materiales": [], "secciones": [],
        "puntos": [{"id": v["id"], "vertice_geometria": v["id"]} for v in geo["vertices"]],
        "vertices_compartidos": [], "frames": [], "asignaciones_muros": [], "asignaciones_frames": [],
        "asignaciones_superficies": [{"objetivo": s["id"], "seccion": None, "fuente": None} for s in geo["superficies"]],
        "patrones": [], "cargas": [], "masa": None, "apoyos": [], "diafragmas": [], "sin_diafragma": [], "espectros": [],
        "casos": [], "combinaciones": [], "analisis": None, "faltantes": [],
        # Sin declarante/fecha de relleno: el validador lo exige hasta generarlo con `conexiones` desde la declaración revisada.
        "conexiones_borde": None,
        "malla": {"estrategia": m.mp.ESTRATEGIA, "fuente": None}, "cortes_nivel": [], "nodos_derivados": [], "subdivision_frames": [],
        "revision": {"estado": "borrador", "aprobacion": None},
    }
    if version_contrato == m.VERSION_LIQUIDOS:
        data["liquidos"] = {"aplicabilidad": "informacion_insuficiente", "fuente": None,
                            "motivo": "Existencia de cisterna/tanque por revisar en los planos; no se asume ausencia.", "declaraciones": []}
    return data


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="op", required=True)
    for nombre in ("borrador", "conexiones"):
        s = sub.add_parser(nombre)
        s.add_argument("--raiz", type=Path, required=True); s.add_argument("--caso", required=True)
        s.add_argument("--geometria", required=True); s.add_argument("--salida", type=Path, required=True)
        if nombre == "borrador":
            s.add_argument("--version", choices=(m.VERSION_MALLA, m.VERSION_LIQUIDOS), default=m.VERSION_MALLA)
        else:
            s.add_argument("--entrada", type=Path, required=True, help="JSON {conexiones, fuentes, declaracion:{declarado_por,fecha,alcance}}")
    a = ap.parse_args(argv)
    try:
        if a.op == "borrador":
            out = borrador(a.raiz, a.caso, a.geometria, version_contrato=a.version)
        else:
            entrada = json.loads(a.entrada.read_text(encoding="utf-8"))
            geo = gg.consultar_version(a.raiz, a.caso, a.geometria).geometria
            out = documento_conexiones(geo, entrada["conexiones"], entrada["fuentes"], entrada["declaracion"], entrada.get("id", "CX1"))
        with open(a.salida, "x", encoding="utf-8") as f:
            f.write(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
        print(f"Escrito {a.salida} (no aprobado; revíselo en el editor de configuración).")
        return 0
    except (ErrorPlantilla, ValueError, OSError, KeyError) as exc:
        print("No generado: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
