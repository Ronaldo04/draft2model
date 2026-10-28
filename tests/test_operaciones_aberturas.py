"""Operaciones0.3 y doble PowerShell persistente; no ETABS ni gestión sustituida."""
import copy
import hashlib
import re
from pathlib import Path
from unittest import mock
from draft2model import operaciones_etabs as o, ejecutor_etabs as ej
from tests.test_modelo_aberturas import CasoAberturas
from tests import test_operaciones_superficies as ts, test_ejecutor_etabs as te


class PlanAberturasTests(CasoAberturas):
    def plan(self):
        return o.generar_plan_aberturas(self.raiz,self.data,destino_guardado=str(self.f.trabajo/"salida"/"modelo.edb"),gravedad_programa_m_s2=9.80665,**({"tipo_shell_muro":"ShellThin"} if self.data["secciones"][1]["tipo"]=="shell_muro" else {"tipo_shell_losa":"ShellThin"}))

    def test_orientaciones_y_cobertura_sin_carga_al_hueco(self):
        for orientacion in ("horizontal","inclinado","vertical"):
            self.montar(orientacion); plan=self.plan().datos
            self.assertEqual(o.validar_plan_aberturas(plan),[])
            self.assertTrue(o.validar_plan(plan)); self.assertTrue(o.validar_plan_superficies(plan))
            self.assertEqual(plan["version_contrato"],"0.3.0"); self.assertFalse(plan["ejecutable"])
            self.assertEqual(plan["cobertura_aberturas"],["HUECO1"])
            tr=plan["trazabilidad_superficies"]["S1"]
            self.assertAlmostEqual(tr["area_bruta_m2"]-tr["area_aberturas_m2"],tr["area_neta_m2"])
            ops=plan["operaciones"]
            agregar=[x for x in ops if x["metodo"]=="cAreaObj.AddByPoint" and x["origen"]=="geometria.aberturas.HUECO1"][0]
            self.assertEqual({x["nombre"]:x["valor"] for x in agregar["argumentos"]}["PropName"],"None")
            self.assertEqual(len([x for x in ops if x["metodo"]=="cAreaObj.SetLoadUniform"]),1)
            self.assertNotIn("abertura",str(next(x for x in ops if x["metodo"]=="cAreaObj.SetLoadUniform")["argumentos"]))

    def test_plan_omitido_sha_y_tipo_invalidos(self):
        p=self.plan().datos
        q=copy.deepcopy(p);q["operaciones"]=[x for x in q["operaciones"] if x["metodo"]!="cAreaObj.SetOpening"];q["huella_plan"]=o.huella_plan(q)
        self.assertTrue(o.validar_plan_aberturas(q))
        q=copy.deepcopy(p);q["huella_plan"]="0"*64;self.assertTrue(o.validar_plan_aberturas(q))
        q=copy.deepcopy(p)
        op=next(x for x in q["operaciones"] if x["metodo"]=="cAreaObj.SetOpening" and x["origen"]=="geometria.aberturas.HUECO1")
        next(x for x in op["argumentos"] if x["nombre"]=="IsOpening")["valor"]=False
        q["huella_plan"]=o.huella_plan(q);self.assertTrue(o.validar_plan_aberturas(q))
        q=copy.deepcopy(p)
        op=next(x for x in q["operaciones"] if x["metodo"]=="cAreaObj.SetOpening")
        next(x for x in op["argumentos"] if x["nombre"]=="ItemType")["valor"]={"enum":"eItemType","nombre":"Objects","valor":999}
        q["huella_plan"]=o.huella_plan(q);self.assertTrue(o.validar_plan_aberturas(q))

    def test_firmas_reflejadas_y_listas(self):
        self.assertEqual(o.verificar_firmas_dll()["diferencias"],[])
        script=ej.SCRIPT_EJECUTOR.read_bytes().decode("utf-8-sig")
        bloque=re.search(r"\$MetodosPermitidos = @\((.*?)\n\)",script,re.S).group(1)
        self.assertEqual(set(re.findall(r"'([^']+)'",bloque)),set(o.FIRMAS))


class DespachoAberturasTests(CasoAberturas):
    ejecutar=ts.DespachoSuperficiesTests.ejecutar
    tearDownClass=classmethod(ts.DespachoSuperficiesTests.tearDownClass.__func__)

    @classmethod
    def setUpClass(cls):
        cuerpos=dict(ts.CUERPOS)
        cuerpos["cPropArea.SetWall"]='Estado.Mat[Name] = MatProp; Estado.Esp[Name] = Thickness; return 0;'
        cuerpos["cPropArea.GetWall"]='MatProp = Estado.Mat[Name]; Thickness = Estado.Esp[Name]; return 0;'
        cuerpos["cAreaObj.SetOpening"]='Huecos.O[Name] = IsOpening; return Falso.Retorno("cAreaObj.SetOpening", 0);'
        cuerpos["cAreaObj.GetOpening"]='IsOpening = Huecos.O[Name]; if (Falso.Env("FALSO_ABERTURA") == "1") IsOpening = !IsOpening; return 0;'
        extra=ts.ESTADO_CS + ' public static class Huecos { public static System.Collections.Generic.Dictionary<string,bool> O = new System.Collections.Generic.Dictionary<string,bool>(); }'
        with mock.patch.object(ts,"CUERPOS",cuerpos),mock.patch.object(ts,"ESTADO_CS",extra):
            ts.DespachoSuperficiesTests.setUpClass.__func__(cls)

    def preparar(self,orientacion="horizontal"):
        self.montar(orientacion)
        self.trabajo=self.f.trabajo
        self.copia=self.trabajo/"copia.edb";self.copia.write_bytes(te.CONTENIDO_COPIA)
        self.data["plantilla"]["sha256"]=hashlib.sha256(te.CONTENIDO_COPIA).hexdigest()
        self.data=self.aprobar(self.data)
        self.destino=str(self.trabajo/"salida"/(orientacion+".edb"));Path(self.destino).parent.mkdir(exist_ok=True)
        self.plan_datos=o.generar_plan_aberturas(self.raiz,self.data,destino_guardado=self.destino,gravedad_programa_m_s2=9.80665,**({"tipo_shell_muro":"ShellThin"} if orientacion=="vertical" else {"tipo_shell_losa":"ShellThin"})).datos

    def test_host_y_abertura_persisten(self):
        for orientacion in ("horizontal","inclinado","vertical"):
            self.preparar(orientacion)
            codigo,respuesta,llamadas=self.ejecutar()
            self.assertEqual(codigo,0,respuesta)
            self.assertTrue(Path(self.destino).is_file())
            self.assertEqual(len([l for l in llamadas if l["m"]=="cAreaObj.GetOpening"]),2)
            self.assertEqual(respuesta["progreso"]["mapeo_nombres"]["abertura:HUECO1"],"ABERTURA.HUECO1")

    def test_falso_getter_y_retorno_detienen_sin_guardar(self):
        for entorno in ({"FALSO_ABERTURA":"1"},{"FALSO_FALLA":"cAreaObj.SetOpening"}):
            self.preparar()
            codigo,respuesta,llamadas=self.ejecutar(**entorno)
            self.assertEqual(codigo,30,respuesta)
            self.assertFalse(Path(self.destino).exists())
            self.assertNotIn("cFile.Save",[l["m"] for l in llamadas])
