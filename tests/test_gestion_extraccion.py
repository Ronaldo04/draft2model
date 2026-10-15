"""Integración local de extracciones con expediente, revisión y recorte sintéticos."""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pymupdf

from draft2model import gestion_extraccion as g
from draft2model.ingreso import file_hash, registrar_expediente
from draft2model.recortes import generar_recorte
from draft2model.revision_documental import revisar_expediente

CASO = "sintetico-gestion"


def crear_caso(raiz: Path, trabajo: Path):
    """Expediente fuera del MVP con un PDF sintético de dos páginas, revisión y un recorte."""
    pdf = trabajo / "plano_sintetico.pdf"
    with pymupdf.open() as doc:
        for _ in range(2):
            page = doc.new_page(width=400, height=300)
            page.draw_rect((50, 50, 350, 250), color=(0, 0, 0))
        doc.save(pdf)
    manifest = registrar_expediente(CASO, [pdf], raiz, uso_autorizado=True, provisional_fuera_alcance=True)
    revisar_expediente(manifest, max_lado=256)
    recorte_json = generar_recorte(manifest, "L0001", 1, [0.0, 0.0, 0.5, 0.5], dpi=72)
    return manifest, json.loads(recorte_json.read_text(encoding="utf-8"))


def extraccion(manifest: Path, recorte: dict) -> dict:
    expediente = json.loads(manifest.read_text(encoding="utf-8"))
    sha = expediente["archivos"][0]["sha256"]

    def ev(bbox, con_recorte=False):
        item = {"archivo_id": "L0001", "pagina": 1, "original_sha256": sha, "bbox_normalizada": bbox}
        if con_recorte:
            item.update(recorte_id=recorte["id"], imagen_sha256=recorte["imagen_sha256"])
        return item

    return {
        "contrato": "draft2model.extraccion_preliminar",
        "version_contrato": "0.1.0",
        "caso": CASO,
        "procedencia": {"tipo": "expediente", "descripcion": "Lectura manual sintética para pruebas."},
        "alcance": expediente["alcance"],
        "sistema_coordenadas": "pagina_visible_normalizada",
        "candidatos": [
            {"id": "C001", "tipo": "cota", "valor_propuesto": 2.6, "unidad": "m",
             "metodo": {"tipo": "manual"}, "evidencia": [ev([0.1, 0.1, 0.2, 0.2], True)]},
            {"id": "C002", "tipo": "cota", "valor_propuesto": None, "unidad": "desconocida",
             "metodo": {"tipo": "manual"}, "evidencia": [ev([0.3, 0.1, 0.4, 0.2])]},
            {"id": "C003", "tipo": "etiqueta", "valor_propuesto": "EJE A", "unidad": "no_aplica",
             "metodo": {"tipo": "vision", "herramienta": "pendiente"}, "evidencia": [ev([0.6, 0.1, 0.7, 0.2])]},
            {"id": "C004", "tipo": "elemento", "valor_propuesto": "muro", "unidad": "no_aplica",
             "metodo": {"tipo": "manual"}, "evidencia": [ev([0.1, 0.5, 0.9, 0.6])]},
        ],
    }


def instantanea(carpeta: Path) -> dict:
    return {p.relative_to(carpeta).as_posix(): p.read_bytes() for p in sorted(carpeta.rglob("*")) if p.is_file()}


def enlazar_carpeta(enlace: Path, destino: Path) -> str:
    """Crea una junction de Windows o, si no es posible, un enlace simbólico de carpeta.

    Devuelve el tipo creado o None. Las junctions no requieren privilegios de symlink.
    """
    try:
        import _winapi

        _winapi.CreateJunction(str(destino), str(enlace))
        return "junction"
    except (ImportError, OSError):
        pass
    try:
        os.symlink(destino, enlace, target_is_directory=True)
        return "symlink"
    except (OSError, NotImplementedError):
        return None


def quitar_enlace(enlace: Path) -> None:
    """Elimina el enlace sin tocar el contenido de su destino."""
    if os.path.lexists(enlace):
        try:
            os.rmdir(enlace)  # junction o symlink de carpeta
        except OSError:
            os.unlink(enlace)


class CasoSintetico(unittest.TestCase):
    """Preparación común: expediente, revisión y recorte sintéticos en una carpeta temporal."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.trabajo = Path(temp.name)
        self.raiz = self.trabajo / "private"
        self.manifest, self.recorte = crear_caso(self.raiz, self.trabajo)
        self.caso_dir = self.manifest.parent
        self.original = self.caso_dir / "originales" / "lamina-0001.pdf"
        self.imagen = self.caso_dir / "recortes" / self.recorte["id"] / "recorte.png"
        self.data = extraccion(self.manifest, self.recorte)
        self.entrada = self.escribir(self.data)

    def escribir(self, data, nombre="entrada.json"):
        ruta = self.trabajo / nombre
        ruta.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return ruta

    def versiones(self):
        carpeta = self.caso_dir / g.CARPETA_VERSIONES
        return sorted(p.name for p in carpeta.iterdir()) if carpeta.exists() else []

    def exportaciones(self):
        carpeta = self.caso_dir / g.CARPETA_EXPORTACIONES
        return sorted(p.name for p in carpeta.iterdir()) if carpeta.exists() else []

    def importar(self):
        return g.importar_extraccion(self.raiz, CASO, self.entrada)

    def revisar_c001(self, padre, **extra):
        argumentos = dict(estado="revisado", motivo="Se lee 2.65 en el recorte.", fecha="2026-10-15",
                          revisor_declarado="Revisor sintético", valor_revisado=2.65, unidad_revisada="m")
        argumentos.update(extra)
        return g.corregir_version(self.raiz, CASO, padre, "C001", **argumentos)


class GestionExtraccionTests(CasoSintetico):
    # -- flujo completo --------------------------------------------------
    def test_flujo_importar_corregir_exportar(self):
        imp = self.importar()
        carpeta = imp.ruta
        self.assertEqual(sorted(p.name for p in carpeta.iterdir()),
                         ["extraccion.json", "fuente_importada.json", "reporte.json", "version.json"])
        self.assertEqual((carpeta / "fuente_importada.json").read_bytes(), self.entrada.read_bytes())
        meta = json.loads((carpeta / "version.json").read_text(encoding="utf-8"))
        self.assertEqual((meta["operacion"], meta["padre"], meta["aprobacion_ingenieria"]), ("importacion", None, None))
        self.assertEqual({a["tipo"] for a in meta["archivos_verificados"]}, {"original", "imagen_recorte"})
        self.assertTrue(json.loads((carpeta / "reporte.json").read_text(encoding="utf-8"))["correcta"])

        v1 = self.revisar_c001(imp.identificador)
        v2 = g.corregir_version(self.raiz, CASO, v1.identificador, "C004", estado="rechazado",
                                motivo="Es una línea de cota.", fecha="2026-10-15", revisor_declarado="Revisor sintético")
        self.assertEqual(v2.datos["padre"]["id"], v1.identificador)
        self.assertEqual(v1.datos["padre"], {"id": imp.identificador, "huella_extraccion": meta["huella_extraccion"]})
        self.assertEqual(v1.datos["correccion"]["identidad_revisor"], "declarada_no_verificada")

        exp = g.exportar_version(self.raiz, CASO, v2.identificador)
        datos = json.loads(exp.ruta.read_text(encoding="utf-8"))
        self.assertEqual([c["id"] for c in datos["candidatos"]], ["C001"])
        self.assertEqual(datos["excluidos"], {"pendientes": ["C002", "C003"], "rechazados": ["C004"]})
        self.assertIsNone(datos["aprobacion_ingenieria"])
        c001 = datos["candidatos"][0]
        self.assertEqual((c001["valor_propuesto"], c001["valor_revisado"]), (2.6, 2.65))
        self.assertEqual(c001["evidencia"][0]["estado_referencia"], "comprobada")
        self.assertEqual(datos["origen"]["extraccion_id"], v2.identificador)
        for clave in ("nodos", "muros", "niveles"):
            self.assertNotIn(clave, datos)
        # Una segunda exportación no sobrescribe la primera.
        g.exportar_version(self.raiz, CASO, v2.identificador)
        self.assertEqual(len(self.exportaciones()), 2)

    def test_conserva_fuera_mvp_y_procedencia(self):
        imp = self.importar()
        alcance = json.loads(self.manifest.read_text(encoding="utf-8"))["alcance"]
        self.assertEqual(alcance["estado"], "fuera_mvp_declarado")
        self.assertIn("fuera_mvp", {h.codigo for h in imp.comprobacion.resultado.advertencias})
        v1 = self.revisar_c001(imp.identificador)
        datos = g.exportar_version(self.raiz, CASO, v1.identificador).datos
        self.assertEqual(datos["alcance"], alcance)
        self.assertEqual(datos["procedencia"], self.data["procedencia"])
        # Retirar la marca en la entrada se rechaza.
        self.data["alcance"] = {"estado": "pendiente_verificar", "uso": "pendiente", "motivos": []}
        with self.assertRaises(g.ErrorEvidencia):
            g.importar_extraccion(self.raiz, CASO, self.escribir(self.data, "sin_marca.json"))

    def test_versiones_anteriores_no_cambian(self):
        imp = self.importar()
        antes = instantanea(imp.ruta)
        v1 = self.revisar_c001(imp.identificador)
        self.revisar_c001(v1.identificador, valor_revisado=2.6, fecha="2026-10-16")
        g.exportar_version(self.raiz, CASO, v1.identificador)
        self.assertEqual(instantanea(imp.ruta), antes)
        self.assertEqual(len(self.versiones()), 3)
        original = json.loads((imp.ruta / "extraccion.json").read_text(encoding="utf-8"))
        self.assertNotIn("revision", original["candidatos"][0])
        self.assertTrue(g.validar_version(self.raiz, CASO, imp.identificador).correcta)

    def test_datos_desconocidos_permanecen(self):
        imp = self.importar()
        guardado = json.loads((imp.ruta / "extraccion.json").read_text(encoding="utf-8"))
        c002 = guardado["candidatos"][1]
        self.assertEqual((c002["valor_propuesto"], c002["unidad"]), (None, "desconocida"))
        with self.assertRaises(g.ErrorEvidencia):
            g.corregir_version(self.raiz, CASO, imp.identificador, "C002", estado="revisado", motivo="m",
                               fecha="2026-10-15", revisor_declarado="r", valor_revisado=None, unidad_revisada="m")
        with self.assertRaises(g.ErrorEvidencia):
            g.corregir_version(self.raiz, CASO, imp.identificador, "C001", estado="revisado", motivo="m",
                               fecha="2026-10-15", revisor_declarado="r", valor_revisado="2.65", unidad_revisada="m")
        v = g.corregir_version(self.raiz, CASO, imp.identificador, "C002", estado="revisado", motivo="Se lee 3.10",
                               fecha="2026-10-15", revisor_declarado="r", valor_revisado=3.1, unidad_revisada="desconocida")
        datos = g.exportar_version(self.raiz, CASO, v.identificador).datos
        self.assertEqual(datos["candidatos"][0]["unidad_revisada"], "desconocida")
        self.assertEqual(len(self.versiones()), 2)

    # -- entradas inválidas ---------------------------------------------
    def test_entradas_invalidas_no_persisten(self):
        duplicada = self.trabajo / "duplicada.json"
        duplicada.write_text('{"caso": "a", "caso": "b"}', encoding="utf-8")
        nan = self.trabajo / "nan.json"
        nan.write_text('{"valor": NaN}', encoding="utf-8")
        for ruta in (duplicada, nan, self.trabajo / "no_existe.json"):
            with self.subTest(ruta=ruta.name), self.assertRaises(g.ErrorGestion):
                g.importar_extraccion(self.raiz, CASO, ruta)
        variantes = {
            "sintetica": lambda d: d["procedencia"].update(tipo="sintetico"),
            "otro_caso": lambda d: d.update(caso="otro-caso"),
            "archivo_inexistente": lambda d: d["candidatos"][1]["evidencia"][0].update(archivo_id="L0009"),
            "pagina_inexistente": lambda d: d["candidatos"][1]["evidencia"][0].update(pagina=3),
            "recorte_inexistente": lambda d: d["candidatos"][0]["evidencia"][0].update(recorte_id="f" * 32),
            "hash_declarado": lambda d: d["candidatos"][1]["evidencia"][0].update(original_sha256="0" * 64),
            "expediente_declarado": lambda d: d["procedencia"].update(expediente_sha256="0" * 64),
            "id_duplicado": lambda d: d["candidatos"][2].update(id="C001"),
        }
        for nombre, cambio in variantes.items():
            with self.subTest(nombre=nombre):
                data = json.loads(json.dumps(self.data))
                cambio(data)
                with self.assertRaises(g.ErrorEvidencia):
                    g.importar_extraccion(self.raiz, CASO, self.escribir(data, f"{nombre}.json"))
        self.assertEqual(self.versiones(), [])

    def test_ids_y_rutas_que_escapan(self):
        for caso in ("../" + CASO, "CON", "a/b", "", "..", CASO + "/../" + CASO):
            with self.subTest(caso=caso), self.assertRaises(g.ErrorGestion):
                g.importar_extraccion(self.raiz, caso, self.entrada)
        imp = self.importar()
        for ident in ("../../x", "abc", imp.identificador.upper(), "0" * 32):
            with self.subTest(ident=ident), self.assertRaises(g.ErrorGestion):
                g.validar_version(self.raiz, CASO, ident)
        # Un recorte cuya imagen apunta fuera de su carpeta se rechaza.
        recorte_json = self.imagen.parent / "recorte.json"
        meta = json.loads(recorte_json.read_text(encoding="utf-8"))
        meta["imagen"] = "../../originales/lamina-0001.pdf"
        recorte_json.write_text(json.dumps(meta), encoding="utf-8")
        comp = g.validar_version(self.raiz, CASO, imp.identificador)
        self.assertFalse(comp.correcta)
        self.assertTrue(any("fuera del caso" in p for p in comp.problemas), comp.problemas)

    def test_enlace_que_sale_del_caso(self):
        externo = self.trabajo / "externo.png"
        externo.write_bytes(self.imagen.read_bytes())
        self.imagen.unlink()
        try:
            self.imagen.symlink_to(externo)
        except (OSError, NotImplementedError):
            self.skipTest("El sistema no permite crear enlaces simbólicos sin privilegios.")
        with self.assertRaises(g.ErrorEvidencia) as ctx:
            self.importar()
        self.assertIn("fuera del caso", str(ctx.exception))

    # -- evidencia alterada ---------------------------------------------
    def test_original_o_imagen_alterados_o_ausentes(self):
        casos = {
            "original_alterado": (self.original, lambda p: p.write_bytes(p.read_bytes() + b"%cambio\n"), "alterado"),
            "original_ausente": (self.original, lambda p: p.unlink(), "ausente"),
            "imagen_alterada": (self.imagen, lambda p: p.write_bytes(p.read_bytes() + b"x"), "alterada"),
            "imagen_ausente": (self.imagen, lambda p: p.unlink(), "ausente"),
        }
        for nombre, (ruta, accion, texto) in casos.items():
            with self.subTest(nombre=nombre):
                respaldo = ruta.read_bytes()
                accion(ruta)
                try:
                    with self.assertRaises(g.ErrorEvidencia) as ctx:
                        self.importar()
                    self.assertIn(texto, str(ctx.exception))
                finally:
                    ruta.write_bytes(respaldo)
        self.assertEqual(self.versiones(), [])
        self.assertTrue(self.importar().comprobacion.correcta)

    def test_alteracion_posterior_bloquea_correccion_y_exportacion(self):
        imp = self.importar()
        self.original.write_bytes(self.original.read_bytes() + b"%cambio\n")
        comp = g.validar_version(self.raiz, CASO, imp.identificador)
        self.assertFalse(comp.correcta)
        with self.assertRaises(g.ErrorEvidencia):
            self.revisar_c001(imp.identificador)
        with self.assertRaises(g.ErrorEvidencia):
            g.exportar_version(self.raiz, CASO, imp.identificador)
        self.assertEqual(self.versiones(), [imp.identificador])
        self.assertEqual(self.exportaciones(), [])

    def test_expediente_cambiado(self):
        imp = self.importar()
        contenido = self.manifest.read_bytes()
        self.manifest.write_bytes(contenido + b"\n")  # mismo JSON, distinto SHA256
        comp = g.validar_version(self.raiz, CASO, imp.identificador)
        self.assertFalse(comp.correcta)
        self.assertTrue(any("expediente cambió" in p for p in comp.problemas), comp.problemas)
        with self.assertRaises(g.ErrorEvidencia):
            g.importar_extraccion(self.raiz, CASO, self.entrada)
        self.assertEqual(self.versiones(), [imp.identificador])

    def test_version_guardada_editada_se_detecta(self):
        imp = self.importar()
        v1 = self.revisar_c001(imp.identificador)
        ruta = imp.ruta / "extraccion.json"
        data = json.loads(ruta.read_text(encoding="utf-8"))
        data["candidatos"][0]["valor_propuesto"] = 9.99
        ruta.write_text(json.dumps(data), encoding="utf-8")
        for ident in (imp.identificador, v1.identificador):  # el hijo detecta el padre alterado
            with self.subTest(ident=ident):
                comp = g.validar_version(self.raiz, CASO, ident)
                self.assertFalse(comp.correcta)
        with self.assertRaises(g.ErrorEvidencia):
            g.exportar_version(self.raiz, CASO, v1.identificador)

    def test_fallo_al_escribir_no_deja_version_parcial(self):
        escribir = Path.write_bytes
        llamadas = []

        def falla_en_la_segunda(self_path, contenido):
            llamadas.append(self_path.name)
            if len(llamadas) == 2:
                raise OSError("disco lleno simulado")
            return escribir(self_path, contenido)

        with mock.patch.object(Path, "write_bytes", falla_en_la_segunda), self.assertRaises(OSError):
            self.importar()
        carpeta = self.caso_dir / g.CARPETA_VERSIONES
        self.assertEqual(list(carpeta.iterdir()), [])  # ni versión ni temporal
        self.assertTrue(self.importar().comprobacion.correcta)

    def test_no_modifica_expediente_ni_originales(self):
        antes = {p: p.read_bytes() for p in (self.manifest, self.original, self.imagen, self.imagen.parent / "recorte.json")}
        imp = self.importar()
        v1 = self.revisar_c001(imp.identificador)
        g.validar_version(self.raiz, CASO, v1.identificador)
        g.exportar_version(self.raiz, CASO, v1.identificador)
        for ruta, contenido in antes.items():
            self.assertEqual(ruta.read_bytes(), contenido, ruta.name)
        self.assertEqual(file_hash(self.original), json.loads(self.manifest.read_text(encoding="utf-8"))["archivos"][0]["sha256"])


class RegresionAuditoriaTests(CasoSintetico):
    """Defectos reproducidos por tmp/auditar_entrega_extraccion.py; cada prueba exige el rechazo."""

    def enlace(self, enlace: Path, destino: Path) -> None:
        tipo = enlazar_carpeta(enlace, destino)
        if tipo is None:
            self.skipTest("El sistema no permite crear junctions ni enlaces simbólicos de carpeta.")
        self.addCleanup(quitar_enlace, enlace)

    def externo(self, nombre="fuera_del_caso") -> Path:
        carpeta = self.trabajo / nombre
        carpeta.mkdir()
        return carpeta

    # -- defecto 1: escritura fuera del caso mediante enlaces -------------
    def test_d1_importacion_con_extracciones_enlazada_fuera(self):
        externo = self.externo()
        self.enlace(self.caso_dir / g.CARPETA_VERSIONES, externo)
        with self.assertRaises(g.ErrorGestion) as ctx:
            self.importar()
        self.assertIn("fuera del caso", str(ctx.exception))
        self.assertEqual(list(externo.iterdir()), [])

    def test_d1_enlace_interno_tambien_se_rechaza(self):
        # Un enlace que apunta dentro del caso, pero a otra carpeta, tampoco es un destino válido.
        originales = self.caso_dir / "originales"
        antes = instantanea(originales)
        self.enlace(self.caso_dir / g.CARPETA_VERSIONES, originales)
        with self.assertRaises(g.ErrorGestion):
            self.importar()
        self.assertEqual(instantanea(originales), antes)

    def test_d1_correccion_con_extracciones_enlazada_fuera(self):
        imp = self.importar()
        externo = self.trabajo / "versiones_movidas"
        shutil.move(str(self.caso_dir / g.CARPETA_VERSIONES), str(externo))
        self.enlace(self.caso_dir / g.CARPETA_VERSIONES, externo)
        antes = instantanea(externo)
        with self.assertRaises(g.ErrorGestion):
            self.revisar_c001(imp.identificador)
        with self.assertRaises(g.ErrorGestion):
            g.validar_version(self.raiz, CASO, imp.identificador)
        self.assertEqual(instantanea(externo), antes)
        self.assertEqual([p.name for p in externo.iterdir()], [imp.identificador])

    def test_d1_exportacion_con_carpeta_enlazada_fuera(self):
        imp = self.importar()
        v1 = self.revisar_c001(imp.identificador)
        externo = self.externo()
        self.enlace(self.caso_dir / g.CARPETA_EXPORTACIONES, externo)
        with self.assertRaises(g.ErrorGestion) as ctx:
            g.exportar_version(self.raiz, CASO, v1.identificador)
        self.assertIn("fuera del caso", str(ctx.exception))
        self.assertEqual(list(externo.iterdir()), [])

    # -- defecto 2: sistema de coordenadas del recorte -------------------
    def editar_recorte(self, **cambios):
        ruta = self.imagen.parent / "recorte.json"
        meta = json.loads(ruta.read_text(encoding="utf-8"))
        for clave, valor in cambios.items():
            if valor is _BORRAR:
                meta.pop(clave, None)
            else:
                meta[clave] = valor
        ruta.write_text(json.dumps(meta), encoding="utf-8")

    def test_d2_importacion_con_sistema_incompatible(self):
        ruta = self.imagen.parent / "recorte.json"
        respaldo = ruta.read_bytes()
        for valor in ("pixeles_sin_rotacion", _BORRAR, None, 5, ["pagina_visible_normalizada"]):
            with self.subTest(valor=valor):
                self.editar_recorte(sistema_coordenadas=valor)
                try:
                    with self.assertRaises(g.ErrorEvidencia) as ctx:
                        self.importar()
                    self.assertIn("sistema de coordenadas", str(ctx.exception))
                finally:
                    ruta.write_bytes(respaldo)
        self.assertEqual(self.versiones(), [])
        self.assertEqual(json.loads(respaldo)["sistema_coordenadas"], "pagina_visible_normalizada")

    def test_d2_version_almacenada_con_recorte_vuelto_incompatible(self):
        imp = self.importar()
        v1 = self.revisar_c001(imp.identificador)
        self.editar_recorte(sistema_coordenadas="pixeles_sin_rotacion")
        comp = g.validar_version(self.raiz, CASO, v1.identificador)
        self.assertFalse(comp.correcta)
        self.assertTrue(any("sistema de coordenadas" in p for p in comp.problemas), comp.problemas)
        with self.assertRaises(g.ErrorEvidencia):
            self.revisar_c001(v1.identificador, fecha="2026-10-16")
        with self.assertRaises(g.ErrorEvidencia):
            g.exportar_version(self.raiz, CASO, v1.identificador)
        self.assertEqual(len(self.versiones()), 2)
        self.assertEqual(self.exportaciones(), [])

    # -- defecto 3: fuente importada -------------------------------------
    def test_d3_fuente_alterada_o_ausente(self):
        imp = self.importar()
        fuente = imp.ruta / "fuente_importada.json"
        respaldo = fuente.read_bytes()
        casos = {
            "vacia": lambda: fuente.write_text("{}", encoding="utf-8"),
            "reformateada": lambda: fuente.write_bytes(json.dumps(self.data, indent=4).encode("utf-8")),
            "ausente": lambda: fuente.unlink(),
        }
        for nombre, alterar in casos.items():
            with self.subTest(nombre=nombre):
                alterar()
                try:
                    comp = g.validar_version(self.raiz, CASO, imp.identificador)
                    self.assertFalse(comp.correcta)
                    self.assertTrue(any("fuente" in p.lower() for p in comp.problemas), comp.problemas)
                    with self.assertRaises(g.ErrorEvidencia):
                        self.revisar_c001(imp.identificador)
                    with self.assertRaises(g.ErrorEvidencia):
                        g.exportar_version(self.raiz, CASO, imp.identificador)
                finally:
                    fuente.write_bytes(respaldo)
        self.assertEqual(self.versiones(), [imp.identificador])
        self.assertEqual(self.exportaciones(), [])
        self.assertTrue(g.validar_version(self.raiz, CASO, imp.identificador).correcta)

    def test_d3_fuente_con_hash_rehecho_pero_contenido_distinto(self):
        imp = self.importar()
        fuente = imp.ruta / "fuente_importada.json"
        fuente.write_text("{}", encoding="utf-8")
        version = imp.ruta / "version.json"
        meta = json.loads(version.read_text(encoding="utf-8"))
        meta["fuente"]["sha256"] = file_hash(fuente)
        version.write_text(json.dumps(meta), encoding="utf-8")
        comp = g.validar_version(self.raiz, CASO, imp.identificador)
        self.assertFalse(comp.correcta)
        self.assertTrue(any("no corresponde" in p for p in comp.problemas), comp.problemas)

    def test_d3_fuente_alterada_se_detecta_desde_version_hija(self):
        imp = self.importar()
        v1 = self.revisar_c001(imp.identificador)
        self.assertTrue(g.validar_version(self.raiz, CASO, v1.identificador).correcta)
        self.assertFalse((v1.ruta / "fuente_importada.json").exists())  # las correcciones no la guardan
        (imp.ruta / "fuente_importada.json").write_text("{}", encoding="utf-8")
        comp = g.validar_version(self.raiz, CASO, v1.identificador)
        self.assertFalse(comp.correcta)
        self.assertTrue(any(imp.identificador in p and "fuente" in p.lower() for p in comp.problemas), comp.problemas)
        with self.assertRaises(g.ErrorEvidencia):
            g.exportar_version(self.raiz, CASO, v1.identificador)
        with self.assertRaises(g.ErrorEvidencia):
            self.revisar_c001(v1.identificador, fecha="2026-10-16")
        self.assertEqual(len(self.versiones()), 2)

    # -- defecto 4: registros auxiliares malformados ---------------------
    def editar_revision(self, documentos):
        ruta = next((self.caso_dir / "revision_documental").glob("*/revision.json"))
        meta = json.loads(ruta.read_text(encoding="utf-8"))
        meta["documentos"] = documentos
        ruta.write_text(json.dumps(meta), encoding="utf-8")
        return ruta

    def test_d4_revision_con_documentos_malformados(self):
        ruta = next((self.caso_dir / "revision_documental").glob("*/revision.json"))
        respaldo = ruta.read_bytes()
        documento = json.loads(respaldo)["documentos"][0]
        variantes = {
            "nulo": [None],
            "texto": "documentos",
            "numero": 5,
            "objeto": {"id": "L0001"},
            "id_no_texto": [{**documento, "id": ["L0001"]}],
            "archivo_no_texto": [{**documento, "archivo": 7}],
            "paginas_texto": [{**documento, "paginas_declaradas": "2"}],
            "paginas_booleano": [{**documento, "paginas_declaradas": True}],
            "error_no_texto": [{**documento, "error": 1}],
        }
        for nombre, documentos in variantes.items():
            with self.subTest(nombre=nombre):
                self.editar_revision(documentos)
                try:
                    with self.assertRaises(g.ErrorEvidencia) as ctx:
                        self.importar()
                    self.assertIn(f"Revisión {ruta.parent.name}", str(ctx.exception))
                finally:
                    ruta.write_bytes(respaldo)
        self.assertEqual(self.versiones(), [])
        self.assertTrue(self.importar().comprobacion.correcta)

    def test_d4_revision_ilegible_y_version_almacenada(self):
        imp = self.importar()
        ruta = self.editar_revision([None])
        comp = g.validar_version(self.raiz, CASO, imp.identificador)
        self.assertFalse(comp.correcta)
        ruta.write_text("{no es json", encoding="utf-8")
        comp = g.validar_version(self.raiz, CASO, imp.identificador)
        self.assertFalse(comp.correcta)
        self.assertTrue(any(ruta.parent.name in p for p in comp.problemas), comp.problemas)
        with self.assertRaises(g.ErrorEvidencia):
            g.exportar_version(self.raiz, CASO, imp.identificador)
        self.assertEqual(self.exportaciones(), [])

    def test_d4_recorte_con_campos_malformados(self):
        ruta = self.imagen.parent / "recorte.json"
        respaldo = ruta.read_bytes()
        for cambio in ({"archivo_id": ["L0001"]}, {"pagina": "1"}, {"pagina": True},
                       {"bbox_normalizada": ["0", 0, 0.5, 0.5]}, {"bbox_normalizada": [0, 0, 2, 0.5]},
                       {"imagen_sha256": 5}, {"imagen": None}):
            with self.subTest(cambio=cambio):
                self.editar_recorte(**cambio)
                try:
                    with self.assertRaises(g.ErrorEvidencia):
                        self.importar()
                finally:
                    ruta.write_bytes(respaldo)
        self.assertEqual(self.versiones(), [])


_BORRAR = object()


if __name__ == "__main__":
    unittest.main()
