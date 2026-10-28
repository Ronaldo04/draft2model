"""Validación previa de instalación, configuración, rutas y permisos antes de usar ETABS o un proveedor de planos.

Solo metadatos: no inicia ETABS, no abre modelos, no lee ni imprime claves, no llama a red. Cada comprobación
devuelve {id, estado: ok|aviso|error, mensaje, accion}; un error indica que la operación correspondiente se
rechazará y cómo resolverlo. No corrige nada automáticamente (no cambia políticas ni instala software).

Uso:
  .venv/Scripts/python.exe -m draft2model.preflight --raiz data/private [--json]
"""
from __future__ import annotations

import argparse
import ctypes
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from . import adaptador_etabs as ad
from . import operaciones_etabs as op

RAIZ_PROYECTO = Path(__file__).resolve().parents[1]
LIMITE_RUTA = 260
# Sufijo anidado más largo observado en el recorrido (análisis/lectura dentro del caso) más margen para nombres de caso.
SUFIJO_MAS_LARGO = len("\\<caso-de-40-caracteres-aproximadamente-x>\\lecturas_analisis\\" + "0" * 32 + "\\solicitud.json")
PAQUETES = ("PyMuPDF", "Pillow")  # requirements.txt


def _c(ident, estado, mensaje, accion=""):
    return {"id": ident, "estado": estado, "mensaje": mensaje, "accion": accion}


def version_archivo(ruta: Path) -> str | None:
    """FileVersion de Windows sin cargar la DLL (version.dll); None si no está disponible."""
    if os.name != "nt" or not ruta.is_file():
        return None
    try:
        ver = ctypes.windll.version
        n = ver.GetFileVersionInfoSizeW(str(ruta), None)
        if not n:
            return None
        buf = ctypes.create_string_buffer(n)
        if not ver.GetFileVersionInfoW(str(ruta), 0, n, buf):
            return None
        p, ln = ctypes.c_void_p(), ctypes.c_uint()
        if not ver.VerQueryValueW(buf, "\\", ctypes.byref(p), ctypes.byref(ln)):
            return None
        info = ctypes.cast(p, ctypes.POINTER(ctypes.c_uint32 * 13)).contents
        ms, ls = info[2], info[3]
        return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"
    except (OSError, AttributeError, ValueError):
        return None


def comprobar_python() -> list[dict]:
    out = []
    aislado = sys.prefix != sys.base_prefix
    out.append(_c("python", "ok" if sys.version_info[:2] == (3, 10) and aislado else "aviso",
                  f"Python {platform.python_version()} ({'entorno aislado' if aislado else 'SIN entorno aislado'})",
                  "" if aislado else "Use .venv\\Scripts\\python.exe del proyecto (requirements-win-py310.lock)."))
    faltan = []
    for nombre in PAQUETES:
        try:
            importlib.metadata.version(nombre)
        except importlib.metadata.PackageNotFoundError:
            faltan.append(nombre)
    out.append(_c("paquetes", "error" if faltan else "ok", "Paquetes ausentes: " + ", ".join(faltan) if faltan else "Paquetes requeridos presentes",
                  "Instale desde wheels locales con hashes (docs/GUIA_REPRODUCIBLE.md); no descargue versiones distintas." if faltan else ""))
    return out


def comprobar_etabs(dll: Path = op.DLL_ETABS) -> list[dict]:
    if not dll.is_file():
        return [_c("etabs_dll", "error", f"No existe la API local de ETABS: {dll}",
                   "Instale ETABS 21 con su licencia (la API local no requiere clave). Sin ella solo funcionan los dobles.")]
    version = version_archivo(dll)
    if version is None:
        return [_c("etabs_dll", "aviso", "DLL presente; versión de archivo no legible", "Ejecute operaciones_etabs --verificar-firmas antes de construir.")]
    if version != op.VERSION_DLL_VERIFICADA:
        return [_c("etabs_dll", "error", f"ETABSv1.dll {version} distinta de la verificada {op.VERSION_DLL_VERIFICADA}",
                   "Las firmas no están contrastadas para esta versión: ejecute --verificar-firmas y revise diferencias; no construya hasta resolverlas.")]
    return [_c("etabs_dll", "ok", f"ETABSv1.dll {version} (versión verificada)")]


def comprobar_powershell(powershell: Path = ad.POWERSHELL_51) -> list[dict]:
    if not powershell.is_file():
        return [_c("powershell", "error", f"No existe Windows PowerShell 5.1: {powershell}", "El puente ETABS requiere PowerShell 5.1 de Windows.")]
    try:
        r = subprocess.run([str(powershell), "-NoProfile", "-NonInteractive", "-Command", "Get-ExecutionPolicy"],
                           capture_output=True, timeout=30, stdin=subprocess.DEVNULL)
        politica = r.stdout.decode("utf-8", "replace").strip()
    except (OSError, subprocess.TimeoutExpired):
        politica = ""
    if politica in ("Restricted", "AllSigned"):
        return [_c("powershell", "error", f"Directiva efectiva {politica}: bloquea scripts -File del puente",
                   "Ejecute en un entorno con directiva que permita scripts locales (p. ej. RemoteSigned de usuario). "
                   "El proyecto no cambia la directiva ni usa Bypass.")]
    if not politica:
        return [_c("powershell", "aviso", "No se pudo leer la directiva efectiva", "Compruébela con Get-ExecutionPolicy -List.")]
    return [_c("powershell", "ok", f"PowerShell 5.1 presente; directiva efectiva {politica}")]


def comprobar_raiz(raiz: Path) -> list[dict]:
    raiz = Path(raiz).absolute()
    out = []
    if not raiz.is_dir():
        return [_c("raiz", "error", f"La raíz de expedientes no existe: {raiz}", "Cree la carpeta o indique --raiz con la ruta correcta.")]
    out.append(_c("permisos", "ok" if os.access(raiz, os.W_OK) else "error",
                  "Raíz escribible" if os.access(raiz, os.W_OK) else "Sin permiso de escritura en la raíz",
                  "" if os.access(raiz, os.W_OK) else "Use una carpeta del usuario con permiso de escritura; no ejecute como administrador."))
    largo = len(str(raiz)) + SUFIJO_MAS_LARGO
    if largo >= LIMITE_RUTA:
        out.append(_c("rutas", "error", f"Rutas previstas de hasta {largo} caracteres (límite Windows {LIMITE_RUTA}); el motor las rechazará antes de abrirse",
                      "Use una raíz más corta (p. ej. C:\\d2m\\private) copiando el expediente completo con sus hashes; no use junctions ni desactive guardas."))
    elif largo >= LIMITE_RUTA - 30:
        out.append(_c("rutas", "aviso", f"Rutas previstas de hasta {largo} caracteres: margen escaso frente a {LIMITE_RUTA}",
                      "Prefiera una raíz más corta para casos con nombres largos."))
    else:
        out.append(_c("rutas", "ok", f"Rutas previstas de hasta {largo} caracteres"))
    return out


def comprobar_motor(lock: Path = RAIZ_PROYECTO / "tmp" / "d2" / "motor.lock") -> list[dict]:
    marca = Path(str(lock) + ".incierto.json")
    if marca.exists():
        return [_c("motor", "error", "Hay una operación ETABS no confirmada (marca de incertidumbre activa)",
                   "Compruebe en el host que la instancia propia terminó (ApplicationExit=0 observado o proceso del PID propio "
                   "ausente en el host) y registre AdaptadorEtabs.confirmar_recuperacion con la evidencia. No borre la marca a mano.")]
    return [_c("motor", "ok", "Sin operaciones ETABS inciertas registradas")]


def ejecutar(raiz: Path, **kw) -> dict:
    checks = comprobar_python() + comprobar_etabs(kw.get("dll", op.DLL_ETABS)) + comprobar_powershell(kw.get("powershell", ad.POWERSHELL_51)) \
        + comprobar_raiz(raiz) + comprobar_motor(kw.get("lock", RAIZ_PROYECTO / "tmp" / "d2" / "motor.lock"))
    errores = [c for c in checks if c["estado"] == "error"]
    return {"contrato": "draft2model.preflight", "version_contrato": "0.1.0", "listo": not errores,
            "errores": len(errores), "avisos": sum(1 for c in checks if c["estado"] == "aviso"), "comprobaciones": checks,
            "no_hace": ["iniciar ETABS", "leer o imprimir claves", "llamar a red", "cambiar políticas o instalar software"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raiz", type=Path, default=Path("data/private"))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    r = ejecutar(a.raiz)
    if a.json:
        print(json.dumps(r, ensure_ascii=True, indent=2))  # ASCII: consolas cp1252 no fallan
    else:
        for c in r["comprobaciones"]:
            linea = f"[{c['estado'].upper():5}] {c['id']}: {c['mensaje']}" + (f"\n        -> {c['accion']}" if c["accion"] else "")
            print(linea.encode(sys.stdout.encoding or "utf-8", "replace").decode(sys.stdout.encoding or "utf-8"))
        print("LISTO" if r["listo"] else f"NO LISTO: {r['errores']} error(es)")
    return 0 if r["listo"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
