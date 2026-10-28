"""Pruebas sintéticas focales del servicio persistente `ServicioDigitizacion` (Encargo 353).

Sin red, sin APIs externas, sin claves, sin ETABS y sin planos piloto reales.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image
import pymupdf

from draft2model import gestion_geometria as gg
from draft2model.ingreso import registrar_expediente
from draft2model.recortes import generar_recorte
from draft2model.revision_digitizacion import (
    CARPETA,
    ErrorRevisionDigitizacion,
    ServicioDigitizacion,
    _bytes,
    _huella,
)
from draft2model.revision_documental import revisar_expediente
from draft2model.revision_visual import RevisionLocal

ROOT = Path(__file__).resolve().parents[1]
TMP_BASE = ROOT / "tmp" / "antigravity356"
CASO = "dig-sintetico-353"


def _limites_validos() -> dict[str, float]:
    return {
        "residuo_ajuste_max_m": 0.02,
        "error_control_max_m": 0.03,
        "incertidumbre_max_m": 0.15,
        "localizacion_uv": 0.002,
        "referencia_m": 0.002,
        "condicion_max": 25.0,
        "escala_min_m_por_uv": 1.0,
        "escala_max_m_por_uv": 50.0,
        "coordenada_abs_max_m": 500.0,
    }


def _geometria_v03_base(
    caso: str = CASO,
    *,
    sintetica: bool = True,
    con_referencias_doc: bool = False,
    otra_lamina_en_v4: str | None = None,
) -> dict:
    tipo_proc = "sintetico" if sintetica else "plano"
    proc_raiz = {
        "tipo": tipo_proc,
        "descripcion": "Fixture sintética 0.3.0 para digitización calibrada." if sintetica else "Geometría de prueba.",
    }

    def p_vert(vid: str, refs: list[str] | None = None, lamina: str | None = None) -> dict:
        d = copy.deepcopy(proc_raiz)
        if con_referencias_doc and refs:
            d["referencias"] = refs
        if lamina:
            d["lamina"] = lamina
        return d

    # Planta z=0 con 6 vértices (VA..VF) y techo z=2.8 con 4 vértices; además cumbrera z=4.0 con solo 2 vértices (VK1, VK2).
    # Escala exacta en dibujo: x = 10 * u, y = 8 * (1 - v)  => u = x / 10, v = 1 - y / 8
    vertices = [
        {"id": "VA", "x": 1.0, "y": 1.0, "z": 0.0, "procedencia": p_vert("VA", ["COTA_AX", "COTA_AY"])},
        {"id": "VB", "x": 9.0, "y": 1.0, "z": 0.0, "procedencia": p_vert("VB", ["COTA_BX", "COTA_AY"])},
        {"id": "VC", "x": 9.0, "y": 7.0, "z": 0.0, "procedencia": p_vert("VC", ["COTA_BX", "COTA_CY"])},
        {
            "id": "VD",
            "x": 1.0,
            "y": 7.0,
            "z": 0.0,
            "procedencia": p_vert("VD", ["CTRL_DX", "CTRL_DY"], lamina=otra_lamina_en_v4),
        },
        {"id": "VE", "x": 5.0, "y": 1.0, "z": 0.0, "procedencia": p_vert("VE", ["CTRL_EX", "CTRL_EY"])},
        {"id": "VF", "x": 5.0, "y": 5.0, "z": 0.0, "procedencia": p_vert("VF", ["CTRL_FX", "CTRL_FY"])},
        # Vértices en z = 2.8 (otro plano)
        {"id": "VT1", "x": 1.0, "y": 1.0, "z": 2.8, "procedencia": p_vert("VT1", ["SUP_1"])},
        {"id": "VT2", "x": 9.0, "y": 1.0, "z": 2.8, "procedencia": p_vert("VT2", ["SUP_2"])},
        {"id": "VT3", "x": 9.0, "y": 7.0, "z": 2.8, "procedencia": p_vert("VT3", ["SUP_3"])},
        {"id": "VT4", "x": 1.0, "y": 7.0, "z": 2.8, "procedencia": p_vert("VT4", ["SUP_4"])},
        # Solo 2 vértices coplanares en z = 4.0 (para probar insuficiencia de referencias en un plano existente)
        {"id": "VK1", "x": 1.0, "y": 4.0, "z": 4.0, "procedencia": p_vert("VK1", ["CUM_1"])},
        {"id": "VK2", "x": 9.0, "y": 4.0, "z": 4.0, "procedencia": p_vert("VK2", ["CUM_2"])},
    ]
    superficies = [
        {
            "id": "LOSA_BASE",
            "vertices": ["VA", "VB", "VC", "VD"],
            "papel_geometrico": "losa de fondo sintética",
            "procedencia": p_vert("LOSA_BASE", ["LOSA_REF_1"]),
        },
        {
            "id": "LOSA_SUP",
            "vertices": ["VT1", "VT2", "VT3", "VT4"],
            "papel_geometrico": "losa superior sintética",
            "procedencia": p_vert("LOSA_SUP", ["LOSA_REF_2"]),
        },
        {
            "id": "FALDON_1",
            "vertices": ["VT1", "VT2", "VK2", "VK1"],
            "papel_geometrico": "faldón inclinado sintético",
            "procedencia": p_vert("FALDON_1", ["FALDON_REF_1"]),
        },
    ]
    return {
        "contrato": "draft2model.geometria",
        "version_contrato": "0.3.0",
        "id": caso,
        "unidad_longitud": "m",
        "procedencia": proc_raiz,
        "niveles": [],
        "nodos": [],
        "muros": [],
        "vertices": vertices,
        "superficies": superficies,
        "aberturas": [],
        "faltantes": [],
        "revision": {"estado": "borrador", "aprobacion": None},
    }


def _uv_desde_xy(x: float, y: float) -> list[float]:
    return [x / 10.0, 1.0 - (y / 8.0)]


class RevisionDigitizacionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        TMP_BASE.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls) -> None:
        if TMP_BASE.exists():
            shutil.rmtree(TMP_BASE, ignore_errors=True)

    def setUp(self) -> None:
        for destino in ("subprocess.Popen", "urllib.request.urlopen", "socket.create_connection"):
            guardia = patch(destino, side_effect=AssertionError("Red y subprocesos prohibidos en pruebas 356"))
            guardia.start()
            self.addCleanup(guardia.stop)

        tmp = tempfile.TemporaryDirectory(prefix="t356-", dir=TMP_BASE)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()

        pdf_path = self.root / "lamina_1.pdf"
        with pymupdf.open() as doc:
            p1 = doc.new_page(width=300, height=240)
            p1.insert_text((30, 40), "PLANTA SINTETICA Z=0")
            p2 = doc.new_page(width=300, height=240)
            p2.insert_text((30, 40), "ELEVACION SINTETICA")
            doc.save(pdf_path)

        png_path = self.root / "detalle_2.png"
        Image.new("RGB", (200, 160), color=(245, 245, 245)).save(png_path, format="PNG")

        registrar_expediente(
            CASO,
            [pdf_path, png_path],
            self.root / "casos",
            uso_autorizado=True,
            provisional_fuera_alcance=True,
        )
        self.app = RevisionLocal(self.root / "casos")
        self.svc = ServicioDigitizacion(self.app)
        self.case_dir, self.manifest, self.fp = self.app.expediente(CASO)
        self.id_pdf = self.manifest["archivos"][0]["id"]
        self.sha_pdf = self.manifest["archivos"][0]["sha256"]
        self.id_png = self.manifest["archivos"][1]["id"]
        self.sha_png = self.manifest["archivos"][1]["sha256"]

    def _importar_geo(self, datos: dict) -> tuple[str, dict]:
        ruta = self.root / f"geo-{hashlib.sha256(_bytes(datos)).hexdigest()[:10]}.json"
        ruta.write_bytes(_bytes(datos))
        res = gg.importar_geometria(self.app.raiz, CASO, ruta)
        actual = self.app.geometria(CASO, res.identificador)
        return res.identificador, actual

    def _plano_z0(self, unidad: str = "m", cota: float = 0.0, pid: str = "PL_Z0") -> dict:
        return {
            "id": pid,
            "ejes": ["x", "y"],
            "eje_constante": "z",
            "valor_constante": cota,
            "unidad_longitud": unidad,
        }

    def _fuente_base(self, *, con_sha: bool = True, bbox: list[float] | None = None, pagina: int = 1) -> dict:
        f = {
            "original_id": self.id_pdf,
            "pagina": pagina,
            "dibujo_id": "PLANTA_Z0",
            "bbox_pagina": bbox or [0.0, 0.0, 1.0, 1.0],
        }
        if con_sha:
            f["sha256"] = self.sha_pdf
        return f

    def test_flujo_completo_sin_vinculo_documental_conserva_borrador_pendientes_y_naturaleza(self) -> None:
        geo_id, geo_actual = self._importar_geo(_geometria_v03_base(sintetica=True, con_referencias_doc=False))
        geos_antes = self.app.geometrias(CASO)

        prep = self.svc.preparar({
            "caso": CASO,
            "expediente_sha256": self.fp,
            "geometria": geo_id,
            "huella_geometria": geo_actual["huella"],
            "sha256_geometria": geo_actual["sha256_geometria"],
            "fuente": self._fuente_base(con_sha=False),
            "plano": self._plano_z0(),
        })
        self.assertEqual(prep["etapa"], "preparada")
        self.assertTrue(prep["datos_sinteticos"])
        self.assertEqual(prep["fuente_vigente"]["sha256"], self.sha_pdf)
        self.assertFalse(prep["aprueba_ingenieria"] or prep["disponible_para_modelado"] or prep["ejecuta_etabs"])
        codigos_prep = {p["codigo"] for p in prep["pendientes"]}
        self.assertIn("carencia_vinculo_documental_puntos", codigos_prep)

        calc = self.svc.calcular({
            "caso": CASO,
            "expediente_sha256": self.fp,
            "geometria": geo_id,
            "huella_geometria": geo_actual["huella"],
            "sha256_geometria": geo_actual["sha256_geometria"],
            "preparacion_id": prep["id"],
            "huella_preparacion": prep["huella_version"],
            "propuesta_id": "PROP_BORRADOR_1",
            "fuente": prep["fuente_vigente"],
            "plano": self._plano_z0(),
            "limites": _limites_validos(),
            "anclas": [
                {"id": "A1", "punto_resuelto": "VA", "uv_local": _uv_desde_xy(1.0, 1.0)},
                {"id": "A2", "punto_resuelto": "VB", "uv_local": _uv_desde_xy(9.0, 1.0)},
                {"id": "A3", "punto_resuelto": "VC", "uv_local": _uv_desde_xy(9.0, 7.0)},
            ],
            "controles": [],
            "puntos": [
                {"id": "PN_CENTRO", "uv_local": _uv_desde_xy(5.0, 4.0), "relacionados": ["VA", "VB", "VC"]},
            ],
        })
        self.assertEqual(calc["etapa"], "calculada")
        self.assertTrue(calc["datos_sinteticos"])
        self.assertEqual(calc["revision"], {"estado": "borrador", "aprobacion": None})
        self.assertFalse(calc["disponible_para_modelado"])
        self.assertFalse(calc["aprueba_ingenieria"])
        self.assertTrue(calc["resumen"]["calculo_posible"])
        self.assertFalse(calc["resumen"]["contraste_en_controles"])
        self.assertFalse(calc["resumen"]["exactitud_documental_acreditada"])
        self.assertTrue(calc["resumen"]["carencia_vinculo_documental"])
        self.assertTrue(calc["resumen"]["ajuste_tres_anclas_sin_verificacion"])

        codigos_calc = {p["codigo"] for p in calc["pendientes"]}
        self.assertIn("carencia_vinculo_documental_puntos", codigos_calc)
        self.assertIn("ajuste_exacto_tres_anclas_sin_verificacion", codigos_calc)

        pt = calc["resultado"]["puntos"][0]
        self.assertAlmostEqual(pt["coordenadas_m"]["x"], 5.0, places=9)
        self.assertAlmostEqual(pt["coordenadas_m"]["y"], 4.0, places=9)
        self.assertAlmostEqual(pt["coordenadas_m"]["z"], 0.0, places=9)

        # Persistencia, consulta e historial sin modificar geometría ni filtrar rutas locales
        reabierto = self.svc.consultar(CASO, self.fp, calc["id"])
        self.assertEqual(reabierto["huella_version"], calc["huella_version"])
        listado = self.svc.listar(CASO, self.fp)
        self.assertEqual(len(listado["registros"]), 2)
        self.assertTrue(all(r["vigente"] for r in listado["registros"]))
        self.assertEqual(self.app.geometrias(CASO), geos_antes)
        serializado = json.dumps([prep, calc, listado])
        self.assertNotIn(str(self.app.raiz), serializado)

    def test_contraste_en_tres_controles_independientes_con_referencias_sigue_en_borrador(self) -> None:
        geo_id, geo_actual = self._importar_geo(_geometria_v03_base(sintetica=True, con_referencias_doc=True))
        calc = self.svc.calcular({
            "caso": CASO,
            "expediente_sha256": self.fp,
            "geometria": geo_id,
            "huella_geometria": geo_actual["huella"],
            "sha256_geometria": geo_actual["sha256_geometria"],
            "propuesta_id": "PROP_CON_CONTROLES",
            "fuente": self._fuente_base(con_sha=True),
            "plano": self._plano_z0(),
            "limites": _limites_validos(),
            "anclas": [
                {"id": "A1", "punto_resuelto": "VA", "uv_local": _uv_desde_xy(1.0, 1.0)},
                {"id": "A2", "punto_resuelto": "VB", "uv_local": _uv_desde_xy(9.0, 1.0)},
                {"id": "A3", "punto_resuelto": "VC", "uv_local": _uv_desde_xy(9.0, 7.0)},
            ],
            "controles": [
                {"id": "C1", "punto_resuelto": "VD", "uv_local": _uv_desde_xy(1.0, 7.0)},
                {"id": "C2", "punto_resuelto": "VE", "uv_local": _uv_desde_xy(5.0, 1.0)},
                {"id": "C3", "punto_resuelto": "VF", "uv_local": _uv_desde_xy(5.0, 5.0)},
            ],
            "puntos": [
                {"id": "PN_EXT", "uv_local": _uv_desde_xy(0.5, 0.5), "relacionados": ["VA", "VD"]},
            ],
        })
        self.assertTrue(calc["resumen"]["calculo_posible"])
        self.assertTrue(calc["resumen"]["contraste_en_controles"])
        self.assertFalse(calc["resumen"]["exactitud_documental_acreditada"])
        self.assertEqual(calc["revision"], {"estado": "borrador", "aprobacion": None})
        self.assertFalse(calc["disponible_para_modelado"])
        self.assertTrue(calc["resultado"]["puntos"][0]["extrapolacion"])
        self.assertIn("puntos_fuera_casco_anclas", {p["codigo"] for p in calc["pendientes"]})

    def test_control_sin_referencia_documental_no_finge_independencia(self) -> None:
        geo_id, geo_actual = self._importar_geo(_geometria_v03_base(sintetica=True, con_referencias_doc=False))
        with self.assertRaises(ErrorRevisionDigitizacion) as ctx:
            self.svc.calcular({
                "caso": CASO,
                "expediente_sha256": self.fp,
                "geometria": geo_id,
                "huella_geometria": geo_actual["huella"],
                "sha256_geometria": geo_actual["sha256_geometria"],
                "propuesta_id": "PROP_CTRL_DEP",
                "fuente": self._fuente_base(con_sha=True),
                "plano": self._plano_z0(),
                "limites": _limites_validos(),
                "anclas": [
                    {"id": "A1", "punto_resuelto": "VA", "uv_local": _uv_desde_xy(1.0, 1.0)},
                    {"id": "A2", "punto_resuelto": "VB", "uv_local": _uv_desde_xy(9.0, 1.0)},
                    {"id": "A3", "punto_resuelto": "VC", "uv_local": _uv_desde_xy(9.0, 7.0)},
                ],
                "controles": [
                    {"id": "C1", "punto_resuelto": "VD", "uv_local": _uv_desde_xy(1.0, 7.0)},
                ],
                "puntos": [
                    {"id": "PN1", "uv_local": [0.5, 0.5], "relacionados": ["VA"]},
                ],
            })
        self.assertEqual(ctx.exception.codigo, "control_dependiente")

    def test_rechaza_coordenadas_metricas_desde_navegador_o_ia(self) -> None:
        geo_id, geo_actual = self._importar_geo(_geometria_v03_base())
        base_calc = {
            "caso": CASO,
            "expediente_sha256": self.fp,
            "geometria": geo_id,
            "huella_geometria": geo_actual["huella"],
            "sha256_geometria": geo_actual["sha256_geometria"],
            "propuesta_id": "PROP_METRICAS",
            "fuente": self._fuente_base(con_sha=True),
            "plano": self._plano_z0(),
            "limites": _limites_validos(),
            "anclas": [
                {"id": "A1", "punto_resuelto": "VA", "uv_local": [0.1, 0.9]},
                {"id": "A2", "punto_resuelto": "VB", "uv_local": [0.9, 0.9]},
                {"id": "A3", "punto_resuelto": "VC", "uv_local": [0.9, 0.1]},
            ],
            "controles": [],
            "puntos": [{"id": "PN1", "uv_local": [0.5, 0.5], "relacionados": ["VA"]}],
        }

        variantes = []
        v1 = copy.deepcopy(base_calc)
        v1["puntos_resueltos"] = {"VA": {"coordenadas": [1.0, 1.0]}}
        variantes.append(v1)

        v2 = copy.deepcopy(base_calc)
        v2["anclas"][0]["coordenadas"] = [1.0, 1.0]
        variantes.append(v2)

        v3 = copy.deepcopy(base_calc)
        v3["puntos"][0]["x"] = 5.0
        variantes.append(v3)

        v4 = copy.deepcopy(base_calc)
        v4["puntos"][0]["coordenadas_m"] = {"x": 5.0, "y": 4.0, "z": 0.0}
        variantes.append(v4)

        for invalida in variantes:
            with self.assertRaises(ErrorRevisionDigitizacion) as ctx:
                self.svc.calcular(invalida)
            self.assertEqual(ctx.exception.codigo, "coordenadas_metricas_no_admitidas")

    def test_rechaza_sha_falso_y_detecta_bytes_de_original_alterados(self) -> None:
        geo_id, geo_actual = self._importar_geo(_geometria_v03_base())
        fuente_falsa = self._fuente_base(con_sha=True)
        fuente_falsa["sha256"] = "0" * 64
        with self.assertRaises(ErrorRevisionDigitizacion) as ctx:
            self.svc.preparar({
                "caso": CASO,
                "expediente_sha256": self.fp,
                "geometria": geo_id,
                "huella_geometria": geo_actual["huella"],
                "sha256_geometria": geo_actual["sha256_geometria"],
                "fuente": fuente_falsa,
                "plano": self._plano_z0(),
            })
        self.assertEqual(ctx.exception.codigo, "sha256_original_no_coincide")

        guardado = self.svc.calcular({
            "caso": CASO,
            "expediente_sha256": self.fp,
            "geometria": geo_id,
            "huella_geometria": geo_actual["huella"],
            "sha256_geometria": geo_actual["sha256_geometria"],
            "propuesta_id": "PROP_ORIG",
            "fuente": self._fuente_base(con_sha=True),
            "plano": self._plano_z0(),
            "limites": _limites_validos(),
            "anclas": [
                {"id": "A1", "punto_resuelto": "VA", "uv_local": _uv_desde_xy(1.0, 1.0)},
                {"id": "A2", "punto_resuelto": "VB", "uv_local": _uv_desde_xy(9.0, 1.0)},
                {"id": "A3", "punto_resuelto": "VC", "uv_local": _uv_desde_xy(9.0, 7.0)},
            ],
            "controles": [],
            "puntos": [{"id": "PN1", "uv_local": [0.5, 0.5], "relacionados": ["VA"]}],
        })

        ruta_pdf_caso = Path(self.case_dir) / self.manifest["archivos"][0]["archivo"]
        original_bytes = ruta_pdf_caso.read_bytes()
        try:
            ruta_pdf_caso.write_bytes(original_bytes + b"%alterado")
            with self.assertRaises(ErrorRevisionDigitizacion) as ctx_alt:
                self.svc.consultar(CASO, self.fp, guardado["id"])
            self.assertEqual(ctx_alt.exception.codigo, "fuente_alterada")
        finally:
            ruta_pdf_caso.write_bytes(original_bytes)

    def test_detecta_geometria_alterada_o_version_no_030(self) -> None:
        # Geometría 0.1.0 debe rechazarse
        geo_v01 = json.loads((ROOT / "examples" / "geometria_sintetica.json").read_text(encoding="utf-8"))
        geo_v01["id"] = CASO
        id_v01, act_v01 = self._importar_geo(geo_v01)
        with self.assertRaises(ErrorRevisionDigitizacion) as ctx_v01:
            self.svc.preparar({
                "caso": CASO,
                "expediente_sha256": self.fp,
                "geometria": id_v01,
                "huella_geometria": act_v01["huella"],
                "sha256_geometria": act_v01["sha256_geometria"],
                "fuente": self._fuente_base(con_sha=False),
                "plano": self._plano_z0(),
            })
        self.assertEqual(ctx_v01.exception.codigo, "version_geometria_no_admitida")

        # Geometría 0.3.0 alterada en disco después de calcular
        geo_id, geo_actual = self._importar_geo(_geometria_v03_base())
        calc = self.svc.calcular({
            "caso": CASO,
            "expediente_sha256": self.fp,
            "geometria": geo_id,
            "huella_geometria": geo_actual["huella"],
            "sha256_geometria": geo_actual["sha256_geometria"],
            "propuesta_id": "PROP_GEO_ALT",
            "fuente": self._fuente_base(con_sha=True),
            "plano": self._plano_z0(),
            "limites": _limites_validos(),
            "anclas": [
                {"id": "A1", "punto_resuelto": "VA", "uv_local": _uv_desde_xy(1.0, 1.0)},
                {"id": "A2", "punto_resuelto": "VB", "uv_local": _uv_desde_xy(9.0, 1.0)},
                {"id": "A3", "punto_resuelto": "VC", "uv_local": _uv_desde_xy(9.0, 7.0)},
            ],
            "controles": [],
            "puntos": [{"id": "PN1", "uv_local": [0.5, 0.5], "relacionados": ["VA"]}],
        })
        geo_file = Path(self.case_dir) / gg.CARPETA_GEOMETRIAS / geo_id / "geometria.json"
        geo_mod = json.loads(geo_file.read_text(encoding="utf-8"))
        geo_mod["vertices"][0]["x"] = 1.25
        geo_file.write_bytes(_bytes(geo_mod))

        with self.assertRaises(ErrorRevisionDigitizacion):
            self.svc.consultar(CASO, self.fp, calc["id"])
        listado = self.svc.listar(CASO, self.fp)
        self.assertEqual(listado["registros"][0]["vigente"], False)

    def test_detecta_tampering_de_coordenadas_o_aprobacion_en_registro_persistido(self) -> None:
        geo_id, geo_actual = self._importar_geo(_geometria_v03_base())
        calc = self.svc.calcular({
            "caso": CASO,
            "expediente_sha256": self.fp,
            "geometria": geo_id,
            "huella_geometria": geo_actual["huella"],
            "sha256_geometria": geo_actual["sha256_geometria"],
            "propuesta_id": "PROP_TAMP",
            "fuente": self._fuente_base(con_sha=True),
            "plano": self._plano_z0(),
            "limites": _limites_validos(),
            "anclas": [
                {"id": "A1", "punto_resuelto": "VA", "uv_local": _uv_desde_xy(1.0, 1.0)},
                {"id": "A2", "punto_resuelto": "VB", "uv_local": _uv_desde_xy(9.0, 1.0)},
                {"id": "A3", "punto_resuelto": "VC", "uv_local": _uv_desde_xy(9.0, 7.0)},
            ],
            "controles": [],
            "puntos": [{"id": "PN1", "uv_local": [0.5, 0.5], "relacionados": ["VA"]}],
        })
        carpeta_reg = Path(self.case_dir) / CARPETA / calc["id"]
        reg_path = carpeta_reg / "registro.json"
        ver_path = carpeta_reg / "version.json"

        # Incluso si un atacante recalcula huella_version y sha256_registro tras alterar coordenadas_m,
        # la reejecución pura de calibrar_digitizacion en consultar detecta la manipulación.
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
        reg["resultado"]["puntos"][0]["coordenadas_m"]["x"] = 99.0
        sin_h = {k: v for k, v in reg.items() if k != "huella_version"}
        nueva_h = _huella(sin_h)
        reg["huella_version"] = nueva_h
        raw_reg = _bytes(reg)
        reg_path.write_bytes(raw_reg)
        ver = json.loads(ver_path.read_text(encoding="utf-8"))
        ver["huella_version"] = nueva_h
        ver["sha256_registro"] = hashlib.sha256(raw_reg).hexdigest()
        ver_path.write_bytes(_bytes(ver))

        with self.assertRaises(ErrorRevisionDigitizacion) as ctx:
            self.svc.consultar(CASO, self.fp, calc["id"])
        self.assertEqual(ctx.exception.codigo, "calculo_alterado")

    def test_rechaza_otro_plano_otra_lamina_cota_inventada_y_unidad_distinta(self) -> None:
        geo_id, geo_actual = self._importar_geo(
            _geometria_v03_base(con_referencias_doc=True, otra_lamina_en_v4=self.id_png)
        )
        # Cota inventada z = 99.0
        with self.assertRaises(ErrorRevisionDigitizacion) as ctx_cota:
            self.svc.preparar({
                "caso": CASO,
                "expediente_sha256": self.fp,
                "geometria": geo_id,
                "huella_geometria": geo_actual["huella"],
                "sha256_geometria": geo_actual["sha256_geometria"],
                "fuente": self._fuente_base(con_sha=False),
                "plano": self._plano_z0(cota=99.0),
            })
        self.assertEqual(ctx_cota.exception.codigo, "cota_plano_inexistente_en_geometria")

        # Unidad distinta de la geometría
        with self.assertRaises(ErrorRevisionDigitizacion) as ctx_uni:
            self.svc.preparar({
                "caso": CASO,
                "expediente_sha256": self.fp,
                "geometria": geo_id,
                "huella_geometria": geo_actual["huella"],
                "sha256_geometria": geo_actual["sha256_geometria"],
                "fuente": self._fuente_base(con_sha=False),
                "plano": self._plano_z0(unidad="cm"),
            })
        self.assertEqual(ctx_uni.exception.codigo, "unidad_distinta_de_geometria")

        # Ancla VT1 perteneciente a z = 2.8 usada en plano z = 0.0
        with self.assertRaises(ErrorRevisionDigitizacion) as ctx_plano:
            self.svc.calcular({
                "caso": CASO,
                "expediente_sha256": self.fp,
                "geometria": geo_id,
                "huella_geometria": geo_actual["huella"],
                "sha256_geometria": geo_actual["sha256_geometria"],
                "propuesta_id": "PROP_OTRO_PLANO",
                "fuente": self._fuente_base(con_sha=True),
                "plano": self._plano_z0(),
                "limites": _limites_validos(),
                "anclas": [
                    {"id": "A1", "punto_resuelto": "VA", "uv_local": [0.1, 0.9]},
                    {"id": "A2", "punto_resuelto": "VB", "uv_local": [0.9, 0.9]},
                    {"id": "A3", "punto_resuelto": "VT1", "uv_local": [0.9, 0.1]},
                ],
                "controles": [],
                "puntos": [{"id": "PN1", "uv_local": [0.5, 0.5], "relacionados": ["VA"]}],
            })
        self.assertEqual(ctx_plano.exception.codigo, "referencia_otro_plano")

        # Ancla VD cuya lámina declarada apunta a otro original del caso
        with self.assertRaises(ErrorRevisionDigitizacion) as ctx_fuente:
            self.svc.calcular({
                "caso": CASO,
                "expediente_sha256": self.fp,
                "geometria": geo_id,
                "huella_geometria": geo_actual["huella"],
                "sha256_geometria": geo_actual["sha256_geometria"],
                "propuesta_id": "PROP_OTRA_LAMINA",
                "fuente": self._fuente_base(con_sha=True),
                "plano": self._plano_z0(),
                "limites": _limites_validos(),
                "anclas": [
                    {"id": "A1", "punto_resuelto": "VA", "uv_local": [0.1, 0.9]},
                    {"id": "A2", "punto_resuelto": "VB", "uv_local": [0.9, 0.9]},
                    {"id": "A3", "punto_resuelto": "VD", "uv_local": [0.1, 0.1]},
                ],
                "controles": [],
                "puntos": [{"id": "PN1", "uv_local": [0.5, 0.5], "relacionados": ["VA"]}],
            })
        self.assertEqual(ctx_fuente.exception.codigo, "referencia_otra_fuente")

    def test_plano_con_referencias_insuficientes_conserva_pendiente_sin_fabricar(self) -> None:
        geo_id, geo_actual = self._importar_geo(_geometria_v03_base())
        plano_cumbrera = self._plano_z0(cota=4.0, pid="PL_Z4")

        prep = self.svc.preparar({
            "caso": CASO,
            "expediente_sha256": self.fp,
            "geometria": geo_id,
            "huella_geometria": geo_actual["huella"],
            "sha256_geometria": geo_actual["sha256_geometria"],
            "fuente": self._fuente_base(con_sha=False),
            "plano": plano_cumbrera,
        })
        self.assertFalse(prep["resumen"]["referencias_suficientes_para_ajuste"])
        self.assertIn("referencias_coplanares_insuficientes", {p["codigo"] for p in prep["pendientes"]})

        res_calc = self.svc.calcular({
            "caso": CASO,
            "expediente_sha256": self.fp,
            "geometria": geo_id,
            "huella_geometria": geo_actual["huella"],
            "sha256_geometria": geo_actual["sha256_geometria"],
            "preparacion_id": prep["id"],
            "huella_preparacion": prep["huella_version"],
            "propuesta_id": "PROP_INSUF",
            "fuente": prep["fuente_vigente"],
            "plano": plano_cumbrera,
            "limites": _limites_validos(),
            "anclas": [
                {"id": "A1", "punto_resuelto": "VK1", "uv_local": [0.1, 0.5]},
                {"id": "A2", "punto_resuelto": "VK2", "uv_local": [0.9, 0.5]},
            ],
            "controles": [],
            "puntos": [{"id": "PN1", "uv_local": [0.5, 0.5], "relacionados": ["VK1"]}],
        })
        self.assertEqual(res_calc["etapa"], "pendiente_referencias")
        self.assertIsNone(res_calc["resultado"])
        self.assertFalse(res_calc["resumen"]["calculo_posible"])
        self.assertIn("referencias_coplanares_insuficientes", {p["codigo"] for p in res_calc["pendientes"]})

    def test_revision_documental_y_recorte_vinculados_y_rechazo_de_rutas_o_reparse(self) -> None:
        geo_id, geo_actual = self._importar_geo(_geometria_v03_base())
        rev_path = revisar_expediente(Path(self.case_dir) / "expediente.json", max_lado=800)
        rev_id = rev_path.parent.name
        bbox = [0.1, 0.15, 0.9, 0.85]
        rec_path = generar_recorte(Path(self.case_dir) / "expediente.json", self.id_pdf, 1, bbox, dpi=120, etiqueta="planta")
        rec_id = rec_path.parent.name

        prep = self.svc.preparar({
            "caso": CASO,
            "expediente_sha256": self.fp,
            "geometria": geo_id,
            "huella_geometria": geo_actual["huella"],
            "sha256_geometria": geo_actual["sha256_geometria"],
            "fuente": {
                **self._fuente_base(con_sha=False, bbox=bbox),
                "revision_documental": rev_id,
                "recorte": rec_id,
            },
            "plano": self._plano_z0(),
        })
        self.assertEqual(prep["evidencia_fuente"]["revision_documental_id"], rev_id)
        self.assertEqual(prep["evidencia_fuente"]["recorte_id"], rec_id)

        # BBox incompatible con el recorte vinculado
        with self.assertRaises(ErrorRevisionDigitizacion) as ctx_rec:
            self.svc.preparar({
                "caso": CASO,
                "expediente_sha256": self.fp,
                "geometria": geo_id,
                "huella_geometria": geo_actual["huella"],
                "sha256_geometria": geo_actual["sha256_geometria"],
                "fuente": {
                    **self._fuente_base(con_sha=False, bbox=[0.0, 0.0, 1.0, 1.0]),
                    "recorte": rec_id,
                },
                "plano": self._plano_z0(),
            })
        self.assertEqual(ctx_rec.exception.codigo, "recorte_inconsistente")

        # Separadores de ruta o traversal rechazados
        with self.assertRaises(ErrorRevisionDigitizacion) as ctx_path:
            self.svc.preparar({
                "caso": CASO,
                "expediente_sha256": self.fp,
                "geometria": geo_id,
                "huella_geometria": geo_actual["huella"],
                "sha256_geometria": geo_actual["sha256_geometria"],
                "fuente": {
                    **self._fuente_base(con_sha=False),
                    "original_id": "../fuera",
                },
                "plano": self._plano_z0(),
            })
        self.assertEqual(ctx_path.exception.codigo, "identificador_invalido")

        # Reparse point / symlink detectado en carpeta del registro
        reg_dir = Path(self.case_dir) / CARPETA / prep["id"]
        real_stat = reg_dir.lstat()
        fake_stat = SimpleNamespace(
            st_mode=real_stat.st_mode | stat.S_IFLNK,
            st_file_attributes=getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400),
            st_size=real_stat.st_size,
        )
        with patch.object(Path, "lstat", return_value=fake_stat):
            with self.assertRaises(ErrorRevisionDigitizacion) as ctx_lnk:
                self.svc.consultar(CASO, self.fp, prep["id"])
            self.assertEqual(ctx_lnk.exception.codigo, "enlace_no_permitido")

    def _alterar_registro_y_recalcular_hashes(self, reg_id: str, mutador) -> None:
        carpeta = Path(self.case_dir) / CARPETA / reg_id
        reg_path = carpeta / "registro.json"
        ver_path = carpeta / "version.json"
        reg = json.loads(reg_path.read_bytes())
        ver = json.loads(ver_path.read_bytes())
        mutador(reg)
        sin_huella = {k: v for k, v in reg.items() if k != "huella_version"}
        nueva_huella = _huella(sin_huella)
        reg["huella_version"] = nueva_huella
        raw_reg = _bytes(reg)
        ver["huella_version"] = nueva_huella
        ver["sha256_registro"] = hashlib.sha256(raw_reg).hexdigest()
        reg_path.write_bytes(raw_reg)
        ver_path.write_bytes(_bytes(ver))

    def test_rechaza_alteracion_de_resumen_pendientes_catalogo_y_flags_con_hashes_recalculados(self) -> None:
        """Regresión 355-01: recalcular huella_version y sha256_registro no acredita resumen ni oculta pendientes."""
        geo_id, geo_actual = self._importar_geo(_geometria_v03_base(sintetica=True, con_referencias_doc=False))
        base_body = {
            "caso": CASO,
            "expediente_sha256": self.fp,
            "geometria": geo_id,
            "huella_geometria": geo_actual["huella"],
            "sha256_geometria": geo_actual["sha256_geometria"],
            "propuesta_id": "PROBE355",
            "fuente": self._fuente_base(con_sha=True),
            "plano": self._plano_z0(),
            "limites": _limites_validos(),
            "anclas": [
                {"id": "A1", "punto_resuelto": "VA", "uv_local": _uv_desde_xy(1.0, 1.0)},
                {"id": "A2", "punto_resuelto": "VB", "uv_local": _uv_desde_xy(9.0, 1.0)},
                {"id": "A3", "punto_resuelto": "VC", "uv_local": _uv_desde_xy(9.0, 7.0)},
            ],
            "controles": [],
            "puntos": [{"id": "N1", "uv_local": [0.5, 0.5], "relacionados": ["VA"]}],
        }

        # 1) Reproducción exacta 355-01: falsificar acreditación documental/contraste en resumen y vaciar pendientes
        c1 = self.svc.calcular(copy.deepcopy(base_body))
        self._alterar_registro_y_recalcular_hashes(
            c1["id"],
            lambda r: (
                r["resumen"].update(
                    exactitud_documental_acreditada=True,
                    contraste_en_controles=True,
                    exactitud_verificada_en_controles=True,
                    carencia_vinculo_documental=False,
                    ajuste_tres_anclas_sin_verificacion=False,
                ),
                r.__setitem__("pendientes", []),
            ),
        )
        with self.assertRaises(ErrorRevisionDigitizacion) as ctx_355:
            self.svc.consultar(CASO, self.fp, c1["id"])
        self.assertEqual(ctx_355.exception.codigo, "registro_alterado")

        # 2) Ocultar o recortar un único pendiente sin tocar resumen también se rechaza
        c2 = self.svc.calcular({**copy.deepcopy(base_body), "propuesta_id": "PROBE_PEND"})
        self._alterar_registro_y_recalcular_hashes(
            c2["id"],
            lambda r: r["pendientes"].pop(0),
        )
        with self.assertRaises(ErrorRevisionDigitizacion) as ctx_pend:
            self.svc.consultar(CASO, self.fp, c2["id"])
        self.assertEqual(ctx_pend.exception.codigo, "registro_alterado")

        # 3) Alterar catálogo de referencias (p. ej. ubicacion_en_dibujo_acreditada o tiene_referencia_documental)
        c3 = self.svc.calcular({**copy.deepcopy(base_body), "propuesta_id": "PROBE_CAT"})
        self._alterar_registro_y_recalcular_hashes(
            c3["id"],
            lambda r: r["catalogo_referencias"][0].update(
                tiene_referencia_documental=True,
                ubicacion_en_dibujo_acreditada=True,
            ),
        )
        with self.assertRaises(ErrorRevisionDigitizacion) as ctx_cat:
            self.svc.consultar(CASO, self.fp, c3["id"])
        self.assertEqual(ctx_cat.exception.codigo, "registro_alterado")

        # 4) Alterar flags internos de resumen (integra_al_modelo / datos_sinteticos)
        c4 = self.svc.calcular({**copy.deepcopy(base_body), "propuesta_id": "PROBE_FLAGS"})
        self._alterar_registro_y_recalcular_hashes(
            c4["id"],
            lambda r: r["resumen"].update(integra_al_modelo=True, datos_sinteticos=False),
        )
        with self.assertRaises(ErrorRevisionDigitizacion) as ctx_flg:
            self.svc.consultar(CASO, self.fp, c4["id"])
        self.assertEqual(ctx_flg.exception.codigo, "registro_alterado")

        # El historial marca todos los registros manipulados como no vigentes
        listado = self.svc.listar(CASO, self.fp)
        por_id = {fila["id"]: fila for fila in listado["registros"]}
        for rid in (c1["id"], c2["id"], c3["id"], c4["id"]):
            self.assertFalse(por_id[rid]["vigente"])
            self.assertIn("registro_alterado", por_id[rid]["problemas"])

    def test_rechaza_alteracion_semantica_en_preparada_pendiente_y_con_referencias_textuales(self) -> None:
        """Verifica constructores puros en preparada, pendiente_referencias y con referencias textuales."""
        # Referencias textuales en geometría NO acreditan exactitud documental en el dibujo
        geo_doc_id, geo_doc = self._importar_geo(_geometria_v03_base(sintetica=True, con_referencias_doc=True))
        calc_doc = self.svc.calcular({
            "caso": CASO,
            "expediente_sha256": self.fp,
            "geometria": geo_doc_id,
            "huella_geometria": geo_doc["huella"],
            "sha256_geometria": geo_doc["sha256_geometria"],
            "propuesta_id": "PROP_DOC_TEXTUAL",
            "fuente": self._fuente_base(con_sha=True),
            "plano": self._plano_z0(),
            "limites": _limites_validos(),
            "anclas": [
                {"id": "A1", "punto_resuelto": "VA", "uv_local": _uv_desde_xy(1.0, 1.0)},
                {"id": "A2", "punto_resuelto": "VB", "uv_local": _uv_desde_xy(9.0, 1.0)},
                {"id": "A3", "punto_resuelto": "VC", "uv_local": _uv_desde_xy(9.0, 7.0)},
            ],
            "controles": [
                {"id": "C1", "punto_resuelto": "VD", "uv_local": _uv_desde_xy(1.0, 7.0)},
                {"id": "C2", "punto_resuelto": "VE", "uv_local": _uv_desde_xy(5.0, 1.0)},
                {"id": "C3", "punto_resuelto": "VF", "uv_local": _uv_desde_xy(5.0, 5.0)},
            ],
            "puntos": [{"id": "PN1", "uv_local": _uv_desde_xy(5.0, 4.0), "relacionados": ["VA", "VB"]}],
        })
        self.assertFalse(calc_doc["resumen"]["exactitud_documental_acreditada"])
        self.assertTrue(calc_doc["resumen"]["carencia_vinculo_documental"])
        self._alterar_registro_y_recalcular_hashes(
            calc_doc["id"],
            lambda r: r["resumen"].update(exactitud_documental_acreditada=True, carencia_vinculo_documental=False),
        )
        with self.assertRaises(ErrorRevisionDigitizacion) as ctx_doc:
            self.svc.consultar(CASO, self.fp, calc_doc["id"])
        self.assertEqual(ctx_doc.exception.codigo, "registro_alterado")

        # Etapa preparada y pendiente_referencias en plano z=4.0 (solo 2 vértices coplanares)
        plano_z4 = self._plano_z0(cota=4.0, pid="PL_Z4")
        prep_z4 = self.svc.preparar({
            "caso": CASO,
            "expediente_sha256": self.fp,
            "geometria": geo_doc_id,
            "huella_geometria": geo_doc["huella"],
            "sha256_geometria": geo_doc["sha256_geometria"],
            "fuente": self._fuente_base(con_sha=False),
            "plano": plano_z4,
        })
        pend_z4 = self.svc.calcular({
            "caso": CASO,
            "expediente_sha256": self.fp,
            "geometria": geo_doc_id,
            "huella_geometria": geo_doc["huella"],
            "sha256_geometria": geo_doc["sha256_geometria"],
            "preparacion_id": prep_z4["id"],
            "huella_preparacion": prep_z4["huella_version"],
            "propuesta_id": "PROP_PEND_Z4",
            "fuente": prep_z4["fuente_vigente"],
            "plano": plano_z4,
            "limites": _limites_validos(),
            "anclas": [
                {"id": "A1", "punto_resuelto": "VK1", "uv_local": [0.1, 0.5]},
                {"id": "A2", "punto_resuelto": "VK2", "uv_local": [0.9, 0.5]},
            ],
            "controles": [],
            "puntos": [{"id": "PN1", "uv_local": [0.5, 0.5], "relacionados": ["VK1"]}],
        })

        # Alterar pendiente_referencias (fingir cálculo posible o vaciar pendientes)
        self._alterar_registro_y_recalcular_hashes(
            pend_z4["id"],
            lambda r: (
                r["resumen"].update(calculo_posible=True, referencias_suficientes_para_ajuste=True),
                r.__setitem__("pendientes", []),
            ),
        )
        with self.assertRaises(ErrorRevisionDigitizacion) as ctx_pz4:
            self.svc.consultar(CASO, self.fp, pend_z4["id"])
        self.assertEqual(ctx_pz4.exception.codigo, "registro_alterado")

        # Alterar preparada (fingir referencias suficientes o exactitud documental)
        self._alterar_registro_y_recalcular_hashes(
            prep_z4["id"],
            lambda r: r["resumen"].update(
                referencias_suficientes_para_ajuste=True,
                exactitud_documental_acreditada=True,
            ),
        )
        with self.assertRaises(ErrorRevisionDigitizacion) as ctx_prep:
            self.svc.consultar(CASO, self.fp, prep_z4["id"])
        self.assertEqual(ctx_prep.exception.codigo, "registro_alterado")


if __name__ == "__main__":
    unittest.main()
