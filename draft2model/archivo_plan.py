"""Generación de un plan a archivo sin reemplazar entradas ni salidas existentes."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import tempfile

from .plan_modelado import ESTADO_INCONSISTENTE, preparar_plan_modelado, serializar
from .validacion_geometria import cargar_geometria


class ErrorArchivoPlan(ValueError):
    pass


@dataclass(frozen=True)
class PlanGuardado:
    ruta: Path
    datos: dict

    @property
    def codigo(self):
        return 2 if self.datos['estado_origen'] == ESTADO_INCONSISTENTE else 0


def _sha(path):
    return hashlib.sha256(path.read_bytes()).digest()


def _publicar_nuevo(temporal, destino):
    if os.name == 'nt':
        # En Windows rename falla si destino existe; os.replace no tiene esa garantía.
        os.rename(temporal, destino)
    else:
        os.link(temporal, destino)


def generar_plan_archivo(entrada: Path, salida: Path) -> PlanGuardado:
    """Publica un archivo completo sin reemplazo en el mismo volumen.

    No reemplaza destinos existentes, incluidos enlaces. La huella de entrada se
    comprueba antes y después del cálculo. No bloquea ediciones de otros procesos.
    """
    entrada, salida = Path(entrada), Path(salida)
    if entrada.resolve() == salida.resolve():
        raise ErrorArchivoPlan('La salida debe ser distinta de la entrada; no se sobrescribe geometría.')
    if os.path.lexists(salida):
        raise ErrorArchivoPlan('La salida ya existe; elige un archivo nuevo.')
    before = _sha(entrada)
    geometria = cargar_geometria(entrada)
    plan = preparar_plan_modelado(geometria)
    contenido = serializar(plan).encode('utf-8')
    if _sha(entrada) != before:
        raise ErrorArchivoPlan('La entrada cambió durante el cálculo; no se guarda el plan.')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix='.plan-', suffix='.tmp', dir=salida.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(contenido)
            stream.flush()
            os.fsync(stream.fileno())
        if _sha(entrada) != before:
            raise ErrorArchivoPlan('La entrada cambió antes de publicar; no se guarda el plan.')
        _publicar_nuevo(temporary, salida)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return PlanGuardado(salida, plan)
