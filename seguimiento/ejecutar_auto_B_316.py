"""Una ejecución B aislada con supervisión acotada y sin borrar la evidencia315."""
from pathlib import Path
from datetime import datetime, timezone
import json
import os
import subprocess
import hashlib

root = Path(__file__).resolve().parents[1]
work = root/'seguimiento/ensayo_codex_auto_316'
result = work/'RESULTADO_316.json'
assert not result.exists()
ps = str(Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe')
# Verificación host: la instancia315 y su caller ya deben haber terminado.
guard = subprocess.run([ps,'-NoProfile','-NonInteractive','-Command',
    "if((Get-Process -Id 44832,38060 -ErrorAction SilentlyContinue)){exit 3}"],capture_output=True)
assert guard.returncode == 0, '315 todavía activo o PID reutilizado; no iniciar B'
data = {'inicio_utc':datetime.now(timezone.utc).isoformat(),'datos_sinteticos':True,
        'llamadas_remotas':0,'estado':'en_curso','goal_completo':False}
def save():
    result.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
with (work/'proceso.log').open('w',encoding='utf-8') as log:
    proc = subprocess.Popen([ps,'-NoProfile','-NonInteractive','-File',str(work/'ensayar_B_316.ps1'),
        '-Salida',str(work/'corrida_B'),'-ConfirmarEnsayoSintetico'],stdout=log,stderr=subprocess.STDOUT,cwd=root)
    data['pid_harness']=proc.pid;save()
    try:
        data['codigo']=proc.wait(timeout=180)
    except subprocess.TimeoutExpired:
        data['timeout']=True
        record = work/'corrida_B/registro_316.json'
        if record.exists():
            observed=json.loads(record.read_text(encoding='utf-8-sig')).get('proceso_propio')
            if observed:
                closed=subprocess.run([ps,'-NoProfile','-NonInteractive','-File',str(root/'seguimiento/cerrar_instancia_propia_316.ps1'),
                    '-IdPropio',str(int(observed['pid'])),'-InicioEsperado',observed['inicio_utc']],capture_output=True,text=True,timeout=20)
                data['cleanup']={'codigo':closed.returncode,'salida':closed.stdout,'error':closed.stderr}
        try:data['codigo']=proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill();data['codigo']=proc.wait();data['harness_terminado_por_supervisor']=True
data.update(estado='terminado',fin_utc=datetime.now(timezone.utc).isoformat())
record=work/'corrida_B/registro_316.json'
if record.exists():
    raw=record.read_bytes();receipt=json.loads(raw)
    data['recibo_sha256']=hashlib.sha256(raw).hexdigest()
    data['error_nativo']=receipt.get('error');data['cierre']=receipt.get('cierre')
    data['fases']=[{'modelo':f['modelo'],'analisis':f.get('retorno_analisis')} for f in receipt.get('fases',[])]
save();print(json.dumps(data,ensure_ascii=False))
raise SystemExit(data.get('codigo',2) or (2 if data.get('timeout') else 0))
