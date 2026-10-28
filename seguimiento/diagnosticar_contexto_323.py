from pathlib import Path
import copy,json
from unittest.mock import patch
from tests.test_contexto_particion_284 import fixture
from draft2model import particion_superficies as p

original=p.validar_geometria
for name,g in [('fixture',fixture()),('piloto',json.loads(Path('data/private/pueblo-libre-002/geometrias/25ef94672fac4e53863701b55e32f97d/geometria.json').read_bytes()))]:
    ctx=p._ContextoGeometria(g)
    before=ctx._captura_binaria==p._binario_local(g)
    with patch.object(p,'validar_geometria',side_effect=lambda x:original(copy.deepcopy(x))):
        alt=p._ContextoGeometria(g)
    after=alt._captura_binaria==p._binario_local(g)
    print(name,{'captura_actual_coincide':before,'aislar_validacion_coincide':after})
