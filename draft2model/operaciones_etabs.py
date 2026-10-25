"""Plan declarativo de operaciones de la API CSI de ETABS desde una configuración comprobada.

Genera, sin ejecutar ni contactar ETABS, la lista ordenada de llamadas de la API
(materiales, secciones, pisos, puntos, frames, muros, patrones, cargas, masa, apoyos,
diafragmas, casos, combinaciones, marcas de ejecución y guardado) que un ejecutor
futuro aplicaría sobre una COPIA abierta de la plantilla declarada.

Reglas:
- Solo se planifica una configuración `modelo_estructural` con `apto_para_adaptador`
  verdadero según `comprobar_configuracion` y geometría versionada vigente.
- Cada llamada pertenece a una lista blanca de firmas comprobadas contra la
  `ETABSv1.dll` instalada (`verificar_firmas_dll`), con todos sus argumentos explícitos.
- Si la configuración usa algo fuera del subconjunto soportado, el plan completo se
  rechaza con todos los motivos; nada se omite en silencio.
- Subconjunto: estático lineal, modal Eigen y espectro de respuesta con funciones tabuladas.
  Los parámetros técnicos que el contrato no fija (parámetros eigen, amortiguamiento de la
  función, excentricidad de diafragma y respuesta rígida) se exigen como opciones explícitas.
- ETABS 21 no ofrece setters OAPI para la función espectral de usuario, el amortiguamiento ni
  la combinación modal del caso espectral; se usan las tablas editables de la API
  (DatabaseTables), con campos comprobados antes de mutar y efecto releído con getters OAPI.

Superficies (plan 0.2.0, `generar_plan_superficies`): compila una configuración 0.2 con
puntos XYZ, `AreaObj.AddByPoint` con el contorno exacto, propiedad `SetSlab` y cargas
uniformes de área, y relee coordenadas, contornos y propiedades. Es un plan de DESARROLLO
no ejecutable: `validar_plan` (0.1, el único que acepta el ejecutor) lo rechaza y la
configuración 0.2 nunca es `apto_para_adaptador` hasta revisar el recorrido completo.

Un plan no es una ejecución, no aprueba el modelo y no certifica seguridad estructural.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import gestion_geometria as gg
from . import modelo_estructural as me
from .gestion_extraccion import ErrorGestion
from .validacion_geometria import validar_geometria

CONTRATO_PLAN = "draft2model.plan_operaciones_etabs"
VERSION_PLAN = "0.1.0"
VERSION_PLAN_SUPERFICIES = "0.2.0"
VERSION_PLAN_ABERTURAS = "0.3.0"
VERSION_PLAN_MALLA = "0.4.0"
VERSION_PLAN_LIQUIDOS = "0.5.0"  # malla 0.4 + presión hidrostática revisada en tabla nativa no uniforme
TABLA_NO_UNIFORME = "Area Load Assignments - Non-uniform"
CAMPOS_NO_UNIFORME = ("UniqueName", "LoadPattern", "Dir", "A", "B", "C", "D", "Restriction")
TOLERANCIA_CONSERVACION = 1e-9
ESTADO_PLAN_SUPERFICIES = "plan_desarrollo_no_ejecutable"
UNIDADES_ETABS = "kN_m_C"
DLL_ETABS = Path(r"C:\Program Files\Computers and Structures\ETABS 21\ETABSv1.dll")
POWERSHELL_51 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
VERSION_DLL_VERIFICADA = "1.29.0.0"  # ETABS 21.1.0; firmas comprobadas el 17-10-2026
TIPOS_SHELL_MURO = ("ShellThin", "ShellThick", "Membrane")
TIPOS_SHELL_LOSA = ("ShellThin", "ShellThick", "Membrane")
# R241: función estructural de cada sección de losa cuando la formulación se elige por sección.
FUNCIONES_LOSA = ("piso", "fondo_deposito", "tapa_deposito", "otra")
NOMBRE_BASE_ETABS = "Base"

# Lista blanca: interfaz.método -> (ruta desde SapModel, retorno, [(tipo .NET, parámetro)]).
# Los tipos terminados en '&' son parámetros por referencia (ref/out).
TIPOS_ALIGERADOS = ("shell_losa_nervada_v1", "shell_losa_casetonada_v1")
PARAM_ALIGERADOS = {"OverallDepth": "alto_total_m", "SlabThickness": "capa_m", "StemWidthTop": "ancho_nervio_superior_m", "StemWidthBot": "ancho_nervio_inferior_m"}
def _parametros_aligerados(sec):
    campos = dict(PARAM_ALIGERADOS)
    campos.update({"RibSpacing": "separacion_m", "RibsParallelTo": "direccion_nervios"} if sec["tipo"] == TIPOS_ALIGERADOS[0] else {"RibSpacingDir1": "separacion_1_m", "RibSpacingDir2": "separacion_2_m"})
    return {k: sec["dimensiones"][v] for k, v in campos.items()}

def _parametros_l(sec):
    q = sec["dimensiones"]
    return {"Name": sec["id"], "MatProp": sec["material"], "T3": q["alto_m"], "T2": q["ancho_m"], "Tf": q["espesor_ala_m"],
            "TwC": q["espesor_alma_m"], "TwT": q["espesor_alma_m"], "MirrorAbout2": q["espejo_eje_2"], "MirrorAbout3": q["espejo_eje_3"],
            "Color": -1, "Notes": "", "GUID": ""}


def _clase_losa(sec):
    return "Ribbed" if sec["tipo"] == TIPOS_ALIGERADOS[0] else "Waffle" if sec["tipo"] == TIPOS_ALIGERADOS[1] else "Slab"

FIRMAS: dict[str, tuple[str, str, list[tuple[str, str]]]] = {
    "cSapModel.SetPresentUnits": ("SapModel", "Int32", [("eUnits", "Units")]),
    "cStory.SetStories_2": ("SapModel.Story", "Int32", [
        ("Double", "BaseElevation"), ("Int32", "NumberStories"), ("String[]&", "StoryNames"),
        ("Double[]&", "StoryHeights"), ("Boolean[]&", "IsMasterStory"), ("String[]&", "SimilarToStory"),
        ("Boolean[]&", "SpliceAbove"), ("Double[]&", "SpliceHeight"), ("Int32[]&", "color")]),
    "cPropMaterial.GetNameList": ("SapModel.PropMaterial", "Int32", [
        ("Int32&", "NumberNames"), ("String[]&", "MyName"), ("eMatType", "MatType")]),
    "cPropMaterial.SetMaterial": ("SapModel.PropMaterial", "Int32", [
        ("String", "Name"), ("eMatType", "MatType"), ("Int32", "Color"), ("String", "Notes"), ("String", "GUID")]),
    "cPropMaterial.SetMPIsotropic": ("SapModel.PropMaterial", "Int32", [
        ("String", "Name"), ("Double", "E"), ("Double", "U"), ("Double", "A"), ("Double", "Temp")]),
    "cPropMaterial.SetWeightAndMass": ("SapModel.PropMaterial", "Int32", [
        ("String", "Name"), ("Int32", "MyOption"), ("Double", "Value"), ("Double", "Temp")]),
    "cPropMaterial.SetMassSource_1": ("SapModel.PropMaterial", "Int32", [
        ("Boolean&", "IncludeElements"), ("Boolean&", "IncludeAddedMass"), ("Boolean&", "IncludeLoads"),
        ("Int32", "NumberLoads"), ("String[]&", "LoadPat"), ("Double[]&", "sf")]),
    "cPropArea.GetNameList": ("SapModel.PropArea", "Int32", [
        ("Int32&", "NumberNames"), ("String[]&", "MyName"), ("Int32", "PropType")]),
    "cPropArea.SetWall": ("SapModel.PropArea", "Int32", [
        ("String", "Name"), ("eWallPropType", "WallPropType"), ("eShellType", "ShellType"), ("String", "MatProp"),
        ("Double", "Thickness"), ("Int32", "color"), ("String", "notes"), ("String", "GUID")]),
    "cPropFrame.GetNameList": ("SapModel.PropFrame", "Int32", [
        ("Int32&", "NumberNames"), ("String[]&", "MyName"), ("eFramePropType", "PropType")]),
    "cPropFrame.SetRectangle": ("SapModel.PropFrame", "Int32", [
        ("String", "Name"), ("String", "MatProp"), ("Double", "T3"), ("Double", "T2"), ("Int32", "Color"),
        ("String", "Notes"), ("String", "GUID")]),
    "cPointObj.Count": ("SapModel.PointObj", "Int32", []),
    "cPointObj.AddCartesian": ("SapModel.PointObj", "Int32", [
        ("Double", "X"), ("Double", "Y"), ("Double", "Z"), ("String&", "Name"), ("String", "UserName"),
        ("String", "CSys"), ("Boolean", "MergeOff"), ("Int32", "MergeNumber")]),
    "cPointObj.SetLoadForce": ("SapModel.PointObj", "Int32", [
        ("String", "Name"), ("String", "LoadPat"), ("Double[]&", "Value"), ("Boolean", "Replace"), ("String", "CSys"),
        ("eItemType", "ItemType")]),
    "cPointObj.SetRestraint": ("SapModel.PointObj", "Int32", [
        ("String", "Name"), ("Boolean[]&", "Value"), ("eItemType", "ItemType")]),
    "cPointObj.SetDiaphragm": ("SapModel.PointObj", "Int32", [
        ("String", "Name"), ("eDiaphragmOption", "DiaphragmOption"), ("String", "DiaphragmName")]),
    "cFrameObj.Count": ("SapModel.FrameObj", "Int32", [("String", "MyType")]),
    "cFrameObj.AddByPoint": ("SapModel.FrameObj", "Int32", [
        ("String", "Point1"), ("String", "Point2"), ("String&", "Name"), ("String", "PropName"), ("String", "UserName")]),
    "cFrameObj.SetLoadDistributed": ("SapModel.FrameObj", "Int32", [
        ("String", "Name"), ("String", "LoadPat"), ("Int32", "MyType"), ("Int32", "Dir"), ("Double", "Dist1"),
        ("Double", "Dist2"), ("Double", "Val1"), ("Double", "Val2"), ("String", "CSys"), ("Boolean", "RelDist"),
        ("Boolean", "Replace"), ("eItemType", "ItemType")]),
    "cAreaObj.Count": ("SapModel.AreaObj", "Int32", []),
    "cAreaObj.AddByPoint": ("SapModel.AreaObj", "Int32", [
        ("Int32", "NumberPoints"), ("String[]&", "Point"), ("String&", "Name"), ("String", "PropName"),
        ("String", "UserName")]),
    "cAreaObj.SetLoadUniform": ("SapModel.AreaObj", "Int32", [
        ("String", "Name"), ("String", "LoadPat"), ("Double", "Value"), ("Int32", "Dir"), ("Boolean", "Replace"),
        ("String", "CSys"), ("eItemType", "ItemType")]),
    "cLoadPatterns.GetNameList": ("SapModel.LoadPatterns", "Int32", [("Int32&", "NumberNames"), ("String[]&", "MyName")]),
    "cLoadPatterns.Add": ("SapModel.LoadPatterns", "Int32", [
        ("String", "Name"), ("eLoadPatternType", "MyType"), ("Double", "SelfWTMultiplier"),
        ("Boolean", "AddAnalysisCase")]),
    "cLoadCases.GetNameList": ("SapModel.LoadCases", "Int32", [
        ("Int32&", "NumberNames"), ("String[]&", "MyName"), ("eLoadCaseType", "CaseType")]),
    "cCaseStaticLinear.SetCase": ("SapModel.LoadCases.StaticLinear", "Int32", [("String", "Name")]),
    "cCaseStaticLinear.SetLoads": ("SapModel.LoadCases.StaticLinear", "Int32", [
        ("String", "Name"), ("Int32", "NumberLoads"), ("String[]&", "LoadType"), ("String[]&", "LoadName"),
        ("Double[]&", "SF")]),
    "cCombo.GetNameList": ("SapModel.RespCombo", "Int32", [("Int32&", "NumberNames"), ("String[]&", "MyName")]),
    "cCombo.Add": ("SapModel.RespCombo", "Int32", [("String", "Name"), ("Int32", "ComboType")]),
    "cCombo.SetCaseList": ("SapModel.RespCombo", "Int32", [
        ("String", "Name"), ("eCNameType&", "CNameType"), ("String", "CName"), ("Double", "SF")]),
    "cDiaphragm.GetNameList": ("SapModel.Diaphragm", "Int32", [("Int32&", "NumberNames"), ("String[]&", "MyName")]),
    "cDiaphragm.SetDiaphragm": ("SapModel.Diaphragm", "Int32", [("String", "Name"), ("Boolean", "SemiRigid")]),
    "cAnalyze.SetRunCaseFlag": ("SapModel.Analyze", "Int32", [("String", "Name"), ("Boolean", "Run"), ("Boolean", "All")]),
    "cFile.Save": ("SapModel.File", "Int32", [("String", "FileName")]),
    # Modal Eigen.
    "cCaseModalEigen.SetCase": ("SapModel.LoadCases.ModalEigen", "Int32", [("String", "Name")]),
    "cCaseModalEigen.SetNumberModes": ("SapModel.LoadCases.ModalEigen", "Int32", [
        ("String", "Name"), ("Int32", "MaxModes"), ("Int32", "MinModes")]),
    "cCaseModalEigen.SetParameters": ("SapModel.LoadCases.ModalEigen", "Int32", [
        ("String", "Name"), ("Double", "EigenShiftFreq"), ("Double", "EigenCutOff"), ("Double", "EigenTol"),
        ("Int32", "AllowAutoFreqShift")]),
    "cCaseModalEigen.GetNumberModes": ("SapModel.LoadCases.ModalEigen", "Int32", [
        ("String", "Name"), ("Int32&", "MaxModes"), ("Int32&", "MinModes")]),
    "cCaseModalEigen.GetParameters": ("SapModel.LoadCases.ModalEigen", "Int32", [
        ("String", "Name"), ("Double&", "EigenShiftFreq"), ("Double&", "EigenCutOff"), ("Double&", "EigenTol"),
        ("Int32&", "AllowAutoFreqShift")]),
    "cCaseModalEigen.GetLoads": ("SapModel.LoadCases.ModalEigen", "Int32", [
        ("String", "Name"), ("Int32&", "NumberLoads"), ("String[]&", "LoadType"), ("String[]&", "LoadName"),
        ("Double[]&", "TargetPar"), ("Boolean[]&", "StaticCorrect")]),
    # Espectro de respuesta.
    "cCaseResponseSpectrum.SetCase": ("SapModel.LoadCases.ResponseSpectrum", "Int32", [("String", "Name")]),
    "cCaseResponseSpectrum.SetModalCase": ("SapModel.LoadCases.ResponseSpectrum", "Int32", [
        ("String", "Name"), ("String", "ModalCase")]),
    "cCaseResponseSpectrum.SetLoads": ("SapModel.LoadCases.ResponseSpectrum", "Int32", [
        ("String", "Name"), ("Int32", "NumberLoads"), ("String[]&", "LoadName"), ("String[]&", "Func"),
        ("Double[]&", "SF"), ("String[]&", "CSys"), ("Double[]&", "Ang")]),
    "cCaseResponseSpectrum.SetEccentricity": ("SapModel.LoadCases.ResponseSpectrum", "Int32", [
        ("String", "Name"), ("Double", "Eccen")]),
    "cCaseResponseSpectrum.GetModalCase": ("SapModel.LoadCases.ResponseSpectrum", "Int32", [
        ("String", "Name"), ("String&", "ModalCase")]),
    "cCaseResponseSpectrum.GetLoads": ("SapModel.LoadCases.ResponseSpectrum", "Int32", [
        ("String", "Name"), ("Int32&", "NumberLoads"), ("String[]&", "LoadName"), ("String[]&", "Func"),
        ("Double[]&", "SF"), ("String[]&", "CSys"), ("Double[]&", "Ang")]),
    "cCaseResponseSpectrum.GetEccentricity": ("SapModel.LoadCases.ResponseSpectrum", "Int32", [
        ("String", "Name"), ("Double&", "Eccen")]),
    "cCaseResponseSpectrum.GetDampConstant": ("SapModel.LoadCases.ResponseSpectrum", "Int32", [
        ("String", "Name"), ("Double&", "Damp")]),
    "cCaseResponseSpectrum.GetDampType": ("SapModel.LoadCases.ResponseSpectrum", "Int32", [
        ("String", "Name"), ("Int32&", "DampType")]),
    "cCaseResponseSpectrum.GetModalComb_1": ("SapModel.LoadCases.ResponseSpectrum", "Int32", [
        ("String", "Name"), ("Int32&", "MyType"), ("Double&", "F1"), ("Double&", "F2"),
        ("Int32&", "PeriodicRigidCombType"), ("Double&", "Td")]),
    # Funciones.
    "cFunction.GetNameList": ("SapModel.Func", "Int32", [
        ("Int32&", "NumberNames"), ("String[]&", "MyName"), ("Int32", "FuncType")]),
    "cFunction.GetValues": ("SapModel.Func", "Int32", [
        ("String", "Name"), ("Int32&", "NumberItems"), ("Double[]&", "MyTime"), ("Double[]&", "Value")]),
    # Tablas editables (sin setters OAPI equivalentes en ETABS 21).
    "cDatabaseTables.GetAllFieldsInTable": ("SapModel.DatabaseTables", "Int32", [
        ("String", "TableKey"), ("Int32&", "TableVersion"), ("Int32&", "NumberFields"), ("String[]&", "FieldKey"),
        ("String[]&", "FieldName"), ("String[]&", "Description"), ("String[]&", "UnitsString"),
        ("Boolean[]&", "IsImportable")]),
    "cDatabaseTables.GetTableForEditingArray": ("SapModel.DatabaseTables", "Int32", [
        ("String", "TableKey"), ("String", "GroupName"), ("Int32&", "TableVersion"), ("String[]&", "FieldsKeysIncluded"),
        ("Int32&", "NumberRecords"), ("String[]&", "TableData")]),
    "cDatabaseTables.SetTableForEditingArray": ("SapModel.DatabaseTables", "Int32", [
        ("String", "TableKey"), ("Int32&", "TableVersion"), ("String[]&", "FieldsKeysIncluded"),
        ("Int32", "NumberRecords"), ("String[]&", "TableData")]),
    "cDatabaseTables.ApplyEditedTables": ("SapModel.DatabaseTables", "Int32", [
        ("Boolean", "FillImportLog"), ("Int32&", "NumFatalErrors"), ("Int32&", "NumErrorMsgs"),
        ("Int32&", "NumWarnMsgs"), ("Int32&", "NumInfoMsgs"), ("String&", "ImportLog")]),
    # Superficies (plan 0.2). Firmas contrastadas por reflexión de metadatos de ETABSv1.dll 1.29.0.0
    # (ETABS 21.1.0) el 19-10-2026, sin iniciar ETABS: tmp/superficies_qa/firmas_reflejadas.json.
    "cPropArea.SetSlab": ("SapModel.PropArea", "Int32", [
        ("String", "Name"), ("eSlabType", "SlabType"), ("eShellType", "ShellType"), ("String", "MatProp"),
        ("Double", "Thickness"), ("Int32", "color"), ("String", "notes"), ("String", "GUID")]),
    "cPropArea.GetSlab": ("SapModel.PropArea", "Int32", [
        ("String", "Name"), ("eSlabType&", "SlabType"), ("eShellType&", "ShellType"), ("String&", "MatProp"),
        ("Double&", "Thickness"), ("Int32&", "color"), ("String&", "notes"), ("String&", "GUID")]),
    "cPropArea.GetWall": ("SapModel.PropArea", "Int32", [
        ("String", "Name"), ("eWallPropType&", "WallPropType"), ("eShellType&", "ShellType"), ("String&", "MatProp"),
        ("Double&", "Thickness"), ("Int32&", "color"), ("String&", "notes"), ("String&", "GUID")]),
    "cAreaObj.GetPoints": ("SapModel.AreaObj", "Int32", [
        ("String", "Name"), ("Int32&", "NumberPoints"), ("String[]&", "Point")]),
    "cAreaObj.GetProperty": ("SapModel.AreaObj", "Int32", [("String", "Name"), ("String&", "PropName")]),
    "cPointObj.GetCoordCartesian": ("SapModel.PointObj", "Int32", [
        ("String", "Name"), ("Double&", "X"), ("Double&", "Y"), ("Double&", "Z"), ("String", "CSys")]),
}

for _nombre, _extras in (("Ribbed", [("Double", "RibSpacing"), ("Int32", "RibsParallelTo")]), ("Waffle", [("Double", "RibSpacingDir1"), ("Double", "RibSpacingDir2")])):
    _p = [("Double", k) for k in PARAM_ALIGERADOS] + _extras
    FIRMAS["cPropArea.SetSlab" + _nombre] = ("SapModel.PropArea", "Int32", [("String", "Name")] + _p)
    FIRMAS["cPropArea.GetSlab" + _nombre] = ("SapModel.PropArea", "Int32", [("String", "Name")] + [(t + "&", n) for t, n in _p])
FIRMAS["cAreaObj.SetLocalAxes"] = ("SapModel.AreaObj", "Int32", [("String", "Name"), ("Double", "Ang"), ("eItemType", "ItemType")])
FIRMAS["cAreaObj.GetLocalAxes"] = ("SapModel.AreaObj", "Int32", [("String", "Name"), ("Double&", "Ang"), ("Boolean&", "Advanced")])

FIRMAS["cAreaObj.SetOpening"] = ("SapModel.AreaObj", "Int32", [("String", "Name"), ("Boolean", "IsOpening"), ("eItemType", "ItemType")])
FIRMAS["cAreaObj.GetOpening"] = ("SapModel.AreaObj", "Int32", [("String", "Name"), ("Boolean&", "IsOpening")])
# Relecturas del plan 0.4 (malla). GetRestraint, GetLoadUniform y GetMassSource_1 reflejados en ETABS 21.1;
# cFrameObj.GetPoints según la ayuda CSI: verificar_firmas_dll debe confirmarlo antes de una ejecución real.
FIRMAS["cPointObj.GetRestraint"] = ("SapModel.PointObj", "Int32", [("String", "Name"), ("Boolean[]&", "Value")])
FIRMAS["cAreaObj.GetLoadUniform"] = ("SapModel.AreaObj", "Int32", [("String", "Name"), ("Int32&", "NumberItems"), ("String[]&", "AreaName"),
    ("String[]&", "LoadPat"), ("String[]&", "CSys"), ("Int32[]&", "Dir"), ("Double[]&", "Value"), ("eItemType", "ItemType")])
FIRMAS["cPropMaterial.GetMassSource_1"] = ("SapModel.PropMaterial", "Int32", [("Boolean&", "IncludeElements"), ("Boolean&", "IncludeAddedMass"),
    ("Boolean&", "IncludeLoads"), ("Int32&", "NumberLoads"), ("String[]&", "LoadPat"), ("Double[]&", "sf")])
FIRMAS["cFrameObj.GetPoints"] = ("SapModel.FrameObj", "Int32", [("String", "Name"), ("String&", "Point1"), ("String&", "Point2")])
# Sección L nativa e inserción (configuración 0.5). Firmas reflejadas de ETABSv1.dll 1.29.0.0 (auditoría Codex 246,
# tmp/auditoria_c1_246/firmas_*.txt); semántica de espejos e inserción ensayada en instancias propias (columna_l_246b).
_L = [("Double", "T3"), ("Double", "T2"), ("Double", "Tf"), ("Double", "TwC"), ("Double", "TwT"), ("Boolean", "MirrorAbout2"), ("Boolean", "MirrorAbout3")]
FIRMAS["cPropFrame.SetConcreteL"] = ("SapModel.PropFrame", "Int32", [("String", "Name"), ("String", "MatProp")] + _L
                                     + [("Int32", "Color"), ("String", "Notes"), ("String", "GUID")])
FIRMAS["cPropFrame.GetConcreteL"] = ("SapModel.PropFrame", "Int32", [("String", "Name"), ("String&", "FileName"), ("String&", "MatProp")]
                                     + [(t + "&", n) for t, n in _L] + [("Int32&", "Color"), ("String&", "Notes"), ("String&", "GUID")])
FIRMAS["cFrameObj.SetInsertionPoint"] = ("SapModel.FrameObj", "Int32", [
    ("String", "Name"), ("Int32", "CardinalPoint"), ("Boolean", "Mirror2"), ("Boolean", "StiffTransform"),
    ("Double[]&", "Offset1"), ("Double[]&", "Offset2"), ("String", "CSys"), ("eItemType", "ItemType")])
FIRMAS["cFrameObj.GetInsertionPoint"] = ("SapModel.FrameObj", "Int32", [
    ("String", "Name"), ("Int32&", "CardinalPoint"), ("Boolean&", "Mirror2"), ("Boolean&", "StiffTransform"),
    ("Double[]&", "Offset1"), ("Double[]&", "Offset2"), ("String&", "CSys")])

# Llamadas que usa una operación 'edicion_tabla' (importabilidad, lectura, escritura y aplicación).
METODOS_EDICION_TABLA = ("cDatabaseTables.GetAllFieldsInTable", "cDatabaseTables.GetTableForEditingArray",
                         "cDatabaseTables.SetTableForEditingArray", "cDatabaseTables.ApplyEditedTables")
# Estas tres solo se admiten dentro de una edición; GetAllFieldsInTable también es una verificación previa.
METODOS_SOLO_EDICION = METODOS_EDICION_TABLA[1:]

# Valores de enumeración usados, comprobados por reflexión. 0 en GetNameList significa "todos".
ENUMS: dict[str, dict[str, int]] = {
    "eUnits": {"kN_m_C": 6},
    "eMatType": {"NoDesign": 3},
    "eShellType": {"ShellThin": 1, "ShellThick": 2, "Membrane": 3},
    "eWallPropType": {"Specified": 1},
    "eLoadPatternType": {"Dead": 1, "Live": 3, "Quake": 5, "Other": 8},
    "eItemType": {"Objects": 0},
    "eDiaphragmOption": {"Disconnect": 1, "DefinedDiaphragm": 3},
    "eCNameType": {"LoadCase": 0},
    "eSlabType": {"Slab": 0, "Ribbed": 3, "Waffle": 4},  # reflejado en 1.29.0.0: Slab 0, Drop 1, Ribbed 3, Waffle 4 (solo se usa Slab)
}
ENUM_TODOS = {"eMatType", "eFramePropType", "eLoadCaseType"}  # GetNameList con 0 = todos

TIPO_PATRON = {"muerta": "Dead", "viva": "Live", "sismo": "Quake", "otro": "Other"}
TIPO_COMBINACION = {"lineal": 0, "envolvente": 1}  # cCombo.Add: 0 aditiva lineal, 1 envolvente
DIRECCION_GLOBAL = (4, 5, 6)  # Dir 4/5/6 = X/Y/Z globales (ayuda CSI de SetLoadDistributed/SetLoadUniform)

# Esquemas OBSERVADOS en ETABS 21.1 (lectura real de solo lectura de Codex, 17-10-2026:
# tmp/d1/tablas_dinamicas_reales.json y tmp/d1/tablas_damping_reales.json). Campos, importabilidad y
# unidades tal como GetAllFieldsInTable los devolvió sobre la copia; los dobles de prueba usan estos datos.
# La primera ejecución dinámica real se detuvo antes de mutar con GetAllFieldsInTable = -96 para la clave
# inventada 'Load Cases - Response Spectrum', que no existe.
TABLA_FUNCION_RS = "Functions - Response Spectrum - User Defined"
TABLA_CASO_RS = "Load Case Definitions - Response Spectrum"
TABLA_AMORTIGUAMIENTO_MODAL = "Load Case Definitions - Damping - Modal"
RETORNO_TABLA_INEXISTENTE_OBSERVADO = -96
ESQUEMAS_OBSERVADOS = {
    # Observado en ETABS 21.1 real (registro 185, unidades presentes N_mm_C); Story/Label no importables.
    TABLA_NO_UNIFORME: {
        "version": 1, "tipo_importacion": 2,
        "campos": ("Story", "Label", "UniqueName", "LoadPattern", "Dir", "A", "B", "C", "D", "Restriction", "GUID"),
        "importables": (False, False, True, True, True, True, True, True, True, True, True),
        "unidades": ("", "", "", "", "", "N/mm3", "N/mm3", "N/mm3", "N/mm2", "", ""),
    },
    TABLA_FUNCION_RS: {
        "version": 1, "tipo_importacion": 2,
        "campos": ("Name", "Period", "Value", "DampRatio", "GUID"),
        "importables": (True, True, True, True, True),
        "unidades": ("", "sec", "", "", ""),
    },
    TABLA_CASO_RS: {
        "version": 1, "tipo_importacion": 2,
        "campos": ("Name", "MassSource", "LoadName", "Function", "TransAccSF", "RotAccSF", "CoordSys", "Angle",
                   "ModalCase", "ModalCombo", "RigidResp", "f1", "f2", "RigidCombo", "td", "DirCombo", "AbsSF",
                   "EccenRatio", "OverStory", "OverDiaph", "OverEccen", "DesignType", "UserDesType", "GUID", "Notes"),
        "importables": (True, False, True, True, True, True, False, True, True, True, True, True, True, True, True,
                        True, True, True, True, True, True, True, True, True, True),
        "unidades": ("", "", "", "", "m/sec2", "rad/sec2", "", "deg", "", "", "", "cyc/sec", "cyc/sec", "", "sec",
                     "", "sec", "", "", "", "m", "", "", "", ""),
    },
    TABLA_AMORTIGUAMIENTO_MODAL: {
        "version": 1, "tipo_importacion": 2,
        "campos": ("Name", "MaxFreq", "DampType", "ConstDamp", "IntBy", "IntTimeVal", "IntDamping", "ProBy",
                   "MassCoeff", "StiffCoeff", "ProTimeVal1", "ProDamping1", "ProTimeVal2", "ProDamping2", "Mode4Ratio",
                   "OverMode", "OverDamp"),
        "importables": (True,) * 17,
        "unidades": ("", "1/sec", "", "", "", "", "", "", "1/sec", "sec", "", "", "", "", "", "", ""),
    },
}
# Edición del caso separada de su amortiguamiento: el caso NO tiene ConstDamp; está en la tabla modal de damping.
TABLAS_EDITABLES = {
    TABLA_FUNCION_RS: {"clave": "Name", "campos": ("Name", "Period", "Value", "DampRatio"), "modo": "agregar"},
    TABLA_CASO_RS: {"clave": "Name", "campos": ("Name", "ModalCombo", "RigidResp"), "modo": "modificar"},
    TABLA_AMORTIGUAMIENTO_MODAL: {"clave": "Name", "campos": ("Name", "ConstDamp"), "modo": "modificar"},
    # ETABS 21 v1 (metadatos reales 185): Story/Label son de solo lectura y no se reenvían; GUID opcional.
    # Modo agregar: conserva filas ajenas y rechaza objetos que ya tengan registros (colisión), sin reemplazar la tabla.
    TABLA_NO_UNIFORME: {"clave": "UniqueName", "campos": CAMPOS_NO_UNIFORME, "modo": "agregar"},
}
# Textos de celda NO observados en filas reales: antes de mutar, la descripción real del campo
# (GetAllFieldsInTable) debe nombrarlos como palabra completa; si no, el plan se detiene.
# Código de GetModalComb_1 según la convención CSI documentada para SAP2000 (1 = CQC, 2 = SRSS); se relee.
COMBINACION_MODAL = {"CQC": ("CQC", 1), "SRSS": ("SRSS", 2)}
TEXTO_SIN_RESPUESTA_RIGIDA = "No"
DIRECCION_ESPECTRAL = {"UX": "U1", "UY": "U2", "UZ": "U3"}  # con CSys Global y Ang 0, U1/U2/U3 = X/Y/Z
TOLERANCIA_RELECTURA = 1e-12
CLAVES_EIGEN = ("frecuencia_desplazamiento_hz", "frecuencia_corte_hz", "tolerancia", "desplazamiento_automatico")

# Capacidades fuera del subconjunto: su presencia rechaza el plan completo.
PENDIENTES = {
    "respuesta_rigida": "Respuesta rígida en casos espectrales (f1, f2 y combinación periódica+rígida) no implementada.",
    "masa_explicita": "Masas puntuales: el contrato no declara a qué grados de libertad se asigna la masa escalar.",
}

CONSTANTES_DINAMICAS = [
    {"parametro": "cCaseModalEigen.SetNumberModes", "valor": "MaxModes = MinModes = numero_modos",
     "motivo": "El contrato declara un número de modos; se piden exactamente esos modos."},
    {"parametro": "cCaseResponseSpectrum.SetLoads", "valor": "LoadName U1/U2/U3, CSys 'Global', Ang 0",
     "motivo": "Traducción directa de direccion UX/UY/UZ; sin rotación."},
    {"parametro": "cCaseResponseSpectrum.SetLoads.SF", "valor": "factor del caso",
     "motivo": "La función guarda valores numéricos iguales a la aceleración en m/s2 (ETABS los trata como adimensionales) "
               "y el factor de escala lleva las unidades de aceleración del modelo (m con kN_m_C)."},
    {"parametro": TABLA_CASO_RS + ".RigidResp", "valor": TEXTO_SIN_RESPUESTA_RIGIDA,
     "motivo": "Solo se admite respuesta_rigida_espectral = false declarada explícitamente; texto no observado en filas, "
               "exigido en la descripción real del campo antes de mutar."},
    {"parametro": TABLA_AMORTIGUAMIENTO_MODAL + ".ConstDamp", "valor": "amortiguamiento del caso",
     "motivo": "El caso espectral no tiene campo de amortiguamiento; se edita la fila del mismo Name en la tabla modal "
               "de damping. DampType no se modifica: se registra GetDampType y se comprueba GetDampConstant."},
    {"parametro": "Combinación direccional", "valor": "no se fija",
     "motivo": "Cada caso del contrato tiene una sola dirección de aceleración; la combinación direccional no interviene."},
]

CONSTANTES_ADAPTADOR = [
    {"parametro": "cPropMaterial.SetMPIsotropic.A", "valor": 0.0,
     "motivo": "El contrato no incluye coeficiente térmico ni cargas térmicas; no interviene en casos estáticos sin temperatura."},
    {"parametro": "cPropMaterial.SetMaterial.MatType", "valor": "NoDesign",
     "motivo": "Material isótropo lineal sin diseño; no se infiere hormigón, acero ni albañilería."},
    {"parametro": "Temp", "valor": 0.0, "motivo": "Propiedades sin dependencia de temperatura."},
    {"parametro": "Color/Notes/GUID", "valor": "-1/''/''", "motivo": "Solo presentación; valores predeterminados de la API."},
    {"parametro": "cStory.SetStories_2", "valor": "IsMasterStory=True, SimilarToStory='', SpliceAbove=False, SpliceHeight=0, color=0",
     "motivo": "Pisos independientes sin empalmes; el color es solo visual."},
    {"parametro": "cPointObj.AddCartesian.MergeOff", "valor": True,
     "motivo": "Evita fusiones silenciosas: cada punto conserva su identificador."},
    {"parametro": "cLoadPatterns.Add.AddAnalysisCase", "valor": False,
     "motivo": "Los casos se crean explícitamente desde la configuración."},
]

CONSTANTES_SUPERFICIES = [
    {"parametro": "cPropArea.SetSlab.SlabType", "valor": "Slab",
     "motivo": "Placa homogénea de prueba (shell_losa_homogenea); no se declara Ribbed/Waffle ni equivalencia con aligerado."},
    {"parametro": "cPropArea.SetSlab.ShellType", "valor": "opción tipo_shell_losa",
     "motivo": "Formulación explícita declarada por el usuario; no hay valor por defecto."},
    {"parametro": "cAreaObj.AddByPoint.Point", "valor": "contorno exacto de la geometría 0.2",
     "motivo": "Mismo orden y número de vértices; sin triangular, reordenar ni fusionar."},
    {"parametro": "Ejes locales de área", "valor": "los que asigne ETABS; no se fijan",
     "motivo": "La normal geométrica no se declara eje local ETABS; las cargas usan direcciones globales."},
    {"parametro": "cAreaObj.SetLoadUniform.Dir (superficie)", "valor": "4/5/6 globales",
     "motivo": "Fuerza por unidad de área real del objeto, no proyectada (Dir 10/11 no se usan)."},
]

PENDIENTES_SUPERFICIES = {
    "aberturas": "Huecos/aberturas en superficies: no implementados; un piso con huecos no puede pasar como polígono relleno.",
    "aligerado": "Propiedad explícita Ribbed/Waffle v1 horizontal en plan de desarrollo; falta relectura independiente tras reapertura y validación real. No admite rellenos, nervios discontinuos ni equivalencia automática del caso real.",
    "tanque_agua": ("Efecto hidrodinámico, interacción suelo-depósito y apoyos de tanque/cisterna: no implementados. La presión "
                    "hidrostática estática sobre superficies declaradas existe en el plan 0.5; fondos/tapas requieren su "
                    "formulación por sección (tipo_shell_losa por sección, R241)."),
    "escalera": "Escalera completa (tramos, descansos y vínculo con pisos): no implementada; solo superficies planas sueltas.",
    "concavidad": "Contornos cóncavos: válidos en geometría 0.2 pero rechazados por este primer transporte hasta verificarlos en ETABS.",
    "lectura_cargas_area": "El efecto de SetLoadUniform no se relee (GetLoadUniform no está en la lista blanca).",
}

INTEGRACION_PENDIENTE = [
    "Ejecutor y script: el ejecutor solo acepta planes 0.1 (validar_plan); ejecutar un plan 0.2 exige revisión de Codex del recorrido completo.",
    "Gestión de configuración, plan geométrico e interfaz: crear, revisar y aprobar configuraciones 0.2 y mostrar superficies.",
    "Lectura posterior (normalización, controles, informe): propagar superficies, huellas 0.2 y sus límites.",
    "Prueba local ETABS en copia: coordenadas, conectividad, sección, cargas y fuente de masa tras guardar y reabrir.",
]


# -- errores -------------------------------------------------------------------

PENDIENTES_MALLA = {
    "verificacion_real": "Transporte, guardado, reapertura y relectura independiente en ETABS real (Codex); los dobles no lo acreditan.",
    "calidad_malla": "Calidad de malla, rigidez y convergencia no evaluadas; sin solver.",
    "diafragma_nodos_derivados": "Asignación de diafragma de nodos derivados sin getter en la lista blanca: se registra en la traza de llamadas, no se relee.",
    "presion_hidrostatica": "No se convierte presión hidrostática ni variable: solo cargas uniformes globales copiadas por triángulo.",
}


class ErrorPlan(ValueError):
    """Solicitud inválida (opciones, rutas). Código 1."""

    codigo = 1


class ErrorPlanRechazado(ErrorPlan):
    """Configuración no apta o con características no soportadas. Código 2; no se genera plan."""

    codigo = 2

    def __init__(self, mensaje: str, motivos: list[str]):
        super().__init__(mensaje + "\n" + "\n".join(f"  - {m}" for m in motivos))
        self.motivos = list(motivos)


@dataclass
class PlanOperaciones:
    datos: dict[str, Any]

    @property
    def huella(self) -> str:
        return self.datos["huella_plan"]

    @property
    def operaciones(self) -> list[dict[str, Any]]:
        return self.datos["operaciones"]

    def a_json(self) -> str:
        return json.dumps(self.datos, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def huella_plan(datos: dict[str, Any]) -> str:
    contenido = {k: v for k, v in datos.items() if k != "huella_plan"}
    return hashlib.sha256(json.dumps(contenido, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


# -- construcción de operaciones --------------------------------------------

def _enum(tipo: str, nombre: str | None) -> dict[str, Any]:
    if nombre is None:
        return {"enum": tipo, "nombre": None, "valor": 0, "significado": "todos"}
    return {"enum": tipo, "nombre": nombre, "valor": ENUMS[tipo][nombre]}


def _ref(clase: str, ident: str) -> dict[str, str]:
    return {"ref": f"{clase}:{ident}"}


class _Constructor:
    def __init__(self):
        self.operaciones: list[dict[str, Any]] = []
        self.salidas: set[str] = set()

    def op(self, fase: str, metodo: str, valores: dict[str, Any], origen: str, *,
           salidas: dict[str, tuple[str, str]] | None = None, retorno: int = 0,
           ausentes: dict[str, list[str]] | None = None, presentes: dict[str, list[str]] | None = None,
           releer: dict[str, Any] | None = None, importables: list[str] | None = None,
           textos: dict[str, list[str]] | None = None, registrar: list[str] | None = None,
           descripcion: str = "") -> None:
        ruta, tipo_retorno, parametros = FIRMAS[metodo]
        nombres = [nombre for _, nombre in parametros]
        if list(valores) != nombres:
            raise AssertionError(f"{metodo}: argumentos {list(valores)} no siguen la firma {nombres}")
        argumentos = []
        for (tipo, nombre) in parametros:
            valor = valores[nombre]
            for referencia in _referencias(valor):
                if referencia not in self.salidas:
                    raise AssertionError(f"{metodo}: referencia anterior inexistente {referencia}")
            argumentos.append({"nombre": nombre, "tipo": tipo, "valor": valor})
        operacion = {
            "orden": len(self.operaciones) + 1, "fase": fase, "interfaz": ruta, "metodo": metodo,
            "argumentos": argumentos, "retorno": {"tipo": tipo_retorno, "esperado": retorno}, "origen": origen,
        }
        if descripcion:
            operacion["descripcion"] = descripcion
        if salidas:
            operacion["salidas"] = [{"parametro": p, "registra": reg, "debe_ser": esperado}
                                    for p, (reg, esperado) in salidas.items()]
            for reg, _ in salidas.values():
                if reg in self.salidas:
                    raise AssertionError(f"Salida registrada dos veces: {reg}")
                self.salidas.add(reg)
        if ausentes:
            operacion["verificar_ausentes"] = [{"parametro": p, "nombres": sorted(n)} for p, n in ausentes.items()]
        if presentes:
            operacion["verificar_presentes"] = [{"parametro": p, "nombres": sorted(n)} for p, n in presentes.items()]
        if releer:
            operacion["verificar_valores"] = [{"parametro": p, "esperado": v, "tolerancia_relativa": TOLERANCIA_RELECTURA}
                                              for p, v in releer.items()]
        if importables:
            operacion["verificar_importables"] = sorted(importables)
        if textos:
            operacion["verificar_textos"] = [{"campo": c, "valores": sorted(set(v))} for c, v in sorted(textos.items())]
        if registrar:
            operacion["registrar_valores"] = list(registrar)
        self.operaciones.append(operacion)

    def tabla(self, fase: str, tabla: str, registros: list[dict[str, str]], origen: str, descripcion: str) -> None:
        definicion = TABLAS_EDITABLES[tabla]
        self.operaciones.append({
            "orden": len(self.operaciones) + 1, "fase": fase, "tipo": "edicion_tabla", "interfaz": "SapModel.DatabaseTables",
            "metodo": "edicion_tabla", "tabla": tabla, "modo": definicion["modo"], "clave": definicion["clave"],
            "campos": list(definicion["campos"]), "registros": registros, "metodos": list(METODOS_EDICION_TABLA),
            "retorno": {"tipo": "Int32", "esperado": 0}, "origen": origen, "descripcion": descripcion,
        })


def _referencias(valor: Any) -> list[str]:
    if isinstance(valor, dict) and set(valor) == {"ref"}:
        return [valor["ref"]]
    if isinstance(valor, list):
        return [r for v in valor for r in _referencias(v)]
    return []


def _motivos_no_soportados(config: dict, opciones: dict) -> list[str]:
    motivos = []
    for caso, rigida in sorted((opciones.get("respuesta_rigida_espectral") or {}).items()):
        if rigida is True:
            motivos.append(f"Caso espectral '{caso}' con respuesta rígida: " + PENDIENTES["respuesta_rigida"])
    masa = config["masa"]
    if masa["metodo"] != "patrones":
        motivos.append("Masa por método 'explicita': " + PENDIENTES["masa_explicita"])
    else:
        g_programa = opciones.get("gravedad_programa_m_s2")
        if g_programa is None:
            motivos.append("La masa desde cargas usa la gravedad interna de ETABS, que la API no permite fijar ni leer; "
                           "declare gravedad_programa_m_s2 tras comprobarla en ETABS.")
        elif not math.isclose(g_programa, masa["gravedad_m_s2"], rel_tol=0, abs_tol=1e-9):
            motivos.append(f"gravedad_m_s2 de la configuración ({masa['gravedad_m_s2']}) difiere de la gravedad "
                           f"declarada del programa ({g_programa}).")
    casos = {c["id"] for c in config["casos"]}
    for combo in config["combinaciones"]:
        if combo["id"] in casos:
            motivos.append(f"La combinación '{combo['id']}' repite el nombre de un caso; ETABS exige nombres distintos.")
    vistos: dict[tuple, str] = {}
    for carga in config["cargas"]:
        for i, valor in enumerate(carga["componentes"]):
            if valor == 0:
                continue
            clave = (carga["objetivo_tipo"], carga["objetivo"], carga["patron"], i)
            if clave in vistos:
                motivos.append(f"Cargas '{vistos[clave]}' y '{carga['id']}' coinciden en objetivo, patrón y dirección; "
                               "la acumulación en ETABS no está verificada.")
            vistos[clave] = carga["id"]
    return motivos


def _finito(valor: Any) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)


def _texto_numero(valor: Any) -> str:
    """Número para una tabla editable: representación decimal exacta de ida y vuelta, con punto."""
    return repr(float(valor))


def _validar_eigen(valor: Any) -> str | None:
    if not isinstance(valor, dict) or set(valor) != set(CLAVES_EIGEN):
        return "se requieren exactamente " + ", ".join(CLAVES_EIGEN)
    if not all(_finito(valor[k]) and valor[k] >= 0 for k in CLAVES_EIGEN[:2]):
        return "frecuencias de desplazamiento y de corte deben ser números >= 0 (Hz)"
    if not _finito(valor["tolerancia"]) or valor["tolerancia"] <= 0:
        return "tolerancia debe ser un número positivo"
    if not isinstance(valor["desplazamiento_automatico"], bool):
        return "desplazamiento_automatico debe ser booleano"
    return None


def _validar_opciones_dinamicas(config: dict, opciones: dict) -> None:
    """Exige una opción explícita por cada caso o espectro que la necesite; nada sobra ni falta."""
    modales = [c["id"] for c in config["casos"] if c["tipo"] == "modal_eigen"]
    espectrales = [c["id"] for c in config["casos"] if c["tipo"] == "espectro_respuesta"]
    espectros = [e["id"] for e in config["espectros"]]
    errores = []
    reglas = [
        ("parametros_modales", modales, _validar_eigen, "casos modal_eigen"),
        ("amortiguamiento_funciones", espectros,
         lambda v: None if _finito(v) and 0 <= v < 1 else "amortiguamiento de la función: número 0 <= valor < 1", "espectros"),
        ("excentricidad_espectral", espectrales,
         lambda v: None if _finito(v) and v >= 0 else "razón de excentricidad de diafragma: número >= 0",
         "casos espectro_respuesta"),
        ("respuesta_rigida_espectral", espectrales,
         lambda v: None if isinstance(v, bool) else "debe declararse true o false", "casos espectro_respuesta"),
    ]
    for nombre, ids, validar, que in reglas:
        valor = opciones.get(nombre)
        if not ids:
            if valor is not None:
                errores.append(f"'{nombre}' no aplica: la configuración no declara {que}.")
            continue
        if not isinstance(valor, dict):
            errores.append(f"'{nombre}' es obligatoria y explícita para {', '.join(ids)}; no hay valor por defecto.")
            continue
        for faltante in sorted(set(ids) - set(valor)):
            errores.append(f"'{nombre}' no declara '{faltante}'.")
        for sobrante in sorted(set(valor) - set(ids)):
            errores.append(f"'{nombre}' declara '{sobrante}', que no es uno de sus {que}.")
        for ident in ids:
            if ident in valor:
                mensaje = validar(valor[ident])
                if mensaje:
                    errores.append(f"{nombre}.{ident}: {mensaje}.")
    if errores:
        raise ErrorPlan("Opciones dinámicas inválidas o ausentes:\n" + "\n".join(f"  - {e}" for e in errores))


def _validar_opciones(opciones: dict) -> dict:
    permitidas = {"destino_guardado", "tipo_shell_muro", "gravedad_programa_m_s2", "parametros_modales",
                  "amortiguamiento_funciones", "excentricidad_espectral", "respuesta_rigida_espectral"}
    sobrantes = set(opciones) - permitidas
    if sobrantes:
        raise ErrorPlan("Opciones no admitidas: " + ", ".join(sorted(sobrantes)))
    destino = opciones.get("destino_guardado")
    if not isinstance(destino, str) or not Path(destino).is_absolute() or Path(destino).suffix.lower() != ".edb":
        raise ErrorPlan("'destino_guardado' debe ser una ruta absoluta .edb (el ejecutor exigirá que no exista).")
    if opciones.get("tipo_shell_muro") not in TIPOS_SHELL_MURO:
        raise ErrorPlan("'tipo_shell_muro' es obligatorio y explícito: " + ", ".join(TIPOS_SHELL_MURO) + ".")
    g = opciones.get("gravedad_programa_m_s2")
    if g is not None and (isinstance(g, bool) or not isinstance(g, (int, float)) or not math.isfinite(g) or g <= 0):
        raise ErrorPlan("'gravedad_programa_m_s2' debe ser un número positivo.")
    return dict(opciones)


def generar_plan(raiz: Path, configuracion: Any, **opciones: Any) -> PlanOperaciones:
    """Genera el plan desde una configuración apta. No escribe archivos ni contacta ETABS.

    Opciones obligatorias: destino_guardado (.edb absoluto), tipo_shell_muro. Con masa por
    patrones también gravedad_programa_m_s2. Lanza ErrorPlan o ErrorPlanRechazado.
    """
    opciones = _validar_opciones(opciones)
    config = copy.deepcopy(configuracion)  # las entradas no se modifican
    resultado = me.comprobar_configuracion(Path(raiz), config)
    if not resultado.apto_para_adaptador:
        raise ErrorPlanRechazado("La configuración no es apta para el adaptador; no se genera plan.",
                                 list(resultado.errores) + list(resultado.bloqueos) or ["apto_para_adaptador es falso."])
    vg = _geometria_vigente(Path(raiz), config)
    _validar_opciones_dinamicas(config, opciones)
    motivos = _motivos_no_soportados(config, opciones)
    niveles = _niveles_piso(vg)
    motivos += _motivos_niveles(niveles)
    if motivos:
        raise ErrorPlanRechazado("Características no soportadas por el subconjunto inicial; se rechaza el plan completo.",
                                 motivos)
    return _compilar(config, resultado, vg, niveles, opciones, None)


def _geometria_vigente(raiz: Path, config: dict):
    origen = config["geometria_origen"]
    try:
        consulta = gg.consultar_version(raiz, config["caso"], origen["version_id"])
    except ErrorGestion as error:
        raise ErrorPlanRechazado("Geometría versionada no disponible.", [str(error)]) from error
    comp = consulta.comprobacion
    if not comp.correcta or comp.sha256_geometria != origen["sha256_geometria"] or comp.huella_contenido != origen["huella_contenido"]:
        raise ErrorPlanRechazado("La geometría cambió desde la comprobación.", list(comp.problemas) or ["Huellas distintas."])
    return validar_geometria(consulta.geometria)


def _niveles_piso(vg: Any) -> list[dict]:
    """Pisos ordenados por cota; las cotas auxiliares (tipo "auxiliar") no son Story de ETABS."""
    return sorted((n for n in vg.geometria_m["niveles"] if n.get("tipo", "piso") == "piso"), key=lambda n: n["cota"])


def _niveles_auxiliares(vg: Any) -> list[dict]:
    return sorted((n for n in vg.geometria_m["niveles"] if n.get("tipo") == "auxiliar"), key=lambda n: n["cota"])


def _motivos_niveles(niveles: list[dict]) -> list[str]:
    motivos = []
    if len(niveles) < 2:
        motivos.append("ETABS requiere al menos un piso sobre la base; la geometría tiene un único nivel.")
    if any(n["id"] == NOMBRE_BASE_ETABS for n in niveles[1:]):
        motivos.append(f"Un nivel superior se llama '{NOMBRE_BASE_ETABS}', reservado para la base en ETABS.")
    return motivos


def _compilar(config: dict, resultado: Any, vg: Any, niveles: list[dict], opciones: dict,
              sup: dict | None) -> PlanOperaciones:
    """Operaciones comunes. `sup` (solo plan 0.2) aporta coordenadas XYZ, contornos y asignaciones de superficies."""
    origen = config["geometria_origen"]
    nodos = {n["id"]: n for n in vg.geometria_m["nodos"]}
    cotas = {n["id"]: n["cota"] for n in niveles}
    puntos = {p["id"]: p for p in config["puntos"]}
    par_punto = {(p["nodo_geometria"], p["nivel_geometria"]): p["id"] for p in config["puntos"] if "nodo_geometria" in p}
    secciones = {s["id"]: s for s in config["secciones"]}
    asign_frames = {a["objetivo"]: a["seccion"] for a in config["asignaciones_frames"]}
    asign_muros = {a["objetivo"]: a["seccion"] for a in config["asignaciones_muros"]}
    muros = {m["id"]: m for m in vg.geometria_m["muros"]}
    b = _Constructor()

    # 0. Verificaciones de lectura sobre la copia abierta: modelo vacío y nombres libres.
    b.op("verificacion", "cPointObj.Count", {}, "precondicion", retorno=0, descripcion="La copia no contiene puntos.")
    b.op("verificacion", "cFrameObj.Count", {"MyType": "All"}, "precondicion", retorno=0)
    b.op("verificacion", "cAreaObj.Count", {}, "precondicion", retorno=0)
    libres = [
        ("cPropMaterial.GetNameList", {"MatType": _enum("eMatType", None)}, [m["id"] for m in config["materiales"]]),
        ("cPropArea.GetNameList", {"PropType": 0}, [s["id"] for s in config["secciones"]
                                                    if s["tipo"] in ("shell_muro", "shell_losa_homogenea") + TIPOS_ALIGERADOS]),
        ("cPropFrame.GetNameList", {"PropType": _enum("eFramePropType", None)},
         [s["id"] for s in config["secciones"] if s["tipo"] in me.TIPOS_FRAME]),
        ("cLoadPatterns.GetNameList", {}, [p["id"] for p in config["patrones"]]),
        ("cLoadCases.GetNameList", {"CaseType": _enum("eLoadCaseType", None)},
         [c["id"] for c in config["casos"]] + [c["id"] for c in config["combinaciones"]]),
        ("cCombo.GetNameList", {}, [c["id"] for c in config["combinaciones"]] + [c["id"] for c in config["casos"]]),
        ("cDiaphragm.GetNameList", {}, [d["id"] for d in config["diafragmas"]]),
    ]
    for metodo, extra, nombres in libres:
        b.op("verificacion", metodo, {"NumberNames": 0, "MyName": [], **extra}, "precondicion",
             ausentes={"MyName": nombres})
    modales = [c for c in config["casos"] if c["tipo"] == "modal_eigen"]
    espectrales = [c for c in config["casos"] if c["tipo"] == "espectro_respuesta"]
    espectros = config["espectros"]
    dinamico = bool(modales or espectrales or espectros)
    if espectros:
        b.op("verificacion", "cFunction.GetNameList", {"NumberNames": 0, "MyName": [], "FuncType": 0}, "precondicion",
             ausentes={"MyName": [e["id"] for e in espectros]}, descripcion="FuncType 0: todas las funciones.")
    textos_caso = {"ModalCombo": [COMBINACION_MODAL[c["parametros"]["combinacion_modal"]][0] for c in espectrales],
                   "RigidResp": [TEXTO_SIN_RESPUESTA_RIGIDA]}
    tablas = ([TABLA_FUNCION_RS] if espectros else []) + ([TABLA_CASO_RS, TABLA_AMORTIGUAMIENTO_MODAL] if espectrales else [])
    for tabla in tablas:
        campos = list(TABLAS_EDITABLES[tabla]["campos"])
        b.op("verificacion", "cDatabaseTables.GetAllFieldsInTable", {"TableKey": tabla, "TableVersion": 0, "NumberFields": 0,
             "FieldKey": [], "FieldName": [], "Description": [], "UnitsString": [], "IsImportable": []}, "precondicion",
             presentes={"FieldKey": campos}, importables=campos, textos=textos_caso if tabla == TABLA_CASO_RS else None,
             descripcion="La tabla existe, ofrece los campos editados como importables y, en el caso, su descripción "
                         "nombra los textos que el plan escribirá.")

    # 1. Unidades y pisos.
    b.op("unidades", "cSapModel.SetPresentUnits", {"Units": _enum("eUnits", UNIDADES_ETABS)}, "$.unidades")
    pisos = niveles[1:]
    b.op("pisos", "cStory.SetStories_2", {
        "BaseElevation": niveles[0]["cota"], "NumberStories": len(pisos), "StoryNames": [n["id"] for n in pisos],
        "StoryHeights": [n["cota"] - a["cota"] for a, n in zip(niveles, pisos)],
        "IsMasterStory": [True] * len(pisos), "SimilarToStory": [""] * len(pisos), "SpliceAbove": [False] * len(pisos),
        "SpliceHeight": [0.0] * len(pisos), "color": [0] * len(pisos)}, "geometria.niveles")

    # 2. Materiales y secciones.
    for mat in config["materiales"]:
        origen_m = f"$.materiales.{mat['id']}"
        b.op("materiales", "cPropMaterial.SetMaterial", {"Name": mat["id"], "MatType": _enum("eMatType", "NoDesign"),
             "Color": -1, "Notes": "", "GUID": ""}, origen_m)
        b.op("materiales", "cPropMaterial.SetMPIsotropic", {"Name": mat["id"], "E": mat["E_kN_m2"], "U": mat["poisson"],
             "A": 0.0, "Temp": 0.0}, origen_m)
        b.op("materiales", "cPropMaterial.SetWeightAndMass", {"Name": mat["id"], "MyOption": 1,
             "Value": mat["peso_kN_m3"], "Temp": 0.0}, origen_m, descripcion="MyOption 1: peso por unidad de volumen.")
    for sec in config["secciones"]:
        origen_s = f"$.secciones.{sec['id']}"
        if sec["tipo"] == "shell_muro":
            b.op("secciones", "cPropArea.SetWall", {"Name": sec["id"], "WallPropType": _enum("eWallPropType", "Specified"),
                 "ShellType": _enum("eShellType", opciones["tipo_shell_muro"]), "MatProp": sec["material"],
                 "Thickness": sec["dimensiones"].get("espesor_m", sec["dimensiones"].get("alto_total_m")), "color": -1, "notes": "", "GUID": ""}, origen_s)
        elif sec["tipo"] in ("shell_losa_homogenea",) + TIPOS_ALIGERADOS:
            b.op("secciones", "cPropArea.SetSlab", {"Name": sec["id"], "SlabType": _enum("eSlabType", _clase_losa(sec)),
                 "ShellType": _enum("eShellType", _tipo_losa(opciones, sec["id"])), "MatProp": sec["material"],
                 "Thickness": sec["dimensiones"].get("espesor_m", sec["dimensiones"].get("capa_m")), "color": -1, "notes": "", "GUID": ""}, origen_s,
                 descripcion="Espesor de placa/capa; el alto total de aligerados se fija separadamente con SetSlabRibbed/Waffle.")
            if sec["tipo"] in TIPOS_ALIGERADOS:
                b.op("secciones", "cPropArea.SetSlab" + _clase_losa(sec), {"Name": sec["id"], **_parametros_aligerados(sec)}, origen_s)
        elif sec["tipo"] == me.SECCION_L:
            b.op("secciones", "cPropFrame.SetConcreteL", _parametros_l(sec), origen_s,
                 descripcion="L nativa: T3 = alto_m y T2 = ancho_m (envolvente), Tf = espesor_ala_m, TwC = TwT = espesor_alma_m; "
                             "espejos según la convención ensayada (sin espejos: brazos a +local2/−local3).")
        else:
            b.op("secciones", "cPropFrame.SetRectangle", {"Name": sec["id"], "MatProp": sec["material"],
                 "T3": sec["dimensiones"]["alto_m"], "T2": sec["dimensiones"]["ancho_m"], "Color": -1, "Notes": "",
                 "GUID": ""}, origen_s, descripcion="T3 = alto_m (peralte), T2 = ancho_m.")

    # 3. Objetos: puntos, frames y muros. ETABS asigna Name; se exige que sea el ID declarado.
    for pid, punto in puntos.items():
        if sup is not None:
            x, y, z = sup["coordenadas"][pid]  # metros de geometria_m; un vértice puede quedar entre pisos
        else:
            nodo = nodos[punto["nodo_geometria"]]
            x, y, z = nodo["x"], nodo["y"], cotas[punto["nivel_geometria"]]
        b.op("puntos", "cPointObj.AddCartesian", {"X": x, "Y": y, "Z": z,
             "Name": "", "UserName": pid, "CSys": "Global", "MergeOff": True, "MergeNumber": 0}, f"$.puntos.{pid}",
             salidas={"Name": (f"punto:{pid}", pid)})
    for frame in config["frames"]:
        b.op("frames", "cFrameObj.AddByPoint", {"Point1": _ref("punto", frame["inicio"]), "Point2": _ref("punto", frame["fin"]),
             "Name": "", "PropName": asign_frames[frame["id"]], "UserName": frame["id"]}, f"$.frames.{frame['id']}",
             salidas={"Name": (f"frame:{frame['id']}", frame["id"])})
    for ins in config.get("insercion_frames", []):
        b.op("frames", "cFrameObj.SetInsertionPoint", {"Name": _ref("frame", ins["frame"]), "CardinalPoint": ins["punto_cardinal"],
             "Mirror2": False, "StiffTransform": ins["transformar_rigidez"], "Offset1": list(ins["desplazamiento_global_m"]),
             "Offset2": list(ins["desplazamiento_global_m"]), "CSys": "Global", "ItemType": _enum("eItemType", "Objects")},
             f"$.insercion_frames.{ins['frame']}",
             descripcion="Centroide desplazado del eje del frame por el vector global (igual en ambos extremos); rigidez transformada.")
    for mid in sorted(asign_muros):
        muro = muros[mid]
        esquinas = [par_punto[(muro["nodo_inicio"], muro["nivel_inferior"])], par_punto[(muro["nodo_fin"], muro["nivel_inferior"])],
                    par_punto[(muro["nodo_fin"], muro["nivel_superior"])], par_punto[(muro["nodo_inicio"], muro["nivel_superior"])]]
        b.op("muros", "cAreaObj.AddByPoint", {"NumberPoints": 4, "Point": [_ref("punto", p) for p in esquinas], "Name": "",
             "PropName": asign_muros[mid], "UserName": mid}, f"geometria.muros.{mid}",
             salidas={"Name": (f"muro:{mid}", mid)}, descripcion="Esquinas en orden perimetral: inicio-inf, fin-inf, fin-sup, inicio-sup.")
    if sup is not None:
        _superficies(b, config, sup, asign_muros, muros, par_punto, opciones)

    # 4. Patrones y cargas (fuerzas globales; una llamada por componente no nula).
    for patron in config["patrones"]:
        b.op("patrones", "cLoadPatterns.Add", {"Name": patron["id"], "MyType": _enum("eLoadPatternType", TIPO_PATRON[patron["tipo"]]),
             "SelfWTMultiplier": patron["multiplicador_peso_propio"], "AddAnalysisCase": False}, f"$.patrones.{patron['id']}")
    sin_efecto = []
    for carga in config["cargas"]:
        origen_c = f"$.cargas.{carga['id']}"
        comp = carga["componentes"]
        if not any(comp):
            sin_efecto.append(carga["id"])
            continue
        if carga["objetivo_tipo"] == "punto":
            b.op("cargas", "cPointObj.SetLoadForce", {"Name": _ref("punto", carga["objetivo"]), "LoadPat": carga["patron"],
                 "Value": [comp[0], comp[1], comp[2], 0.0, 0.0, 0.0], "Replace": False, "CSys": "Global",
                 "ItemType": _enum("eItemType", "Objects")}, origen_c, descripcion="[Fx,Fy,Fz,Mx,My,Mz] en kN; momentos nulos.")
            continue
        for i, valor in enumerate(comp):
            if valor == 0:
                continue
            if carga["objetivo_tipo"] == "frame":
                b.op("cargas", "cFrameObj.SetLoadDistributed", {"Name": _ref("frame", carga["objetivo"]), "LoadPat": carga["patron"],
                     "MyType": 1, "Dir": DIRECCION_GLOBAL[i], "Dist1": 0.0, "Dist2": 1.0, "Val1": valor, "Val2": valor,
                     "CSys": "Global", "RelDist": True, "Replace": False, "ItemType": _enum("eItemType", "Objects")},
                     origen_c, descripcion="Fuerza uniforme kN/m en toda la longitud.")
            elif carga["objetivo_tipo"] == "superficie":
                b.op("cargas", "cAreaObj.SetLoadUniform", {"Name": _ref("superficie", carga["objetivo"]),
                     "LoadPat": carga["patron"], "Value": valor, "Dir": DIRECCION_GLOBAL[i], "Replace": False,
                     "CSys": "Global", "ItemType": _enum("eItemType", "Objects")}, origen_c,
                     descripcion="Fuerza uniforme kN/m2 por unidad de área real, dirección global (no proyectada).")
            else:
                b.op("cargas", "cAreaObj.SetLoadUniform", {"Name": _ref("muro", carga["objetivo"]), "LoadPat": carga["patron"],
                     "Value": valor, "Dir": DIRECCION_GLOBAL[i], "Replace": False, "CSys": "Global",
                     "ItemType": _enum("eItemType", "Objects")}, origen_c, descripcion="Presión uniforme kN/m2.")

    # 5. Masa, apoyos y diafragmas.
    masa = config["masa"]
    b.op("masa", "cPropMaterial.SetMassSource_1", {"IncludeElements": masa["incluir_masa_propia"], "IncludeAddedMass": False,
         "IncludeLoads": True, "NumberLoads": len(masa["factores_patrones"]),
         "LoadPat": [f["patron"] for f in masa["factores_patrones"]], "sf": [f["factor"] for f in masa["factores_patrones"]]},
         "$.masa", descripcion="Masa desde patrones de carga con la gravedad interna de ETABS.")
    for apoyo in config["apoyos"]:
        b.op("apoyos", "cPointObj.SetRestraint", {"Name": _ref("punto", apoyo["punto"]), "Value": list(apoyo["restricciones"]),
             "ItemType": _enum("eItemType", "Objects")}, f"$.apoyos.{apoyo['punto']}", descripcion="[Ux,Uy,Uz,Rx,Ry,Rz].")
    for dia in config["diafragmas"]:
        b.op("diafragmas", "cDiaphragm.SetDiaphragm", {"Name": dia["id"], "SemiRigid": dia["tipo"] == "semirigido"},
             f"$.diafragmas.{dia['id']}")
        for pid in dia["puntos"]:
            b.op("diafragmas", "cPointObj.SetDiaphragm", {"Name": _ref("punto", pid),
                 "DiaphragmOption": _enum("eDiaphragmOption", "DefinedDiaphragm"), "DiaphragmName": dia["id"]},
                 f"$.diafragmas.{dia['id']}")
    for item in config["sin_diafragma"]:
        b.op("diafragmas", "cPointObj.SetDiaphragm", {"Name": _ref("punto", item["punto"]),
             "DiaphragmOption": _enum("eDiaphragmOption", "Disconnect"), "DiaphragmName": ""},
             f"$.sin_diafragma.{item['punto']}")

    # 6. Casos, combinaciones y marcas de ejecución (sin ejecutar análisis).
    for caso in config["casos"]:
        if caso["tipo"] != "estatico_lineal":
            continue  # modal y espectral: fases propias más abajo
        patrones = caso["parametros"]["patrones"]
        b.op("casos", "cCaseStaticLinear.SetCase", {"Name": caso["id"]}, f"$.casos.{caso['id']}")
        b.op("casos", "cCaseStaticLinear.SetLoads", {"Name": caso["id"], "NumberLoads": len(patrones),
             "LoadType": ["Load"] * len(patrones), "LoadName": [p["patron"] for p in patrones],
             "SF": [p["factor"] for p in patrones]}, f"$.casos.{caso['id']}")
    for caso in modales:
        eigen = opciones["parametros_modales"][caso["id"]]
        n = caso["parametros"]["numero_modos"]
        origen_k = f"$.casos.{caso['id']}"
        b.op("casos_modales", "cCaseModalEigen.SetCase", {"Name": caso["id"]}, origen_k)
        b.op("casos_modales", "cCaseModalEigen.SetNumberModes", {"Name": caso["id"], "MaxModes": n, "MinModes": n}, origen_k)
        b.op("casos_modales", "cCaseModalEigen.SetParameters", {"Name": caso["id"],
             "EigenShiftFreq": eigen["frecuencia_desplazamiento_hz"], "EigenCutOff": eigen["frecuencia_corte_hz"],
             "EigenTol": eigen["tolerancia"], "AllowAutoFreqShift": 1 if eigen["desplazamiento_automatico"] else 0},
             f"opciones.parametros_modales.{caso['id']}", descripcion="Frecuencias en cyc/s; 1 = desplazamiento automático.")
    if espectros:
        registros = [{"Name": e["id"], "Period": _texto_numero(t), "Value": _texto_numero(a),
                      "DampRatio": _texto_numero(opciones["amortiguamiento_funciones"][e["id"]])}
                     for e in espectros for t, a in e["puntos"]]
        b.tabla("funciones_espectrales", TABLA_FUNCION_RS, registros, "$.espectros",
                "Funciones tabuladas: periodo s, aceleración m/s2 como valor numérico, amortiguamiento explícito.")
    for caso in espectrales:
        p = caso["parametros"]
        origen_k = f"$.casos.{caso['id']}"
        b.op("casos_espectrales", "cCaseResponseSpectrum.SetCase", {"Name": caso["id"]}, origen_k)
        b.op("casos_espectrales", "cCaseResponseSpectrum.SetModalCase", {"Name": caso["id"], "ModalCase": p["modal"]}, origen_k)
        b.op("casos_espectrales", "cCaseResponseSpectrum.SetLoads", {"Name": caso["id"], "NumberLoads": 1,
             "LoadName": [DIRECCION_ESPECTRAL[p["direccion"]]], "Func": [p["espectro"]], "SF": [p["factor"]],
             "CSys": ["Global"], "Ang": [0.0]}, origen_k)
        b.op("casos_espectrales", "cCaseResponseSpectrum.SetEccentricity", {"Name": caso["id"],
             "Eccen": opciones["excentricidad_espectral"][caso["id"]]}, f"opciones.excentricidad_espectral.{caso['id']}")
    if espectrales:
        b.tabla("casos_espectrales", TABLA_CASO_RS, [
            {"Name": c["id"], "ModalCombo": COMBINACION_MODAL[c["parametros"]["combinacion_modal"]][0],
             "RigidResp": TEXTO_SIN_RESPUESTA_RIGIDA} for c in espectrales], "$.casos",
            "Combinación modal y respuesta rígida del caso (sin setter OAPI en ETABS 21).")
        b.tabla("casos_espectrales", TABLA_AMORTIGUAMIENTO_MODAL, [
            {"Name": c["id"], "ConstDamp": _texto_numero(c["parametros"]["amortiguamiento"])} for c in espectrales],
            "$.casos", "Amortiguamiento constante del caso en su fila de damping modal (sin setter OAPI en ETABS 21).")
    # Relectura con getters OAPI: el efecto de cada asignación dinámica se comprueba antes de seguir.
    for caso in modales:
        eigen, n = opciones["parametros_modales"][caso["id"]], caso["parametros"]["numero_modos"]
        b.op("comprobacion_dinamica", "cCaseModalEigen.GetNumberModes", {"Name": caso["id"], "MaxModes": 0, "MinModes": 0},
             f"$.casos.{caso['id']}", releer={"MaxModes": n, "MinModes": n})
        b.op("comprobacion_dinamica", "cCaseModalEigen.GetParameters", {"Name": caso["id"], "EigenShiftFreq": 0.0,
             "EigenCutOff": 0.0, "EigenTol": 0.0, "AllowAutoFreqShift": 0}, f"opciones.parametros_modales.{caso['id']}",
             releer={"EigenShiftFreq": eigen["frecuencia_desplazamiento_hz"], "EigenCutOff": eigen["frecuencia_corte_hz"],
                      "EigenTol": eigen["tolerancia"], "AllowAutoFreqShift": 1 if eigen["desplazamiento_automatico"] else 0})
        b.op("comprobacion_dinamica", "cCaseModalEigen.GetLoads", {"Name": caso["id"], "NumberLoads": 0, "LoadType": [],
             "LoadName": [], "TargetPar": [], "StaticCorrect": []}, f"$.casos.{caso['id']}", releer={"NumberLoads": 0},
             descripcion="El contrato no declara cargas iniciales del caso modal.")
    for e in espectros:
        b.op("comprobacion_dinamica", "cFunction.GetValues", {"Name": e["id"], "NumberItems": 0, "MyTime": [], "Value": []},
             f"$.espectros.{e['id']}", releer={"NumberItems": len(e["puntos"]), "MyTime": [t for t, _ in e["puntos"]],
                                                "Value": [a for _, a in e["puntos"]]})
    for caso in espectrales:
        p = caso["parametros"]
        origen_k = f"$.casos.{caso['id']}"
        b.op("comprobacion_dinamica", "cCaseResponseSpectrum.GetModalCase", {"Name": caso["id"], "ModalCase": ""}, origen_k,
             releer={"ModalCase": p["modal"]})
        b.op("comprobacion_dinamica", "cCaseResponseSpectrum.GetLoads", {"Name": caso["id"], "NumberLoads": 0, "LoadName": [],
             "Func": [], "SF": [], "CSys": [], "Ang": []}, origen_k,
             releer={"NumberLoads": 1, "LoadName": [DIRECCION_ESPECTRAL[p["direccion"]]], "Func": [p["espectro"]],
                      "SF": [p["factor"]], "CSys": ["Global"], "Ang": [0.0]})
        b.op("comprobacion_dinamica", "cCaseResponseSpectrum.GetEccentricity", {"Name": caso["id"], "Eccen": 0.0},
             f"opciones.excentricidad_espectral.{caso['id']}", releer={"Eccen": opciones["excentricidad_espectral"][caso["id"]]})
        b.op("comprobacion_dinamica", "cCaseResponseSpectrum.GetDampConstant", {"Name": caso["id"], "Damp": 0.0}, origen_k,
             releer={"Damp": p["amortiguamiento"]})
        b.op("comprobacion_dinamica", "cCaseResponseSpectrum.GetDampType", {"Name": caso["id"], "DampType": 0}, origen_k,
             registrar=["DampType"], descripcion="Se registra; el código del tipo constante no está documentado ni observado.")
        b.op("comprobacion_dinamica", "cCaseResponseSpectrum.GetModalComb_1", {"Name": caso["id"], "MyType": 0, "F1": 0.0,
             "F2": 0.0, "PeriodicRigidCombType": 0, "Td": 0.0}, origen_k,
             releer={"MyType": COMBINACION_MODAL[p["combinacion_modal"]][1]})
    for combo in config["combinaciones"]:
        b.op("combinaciones", "cCombo.Add", {"Name": combo["id"], "ComboType": TIPO_COMBINACION[combo["tipo"]]},
             f"$.combinaciones.{combo['id']}", descripcion="ComboType 0 aditiva lineal, 1 envolvente.")
        for factor in combo["casos"]:
            b.op("combinaciones", "cCombo.SetCaseList", {"Name": combo["id"], "CNameType": _enum("eCNameType", "LoadCase"),
                 "CName": factor["caso"], "SF": factor["factor"]}, f"$.combinaciones.{combo['id']}")
    b.op("analisis", "cAnalyze.SetRunCaseFlag", {"Name": "", "Run": False, "All": True}, "$.analisis",
         descripcion="Desmarca todos los casos de la plantilla; no ejecuta análisis.")
    for caso in config["analisis"]["casos_ejecutar"]:
        b.op("analisis", "cAnalyze.SetRunCaseFlag", {"Name": caso, "Run": True, "All": False}, "$.analisis.casos_ejecutar")

    # 7. Guardado en destino nuevo.
    b.op("guardado", "cFile.Save", {"FileName": opciones["destino_guardado"]}, "opciones.destino_guardado",
         descripcion="El ejecutor exige que el destino no exista antes de llamar.")

    datos = {
        "contrato": CONTRATO_PLAN, "version_contrato": VERSION_PLAN,
        "estado": "plan_no_ejecutado", "ejecutado": False, "aprueba_modelo": False,
        "certifica_seguridad_estructural": False,
        "aviso": ("Plan declarativo de llamadas a la API. No es una ejecución, no aprueba el modelo ni sus resultados "
                  "y no certifica seguridad estructural. Debe aplicarse solo sobre una copia verificada de la plantilla."),
        "origen": {
            "configuracion_id": config["id"], "caso": config["caso"], "datos_sinteticos": config["datos_sinteticos"],
            "huella_configuracion": resultado.huella_contenido,
            "geometria": {"version_id": origen["version_id"], "sha256_geometria": origen["sha256_geometria"],
                          "huella_contenido": origen["huella_contenido"]},
            "plantilla": {k: config["plantilla"][k] for k in ("id", "version", "sha256")},
        },
        "comprobacion": {"apto_para_adaptador": True, "geometria_comprobada": resultado.geometria_comprobada,
                         "ejecutable_en_etabs": False},
        "unidades_etabs": UNIDADES_ETABS,
        "api": {"dll": str(DLL_ETABS), "version_archivo_verificada": VERSION_DLL_VERIFICADA,
                "verificacion": "Firmas y enumeraciones de FIRMAS/ENUMS comprobadas por reflexión (verificar_firmas_dll)."},
        "opciones": opciones,
        # Solo con formulación por sección (R241): el modo global conserva byte a byte los planes históricos,
        # que la revisión del modelo regenera y compara.
        **({"idealizacion_losas": idealizacion_losas(config, opciones)} if isinstance(opciones.get("tipo_shell_losa"), dict) else {}),
        "precondiciones": [
            f"Abrir con adaptador_etabs.abrir_copia_plantilla una COPIA cuyo SHA256 sea {config['plantilla']['sha256']}.",
            "La copia no contiene puntos, frames ni muros, y no usa los nombres que el plan crea (fase verificacion).",
            "Cada operación se ejecuta en orden; ante un retorno distinto del esperado, una salida distinta de "
            "debe_ser o un nombre ya existente, el ejecutor se detiene y descarta la copia (sin reparaciones).",
            "El destino de guardado no existe.",
        ] + ([
            "Las tablas y campos editados (TABLAS_EDITABLES, con los esquemas observados en ETABS 21.1) se comprueban "
            "con GetAllFieldsInTable antes de mutar: existencia, importabilidad y textos nombrados en la descripción. "
            "Solo se escriben columnas importables; ApplyEditedTables debe terminar sin errores fatales, errores ni "
            "advertencias, y cada efecto se relee (tabla y getters OAPI) antes de continuar.",
        ] if dinamico else []),
        "constantes_adaptador": CONSTANTES_ADAPTADOR + (CONSTANTES_DINAMICAS if dinamico else []),
        "pendientes": [{"capacidad": k, "motivo": v} for k, v in PENDIENTES.items()],
        "no_aplicados_por_api": {
            "sitio": "Descripción y parámetros del sitio se conservan en la configuración; ninguna llamada estática los usa.",
            "fuentes_hipotesis": "Trazabilidad documental; no tienen equivalente en la API.",
            "combinaciones_resultados": list(config["analisis"]["combinaciones_resultados"]),
            "cargas_sin_efecto": sin_efecto,
        },
        "mapeo_ids": {
            "niveles": {niveles[0]["id"]: NOMBRE_BASE_ETABS, **{n["id"]: n["id"] for n in pisos}},
            "puntos": {pid: pid for pid in puntos}, "frames": {f["id"]: f["id"] for f in config["frames"]},
            "muros": {mid: mid for mid in sorted(asign_muros)},
            "materiales": {m["id"]: m["id"] for m in config["materiales"]},
            "secciones": {s["id"]: s["id"] for s in config["secciones"]},
            "patrones": {p["id"]: p["id"] for p in config["patrones"]},
            "casos": {c["id"]: c["id"] for c in config["casos"]},
            "combinaciones": {c["id"]: c["id"] for c in config["combinaciones"]},
            "diafragmas": {d["id"]: d["id"] for d in config["diafragmas"]},
            **({"funciones": {e["id"]: e["id"] for e in espectros}} if espectros else {}),
        },
        "operaciones": b.operaciones,
        "resumen": {fase: sum(1 for o in b.operaciones if o["fase"] == fase)
                    for fase in dict.fromkeys(o["fase"] for o in b.operaciones)},
    }
    if sup is not None:
        _datos_superficies(datos, resultado, sup)
        if config["version_contrato"] == me.VERSION_ABERTURAS:
            _datos_aberturas(datos, config, sup)
    auxiliares = _niveles_auxiliares(vg)
    if auxiliares:   # solo con cotas auxiliares declaradas: los planes existentes conservan contenido y vigencia
        datos["niveles_auxiliares"] = [{"id": n["id"], "cota": n["cota"], "story_etabs": None,
                                        "nota": "cota auxiliar declarada: sin Story, diafragma ni altura sísmica"} for n in auxiliares]
    datos["huella_plan"] = huella_plan(datos)
    problemas = validar_plan(datos) if sup is None else (validar_plan_aberturas(datos) if config["version_contrato"] == me.VERSION_ABERTURAS else validar_plan_superficies(datos))
    if problemas:
        raise AssertionError("El plan generado no supera su propia validación: " + "; ".join(problemas))
    return PlanOperaciones(datos)


# -- superficies (plan 0.2 de desarrollo) --------------------------------------

def _validar_opciones_superficies(opciones: dict) -> dict:
    permitidas = {"destino_guardado", "tipo_shell_muro", "tipo_shell_losa", "gravedad_programa_m_s2", "parametros_modales",
                  "amortiguamiento_funciones", "excentricidad_espectral", "respuesta_rigida_espectral"}
    sobrantes = set(opciones) - permitidas
    if sobrantes:
        raise ErrorPlan("Opciones no admitidas: " + ", ".join(sorted(sobrantes)))
    destino = opciones.get("destino_guardado")
    if not isinstance(destino, str) or not Path(destino).is_absolute() or Path(destino).suffix.lower() != ".edb":
        raise ErrorPlan("'destino_guardado' debe ser una ruta absoluta .edb (el ejecutor exigirá que no exista).")
    g = opciones.get("gravedad_programa_m_s2")
    if g is not None and (isinstance(g, bool) or not isinstance(g, (int, float)) or not math.isfinite(g) or g <= 0):
        raise ErrorPlan("'gravedad_programa_m_s2' debe ser un número positivo.")
    return dict(opciones)


def _tipo_losa(opciones: dict, seccion: str) -> str:
    """Formulación de la sección: global (texto) o elegida por sección (R241)."""
    valor = opciones["tipo_shell_losa"]
    return valor if isinstance(valor, str) else valor[seccion]["tipo"]


def _validar_losas_por_seccion(config: dict, valor: dict) -> None:
    """Mapa {sección: {tipo, funcion, justificacion}} que cubre exactamente todas las secciones de losa.

    La función estructural se DECLARA (no se deduce de que el polígono sea horizontal). Una membrana no resiste
    flexión fuera del plano: no se admite en fondos ni tapas de depósito sometidos a presión normal.
    """
    losas = {s["id"] for s in config["secciones"] if s["tipo"] in ("shell_losa_homogenea",) + TIPOS_ALIGERADOS}
    if set(valor) != losas:
        raise ErrorPlan("'tipo_shell_losa' por sección debe cubrir exactamente las secciones de losa: "
                        f"faltan {sorted(losas - set(valor))}, sobran {sorted(set(valor) - losas)}.")
    for sid, d in sorted(valor.items()):
        if not isinstance(d, dict) or set(d) != {"tipo", "funcion", "justificacion"}:
            raise ErrorPlan(f"'tipo_shell_losa.{sid}' requiere exactamente tipo, funcion y justificacion.")
        if d["tipo"] not in TIPOS_SHELL_LOSA or d["funcion"] not in FUNCIONES_LOSA:
            raise ErrorPlan(f"'tipo_shell_losa.{sid}': tipo en {TIPOS_SHELL_LOSA} y funcion en {FUNCIONES_LOSA}.")
        if not isinstance(d["justificacion"], str) or not d["justificacion"].strip():
            raise ErrorPlan(f"'tipo_shell_losa.{sid}': la justificación es obligatoria.")
        if d["funcion"] in ("fondo_deposito", "tapa_deposito") and d["tipo"] == "Membrane":
            raise ErrorPlan(f"'tipo_shell_losa.{sid}': una membrana no resiste la presión normal de un {d['funcion']}; "
                            "use ShellThin o ShellThick.")


def idealizacion_losas(config: dict, opciones: dict) -> list[dict]:
    """Registro trazable de la formulación de cada sección de losa y su función; avisos de E.030 30.8."""
    salida = []
    for sec in config["secciones"]:
        if sec["tipo"] not in ("shell_losa_homogenea",) + TIPOS_ALIGERADOS or "tipo_shell_losa" not in opciones:
            continue
        valor = opciones["tipo_shell_losa"]
        d = {"tipo": valor, "funcion": "no_declarada", "justificacion": "opción global (una sola formulación para todas)"} \
            if isinstance(valor, str) else valor[sec["id"]]
        item = {"seccion": sec["id"], **d}
        if d["funcion"] == "piso" and d["tipo"] != "Membrane":
            item["aviso"] = ("E.030 art. 30.8 (RM 183-2026): en el modelo sísmico se excluye la rigidez fuera del plano de "
                             "las losas de piso; la elección distinta de Membrane queda justificada por el revisor, no evaluada.")
        if isinstance(valor, str):
            item["aviso"] = "Formulación global: no distingue pisos de fondos/tapas de depósito (R241)."
        salida.append(item)
    return salida


def _aplicabilidad_shell(config: dict, opciones: dict) -> None:
    """Formulación explícita solo para los tipos de sección presentes; nada sobra ni falta."""
    tipos = {s["tipo"] for s in config["secciones"]}
    if tipos.intersection(TIPOS_ALIGERADOS):
        tipos.add("shell_losa_homogenea")
    if isinstance(opciones.get("tipo_shell_losa"), dict) and "shell_losa_homogenea" in tipos:
        _validar_losas_por_seccion(config, opciones["tipo_shell_losa"])
    for clave, tipo, admitidos in (("tipo_shell_muro", "shell_muro", TIPOS_SHELL_MURO),
                                   ("tipo_shell_losa", "shell_losa_homogenea", TIPOS_SHELL_LOSA)):
        if clave == "tipo_shell_losa" and isinstance(opciones.get(clave), dict) and tipo in tipos:
            continue
        if tipo in tipos and opciones.get(clave) not in admitidos:
            raise ErrorPlan(f"'{clave}' es obligatorio y explícito para secciones {tipo}: " + ", ".join(admitidos) + ".")
        if tipo not in tipos and clave in opciones:
            raise ErrorPlan(f"'{clave}' no aplica: la configuración no declara secciones {tipo}.")


def _contexto_superficies(config: dict, vg: Any) -> dict:
    g = vg.geometria_m
    niveles = {n["id"]: n["cota"] for n in g["niveles"]}
    nodos = {n["id"]: n for n in g["nodos"]}
    vertices = {v["id"]: v for v in g["vertices"]}
    coordenadas = {}
    for p in config["puntos"]:
        if "vertice_geometria" in p:
            v = vertices[p["vertice_geometria"]]
            coordenadas[p["id"]] = (v["x"], v["y"], v["z"])
        else:
            n = nodos[p["nodo_geometria"]]
            coordenadas[p["id"]] = (n["x"], n["y"], niveles[p["nivel_geometria"]])
    punto_de_vertice = {p["vertice_geometria"]: p["id"] for p in config["puntos"] if "vertice_geometria" in p}
    punto_de_vertice.update({c["vertice_geometria"]: c["punto"] for c in config["vertices_compartidos"]})
    superficies = {s["id"]: s for s in g["superficies"]}
    asignaciones = {a["objetivo"]: a["seccion"] for a in config["asignaciones_superficies"]}
    aligerados = {s["id"]: {"seccion_declarada": copy.deepcopy(s), "peso_propio": "Material y propiedad ETABS; sin relleno ni carga adicional inferidos.",
                            "unidad_dimensiones": "m", "unidad_peso_material": "kN/m3",
                            "peso_material_kN_m3": next(m["peso_kN_m3"] for m in config["materiales"] if m["id"] == s["material"])}
                  for s in config["secciones"] if s["tipo"] in TIPOS_ALIGERADOS}
    return {"aligerados": aligerados, "coordenadas": coordenadas, "asignaciones": asignaciones, "superficies": superficies,
            "derivados": vg.derivados_m["superficies"],
            "contornos": {sid: [punto_de_vertice[v] for v in superficies[sid]["vertices"]] for sid in asignaciones}}


def _motivos_superficies(sup: dict, niveles: list[dict], auxiliares: list[dict] = ()) -> list[str]:
    """Puntos fuera de [base, último piso] solo se admiten dentro de la envolvente de cotas auxiliares DECLARADAS en la
    geometría versionada (ETABS los asocia a Base/último piso sin crear plantas, ensayo257); no se crean pisos ficticios."""
    motivos = []
    if niveles:
        cotas = [n["cota"] for n in niveles] + [n["cota"] for n in auxiliares]
        base, tope = min(cotas), max(cotas)
        for pid, (_, _, z) in sorted(sup["coordenadas"].items()):
            if not base <= z <= tope:
                motivos.append(f"Punto '{pid}' a cota {z} fuera de [{base}, {tope}] (pisos y cotas auxiliares declaradas); "
                               "no se crean pisos ficticios.")
    for sid in sorted(sup["asignaciones"]):
        puntos = [sup["coordenadas"][p] for p in sup["contornos"][sid]]
        derivado = sup["derivados"][sid]
        normal, eps = derivado["normal_unitaria"], derivado["epsilon_relativo_computacional"]
        for i in range(len(puntos)):
            a, b, c = puntos[i - 1], puntos[i], puntos[(i + 1) % len(puntos)]
            u = [b[k] - a[k] for k in range(3)]
            w = [c[k] - b[k] for k in range(3)]
            giro = sum(normal[k] * (u[(k + 1) % 3] * w[(k + 2) % 3] - u[(k + 2) % 3] * w[(k + 1) % 3]) for k in range(3))
            if giro < -eps * math.hypot(*u) * math.hypot(*w):
                motivos.append(f"Superficie '{sid}' cóncava: " + PENDIENTES_SUPERFICIES["concavidad"])
                break
    return motivos


def generar_plan_superficies(raiz: Path, configuracion: Any, **opciones: Any) -> PlanOperaciones:
    """Plan 0.2 de DESARROLLO desde una configuración 0.2 con plan de desarrollo admitido. No ejecutable.

    Exige consistencia, aprobación de configuración, evidencia geométrica comprobada y aprobación
    geométrica por huella; los bloqueos de integración permanecen y quedan declarados en el plan.
    """
    opciones = _validar_opciones_superficies(opciones)
    config = copy.deepcopy(configuracion)
    if not isinstance(config, dict) or config.get("version_contrato") != me.VERSION_SUPERFICIES:
        raise ErrorPlan("generar_plan_superficies solo compila configuraciones 0.2.0; use generar_plan para 0.1.")
    resultado = me.comprobar_configuracion(Path(raiz), config)
    if not resultado.apto_para_plan_desarrollo:
        admitidos = {me.BLOQUEO_SUPERFICIES, me.BLOQUEO_INTEGRACION}
        raise ErrorPlanRechazado("La configuración 0.2 no admite un plan de desarrollo; no se genera plan.",
                                 list(resultado.errores) + [b for b in resultado.bloqueos if b not in admitidos]
                                 or ["apto_para_plan_desarrollo es falso."])
    _aplicabilidad_shell(config, opciones)
    vg = _geometria_vigente(Path(raiz), config)
    _validar_opciones_dinamicas(config, opciones)
    motivos = _motivos_no_soportados(config, opciones)
    niveles = _niveles_piso(vg)
    motivos += _motivos_niveles(niveles)
    sup = _contexto_superficies(config, vg)
    motivos += _motivos_superficies(sup, niveles, _niveles_auxiliares(vg))
    if motivos:
        raise ErrorPlanRechazado("Características no soportadas por el transporte de superficies; se rechaza el plan completo.",
                                 motivos)
    return _compilar(config, resultado, vg, niveles, opciones, sup)


def generar_plan_aberturas(raiz: Path, configuracion: Any, **opciones: Any) -> PlanOperaciones:
    """Plan 0.3 no ejecutable con cobertura integral de huecos; nunca delega a despacho0.2."""
    opciones = _validar_opciones_superficies(opciones)
    config = copy.deepcopy(configuracion)
    if not isinstance(config, dict) or config.get("version_contrato") != me.VERSION_ABERTURAS:
        raise ErrorPlan("generar_plan_aberturas exige configuración0.3.0")
    resultado = me.comprobar_configuracion(Path(raiz), config)
    if not resultado.apto_para_plan_desarrollo:
        raise ErrorPlanRechazado("Configuración0.3 sin aptitud de desarrollo", list(resultado.errores) + list(resultado.bloqueos))
    _aplicabilidad_shell(config, opciones)
    vg = _geometria_vigente(Path(raiz), config)
    _validar_opciones_dinamicas(config, opciones)
    niveles = _niveles_piso(vg)
    sup = _contexto_superficies(config, vg)
    por_vertice = {p["vertice_geometria"]: p["id"] for p in config["puntos"] if "vertice_geometria" in p}
    por_vertice.update({c["vertice_geometria"]: c["punto"] for c in config["vertices_compartidos"]})
    sup["aberturas"] = {a["id"]: copy.deepcopy(a) for a in vg.geometria_m["aberturas"]}
    sup["contornos_aberturas"] = {a["id"]: [por_vertice[v] for v in a["vertices"]] for a in vg.geometria_m["aberturas"]}
    sup["derivados_aberturas"] = copy.deepcopy(vg.derivados_m["aberturas"])
    aux = _niveles_auxiliares(vg)
    motivos = _motivos_no_soportados(config, opciones) + _motivos_niveles(niveles) + _motivos_superficies(sup, niveles, aux)
    motivos += _motivos_superficies({"coordenadas": sup["coordenadas"], "asignaciones": sup["aberturas"], "contornos": sup["contornos_aberturas"], "derivados": sup["derivados_aberturas"]}, niveles, aux)
    nombres = [_nombre_abertura(a) for a in sup["aberturas"]]
    areas_host = set(sup["asignaciones"]) | {a["objetivo"] for a in config["asignaciones_muros"]}
    if len(set(nombres)) != len(nombres) or set(nombres) & areas_host:
        motivos.append("Colisión entre nombres explícitos de host y abertura; no se renombra silenciosamente")
    if motivos:
        raise ErrorPlanRechazado("Transporte0.3 rechazado íntegramente", motivos)
    return _compilar(config, resultado, vg, niveles, opciones, sup)


def _nombre_abertura(ident):
    return "ABERTURA." + ident


def _aberturas(b, sup):
    for sid in sorted(sup["asignaciones"]):
        b.op("superficies", "cAreaObj.SetOpening", {"Name": _ref("superficie", sid), "IsOpening": False, "ItemType": _enum("eItemType", "Objects")}, f"geometria.superficies.{sid}")
        b.op("comprobacion_objetos", "cAreaObj.GetOpening", {"Name": _ref("superficie", sid), "IsOpening": True}, f"geometria.superficies.{sid}", releer={"IsOpening": False})
    for aid, abertura in sorted(sup["aberturas"].items()):
        puntos = sup["contornos_aberturas"][aid]
        nombre = _nombre_abertura(aid)
        origen = f"geometria.aberturas.{aid}"
        b.op("aberturas", "cAreaObj.AddByPoint", {"NumberPoints": len(puntos), "Point": [_ref("punto", p) for p in puntos], "Name": "", "PropName": "None", "UserName": nombre}, origen, salidas={"Name": (f"abertura:{aid}", nombre)})
        b.op("aberturas", "cAreaObj.SetOpening", {"Name": _ref("abertura", aid), "IsOpening": True, "ItemType": _enum("eItemType", "Objects")}, origen)
        b.op("comprobacion_objetos", "cAreaObj.GetOpening", {"Name": _ref("abertura", aid), "IsOpening": False}, origen, releer={"IsOpening": True})
        b.op("comprobacion_objetos", "cAreaObj.GetPoints", {"Name": _ref("abertura", aid), "NumberPoints": 0, "Point": []}, origen, releer={"NumberPoints": len(puntos), "Point": puntos})
        b.op("comprobacion_objetos", "cAreaObj.GetProperty", {"Name": _ref("abertura", aid), "PropName": ""}, origen, releer={"PropName": "None"})


def _superficies(b: _Constructor, config: dict, sup: dict, asign_muros: dict, muros: dict, par_punto: dict,
                 opciones: dict) -> None:
    """AreaObj por contorno exacto y relectura de coordenadas, contornos y propiedades creadas."""
    for sid in sorted(sup["asignaciones"]):
        contorno = sup["contornos"][sid]
        b.op("superficies", "cAreaObj.AddByPoint", {"NumberPoints": len(contorno), "Point": [_ref("punto", p) for p in contorno],
             "Name": "", "PropName": sup["asignaciones"][sid], "UserName": sid}, f"geometria.superficies.{sid}",
             salidas={"Name": (f"superficie:{sid}", sid)},
             descripcion="Contorno exacto en el orden de la geometría 0.2; sin triangular, reordenar ni fusionar.")
        sec = next(s for s in config["secciones"] if s["id"] == sup["asignaciones"][sid])
        if sec["tipo"] in TIPOS_ALIGERADOS:
            ang = sec["dimensiones"]["angulo_ejes_locales_grados"]
            b.op("superficies", "cAreaObj.SetLocalAxes", {"Name": _ref("superficie", sid), "Ang": ang, "ItemType": _enum("eItemType", "Objects")}, f"$.secciones.{sec['id']}")
            b.op("comprobacion_objetos", "cAreaObj.GetLocalAxes", {"Name": _ref("superficie", sid), "Ang": 0.0, "Advanced": False}, f"$.secciones.{sec['id']}", releer={"Ang": ang, "Advanced": False})
    if config["version_contrato"] == me.VERSION_ABERTURAS:
        _aberturas(b, sup)
    for p in config["puntos"]:
        x, y, z = sup["coordenadas"][p["id"]]
        b.op("comprobacion_objetos", "cPointObj.GetCoordCartesian", {"Name": _ref("punto", p["id"]), "X": 0.0, "Y": 0.0,
             "Z": 0.0, "CSys": "Global"}, f"$.puntos.{p['id']}", releer={"X": x, "Y": y, "Z": z})
    areas = []
    for mid in sorted(asign_muros):
        muro = muros[mid]
        esquinas = [par_punto[(muro["nodo_inicio"], muro["nivel_inferior"])], par_punto[(muro["nodo_fin"], muro["nivel_inferior"])],
                    par_punto[(muro["nodo_fin"], muro["nivel_superior"])], par_punto[(muro["nodo_inicio"], muro["nivel_superior"])]]
        areas.append(("muro", mid, esquinas, asign_muros[mid], f"geometria.muros.{mid}"))
    areas += [("superficie", sid, sup["contornos"][sid], sup["asignaciones"][sid], f"geometria.superficies.{sid}")
              for sid in sorted(sup["asignaciones"])]
    for clase, ident, contorno, propiedad, origen in areas:
        b.op("comprobacion_objetos", "cAreaObj.GetPoints", {"Name": _ref(clase, ident), "NumberPoints": 0, "Point": []}, origen,
             releer={"NumberPoints": len(contorno), "Point": list(contorno)})
        b.op("comprobacion_objetos", "cAreaObj.GetProperty", {"Name": _ref(clase, ident), "PropName": ""}, origen,
             releer={"PropName": propiedad})
    for sec in config["secciones"]:
        comunes = {"MatProp": "", "Thickness": 0.0, "color": 0, "notes": "", "GUID": ""}
        esperado = {"MatProp": sec["material"], "Thickness": sec["dimensiones"].get("espesor_m", sec["dimensiones"].get("capa_m"))}
        if sec["tipo"] in ("shell_losa_homogenea",) + TIPOS_ALIGERADOS:
            if sec["tipo"] in TIPOS_ALIGERADOS or isinstance(opciones["tipo_shell_losa"], dict):
                # Con formulación por sección la relectura COMPARA el tipo, para detectar cambios entre secciones.
                esperado.update(SlabType=_enum("eSlabType", _clase_losa(sec)), ShellType=_enum("eShellType", _tipo_losa(opciones, sec["id"])))
            b.op("comprobacion_objetos", "cPropArea.GetSlab", {"Name": sec["id"], "SlabType": _enum("eSlabType", _clase_losa(sec)),
                 "ShellType": _enum("eShellType", _tipo_losa(opciones, sec["id"])), **comunes}, f"$.secciones.{sec['id']}",
                 releer=esperado, registrar=["SlabType", "ShellType"],
                 descripcion=("Material, espesor y formulación por sección se comparan (R241)." if isinstance(opciones["tipo_shell_losa"], dict)
                              else "Los enumerados se registran en la traza; material y espesor se comparan."))
            if sec["tipo"] in TIPOS_ALIGERADOS:
                valores = _parametros_aligerados(sec)
                b.op("comprobacion_objetos", "cPropArea.GetSlab" + _clase_losa(sec), {"Name": sec["id"], **{k: 0 for k in valores}}, f"$.secciones.{sec['id']}", releer=valores)
        elif sec["tipo"] == "shell_muro":
            b.op("comprobacion_objetos", "cPropArea.GetWall", {"Name": sec["id"],
                 "WallPropType": _enum("eWallPropType", "Specified"), "ShellType": _enum("eShellType", opciones["tipo_shell_muro"]),
                 **comunes}, f"$.secciones.{sec['id']}", releer=esperado, registrar=["WallPropType", "ShellType"],
                 descripcion="Los enumerados se registran en la traza; material y espesor se comparan.")


def _datos_superficies(datos: dict, resultado: Any, sup: dict) -> None:
    datos.update(version_contrato=VERSION_PLAN_SUPERFICIES, estado=ESTADO_PLAN_SUPERFICIES, ejecutable=False)
    datos["aviso"] = ("Plan de DESARROLLO 0.2 de superficies: no ejecutable. El ejecutor solo acepta planes 0.1 y la "
                      "configuración 0.2 conserva sus bloqueos de integración. No aprueba el modelo ni certifica seguridad "
                      "estructural; shell_losa_homogenea no representa una losa aligerada.")
    datos["comprobacion"] = {"apto_para_adaptador": False, "apto_para_plan_desarrollo": True,
                             "geometria_comprobada": resultado.geometria_comprobada,
                             "geometria_aprobada_por_huella": resultado.geometria_aprobada_por_huella,
                             "ejecutable_en_etabs": False, "bloqueos": list(resultado.bloqueos)}
    datos["precondiciones"].append("Plan de desarrollo: no se entrega al ejecutor hasta que Codex revise e integre el "
                                   "recorrido completo; entonces se exigirá también la relectura de comprobacion_objetos.")
    datos["constantes_adaptador"] = datos["constantes_adaptador"] + CONSTANTES_SUPERFICIES
    datos["pendientes"] = datos["pendientes"] + [{"capacidad": k, "motivo": v} for k, v in PENDIENTES_SUPERFICIES.items()]
    datos["integracion_pendiente"] = list(INTEGRACION_PENDIENTE)
    datos["mapeo_ids"]["superficies"] = {sid: sid for sid in sorted(sup["asignaciones"])}
    if sup["aligerados"]:
        datos["trazabilidad_aligerados"] = copy.deepcopy(sup["aligerados"])
    datos["trazabilidad_superficies"] = {
        sid: {"vertices_geometria": list(sup["superficies"][sid]["vertices"]), "puntos": list(sup["contornos"][sid]),
              "papel_geometrico": sup["superficies"][sid]["papel_geometrico"],
              "procedencia": copy.deepcopy(sup["superficies"][sid]["procedencia"]),
              "seccion": sup["asignaciones"][sid], "area_m2": sup["derivados"][sid]["area_m2"],
              "normal_unitaria": list(sup["derivados"][sid]["normal_unitaria"])}
        for sid in sorted(sup["asignaciones"])}


def _datos_aberturas(datos, config, sup):
    datos["version_contrato"] = VERSION_PLAN_ABERTURAS
    datos["aviso"] = "Plan de desarrollo0.3 no ejecutable. Huecos nativos declarados; efecto físico, malla, cargas netas y reapertura pendientes de verificación real."
    datos["mapeo_ids"]["aberturas"] = {a: _nombre_abertura(a) for a in sorted(sup["aberturas"])}
    datos["cobertura_aberturas"] = sorted(sup["aberturas"])
    datos["trazabilidad_aberturas"] = {a: {"nombre_etabs": _nombre_abertura(a), "superficie": h["superficie"], "vertices_geometria": list(h["vertices"]), "puntos": list(sup["contornos_aberturas"][a]), "procedencia": copy.deepcopy(h["procedencia"]), "area_m2": sup["derivados_aberturas"][a]["area_m2"], "propiedad": "None", "es_abertura": True} for a, h in sup["aberturas"].items()}
    for sid, traza in datos["trazabilidad_superficies"].items():
        d = sup["derivados"][sid]
        traza.update({k: copy.deepcopy(d[k]) for k in ("area_bruta_m2", "area_aberturas_m2", "area_neta_m2", "aberturas_ids")})
    datos["cargas_superficies_netas_declaradas"] = [{"id": c["id"], "superficie": c["objetivo"], "area_neta_m2": sup["derivados"][c["objetivo"]]["area_neta_m2"], "componentes_kN_m2": copy.deepcopy(c["componentes"]), "resultante_esperada_kN_no_observada": [v * sup["derivados"][c["objetivo"]]["area_neta_m2"] for v in c["componentes"]]} for c in config["cargas"] if c["objetivo_tipo"] == "superficie"]
    datos["integracion_pendiente"].append("Huecos: probar malla compatible y vaciado físico en modelo analítico, deducción única de peso/cargas por área neta y lectura independiente tras reapertura; paredes requieren partición/mallado para incorporar huecos según CSI.")


def validar_plan_aberturas(datos):
    if not isinstance(datos, dict) or datos.get("contrato") != CONTRATO_PLAN or datos.get("version_contrato") != VERSION_PLAN_ABERTURAS:
        return ["Contrato de plan de aberturas no admitido."]
    problemas = []
    if datos.get("estado") != ESTADO_PLAN_SUPERFICIES or datos.get("ejecutable") is not False or datos.get("comprobacion", {}).get("ejecutable_en_etabs") is not False:
        problemas.append("Plan0.3 debe ser desarrollo no ejecutable")
    trazas = datos.get("trazabilidad_aberturas")
    ids = datos.get("cobertura_aberturas")
    if not isinstance(trazas, dict) or not isinstance(ids, list) or sorted(trazas) != ids:
        return problemas + ["Cobertura de aberturas ausente o inconsistente"]
    for aid, traza in trazas.items():
        origen = f"geometria.aberturas.{aid}"
        ops = [op for op in datos.get("operaciones", []) if isinstance(op, dict) and op.get("origen") == origen]
        # Las mismas guardas de firma/huella/tipo se aplican en _problemas_plan.
        metodos = [op.get("metodo") for op in ops]
        requeridos = ["cAreaObj.AddByPoint", "cAreaObj.SetOpening", "cAreaObj.GetOpening", "cAreaObj.GetPoints", "cAreaObj.GetProperty"]
        if metodos != requeridos:
            problemas.append(f"Abertura {aid}: operaciones/lecturas incompletas")
            continue
        if not isinstance(traza, dict) or traza.get("superficie") not in datos.get("trazabilidad_superficies", {}) or traza.get("propiedad") != "None" or traza.get("es_abertura") is not True:
            problemas.append(f"Abertura {aid}: traza o host inválidos")
            continue
        argumentos = [{a["nombre"]: a["valor"] for a in op.get("argumentos", []) if isinstance(a, dict) and "nombre" in a and "valor" in a} for op in ops]
        nombre = _nombre_abertura(aid)
        ref = _ref("abertura", aid)
        puntos = traza.get("puntos", [])
        if not isinstance(puntos, list) or len(puntos) < 3 or argumentos[0].get("PropName") != "None" or argumentos[0].get("UserName") != nombre or argumentos[0].get("NumberPoints") != len(puntos) or argumentos[0].get("Point") != [_ref("punto", p) for p in puntos] or traza.get("nombre_etabs") != nombre:
            problemas.append(f"Abertura {aid}: contorno/null/nombre no corresponden")
        if argumentos[1].get("Name") != ref or argumentos[1].get("IsOpening") is not True:
            problemas.append(f"Abertura {aid}: falta designación void verdadera")
        for op, valores, esperado in zip(ops[2:], argumentos[2:], ({"IsOpening": True}, {"NumberPoints": len(puntos), "Point": puntos}, {"PropName": "None"})):
            releido = {v.get("parametro"): v.get("esperado") for v in op.get("verificar_valores", []) if isinstance(v, dict)}
            if valores.get("Name") != ref or releido != esperado:
                problemas.append(f"Abertura {aid}: lectura de efecto no corresponde")
    for op in datos.get("operaciones", []):
        if isinstance(op, dict) and op.get("metodo") == "cAreaObj.SetLoadUniform":
            if any(isinstance(a, dict) and isinstance(a.get("valor"), dict) and str(a["valor"].get("ref", "")).startswith("abertura:") for a in op.get("argumentos", [])):
                problemas.append("Una abertura no admite carga de área")
    for sid in datos.get("trazabilidad_superficies", {}):
        host = [op for op in datos.get("operaciones", []) if isinstance(op, dict) and op.get("origen") == f"geometria.superficies.{sid}" and op.get("metodo") in ("cAreaObj.SetOpening", "cAreaObj.GetOpening")]
        if len(host) != 2 or host[0].get("metodo") != "cAreaObj.SetOpening" or host[1].get("metodo") != "cAreaObj.GetOpening":
            problemas.append(f"Host {sid}: designación/relectura no hueco ausente")
        elif next((a.get("valor") for a in host[0].get("argumentos", []) if a.get("nombre") == "IsOpening"), None) is not False or {v.get("parametro"): v.get("esperado") for v in host[1].get("verificar_valores", [])} != {"IsOpening": False}:
            problemas.append(f"Host {sid}: no debe designarse abertura")
    return problemas + _problemas_plan(datos)


# -- malla triangulada (plan 0.4 ejecutable) ------------------------------------

def _nombre_carga_malla(carga_id: str, objeto: str) -> str:
    return f"{carga_id}@{objeto}"


def _centroide_neto(vertices: list, huecos: list, normal: list) -> tuple[float, list[float]]:
    """Área neta y centroide del polígono fuente (exterior menos huecos), independiente de la malla."""
    def poligono(q):
        area, momento = 0.0, [0.0, 0.0, 0.0]
        for i in range(1, len(q) - 1):
            a, b, c = q[0], q[i], q[i + 1]
            u = [b[k] - a[k] for k in range(3)]
            w = [c[k] - a[k] for k in range(3)]
            cruz = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
            s = sum(cruz[k] * normal[k] for k in range(3)) / 2
            area += s
            for k in range(3):
                momento[k] += s * (a[k] + b[k] + c[k]) / 3
        return abs(area), [m if area >= 0 else -m for m in momento]
    area, momento = poligono(vertices)
    for h in huecos:
        ah, mh = poligono(h)
        area -= ah
        momento = [momento[k] - mh[k] for k in range(3)]
    return area, [m / area for m in momento]


def _error_relativo(a: float, b: float) -> float:
    return abs(a - b) / max(1.0, abs(a), abs(b))


def _expandir_malla(config: dict, prep: dict, vg: Any) -> tuple[dict, dict, dict]:
    """Configuración interna equivalente: triángulos en lugar de hosts, frames subdivididos y cargas copiadas.

    Nunca crea el host completo ni Opening; ningún triángulo cubre un hueco (lo garantiza la partición reproducida).
    """
    exp = copy.deepcopy(config)
    nodos = {n["csi"]: n for n in prep["nodos"]}
    derivados = {n["nodo"]: n for n in config["nodos_derivados"]}
    exp["puntos"] = config["puntos"] + [{"id": n} for n in prep["nodos_derivados"]]
    sub = {r["frame"]: r for r in prep["frames_subdivision_requerida"]}
    frames, asign = [], {a["objetivo"]: a for a in config["asignaciones_frames"]}
    asign_exp = []
    for f in config["frames"]:
        if f["id"] in sub:
            nodos_f = sub[f["id"]]["nodos"]
            for k, nombre in enumerate(sub[f["id"]]["subframes"]):
                frames.append({"id": nombre, "inicio": nodos_f[k], "fin": nodos_f[k + 1], "tipo": f["tipo"], "fuente": f["fuente"]})
                asign_exp.append({**asign[f["id"]], "objetivo": nombre})
        else:
            frames.append(f)
            asign_exp.append(asign[f["id"]])
    exp["frames"], exp["asignaciones_frames"] = frames, asign_exp
    if "insercion_frames" in config:
        exp["insercion_frames"] = [{**i, "frame": nombre} for i in config["insercion_frames"]
                                   for nombre in (sub[i["frame"]]["subframes"] if i["frame"] in sub else [i["frame"]])]
    por_host = {}
    for t in prep["triangulos"]:
        por_host.setdefault(t["host"], []).append(t["csi"])
    exp["asignaciones_superficies"] = [{"objetivo": t["csi"], "seccion": t["seccion"], "fuente": a["fuente"]}
                                       for a in config["asignaciones_superficies"] for t in prep["triangulos"] if t["host"] == a["objetivo"]]
    cargas = []
    for c in config["cargas"]:
        if c["objetivo_tipo"] == "superficie":
            cargas += [{**c, "id": _nombre_carga_malla(c["id"], t), "objetivo": t} for t in por_host[c["objetivo"]]]
        elif c["objetivo_tipo"] == "frame" and c["objetivo"] in sub:
            cargas += [{**c, "id": _nombre_carga_malla(c["id"], s), "objetivo": s} for s in sub[c["objetivo"]]["subframes"]]
        else:
            cargas.append(c)
    exp["cargas"] = cargas
    exp["apoyos"] = config["apoyos"] + [{"punto": n, "restricciones": list(d["restricciones"]), "fuente": d["fuente"]}
                                        for n, d in sorted(derivados.items()) if any(d["restricciones"])]
    exp["diafragmas"] = [{**d, "puntos": list(d["puntos"]) + [n for n, x in sorted(derivados.items()) if x["diafragma"] == d["id"]]}
                         for d in config["diafragmas"]]
    exp["sin_diafragma"] = config["sin_diafragma"] + [{"punto": n, "motivo": x["motivo_sin_diafragma"], "fuente": x["fuente"]}
                                                      for n, x in sorted(derivados.items()) if x["diafragma"] is None]
    coordenadas = {}
    g = vg.geometria_m
    niveles = {n["id"]: n["cota"] for n in g["niveles"]}
    nodos_g = {n["id"]: n for n in g["nodos"]}
    vertices = {v["id"]: v for v in g["vertices"]}
    for p in config["puntos"]:
        if "vertice_geometria" in p:
            v = vertices[p["vertice_geometria"]]
            coordenadas[p["id"]] = (v["x"], v["y"], v["z"])
        else:
            n = nodos_g[p["nodo_geometria"]]
            coordenadas[p["id"]] = (n["x"], n["y"], niveles[p["nivel_geometria"]])
    for nombre in prep["nodos_derivados"]:
        coordenadas[nombre] = tuple(nodos[nombre]["xyz_m"])
    superficies = {s["id"]: s for s in g["superficies"]}
    derivados_sup = vg.derivados_m["superficies"]
    tri = {t["csi"]: t for t in prep["triangulos"]}
    sup = {
        "aligerados": {s["id"]: {"seccion_declarada": copy.deepcopy(s), "peso_propio": "Material y propiedad ETABS; sin relleno ni carga adicional inferidos.",
                                 "unidad_dimensiones": "m", "unidad_peso_material": "kN/m3",
                                 "peso_material_kN_m3": next(m["peso_kN_m3"] for m in config["materiales"] if m["id"] == s["material"])}
                       for s in config["secciones"] if s["tipo"] in TIPOS_ALIGERADOS},
        "coordenadas": coordenadas,
        "asignaciones": {t: x["seccion"] for t, x in tri.items()},
        "superficies": {t: {"vertices": list(x["nodos"]), "papel_geometrico": superficies[x["host"]]["papel_geometrico"],
                            "procedencia": copy.deepcopy(superficies[x["host"]]["procedencia"])} for t, x in tri.items()},
        "derivados": {t: {"area_m2": x["area_m2"], "normal_unitaria": list(derivados_sup[x["host"]]["normal_unitaria"]),
                          "epsilon_relativo_computacional": derivados_sup[x["host"]]["epsilon_relativo_computacional"]} for t, x in tri.items()},
        "contornos": {t: list(x["nodos"]) for t, x in tri.items()},
    }
    return exp, sup, por_host


def _conservacion_malla(config: dict, prep: dict, vg: Any, sup: dict, exp: dict) -> dict:
    """Prueba numérica (no observada en ETABS): fuerza y momento de cada carga y área de masa propia."""
    g = vg.geometria_m
    xyz_v = {v["id"]: [v["x"], v["y"], v["z"]] for v in g["vertices"]}
    der = vg.derivados_m["superficies"]
    tri = {t["csi"]: t for t in prep["triangulos"]}
    hosts = {}
    for h, info in prep["hosts"].items():
        s = next(x for x in g["superficies"] if x["id"] == h)
        huecos = [[xyz_v[v] for v in a["vertices"]] for a in g["aberturas"] if a["superficie"] == h]
        area, cen = _centroide_neto([xyz_v[v] for v in s["vertices"]], huecos, der[h]["normal_unitaria"])
        malla = math.fsum(tri[t]["area_m2"] for t in info["triangulos"])
        hosts[h] = {"area_neta_fuente_m2": der[h]["area_neta_m2"], "area_neta_poligono_m2": area, "centroide_fuente_m": cen,
                    "area_triangulos_m2": malla, "error_relativo_area": _error_relativo(malla, der[h]["area_neta_m2"])}
    cargas = []
    coords = sup["coordenadas"]
    for c in config["cargas"]:
        if c["objetivo_tipo"] == "superficie":
            partes = [x for x in exp["cargas"] if x["id"].startswith(c["id"] + "@")]
            h = hosts[c["objetivo"]]
            fuerza = [v * h["area_neta_fuente_m2"] for v in c["componentes"]]
            momento_ref = [h["centroide_fuente_m"][k] * h["area_neta_fuente_m2"] for k in range(3)]
            area_m = math.fsum(tri[x["objetivo"]]["area_m2"] for x in partes)
            primer = [math.fsum(tri[x["objetivo"]]["area_m2"] * tri[x["objetivo"]]["centroide_m"][k] for x in partes) for k in range(3)]
            fuerza_m = [v * area_m for v in c["componentes"]]
        elif c["objetivo_tipo"] == "frame" and any(x["id"].startswith(c["id"] + "@") for x in exp["cargas"]):
            partes = [x for x in exp["cargas"] if x["id"].startswith(c["id"] + "@")]
            f = next(x for x in config["frames"] if x["id"] == c["objetivo"])
            a, b = coords[f["inicio"]], coords[f["fin"]]
            largo = math.dist(a, b)
            fuerza = [v * largo for v in c["componentes"]]
            momento_ref = [largo * (a[k] + b[k]) / 2 for k in range(3)]
            subs = {x["id"]: x for x in exp["frames"]}
            tramos = [(coords[subs[x["objetivo"]]["inicio"]], coords[subs[x["objetivo"]]["fin"]]) for x in partes]
            area_m = math.fsum(math.dist(p, q) for p, q in tramos)
            primer = [math.fsum(math.dist(p, q) * (p[k] + q[k]) / 2 for p, q in tramos) for k in range(3)]
            fuerza_m = [v * area_m for v in c["componentes"]]
        else:
            continue
        # Momento de una fuerza uniforme w: M = r_c × F, con r_c el centroide (primer momento / medida).
        def mom(primer_momento, w):
            return [primer_momento[1] * w[2] - primer_momento[2] * w[1], primer_momento[2] * w[0] - primer_momento[0] * w[2],
                    primer_momento[0] * w[1] - primer_momento[1] * w[0]]
        m_ref, m_malla = mom(momento_ref, c["componentes"]), mom(primer, c["componentes"])
        errores = [_error_relativo(x, y) for x, y in zip(fuerza + m_ref, fuerza_m + m_malla)]
        cargas.append({"carga": c["id"], "objetivo_tipo": c["objetivo_tipo"], "objetivo": c["objetivo"], "partes": [x["objetivo"] for x in partes],
                       "intensidad_copiada": list(c["componentes"]), "fuerza_esperada_kN": fuerza, "fuerza_malla_kN": fuerza_m,
                       "momento_esperado_kNm": m_ref, "momento_malla_kNm": m_malla, "error_relativo_max": max(errores)})
    return {"tolerancia_relativa": TOLERANCIA_CONSERVACION, "hosts": hosts, "cargas": cargas,
            "masa_propia": "Peso propio por material/propiedad de cada triángulo; suma de áreas = área neta del host, sin host completo ni huecos.",
            "aviso": "Conservación calculada con la malla reproducida; no observada en ETABS ni con solver."}


def generar_plan_malla(raiz: Path, configuracion: Any, **opciones: Any) -> PlanOperaciones:
    """Plan 0.4 desde configuración 0.4 apta: partición+compatibilidad+triangulación reproducidas. Habilitación
    operativa del transporte; no aprueba ingeniería ni sustituye la verificación real en ETABS."""
    opciones = _validar_opciones_superficies(opciones)
    config = copy.deepcopy(configuracion)
    if not isinstance(config, dict) or config.get("version_contrato") not in (me.VERSION_MALLA, me.VERSION_LIQUIDOS):
        raise ErrorPlan("generar_plan_malla exige configuración 0.4.0 o 0.5.0.")
    resultado = me.comprobar_configuracion(Path(raiz), config)
    if not resultado.apto_para_adaptador:
        raise ErrorPlanRechazado("La configuración 0.4 no es apta; no se genera plan.",
                                 list(resultado.errores) + [f"faltante {f['ruta']}" for f in resultado.faltantes]
                                 + [b for b in resultado.bloqueos if b != me.BLOQUEO_GEOMETRIA_ABERTURAS] or ["apto_para_adaptador es falso."])
    _aplicabilidad_shell(config, opciones)
    vg = _geometria_vigente(Path(raiz), config)
    consulta = gg.consultar_version(Path(raiz), config["caso"], config["geometria_origen"]["version_id"])
    try:
        from . import reuso_preparacion as rp
        prep = rp.obtener(getattr(resultado, "_preparacion_malla_reutilizable", None), consulta.geometria, config)
        if prep is None:
            prep = me.mp.preparar_malla(consulta.geometria, config)
    except me.mp.ErrorMalla as error:
        raise ErrorPlanRechazado("Malla no reproducible.", [str(error)]) from error
    if prep["huella_preparacion"] != (resultado.preparacion_malla or {}).get("huella_preparacion"):
        raise ErrorPlanRechazado("La malla cambió desde la comprobación.", ["huella_preparacion distinta."])
    liquidos = None
    if config["version_contrato"] == me.VERSION_LIQUIDOS:
        from . import liquidos_malla as lm  # importación diferida: liquidos_malla depende de este módulo
        try:
            liquidos = lm.preparar_liquidos(consulta.geometria, config, prep)
        except lm.ErrorCargaLiquido as error:
            raise ErrorPlanRechazado("Cargas de líquido no reproducibles; no se genera plan.", [str(error)]) from error
    _validar_opciones_dinamicas(config, opciones)
    niveles = _niveles_piso(vg)
    exp, sup, por_host = _expandir_malla(config, prep, vg)
    motivos = (_motivos_no_soportados(config, opciones) + _motivos_niveles(niveles)
               + _motivos_superficies(sup, niveles, _niveles_auxiliares(vg)))
    nombres = set(sup["asignaciones"]) | {f["id"] for f in exp["frames"]} | {p["id"] for p in exp["puntos"]}
    if len(nombres) != len(sup["asignaciones"]) + len(exp["frames"]) + len(exp["puntos"]):
        motivos.append("Colisión de nombres CSI entre puntos, frames y triángulos; no se renombra.")
    if motivos:
        raise ErrorPlanRechazado("Transporte de malla 0.4 rechazado íntegramente.", motivos)
    plan = _compilar(exp, resultado, vg, niveles, opciones, sup)
    datos = plan.datos
    b = _Constructor()
    b.operaciones = [o for o in datos["operaciones"] if o["metodo"] != "cFile.Save"]
    b.salidas = {s["registra"] for o in b.operaciones for s in o.get("salidas", [])}
    if liquidos and liquidos["filas"]:
        _operaciones_liquidos(b, liquidos)
    _relecturas_malla(b, exp, sup)
    b.op("guardado", "cFile.Save", {"FileName": opciones["destino_guardado"]}, "opciones.destino_guardado",
         descripcion="El ejecutor exige que el destino no exista antes de llamar.")
    datos["operaciones"] = b.operaciones
    datos["resumen"] = {fase: sum(1 for o in b.operaciones if o["fase"] == fase) for fase in dict.fromkeys(o["fase"] for o in b.operaciones)}
    _datos_malla(datos, config, resultado, prep, sup, exp, por_host, vg)
    if liquidos is not None:
        datos["version_contrato"] = VERSION_PLAN_LIQUIDOS
        datos["origen"]["configuracion_version"] = config["version_contrato"]
        datos["liquidos"] = liquidos
        datos["aviso"] += (" Líquidos: aplicabilidad " + liquidos["aplicabilidad"] + "; presión estática revisada en tabla nativa "
                           "no uniforme (no hidrodinámica, geotecnia ni flotación).")
        if resultado.contenido_masa is not None:
            # R249-02: inventario del contenido (estado por depósito, γV, Fz de presión, factor 1 en la fuente de masa) ligado a la
            # huella de líquidos de este plan; la masa ENSAMBLADA se acredita tras el análisis (masa_ensamblada), no aquí.
            if resultado.contenido_masa["huella_liquidos"] != liquidos["huella_liquidos"]:
                raise ErrorPlanRechazado("El contenido se contabilizó con otras presiones.", ["huella_liquidos distinta."])
            datos["contenido_masa"] = copy.deepcopy(resultado.contenido_masa)
            datos["pendientes"] = datos["pendientes"] + [{"capacidad": "liquidos_no_afirmado", "motivo": "Hidrodinámica, geotecnia y flotación no se modelan; la masa del contenido está contabilizada (declarada) y su masa ensamblada en ETABS queda por acreditar tras el análisis."}]
        else:
            datos["pendientes"] = datos["pendientes"] + [{"capacidad": "liquidos_no_afirmado", "motivo": "Hidrodinámica, geotecnia, flotación y masa del líquido no se modelan ni afirman."}]
    datos["huella_plan"] = huella_plan(datos)
    problemas = validar_plan_por_version(datos)
    if problemas:
        raise AssertionError("El plan de malla generado no supera su propia validación: " + "; ".join(problemas))
    return PlanOperaciones(datos)


def _operaciones_liquidos(b: _Constructor, liq: dict) -> None:
    """Verificación del esquema nativo ANTES de mutar (insertada tras las verificaciones) y edición «agregar» de la tabla."""
    campos = list(CAMPOS_NO_UNIFORME)
    textos = {"Dir": sorted({r["Dir"] for r in liq["filas"]}), "Restriction": sorted({r["Restriction"] for r in liq["filas"]})}
    previa = _Constructor()
    previa.op("verificacion", "cDatabaseTables.GetAllFieldsInTable", {"TableKey": TABLA_NO_UNIFORME, "TableVersion": 0, "NumberFields": 0,
              "FieldKey": [], "FieldName": [], "Description": [], "UnitsString": [], "IsImportable": []}, "$.liquidos",
              presentes={"FieldKey": campos}, importables=campos, textos=textos,
              descripcion="Esquema nativo de la tabla no uniforme: campos importables y textos de dirección/restricción nombrados.")
    ultima = max(i for i, o in enumerate(b.operaciones) if o["fase"] == "verificacion")
    b.operaciones.insert(ultima + 1, previa.operaciones[0])
    for i, o in enumerate(b.operaciones, 1):
        o["orden"] = i
    b.tabla("cargas_liquidos", TABLA_NO_UNIFORME, [dict(r) for r in liq["filas"]], "$.liquidos",
            "Presión hidrostática p=gamma*max(0,h-z) por componente global (A,B,C kN/m3; D kN/m2) sobre triángulos de la malla; "
            "patrón dedicado sin peso propio. Agregar conserva filas ajenas y rechaza colisiones.")


def _relecturas_malla(b: _Constructor, exp: dict, sup: dict) -> None:
    """Getters añadidos por 0.4: apoyos, cargas de área por triángulo, fuente de masa y extremos de frames."""
    for apoyo in exp["apoyos"]:
        b.op("comprobacion_malla", "cPointObj.GetRestraint", {"Name": _ref("punto", apoyo["punto"]), "Value": []},
             f"$.apoyos.{apoyo['punto']}", releer={"Value": list(apoyo["restricciones"])})
    por_area = {}
    for c in exp["cargas"]:
        if c["objetivo_tipo"] == "superficie":
            por_area.setdefault(c["objetivo"], []).extend(
                (c["patron"], DIRECCION_GLOBAL[i], v) for i, v in enumerate(c["componentes"]) if v != 0)
    for t in sorted(sup["asignaciones"]):
        items = por_area.get(t, [])
        releer = {"NumberItems": len(items)}
        if len(items) == 1:
            releer.update(AreaName=[t], LoadPat=[items[0][0]], CSys=["Global"], Dir=[items[0][1]], Value=[items[0][2]])
        b.op("comprobacion_malla", "cAreaObj.GetLoadUniform", {"Name": _ref("superficie", t), "NumberItems": 0, "AreaName": [],
             "LoadPat": [], "CSys": [], "Dir": [], "Value": [], "ItemType": _enum("eItemType", "Objects")},
             f"malla.triangulos.{t}", releer=releer, registrar=[] if len(items) == 1 else ["LoadPat", "Dir", "Value"],
             descripcion="Número de cargas uniformes del triángulo; valores completos si hay una sola (orden no observado si hay varias).")
    masa = exp["masa"]
    b.op("comprobacion_malla", "cPropMaterial.GetMassSource_1", {"IncludeElements": False, "IncludeAddedMass": False,
         "IncludeLoads": False, "NumberLoads": 0, "LoadPat": [], "sf": []}, "$.masa",
         releer={"IncludeElements": masa["incluir_masa_propia"], "IncludeAddedMass": False, "IncludeLoads": True,
                 "NumberLoads": len(masa["factores_patrones"])}, registrar=["LoadPat", "sf"])
    for sec in exp["secciones"]:
        if sec["tipo"] == me.SECCION_L:
            esperado = {k: v for k, v in _parametros_l(sec).items() if k not in ("Name", "Color", "Notes", "GUID")}
            b.op("comprobacion_malla", "cPropFrame.GetConcreteL", {"Name": sec["id"], "FileName": "", "MatProp": "", "T3": 0.0, "T2": 0.0,
                 "Tf": 0.0, "TwC": 0.0, "TwT": 0.0, "MirrorAbout2": False, "MirrorAbout3": False, "Color": 0, "Notes": "", "GUID": ""},
                 f"$.secciones.{sec['id']}", releer=esperado)
    for ins in exp.get("insercion_frames", []):
        b.op("comprobacion_malla", "cFrameObj.GetInsertionPoint", {"Name": _ref("frame", ins["frame"]), "CardinalPoint": 0, "Mirror2": False,
             "StiffTransform": False, "Offset1": [], "Offset2": [], "CSys": ""}, f"$.insercion_frames.{ins['frame']}",
             releer={"CardinalPoint": ins["punto_cardinal"], "Mirror2": False, "StiffTransform": ins["transformar_rigidez"],
                     "Offset1": list(ins["desplazamiento_global_m"]), "Offset2": list(ins["desplazamiento_global_m"]), "CSys": "Global"})
    for f in exp["frames"]:
        b.op("comprobacion_malla", "cFrameObj.GetPoints", {"Name": _ref("frame", f["id"]), "Point1": "", "Point2": ""},
             f"$.frames.{f['id']}", releer={"Point1": f["inicio"], "Point2": f["fin"]})


def _cargas_distribuidas(cargas_config, cargas_expandidas) -> dict:
    """{id_config: [ids expandidos que empiezan por id_config + '@']} en el orden de la configuración y de la expansión.

    Equivalente exacto a la comprensión cuadrática anterior (3610 × 7450 × 2 startswith en 09d1, ≈ 27 s): se agrupan en una pasada
    TODOS los prefijos terminados en '@' de cada id expandido, de modo que ids con varios '@' se asignan igual que con startswith.
    """
    ids_config = {c["id"] for c in cargas_config}
    grupos: dict[str, list] = {}
    for x in cargas_expandidas:
        xid = x["id"]
        i = xid.find("@")
        while i != -1:
            base = xid[:i]
            if base in ids_config:
                grupos.setdefault(base, []).append(xid)
            i = xid.find("@", i + 1)
    return {c["id"]: grupos[c["id"]] for c in cargas_config if c["id"] in grupos}


def _datos_malla(datos, config, resultado, prep, sup, exp, por_host, vg) -> None:
    datos.update(version_contrato=VERSION_PLAN_MALLA, estado="plan_no_ejecutado", ejecutable=True, aprueba_ingenieria=False)
    datos["aviso"] = ("Plan 0.4 de malla triangulada: habilitación operativa del transporte (datos completos, sin faltantes). "
                      "No aprueba el modelo ni la ingeniería, no certifica seguridad estructural y no sustituye la "
                      "verificación real en ETABS (guardado, reapertura y relectura independiente).")
    datos["origen"]["huella_configuracion"] = resultado.huella_contenido
    datos["origen"]["configuracion_version"] = config["version_contrato"]
    datos["comprobacion"] = {"apto_para_adaptador": True, "geometria_comprobada": resultado.geometria_comprobada,
                             "geometria_aprobada_por_huella": resultado.geometria_aprobada_por_huella,
                             "ejecutable_en_etabs": False, "bloqueos_informativos": list(resultado.bloqueos)}
    datos.pop("integracion_pendiente", None)
    datos["pendientes"] = [p for p in datos["pendientes"] if p["capacidad"] not in PENDIENTES_SUPERFICIES] + [
        {"capacidad": k, "motivo": v} for k, v in PENDIENTES_MALLA.items()]
    datos["precondiciones"] = [p for p in datos["precondiciones"] if not p.startswith("Plan de desarrollo")] + [
        "El ejecutor regenera este plan desde la configuración 0.4 (partición, compatibilidad y triangulación "
        "reproducidas) y exige igualdad canónica; cualquier relectura discrepante o fallo parcial impide cFile.Save."]
    datos["mapeo_ids"]["hosts_malla"] = {h: list(ts) for h, ts in sorted(por_host.items())}
    datos["mapeo_ids"]["frames_subdivididos"] = {r["frame"]: list(r["subframes"]) for r in prep["frames_subdivision_requerida"]}
    datos["mapeo_ids"]["nodos_derivados"] = list(prep["nodos_derivados"])
    datos["mapeo_ids"]["cargas_distribuidas"] = _cargas_distribuidas(config["cargas"], exp["cargas"])
    datos["malla"] = {
        "estrategia": prep["estrategia"], "huella_preparacion": prep["huella_preparacion"], "origen": copy.deepcopy(prep["origen"]),
        "hosts": copy.deepcopy(prep["hosts"]),
        "triangulos": {t["csi"]: {"host": t["host"], "celda": t["celda"], "id_malla": t["id_malla"], "nodos": list(t["nodos"]),
                                  "seccion": t["seccion"], "area_m2": t["area_m2"]} for t in prep["triangulos"]},
        "nodos_derivados": {n["csi"]: {"xyz_m": list(n["xyz_m"]), "nodo_malla": n["nodo_malla"], "alias": list(n["alias"]),
                                       "politica": next(copy.deepcopy(d) for d in config["nodos_derivados"] if d["nodo"] == n["csi"])}
                            for n in prep["nodos"] if n["tipo"] == "derivado"},
        "frames_subdivididos": copy.deepcopy(prep["frames_subdivision_requerida"]),
        "conexiones": [{"id": c["id"], "nodos_compartidos": list(c["nodos_compartidos"])} for c in prep["conexiones"]],
        "cortes_nivel": copy.deepcopy(prep["cortes_nivel"]),
        "sin_host_completo": True, "sin_aberturas_opening": True,
    }
    datos["conservacion"] = _conservacion_malla(config, prep, vg, sup, exp)


def validar_plan_malla(datos: Any) -> list[str]:
    """Plan 0.4: reglas comunes + malla sin host completo ni Opening, relecturas completas y conservación."""
    if not isinstance(datos, dict) or datos.get("contrato") != CONTRATO_PLAN or datos.get("version_contrato") != VERSION_PLAN_MALLA:
        return ["Contrato de plan de malla no admitido."]
    return _problemas_malla(datos)


def validar_plan_liquidos(datos: Any) -> list[str]:
    """Plan 0.5: todas las reglas de malla + líquidos coherentes (tabla única, filas = sección, patrones dedicados)."""
    if not isinstance(datos, dict) or datos.get("contrato") != CONTRATO_PLAN or datos.get("version_contrato") != VERSION_PLAN_LIQUIDOS:
        return ["Contrato de plan de líquidos no admitido."]
    problemas = _problemas_malla(datos)
    liq = datos.get("liquidos")
    ops = [o for o in datos.get("operaciones", []) if isinstance(o, dict)] if isinstance(datos.get("operaciones"), list) else []
    if not isinstance(liq, dict) or liq.get("aplicabilidad") not in ("ausente_confirmado", "presente") or not isinstance(liq.get("filas"), list):
        return problemas + ["Plan 0.5 sin sección liquidos con aplicabilidad ausente_confirmado o presente."]
    tablas = [o for o in ops if o.get("metodo") == "edicion_tabla" and o.get("tabla") == TABLA_NO_UNIFORME]
    previas = [o for o in ops if o.get("metodo") == "cDatabaseTables.GetAllFieldsInTable" and o.get("fase") == "verificacion"
               and any(a.get("nombre") == "TableKey" and a.get("valor") == TABLA_NO_UNIFORME for a in o.get("argumentos", []) if isinstance(a, dict))]
    if liq["aplicabilidad"] == "ausente_confirmado":
        if liq["filas"] or tablas or previas:
            problemas.append("Plan 0.5 con ausencia confirmada no admite filas ni edición de la tabla no uniforme.")
        return problemas
    if len(tablas) != 1 or len(previas) != 1 or not liq["filas"]:
        return problemas + ["Plan 0.5 presente: una verificación previa del esquema y una única edición de la tabla no uniforme."]
    if tablas[0].get("registros") != liq["filas"]:
        problemas.append("Plan 0.5: las filas editadas difieren de la sección liquidos.")
    tri = (datos.get("malla") or {}).get("triangulos") or {}
    patrones = set(liq.get("patrones") or [])
    creados = {a.get("valor") for o in ops if o.get("metodo") == "cLoadPatterns.Add" for a in o.get("argumentos", []) if isinstance(a, dict) and a.get("nombre") == "Name"}
    for fila in liq["filas"]:
        if not isinstance(fila, dict) or set(fila) != set(CAMPOS_NO_UNIFORME) or fila["UniqueName"] not in tri or fila["LoadPattern"] not in patrones:
            problemas.append("Plan 0.5: fila de líquido fuera de los triángulos o patrones declarados.")
            break
    if not patrones <= creados:
        problemas.append("Plan 0.5: patrón de líquido sin cLoadPatterns.Add.")
    for o in ops:
        if o.get("metodo") in ("cAreaObj.SetLoadUniform", "cFrameObj.SetLoadDistributed", "cPointObj.SetLoadForce"):
            if any(a.get("nombre") == "LoadPat" and a.get("valor") in patrones for a in o.get("argumentos", []) if isinstance(a, dict)):
                problemas.append("Plan 0.5: el patrón de líquido debe estar dedicado (sin otras cargas).")
                break
    if any(not isinstance(h, dict) or not (h.get("error_relativo_max", 1) <= 1e-9) for h in liq.get("hosts", [])):
        problemas.append("Plan 0.5: la presión sobre piezas no conserva fuerza y momento del contorno neto.")
    return problemas


def _problemas_malla(datos: dict) -> list[str]:
    problemas = []
    if datos.get("estado") != "plan_no_ejecutado" or datos.get("ejecutable") is not True or datos.get("aprueba_ingenieria") is not False:
        problemas.append("Plan 0.4: estado plan_no_ejecutado, ejecutable=true y aprueba_ingenieria=false.")
    malla = datos.get("malla")
    ops = [o for o in datos.get("operaciones", []) if isinstance(o, dict)] if isinstance(datos.get("operaciones"), list) else []
    if not isinstance(malla, dict) or not isinstance(malla.get("triangulos"), dict) or not isinstance(malla.get("hosts"), dict):
        return problemas + ["Plan 0.4 sin sección malla."] + _problemas_plan(datos)
    tri = malla["triangulos"]

    def args(o):
        return {a.get("nombre"): a.get("valor") for a in o.get("argumentos", []) if isinstance(a, dict)}
    if any(o.get("metodo") in ("cAreaObj.SetOpening", "cAreaObj.GetOpening") for o in ops):
        problemas.append("Plan 0.4: no se crean ni designan aberturas Opening.")
    creadas = [args(o) for o in ops if o.get("metodo") == "cAreaObj.AddByPoint"]
    nombres = [a.get("UserName") for a in creadas]
    if sorted(nombres) != sorted(tri) or set(nombres) & set(malla["hosts"]):
        problemas.append("Plan 0.4: las áreas creadas deben ser exactamente los triángulos (sin host completo).")
    for a in creadas:
        t = tri.get(a.get("UserName"))
        if t is None or a.get("NumberPoints") != 3 or a.get("Point") != [_ref("punto", p) for p in t.get("nodos", [])] or a.get("PropName") != t.get("seccion"):
            problemas.append(f"Plan 0.4: triángulo {a.get('UserName')} con contorno o propiedad distintos de la malla.")
    # Agrupación en una pasada (antes: hosts × triángulos, ≈ 13 M comparaciones por llamada en 09d1). Las claves de hosts son
    # textos JSON: solo un host textual pudo coincidir antes, así que solo esos se agrupan; la comparación sigue siendo sorted == sorted.
    por_host_tri: dict[str, list] = {}
    for t, x in tri.items():
        if isinstance(x, dict) and isinstance(x.get("host"), str):
            por_host_tri.setdefault(x["host"], []).append(t)
    for h, info in malla["hosts"].items():
        if not isinstance(info, dict) or sorted(info.get("triangulos", [])) != sorted(por_host_tri.get(h, []) if isinstance(h, str) else
                                                                                  [t for t, x in tri.items() if isinstance(x, dict) and x.get("host") == h]):
            problemas.append(f"Plan 0.4: host {h} con cobertura de triángulos inconsistente.")
    lect = {}
    for o in ops:
        if o.get("metodo") in ("cAreaObj.GetPoints", "cAreaObj.GetProperty", "cAreaObj.GetLoadUniform"):
            ref = args(o).get("Name")
            if isinstance(ref, dict):
                lect.setdefault(ref.get("ref"), set()).add(o["metodo"])
    for t in tri:
        if lect.get(f"superficie:{t}") != {"cAreaObj.GetPoints", "cAreaObj.GetProperty", "cAreaObj.GetLoadUniform"}:
            problemas.append(f"Plan 0.4: triángulo {t} sin relectura completa de contorno, propiedad y cargas.")
    for o in ops:
        if o.get("metodo") in ("cAreaObj.SetLoadUniform",):
            ref = args(o).get("Name")
            if not isinstance(ref, dict) or not str(ref.get("ref", "")).startswith("superficie:") or ref["ref"].split(":", 1)[1] not in tri:
                problemas.append("Plan 0.4: carga de área fuera de un triángulo de la malla.")
    apoyos = {args(o).get("Name", {}).get("ref") for o in ops if o.get("metodo") == "cPointObj.SetRestraint" and isinstance(args(o).get("Name"), dict)}
    releidos = {args(o).get("Name", {}).get("ref") for o in ops if o.get("metodo") == "cPointObj.GetRestraint" and isinstance(args(o).get("Name"), dict)}
    if apoyos != releidos:
        problemas.append("Plan 0.4: cada apoyo asignado requiere relectura GetRestraint.")
    if sum(1 for o in ops if o.get("metodo") == "cPropMaterial.GetMassSource_1") != 1:
        problemas.append("Plan 0.4: falta la relectura única de la fuente de masa.")
    frames = {args(o).get("UserName") for o in ops if o.get("metodo") == "cFrameObj.AddByPoint"}
    frames_leidos = {args(o).get("Name", {}).get("ref", "").split(":", 1)[-1] for o in ops if o.get("metodo") == "cFrameObj.GetPoints" and isinstance(args(o).get("Name"), dict)}
    if frames != frames_leidos:
        problemas.append("Plan 0.4: cada frame creado requiere relectura de extremos.")
    cons = datos.get("conservacion")
    if not isinstance(cons, dict) or cons.get("tolerancia_relativa") != TOLERANCIA_CONSERVACION:
        problemas.append("Plan 0.4: sin prueba de conservación.")
    else:
        for h, x in cons.get("hosts", {}).items():
            if not isinstance(x, dict) or not (x.get("error_relativo_area", 1) <= TOLERANCIA_CONSERVACION):
                problemas.append(f"Plan 0.4: el área de triángulos del host {h} no conserva el área neta.")
        for c in cons.get("cargas", []):
            if not isinstance(c, dict) or not (c.get("error_relativo_max", 1) <= TOLERANCIA_CONSERVACION):
                problemas.append(f"Plan 0.4: la carga {c.get('carga') if isinstance(c, dict) else c} no conserva fuerza y momento.")
    return problemas + _problemas_plan(datos)


def generar_plan_por_version(raiz: Path, configuracion: Any, **opciones: Any) -> PlanOperaciones:
    """Despacho del recorrido normal: 0.1 → plan 0.1; 0.4 → plan 0.4. 0.2/0.3 son de desarrollo y no se ejecutan."""
    version = configuracion.get("version_contrato") if isinstance(configuracion, dict) else None
    if version in (me.VERSION_MALLA, me.VERSION_LIQUIDOS):
        return generar_plan_malla(raiz, configuracion, **opciones)
    if version in (me.VERSION_SUPERFICIES, me.VERSION_ABERTURAS):
        raise ErrorPlanRechazado("Configuración de desarrollo sin plan ejecutable.",
                                 [f"La configuración {version} solo admite planes de desarrollo no ejecutables."])
    return generar_plan(raiz, configuracion, **opciones)


def validar_plan_por_version(datos: Any) -> list[str]:
    """Valida un plan ejecutable (0.1 o 0.4); los planes 0.2/0.3 de desarrollo se rechazan para el ejecutor."""
    version = datos.get("version_contrato") if isinstance(datos, dict) else None
    if version == VERSION_PLAN_MALLA:
        return validar_plan_malla(datos)
    if version == VERSION_PLAN_LIQUIDOS:
        return validar_plan_liquidos(datos)
    if version in (VERSION_PLAN_SUPERFICIES, VERSION_PLAN_ABERTURAS):
        return [f"Plan {version} de desarrollo: no ejecutable."]
    return validar_plan(datos)


# -- validación de planes ----------------------------------------------------

def _tipo_valido(tipo: str, valor: Any) -> bool:
    base = tipo.rstrip("&")
    if base.endswith("[]"):
        return isinstance(valor, list) and all(_tipo_valido(base[:-2], v) for v in valor)
    if isinstance(valor, dict) and set(valor) == {"ref"}:
        return base == "String"
    if base.startswith("e"):
        if not isinstance(valor, dict) or valor.get("enum") != base:
            return False
        if valor.get("nombre") is None:
            return base in ENUM_TODOS and valor.get("valor") == 0
        return ENUMS.get(base, {}).get(valor["nombre"]) == valor.get("valor")
    if base == "String":
        return isinstance(valor, str)
    if base == "Boolean":
        return isinstance(valor, bool)
    if base == "Int32":
        return isinstance(valor, int) and not isinstance(valor, bool) and -2**31 <= valor < 2**31
    if base == "Double":
        return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)
    return False


def es_lectura(metodo: Any) -> bool:
    """Count y Get*: llamadas que no modifican el modelo."""
    if not isinstance(metodo, str) or "." not in metodo:
        return False
    nombre = metodo.split(".", 1)[1]
    return nombre == "Count" or nombre.startswith("Get")


def _problemas_tabla(op: dict, etiqueta: str) -> list[str]:
    definicion = TABLAS_EDITABLES.get(op.get("tabla"))
    if definicion is None:
        return [f"{etiqueta}: tabla no admitida para edición: {op.get('tabla')!r}."]
    problemas = []
    esperado = {"tipo": "edicion_tabla", "interfaz": "SapModel.DatabaseTables", "modo": definicion["modo"],
                "clave": definicion["clave"], "campos": list(definicion["campos"]), "metodos": list(METODOS_EDICION_TABLA),
                "retorno": {"tipo": "Int32", "esperado": 0}}
    for clave, valor in esperado.items():
        if op.get(clave) != valor:
            problemas.append(f"{etiqueta}: '{clave}' no corresponde a la definición de {op['tabla']}.")
    registros = op.get("registros")
    if not isinstance(registros, list) or not registros:
        return problemas + [f"{etiqueta}: la edición no declara registros."]
    for registro in registros:
        if not isinstance(registro, dict) or set(registro) != set(definicion["campos"]) or \
                not all(isinstance(v, str) and v for v in registro.values()):
            problemas.append(f"{etiqueta}: cada registro debe dar texto no vacío para exactamente {definicion['campos']}.")
            break
    return problemas


def validar_plan(datos: Any) -> list[str]:
    """Comprueba lista blanca, firmas, tipos, orden, referencias y huella. No toca ETABS."""
    if not isinstance(datos, dict) or datos.get("contrato") != CONTRATO_PLAN or datos.get("version_contrato") != VERSION_PLAN:
        return ["Contrato de plan no admitido."]
    return _problemas_plan(datos)


def validar_plan_superficies(datos: Any) -> list[str]:
    """Plan 0.2 de desarrollo: mismas reglas que 0.1 y declaración explícita de no ejecutable."""
    if not isinstance(datos, dict) or datos.get("contrato") != CONTRATO_PLAN or \
            datos.get("version_contrato") != VERSION_PLAN_SUPERFICIES:
        return ["Contrato de plan de superficies no admitido."]
    problemas = []
    if datos.get("estado") != ESTADO_PLAN_SUPERFICIES or datos.get("ejecutable") is not False or \
            not isinstance(datos.get("comprobacion"), dict) or datos["comprobacion"].get("ejecutable_en_etabs") is not False:
        problemas.append("Un plan 0.2 debe declararse plan_desarrollo_no_ejecutable, ejecutable=false.")
    return problemas + _problemas_plan(datos)


def _problemas_plan(datos: dict) -> list[str]:
    problemas = []
    if datos.get("ejecutado") is not False or datos.get("aprueba_modelo") is not False:
        problemas.append("Un plan debe declarar ejecutado=false y aprueba_modelo=false.")
    try:
        if datos.get("huella_plan") != huella_plan(datos):
            problemas.append("La huella del plan no corresponde a su contenido.")
    except (TypeError, ValueError):
        problemas.append("Plan no serializable como JSON estricto.")
    registradas: set[str] = set()
    operaciones = datos.get("operaciones")
    if not isinstance(operaciones, list) or not operaciones:
        return problemas + ["El plan no contiene operaciones."]
    for indice, op in enumerate(operaciones, 1):
        etiqueta = f"Operación {indice}"
        if not isinstance(op, dict) or op.get("orden") != indice:
            problemas.append(f"{etiqueta}: orden ausente o no consecutivo.")
            continue
        if op.get("metodo") == "edicion_tabla":
            problemas.extend(_problemas_tabla(op, etiqueta))
            if op.get("fase") == "verificacion":
                problemas.append(f"{etiqueta}: una edición de tabla no puede ser una verificación.")
            continue
        if op.get("metodo") in METODOS_SOLO_EDICION:
            problemas.append(f"{etiqueta}: {op['metodo']} solo se admite dentro de una edición de tabla.")
            continue
        if op.get("fase") == "verificacion" and not es_lectura(op.get("metodo")):
            problemas.append(f"{etiqueta}: la fase de verificación solo admite lecturas.")
        firma = FIRMAS.get(op.get("metodo"))
        if firma is None:
            problemas.append(f"{etiqueta}: método fuera de la lista blanca: {op.get('metodo')!r}.")
            continue
        ruta, retorno, parametros = firma
        if op.get("interfaz") != ruta or op.get("retorno", {}).get("tipo") != retorno:
            problemas.append(f"{etiqueta}: interfaz o tipo de retorno distintos de la firma.")
        if not isinstance(op.get("retorno", {}).get("esperado"), int):
            problemas.append(f"{etiqueta}: falta el retorno esperado.")
        argumentos = op.get("argumentos")
        if not isinstance(argumentos, list) or [(a.get("tipo"), a.get("nombre")) for a in argumentos if isinstance(a, dict)] != parametros:
            problemas.append(f"{etiqueta}: argumentos no coinciden con la firma {op['metodo']}.")
            continue
        for arg in argumentos:
            if not _tipo_valido(arg["tipo"], arg.get("valor")):
                problemas.append(f"{etiqueta}: valor no válido para {arg['nombre']} ({arg['tipo']}).")
            for referencia in _referencias(arg.get("valor")):
                if referencia not in registradas:
                    problemas.append(f"{etiqueta}: referencia {referencia} no registrada por una operación anterior.")
        tipos = dict((nombre, tipo) for tipo, nombre in parametros)
        for salida in op.get("salidas", []):
            if not tipos.get(salida.get("parametro"), "").endswith("&") or salida.get("registra") in registradas:
                problemas.append(f"{etiqueta}: salida inválida o repetida.")
            registradas.add(salida.get("registra"))
        for clave in ("verificar_ausentes", "verificar_presentes"):
            for item in op.get(clave, []):
                if not tipos.get(item.get("parametro"), "").endswith("&") or not isinstance(item.get("nombres"), list):
                    problemas.append(f"{etiqueta}: {clave} sobre un parámetro que no es de salida.")
        for item in op.get("verificar_valores", []):
            tipo = tipos.get(item.get("parametro"), "")
            tolerancia = item.get("tolerancia_relativa")
            if not tipo.endswith("&") or not _tipo_valido(tipo, item.get("esperado")) or \
                    not (_finito(tolerancia) and 0 <= tolerancia < 1e-6):
                problemas.append(f"{etiqueta}: verificar_valores inválido para {item.get('parametro')!r}.")
        for parametro in op.get("registrar_valores", []):
            if not tipos.get(parametro, "").endswith("&"):
                problemas.append(f"{etiqueta}: registrar_valores sobre un parámetro que no es de salida.")
        if ("verificar_importables" in op or "verificar_textos" in op) and op.get("metodo") != "cDatabaseTables.GetAllFieldsInTable":
            problemas.append(f"{etiqueta}: verificar_importables/verificar_textos solo aplican a GetAllFieldsInTable.")
        if not isinstance(op.get("verificar_importables", []), list) or \
                not all(isinstance(c, str) and c for c in op.get("verificar_importables", [])):
            problemas.append(f"{etiqueta}: verificar_importables debe ser una lista de campos.")
        for item in op.get("verificar_textos", []):
            if not isinstance(item, dict) or not isinstance(item.get("campo"), str) or not item.get("valores") or \
                    not all(isinstance(v, str) and v.strip() for v in item.get("valores", [])):
                problemas.append(f"{etiqueta}: verificar_textos inválido.")
    fases = [op.get("fase") for op in operaciones if isinstance(op, dict)]
    if "verificacion" in fases and any(f != "verificacion" for f in fases[:max(i for i, f in enumerate(fases) if f == "verificacion")]):
        problemas.append("Las verificaciones deben preceder a toda mutación.")
    metodos = [op.get("metodo") for op in operaciones if isinstance(op, dict)]
    if metodos[-1:] != ["cFile.Save"] or metodos.count("cFile.Save") != 1:
        problemas.append("El guardado debe ser la última y única operación de guardado.")
    return problemas


# -- verificación de firmas contra la DLL instalada --------------------------

_SCRIPT_REFLEXION = r"""
$ErrorActionPreference = 'Stop'
$asm = [Reflection.Assembly]::LoadFrom($env:D2M_DLL)
$salida = [ordered]@{ version_archivo = (Get-Item -LiteralPath $env:D2M_DLL).VersionInfo.FileVersion; metodos = @{}; enums = @{} }
foreach ($clave in ($env:D2M_METODOS -split ';')) {
    $tipo, $nombre = $clave -split '\.'
    $t = $asm.GetType("ETABSv1.$tipo")
    $firmas = @()
    if ($t) { foreach ($m in $t.GetMethods()) { if ($m.Name -eq $nombre) {
        $firmas += ,@($m.ReturnType.Name, @($m.GetParameters() | ForEach-Object { $_.ParameterType.Name + ' ' + $_.Name }))
    } } }
    $salida.metodos[$clave] = $firmas
}
foreach ($e in ($env:D2M_ENUMS -split ';')) {
    $t = $asm.GetType("ETABSv1.$e"); $valores = @{}
    if ($t) { foreach ($n in [enum]::GetNames($t)) { $valores[$n] = [int][enum]::Parse($t, $n) } }
    $salida.enums[$e] = $valores
}
[Console]::Out.Write((ConvertTo-Json -InputObject $salida -Depth 8 -Compress))
"""


def reflejar_dll(dll: Path = DLL_ETABS, powershell: Path = POWERSHELL_51, timeout_s: float = 120) -> dict[str, Any]:
    """Lee por reflexión las firmas de FIRMAS y los valores de ENUMS. Solo carga metadatos; no inicia ETABS."""
    if not Path(dll).is_file() or not Path(powershell).is_file():
        raise ErrorPlan("Se requieren la DLL de ETABS y Windows PowerShell 5.1 para verificar firmas.")
    entorno = dict(os.environ, D2M_DLL=str(dll), D2M_METODOS=";".join(FIRMAS),
                   D2M_ENUMS=";".join(sorted(set(ENUMS) | ENUM_TODOS)))
    # -EncodedCommand: no depende de la directiva de ejecución de scripts ni de leer bloques por stdin.
    codificado = base64.b64encode(_SCRIPT_REFLEXION.encode("utf-16-le")).decode("ascii")
    proceso = subprocess.run([str(powershell), "-NoProfile", "-NonInteractive", "-EncodedCommand", codificado],
                             capture_output=True, env=entorno, timeout=timeout_s, check=False, stdin=subprocess.DEVNULL)
    if proceso.returncode != 0:
        raise ErrorPlan("La reflexión de la DLL falló: " + proceso.stderr.decode("utf-8", "replace")[-2000:])
    return json.loads(proceso.stdout.decode("utf-8-sig"))


def comparar_firmas(reflejado: dict[str, Any]) -> list[str]:
    """Diferencias entre la lista blanca y lo reflejado; lista vacía si todo coincide."""
    diferencias = []
    for clave, (_, retorno, parametros) in FIRMAS.items():
        esperada = [retorno, [f"{tipo} {nombre}" for tipo, nombre in parametros]]
        encontradas = reflejado.get("metodos", {}).get(clave) or []
        if isinstance(encontradas, list) and len(encontradas) == 2 and isinstance(encontradas[0], str):
            encontradas = [encontradas]  # ConvertTo-Json puede aplanar una única sobrecarga
        normalizadas = [[f[0], list(f[1]) if isinstance(f[1], list) else ([f[1]] if f[1] else [])] for f in encontradas]
        if esperada not in normalizadas:
            diferencias.append(f"{clave}: esperada {esperada}; DLL {normalizadas}")
    for enum, valores in ENUMS.items():
        reales = reflejado.get("enums", {}).get(enum) or {}
        for nombre, valor in valores.items():
            if reales.get(nombre) != valor:
                diferencias.append(f"{enum}.{nombre}: esperado {valor}; DLL {reales.get(nombre)}")
    return diferencias


def verificar_firmas_dll(dll: Path = DLL_ETABS, powershell: Path = POWERSHELL_51) -> dict[str, Any]:
    reflejado = reflejar_dll(dll, powershell)
    return {"version_archivo": reflejado.get("version_archivo"), "metodos": len(FIRMAS),
            "diferencias": comparar_firmas(reflejado)}


# -- línea de comandos propia (no registrada en __main__) ----------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Plan declarativo de operaciones ETABS; no ejecuta ETABS.")
    parser.add_argument("--verificar-firmas", action="store_true", help="Solo comparar la lista blanca con la DLL")
    parser.add_argument("--raiz", type=Path)
    parser.add_argument("--entrada", type=Path, help="Configuración draft2model.modelo_estructural")
    parser.add_argument("--salida", type=Path, help="Archivo JSON nuevo; no se sobrescribe")
    parser.add_argument("--destino-guardado")
    parser.add_argument("--tipo-shell-muro", choices=TIPOS_SHELL_MURO)
    losa = parser.add_mutually_exclusive_group()
    losa.add_argument("--tipo-shell-losa", choices=TIPOS_SHELL_LOSA, help="Formulación GLOBAL de losas (configuraciones 0.2/0.3/0.4/0.5)")
    losa.add_argument("--tipo-shell-losa-json", type=Path,
                      help="Archivo JSON con el mapa POR SECCIÓN {seccion: {tipo, funcion, justificacion}} (R241; 0.4/0.5)")
    parser.add_argument("--gravedad-programa", type=float)
    args = parser.parse_args(argv)
    try:
        if args.verificar_firmas:
            informe = verificar_firmas_dll()
            print(json.dumps(informe, ensure_ascii=False, indent=2))
            return 0 if not informe["diferencias"] else 2
        if not (args.raiz and args.entrada and args.salida):
            raise ErrorPlan("Se requieren --raiz, --entrada y --salida.")
        config = me.cargar_configuracion(args.entrada)
        version = config.get("version_contrato") if isinstance(config, dict) else None
        tipo_losa = args.tipo_shell_losa
        if args.tipo_shell_losa_json is not None:
            if version not in (me.VERSION_MALLA, me.VERSION_LIQUIDOS):
                raise ErrorPlan("--tipo-shell-losa-json solo aplica a configuraciones 0.4/0.5 (malla).")
            try:
                tipo_losa = me.json_desde_bytes(Path(args.tipo_shell_losa_json).read_bytes(), "tipo_shell_losa.json")
            except OSError as exc:
                raise ErrorPlan(f"Mapa de losas ilegible: {exc}") from exc
            if not isinstance(tipo_losa, dict) or not tipo_losa:
                raise ErrorPlan("El mapa de losas debe ser un objeto JSON no vacío {seccion: {tipo, funcion, justificacion}}.")
        if version in (me.VERSION_MALLA, me.VERSION_LIQUIDOS):
            # Plan 0.4/0.5 ejecutable por el recorrido normal (con guardas y relectura); no aprueba ingeniería.
            opciones = {k: v for k, v in (("destino_guardado", args.destino_guardado), ("tipo_shell_muro", args.tipo_shell_muro),
                                          ("tipo_shell_losa", tipo_losa),
                                          ("gravedad_programa_m_s2", args.gravedad_programa)) if v is not None}
            plan = generar_plan_malla(args.raiz, config, **opciones)
        elif isinstance(config, dict) and config.get("version_contrato") in (me.VERSION_SUPERFICIES, me.VERSION_ABERTURAS):
            # Plan 0.2 de desarrollo: se escribe para revisión; ningún ejecutor lo acepta.
            opciones = {k: v for k, v in (("destino_guardado", args.destino_guardado), ("tipo_shell_muro", args.tipo_shell_muro),
                                          ("tipo_shell_losa", args.tipo_shell_losa),
                                          ("gravedad_programa_m_s2", args.gravedad_programa)) if v is not None}
            generador = generar_plan_aberturas if config["version_contrato"] == me.VERSION_ABERTURAS else generar_plan_superficies
            plan = generador(args.raiz, config, **opciones)
        else:
            if args.tipo_shell_losa is not None:
                raise ErrorPlan("--tipo-shell-losa solo aplica a configuraciones con losas (0.2/0.3/0.4/0.5).")
            opciones = {"destino_guardado": args.destino_guardado, "tipo_shell_muro": args.tipo_shell_muro}
            if args.gravedad_programa is not None:
                opciones["gravedad_programa_m_s2"] = args.gravedad_programa
            plan = generar_plan(args.raiz, config, **opciones)
        with open(args.salida, "x", encoding="utf-8") as archivo:
            archivo.write(plan.a_json())
    except ErrorPlan as error:
        print(str(error), file=sys.stderr)
        return error.codigo
    except (ErrorGestion, OSError) as error:
        print(f"Operación no completada: {error}", file=sys.stderr)
        return 1
    print(f"Plan: {args.salida} ({len(plan.operaciones)} operaciones, huella {plan.huella}); no ejecutado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
