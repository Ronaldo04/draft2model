"""Registra insumos geométricos revisados, no aprobación ni ensayo ETABS."""
import hashlib
import json
from fractions import Fraction
from pathlib import Path
root=Path(__file__).resolve().parent.parent
reports=['AUDITORIA_DEPOSITOS_248.md','AUDITORIA_ESCALERA_248.md','AUDITORIA_C6_PL10_248.md']
sha={f:hashlib.sha256((root/'seguimiento'/f).read_bytes()).hexdigest() for f in reports}
cases=[]
for name,h in [('tanque_division_interior',Fraction('1.10')),('cisterna_altura_interior',Fraction('2.22'))]:
    cases.append({'escenario':name,'h_m':float(h),'p_fondo_kPa':float(10*h),'F_por_m_kN_m':float(5*h*h),'brazo_m':float(h/3),'estado':'referencia_condicional_no_nivel_operativo_confirmado'})
volume=Fraction('2.00')*Fraction('2.15')*Fraction('2.22')
assert volume == Fraction('9.546')
out={'fecha':'2026-10-22','informes_sha256':sha,
     'revision_propia':'Vistas E03tanque/cisterna/techo, A03planta, E02detalle escalera, A03escalera, E01C6cuadro/corte2-2. Hashes/rotaciones/fuentes auditados; no verificación de todos los contornos ni aprobación técnica.',
     'datos_confirmados':'Cisterna altura interior2.22; claros techo2.00/2.15; escaleragarganta.15 y huella.25/ancho1.20; cercoPL10.10/altura2.40/concreto175; C6cuadro.15×.75 con conflicto planta.20×.75.',
     'control_hidrostatico_condicional':cases,'volumen_cisterna_limite_m3':float(volume),'peso_limite_agua_kN':float(volume*10),
     'limites':'No confirma nivel operativo, sección/ejes de apoyo del tanque ni continuidadPL10/C6; no hay EMS. No modifica configuración y no prueba cargas nativas. A03/E02rotacion270: convertir coordenadas antes de cotejar.',
     'aviso_claude':'pendiente_envio'}
(root/'seguimiento/REVISION_AUDITORIAS_248.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'informes':len(sha),'control':cases,'volumen_limite':float(volume)},ensure_ascii=False))
