# Brecha CLI 247: plan-etabs, configuración 0.5 y losas R241

Fecha: 2026-10-22. Estado: **confirmada en la copia congelada 246**. No se modificó producto.

Fuente auditada: `tmp/revision_codex_246/draft2model/operaciones_etabs.py`, SHA256 `8270CC423C0D463507A9B641CB8E83BEEE0378AF02814F730F49825B74AFFDC1`.

## Resultado e impacto

La entrada pública `python -m draft2model plan-etabs` delega en `operaciones_etabs.main()`. Su despacho CLI no incluye 0.5 en la rama malla y su argumento `--tipo-shell-losa` acepta exclusivamente texto global. Por tanto, el CLI congelado no transporta la elección R241 por sección ni dirige correctamente la configuración 0.5 al generador malla/líquidos.

| Configuración simulada | Argumentos adicionales | Resultado observado |
| --- | --- | --- |
| 0.4.0 | `--tipo-shell-losa Membrane` | Invoca `generar_plan_malla` (control positivo). |
| 0.5.0 | `--tipo-shell-losa Membrane` | Código 1; `--tipo-shell-losa solo aplica a configuraciones 0.2.`; ningún generador invocado. |
| 0.5.0 | Sin opción de losa | Invoca `generar_plan` legado, no malla/líquidos. |
| 0.5.0 | `--tipo-shell-losa` con mapa JSON inline | Argparse termina con código 2, `invalid choice`; ningún generador invocado. |
| 0.5.0 | `--tipo-shell-losa-json losas.json` | Argparse termina con código 2, `unrecognized arguments`; ese argumento no existe. |

Los códigos 1 de las ramas con generador simulado proceden de centinelas deliberados, no de una validación de configuración ni de un intento de construir un plan real.

Puntos del código congelado:

- Líneas 2028 y 2030: `choices=TIPOS_SHELL_LOSA`; no existe entrada de mapa/archivo de opciones.
- Líneas 2039–2044: solo `me.VERSION_MALLA` entra en la rama malla.
- Líneas 2045–2050: 0.2/0.3 conservan sus generadores de desarrollo.
- Líneas 2051–2059: 0.5 cae en la rama legada; con el argumento de losa se rechaza incluso antes de generar.
- Líneas 1774–1783: `generar_plan_por_version` sí contempla 0.4/0.5. La divergencia está en el despacho CLI duplicado; sustituirlo sin cuidado alteraría el soporte CLI de planes de desarrollo 0.2/0.3.

## Reproducción focal ejecutada

Desde la raíz del proyecto, ejecutar este bloque PowerShell. Usa Python con `-B`, importa explícitamente la copia 246 y sustituye únicamente el cargador y los generadores por dobles. No necesita que existan los archivos nominales de entrada/salida.

```powershell
@'
import sys, io, json, contextlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path('tmp/revision_codex_246').resolve()))
from draft2model import operaciones_etabs as op
from draft2model.__main__ import main
print('fuente=' + str(Path(op.__file__).resolve()))
base=['plan-etabs','--raiz','.','--entrada','config05.json',
      '--salida','no-se-escribe.json']
rows=[]
cases=[('0.4.0',['--tipo-shell-losa','Membrane']),
       ('0.5.0',['--tipo-shell-losa','Membrane']),
       ('0.5.0',[]),
       ('0.5.0',['--tipo-shell-losa',
        '{"PISO":{"tipo":"Membrane","funcion":"piso","justificacion":"revision"}}']),
       ('0.5.0',['--tipo-shell-losa-json','losas.json'])]
for version, extra in cases:
    calls=[]
    def legacy(*args,**kwargs):
        calls.append('generar_plan');raise op.ErrorPlan('CENTINELA_LEGACY')
    def mesh(*args,**kwargs):
        calls.append('generar_plan_malla');raise op.ErrorPlan('CENTINELA_MALLA')
    err=io.StringIO()
    with patch.object(op.me,'cargar_configuracion',return_value={'version_contrato':version}), \
         patch.object(op,'generar_plan',side_effect=legacy), \
         patch.object(op,'generar_plan_malla',side_effect=mesh), \
         contextlib.redirect_stderr(err):
        try: code=main(base+extra)
        except SystemExit as exc: code=exc.code
    rows.append({'version':version,'args':extra,'codigo':code,
                 'generador':calls,'error':err.getvalue().strip().splitlines()[-1]})
assert rows[0]['generador']==['generar_plan_malla']
assert rows[1]['generador']==[] and 'solo aplica' in rows[1]['error']
assert rows[2]['generador']==['generar_plan']
assert rows[3]['generador']==[] and 'invalid choice' in rows[3]['error']
assert rows[4]['generador']==[] and 'unrecognized arguments' in rows[4]['error']
print(json.dumps(rows,ensure_ascii=False,indent=2))
print('5 contrastes focales OK; sin escribir plan, sin ETABS/red')
'@ | python -B -
```

Resultado de la ejecución: **5 contrastes focales OK**. No se abrió ETABS, no se reflejó DLL, no se usó red, no se escribió salida de plan y no se repitieron los tests backend R241.

## Propuesta mínima para una corrección posterior

1. Ampliar la rama CLI de malla a `(me.VERSION_MALLA, me.VERSION_LIQUIDOS)`, manteniendo las ramas de desarrollo y legado. Corregir también la ayuda y el diagnóstico que mencionan versiones incompletas.
2. Añadir `--tipo-shell-losa-json RUTA` como alternativa mutuamente excluyente de `--tipo-shell-losa`. El archivo contendría directamente el mapa `{seccion: {tipo, funcion, justificacion}}`; leer con el cargador JSON estricto existente y exigir objeto antes de delegar. El backend conserva la validación de cobertura exacta, tipos, función y justificación. No inferir función ni convertir una elección global en decisiones por sección.
3. Documentar ambas rutas: texto global como compatibilidad; archivo como declaración explícita por sección. Ejemplo de mapa: `{"PISO":{"tipo":"Membrane","funcion":"piso","justificacion":"Idealización de piso revisada"},"FONDO":{"tipo":"ShellThin","funcion":"fondo_deposito","justificacion":"Resistencia fuera del plano revisada"}}`. El ejemplo no equivale a aprobar una solución estructural.
4. Añadir prueba CLI focal de 0.5 que observe `generar_plan_malla` y el mapa exacto recibido, incluyendo piso/fondo diferentes. Cubrir conflicto entre flags, archivo ilegible, JSON inválido/no objeto y la conservación del texto global en 0.4/0.5 y de rutas previas. Una prueba de integración con fixture 0.5 real debe verificar el plan producido; el contraste de despacho de este informe no sustituye esa validación.

## Alcance y límites

El hallazgo demuestra selección de rama y restricciones del parser en los bytes congelados 246 mediante la entrada pública. La configuración mínima es un doble deliberado: no pretende ser una configuración 0.5 válida. No demuestra generación integral, geometría, comportamiento COM, relectura ni seguridad estructural. Tampoco afirma que los archivos activos de Claude conserven la brecha: deben revisarse tras su próxima entrega. Único archivo escrito por esta auditoría: este informe.
