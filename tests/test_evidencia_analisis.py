"""Evidencia de análisis ligada al resultado: vínculo, alteraciones, ausencia y compatibilidad de informe/panel.

Usa COPIAS del paquete tests/fixtures/etabs21_sintetico, capturado en ETABS21.1
con datos fabricados. No depende de tmp de sesiones ni conecta con el motor.
Las alteraciones se hacen solo sobre copias temporales verificadas por SHA256.
"""

import copy
import json
import re
import shutil
import tempfile
import unicodedata
import unittest
from pathlib import Path

import pymupdf

from draft2model import evidencia_analisis as ea
from draft2model.informe import aprobar_informe, crear_informe, exportar_informe, main as main_informe, renderizar_html, validar_informe
from draft2model.panel_tecnico import crear_panel
from tests.fixture_etabs import extraer_evidencia

RAIZ_PROYECTO = Path(__file__).resolve().parents[1]
CASO = "demo-integrada-sintetica"
RESULTADO = "72c06efb3bfe477bb1fe565809aeddec"
CONTEXTO = {"titulo": "Ensayo sintético con evidencia de análisis", "hipotesis": ["Datos fabricados para probar software."],
            "faltantes": ["Reglas normativas revisadas no aportadas."], "sitio": None}


def instantanea(carpeta: Path) -> dict:
    return {p.relative_to(carpeta).as_posix(): p.read_bytes() for p in sorted(carpeta.rglob("*")) if p.is_file()}


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name).resolve()
        bundle=extraer_evidencia(self.dir/'evidencia')
        self.raiz = bundle / "private"
        self.corrida = bundle / "analisis" / 'adf97fbc232141e8ae687872c0d71232'
        self.otra_corrida=bundle/'otro_analisis'/'28f6d928fac949acadd19f294e6bf644'
        self.informe_historico=bundle/'informe_historico.json'
        self.caso_dir = self.raiz / CASO
        self.carpeta_resultado = self.caso_dir / "resultados_estructurales" / RESULTADO
        self.resultados = json.loads((self.carpeta_resultado / "resultados.json").read_text(encoding="utf-8"))
        self.fuente = {"raiz": self.raiz, "caso": CASO, "resultado": RESULTADO, "corrida": self.corrida}

    def verificar(self, **cambios):
        f = dict(self.fuente, **cambios)
        return ea.verificar_evidencia(f["raiz"], f["caso"], f["resultado"], f["corrida"])

    def rechaza(self, mensaje=None, **cambios):
        with self.assertRaises(ea.ErrorEvidenciaAnalisis) as ctx:
            self.verificar(**cambios)
        if mensaje:
            self.assertIn(mensaje, str(ctx.exception))
        return ctx.exception

    def editar_json(self, ruta: Path, cambio):
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        cambio(datos)
        ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


class VerificacionTests(Base):
    def test_cadena_real_verificada_sin_rutas_ni_escrituras(self):
        antes = (instantanea(self.raiz), instantanea(self.corrida))
        evidencia = self.verificar()
        self.assertEqual((instantanea(self.raiz), instantanea(self.corrida)), antes)
        self.assertEqual(evidencia["analisis"]["casos"], [{"id": "EST", "estado_csi": 4}])
        self.assertEqual(evidencia["analisis"]["sha256_edb_analizado"], "d317cb7f88b5d62cee61fae8a69a1bbf4e4cdfb07705e3bc595772801ed34bb7")
        self.assertEqual(evidencia["resultado"]["sha256_edb_leido"], evidencia["analisis"]["sha256_edb_analizado"])
        self.assertEqual((evidencia["modelo"]["modelo_id"], evidencia["modelo"]["aprobacion_id"]),
                         ("225f8c4a9a0744fbb702a9f0b9affdc0", "b596d594ceaf4f8687f6ea502a376591"))
        self.assertEqual(evidencia["estados"], {"calculo": "completado_verificado", "revision_resultados": "pendiente",
                                                "conformidad_normativa": "no_evaluada", "correspondencias_tablas": "revision_declarada"})
        self.assertFalse(evidencia["aprueba_resultados"] or evidencia["aprueba_ingenieria"])
        texto = json.dumps(evidencia, ensure_ascii=False)
        for privado in (str(self.dir), str(RAIZ_PROYECTO), ":\\", "tmp", "private"):
            self.assertNotIn(privado, texto)

    def test_edb_y_entrada_alterados(self):
        for archivo, mensaje in (("analizado.EDB", "EDB analizado fue alterado"), ("entrada.edb", "entrada del análisis fue alterada")):
            with self.subTest(archivo):
                ruta = self.corrida / archivo
                original = ruta.read_bytes()
                ruta.write_bytes(original + b"\x00")
                self.rechaza(mensaje)
                ruta.write_bytes(original)
        self.verificar()

    def test_aceptacion_no_aceptada_o_incompleta(self):
        casos = {
            "no aceptada": lambda d: d.update(aceptada=False),
            "estado 3": lambda d: d["estados_casos"].update(EST=3),
            "aprueba resultados": lambda d: d.update(aprueba_resultados=True),
            "campo exitosa añadido": lambda d: d.update(exitosa=True),
            "sin análisis": lambda d: d.update(analisis_ejecutado=False),
            "otro modelo": lambda d: d.update(modelo_id="0" * 32),
            "doble con datos reales": lambda d: d.update(modo="doble", datos_sinteticos=False),
        }
        ruta = self.corrida / "aceptacion_analisis.json"
        original = ruta.read_bytes()
        for nombre, cambio in casos.items():
            with self.subTest(nombre):
                self.editar_json(ruta, cambio)
                self.rechaza()
                ruta.write_bytes(original)

    def test_un_json_exitoso_no_basta(self):
        (self.corrida / "aceptacion_analisis.json").write_text(json.dumps({"aceptada": True, "exitosa": True}), encoding="utf-8")
        self.rechaza("campos exactos")
        vacia = self.dir / "vacia" / ("a" * 32)
        vacia.mkdir(parents=True)
        (vacia / "aceptacion_analisis.json").write_text(json.dumps({"exitosa": True}), encoding="utf-8")
        self.rechaza(corrida=vacia)

    def test_respuesta_y_solicitud_alteradas(self):
        for archivo, cambio in (("respuesta.json", lambda d: d["datos"]["estados_casos"].update(EST=3)),
                                ("respuesta.json", lambda d: d.update(id_solicitud="b" * 32)),
                                ("solicitud.json", lambda d: d.update(casos=["EST", "OTRO"]))):
            with self.subTest(archivo):
                ruta = self.corrida / archivo
                original = ruta.read_bytes()
                self.editar_json(ruta, cambio)
                self.rechaza("no corresponde a la aceptación")
                ruta.write_bytes(original)

    def test_corrida_no_aceptada_o_renombrada(self):
        (self.corrida / "analisis_no_aceptado.json").write_text("{}", encoding="utf-8")
        self.rechaza("no aceptado")
        (self.corrida / "analisis_no_aceptado.json").unlink()
        renombrada = self.corrida.with_name("c" * 32)
        self.corrida.rename(renombrada)
        self.rechaza(corrida=renombrada)

    def test_resultado_alterado_o_no_rederivable(self):
        casos = {
            "valor": ("resultados.json", lambda d: d["resultados"][2].update(valor=4e-06)),
            "respuesta de tablas": ("respuesta_puente.json", lambda d: d["datos"].update(version_etabs="21.0.0")),
            "fila citada con otro filtro": ("trazabilidad.json", lambda d: d["correspondencias"][2]["filtros"].update(Direction="Y")),
            "factor alterado": ("trazabilidad.json", lambda d: d["correspondencias"][0].update(factor=2)),
            "mapeo sin revisión": ("mapeo.json", lambda d: d["revision"].update(estado="borrador")),
        }
        for nombre, (archivo, cambio) in casos.items():
            with self.subTest(nombre):
                ruta = self.carpeta_resultado / archivo
                original = ruta.read_bytes()
                self.editar_json(ruta, cambio)
                self.rechaza()
                ruta.write_bytes(original)
        self.verificar()

    def test_copia_edb_del_caso_alterada(self):
        ruta = self.caso_dir / "resultado_estatico_005" / "analizado.edb"
        ruta.write_bytes(ruta.read_bytes() + b"\x00")
        self.rechaza("copia EDB del caso")

    def test_otro_caso_o_resultado(self):
        self.rechaza(caso="otro-caso")
        self.rechaza(resultado="d" * 32)
        self.rechaza(resultado="no-es-id")

    def test_analisis_aceptado_de_otro_modelo(self):
        otra = self.dir / "otra" / self.otra_corrida.name
        shutil.copytree(self.otra_corrida, otra)
        self.rechaza(corrida=otra)

    def test_revision_del_modelo_o_evidencia_del_expediente_alteradas(self):
        aprobacion = self.caso_dir / "aprobaciones_modelo" / "b596d594ceaf4f8687f6ea502a376591" / "aprobacion.json"
        original = aprobacion.read_bytes()
        self.editar_json(aprobacion, lambda d: d.update(alcance=d["alcance"] + " (editado)"))
        self.rechaza()
        aprobacion.write_bytes(original)
        self.verificar()
        for original_doc in (self.caso_dir / "originales").iterdir():
            original_doc.write_bytes(original_doc.read_bytes() + b"\x00")
            break
        self.rechaza()

    def test_validar_snapshot_contra_otros_resultados(self):
        evidencia = self.verificar()
        otros = copy.deepcopy(self.resultados)
        otros["resultados"][0]["valor"] = 1.0
        with self.assertRaises(ea.ErrorEvidenciaAnalisis):
            ea.validar_evidencia(evidencia, otros)
        for cambio in (lambda e: e["estados"].update(revision_resultados="aprobado"),
                       lambda e: e["analisis"]["casos"][0].update(estado_csi=3),
                       lambda e: e.update(aprueba_resultados=True),
                       lambda e: e["analisis"].update(ruta="C:\\privado\\analizado.edb")):
            alterada = copy.deepcopy(evidencia)
            cambio(alterada)
            with self.assertRaises(ea.ErrorEvidenciaAnalisis):
                ea.validar_evidencia(alterada, self.resultados)

    def test_localizador_cli_todo_o_nada(self):
        self.assertIsNone(ea.fuente_desde_argumentos(None, None, None, None))
        with self.assertRaises(ea.ErrorEvidenciaAnalisis):
            ea.fuente_desde_argumentos(self.raiz, CASO, None, self.corrida)


class InformeConEvidenciaTests(Base):
    def crear(self, **extra):
        return crear_informe(self.resultados, None, copy.deepcopy(CONTEXTO), evidencia_analisis=self.fuente, **extra)

    def test_informe_muestra_estado_separado_sin_rutas_ni_tablas_anidadas(self):
        informe = self.crear()
        self.assertTrue(validar_informe(informe))
        self.assertEqual(informe["evidencia_analisis"], self.verificar())
        estado = informe["siete_resultados"]["estado_modelo_analisis"]
        self.assertEqual((estado["analisis"], estado["revision_resultados"], estado["conformidad_normativa"]),
                         ("completado_verificado", "pendiente", "no_evaluada"))
        self.assertIn("evidencia_analisis", informe["huellas"])
        self.assertEqual(informe["revision"], {"estado": "borrador", "aprobacion": None})
        html = renderizar_html(informe)
        for esperado in ("EST = estado CSI 4 (terminado)", "Revisión de resultados: pendiente",
                         "Conformidad normativa: no_evaluada", "adf97fbc232141e8ae687872c0d71232", "d317cb7f88b5d62c"):
            self.assertIn(esperado, html)
        self.assertNotIn("Estado del solver: no disponible", html)
        for privado in (str(self.dir), str(RAIZ_PROYECTO), "tmp\\a5", "private\\"):
            self.assertNotIn(privado, html)
        self.assertIsNone(re.search(r"<table(?:(?!</table>).)*<table", html, re.S))  # sin tablas anidadas

    def test_exportar_revalida_y_pdf_conserva_la_evidencia(self):
        informe = self.crear()
        with self.assertRaises(ValueError):
            exportar_informe(informe, self.dir / "sin_fuente")  # la evidencia del informe exige su fuente
        self.assertFalse((self.dir / "sin_fuente").exists())
        carpeta = exportar_informe(informe, self.dir / "con_evidencia", evidencia_analisis=self.fuente)
        with pymupdf.open(carpeta / "informe.pdf") as doc:
            texto = unicodedata.normalize("NFKC", "\n".join(p.get_text() for p in doc))
        for esperado in ("CÁLCULO COMPLETADO", "estado CSI 4", "Revisión de resultados: pendiente", "4. Derivas", "Trazabilidad"):
            self.assertIn(esperado, texto)
        self.assertNotIn(str(self.dir), (carpeta / "informe.html").read_text(encoding="utf-8"))
        # Evidencia alterada entre crear y exportar: rechazo, sin carpeta nueva.
        (self.corrida / "analizado.EDB").write_bytes((self.corrida / "analizado.EDB").read_bytes() + b"\x00")
        with self.assertRaises(ValueError):
            exportar_informe(informe, self.dir / "alterada", evidencia_analisis=self.fuente)
        self.assertFalse((self.dir / "alterada").exists())

    def test_snapshot_de_evidencia_manipulado_en_el_informe(self):
        informe = self.crear()
        for cambio in (lambda i: i["evidencia_analisis"]["estados"].update(revision_resultados="aprobado"),
                       lambda i: i["evidencia_analisis"]["analisis"].update(modo="doble"),
                       lambda i: i["siete_resultados"]["estado_modelo_analisis"].update(conformidad_normativa="cumple"),
                       lambda i: i.pop("evidencia_analisis"),
                       lambda i: i.update(evidencia_analisis=None)):
            alterado = copy.deepcopy(informe)
            cambio(alterado)
            with self.assertRaises(ValueError):
                validar_informe(alterado)

    def test_aprobacion_documental_no_aprueba_resultados(self):
        aprobado = aprobar_informe(self.crear(), revisor_declarado="Revisor SINTÉTICO", fecha="2026-10-17", motivo="Prueba documental.")
        self.assertTrue(validar_informe(aprobado))
        self.assertEqual(aprobado["evidencia_analisis"]["estados"]["revision_resultados"], "pendiente")
        self.assertFalse(aprobado["evidencia_analisis"]["aprueba_resultados"])

    def test_evidencia_ajena_al_resultado_rechazada(self):
        otros = copy.deepcopy(self.resultados)
        otros["resultados"][3]["motivo_omision"] = "Otro motivo."
        with self.assertRaises(ValueError):
            crear_informe(otros, None, copy.deepcopy(CONTEXTO), evidencia_analisis=self.fuente)

    def test_cli_con_y_sin_evidencia_completa(self):
        resultados = self.dir / "resultados.json"
        resultados.write_bytes((self.carpeta_resultado / "resultados.json").read_bytes())
        contexto = self.dir / "contexto.json"
        contexto.write_text(json.dumps(CONTEXTO, ensure_ascii=False), encoding="utf-8")
        base = ["--resultados", str(resultados), "--contexto", str(contexto)]
        evidencia = ["--analisis-raiz", str(self.raiz), "--analisis-caso", CASO, "--analisis-resultado", RESULTADO,
                     "--analisis-corrida", str(self.corrida)]
        self.assertEqual(main_informe(base + ["--salida", str(self.dir / "cli")] + evidencia), 0)
        self.assertIn("evidencia_analisis", json.loads((self.dir / "cli" / "informe.json").read_text(encoding="utf-8")))
        self.assertEqual(main_informe(base + ["--salida", str(self.dir / "parcial")] + evidencia[:4]), 1)
        self.assertFalse((self.dir / "parcial").exists())


class CompatibilidadTests(Base):
    def test_sin_evidencia_conserva_forma_y_ausencia_explicita(self):
        informe = crear_informe(self.resultados, None, copy.deepcopy(CONTEXTO))
        self.assertNotIn("evidencia_analisis", informe)
        self.assertNotIn("evidencia_analisis", informe["huellas"])
        self.assertEqual(informe["siete_resultados"]["estado_modelo_analisis"]["analisis"], "no_disponible")
        self.assertIn("Estado del solver: no disponible", renderizar_html(informe))
        with self.assertRaises(ValueError):  # no se puede adjuntar evidencia al exportar un informe que no la contiene
            exportar_informe(informe, self.dir / "x", evidencia_analisis=self.fuente)

    def test_informe_historico_sigue_validando(self):
        self.assertTrue(validar_informe(json.loads(self.informe_historico.read_text(encoding="utf-8"))))


class PanelConEvidenciaTests(Base):
    def datos(self, salida: Path) -> tuple[dict, str]:
        html = salida.read_text(encoding="utf-8")
        return json.loads(html.split('id="datos">')[1].split("</script>")[0]), html

    def test_panel_con_evidencia_sin_rutas(self):
        resultados = self.carpeta_resultado / "resultados.json"
        salida = crear_panel(resultados, None, self.dir / "panel.html", evidencia_analisis=self.fuente)
        datos, html = self.datos(salida)
        self.assertEqual(datos["evidencia_analisis"], self.verificar())
        self.assertIsNone(datos["evaluacion"])
        self.assertIn("Cálculo completado verificado", html)
        self.assertIn("Evidencia de análisis", html)
        for privado in (str(self.dir), str(RAIZ_PROYECTO), "tmp\\\\a5", ":\\\\"):
            self.assertNotIn(privado, html)

    def test_panel_sin_evidencia_y_evidencia_alterada(self):
        resultados = self.carpeta_resultado / "resultados.json"
        datos, _ = self.datos(crear_panel(resultados, None, self.dir / "sin.html"))
        self.assertNotIn("evidencia_analisis", datos)
        (self.corrida / "respuesta.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            crear_panel(resultados, None, self.dir / "alterado.html", evidencia_analisis=self.fuente)
        self.assertFalse((self.dir / "alterado.html").exists())


class RederivacionModalTests(unittest.TestCase):
    def test_case_modal_unico_y_ausencia_no_fabricada(self):
        res={'casos':[{'id':'MOD','tipo':'modal_eigen'}],
             'resultados':[{'id':'T1','caso':'MOD','variable':'periodo','valor':0.442}]}
        table={'clave':'Modal Periods And Frequencies','filas':[{'Case':'MOD','Mode':'1','Period':'0.442'}]}
        data={'tablas':[table]}
        trace={'correspondencias':[{'resultado_id':'T1','tabla':table['clave'],
            'filtros':{'Case':'MOD','Mode':'1'},'campo':'Period','factor':1.0,'fila_indice':0}]}
        ea._rederivar(res,trace,data)
        res['resultados'][0]['valor']=None;trace['correspondencias'][0]['fila_indice']=None
        with self.assertRaises(ea.ErrorEvidenciaAnalisis):ea._rederivar(res,trace,data)
        res['resultados'][0]['valor']=0.442;trace['correspondencias'][0]['fila_indice']=0
        table['filas'].append(copy.deepcopy(table['filas'][0]))
        with self.assertRaises(ea.ErrorEvidenciaAnalisis):ea._rederivar(res,trace,data)


if __name__ == "__main__":
    unittest.main()
