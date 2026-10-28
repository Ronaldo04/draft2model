"""Ejemplo reproducible enteramente sintético, sin proveedor de visión ni ETABS."""

import argparse
import copy
import json
from pathlib import Path

import pymupdf

from draft2model.conversion_geometria import convertir_lecturas
from draft2model.gestion_extraccion import importar_extraccion, corregir_version
from draft2model.gestion_geometria import importar_geometria
from draft2model.ingreso import registrar_expediente
from draft2model.revision_documental import revisar_expediente


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raiz", required=True, type=Path)
    parser.add_argument("--caso", default="conversion-demo-sintetica")
    args = parser.parse_args(argv)
    # Se conservan las fuentes auxiliares dentro de la raíz elegida; no se sobrescriben casos.
    if (args.raiz / args.caso).exists():
        parser.error("El caso ya existe; use otro --caso o una raíz nueva.")
    trabajo = args.raiz / f"fuentes-{args.caso}"
    trabajo.mkdir(parents=True, exist_ok=False)
    pdf = trabajo / "plano_sintetico.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page(width=400, height=300)
        page.draw_rect((50, 50, 350, 250))
        page.insert_text((55, 75), "SINTETICO: altura 260 cm; longitud 400 cm; espesor 15 cm")
        doc.save(pdf)
    expediente = registrar_expediente(args.caso, [pdf], args.raiz, uso_autorizado=True, provisional_fuera_alcance=True)
    revisar_expediente(expediente, max_lado=256)
    registrado = json.loads(expediente.read_bytes())
    evidencia = {"archivo_id": "L0001", "pagina": 1, "original_sha256": registrado["archivos"][0]["sha256"],
                 "bbox_normalizada": [0.1, 0.1, 0.9, 0.9]}
    valores = [("C001", "cota", 260, "cm"), ("C004", "elemento", "muro", "no_aplica"),
               ("C005", "cota", 15, "cm"), ("C006", "cota", 400, "cm")]
    lectura = {
        "contrato": "draft2model.extraccion_preliminar", "version_contrato": "0.1.0", "caso": args.caso,
        "procedencia": {"tipo": "expediente", "descripcion": "Contenedor de un PDF SINTÉTICO creado por este ejemplo."},
        "alcance": registrado["alcance"], "sistema_coordenadas": "pagina_visible_normalizada",
        "candidatos": [{"id": ident, "tipo": tipo, "valor_propuesto": valor, "unidad": unidad,
                        "metodo": {"tipo": "sintetico"}, "evidencia": [copy.deepcopy(evidencia)]}
                       for ident, tipo, valor, unidad in valores],
    }
    entrada = trabajo / "lecturas.json"
    entrada.write_text(json.dumps(lectura, ensure_ascii=False, indent=2), encoding="utf-8")
    version = importar_extraccion(args.raiz, args.caso, entrada)
    for ident, _, valor, unidad in valores:
        version = corregir_version(args.raiz, args.caso, version.identificador, ident,
                                   estado="revisado", motivo="Lectura SINTÉTICA reproducible del ejemplo.",
                                   fecha="2026-10-16", revisor_declarado="Operador SINTÉTICO del ejemplo",
                                   valor_revisado=valor, unidad_revisada=unidad)
    manifest = json.loads(Path(__file__).with_name("manifiesto.json").read_bytes())
    manifest["caso"] = args.caso
    manifiesto = trabajo / "manifiesto.json"
    manifiesto.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    conversion = convertir_lecturas(args.raiz, args.caso, version.identificador, manifiesto)
    geometria = importar_geometria(args.raiz, args.caso, conversion.ruta / "geometria.json")
    print(json.dumps({"caso": args.caso, "extraccion_id": version.identificador,
                      "conversion_id": conversion.identificador, "ruta_conversion": str(conversion.ruta.resolve()),
                      "geometria_id": geometria.identificador, "comprobacion_correcta": geometria.comprobacion.correcta,
                      "disponible_para_modelado": geometria.comprobacion.validacion["disponible_para_modelado"],
                      "datos_sinteticos": True}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
