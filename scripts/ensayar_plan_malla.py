"""Ensayo nativo sintético del ejecutor normal0.4; no usa planos ni modelo manual.

Conserva fixtures y evidencias en una carpeta NUEVA dentro de tmp. No analiza.
"""
import argparse
import base64
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from draft2model import adaptador_etabs as ad, ejecutor_etabs as ej
from draft2model import gestion_configuracion as gc, modelo_estructural as m
from draft2model import operaciones_etabs as op, revision_modelo as rm
from draft2model.ejecucion_modelo import EjecutorVerificado
from tests.test_integracion_malla import CasoMalla, REVISOR
from tests import test_gestion_geometria as disco
from draft2model.ingreso import registrar_expediente


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def guardar(p, x):
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trabajo', type=Path, required=True)
    parser.add_argument('--confirmar-sintetico', action='store_true', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    work = args.trabajo.absolute()
    if not work.is_relative_to(root/'tmp') or work.resolve() != work:
        raise ValueError('Carpeta nueva dentro de tmp requerida.')
    lock = root/'tmp/d2/motor.lock'
    incierto = Path(str(lock)+'.incierto.json')
    if incierto.exists():
        raise ValueError('Hay incertidumbre del motor; no se abre instancia.')
    work.mkdir(exist_ok=False)
    source = root/'tmp/d4/copia/plantilla_vacia.edb'
    original = sha(source)
    firmas = op.verificar_firmas_dll()
    guardar(work/'firmas.json', firmas)
    if firmas['diferencias']:
        raise ValueError('Firmas distintas; no se abre ETABS.')
    # Fixtures de software conservadas, sin dobles del motor ni modificación de sus funciones.
    (work/'fuentes').mkdir()
    # No usar TemporaryDirectory: su finalizador borraría las fuentes/registro
    # al terminar Python aunque no se haya llamado explícitamente a cleanup.
    cm = CasoMalla()
    cm.f = disco.CasoGeometria()
    cm.f.trabajo = work/'fuentes'
    cm.f.raiz = cm.f.trabajo/'private'
    pdf = cm.f.trabajo/'plano_sintetico.pdf'
    pdf.write_bytes(b'%PDF-1.4\ncontenido sintetico para pruebas de geometria\n')
    cm.f.manifest = registrar_expediente(disco.CASO,[pdf],cm.f.raiz,
                                       uso_autorizado=True,provisional_fuera_alcance=True)
    cm.f.caso_dir = cm.f.manifest.parent
    cm.f.original = cm.f.caso_dir/'originales/lamina-0001.pdf'
    cm.f.entrada = cm.f.trabajo/'geometria.json'
    cm.f.entrada.write_bytes(disco.EJEMPLO.read_bytes())
    cm.raiz = cm.f.raiz
    data = cm.montar('conectados_corte')
    data['plantilla']['sha256'] = original
    data = cm.completar(data)
    imp = gc.importar(cm.raiz, disco.CASO, cm.f.escribir(data, 'config_real.json'))
    rev = gc.revisar(cm.raiz, disco.CASO, imp['id'], data, **REVISOR)
    approved = gc.aprobar(cm.raiz, disco.CASO, rev['id'],
                         huella_esperada=m.huella_configuracion(rev['configuracion']),
                         alcance='Ensayo sintético nativo, no ingeniería.', **REVISOR)['configuracion']
    cm.destino = str(work/'modelo.edb')
    plan = op.generar_plan_por_version(cm.raiz, approved, **cm.opciones(approved)).datos
    guardar(work/'configuracion.json', approved); guardar(work/'plan.json', plan)
    (work/'apertura').mkdir(); (work/'motor').mkdir()
    bridge = ad.AdaptadorEtabs(ad.ConfiguracionPuente.real(work/'apertura',lock,timeout_s=180))
    report = {'datos_sinteticos':True,'etabs_real':True,'analisis_ejecutado':False,
              'sha256_original':original,'raiz_fuentes':str(cm.raiz),'cierre_confirmado':False}
    opened = None
    try:
        opened = bridge.abrir_copia_plantilla(source,original,work/'copia',instancia='nueva')
        guardar(work/'apertura.json',opened.datos)
        pid = opened.datos['id_proceso']
        copy = Path(opened.datos['modelo_abierto'])
        report.update(id_proceso=pid,copia=str(copy))
        executor = EjecutorVerificado(ej.configuracion_real(work/'motor',lock,timeout_s=240))
        prepared = executor.preparar(cm.raiz,approved,plan,copia=copy,modelo_esperado=copy,id_proceso=pid)
        report['corrida'] = str(prepared.carpeta)
        guardar(work/'registro.json',report)
        result = executor.ejecutar(prepared,confirmar_mutacion=True)
        report.update(operaciones=result.operaciones_ejecutadas,guardado=result.guardado,
                      aceptacion_integracion=result.extra['aceptacion_integracion'])
        registro = rm.registrar(cm.raiz,disco.CASO,approved,plan,prepared.carpeta)
        report['registro_modelo'] = str(registro)
    except Exception as exc:
        report.update(error_tipo=type(exc).__name__,error=str(exc))
    finally:
        if opened is not None:
            # Solo el PID recién creado y solo sus dos rutas propias permitidas.
            q = lambda s: "'"+str(s).replace("'","''")+"'"
            command = """$ErrorActionPreference='Stop'
function Hash([string]$ruta){$alg=[Security.Cryptography.SHA256]::Create();$f=[IO.File]::OpenRead($ruta);try{return [BitConverter]::ToString($alg.ComputeHash($f)).Replace('-','').ToLowerInvariant()}finally{$f.Dispose();$alg.Dispose()}}
Add-Type -Path 'C:\\Program Files\\Computers and Structures\\ETABS 21\\ETABSv1.dll'
$null=Get-Process -Id PID -ErrorAction Stop
$h=New-Object ETABSv1.Helper
$a=$h.GetObjectProcess('CSI.ETABS.API.ETABSObject',PID)
if($null -eq $a){throw 'Instancia propia no disponible; no se cierra otra.'}
$p=[IO.Path]::GetFullPath($a.SapModel.GetModelFilename($true))
Write-Output ('MODELO_OBSERVADO: '+$p)
if($p -ieq ALIAS){
 if(EXPECTED -eq '' -or -not (Test-Path -LiteralPath DEST)){throw 'Alias sin guardado verificable'}
 if((Hash DEST) -cne EXPECTED){throw 'Guardado cambiado; cierre cancelado'}
} elseif($p -ine COPY -and $p -ine DEST){throw 'Modelo distinto; cierre cancelado.'}
$rc=$a.ApplicationExit($false)
if($rc -ne 0){throw "Cierre devolvio $rc"}
Write-Output 'CIERRE_PROPIO_CONFIRMADO'
""".replace('PID',str(opened.datos['id_proceso'])).replace('COPY',q(opened.datos['modelo_abierto'])).replace('DEST',q(work/'modelo.edb')).replace('ALIAS',q(work/'modelo.$et')).replace('EXPECTED',q(report.get('guardado',{}).get('sha256','')))
            try:
                with ad.BloqueoExclusivo(lock):
                    close = subprocess.run([str(ad.POWERSHELL_51),'-NoProfile','-NonInteractive','-EncodedCommand',
                                            base64.b64encode(command.encode('utf-16le')).decode()],
                                           capture_output=True,timeout=60)
                (work/'cierre.log').write_bytes(close.stdout+close.stderr)
                report['metodo_cierre'] = 'ApplicationExit(false), proceso y ruta propios verificados'
                report['cierre_confirmado'] = close.returncode == 0 and b'CIERRE_PROPIO_CONFIRMADO' in close.stdout
            except Exception as exc:
                report['error_cierre'] = str(exc)
        report['sha256_original_posterior'] = sha(source)
        guardar(work/'registro.json',report)
    print(json.dumps(report,ensure_ascii=True,indent=2))
    return 0 if not report.get('error') and report['cierre_confirmado'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
