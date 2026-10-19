# Arquitectura de SismoVivienda AI

Arquitectura conceptual del flujo asistido para la evaluación sismorresistente preliminar de viviendas autoconstruidas (albañilería confinada, 1 a 2 niveles).

El flujo es híbrido: la IA interpreta información gráfica y redacta explicaciones; los algoritmos verifican consistencia y procesan indicadores; ETABS ejecuta el cálculo; el responsable técnico aprueba datos, modelo e informe.

## Diagrama

```mermaid
flowchart TD

    %% ============ ENTRADA ============
    subgraph ENT["ENTRADA - 5.4 Ingreso y calidad"]
        A1["Plano fotografiado / escaneo<br/>JPG, PNG o PDF"]
        A2["Ficha de la vivienda<br/>niveles, alturas, espesores,<br/>materiales, techo, modificaciones"]
        A3["Expediente identificado<br/>originales conservados +<br/>inventario de laminas"]
        A1 --> A3
        A2 --> A3
    end

    %% ============ LECTURA Y REVISION ============
    subgraph LEC["LECTURA Y REVISION - 5.5 a 5.9"]
        B1["Preprocesamiento - OpenCV<br/>perspectiva, contraste, escala, recortes"]
        B2["OCR - Tesseract<br/>textos y cotas con posicion"]
        B3["Vision multimodal - API<br/>clases, asociaciones, evidencia"]
        B4["extraccion_preliminar.json<br/>candidatos + dudas"]
        B5["Controles geometricos<br/>Pydantic + Shapely<br/>unidades, conectividad, duplicados"]
        B6["Interfaz de revision - Streamlit<br/>geometria superpuesta + tablas editables"]
        B7{{"APROBACION 1<br/>datos de entrada"}}
        B8["estructura_validada.json<br/>version inmutable SHA-256"]

        B1 --> B2
        B1 --> B3
        B2 --> B4
        B3 --> B4
        B4 --> B5
        B5 --> B6
        B6 --> B7
        B7 --> B8
        B6 -. "correccion" .-> B5
    end

    %% ============ SITIO ============
    subgraph SIT["SITIO - 5.9"]
        S1["Ubicacion y cartografia oficial<br/>GeoPandas + Shapely + pyproj"]
        S2["Condicion referencial del sitio<br/>zona, limite, cobertura"]
        S1 --> S2
    end

    %% ============ MODELO Y CALCULO ============
    subgraph MOD["MODELO Y CALCULO - 5.10 y 5.11"]
        C1["Adaptador Python + API ETABS<br/>plantilla parametrizada"]
        C2["Generacion del modelo<br/>niveles, objetos, cargas,<br/>masa, restricciones"]
        C3{{"APROBACION 2<br/>modelo y configuracion de analisis"}}
        C4["Analisis modal / modal espectral"]
        C5["Extraccion de resultados<br/>resultados_etabs.json"]
        C6["Motor de reglas deterministico<br/>E.020, E.030, E.070<br/>evaluacion.json"]
        C7["Estados: alerta / sin alerta /<br/>no evaluado / no aplicable"]

        C1 --> C2
        C2 --> C3
        C3 --> C4
        C4 --> C5
        C5 --> C6
        C6 --> C7
    end

    %% ============ EXPLICACION Y ENTREGA ============
    subgraph EXP["EXPLICACION Y ENTREGA - 5.12 y 5.13"]
        D0[("Corpus tecnico controlado<br/>RNE, normas aprobadas")]
        D1["Recuperacion RAG<br/>SQLite FTS5 / BM25<br/>+ embeddings si aportan"]
        D2["Explicacion con LLM<br/>salida estructurada"]
        D3["Verificacion<br/>cifras = resultados<br/>citas = fragmentos recuperados"]
        D4{{"APROBACION 3<br/>informe"}}
        D5["Dashboard + informe PDF<br/>ReportLab + Matplotlib"]

        D0 --> D1
        D1 --> D2
        D2 --> D3
        D3 --> D4
        D4 --> D5
    end

    %% ============ TRANSVERSALES ============
    subgraph TRA["TRANSVERSAL - 5.7, 5.14 y 5.15"]
        T1[("Persistencia<br/>SQLite + archivos por expediente")]
        T2["Orquestacion<br/>cola local, estados,<br/>un trabajo ETABS a la vez"]
        T3["Pruebas P01-P14 - pytest<br/>evidencia reproducible"]
        T4["Contingencias<br/>CSV/Excel, plantilla sin LLM,<br/>corrida precalculada"]
    end

    %% ============ FLUJO PRINCIPAL ============
    A3 --> B1
    B8 --> C1
    S2 --> B6
    S2 --> C1
    C7 --> D1
    C7 --> D2
    C5 --> D3
    C7 --> D5

    %% Contingencia de vision
    T4 -. "CSV/XLSX supervisado" .-> B5

    %% Transversales
    T2 -.-> ENT
    T2 -.-> LEC
    T2 -.-> MOD
    T2 -.-> EXP
    T1 -.-> T2
    T3 -.-> T2

    %% ============ ESTILOS ============
    classDef aprob fill:#fde68a,stroke:#b45309,stroke-width:2px,color:#000
    classDef ia fill:#dbeafe,stroke:#1d4ed8,color:#000
    classDef eng fill:#dcfce7,stroke:#15803d,color:#000
    classDef data fill:#f3f4f6,stroke:#6b7280,color:#000

    class B7,C3,D4 aprob
    class B3,B2,D2 ia
    class C1,C2,C4,C5,C6,C7 eng
    class T1,D0,B4,B8 data
```

## Leyenda

| Color | Significado |
|-------|-------------|
| Amarillo | Puntos de aprobación humana (datos de entrada, modelo y análisis, informe) |
| Azul | Componentes de IA (OCR, visión multimodal, LLM) |
| Verde | Componentes de ingeniería (ETABS, reglas y evaluación) |
| Gris | Contratos de datos y almacenes |

Las líneas punteadas indican el bucle de corrección, la contingencia de visión (CSV/Excel) y el control de la orquestación sobre cada etapa.

## Las tres aprobaciones

1. **Datos de entrada:** permite construir el modelo.
2. **Modelo y configuración de análisis:** habilita el cálculo y la interpretación.
3. **Informe:** autoriza entregar el resultado preliminar.

Los errores y datos faltantes detienen la etapa correspondiente y se registran en el expediente.
