"""Aplicación de la normativa vigente a una configuración estructural (no aprueba ni declara cumplimiento).

Convierte decisiones EXPLÍCITAS (con fuente y estado) en registros de configuración trazables:
- materiales (E.060 8.5.2/8.5.4 concreto; E.070 24.7 albañilería; pesos E.020 anexo 1), desde lecturas del expediente;
- espectro inelástico tabulado (E.030 art. 41.1: Sa = Z·U·C·S/R·g en m/s²; ya incluye g y R: el caso debe usar
  factor de escala 1 para no escalar dos veces);
- fuentes oficiales con URL pública y SHA-256 del documento descargado (sin depender de archivos no empaquetados);
- hipótesis por cada decisión y faltantes por cada puerta no satisfecha (sitio/EMS, sistema, irregularidades).

Las puertas son distintas: sin perfil de suelo no se genera espectro (faltante), pero los materiales sí se completan.
"""
from __future__ import annotations

import copy

from . import normativa_e030 as e030
from . import normativa_rne as rne

# Documentos oficiales (auditoría de Codex 229, fuentes_manifest.json): URL de descarga y SHA-256 del archivo.
FUENTES_OFICIALES = {
    "RNE-E030-RM183-2026": ("E.030 Diseño Sismorresistente, RM 183-2026-VIVIENDA (El Peruano, 2026-05-03)",
                            "https://epdoc2.elperuano.pe/EpPo/DescargaIN.asp?Referencias=MjUxMTI1OC0xMjAyNjA1MDM=",
                            "d119f9bd35a30dd0ea3a90296d7811c5811a0af7d93fc13c5a9a9d3963fefba6"),
    "RNE-E060-DS010-2009": ("E.060 Concreto Armado, DS 010-2009-VIVIENDA",
                            "https://cdn.www.gob.pe/uploads/document/file/2686419/E.060%20Concreto%20Armado%20DS%20N%C2%B0%20010-2009.pdf",
                            "6b4676e849fd65243e3c4428c22156eba6e52829366f49a0a2d1cad550e1c709"),
    "RNE-E070-DS011-2006": ("E.070 Albañilería, DS 011-2006-VIVIENDA (fe de erratas 21/06/2006)",
                            "https://cdn.www.gob.pe/uploads/document/file/2366661/56%20E.070%20ALBA%C3%91ILERIA.pdf",
                            "1833f30c14225c27c26d44e1ff7ad01d299cb2816201b83bb7c596d6b628828f"),
    "RNE-E020-DS011-2006": ("E.020 Cargas, DS 011-2006-VIVIENDA (fe de erratas 21/06/2006)",
                            "https://cdn.www.gob.pe/uploads/document/file/2366640/50%20E.020%20CARGAS.pdf",
                            "94a80fbbc4733f6fdf7bcf94c55a6b6c2a1d24606014f67aaf741097134e5ec7"),
}
ESTADOS_DECISION = ("declarada_usuario", "hipotesis_piloto", "lectura_expediente")
PERIODOS_POR_DEFECTO = (0.0, 0.02, 0.05, 0.08, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 4.0)


class ErrorNormativa(ValueError):
    """Decisión incompleta o inconsistente; no se completa con valores por defecto."""


def fuente_oficial(ident: str, articulos: str) -> dict:
    desc, url, sha = FUENTES_OFICIALES[ident]
    return {"id": ident, "descripcion": f"{desc}. Artículos aplicados: {articulos}.", "referencia": url, "sha256": sha}


def _decision(decisiones: dict, clave: str, fuentes: set) -> dict | None:
    d = decisiones.get(clave)
    if d is None:
        return None
    if not isinstance(d, dict) or "valor" not in d or d.get("estado") not in ESTADOS_DECISION or d.get("fuente") not in fuentes:
        raise ErrorNormativa(f"Decisión {clave!r}: requiere valor, estado ({', '.join(ESTADOS_DECISION)}) y fuente registrada.")
    return d


def aplicar(config: dict, decisiones: dict) -> tuple[dict, dict]:
    """Devuelve (configuración nueva, informe). `config` no se modifica.

    `decisiones` admite: zona, categoria, perfil, vs30 (opcional), sistema, Ia, Ip, materiales (lista de
    {id, clase: concreto|albanileria, resistencia, unidad, tipo_unidad?, fuente}). Cada decisión escalar es
    {valor, estado, fuente}; la fuente debe existir en config["fuentes"].
    """
    nuevo = copy.deepcopy(config)
    ids_fuentes = {f["id"] for f in nuevo["fuentes"]}
    informe = {"aplicado": [], "faltantes": [], "no_evaluado": [
        "Irregularidades Ia/Ip con resultados del modelo (arts. 23–25)", "Cortante mínimo dinámico (art. 44) tras el análisis",
        "Derivas (arts. 50–51) tras el análisis", "Diseño de elementos (E.060/E.070)"]}

    def agregar_fuente(ident, articulos):
        if ident not in ids_fuentes:
            nuevo["fuentes"].append(fuente_oficial(ident, articulos))
            ids_fuentes.add(ident)

    def hipotesis(clave, d, texto):
        nuevo["hipotesis"].append({"id": f"H-NORMA-{clave.upper()}", "descripcion": f"{texto} [{d['estado']}]", "fuente": d["fuente"]})

    def faltante(ruta, motivo, fuente):
        nuevo["faltantes"].append({"ruta": ruta, "motivo": motivo, "fuente": fuente})
        informe["faltantes"].append({"ruta": ruta, "motivo": motivo})

    # Materiales (independientes del sitio).
    for mat in decisiones.get("materiales", []):
        if not isinstance(mat, dict) or mat.get("fuente") not in ids_fuentes:
            raise ErrorNormativa("Cada material requiere la fuente de su lectura registrada en la configuración.")
        if mat.get("clase") == "concreto":
            r = rne.modulo_concreto(mat["resistencia"], mat["unidad"])
            peso = rne.peso_especifico("concreto_armado")["peso_kN_m3"]
            agregar_fuente("RNE-E060-DS010-2009", "8.5.2, 8.5.4")
            agregar_fuente("RNE-E020-DS011-2006", "Anexo 1")
            registro = {"id": mat["id"], "tipo": "isotropo_lineal", "E_kN_m2": r["Ec_kN_m2"], "poisson": 0.15,
                        "peso_kN_m3": peso, "fuente": "RNE-E060-DS010-2009"}
            nota = f"f'c = {mat['resistencia']} {mat['unidad']} → Ec = 4700√f'c = {r['Ec_MPa']:.1f} MPa; ν = 0,15 derivado de G = Ec/2,3"
        elif mat.get("clase") == "albanileria":
            if "tipo_unidad" not in mat:
                faltante(f"materiales.{mat['id']}", "Tipo de unidad de albañilería no declarado (E.070 24.7).", mat["fuente"])
                continue
            r = rne.modulo_albanileria(mat["resistencia"], mat["unidad"], mat["tipo_unidad"])
            agregar_fuente("RNE-E070-DS011-2006", "24.7")
            if "peso_kN_m3" not in mat:
                faltante(f"materiales.{mat['id']}.peso_kN_m3", "Peso de la albañilería no declarado (E.020 anexo 1 por tipo).", mat["fuente"])
                continue
            registro = {"id": mat["id"], "tipo": "isotropo_lineal", "E_kN_m2": r["Em_kN_m2"], "poisson": 0.25,
                        "peso_kN_m3": mat["peso_kN_m3"], "fuente": "RNE-E070-DS011-2006"}
            nota = f"f'm = {mat['resistencia']} {mat['unidad']}, unidad {mat['tipo_unidad']} → Em = {r['Em_MPa']:.1f} MPa; ν = 0,25 (Gm = 0,4 Em)"
        else:
            raise ErrorNormativa(f"Material {mat.get('id')!r}: clase concreto o albanileria.")
        nuevo["materiales"] = [m for m in nuevo["materiales"] if m["id"] != registro["id"]] + [registro]
        informe["aplicado"].append({"material": mat["id"], "detalle": nota, "cita": r["cita"]})

    # Sitio y espectro: puerta propia.
    d = {k: _decision(decisiones, k, ids_fuentes) for k in ("zona", "categoria", "perfil", "vs30", "sistema", "Ia", "Ip")}
    fuente_falta = next(iter(ids_fuentes), None)
    for clave, motivo in (("perfil", "Perfil de suelo sin EMS/declaración (E.030 art. 16; E.050 6.2.1.c para ≥ 4 pisos)."),
                          ("sistema", "Sistema estructural y R0 no declarados (E.030 arts. 20–22)."),
                          ("zona", "Zona sísmica no declarada (anexo de zonificación)."),
                          ("categoria", "Categoría de uso no declarada (Tabla 7)."),
                          ("Ia", "Ia no declarado: se evalúa con el modelo (Tabla 11)."), ("Ip", "Ip no declarado (Tabla 12).")):
        if d[clave] is None:
            faltante(f"sitio.{clave}", motivo, fuente_falta)
    if all(d[k] is not None for k in ("zona", "categoria", "perfil", "sistema", "Ia", "Ip")):
        z = e030.factor_zona(d["zona"]["valor"])
        u = e030.factor_uso(d["categoria"]["valor"])
        sitio = e030.parametros_sitio(d["zona"]["valor"], d["perfil"]["valor"],
                                      vs30=d["vs30"]["valor"] if d["vs30"] else None)
        r = e030.coeficiente_r(d["sistema"]["valor"], d["Ia"]["valor"], d["Ip"]["valor"])
        esp = e030.espectro(Z=z["Z"], U=u["U"], S=sitio["S"], R=r["R"], TP=sitio["TP"], TL=sitio["TL"],
                            periodos=list(decisiones.get("periodos", PERIODOS_POR_DEFECTO)))
        agregar_fuente("RNE-E030-RM183-2026", "11, 17, 18, 19, 22, 26, 41")
        ident = decisiones.get("id_espectro", "ESP-E030-2026")
        nuevo["espectros"] = [e for e in nuevo["espectros"] if e["id"] != ident] + [{
            "id": ident, "unidad_aceleracion": "m/s2", "puntos": [[f["T_s"], f["Sa_m_s2"]] for f in esp["filas"]],
            "fuente": "RNE-E030-RM183-2026"}]
        for clave in ("zona", "categoria", "perfil", "sistema", "Ia", "Ip") + (("vs30",) if d["vs30"] else ()):
            hipotesis(clave, d[clave], f"E.030: {clave} = {d[clave]['valor']}")
        nuevo["hipotesis"].append({"id": "H-NORMA-ESCALA", "fuente": "RNE-E030-RM183-2026",
                                   "descripcion": "El espectro tabulado ya incluye Z·U·S/R y g (art. 41.1): factor de escala del caso = 1."})
        informe["aplicado"].append({"espectro": ident, "parametros": esp["parametros"], "sitio_metodo": sitio["metodo"],
                                    "cita": esp["cita"] + [z["cita"], u["cita"]] + r["cita"]})
    else:
        informe["espectro"] = "no generado: puerta de sitio/sistema/irregularidades pendiente"
    informe["aprobacion_ingenieria"] = None
    return nuevo, informe
