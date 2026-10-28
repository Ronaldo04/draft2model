"""Libro de masa (configuración + malla + líquidos) y contraste con la captura nativa AssembledJointMass_1 (masa_ensamblada).

El caso sintético es la losa 6 × 4 con dos huecos 1 × 1 (área neta 22 m²) y agua de 1,0 m (W = 220 kN) de test_contenido_liquidos_258.
El contraste usa el extracto existente 253f (ETABS 21, sintético), convertido al formato textual del lector; no es una ejecución nueva.
"""
import copy
import json
import math
import unittest
from pathlib import Path

from draft2model import libro_masa as lb
from draft2model import liquidos_malla as lm
from draft2model import malla_preparacion as mp
from draft2model.validacion_geometria import validar_geometria
from tests import test_contenido_liquidos_258 as tc

FIX = json.loads((Path(__file__).resolve().parent / "fixtures/masa_ensamblada_253f/extracto_sintetico_253f.json").read_text(encoding="utf-8"))


def captura_desde_fixture(control):
    raw, obs = control["raw"], control["observations"]
    texto = lambda v: None if v is None else repr(float(v))
    cap = {"unidades": raw["units"], "retorno": raw["return_code"], "numero_resultados": raw["number_results"],
           "point_elements": [None if v is None else str(v) for v in raw["point_elements"]],
           "mass_sources": [None if v is None else str(v) for v in raw["mass_sources"]],
           **{k: [texto(v) for v in raw[k]] for k in ("U1", "U2", "U3", "R1", "R2", "R3")},
           "observaciones": [{"point_element": r["point_element"], "mass_source": r["mass_source"],
                              "global_xyz": [texto(v) for v in r["global_xyz"]], "point_axes_deg": [texto(v) for v in r["point_axes_deg"]],
                              **{k: texto(r[k]) for k in ("U1", "U2", "U3", "R1", "R2", "R3")}} for r in obs["rows"]]}
    return cap, raw["capture_id"]


class LibroSinteticoTests(tc.ContenidoTests):
    def test_contribuciones_independientes(self):
        cfg = self.montar_contenido()
        prep = mp.preparar_malla(self.geo, cfg)
        liq = lm.preparar_liquidos(self.geo, cfg, prep)
        libro = lb.libro_masa(cfg, validar_geometria(self.geo), prep, liq)
        g = cfg["masa"]["gravedad_m_s2"]
        agua = libro["contribuciones"]["liquido_HIDRO"]
        self.assertAlmostEqual(agua["peso_kn"], 220.0, places=8)
        self.assertAlmostEqual(agua["masa_kn_s2_m"], 220.0 / g, places=10)
        # Peso propio de la losa con su área neta de malla (22 m²), espesor y γ de la configuración.
        sec = next(s for s in cfg["secciones"] if s["id"] == cfg["asignaciones_superficies"][0]["seccion"])
        gamma = next(m for m in cfg["materiales"] if m["id"] == sec["material"])["peso_kN_m3"]
        self.assertAlmostEqual(libro["contribuciones"]["peso_propio_por_patrones"]["detalle"]["shells_kn"],
                               22.0 * sec["dimensiones"]["espesor_m"] * gamma, places=8)
        self.assertAlmostEqual(libro["masa_total_kn_s2_m"], math.fsum(v["masa_kn_s2_m"] for v in libro["contribuciones"].values()))
        self.assertFalse(libro["aprueba_ingenieria"])

    def test_carga_local_rechazada(self):
        cfg = self.montar_contenido()
        cfg["cargas"][0]["sistema"] = "local"
        prep = mp.preparar_malla(self.geo, cfg)
        with self.assertRaises(lb.ErrorLibroMasa):
            lb.libro_masa(cfg, validar_geometria(self.geo), prep)


class ContrasteNativoTests(unittest.TestCase):
    def setUp(self):
        self.control = copy.deepcopy(FIX["controls"][2])   # AGUA_100: 9.734210770955226 kN·s²/m
        self.cap, self.cid = captura_desde_fixture(self.control)

    def contraste(self, total, **kw):
        return lb.contrastar_masa_nativa(self.cap, {"masa_total_kn_s2_m": total}, capture_id=self.cid,
                                         fuente_esperada=kw.get("fuente", "MsSrc1"), tolerancia_relativa=kw.get("tol", 1e-6))

    def test_coherente_con_libro(self):
        r = self.contraste(self.control["expected_mass"])
        self.assertEqual(r["estado"], "coherente", r)
        self.assertAlmostEqual(r["masa_observada_U1"], self.control["expected_mass"], places=9)
        self.assertEqual(r["fuente_observada"], "MsSrc1")

    def test_no_coherente_no_se_convierte_en_exito(self):
        for nombre, total, kw in (("libro distinto", self.control["expected_mass"] * 1.01, {}),
                                  ("otra fuente", self.control["expected_mass"], {"fuente": "MsSrc2"})):
            with self.subTest(nombre):
                r = self.contraste(total, **kw)
                self.assertEqual(r["estado"], "no_coherente")
                self.assertIn(r["codigo"], ("MASS_TOTAL", "SOURCE_MISMATCH"))

    def test_tolerancia_explicita(self):
        for tol in (0.0, 0.2, 1e-3 * 1j, True):
            with self.subTest(tol=tol), self.assertRaises(lb.ErrorLibroMasa):
                self.contraste(self.control["expected_mass"], tol=tol)


if __name__ == "__main__":
    unittest.main()


class TiposCapturaTests(unittest.TestCase):
    """Revisión Codex 266: bool/None/no decimales se rechazan antes de float, en el lector y en el contraste."""

    def base(self):
        return {"unidades": "kN_m_C", "retorno": 0, "numero_resultados": 1, "point_elements": ["P1", None], "mass_sources": ["MsSrc1", ""],
                "U1": ["1", "0"], "U2": ["1", "0"], "U3": ["0", "0"], "R1": ["0", "0"], "R2": ["0", "0"], "R3": ["0", "0"],
                "observaciones": [{"point_element": "P1", "mass_source": "MsSrc1", "global_xyz": ["0", "0", "0"],
                                   "point_axes_deg": ["0", "0", "0"], "U1": "1", "U2": "1", "U3": "0", "R1": "0", "R2": "0", "R3": "0"}]}

    def contraste(self, cap):
        return lb.contrastar_masa_nativa(cap, {"masa_total_kn_s2_m": 1.0}, capture_id="c266", fuente_esperada="MsSrc1",
                                         tolerancia_relativa=1e-6)

    def test_textos_R_y_cola_neutral_legitimos(self):
        from draft2model import lectura_analisis as la
        cap = self.base()
        la._validar_masa_api(cap, "kN_m_C")
        self.assertEqual(self.contraste(cap)["estado"], "coherente")

    def test_invalidos_rechazados_en_lector_y_contraste(self):
        from draft2model import adaptador_etabs as ad
        from draft2model import lectura_analisis as la
        casos = {}
        for nombre, valor in (("bool", True), ("bool_falso", False), ("texto_no_decimal", "1,0"), ("nan", "nan")):
            c = self.base(); c["U1"][0] = valor; c["U2"][0] = valor
            c["observaciones"][0]["U1"] = valor; c["observaciones"][0]["U2"] = valor
            casos["masa_" + nombre] = c
        c = self.base(); c["observaciones"][0]["global_xyz"][0] = True; casos["coordenada_bool"] = c
        c = self.base(); c["observaciones"][0]["point_axes_deg"][2] = None; casos["eje_none"] = c
        c = self.base(); c["observaciones"][0]["U3"] = None; casos["observacion_none"] = c
        c = self.base(); c["point_elements"][0] = 7; casos["identificador_numerico"] = c
        c = self.base(); c["retorno"] = False; casos["retorno_bool"] = c
        for nombre, cap in casos.items():
            with self.subTest(nombre):
                with self.assertRaises(ad.ErrorEvidenciaEtabs):
                    la._validar_masa_api(cap, "kN_m_C")
                with self.assertRaises(lb.ErrorLibroMasa):
                    self.contraste(cap)

    def test_numero_json_rechazado_por_el_lector(self):
        # El lector exige texto 'R'; un número JSON (extractos) solo lo admite el contraste, nunca un bool.
        from draft2model import adaptador_etabs as ad
        from draft2model import lectura_analisis as la
        c = self.base(); c["U1"][0] = 1.0
        with self.assertRaises(ad.ErrorEvidenciaEtabs):
            la._validar_masa_api(c, "kN_m_C")



class TablasSinCasoTests(unittest.TestCase):
    def test_lista_explicita_igual_en_guion_y_lector(self):
        import re as _re
        from draft2model import lectura_analisis as la
        texto = (Path(__file__).resolve().parents[1] / "scripts/leer_analisis_etabs.ps1").read_text(encoding="utf-8")
        lista = _re.search(r"\$sinCaso=@\(([^)]*)\)", texto).group(1)
        self.assertEqual({x.strip().strip("'") for x in lista.split(",")}, la.TABLAS_SIN_CASO)
        self.assertNotIn("Story Drifts", la.TABLAS_SIN_CASO)   # las tablas de resultados siguen exigiendo caso


class ConciliacionExtremosTests(unittest.TestCase):
    CFG = {"masa": {"gravedad_m_s2": 10.0},
           "secciones": [{"id": "V", "tipo": "frame_rectangular", "material": "C", "dimensiones": {"ancho_m": 0.1, "alto_m": 0.5}},
                         {"id": "P", "tipo": "frame_rectangular", "material": "C", "dimensiones": {"ancho_m": 0.2, "alto_m": 0.5}}],
           "materiales": [{"id": "C", "peso_kN_m3": 20.0}],
           "frames": [{"id": "B1", "tipo": "viga"}, {"id": "C1", "tipo": "columna"}, {"id": "B2", "tipo": "viga"}],
           "asignaciones_frames": [{"objetivo": "B1", "seccion": "V"}, {"objetivo": "C1", "seccion": "P"}, {"objetivo": "B2", "seccion": "V"}]}
    LIBRO = {"masa_total_kn_s2_m": 100.0, "contribuciones": {"peso_propio_por_patrones": {"factor_efectivo": 1.0}}}

    def filas(self, **cambios):
        base = [{"UniqueName": "B1", "OffsetI": "0.2", "OffsetJ": "0.3", "RigidFact": "0", "SelfWtOpt": "Auto"},
                {"UniqueName": "C1", "OffsetI": "0", "OffsetJ": "0.3", "RigidFact": "0", "SelfWtOpt": "Auto"},
                {"UniqueName": "B2", "OffsetI": "0.1", "OffsetJ": "0", "RigidFact": "0.5", "SelfWtOpt": "Auto"}]
        for k, v in cambios.items():
            base[0][k] = v
        return base

    def test_solo_vigas_auto_sin_factor_rigido(self):
        c = lb.conciliar_extremos_vigas(self.LIBRO, self.CFG, self.filas(), fuente="sintética")
        self.assertAlmostEqual(c["peso_excluido_kn"], 0.5 * 0.05 * 20.0)          # solo B1: columna y viga con RigidFact ≠ 0 no
        self.assertAlmostEqual(c["masa_total_kn_s2_m"], 100.0 - 0.5 / 10.0)
        self.assertFalse(c["independiente"])

    def test_otra_opcion_no_excluye_y_tipos_invalidos_rechazados(self):
        self.assertEqual(lb.conciliar_extremos_vigas(self.LIBRO, self.CFG, self.filas(SelfWtOpt="Included"), fuente="s")["peso_excluido_kn"], 0.0)
        for cambio in ({"OffsetI": True}, {"OffsetJ": "abc"}, {"UniqueName": "X9"}):
            with self.subTest(cambio=cambio), self.assertRaises(lb.ErrorLibroMasa):
                lb.conciliar_extremos_vigas(self.LIBRO, self.CFG, self.filas(**cambio), fuente="s")


class ConciliacionEntradasInvalidasTests(ConciliacionExtremosTests):
    """Revisión Codex 279 (HALLAZGO_CONCILIACION_279): duplicados y offsets negativos se rechazan; el libro original no cambia."""

    def test_duplicada_y_negativos_rechazados_sin_mutar_libro(self):
        import copy as _copy
        libro = _copy.deepcopy(self.LIBRO)
        dup = self.filas() + [dict(self.filas()[0])]
        for nombre, filas in (("duplicada", dup), ("offset_i_negativo", self.filas(OffsetI="-0.2")),
                              ("offset_j_negativo", self.filas(OffsetJ="-0.01")), ("vacía", []), ("no_lista", {"a": 1})):
            with self.subTest(nombre), self.assertRaises(lb.ErrorLibroMasa):
                lb.conciliar_extremos_vigas(libro, self.CFG, filas, fuente="s")
        self.assertEqual(libro, self.LIBRO)
