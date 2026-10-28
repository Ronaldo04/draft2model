# Cobertura referencial de sitio

`consultar_sitio(archivo, longitud, latitud)` en draft2model.sitio recibe una capa local revisada, con coordenadas EPSG:4326 y polígonos GeoJSON. El contrato `draft2model.capa_sitio` v0.1 declara fuente/título/edición/referencia, fecha, precisión en metros, naturaleza sintética, zonas y aprobación de huella/revisor/fecha/alcance. El fixture de tests/test_sitio.py documenta el esquema completo.

Devuelve dentro, límite, ambiguo por solapamiento o sin cobertura, conservando la fuente y huellas. Los agujeros se excluyen; un borde se marca como límite. Se rechazan CRS distintos, anillos abiertos/degenerados, duplicados y coordenadas no finitas. Capa preparada para polígonos simples locales; no admite cruces del antimeridiano y no valida toda la topología de cartografía arbitraria. La aprobación declarada implica revisión previa de geometrías y transcripción. La precisión de fuente debe ser considerada por un revisor incluso cuando el cálculo puntual devuelve dentro.

No hay cartografía oficial incorporada ni consulta remota. No se deducen parámetros sísmicos, perfil de suelo o capacidad portante a partir de pertenencia a una zona. Estos campos permanecen null. Una fuente oficial aprobada y los parámetros técnicos explícitos se incorporarán para el caso; el cuadrado sintético de pruebas no es una fuente territorial real.
