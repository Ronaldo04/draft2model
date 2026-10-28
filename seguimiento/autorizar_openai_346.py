"""Registra la autorización expresa del usuario para5solicitudes adicionales."""
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from draft2model.adaptador_etabs import BloqueoExclusivo
from draft2model.revision_reconstruccion import _read,_write

root=Path(__file__).resolve().parents[1]
path=root/'seguimiento/CONSUMO_API_211.json'
lock=BloqueoExclusivo(path.with_suffix('.reconstruccion.lock')).adquirir()
try:
    data=_read(path);authorizations=data.setdefault('autorizaciones_adicionales',[])
    ident='openai_5_adicionales_346'
    if not any(a.get('id')==ident for a in authorizations):
        assert len(data['openai'])==5,'Verificar consumo antes de aplicar esta autorización histórica.'
        limits=data.setdefault('limites_autorizados',{'openai':5,'gemini':5})
        assert limits['openai']==5
        limits['openai']=10
        authorizations.append({'id':ident,'fecha_utc':datetime.now(timezone.utc).isoformat(),
            'proveedor':'openai','adicionales':5,'limite_total':10,
            'instruccion_usuario':'Utiliza la API de open AI para las proximas5solicitudes',
            'alcance':'Solo lectura y extracción de información de los planos; no consultas de programación ni explicaciones.'})
        _write(path,data)
    print(json.dumps({'proveedor':'openai','usadas':len(data['openai']),
                      'limite':data['limites_autorizados']['openai'],
                      'restantes':data['limites_autorizados']['openai']-len(data['openai'])}))
finally:lock.liberar()
