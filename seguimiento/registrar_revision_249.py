"""Consolida revisión propia y límites de evidencia sin modificar el caso de Claude."""
import hashlib
import json
from pathlib import Path
root=Path(__file__).resolve().parent.parent
path=root/'seguimiento/claude_ruta/REVISIONES.json'
data=json.loads(path.read_text(encoding='utf-8'))
obs={
 'id':'R249-01','prioridad':'P2_limite_de_evidencia','etapas':['04','06'],
 'hallazgo':'Ensayo nativo L246b confirma A/I22/I33/espejos/inserciones y persistencia metros→mm; no acredita Ixy/acoplamiento flector. C10 coincide con respuesta desacoplada+cortante, Uy de excéntricas explicado por torsión/offsets. No demuestra limitación general ETABS ni defecto del transporte por sí solo.',
 'evidencia':['seguimiento/REVISION_C1_NATIVA_CODEX_249.json','seguimiento/REVISION_NATIVA_C1_249.md'],
 'criterio_aceptacion':'Distinguir transporte nativo de fidelidad mecánica. No usar Uy excéntrico como prueba Ixy ni ensayo sintético como piloto. Documentar idealización y límites; evaluar contraste discriminante si se afirma reproducción del acoplamiento. No bloquear la implementación de otros elementos esperando esta revisión.'}
if not any(o['id']==obs['id'] for o in data['observaciones']):
    data['observaciones'].append(obs)
mass={
 'id':'R249-02','prioridad':'P1_integracion_contenido','etapas':['04','06'],
 'hallazgo':'La hidrostática0.5 excluye expresamente masa_del_liquido. Patrón omitido/factor0/.25/1/2 pasan validación sin faltantes en reproducción focal; no hay enlace depósito/volumen/peso/fuente de masa. Es brecha del objetivo contenido100%, no regresión de lo prometido por el módulo hidrostático.',
 'evidencia':'seguimiento/REVISION_MASA_LIQUIDOS_249.md',
 'criterio_aceptacion':'Inventario por depósito/estado con volumen,peso,masa=gammaV/g,fuentes e hipótesis; única representación física de masa al100% sin duplicar peso estático/presión. Masa por presión exige suma vertical correcta y masa factor1, no prueba válida con solo pared. Alternativa de patrón exclusivo requiere excluirlo de combinaciones estáticas duplicadas y excluir presión de masa. Configuración,plan,guardado/relectura y comprobación nativa de masa deben cerrar el recorrido; depósitos ausentes no reciben masas ficticias. No habilitar masa puntual que el ejecutor no soporte.'}
if not any(o['id']==mass['id'] for o in data['observaciones']):
    data['observaciones'].append(mass)
path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
result={'fecha':'2026-10-22','monitor':{'archivos':['seguimiento/estado_claude.py','seguimiento/test_estado_claude_ruta.py'],
 'correccion':'Dentro de etapa, ordenar incrementos por creado_utc normalizado, no por UUID. Mantiene precedencia de etapas y fallback estable sin fecha. Fechas inválidas/sin zona se rechazan.',
 'pruebas':'6 pruebas focales OK0.387s; protege incrementos invertidos y variantes de zona/fecha, cola histórica, hash y rutas.'},
 'insumos248':'Estado vivo de Claude ya incorpora cisterna/tanque/escaleraU/C6/PL10 y referencia248. Hay evidencia de recepción en archivo; la última captura de comprobación visual se interrumpió por Escape. No repetir aviso como si se supiera no enviado.',
 'nativo_C1':'35 comprobaciones propias sobre recibo conservado, sin invocarETABS; resultado correcto_con_limites. No es cierre del piloto.',
 'proceso_pruebas_Claude':'Consulta host de Python unittest/focos sin procesos coincidentes; focos246_l.log termina140testsOK272.508s. No reiniciar esa ejecución terminal. columna_l_plan_246a.log contiene verificación241operaciones sintéticas, pendiente auditoría/inmutable.',
 'apis':'Sin llamadas nuevas; OpenAI4/5,Gemini2/5',
 'estado_goal':'activo_no_completo'}
result['monitor']['sha256']={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in result['monitor']['archivos']}
(root/'seguimiento/AVANCE_CODEX_249.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Revisión249 registrada; sin cambios en producto/configuración de Claude.')
