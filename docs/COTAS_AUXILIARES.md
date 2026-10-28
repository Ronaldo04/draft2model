# Cotas auxiliares de geometría (contrato 258)

Los depósitos, cercos y apoyos de tanque pueden quedar por debajo de la base o por encima del último piso. Antes, el plan ETABS
rechazaba todo punto fuera de `[base, último piso]` («no se crean pisos ficticios») y la única salida era declarar esas cotas como
niveles, lo que las convertía en `Story` de ETABS (base −2,50, plantas N0/NTF/NTT), con efecto en derivas por piso, diafragmas y
altura sísmica.

## Contrato

`niveles[].tipo` es opcional: `"piso"` (por omisión, comportamiento anterior) o `"auxiliar"`.

- Un nivel **piso** sigue generando `cStory.SetStories_2` (el más bajo es la base).
- Un nivel **auxiliar** no crea `Story`, diafragma ni altura sísmica. Solo amplía la envolvente de cotas admitidas para los puntos
  de superficies y frames (`_motivos_superficies`). Un punto fuera de pisos y cotas auxiliares declaradas sigue rechazado.
- Un muro por niveles (`muros[].nivel_inferior/superior`) no puede referirse a una cota auxiliar (`nivel_auxiliar_en_muro`).
- El plan lista las cotas en `niveles_auxiliares` (`story_etabs: null`).

## Evidencia y límites

- Ensayo nativo de Codex `seguimiento/ENSAYO_COTAS_AUXILIARES_257.md`: ETABS aceptó y persistió puntos, áreas y frames entre −2,5 y
  14,25 manteniendo base 0 y cuatro pisos. Los puntos se releyeron asociados a `Base` o al último piso, sin cambiar su Z global.
  No se repite aquí.
- No se infieren apoyos, diafragmas ni conexiones por estar bajo o sobre un nivel. Siguen siendo declaraciones explícitas de la
  configuración (`apoyos`, `diafragmas`, `sin_diafragma`, `nodos_derivados`).
- Pruebas: `tests/test_cotas_auxiliares_258.py` (contrato, validador y guarda del plan).
- Caso pueblo-libre-002: geometría 09D-v3 marca NCF −2,50, NTF +12,50 y NTT +14,25 como auxiliares; N0 es la base y N1–N4 los
  únicos pisos.
