"""Registrar el hito de rendimiento en curso, sin tocar la entrega322."""
from pathlib import Path
from datetime import datetime,timezone
import json
root=Path(__file__).resolve().parents[1]
d=json.loads((root/'seguimiento/RETOMAR_CODEX_322.json').read_bytes())
d.update(fecha_utc=datetime.now(timezone.utc).isoformat(),anterior='seguimiento/RETOMAR_CODEX_322.json',
    estado_hito='323en validación; solo Codex.322permanece validado e intacto.',
    paquete_candidato='entregas/AECODE_ENTREGA_323',
    huella_candidata='0d1f91eb13217b94b6b26e7bd1f40c98a041df758997e72e153d0d6be85c1f3b',
    cambio323='particion_superficies._binario_local:marshal4 en lugar de2; comparación tipada completa y fallback JSON conservados. README/guías actualizados.3pruebas adicionales.',
    focal323='18pruebas correctas; ensayo100capturas:formato2=.633s,4=.316s. No implica velocidad2x del flujo completo.',
    perfil323={'antes':'seguimiento/PERFIL_MODELO_323.json','despues_exec':79735,'estado':'en_curso','script':'seguimiento/perfilar_modelo_323.py --despues'},
    global323={'exec':45942,'registro':'tmp/validacion_distribucion_323/estado.json','estado':'en_curso','no_repetir':True})
d['siguiente']=['Consultar handles79735 y45942 antes de actuar; no relanzar perfiles ni suite.',
    'Si perfil y global terminan0, consolidar323 con sus logs y comparación explícita de manifest322/323. No atribuir a323 una nueva corrida nativa: se conserva322 y consulta regenerada323.',
    'P04sigue sin referencia humana; no inventar anotaciones ni métricas. No nuevasAPIs, Claude, subagentes, modelo manual ni proyectos2/3.']
(root/'seguimiento/RETOMAR_CODEX_323.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
(root/'seguimiento/RETOMAR_ACTUAL.json').write_text(json.dumps({'checkpoint':'seguimiento/RETOMAR_CODEX_323.json','fecha_utc':d['fecha_utc'],'goal_completo':False},ensure_ascii=False,indent=2),encoding='utf-8')
print('Checkpoint323 guardado;322preservado.')
