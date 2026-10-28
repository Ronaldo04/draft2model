"""Versiones geométricas en expedientes sintéticos dentro de carpetas temporales."""

import copy
import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from draft2model import gestion_geometria as g
from draft2model.contratos import huella_contenido
from draft2model.ingreso import registrar_expediente
from draft2model.validacion_geometria import validar_geometria

EJEMPLO = Path(__file__).resolve().parents[1] / "examples" / "geometria_sintetica.json"
CASO = "sintetico-001"  # coincide con el id de examples/geometria_sintetica.json


def sha(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def instantanea(carpeta: Path) -> dict:
    return {p.name: p.read_bytes() for p in sorted(carpeta.iterdir())}


def enlazar_carpeta(enlace: Path, destino: Path) -> bool:
    """Junction de Windows (sin privilegios) o, si no es posible, enlace simbólico de carpeta."""
    try:
        import _winapi

        _winapi.CreateJunction(str(destino), str(enlace))
        return True
    except (ImportError, OSError):
        pass
    try:
        os.symlink(destino, enlace, target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        return False


class CasoGeometria(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.trabajo = Path(temp.name)
        self.raiz = self.trabajo / "private"
        pdf = self.trabajo / "plano_sintetico.pdf"
        pdf.write_bytes(b"%PDF-1.4\ncontenido sintetico para pruebas de geometria\n")
        self.manifest = registrar_expediente(CASO, [pdf], self.raiz, uso_autorizado=True, provisional_fuera_alcance=True)
        self.caso_dir = self.manifest.parent
        self.original = self.caso_dir / "originales" / "lamina-0001.pdf"
        self.entrada = self.trabajo / "geometria.json"
        self.entrada.write_bytes(EJEMPLO.read_bytes())  # incluye un espesor faltante declarado (M4)

    def completa(self, espesor=0.15):
        data = json.loads(EJEMPLO.read_text(encoding="utf-8"))
        data["muros"][3]["espesor"] = espesor
        data["faltantes"] = []
        return data

    def escribir(self, data, nombre="otra.json"):
        ruta = self.trabajo / nombre
        ruta.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return ruta

    def importar(self, entrada=None):
        return g.importar_geometria(self.raiz, CASO, entrada or self.entrada)

    def revisar(self, padre, propuesta=None, **extra):
        argumentos = dict(motivo="Se completa el espesor de M4.", fecha="2026-10-15", revisor_declarado="Revisor sintético")
        argumentos.update(extra)
        return g.revisar_geometria(self.raiz, CASO, padre, propuesta if propuesta is not None else self.completa(),
                                   **argumentos)

    def aprobar(self, version, huella, **extra):
        argumentos = dict(huella_esperada=huella, revisor_declarado="Revisor sintético", fecha="2026-10-15",
                          motivo="Geometría sintética completa revisada.", alcance_revision="Geometría de muros y niveles.")
        argumentos.update(extra)
        return g.aprobar_geometria(self.raiz, CASO, version, **argumentos)

    def versiones(self):
        carpeta = self.caso_dir / g.CARPETA_GEOMETRIAS
        return sorted(p.name for p in carpeta.iterdir()) if carpeta.exists() else []


class GestionGeometriaTests(CasoGeometria):
    # -- flujo ----------------------------------------------------------------
    def test_importar_y_consultar(self):
        imp = self.importar()
        self.assertEqual(imp.caso, CASO)
        self.assertEqual(imp.ruta, self.caso_dir / "geometrias" / imp.identificador)
        self.assertEqual(sorted(p.name for p in imp.ruta.iterdir()),
                         ["fuente_importada.json", "geometria.json", "version.json"])
        self.assertEqual((imp.ruta / "fuente_importada.json").read_bytes(), self.entrada.read_bytes())
        self.assertTrue(imp.comprobacion.correcta, imp.comprobacion.problemas)

        meta = imp.metadatos
        self.assertEqual((meta["operacion"], meta["padre"], meta["caso"]), ("importacion", None, CASO))
        self.assertEqual(meta["expediente_sha256"], sha(self.manifest))
        self.assertEqual(meta["originales_verificados"], [{"id": "L0001", "sha256": sha(self.original)}])
        self.assertEqual(meta["sha256_geometria"], sha(imp.ruta / "geometria.json"))
        self.assertEqual(meta["huella_contenido"], validar_geometria(json.loads(EJEMPLO.read_text(encoding="utf-8"))).huella_contenido)
        self.assertEqual(meta["alcance"]["estado"], "fuera_mvp_declarado")
        self.assertEqual(meta["alcance"], json.loads(self.manifest.read_text(encoding="utf-8"))["alcance"])
        self.assertTrue(meta["datos_sinteticos"])
        self.assertEqual(meta["procedencia"]["tipo"], "sintetico")
        self.assertEqual(meta["identidad_revisor"], "declarada_no_verificada")

        consulta = g.consultar_version(self.raiz, CASO, imp.identificador)
        self.assertEqual(consulta.geometria, json.loads(EJEMPLO.read_text(encoding="utf-8")))
        self.assertEqual(consulta.metadatos, meta)
        self.assertTrue(consulta.comprobacion.correcta)
        self.assertEqual(consulta.comprobacion.cadena, [imp.identificador])
        json.dumps(consulta.comprobacion.a_dict(), allow_nan=False)

    def test_alcance_sin_marca_provisional_se_copia_tal_cual(self):
        pdf = self.trabajo / "otro.pdf"
        pdf.write_bytes(b"%PDF-1.4\notro original sintetico\n")
        registrar_expediente("caso-normal", [pdf], self.raiz, uso_autorizado=True)
        data = json.loads(EJEMPLO.read_text(encoding="utf-8"))
        data["id"] = "caso-normal"
        imp = g.importar_geometria(self.raiz, "caso-normal", self.escribir(data))
        self.assertEqual(imp.metadatos["alcance"], {"estado": "pendiente_verificar", "uso": "pendiente", "motivos": []})

    def test_faltantes_admitidos_al_guardar_y_bloqueados_al_aprobar(self):
        imp = self.importar()
        self.assertEqual([f["id"] for f in imp.comprobacion.validacion["faltantes"]], ["M4"])
        with self.assertRaises(g.ErrorEvidencia) as ctx:
            self.aprobar(imp.identificador, imp.comprobacion.huella_contenido)
        self.assertIn("faltante", str(ctx.exception))
        self.assertEqual(self.versiones(), [imp.identificador])

    def test_revision_y_aprobacion_explicita(self):
        imp = self.importar()
        antes = instantanea(imp.ruta)
        rev = self.revisar(imp.identificador)
        self.assertTrue(rev.comprobacion.correcta, rev.comprobacion.problemas)
        self.assertEqual(rev.metadatos["padre"]["id"], imp.identificador)
        self.assertEqual(rev.metadatos["revision"]["revisor_declarado"], "Revisor sintético")
        self.assertNotIn("fuente_importada.json", [p.name for p in rev.ruta.iterdir()])

        ap = self.aprobar(rev.identificador, rev.comprobacion.huella_contenido)
        self.assertTrue(ap.comprobacion.correcta, ap.comprobacion.problemas)
        self.assertEqual(ap.comprobacion.cadena, [ap.identificador, rev.identificador, imp.identificador])
        geometria = g.consultar_version(self.raiz, CASO, ap.identificador).geometria
        self.assertEqual(geometria["revision"], {"estado": "aprobado", "aprobacion": {
            "declarada_por": "Revisor sintético", "fecha": "2026-10-15",
            "huella_contenido": rev.comprobacion.huella_contenido,
            "alcance": "Geometría de muros y niveles.", "observaciones": "Geometría sintética completa revisada.",
        }})
        self.assertTrue(validar_geometria(geometria).disponible_para_modelado)
        registro = ap.metadatos["aprobacion"]
        self.assertEqual((registro["identidad_revisor"], registro["certifica_seguridad_estructural"],
                          registro["aprueba_artefactos_derivados"]), ("declarada_no_verificada", False, False))
        # El contenido geométrico (sin revisión) no cambia al aprobar.
        self.assertEqual(ap.metadatos["huella_contenido"], rev.metadatos["huella_contenido"])
        self.assertEqual(instantanea(imp.ruta), antes)
        self.assertEqual(len(self.versiones()), 3)

    def test_aprobacion_ligada_a_la_huella_esperada(self):
        imp = self.importar()
        rev1 = self.revisar(imp.identificador)
        rev2 = self.revisar(rev1.identificador, self.completa(espesor=0.25), motivo="Corrige espesor de M4.")
        for huella in ("0" * 64, rev1.comprobacion.huella_contenido):
            with self.subTest(huella=huella[:8]), self.assertRaises(g.ErrorEvidencia) as ctx:
                self.aprobar(rev2.identificador, huella)
            self.assertIn("huella esperada", str(ctx.exception))
        for huella in ("corta", None, "A" * 64):
            with self.subTest(huella=huella), self.assertRaises(g.ErrorGestion):
                self.aprobar(rev2.identificador, huella)
        self.assertEqual(len(self.versiones()), 3)

    def test_aprobacion_importada_se_rechaza_sin_reescribirla(self):
        aprobada = self.completa()
        aprobada["revision"] = {"estado": "aprobado", "aprobacion": {
            "declarada_por": "Alguien", "fecha": "2026-10-15", "huella_contenido": huella_contenido(aprobada)}}
        self.assertTrue(validar_geometria(aprobada).disponible_para_modelado)
        ruta = self.escribir(aprobada, "aprobada.json")
        antes = ruta.read_bytes()
        with self.assertRaises(g.ErrorEvidencia) as ctx:
            self.importar(ruta)
        self.assertIn("aprobar_geometria", str(ctx.exception))
        self.assertEqual(ruta.read_bytes(), antes)
        # Aprobación no nula con estado borrador: incoherente para el validador.
        incoherente = copy.deepcopy(aprobada)
        incoherente["revision"]["estado"] = "borrador"
        with self.assertRaises(g.ErrorEvidencia):
            self.importar(self.escribir(incoherente, "incoherente.json"))
        self.assertEqual(self.versiones(), [])

    def test_revision_posterior_no_hereda_aprobacion(self):
        imp = self.importar()
        rev = self.revisar(imp.identificador)
        ap = self.aprobar(rev.identificador, rev.comprobacion.huella_contenido)
        antes = instantanea(ap.ruta)
        aprobada = g.consultar_version(self.raiz, CASO, ap.identificador).geometria
        with self.assertRaises(g.ErrorEvidencia) as ctx:
            self.revisar(ap.identificador, aprobada)
        self.assertIn("borrador", str(ctx.exception))
        propuesta = copy.deepcopy(aprobada)
        propuesta["revision"] = {"estado": "borrador", "aprobacion": None}
        propuesta["muros"][0]["espesor"] = 0.2
        hija = self.revisar(ap.identificador, propuesta, motivo="Nueva medición de M1.")
        self.assertEqual(hija.metadatos["estado_revision_geometria"], "borrador")
        self.assertFalse(hija.comprobacion.validacion["disponible_para_modelado"])
        self.assertEqual(instantanea(ap.ruta), antes)
        with self.assertRaises(g.ErrorEvidencia):  # una aprobación no se apila sobre otra
            self.aprobar(ap.identificador, ap.comprobacion.huella_contenido)

    def test_ramas_desde_un_mismo_padre(self):
        imp = self.importar()
        antes = instantanea(imp.ruta)
        a = self.revisar(imp.identificador, self.completa(0.15), motivo="Rama A.")
        b = self.revisar(imp.identificador, self.completa(0.25), motivo="Rama B.")
        self.assertNotEqual(a.identificador, b.identificador)
        self.assertEqual(a.metadatos["padre"]["id"], b.metadatos["padre"]["id"])
        self.assertNotEqual(a.metadatos["huella_contenido"], b.metadatos["huella_contenido"])
        for rama in (a, b):
            self.assertTrue(g.comprobar_version(self.raiz, CASO, rama.identificador).correcta)
        self.assertEqual(instantanea(imp.ruta), antes)
        self.assertEqual(len(self.versiones()), 3)

    def test_propuesta_de_revision_no_se_modifica(self):
        imp = self.importar()
        propuesta = self.completa()
        antes = copy.deepcopy(propuesta)
        rev = self.revisar(imp.identificador, propuesta)
        self.assertEqual(propuesta, antes)
        consulta = g.consultar_version(self.raiz, CASO, rev.identificador)
        consulta.geometria["muros"][0]["espesor"] = 99
        self.assertEqual(g.consultar_version(self.raiz, CASO, rev.identificador).geometria, antes)

    # -- rechazos de entrada --------------------------------------------------
    def test_revision_exige_motivo_fecha_y_revisor(self):
        imp = self.importar()
        for extra in ({"motivo": ""}, {"motivo": None}, {"revisor_declarado": "  "}, {"fecha": "15/10/2026"},
                      {"fecha": "2026-02-30"}, {"fecha": 20261015}):
            with self.subTest(extra=extra), self.assertRaises(g.ErrorGestion):
                self.revisar(imp.identificador, **extra)
        self.assertEqual(self.versiones(), [imp.identificador])

    def test_entradas_inconsistentes_o_de_otro_caso(self):
        rota = json.loads(EJEMPLO.read_text(encoding="utf-8"))
        rota["muros"][0]["nodo_fin"] = "Z"
        otro = json.loads(EJEMPLO.read_text(encoding="utf-8"))
        otro["id"] = "otro-caso"
        for nombre, data in (("rota", rota), ("otro", otro)):
            with self.subTest(nombre=nombre), self.assertRaises(g.ErrorEvidencia):
                self.importar(self.escribir(data, f"{nombre}.json"))
        imp = self.importar()
        with self.assertRaises(g.ErrorEvidencia):
            self.revisar(imp.identificador, rota)
        self.assertEqual(self.versiones(), [imp.identificador])

    def test_json_duplicado_o_no_finito(self):
        for nombre, texto, error in (
            ("duplicado", '{"id": "a", "id": "b"}', g.ErrorGestion),
            ("nan", '{"id": NaN}', g.ErrorGestion),
            ("infinity", '{"id": Infinity}', g.ErrorGestion),
        ):
            with self.subTest(nombre=nombre), self.assertRaises(error):
                ruta = self.trabajo / f"{nombre}.json"
                ruta.write_text(texto, encoding="utf-8")
                self.importar(ruta)
        texto = EJEMPLO.read_text(encoding="utf-8")
        for nombre, sustituto in (("1e999", "1e999"), ("entero_enorme", "1" + "0" * 1000)):
            with self.subTest(nombre=nombre), self.assertRaises(g.ErrorEvidencia):
                ruta = self.trabajo / f"{nombre}.json"
                ruta.write_text(texto.replace('"x": 4.0', f'"x": {sustituto}', 1), encoding="utf-8")
                self.importar(ruta)
        self.assertEqual(self.versiones(), [])

    def test_datos_sinteticos_no_se_convierten(self):
        imp = self.importar()
        propuesta = self.completa()
        propuesta["procedencia"] = {"tipo": "plano", "descripcion": "Supuesta lámina real."}
        with self.assertRaises(g.ErrorEvidencia) as ctx:
            self.revisar(imp.identificador, propuesta)
        self.assertIn("sintética", str(ctx.exception))
        self.assertEqual(self.versiones(), [imp.identificador])

    def test_rutas_e_identificadores_invalidos(self):
        for caso in ("../" + CASO, "CON", "a/b", "", 5, "no-existe"):
            with self.subTest(caso=caso), self.assertRaises(g.ErrorGestion):
                g.importar_geometria(self.raiz, caso, self.entrada)
        imp = self.importar()
        for ident in ("../../x", "abc", imp.identificador.upper(), "0" * 32, None):
            with self.subTest(ident=ident):
                with self.assertRaises(g.ErrorGestion):
                    g.comprobar_version(self.raiz, CASO, ident)
                with self.assertRaises(g.ErrorGestion):
                    self.revisar(ident)
                with self.assertRaises(g.ErrorGestion):
                    self.aprobar(ident, "0" * 64)
        self.assertEqual(self.versiones(), [imp.identificador])

    def test_carpeta_geometrias_enlazada(self):
        externo = self.trabajo / "fuera_del_caso"
        externo.mkdir()
        enlace = self.caso_dir / "geometrias"
        if not enlazar_carpeta(enlace, externo):
            self.skipTest("El sistema no permite crear junctions ni enlaces simbólicos de carpeta.")
        try:
            with self.assertRaises(g.ErrorGestion) as ctx:
                self.importar()
            self.assertIn("fuera del caso", str(ctx.exception))
            self.assertEqual(list(externo.iterdir()), [])
        finally:
            os.rmdir(enlace)
        # Una carpeta de versiones existente reemplazada por un enlace tampoco se lee ni se usa.
        imp = self.importar()
        movida = self.trabajo / "movida"
        shutil.move(str(enlace), str(movida))
        self.assertTrue(enlazar_carpeta(enlace, movida))
        try:
            antes = instantanea(movida / imp.identificador)
            with self.assertRaises(g.ErrorGestion):
                g.comprobar_version(self.raiz, CASO, imp.identificador)
            with self.assertRaises(g.ErrorGestion):
                self.revisar(imp.identificador)
            self.assertEqual(sorted(p.name for p in movida.iterdir()), [imp.identificador])
            self.assertEqual(instantanea(movida / imp.identificador), antes)
        finally:
            os.rmdir(enlace)

    def test_fallo_de_escritura_sin_version_parcial(self):
        escribir = Path.write_bytes
        llamadas = []

        def falla_en_la_segunda(ruta, contenido):
            llamadas.append(ruta.name)
            if len(llamadas) == 2:
                raise OSError("disco lleno simulado")
            return escribir(ruta, contenido)

        with mock.patch.object(Path, "write_bytes", falla_en_la_segunda), self.assertRaises(OSError):
            self.importar()
        self.assertEqual(list((self.caso_dir / "geometrias").iterdir()), [])  # ni versión ni temporal
        self.assertTrue(self.importar().comprobacion.correcta)


class AlteracionesTests(CasoGeometria):
    """Expediente, originales, fuente o versiones alterados después de registrar."""

    def setUp(self):
        super().setUp()
        self.imp = self.importar()
        self.rev = self.revisar(self.imp.identificador)

    def alterar(self, ruta: Path, accion, texto_esperado, versiones=None):
        respaldo = ruta.read_bytes()
        accion(ruta)
        try:
            for version in versiones or (self.imp.identificador, self.rev.identificador):
                comp = g.comprobar_version(self.raiz, CASO, version)
                self.assertFalse(comp.correcta)
                self.assertTrue(any(texto_esperado in p for p in comp.problemas), comp.problemas)
                json.dumps(comp.a_dict(), allow_nan=False)
            with self.assertRaises(g.ErrorEvidencia):
                self.aprobar(self.rev.identificador, self.rev.comprobacion.huella_contenido)
            with self.assertRaises(g.ErrorEvidencia):
                self.revisar(self.rev.identificador, self.completa(0.2))
        finally:
            ruta.write_bytes(respaldo)
        self.assertEqual(len(self.versiones()), 2)
        self.assertTrue(g.comprobar_version(self.raiz, CASO, self.rev.identificador).correcta)

    def test_expediente_alterado(self):
        self.alterar(self.manifest, lambda p: p.write_bytes(p.read_bytes() + b"\n"), "expediente cambió")
        self.alterar(self.manifest, lambda p: p.write_bytes(b"{no es json"), "expediente.json")
        # Con el expediente ilegible tampoco se importa una versión nueva.
        respaldo = self.manifest.read_bytes()
        self.manifest.write_bytes(b"{no es json")
        try:
            with self.assertRaises(g.ErrorEvidencia):
                self.importar()
        finally:
            self.manifest.write_bytes(respaldo)
        self.assertEqual(len(self.versiones()), 2)

    def test_original_alterado_o_ausente(self):
        self.alterar(self.original, lambda p: p.write_bytes(p.read_bytes() + b"%cambio\n"), "alterado")
        self.alterar(self.original, lambda p: p.unlink(), "ausente")

    def test_fuente_importada_alterada_o_ausente(self):
        fuente = self.imp.ruta / "fuente_importada.json"
        self.alterar(fuente, lambda p: p.write_text("{}", encoding="utf-8"), "fuente importada alterada")
        self.alterar(fuente, lambda p: p.unlink(), "fuente_importada.json ausente")

    def test_fuente_con_hash_rehecho_pero_contenido_distinto(self):
        fuente = self.imp.ruta / "fuente_importada.json"
        version = self.imp.ruta / "version.json"
        respaldo_meta = version.read_bytes()
        fuente.write_text("{}", encoding="utf-8")
        meta = json.loads(respaldo_meta)
        meta["fuente"]["sha256"] = sha(fuente)
        version.write_text(json.dumps(meta), encoding="utf-8")
        comp = g.comprobar_version(self.raiz, CASO, self.imp.identificador)
        self.assertTrue(any("no corresponde a geometria.json" in p for p in comp.problemas), comp.problemas)

    def test_geometria_o_metadatos_alterados(self):
        geo = self.rev.ruta / "geometria.json"
        self.alterar(geo, lambda p: p.write_bytes(p.read_bytes().replace(b"  ", b" ")), "alterado",
                     versiones=[self.rev.identificador])
        self.alterar(geo, lambda p: p.unlink(), "geometria.json ausente", versiones=[self.rev.identificador])
        meta = self.rev.ruta / "version.json"

        def cambiar_huella(p):
            datos = json.loads(p.read_text(encoding="utf-8"))
            datos["huella_contenido"] = "0" * 64
            p.write_text(json.dumps(datos), encoding="utf-8")

        self.alterar(meta, cambiar_huella, "huella del contenido", versiones=[self.rev.identificador])
        self.alterar(meta, lambda p: p.write_text("[]", encoding="utf-8"), "no es un objeto",
                     versiones=[self.rev.identificador])

    def test_version_padre_alterada_se_detecta_desde_la_hija(self):
        geo = self.imp.ruta / "geometria.json"
        respaldo = geo.read_bytes()
        geo.write_bytes(respaldo + b"\n")
        try:
            comp = g.comprobar_version(self.raiz, CASO, self.rev.identificador)
            self.assertFalse(comp.correcta)
            self.assertTrue(any(self.imp.identificador in p for p in comp.problemas), comp.problemas)
        finally:
            geo.write_bytes(respaldo)

    def test_aprobacion_alterada_con_hashes_rehechos(self):
        ap = self.aprobar(self.rev.identificador, self.rev.comprobacion.huella_contenido)
        geo, version = ap.ruta / "geometria.json", ap.ruta / "version.json"
        datos = json.loads(geo.read_text(encoding="utf-8"))
        datos["muros"][0]["espesor"] = 0.3  # cambia el contenido aprobado
        geo.write_text(json.dumps(datos), encoding="utf-8")
        meta = json.loads(version.read_text(encoding="utf-8"))
        meta["sha256_geometria"] = sha(geo)
        version.write_text(json.dumps(meta), encoding="utf-8")
        comp = g.comprobar_version(self.raiz, CASO, ap.identificador)
        self.assertFalse(comp.correcta)
        self.assertTrue(any("aprobación" in p for p in comp.problemas), comp.problemas)

    def test_metadatos_derivados_alterados_sin_rehacer_hashes(self):
        cambios = {
            "procedencia": {"tipo": "plano", "descripcion": "Origen alterado"},
            "originales_verificados": [],
            "validacion": {"disponible_para_modelado": True},
            "estado_revision_geometria": "aprobado",
            "version_registro": "999",
            "contrato_geometria": {"contrato": "otro", "version_contrato": "0.1.0"},
            "identidad_revisor": "autenticada",
            "aviso": "Certificación estructural",
            "datos_sinteticos": 1,  # True y 1 no son equivalentes en el contrato JSON.
        }
        for clave, valor in cambios.items():
            def cambiar(ruta, clave=clave, valor=valor):
                meta = json.loads(ruta.read_bytes())
                meta[clave] = valor
                ruta.write_text(json.dumps(meta), encoding="utf-8")
            for version in (self.imp, self.rev):
                with self.subTest(campo=clave, operacion=version.metadatos["operacion"]):
                    self.alterar(version.ruta / "version.json", cambiar,
                                 "sintéticos" if clave == "datos_sinteticos" else clave,
                                 versiones=[self.rev.identificador])

    def test_expediente_y_alcance_del_padre_se_comprueban_desde_hija(self):
        for clave, valor, mensaje in (
            ("expediente_sha256", "0" * 64, "expediente cambió"),
            ("alcance", {"estado": "otro"}, "alcance"),
        ):
            def cambiar(ruta, clave=clave, valor=valor):
                meta = json.loads(ruta.read_bytes())
                meta[clave] = valor
                ruta.write_text(json.dumps(meta), encoding="utf-8")
            with self.subTest(campo=clave):
                self.alterar(self.imp.ruta / "version.json", cambiar, mensaje)

    def test_huella_del_vinculo_padre_se_contrasta(self):
        def cambiar(ruta):
            meta = json.loads(ruta.read_bytes())
            meta["padre"]["huella_contenido"] = "0" * 64
            ruta.write_text(json.dumps(meta), encoding="utf-8")
        self.alterar(self.rev.ruta / "version.json", cambiar, "huella del contenido",
                     versiones=[self.rev.identificador])

    def test_registro_aprobacion_corresponde_a_geometria_y_limitaciones(self):
        ap = self.aprobar(self.rev.identificador, self.rev.comprobacion.huella_contenido)
        ruta = ap.ruta / "version.json"
        original = ruta.read_bytes()
        cambios = {
            "revisor_declarado": "Otro revisor", "fecha": "2026-01-01",
            "motivo": "Otro motivo", "alcance_revision": "Otro alcance",
            "huella_esperada": "0" * 64, "identidad_revisor": "autenticada",
            "certifica_seguridad_estructural": True, "aprueba_artefactos_derivados": True,
        }
        for clave, valor in cambios.items():
            with self.subTest(campo=clave):
                meta = json.loads(original)
                meta["aprobacion"][clave] = valor
                ruta.write_text(json.dumps(meta), encoding="utf-8")
                try:
                    consulta = g.consultar_version(self.raiz, CASO, ap.identificador)
                    self.assertFalse(consulta.comprobacion.correcta)
                    self.assertTrue(any("metadatos de aprobación" in p for p in consulta.comprobacion.problemas))
                    propuesta = copy.deepcopy(consulta.geometria)
                    propuesta["revision"] = {"estado": "borrador", "aprobacion": None}
                    with self.assertRaises(g.ErrorEvidencia):
                        self.revisar(ap.identificador, propuesta)
                finally:
                    ruta.write_bytes(original)
        self.assertTrue(g.comprobar_version(self.raiz, CASO, ap.identificador).correcta)

    def test_fecha_e_identidad_revision_persistidas_se_validan(self):
        for clave, valor, mensaje in (("fecha", "fecha-invalida", "fecha"),
                                       ("identidad_revisor", "autenticada", "identidad")):
            def cambiar(ruta, clave=clave, valor=valor):
                meta = json.loads(ruta.read_bytes())
                meta["revision"][clave] = valor
                ruta.write_text(json.dumps(meta), encoding="utf-8")
            with self.subTest(campo=clave):
                self.alterar(self.rev.ruta / "version.json", cambiar, mensaje,
                             versiones=[self.rev.identificador])


if __name__ == "__main__":
    unittest.main()
