"""311: pruebas del helper con fixtures EXPLÍCITAMENTE SINTÉTICAS (caso «sintetico-311», hashes ficticios). No toca el expediente real.
Ejecutar: python -m unittest seguimiento/claude_ruta/preparacion_benchmark_311/test_recepcion_311.py
"""
import copy, json, sys, tempfile, unittest
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import recepcion_311 as r  # noqa: E402
from draft2model.evaluacion_vision import evaluar_lecturas  # noqa: E402

H = {k: k * 64 for k in "abcdef"}
ALCANCE = {"estado": "prueba_sintetica"}
KIT = {"caso": "sintetico-311", "paginas": [
    {"archivo_id": "L0001", "pagina": 1, "original_sha256": H["a"], "imagen_sha256": H["b"]},
    {"archivo_id": "L0002", "pagina": 1, "original_sha256": H["c"], "imagen_sha256": H["d"]},
    {"archivo_id": "L0003", "pagina": 1, "original_sha256": H["e"], "imagen_sha256": H["f"]}]}
UNIDAD = {"cota": "m", "etiqueta": "no_aplica", "elemento": "no_aplica"}


def ev(lam, bbox):
    p = KIT["paginas"][lam]
    return {"archivo_id": p["archivo_id"], "pagina": 1, "original_sha256": p["original_sha256"], "imagen_sha256": p["imagen_sha256"], "recorte_id": f"R{lam + 1}",
            "bbox_normalizada": bbox}


def obs(i, tipo, lam, bbox, valor):
    return {"id": f"O{i:03d}", "tipo": tipo, "valor": valor, "unidad": UNIDAD[tipo], "legibilidad": "legible", "evidencia": [ev(lam, bbox)]}


def referencia(n=30):
    tipos = ("cota", "etiqueta", "elemento")
    o = [obs(i, tipos[i % 3], i % 3, [0.01 * (i % 50), 0.1, 0.01 * (i % 50) + 0.05, 0.2], 1.25 if tipos[i % 3] == "cota" else f"T{i}") for i in range(n)]
    return {"contrato": "draft2model.referencia_vision", "version_contrato": "0.1.0", "caso": KIT["caso"],
            "procedencia": {"tipo": "sintetico", "descripcion": "FIXTURE SINTÉTICA 311: no es referencia humana."},
            "alcance": ALCANCE, "sistema_coordenadas": "pagina_visible_normalizada",
            "revision": {"revisor_declarado": "REVISOR SINTÉTICO DE PRUEBA", "fecha": "2026-10-24", "estado": "revisado"}, "observaciones": o}


def extraccion(ref, valor_distinto=False):
    cands = []
    for o in ref["observaciones"][:5]:
        b = o["evidencia"][0]["bbox_normalizada"]
        cands.append({"id": "C" + o["id"][1:], "tipo": o["tipo"], "valor_propuesto": (9.99 if o["tipo"] == "cota" else "X") if valor_distinto else o["valor"],
                      "unidad": o["unidad"], "metodo": {"tipo": "sintetico"}, "evidencia": [dict(o["evidencia"][0], bbox_normalizada=[b[0] + .01, b[1], b[2] + .01, b[3]])]})
    # candidato con el MISMO valor que O000 pero en otra lámina y región: no debe sugerirse (no se empareja por valor)
    cands.append({"id": "CVALOR", "tipo": "cota", "valor_propuesto": 1.25, "unidad": "m", "metodo": {"tipo": "sintetico"},
                  "evidencia": [ev(1, [0.8, 0.8, 0.9, 0.9])]})
    return {"contrato": "draft2model.extraccion_preliminar", "version_contrato": "0.1.0", "caso": ref["caso"],
            "procedencia": {"tipo": "sintetico", "descripcion": "FIXTURE SINTÉTICA 311"}, "alcance": ALCANCE,
            "sistema_coordenadas": "pagina_visible_normalizada", "candidatos": cands}


class Recepcion(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="d2m311_")); self.kit = self.tmp / "kit.json"; self.kit.write_text(json.dumps(KIT), encoding="utf-8")

    def escribir(self, nombre, data):
        p = self.tmp / nombre; p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8"); return str(p)

    def test_referencia_ausente_no_es_cero_ni_cien(self):
        self.assertEqual(r.main(["recibir", "--referencia", str(self.tmp / "no_existe.json"), "--fuentes", str(self.kit), "--salida", str(self.tmp / "o.json")]), 2)
        self.assertFalse((self.tmp / "o.json").exists())

    def test_plantilla_vacia_o_sin_revision_rechazada(self):
        ref = referencia(); ref["observaciones"] = []
        self.assertEqual(r.main(["recibir", "--referencia", self.escribir("v.json", ref), "--fuentes", str(self.kit), "--salida", str(self.tmp / "o.json")]), 2)
        ref = referencia(); ref["revision"]["estado"] = "pendiente"
        self.assertEqual(r.main(["recibir", "--referencia", self.escribir("p.json", ref), "--fuentes", str(self.kit), "--salida", str(self.tmp / "o2.json")]), 2)

    def test_completa_y_parcial(self):
        out = r.recibir(referencia(30), KIT)
        self.assertEqual(out["estado"], "protocolo_completo"); self.assertEqual(out["identidad_revisor"], "declarada_no_autenticada")
        parcial = referencia(30); parcial["observaciones"] = [o for o in parcial["observaciones"] if o["tipo"] != "elemento"][:12]
        out = r.recibir(parcial, KIT)
        self.assertEqual(out["estado"], "referencia_parcial")
        self.assertTrue(any("elemento" in f for f in out["faltantes_protocolo"])); self.assertTrue(any("L0003" in f for f in out["faltantes_protocolo"]))
        self.assertNotIn("metricas", out)

    def test_caso_y_huellas_incompatibles(self):
        ref = referencia(); ref["caso"] = "otro-caso"
        with self.assertRaises(r.Rechazo) as c: r.recibir(ref, KIT)
        self.assertEqual(c.exception.codigo, 3)
        ref = referencia(); ref["observaciones"][0]["evidencia"][0]["original_sha256"] = "9" * 64
        with self.assertRaises(r.Rechazo) as c: r.recibir(ref, KIT)
        self.assertEqual(c.exception.codigo, 3)

    def test_sugerencias_pendientes_sin_valor(self):
        ref = referencia(); ext = extraccion(ref, valor_distinto=True)
        prop = r.sugerir(ref, ext, "sintetica")
        self.assertEqual(prop["revision"]["estado"], "pendiente"); self.assertIsNone(prop["revision"]["revisor_declarado"])
        self.assertTrue(prop["sugerencias"]); self.assertTrue(all(p["principal"] is None and p["evidencia_correcta"] is None for p in prop["sugerencias"]))
        # valores distintos se sugieren igual (por región); el candidato de valor idéntico en otra lámina NO se sugiere
        self.assertIn("C000", {p["candidato_id"] for p in prop["sugerencias"]})
        self.assertIn("CVALOR", prop["candidatos_sin_sugerencia"]); self.assertIn("O029", prop["observaciones_sin_candidato"])
        self.assertTrue(all("valor" not in k for p in prop["sugerencias"] for k in p))

    def test_evaluador_rechaza_propuesta_y_verificar_bloquea(self):
        ref = referencia(); ext = extraccion(ref); prop = r.sugerir(ref, ext, "sintetica")
        with self.assertRaises(ValueError):
            evaluar_lecturas(ref, ext, prop)
        with self.assertRaises(r.Rechazo) as c: r.verificar(ref, ext, prop)
        self.assertEqual(c.exception.codigo, 4)
        # contrato oficial pero revisión pendiente: también bloqueado
        oficial = {"contrato": "draft2model.correspondencias_vision", "version_contrato": "0.1.0", "caso": ref["caso"],
                   "huella_referencia": prop["huella_referencia"], "huella_extraccion": prop["huella_extraccion"],
                   "revision": {"revisor_declarado": "", "fecha": "2026-10-24", "estado": "pendiente"}, "pares": [], "sin_respaldo": []}
        with self.assertRaises(r.Rechazo): r.verificar(ref, ext, oficial)

    def test_huella_desactualizada_y_mezcla_procedencia(self):
        ref = referencia(); ext = extraccion(ref); prop = r.sugerir(ref, ext, "s")
        corr = {"contrato": "draft2model.correspondencias_vision", "version_contrato": "0.1.0", "caso": ref["caso"],
                "huella_referencia": prop["huella_referencia"], "huella_extraccion": "0" * 64,
                "revision": {"revisor_declarado": "REVISOR SINTÉTICO", "fecha": "2026-10-24", "estado": "revisado"}, "pares": [], "sin_respaldo": []}
        with self.assertRaises(r.Rechazo) as c: r.verificar(ref, ext, corr)
        self.assertEqual(c.exception.codigo, 4)
        ext2 = copy.deepcopy(ext); ext2["procedencia"]["tipo"] = "expediente"
        with self.assertRaises(r.Rechazo) as c: r.sugerir(ref, ext2, "s")
        self.assertEqual(c.exception.codigo, 3)

    def test_correspondencias_oficiales_revisadas_listas(self):
        # control positivo SINTÉTICO: el humano (aquí, la fixture) decide pares; verificar solo confirma requisitos
        ref = referencia(); ext = extraccion(ref); prop = r.sugerir(ref, ext, "s")
        # decisión SIMULADA de la fixture: una principal por observación (mayor IoU) y cada candidato una sola vez
        pares, usadas, usados = [], set(), set()
        for p in prop["sugerencias"]:
            if p["observacion_id"] in usadas or p["candidato_id"] in usados:
                continue
            usadas.add(p["observacion_id"]); usados.add(p["candidato_id"])
            pares.append({"observacion_id": p["observacion_id"], "candidato_id": p["candidato_id"], "principal": True, "evidencia_correcta": True,
                          "indice_evidencia_referencia": 0, "indice_evidencia_candidato": 0})
        corr = {"contrato": "draft2model.correspondencias_vision", "version_contrato": "0.1.0", "caso": ref["caso"],
                "huella_referencia": prop["huella_referencia"], "huella_extraccion": prop["huella_extraccion"],
                "revision": {"revisor_declarado": "REVISOR SINTÉTICO", "fecha": "2026-10-24", "estado": "revisado"}, "pares": pares, "sin_respaldo": ["CVALOR"]}
        self.assertTrue(r.verificar(ref, ext, corr)["listo_para_medir"])
        res = evaluar_lecturas(ref, ext, corr)
        self.assertTrue(res["datos_sinteticos"]); self.assertEqual(res["metricas"]["cobertura"]["denominador"], 30)
        vacio = copy.deepcopy(ref); vacio["observaciones"] = [o for o in vacio["observaciones"] if o["tipo"] == "cota"]
        self.assertIsNone(r.sugerir(vacio, ext, "s")["revision"]["revisor_declarado"])

    def test_salida_no_se_sobrescribe(self):
        ref = self.escribir("ref.json", referencia()); out = self.tmp / "rec.json"
        self.assertEqual(r.main(["recibir", "--referencia", ref, "--fuentes", str(self.kit), "--salida", str(out)]), 0)
        self.assertEqual(r.main(["recibir", "--referencia", ref, "--fuentes", str(self.kit), "--salida", str(out)]), 2)


if __name__ == "__main__":
    unittest.main()
