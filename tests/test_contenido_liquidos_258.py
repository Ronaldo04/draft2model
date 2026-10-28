"""R249-02: liquidos.contenido en el contrato 0.5. Estado explícito por depósito y contabilidad de masa (masa_contenido) con la
malla vigente. Datos sintéticos (losa 6 × 4 con dos huecos 1 × 1 a z = 2,6; agua 1,0 m sobre ella: V = 22 m³, W = 220 kN)."""
import copy

from draft2model import modelo_estructural as m
from tests import test_liquidos_ruta201 as tlr

F = tlr.F


class ContenidoTests(tlr.CasoLiquidos):
    def montar_contenido(self, estado="lleno", volumen=22.0, factor=1, contenido=True, aplicabilidad="presente"):
        decls = [tlr.declaracion("FONDO", 3.6, [("S1", -1)])] if aplicabilidad == "presente" else []
        data = self.montar_liquidos("horizontal", aplicabilidad, [(d, f, "HIDRO") for d, f in decls],
                                    patrones=("HIDRO",) if decls else ())
        data["masa"].update(metodo="patrones", masas_puntos=[])
        data["masa"]["factores_patrones"] = [x for x in data["masa"]["factores_patrones"] if x["patron"] != "HIDRO"]
        if decls:
            data["masa"]["factores_patrones"].append({"patron": "HIDRO", "factor": factor})
        if contenido:
            con_decl = estado in ("lleno", "vacio")
            data["liquidos"]["contenido"] = [{
                "deposito": "TANQUE", "estado": estado, "fuente": F, "motivo": "Escenario sintético de llenado.",
                "declaracion": "FONDO" if con_decl else None, "modo": "patron_presion" if con_decl else None,
                "patron_masa_exclusivo": None, "peso_vertical_referencia_kn": None, "volumen_m3": volumen if con_decl else None}]
        return self.aprobar_local(self.completar(data))

    def validar(self, data):
        return m.validar_configuracion(data, self.geo)

    def test_lleno_coherente_con_presion_y_fuente_de_masa(self):
        r = self.validar(self.montar_contenido())
        self.assertTrue(r.consistente, r.errores)
        inv = r.contenido_masa
        self.assertEqual(inv["estado"], "contabilidad_declarada_coherente")
        self.assertAlmostEqual(inv["peso_total_kn"], 220.0, places=9)
        self.assertAlmostEqual(inv["escenarios"][0]["fz_presion_kn"], -220.0, places=9)
        self.assertEqual(inv["estados"], {"TANQUE": "lleno"})
        self.assertFalse(inv["masa_nativa_verificada"])
        self.assertIn("contenido_masa", r.a_dict())

    def test_sin_clave_la_salida_no_cambia(self):
        r = self.validar(self.montar_contenido(contenido=False))
        self.assertTrue(r.consistente, r.errores)
        self.assertIsNone(r.contenido_masa)
        self.assertNotIn("contenido_masa", r.a_dict())

    def test_rechazos(self):
        casos = {"volumen distinto de Fz/γ": self.montar_contenido(volumen=20.0),
                 "factor de masa parcial": self.montar_contenido(factor=0.25),
                 "vacío con volumen": self.montar_contenido(estado="vacio", volumen=22.0)}
        sin_estado = self.montar_contenido()
        sin_estado["liquidos"]["contenido"][0]["declaracion"] = "OTRA"
        casos["declaración inexistente"] = sin_estado
        doble = self.montar_contenido()
        doble["liquidos"]["contenido"].append(copy.deepcopy(doble["liquidos"]["contenido"][0]))
        casos["depósito repetido"] = doble
        for nombre, data in casos.items():
            with self.subTest(nombre):
                r = self.validar(self.aprobar_local(data))
                self.assertFalse(r.consistente, nombre)
                self.assertIsNone(r.contenido_masa)

    def test_desconocido_es_faltante_no_ausencia(self):
        r = self.validar(self.montar_contenido(estado="desconocido", aplicabilidad="informacion_insuficiente"))
        self.assertTrue(r.consistente, r.errores)
        self.assertIn("$.liquidos.contenido[0].estado", {f["ruta"] for f in r.faltantes})
        self.assertFalse(r.apto_para_adaptador)

    def test_plan_lleva_inventario_ligado_a_sus_presiones(self):
        data = self.montar_contenido()
        data["revision"] = {"estado": "borrador", "aprobacion": None}
        p = self.plan(self.aprobar_en_disco(data))
        from draft2model import operaciones_etabs as o
        self.assertEqual(o.validar_plan_por_version(p), [])
        self.assertEqual(p["contenido_masa"]["huella_liquidos"], p["liquidos"]["huella_liquidos"])
        self.assertAlmostEqual(p["contenido_masa"]["peso_total_kn"], 220.0, places=9)

    def test_json_malformado_da_error_controlado(self):
        # Revisión Codex 260: tipos inválidos no deben llegar a set/dict (TypeError unhashable).
        base = self.montar_contenido()
        for campo, valor in (("deposito", []), ("deposito", {}), ("deposito", 3), ("deposito", None), ("estado", []),
                             ("estado", {}), ("declaracion", {}), ("declaracion", []), ("modo", []), ("fuente", {})):
            with self.subTest(campo=campo, valor=valor):
                data = copy.deepcopy(base)
                data["liquidos"]["contenido"][0][campo] = valor
                r = self.validar(self.aprobar_local(data))
                self.assertFalse(r.consistente)
                self.assertIsNone(r.contenido_masa)
        for valor in ([[]], [{}], "texto", {"a": 1}):
            with self.subTest(contenido=valor):
                data = copy.deepcopy(base)
                data["liquidos"]["contenido"] = valor
                r = self.validar(self.aprobar_local(data))
                self.assertFalse(r.consistente)
                self.assertIsNone(r.contenido_masa)

    def test_desconocido_no_admite_volumen(self):
        data = self.montar_contenido(estado="desconocido", aplicabilidad="informacion_insuficiente")
        data["liquidos"]["contenido"][0]["volumen_m3"] = 3.0
        self.assertFalse(self.validar(self.aprobar_local(data)).consistente)


if __name__ == "__main__":
    import unittest
    unittest.main()
