"""Caso sintético aislado para comprobar interfaz; no valida ingeniería."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pymupdf
from draft2model.ingreso import registrar_expediente
from draft2model.gestion_geometria import importar_geometria


def main():
    root = Path(__file__).resolve().parents[1]
    work = root / 'tmp/demo_integrado'
    work.mkdir(parents=True, exist_ok=True)
    private = work / 'private'
    case = private / 'sintetico-001'
    if case.exists():
        print('Demostración ya existente; se conserva: ' + str(case))
        return
    with pymupdf.open() as doc:
        page = doc.new_page(width=600, height=460)
        page.insert_text((50, 40), 'DRAFT2MODEL - PLANO SINTETICO - NO ES UN CASO REAL', fontsize=12)
        page.draw_rect(pymupdf.Rect(100, 100, 500, 400), width=3)
        page.insert_text((280, 90), '4.0 m', fontsize=14)
        page.insert_text((45, 250), '3.0 m', fontsize=14)
        doc.save(work / 'plano_sintetico.pdf')
    registrar_expediente('sintetico-001', [work / 'plano_sintetico.pdf'], private,
                         uso_autorizado=True, provisional_fuera_alcance=True)
    result = importar_geometria(private, 'sintetico-001', root / 'examples/geometria_sintetica.json')
    print(json.dumps({'raiz': str(private), 'caso': 'sintetico-001', 'version': result.identificador}))


if __name__ == '__main__':
    main()
