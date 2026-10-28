"""Una lectura nativa acotada de configuración; el original jamás se abre en ETABS."""
from pathlib import Path
from datetime import datetime, timezone
import json
import os
import subprocess

root=Path(__file__).resolve().parents[1]
summary=root/'seguimiento/RESULTADO_CONFIGURACION_318_REPARACION.json'
assert not summary.exists() and not (root/'tmp/configuracion_318_reparacion').exists()
ps=str(Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe')
data={'inicio_utc':datetime.now(timezone.utc).isoformat(),'estado':'en_curso','goal_completo':False}
def save():summary.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
with (root/'tmp/configuracion_318_reparacion_proceso.log').open('w',encoding='utf-8') as log:
    proc=subprocess.Popen([ps,'-NoProfile','-NonInteractive','-File',str(root/'seguimiento/inspeccionar_configuracion_318.ps1')],cwd=root,stdout=log,stderr=subprocess.STDOUT)
    data['pid_harness']=proc.pid;save()
    try:data['codigo']=proc.wait(timeout=180)
    except subprocess.TimeoutExpired:
        data['timeout']=True
        receipt=root/'tmp/configuracion_318_reparacion/registro.json'
        if receipt.exists():
            own=json.loads(receipt.read_text(encoding='utf-8-sig')).get('proceso_propio')
            if own:
                cleanup=subprocess.run([ps,'-NoProfile','-NonInteractive','-File',str(root/'seguimiento/cerrar_instancia_propia_316.ps1'),
                    '-IdPropio',str(int(own['pid'])),'-InicioEsperado',own['inicio_utc']],capture_output=True,text=True,timeout=20)
                data['cleanup']={'codigo':cleanup.returncode,'salida':cleanup.stdout,'error':cleanup.stderr}
        try:data['codigo']=proc.wait(timeout=20)
        except subprocess.TimeoutExpired:proc.kill();data['codigo']=proc.wait()
data.update(estado='terminado',fin_utc=datetime.now(timezone.utc).isoformat());save()
print(json.dumps(data,ensure_ascii=False))
raise SystemExit(data['codigo'] or (2 if data.get('timeout') else 0))
