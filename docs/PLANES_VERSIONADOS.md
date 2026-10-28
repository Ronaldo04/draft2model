# Planes vinculados a versiones geométricas

`python -m draft2model.gestion_planes generar --raiz data/private --caso CASO --version VERSION` crea una carpeta nueva `planes/<uuid>/` con plan.json y version.json. Para comprobar: `python -m draft2model.gestion_planes comprobar --raiz data/private --caso CASO --plan UUID`.

Se comprueban originales, expediente y cadena geométrica antes de calcular. El plan cita ID de versión, SHA256 de geometría, huella de contenido, expediente y metadatos. La comprobación recalcula el plan y contrasta su contenido completo, de modo que rehacer únicamente el hash del plan no oculta una modificación. Una nueva revisión geométrica no reescribe los planes anteriores: permanecen ligados a su origen y pueden consultarse si esa versión y su evidencia siguen íntegras.

Los borradores y faltantes son admisibles para preparar propuestas con bloqueos/omisiones. No se concede aprobación al plan, no se ejecuta ETABS ni se acreditan materiales, cargas o cálculo estructural. Las huellas no son firmas criptográficas frente a un atacante que reescriba coherentemente toda la evidencia. No hay bloqueo entre procesos que impida una edición externa inmediatamente después de comprobar; volver a comprobar antes de consumir el artefacto.

Códigos: 0 correcto, 1 solicitud/lectura inválida, 2 evidencia incoherente. Pruebas: `python -m unittest discover -s tests -p test_gestion_planes.py -v`.
