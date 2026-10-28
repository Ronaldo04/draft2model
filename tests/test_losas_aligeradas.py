"""Pruebas sintéticas: no acreditan ETABS ni equivalencia del caso real."""
import copy
import unittest
from draft2model import modelo_estructural as m, operaciones_etabs as o
from tests import test_operaciones_superficies as ts
PlanSuperficiesBase = ts.PlanSuperficiesBase
CUERPOS, ESTADO_CS = ts.CUERPOS, ts.ESTADO_CS


def configurar(data, tipo="shell_losa_nervada_v1"):
    sec = next(s for s in data["secciones"] if s["id"] == "LOSA20")
    # S2 permanece homogénea: aligerado solo horizontal explícito.
    data["secciones"].append(copy.deepcopy(sec))
    data["secciones"][-1]["id"] = "MACIZA"
    data["asignaciones_superficies"][1]["seccion"] = "MACIZA"
    sec["tipo"] = tipo
    sec["dimensiones"] = dict(alto_total_m=.25, capa_m=.05, ancho_nervio_superior_m=.12, ancho_nervio_inferior_m=.1, angulo_ejes_locales_grados=30)
    sec["dimensiones"].update(dict(separacion_m=.6, direccion_nervios=1) if tipo == m.TIPOS_ALIGERADOS[0] else dict(separacion_1_m=.6, separacion_2_m=.7))
    return sec


class LosasTests(PlanSuperficiesBase):
    def test_plan_nervada_y_casetonada(self):
        for tipo, metodo in zip(m.TIPOS_ALIGERADOS, ("Ribbed", "Waffle")):
            data = copy.deepcopy(self.data)
            sec = configurar(data, tipo)
            r = m.validar_configuracion(data, self.geometria)
            self.assertTrue(r.consistente, r.errores)
            plan = self.plan(self.aprobar_config(data))
            self.assertFalse(plan.datos["ejecutable"])
            self.assertEqual(plan.datos["trazabilidad_aligerados"]["LOSA20"]["seccion_declarada"], sec)
            self.assertEqual(self.args(self.ops(plan, "cPropArea.SetSlab" + metodo)[0]), {"Name": "LOSA20", **o._parametros_aligerados(sec)})
            self.assertTrue(self.ops(plan, "cPropArea.GetSlab" + metodo))
            self.assertEqual(self.args(self.ops(plan, 'cPropArea.SetSlab')[0])['Thickness'],.05)
            getter=next(x for x in self.ops(plan,'cPropArea.GetSlab') if self.args(x)['Name']=='LOSA20')
            self.assertEqual({x['parametro']:x['esperado'] for x in getter['verificar_valores']}['Thickness'],.05)
            self.assertTrue(self.ops(plan, "cAreaObj.SetLocalAxes"))
            o.validar_plan_superficies(plan.datos)
            self.assertEqual(o.validar_plan(plan.datos), ["Contrato de plan no admitido."])

    def test_rechaza_dimensiones_y_cobertura(self):
        cambios = [lambda s: s["dimensiones"].pop("capa_m"),
                   lambda s: s["dimensiones"].update(capa_m=.3),
                   lambda s: s["dimensiones"].update(separacion_m=.1),
                   lambda s: s["dimensiones"].update(direccion_nervios=True),
                   lambda s: s["dimensiones"].update(direccion_nervios=3),
                   lambda s: s["dimensiones"].update(alto_total_m=float("nan")),
                   lambda s: s["dimensiones"].update(alto_total_m=10**1000),
                   lambda s: s["dimensiones"].update(angulo_ejes_locales_grados=180),
                   lambda s: s.update(tipo="shell_losa_magica"),
                   lambda s: s.update(fuente="INEXISTENTE")]
        for cambio in cambios:
            data = copy.deepcopy(self.data); sec = configurar(data); cambio(sec)
            self.assertFalse(m.validar_configuracion(data, self.geometria).consistente)
        data = copy.deepcopy(self.data); configurar(data)
        data["asignaciones_superficies"][1]["seccion"] = "LOSA20"
        self.assertFalse(m.validar_configuracion(data, self.geometria).consistente)
        data = copy.deepcopy(self.data); configurar(data); data["unidades"] = "ton_m_C"
        self.assertFalse(m.validar_configuracion(data, self.geometria).consistente)

    def test_firmas_locales(self):
        import re
        from draft2model import ejecutor_etabs as ej
        self.assertEqual(o.verificar_firmas_dll()["diferencias"], [])
        script = ej.SCRIPT_EJECUTOR.read_bytes().decode("utf-8-sig")
        bloque = re.search(r"\$MetodosPermitidos = @\((.*?)\n\)", script, re.S).group(1)
        self.assertEqual(set(re.findall(r"'([^']+)'", bloque)), set(o.FIRMAS))
        self.assertEqual(o.ENUMS["eSlabType"], {"Slab": 0, "Ribbed": 3, "Waffle": 4})


class DespachoLosasTests(PlanSuperficiesBase):
    ejecutar = ts.DespachoSuperficiesTests.ejecutar
    tearDownClass = classmethod(ts.DespachoSuperficiesTests.tearDownClass.__func__)

    @classmethod
    def setUpClass(cls):
        import base64, os, subprocess, tempfile
        from pathlib import Path
        from tests import test_ejecutor_etabs as te
        from draft2model import adaptador_etabs as ad
        cls._dir = tempfile.TemporaryDirectory()
        carpeta = Path(cls._dir.name)
        cs, cls.dll = carpeta / "aligeradas.cs", carpeta / "aligeradas.dll"
        extra = ESTADO_CS + r"""
public static class Nervios {
 public static System.Collections.Generic.Dictionary<string, ETABSv1.eSlabType> S = new System.Collections.Generic.Dictionary<string, ETABSv1.eSlabType>();
 public static System.Collections.Generic.Dictionary<string, ETABSv1.eShellType> Sh = new System.Collections.Generic.Dictionary<string, ETABSv1.eShellType>();
 public static System.Collections.Generic.Dictionary<string, double[]> D = new System.Collections.Generic.Dictionary<string, double[]>();
 public static System.Collections.Generic.Dictionary<string, double> A = new System.Collections.Generic.Dictionary<string, double>();
}
"""
        cuerpos = dict(CUERPOS)
        cuerpos["cPropArea.SetSlab"] += " Nervios.S[Name] = SlabType; Nervios.Sh[Name] = ShellType;"
        cuerpos["cPropArea.SetSlab"] = cuerpos["cPropArea.SetSlab"].replace('return Falso.Retorno("cPropArea.SetSlab", 0);', '') + 'return Falso.Retorno("cPropArea.SetSlab", 0);'
        cuerpos["cPropArea.GetSlab"] = 'SlabType = Falso.Env("FALSO_TIPO_LOSA") == "1" ? ETABSv1.eSlabType.Slab : Nervios.S[Name]; ShellType = Nervios.Sh[Name]; ' + cuerpos["cPropArea.GetSlab"]
        for clase in ("Ribbed", "Waffle"):
            nombres = list(o.PARAM_ALIGERADOS) + (["RibSpacing", "RibsParallelTo"] if clase == "Ribbed" else ["RibSpacingDir1", "RibSpacingDir2"])
            cuerpos["cPropArea.SetSlab" + clase] = 'Estado.Esp[Name] = SlabThickness; Nervios.D[Name] = new double[] {' + ','.join(nombres) + '}; return Falso.Retorno("cPropArea.SetSlab' + clase + '", 0);'
            cuerpos["cPropArea.GetSlab" + clase] = ''.join(n + ' = ' + ('(int)' if n == 'RibsParallelTo' else '') + 'Nervios.D[Name][' + str(i) + '];' for i, n in enumerate(nombres)) + ' if (Falso.Env("FALSO_DESVIO_NERVIO") == "1") OverallDepth += .1; return 0;'
        cuerpos["cAreaObj.SetLocalAxes"] = 'Nervios.A[Name] = Ang; return 0;'
        cuerpos["cAreaObj.GetLocalAxes"] = 'Ang = Nervios.A[Name]; Advanced = false; return 0;'
        cs.write_text(te.generar_cs(cuerpos, extra), encoding="utf-8")
        script = "Add-Type -TypeDefinition ([IO.File]::ReadAllText($env:D2M_CS)) -OutputAssembly $env:D2M_DLL -OutputType Library"
        proceso = subprocess.run([str(ad.POWERSHELL_51), "-NoProfile", "-NonInteractive", "-EncodedCommand", base64.b64encode(script.encode("utf-16-le")).decode()], env=dict(os.environ, D2M_CS=str(cs), D2M_DLL=str(cls.dll)), capture_output=True, timeout=180)
        if proceso.returncode:
            raise AssertionError(proceso.stderr.decode("utf-8", "replace"))

    def setUp(self):
        import hashlib
        from pathlib import Path
        from tests import test_ejecutor_etabs as te
        super().setUp()
        self.copia = self.trabajo / "copia.edb"
        self.copia.write_bytes(te.CONTENIDO_COPIA)
        self.data["plantilla"]["sha256"] = hashlib.sha256(te.CONTENIDO_COPIA).hexdigest()
        Path(self.destino).parent.mkdir()

    def test_parametros_persistidos_y_fallo_detiene(self):
        from pathlib import Path
        for tipo, clase in zip(m.TIPOS_ALIGERADOS, ("Ribbed", "Waffle")):
            data = copy.deepcopy(self.data); configurar(data, tipo)
            self.plan_datos = self.plan(self.aprobar_config(data)).datos
            codigo, respuesta, llamadas = self.ejecutar()
            self.assertEqual(codigo, 0, respuesta)
            self.assertTrue(any(l["m"] == "cPropArea.GetSlab" + clase for l in llamadas))
            Path(self.destino).unlink()
            codigo, respuesta, llamadas = self.ejecutar(FALSO_FALLA="cPropArea.SetSlab" + clase)
            self.assertEqual(codigo, 30, respuesta)
            self.assertFalse(Path(self.destino).exists())
            self.assertNotIn("cFile.Save", [l["m"] for l in llamadas])
            codigo, respuesta, llamadas = self.ejecutar(FALSO_DESVIO_NERVIO="1")
            self.assertEqual(codigo, 30, respuesta)
            self.assertFalse(Path(self.destino).exists())
            self.assertEqual(llamadas[-1]["m"], "cPropArea.GetSlab" + clase)
            codigo, respuesta, llamadas = self.ejecutar(FALSO_TIPO_LOSA="1")
            self.assertEqual(codigo, 30, respuesta)
            self.assertFalse(Path(self.destino).exists())
            self.assertEqual(llamadas[-1]["m"], "cPropArea.GetSlab")
