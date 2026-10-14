# Guía de puesta en marcha: GitHub privado

Verificada con documentación oficial el 13 de octubre de 2026. Contempla versionado privado y acceso de consulta. La base del repositorio ya está creada y cargada. Los procedimientos siguientes sirven como referencia; no implican que los pendientes de acceso estén resueltos.

## 1. Elegir el acceso antes de crear o invitar

| Necesidad | Modalidad | Qué puede hacer una persona invitada |
| --- | --- | --- |
| Iniciar el versionado privado | Repositorio privado en la cuenta personal del usuario | Solo la cuenta propietaria, mientras no haya otras autorizaciones. |
| Equipo que debe consultar sin escribir | Repositorio privado propiedad de una organización administrada por el usuario | Permiso Read sobre el repositorio. |
| Invitar al privado personal | Cuenta personal | Concede lectura y escritura: no cumple solo lectura; necesita aceptar expresamente esa diferencia antes de invitar. |

**Un repositorio privado personal no permite colaboradores de solo lectura.** Un acuerdo verbal de no editar no cambia ese permiso. Tampoco permite dar acceso distinto por carpeta. Compartir la URL no concede acceso: la persona debe iniciar sesión con una cuenta autorizada y aceptar su invitación. [Permisos personales](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/permission-levels-for-a-personal-account-repository), [roles de organización](https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/repository-roles-for-an-organization).

La organización no es una cuenta compartida: la administración se realiza con la cuenta personal autorizada. Esa alternativa cambia el propietario del repositorio a la organización, por lo que debe aceptarse antes de elegirla. No se ha creado ninguna organización.

Si solo se necesita preparar el proyecto ahora, crear el remoto privado sin invitar todavía evita conceder permisos no deseados.

## 2. Datos necesarios

- Cuenta propietaria autenticada en GitHub; no entregar su contraseña al equipo ni al asistente.
- Nombre elegido; `draft2model` es la propuesta inicial.
- Cuentas GitHub de quienes recibirán acceso; validar que correspondan a las personas correctas.
- Decisión sobre cómo dar consulta sin conceder escritura no deseada; no asumir que el acceso personal equivale a Read.
- Plan GitHub del propietario para conocer qué protección de ramas puede aplicarse.

No se necesita comprar un plan para tener un repositorio privado personal con colaboradores. No confundir esto con la disponibilidad de protecciones avanzadas. [Invitar colaboradores](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/inviting-collaborators-to-a-personal-repository).

## 3. Crear el repositorio manualmente en el navegador

Para comenzar bajo la cuenta personal, crear el privado sin invitar personas. Los permisos de consulta se configuran según la modalidad aprobada. El acceso de consulta se resuelve por separado; si se necesita Read efectivo sobre el mismo repositorio, elegir una organización antes de conceder acceso.

1. Abrir [crear repositorio](https://github.com/new) estando en la cuenta propietaria.
2. En **Owner**, verificar la cuenta personal correcta.
3. En **Repository name**, escribir el nombre confirmado.
4. Descripción sugerida: `Asistente para transformar planos en modelos ETABS y evaluación preliminar trazable.`
5. Seleccionar **Private** y comprobarlo antes de crear.
6. Dejar desmarcada la creación de README. No seleccionar plantilla `.gitignore` ni licencia: la carpeta ya contiene README y exclusiones; la licencia aún no se ha acordado.
7. Crear el repositorio. Debe quedar vacío para seguir cualquiera de las rutas de carga indicadas abajo.
8. Copiar su URL y registrarla en `REGISTRO_DECISIONES.md`. No incluir credenciales en ella.

Si se eligió organización, seleccionar esa organización como Owner después de verificar su creación y autorización. El resto de la carga es equivalente; la administración de permisos cambia en el apartado 6.

[Creación oficial de repositorios](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository).

## 4. Revisar qué se sube

| Contenido | Tratamiento inicial |
| --- | --- |
| `README.md`, `docs/`, `.gitignore`, `.github/` | Documentación y preparación de operación. |
| Dos PDF base | Preservar y compartir únicamente si el material está autorizado para el equipo. |
| `entregables/` | Material de definición; revisar antes de cargar. |
| `tmp/` | Intermedios y scripts de exportación existentes; excluidos en esta preparación. Revisar qué scripts merece conservar cuando se trabaje reproducibilidad. |
| Credenciales, `.env`, secretos | No subir. |
| Originales privados, datos personales, corridas y modelos generados | Mantener fuera del seguimiento inicial; usar muestras autorizadas y referencias de ubicación cuando corresponda. |

No trasladar todo ciegamente ni usar `git add .` como primera revisión. `.gitignore` no elimina material previamente versionado y no sustituye la lectura de los cambios. Mantener los originales locales: aquí no se ha movido ni borrado ninguno.

Los dos PDF base son pequeños (aproximadamente 147 KB y 89 KB); no requieren Git LFS por su tamaño. El tratamiento de modelos o archivos grandes futuros se decide cuando exista el inventario correspondiente.

## 5. Carga inicial: elegir UNA ruta

No combinar ambas sobre distintas copias sin saber cuál es la copia de trabajo vigente.

### Ruta A: GitHub Desktop, sin comandos

Adecuada si se prefiere interfaz gráfica.

1. Instalar [GitHub Desktop](https://desktop.github.com/) si no está disponible e iniciar sesión con la cuenta propietaria.
2. Usar **File -> Clone repository**, pestaña **URL**, pegar la URL del remoto vacío.
3. Elegir una carpeta nueva vacía para la copia de trabajo. No clonar encima de esta carpeta con documentos.
4. Copiar a esa nueva carpeta únicamente `README.md`, `docs/`, `.github/`, `.gitignore`, los dos PDF base y `entregables/` autorizados. Mostrar archivos ocultos en el Explorador si hace falta. No copiar una carpeta `.git` de otro lugar.
5. En Desktop, revisar **Changes**, los nombres y el contenido. Retirar de la copia de trabajo cualquier archivo que no deba enviarse, conservando el original en su ubicación de origen.
6. Crear el primer commit con el resumen `Preparar documentación y plan de operación`.
7. Verificar que la rama principal sea `main` antes de seguir; ajustar el nombre si la configuración inicial de la cuenta usó otro.
8. Usar **Push origin** y abrir el repositorio en el navegador. Si aparece **Publish branch** para la primera rama, verificar el remoto de destino antes de publicar esa rama.
9. Confirmar que sigue siendo privado y que se ven los documentos y plantillas.
10. Registrar cuál es la carpeta clonada: será la copia de trabajo vigente para no mantener dos versiones editables en paralelo.

[Clonar con Desktop](https://docs.github.com/en/desktop/adding-and-cloning-repositories/cloning-and-forking-repositories-from-github-desktop).

### Ruta B: Git en la carpeta actual

Adecuada si se quiere mantener esta carpeta como copia de trabajo. Requiere Git instalado y autenticación propia. Ejecutar solo si sigue sin existir un repositorio Git y el remoto creado está vacío. Si alguno ya tiene historial, detener esta ruta y revisar cómo conectarlo; no forzar un push ni sobrescribir historia.

Abrir PowerShell en la carpeta del proyecto. Ejecutar cada paso por separado y comprobar su resultado:

```powershell
git --version
git init -b main
git status --short
```

Comprobar la identidad configurada:

```powershell
git config user.name
git config user.email
```

Si faltan o son incorrectas, establecer **solo para este repositorio** los valores reales; puede usarse el correo privado de commits proporcionado por GitHub:

```powershell
git config user.name "TU NOMBRE"
git config user.email "TU CORREO DE COMMITS"
```

Agregar únicamente el paquete revisado, omitiendo cualquier elemento que no esté autorizado:

```powershell
git add -- README.md .gitignore docs .github
git add -- SismoVivienda_AI_Desarrollo_Tecnico.pdf "SismoVivienda_AI_Entrega_Avance 01 - 03-10-2026.pdf" entregables
git diff --cached --stat
git diff --cached
git status --short
```

Si la lista es correcta, confirmar y conectar. **Reemplazar la URL de ejemplo por la real antes de ejecutar:**

```powershell
git commit -m "Preparar documentación y plan de operación"
git remote add origin https://github.com/TU_USUARIO/TU_REPOSITORIO.git
git remote -v
git push -u origin main
```

El inicio de sesión debe utilizar el flujo de autenticación de Git disponible en esa máquina. No escribir tokens en comandos, URLs ni archivos compartidos. Si falla por autenticación, resolver acceso antes de repetir; si el remoto ya tiene commits, revisar historia sin usar `--force`.

Verificar en el navegador los archivos y privacidad. Guardar URL, rama principal y estado en los registros Markdown. Los comandos anteriores **no se han ejecutado** desde este chat.

## 6. Invitar y comprobar permisos

### Repositorio personal: límite de permisos

El propósito actual del equipo es consultar el código. Esta ruta otorga escritura y no es una solución de solo lectura. No ejecutar invitaciones hasta aceptar expresamente ese permiso o elegir la alternativa de organización.

1. Solicitar el usuario GitHub de cada persona.
2. Ir a **Settings -> Collaborators -> Add people**.
3. Identificar la cuenta correcta y enviar la invitación.
4. La persona acepta con su propia cuenta. Verificar aceptación; no basta con enviarla.
5. Compartir después el enlace del repositorio como acceso directo.
6. Comprobar juntos que ve los archivos. Confirmar que el permiso real incluye escritura, aunque no se le soliciten cambios ni entregas.

Para cancelar una invitación pendiente o retirar una persona, utilizar la misma sección de acceso. La retirada no borra clones o descargas anteriores. [Guía oficial de invitaciones](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/inviting-collaborators-to-a-personal-repository).

### Organización: acceso de consulta

La cuenta propietaria administra la organización. Revisar permisos base; no conceder acceso global innecesario. Dar **Read** a las cuentas del equipo que consultarán el código, sin concederles Write, Maintain ni Admin. Verificar que pertenencia a equipos u otros permisos no otorgue un nivel superior. El permiso técnico de GitHub no asigna tareas de desarrollo. [Permisos oficiales](https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/repository-roles-for-an-organization).

La selección de organización y sus invitaciones requiere la decisión del propietario. No está configurada por esta guía.

## 7. Seguimiento del avance

1. Mantener **Issues** habilitado y utilizar la plantilla preparada.
2. Abrir una Issue por requisito o entrega. Registrar dependencia, comprobación y evidencia.
3. Crear hitos O0-O6 sin fechas hasta acordar el plazo. Para empezar basta la lista de Issues; un GitHub Project privado con columnas puede agregarse después.
4. Utilizar ramas como `docs/operacion`, `feat/contratos` o `fix/unidades` cuando convenga aislar cambios. Coordinar sesiones de Codex y Claude Code para evitar ediciones simultáneas incompatibles.
5. Los PR registran cambios, comprobaciones y evidencia. La integración se sustenta en criterios verificables, sin aprobaciones externas obligatorias. Las observaciones de reunión se documentan cuando existan.
6. Verificar plan: GitHub Free no ofrece protección de ramas para repositorios privados; en cuenta personal esa protección está disponible con GitHub Pro. Para organizaciones privadas corresponde un plan compatible, como GitHub Team. Una cuenta Claude Pro no es un plan GitHub Pro.
7. Si está disponible, impedir force push y eliminación de `main`; exigir controles automáticos únicamente cuando existan y estén verificados. Utilizar PR como registro de cambios y comprobaciones. Configurar criterios de integración verificables sin exigir aprobaciones externas obligatorias.
8. Si no está disponible, registrar el proceso como **convención de trabajo**, no como restricción técnica. Una cuenta con escritura conserva capacidad de omitirlo. Verificar cambios y evidencias antes de integrar.
9. No activar Pages, despliegues o automatizaciones de pago como parte de esta preparación.

[Disponibilidad y funcionamiento de protección de ramas](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

[Limitación de aprobación del propio PR](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/approving-a-pull-request-with-required-reviews).

## 8. Consulta del equipo

Una vez autorizado, el equipo puede leer documentos, historial y código con su propia cuenta, o clonar para consulta. Las observaciones se discuten en reunión y se registran cuando corresponda.

Para consultar el estado reciente desde una copia local, obtener los últimos cambios. El navegador muestra el estado remoto. GitHub no sincroniza carpetas automáticamente ni instala Python, ETABS o Claude Code. La estación de desarrollo se prepara en O1.

El acceso a GitHub no concede acceso a la suscripción Claude ni a APIs de modelos. Esos accesos se configuran individualmente cuando se planifique el entorno; ninguna credencial se comparte mediante el repositorio.

## 9. Comprobación final de O0

- [ ] Propietario, nombre, URL y modalidad de permisos registrados.
- [ ] Visibilidad Private comprobada después de la carga.
- [ ] Una ventana sin sesión no muestra el contenido privado; no cambiar a público para facilitar acceso.
- [ ] Cada persona autorizada aceptó y comprobó su acceso real.
- [ ] No hay personas adicionales con acceso no previsto.
- [ ] README, plan, contexto, registros y fuentes autorizadas visibles y enlazados.
- [ ] Sin temporales, credenciales ni expedientes privados en el primer commit.
- [ ] Copia de trabajo vigente identificada para evitar edición de duplicados.
- [ ] Tareas por requisito y criterios verificables de integración; protección real distinguida de convención.
- [ ] AVANCES y REGISTRO_DECISIONES reflejan lo ejecutado, sin marcar como hecho lo pendiente.

## 10. Próximo dato para continuar con asistencia

El repositorio confirmado es [Ronaldo04/draft2model](https://github.com/Ronaldo04/draft2model), privado y con rama main. Indicar las cuentas autorizadas y la ruta de carga elegida. Se puede continuar desarrollando aunque el acceso de lectores siga pendiente, sin concederles escritura por defecto.
