"""Rotación cíclica observada en GetPoints191: preserva sentido y todos los nodos."""
import base64
import json
from pathlib import Path
import subprocess
import unittest
from draft2model.adaptador_etabs import POWERSHELL_51
from draft2model.verificacion_modelo_guardado import contorno_orientado_igual


class ContornoNativoTests(unittest.TestCase):
    def test_python_reader_preserves_orientation_and_connectivity(self):
        expected = ['MC_1','W1','MN_S2_1']
        for actual in (['W1','MN_S2_1','MC_1'], expected, ['MN_S2_1','MC_1','W1']):
            self.assertTrue(contorno_orientado_igual(expected,actual))
        for actual in (list(reversed(expected)), ['W1','W1','MC_1'], ['W1','OTRO','MC_1'],
                       ['W1','MC_1'], ['W1','MN_S2_1','mc_1']):
            self.assertFalse(contorno_orientado_igual(expected,actual))
        self.assertFalse(contorno_orientado_igual(['A','B','C','D'],['A','C','B','D']))

    def test_native_cyclic_start_without_accepting_inversion_or_other_connectivity(self):
        script = Path(__file__).resolve().parents[1]/'scripts/ejecutar_plan_etabs.ps1'
        cmd = """$ErrorActionPreference='Stop'
$t=$null;$e=$null
$a=[System.Management.Automation.Language.Parser]::ParseFile(PATH,[ref]$t,[ref]$e)
if($e.Count){throw 'Script no válido'}
$f=$a.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Test-ContornoOrientadoIgual'},$true)
if($null -eq $f){throw 'Función no encontrada'}
Invoke-Expression $f.Extent.Text
$expected=@('MC_1','W1','MN_S2_1')
$r=@()
$r+=Test-ContornoOrientadoIgual @('W1','MN_S2_1','MC_1') $expected
$r+=Test-ContornoOrientadoIgual @('MC_1','W1','MN_S2_1') $expected
$r+=Test-ContornoOrientadoIgual @('MN_S2_1','MC_1','W1') $expected
$r+=Test-ContornoOrientadoIgual @('MC_1','MN_S2_1','W1') $expected
$r+=Test-ContornoOrientadoIgual @('W1','W1','MC_1') $expected
$r+=Test-ContornoOrientadoIgual @('W1','OTRO','MC_1') $expected
$r+=Test-ContornoOrientadoIgual @('W1','MC_1') $expected
$r+=Test-ContornoOrientadoIgual @('W1','MN_S2_1','mc_1') $expected
$r+=Test-ContornoOrientadoIgual @('A','C','B','D') @('A','B','C','D')
ConvertTo-Json -InputObject $r -Compress
""".replace('PATH',"'"+str(script).replace("'","''")+"'")
        result = subprocess.run([str(POWERSHELL_51),'-NoProfile','-NonInteractive','-EncodedCommand',
                                 base64.b64encode(cmd.encode('utf-16le')).decode()],capture_output=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout),[True,True,True,False,False,False,False,False,False])


if __name__=='__main__':unittest.main()
