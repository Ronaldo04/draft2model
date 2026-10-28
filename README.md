# Draft2Model

> **Asistente local para convertir planos estructurales en datos revisables, modelos ETABS e informes preliminares trazables.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%20%7C%203.11-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Normativa: RNE E.030](https://img.shields.io/badge/Norma-NTP%20E.030%202026-green.svg)](docs/MATRIZ_REQUISITOS_REFERENCIA.md)
[![ETABS: OAPI COM](https://img.shields.io/badge/CSI%20ETABS-v18%20--%20v22-orange.svg)](docs/ADAPTADOR_ETABS.md)

Draft2Model es una plataforma local desarrollada para ingenieros civiles y proyectistas estructurales. Permite digitalizar y calibrar planos de estructuras (PDF o imágenes), extraer geometrías de muros, columnas y losas, ensamblar modelos analíticos en **CSI ETABS** a través de su API oficial (OAPI), realizar el cálculo espectral sismorresistente bajo la **Norma Técnica Peruana E.030**, y generar informes técnicos detallados con trazabilidad integral.

---

## Índice

1. [Características Principales](#-características-principales)
2. [Requisitos del Sistema](#-requisitos-del-sistema)
3. [Instalación Rápida](#-instalación-rápida)
4. [Uso Rápido: Primeros Pasos](#-uso-rápido-primeros-pasos)
   - [Opción A: Demo Sintética Integrada](#opción-a-demo-sintética-integrada-sin-conexión-ni-licencias)
   - [Opción B: Interfaz Gráfica Web Local](#opción-b-interfaz-gráfica-web-local)
5. [Flujo de Trabajo Completo](#-flujo-de-trabajo-completo)
6. [Arquitectura del Repositorio (EGM Blueprint)](#-arquitectura-del-repositorio)
7. [Pruebas y Verificación](#-pruebas-y-verificación)
8. [Alcance y Responsabilidad Técnica](#-alcance-y-responsabilidad-técnica)
9. [Licencia](#-licencia)

---

## 🌟 Características Principales

* **Digitalización y Calibración Geométrica**: Ingesta de planos en PDF o raster, calibración métrica mediante cotas y correspondencia de ejes estructurales.
* **Procesamiento Híbrido (Offline / Cloud Opcional)**:
  * Funciona al **100% de manera local y offline** utilizando geometría analítica y casos sintéticos.
  * Opcionalmente permite conectar con modelos multimodales (Google Gemini o OpenAI) para extracción asistida de planos.
* **Integración Nativa con CSI ETABS**: Creación automatizada de materiales, secciones, grillas, muros de corte, losas con aberturas, diafragmas rígidos, asignación de cargas y corridas de análisis modal/espectral.
* **Normativa Sísmica Peruana E.030**: Motor integrado para el cálculo automático de factores sísmicos ($Z$, $U$, $C$, $S$, $R$) y espectro de aceleraciones para todos los distritos del Perú.
* **Interfaz Visual Local SPA**: Entorno web interactivo para superposición de planos, visualización tridimensional (Three.js/WebGL) y auditoría de resultados sin enviar datos a servidores externos.
* **Trazabilidad Criptográfica**: Cada plano procesado cuenta con su huella digital SHA-256 para auditoría y reproducibilidad forense.

---

## 💻 Requisitos del Sistema

* **Sistema Operativo**: Windows 10 o Windows 11 (64-bit). *(Requerido para la integración OAPI COM con ETABS. El motor geométrico y la interfaz web también son compatibles con Linux/macOS).*
* **Python**: Versión **3.10** o **3.11** (64-bit).
* **Dependencias Base**: PyMuPDF y Pillow (instalables vía pip).
* **Software Opcional**:
  * **CSI ETABS**: v18, v19, v20, v21 o v22 instalado localmente *(sólo necesario para generar y correr modelos `.EDB` reales)*.
  * **API Keys (Opcional)**: Clave de OpenAI o Gemini *(sólo si deseas usar visión artificial sobre planos no vectorizados; no requerida para el flujo estándar)*.

---

## 🚀 Instalación Rápida

### 1. Clonar el repositorio
```bash
git clone https://github.com/Ronaldo04/draft2model.git
cd draft2model
```

### 2. Crear y activar el entorno virtual
En **PowerShell** (Windows):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Instalar dependencias
Instalación estándar:
```powershell
pip install -r requirements.txt
```

*(Opcional: Si deseas una instalación hermética exactamente reproducible idéntica al entorno de pruebas, utiliza el archivo lock)*:
```powershell
pip install --require-hashes -r requirements-win-py310.lock
```

---

## 🎯 Uso Rápido: Primeros Pasos

### Opción A: Demo Sintética Integrada (Sin conexión ni licencias)

Puedes validar el funcionamiento completo de Draft2Model en menos de un minuto utilizando la demo integrada. Esta demo ejecuta todas las etapas (ingreso, calibración, geometría, análisis y reporte) usando un caso sintético con aprobaciones simuladas:

```powershell
# 1. Ejecutar la demo generando los artefactos en una carpeta temporal:
python -m draft2model demo-integrada --salida tmp/demo_inicial

# 2. Verificar la integridad de los resultados generados:
python -m draft2model demo-integrada --salida tmp/demo_inicial --verificar
```

### Opción B: Interfaz Gráfica Web Local

Para abrir el entorno visual de revisión de planos en tu navegador web:

1. Haz doble clic en el acceso directo:
   ```text
   Abrir revision de planos.cmd
   ```
2. O ejecuta desde tu terminal:
   ```powershell
   python -m draft2model.revision_visual --puerto 8766
   ```

El servidor local se iniciará en `http://localhost:8766` y abrirá automáticamente tu navegador predeterminado. Para detener el servidor, presiona `Ctrl + C` en la consola.

---

## 🔄 Flujo de Trabajo Completo

El ciclo de vida en Draft2Model se estructura en etapas auditables e independientes:

```text
[ Plano PDF / Imagen ]
          │
          ▼
1. INGESTA Y CALIBRACIÓN  ──► (Cálculo de escala física px/m y ejes)
          │
          ▼
2. EXTRACCIÓN GEOMÉTRICA  ──► (Muros, losas, aberturas, polígonos)
          │
          ▼
3. REVISIÓN Y APROBACIÓN  ──► (Lienzo interactivo / superposición)
          │
          ▼
4. NORMATIVA SÍSMICA      ──► (Cálculo E.030: Z, U, S, C, R)
          │
          ▼
5. AUTOMATIZACIÓN ETABS   ──► (Creación de modelo .EDB y corrida modal)
          │
          ▼
6. INFORME TÉCNICO        ──► (Exportación formal JSON / HTML / PDF)
```

### Comandos de la Línea de Comandos (CLI)

```powershell
# Ver todos los subcomandos disponibles:
python -m draft2model --help

# Diagnosticar estado del entorno y de la API de ETABS:
python scripts/diagnosticar_entorno.py
powershell -File scripts/diagnosticar_api_etabs.ps1

# Consultar parámetros sísmicos de un distrito (Norma E.030):
python -m draft2model.normativa_e030 --distrito "PUEBLO LIBRE" --suelo S2
```

---

## 🏗 Arquitectura del Repositorio

El proyecto implementa el estándar arquitectónico de contratos **Elephant-and-Goldfish Model (EGM)**, donde cada paquete cuenta con su contrato explícito de interfaces, invariantes y efectos colaterales:

```text
draft2model/
├── draft2model/                  # Motor principal del sistema
│   ├── datos/                    # Tablas y coeficientes sísmicos E.030
│   │   └── README.md             # Contrato de datos normativos
│   ├── revision_web/             # Interfaz web local SPA (HTML/JS/Canvas/3D)
│   │   └── README.md             # Contrato de la interfaz de usuario
│   └── README.md                 # Contrato central de interfaces y símbolos
├── scripts/                      # Herramientas de automatización y diagnósticos
│   └── README.md                 # Contrato de herramientas de soporte
├── tests/                        # Suite de pruebas unitarias y funcionales
│   └── README.md                 # Contrato de pruebas y fixtures
├── docs/                         # Especificaciones técnicas y de diseño
│   └── README.md                 # Blueprint de documentación
├── examples/                     # Demostraciones y casos sintéticos
│   └── README.md                 # Contrato de casos de prueba reproducibles
├── seguimiento/                  # Matriz de hitos y trazabilidad técnica
│   └── README.md                 # Contrato de verificación de criterios
├── requirements.txt              # Dependencias de producción
├── requirements-win-py310.lock   # Lockfile con hashes criptográficos
├── Control de avance.html        # Panel visual de avance del proyecto
├── Abrir control de avance.cmd   # Lanzador directo del control de avance
├── Abrir revision de planos.cmd  # Lanzador directo del servidor web local
└── LICENSE                       # Licencia de código abierto Apache 2.0
```

### Contratos de Módulos (EGM Blueprints)
- [`draft2model/`](draft2model/README.md): Lógica de visión, geometría computacional, adaptador OAPI ETABS y generador de informes.
- [`draft2model/datos/`](draft2model/datos/README.md): Base de datos distrital de zonificación y factores de suelo del Perú.
- [`draft2model/revision_web/`](draft2model/revision_web/README.md): Interfaz web de usuario y visualizador tridimensional local.
- [`scripts/`](scripts/README.md): Scripts de verificación, diagnóstico OAPI y empaquetado.
- [`tests/`](tests/README.md): Batería de pruebas automatizadas con pytest y runners Node.js.
- [`docs/`](docs/README.md): Documentación detallada de diseño, guías reproducibles y protocolos.
- [`examples/`](examples/README.md): Ejemplos y fixtures sin datos confidenciales.
- [`seguimiento/`](seguimiento/README.md): Registro de hitos y validaciones de calidad.

### Invariantes Globales del Sistema
1. **Seguridad y Privacidad**: Ningún plano ni dato sensible de ingeniería es enviado a servidores remotos a menos que el usuario configure voluntariamente claves de API y confirme explícitamente el envío.
2. **Aprobaciones Declarativas**: Aprobar una lectura geométrica, un análisis numérico o un informe son actos diferenciados e independientes.
3. **No Invasión de Archivos**: Los archivos `.EDB` de ETABS de proyectos existentes nunca se modifican en el lugar original; todo cálculo se ejecuta en réplicas de trabajo temporales dentro de la ruta especificada por el usuario.

---

## 🧪 Pruebas y Verificación

Para ejecutar la batería completa de pruebas automatizadas:

```powershell
# Ejecutar todas las pruebas con pytest:
pytest tests/

# Comprobar la integridad de las fuentes del repositorio:
python scripts/crear_paquete_aecode.py --comprobar

# Comprobar el seguimiento de criterios técnicos:
python seguimiento/control.py
```

---

## ⚖️ Alcance y Responsabilidad Técnica

* **Uso Asistencial**: Draft2Model es una herramienta de asistencia tecnológica para el modelado preliminar y ordenamiento de datos. **No reemplaza el criterio ni la responsabilidad civil del Ingeniero Estructural Colegiado.**
* **Validación Obligatoria**: Todo modelo generado en ETABS y todo informe emitido deben ser revisados, verificados y sellados por el profesional responsable antes de su uso en proyectos constructivos reales o expedientes municipales.
* **Límites Normativos**: Los espectros y factores calculados corresponden estrictamente a las fórmulas del Reglamento Nacional de Edificaciones (RNE E.030). El sistema no certifica la seguridad estructural frente al colapso ni deduce capacidades portantes sin estudios de mecánica de suelos aprobados.

---

## 📄 Licencia

Este proyecto está bajo la Licencia **Apache 2.0**. Para más información, consulta el archivo [LICENSE](LICENSE).
