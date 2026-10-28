"""Infraestructura explícita con geometría sintética versionada, sin ETABS."""
import copy
import io
import json
import math
from contextlib import redirect_stdout
from pathlib import Path

from draft2model import modelo_estructural as m
from draft2model import gestion_geometria as g
from draft2model.contratos import huella_contenido
from tests.test_gestion_geometria import CasoGeometria, CASO

EJEMPLO = Path(__file__).resolve().parents[1] / "examples" / "modelo_estructural_sintetico.json"


class ModeloTests(CasoGeometria):
    def setUp(self):
        super().setUp()
        self.data = json.loads(EJEMPLO.read_bytes())
        self.geometria = self.completa()
        imp = self.importar(self.escribir(self.geometria))
        self.aprobada = self.aprobar(imp.identificador, imp.comprobacion.huella_contenido)
        self.data["geometria_origen"] = {
            "version_id": self.aprobada.identificador,
            "sha256_geometria": self.aprobada.comprobacion.sha256_geometria,
            "huella_contenido": self.aprobada.comprobacion.huella_contenido,
        }
        self.geometria = g.consultar_version(self.raiz, CASO, self.aprobada.identificador).geometria

    def aprobar_config(self, data=None):
        data = copy.deepcopy(self.data if data is None else data)
        data["revision"] = {"estado": "aprobado", "aprobacion": {
            "revisor_declarado": "Revisor SINTÉTICO de software", "fecha": "2026-10-16",
            "huella_configuracion": m.huella_configuracion(data),
            "alcance": "Configuración y plantilla sintéticas completas; solo prueba de software.",
            "identidad_revisor": "declarada_no_verificada",
        }}
        return data

    def test_borrador_consistente_sin_ejecucion_y_api_pura(self):
        antes = copy.deepcopy(self.data)
        r = m.validar_configuracion(self.data, self.geometria)
        self.assertTrue(r.consistente, r.errores)
        self.assertFalse(r.apto_para_adaptador)
        self.assertFalse(r.a_dict()["ejecutable_en_etabs"])
        self.assertEqual(self.data, antes)
        self.assertEqual(r.huella_contenido, m.huella_configuracion(self.data))
        json.dumps(r.a_dict(), allow_nan=False)

    def test_apto_solo_config_y_geometria_aprobadas_y_evidencia_vigente(self):
        data = self.aprobar_config()
        r = m.comprobar_configuracion(self.raiz, data)
        self.assertTrue(r.consistente, r.errores)
        self.assertTrue(r.apto_para_adaptador, r.bloqueos)
        self.assertTrue(r.geometria_comprobada)
        self.assertFalse(r.a_dict()["ejecutable_en_etabs"])
        self.assertFalse(m.validar_configuracion(data, self.geometria).apto_para_adaptador)
        data["materiales"][0]["E_kN_m2"] = 2e6
        r = m.comprobar_configuracion(self.raiz, data)
        self.assertFalse(r.apto_para_adaptador)
        self.assertTrue(any("huella" in error for error in r.errores))

    def test_faltantes_declarados_preservados_bloquean(self):
        self.data["materiales"][0]["E_kN_m2"] = None
        self.data["faltantes"] = [{"ruta": "$.materiales.MAT1.E_kN_m2", "motivo": "Dato pendiente de ingeniería", "fuente": "F-SINTETICA"}]
        r = m.comprobar_configuracion(self.raiz, self.aprobar_config())
        self.assertTrue(r.consistente, r.errores)
        self.assertEqual(r.faltantes, self.data["faltantes"])
        self.assertFalse(r.apto_para_adaptador)
        self.data["faltantes"] = []
        self.assertFalse(m.validar_configuracion(self.data).consistente)

    def test_alteraciones_evidencia_origen_y_naturaleza(self):
        for clave in ("sha256_geometria", "huella_contenido"):
            data = copy.deepcopy(self.data)
            data["geometria_origen"][clave] = "0" * 64
            self.assertFalse(m.comprobar_configuracion(self.raiz, self.aprobar_config(data)).apto_para_adaptador)
        data = self.aprobar_config()
        self.original.write_bytes(self.original.read_bytes() + b"cambio")
        self.assertFalse(m.comprobar_configuracion(self.raiz, data).apto_para_adaptador)

    def test_geometria_borrador_no_habilita_config_aprobada(self):
        propuesta = copy.deepcopy(self.geometria)
        propuesta["revision"] = {"estado": "borrador", "aprobacion": None}
        rev = self.revisar(self.aprobada.identificador, propuesta)
        self.data["geometria_origen"].update(version_id=rev.identificador, sha256_geometria=rev.comprobacion.sha256_geometria)
        r = m.comprobar_configuracion(self.raiz, self.aprobar_config())
        self.assertTrue(r.consistente, r.errores)
        self.assertFalse(r.apto_para_adaptador)

    def test_referencias_cobertura_conectividad_y_unidades(self):
        mutaciones = [
            lambda d: d["materiales"][0].update(E_kN_m2=0),
            lambda d: d["materiales"][0].update(poisson=.5),
            lambda d: d["materiales"][0].update(peso_kN_m3=-1),
            lambda d: d["secciones"][0].update(material="NO"),
            lambda d: d["secciones"][0]["dimensiones"].update(espesor_m=.2),
            lambda d: d["asignaciones_muros"].pop(),
            lambda d: d["asignaciones_frames"].pop(),
            lambda d: d["puntos"].pop(),
            lambda d: d["frames"][0].update(fin="A0"),
            lambda d: d["frames"][0].update(fin="B1"),
            lambda d: d["frames"][1].update(fin="B0"),
            lambda d: d["frames"].append({"id": "COL-DUP", "inicio": "A1", "fin": "A0", "tipo": "columna", "fuente": "F-SINTETICA"}),
            lambda d: d["unidades"].update(fuerza="N"),
            lambda d: d["cargas"][0].update(unidad="kN/m"),
            lambda d: d["cargas"][0].update(objetivo="NO"),
            lambda d: d["cargas"][0].update(componentes=[0, True, -1]),
            lambda d: d["masa"].update(incluir_masa_propia=True),
            lambda d: d["masa"].update(factores_patrones=[{"patron": "D", "factor": 0}, {"patron": "L", "factor": 0}]),
            lambda d: d["apoyos"].clear(),
            lambda d: d["apoyos"][0].update(restricciones=[True]*5+[1]),
            lambda d: d["sin_diafragma"].pop(),
            lambda d: d["diafragmas"][0]["puntos"].append("A0"),
            lambda d: d["casos"][2]["parametros"].update(modal="EST"),
            lambda d: d["casos"][1]["parametros"].update(numero_modos=True),
            lambda d: d["espectros"][0].update(puntos=[[1, .1], [1, .2]]),
            lambda d: d["analisis"].update(casos_ejecutar=["EST", "EX"]),
            lambda d: d.update(datos_sinteticos=False),
        ]
        for i, mutar in enumerate(mutaciones):
            data = copy.deepcopy(self.data)
            mutar(data)
            with self.subTest(mutacion=i):
                r = m.validar_configuracion(data, self.geometria)
                self.assertFalse(r.consistente, i)
                json.dumps(r.a_dict(), allow_nan=False)

    def test_numeros_no_finitos_enteros_enormes_y_entradas_malformadas(self):
        for valor in (math.nan, math.inf, -math.inf, 10**1000, True):
            data = copy.deepcopy(self.data)
            data["materiales"][0]["E_kN_m2"] = valor
            r = m.validar_configuracion(data)
            self.assertFalse(r.consistente)
            json.dumps(r.a_dict(), allow_nan=False)
        for ruta, campo in (("frames", "inicio"), ("cargas", "objetivo_tipo"), ("casos", "tipo"),
                            ("puntos", "id"), ("puntos", "nodo_geometria"), ("puntos", "nivel_geometria")):
            for valor in ([], {}, None, True):
                data = copy.deepcopy(self.data)
                data[ruta][0][campo] = valor
                with self.subTest(ruta=ruta, valor=valor):
                    r = m.validar_configuracion(data, self.geometria)
                    self.assertFalse(r.consistente)
                    json.dumps(r.a_dict(), allow_nan=False)

    def test_sin_limite_dos_pisos(self):
        data, geo = copy.deepcopy(self.data), copy.deepcopy(self.geometria)
        for piso in range(2, 7):
            inferior, superior = f"N{piso-1}", f"N{piso}"
            geo["niveles"].append({"id": superior, "cota": 2.6*piso})
            for nodo in "ABCD":
                data["puntos"].append({"id": nodo+str(piso), "nodo_geometria": nodo, "nivel_geometria": superior})
            for base in copy.deepcopy(self.geometria["muros"]):
                base.update(id=base["id"]+"-"+str(piso), nivel_inferior=inferior, nivel_superior=superior)
                geo["muros"].append(base)
                data["asignaciones_muros"].append({"objetivo": base["id"], "seccion": "SHELL15", "fuente": "F-SINTETICA"})
            data["diafragmas"].append({"id": "DIA"+str(piso), "tipo": "rigido", "puntos": [n+str(piso) for n in "ABCD"], "fuente": "F-SINTETICA"})
        data["geometria_origen"]["huella_contenido"] = huella_contenido(geo)
        geo["revision"]["aprobacion"]["huella_contenido"] = huella_contenido(geo)
        r = m.validar_configuracion(data, geo)
        self.assertTrue(r.consistente, r.errores)
        geo["revision"] = {"estado": "borrador", "aprobacion": None}
        rev = self.revisar(self.aprobada.identificador, geo)
        ap = self.aprobar(rev.identificador, rev.comprobacion.huella_contenido)
        data["geometria_origen"] = {"version_id": ap.identificador,
                                     "sha256_geometria": ap.comprobacion.sha256_geometria,
                                     "huella_contenido": ap.comprobacion.huella_contenido}
        r = m.comprobar_configuracion(self.raiz, self.aprobar_config(data))
        self.assertTrue(r.apto_para_adaptador, (r.errores, r.bloqueos))

    def test_formas_arbitrarias_no_lanzan_ni_rompen_json_de_salida(self):
        rutas = []
        def recorrer(valor, ruta=()):
            if ruta:
                rutas.append(ruta)
            if isinstance(valor, dict):
                for clave, hijo in valor.items():
                    recorrer(hijo, ruta + (clave,))
            elif isinstance(valor, list):
                for indice, hijo in enumerate(valor):
                    recorrer(hijo, ruta + (indice,))
        recorrer(self.data)
        for ruta in rutas:
            for reemplazo in (None, True, [], {}, math.nan, "x"):
                data = copy.deepcopy(self.data)
                destino = data
                for clave in ruta[:-1]:
                    destino = destino[clave]
                destino[ruta[-1]] = reemplazo
                with self.subTest(ruta=ruta, tipo=type(reemplazo).__name__):
                    json.dumps(m.validar_configuracion(data, self.geometria).a_dict(), allow_nan=False)

    def test_json_estricto_y_cli(self):
        ruta = self.escribir(self.data, "configuracion.json")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(m.main(["--entrada", str(ruta), "--raiz", str(self.raiz)]), 0)
        for texto in ('{"id":"a","id":"b"}', '{"x":NaN}', '{"x":Infinity}'):
            ruta.write_text(texto, encoding="utf-8")
            with self.assertRaises(m.ErrorGestion):
                m.cargar_configuracion(ruta)
