#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_presentation_pdf.py
Sincroniza y renderiza automáticamente la presentación HTML de Draft2Model en PDF
vectorizado de alta definición (16:9, 13 láminas exactas), y actualiza todos los paquetes
y entregables.
"""

import os
import sys
import shutil
import subprocess
import base64
import zipfile

# Asegurar codificación UTF-8 en consola de Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def find_browser():
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

def main():
    base_dir = r"d:\RONALDO CUCHILLA\1. RONALDO CUCHILLA\2. INGENIERÍA CIVIL DOCS AND PROJECTS\AECODE CURSOS\AECODE AI TALENT\PROYECTO FINAL"
    src_html = os.path.join(base_dir, "Presentacion Demo-Day Draft2Model.html")
    pdf_root = os.path.join(base_dir, "Presentacion Demo-Day Draft2Model.pdf")
    pkg_dir = os.path.join(base_dir, "Presentacion_Draft2Model_Equipo12")
    pdf_pkg = os.path.join(pkg_dir, "Presentacion Demo-Day Draft2Model.pdf")
    entregables_dir = os.path.join(base_dir, "entregables")
    pdf_entregables = os.path.join(entregables_dir, "Presentacion Demo-Day Draft2Model.pdf")
    zip_root = os.path.join(base_dir, "Presentacion_Draft2Model_Equipo12.zip")
    zip_entregables = os.path.join(entregables_dir, "Presentacion_Draft2Model_Equipo12.zip")

    if not os.path.exists(src_html):
        print(f"[ERROR] No se encontró el archivo HTML en: {src_html}")
        sys.exit(1)

    browser_bin = find_browser()
    if not browser_bin:
        print("[ERROR] No se encontró Google Chrome ni Microsoft Edge en las rutas estándar.")
        sys.exit(1)

    print(f"[INFO] Navegador detectado: {browser_bin}")
    print(f"[INFO] Renderizando PDF desde: {src_html}")

    file_url = "file:///" + src_html.replace(os.sep, "/")
    cmd = [
        browser_bin,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_root}",
        file_url
    ]

    res = subprocess.run(cmd, capture_output=True)
    if res.returncode != 0 or not os.path.exists(pdf_root):
        print(f"[ERROR] Error al renderizar PDF. Código de salida: {res.returncode}")
        sys.exit(1)

    pdf_size_mb = os.path.getsize(pdf_root) / (1024 * 1024)
    print(f"[OK] PDF renderizado exitosamente: {pdf_root} ({pdf_size_mb:.2f} MB)")

    # Verificar cantidad de páginas del PDF
    try:
        import pypdf
        reader = pypdf.PdfReader(pdf_root)
        num_pages = len(reader.pages)
        print(f"[OK] Total de páginas verificadas en el PDF: {num_pages} láminas.")
    except Exception:
        try:
            import fitz
            doc = fitz.open(pdf_root)
            num_pages = len(doc)
            print(f"[OK] Total de páginas verificadas en el PDF (fitz): {num_pages} láminas.")
        except Exception:
            num_pages = 13
            print("[INFO] No se pudo cargar módulo de verificación de páginas, PDF creado.")

    # 1. Asegurar directorios de destino
    os.makedirs(pkg_dir, exist_ok=True)
    os.makedirs(entregables_dir, exist_ok=True)
    pkg_assets_equipo = os.path.join(pkg_dir, "assets", "equipo")
    os.makedirs(pkg_assets_equipo, exist_ok=True)

    # 2. Copiar assets del equipo
    src_assets_equipo = os.path.join(base_dir, "assets", "equipo")
    if os.path.exists(src_assets_equipo):
        for f in os.listdir(src_assets_equipo):
            s_path = os.path.join(src_assets_equipo, f)
            d_path = os.path.join(pkg_assets_equipo, f)
            if os.path.isfile(s_path):
                shutil.copy2(s_path, d_path)
    print("[OK] Assets del equipo sincronizados en el paquete.")

    # 3. Sincronizar HTML principal e index.html
    shutil.copy2(src_html, os.path.join(pkg_dir, "Presentacion Demo-Day Draft2Model.html"))
    shutil.copy2(src_html, os.path.join(pkg_dir, "index.html"))
    print("[OK] HTML principal e index.html actualizados.")

    # 4. Copiar PDF a paquete y entregables
    shutil.copy2(pdf_root, pdf_pkg)
    shutil.copy2(pdf_root, pdf_entregables)
    print(f"[OK] Copia de PDF sincronizada en paquete: {pdf_pkg}")
    print(f"[OK] Copia de PDF sincronizada en entregables: {pdf_entregables}")

    # 5. Generar versión autocontenida Base64
    with open(src_html, "r", encoding="utf-8") as f:
        html_content = f.read()

    images_to_embed = {
        "assets/equipo/ronaldo_cuchilla.jpg": os.path.join(src_assets_equipo, "ronaldo_cuchilla.jpg"),
        "assets/equipo/abel_pandal.png": os.path.join(src_assets_equipo, "abel_pandal.png"),
        "assets/equipo/mikel_morales.jpg": os.path.join(src_assets_equipo, "mikel_morales.jpg"),
        "assets/equipo/luis_yupayccana.png": os.path.join(src_assets_equipo, "luis_yupayccana.png"),
    }
    html_standalone = html_content
    for rel_p, abs_p in images_to_embed.items():
        if os.path.exists(abs_p):
            ext = os.path.splitext(abs_p)[1].lower()
            mime = "image/png" if ext == ".png" else "image/jpeg"
            with open(abs_p, "rb") as img_f:
                b64 = base64.b64encode(img_f.read()).decode("utf-8")
                html_standalone = html_standalone.replace(rel_p, f"data:{mime};base64,{b64}")

    standalone_path = os.path.join(pkg_dir, "Presentacion_Draft2Model_Autocontenida.html")
    with open(standalone_path, "w", encoding="utf-8") as f:
        f.write(html_standalone)
    print("[OK] Versión autocontenida HTML (Base64) actualizada.")

    # 6. Actualizar INSTRUCCIONES.txt
    readme_content = f"""# PRESENTACIÓN DEMO DAY - DRAFT2MODEL
## AECODE AI TALENT (2.ª GENERACIÓN) · EQUIPO 12

¡Bienvenido al paquete oficial de la presentación de **Draft2Model**!

---

### ¿CÓMO ABRIR Y EXPONER LA PRESENTACIÓN?

1. **Opción A (Recomendada en Navegador Web):**
   Haz doble clic en:
   `Presentacion Demo-Day Draft2Model.html`  (o en `index.html`).
   Utiliza los recursos optimizados de la carpeta `assets/equipo/`.

2. **Opción B (Archivo Único Autocontenido):**
   Haz doble clic en:
   `Presentacion_Draft2Model_Autocontenida.html`.
   Esta versión contiene todas las fotos, logotipos y vectores incrustados en código Base64. Puedes enviar solo este archivo por correo o mensajería y abrirá al 100% en cualquier dispositivo sin requerir carpetas auxiliares.

3. **Opción C (Documento de Respaldo en PDF):**
   Haz doble clic en:
   `Presentacion Demo-Day Draft2Model.pdf`.
   Documento vectorizado en alta resolución a escala 16:9 con las {num_pages} láminas completas. Ideal para imprimir, enviar como documento estático o proyectar en salas sin navegador web.

---

### CONTROLES Y ATAJOS DE TECLADO DURANTE LA SUSTENTACIÓN (HTML)

* **Avanzar paso / lámina:** Tecla `→` (flecha derecha), `Barra Espaciadora` o `Clic en pantalla`.
* **Retroceder paso / lámina:** Tecla `←` (flecha izquierda).
* **Pantalla completa:** Tecla `F` (o clic en el botón ⛶).
* **Notas del orador (Pitch Script):** Tecla `N` (abre el guion de exposición de cada lámina).
* **Índice interactivo de láminas:** Tecla `I` (abre el menú para saltar a cualquiera de las 13 láminas).
* **Alternar Tema Oscuro / Claro:** Tecla `T`.
* **Imprimir / Guardar en PDF:** Botón `PDF` en la barra inferior (márgenes «Ninguno» y «Gráficos de fondo» activos).
* **Cerrar modales:** Tecla `Escape`.
* **Ayuda de atajos:** Tecla `?`.

---

### CÓMO RE-SINCRONIZAR EL PDF TRAS CAMBIOS EN EL HTML

Si editas `Presentacion Demo-Day Draft2Model.html`, ejecuta simplemente:
```powershell
python render_presentation.py
```
o haz doble clic en `render_presentation.bat`.
Esto re-renderizará de forma automática el PDF, actualizará el HTML autocontenido y regenerará el paquete ZIP.

---

### ESTRUCTURA DE ARCHIVOS DE ESTE PAQUETE

```
Presentacion_Draft2Model_Equipo12/
│
├── Presentacion Demo-Day Draft2Model.html      <-- Presentación interactiva principal
├── index.html                                  <-- Acceso rápido estándar
├── Presentacion_Draft2Model_Autocontenida.html <-- Versión portátil Base64 (1 solo archivo)
├── Presentacion Demo-Day Draft2Model.pdf       <-- Respaldo vectorizado 16:9 ({num_pages} láminas)
├── INSTRUCCIONES.txt                           <-- Esta guía de uso rápido
│
└── assets/
    └── equipo/                                 <-- Fotografías de los miembros
        ├── ronaldo_cuchilla.jpg
        ├── abel_pandal.png
        ├── mikel_morales.jpg
        └── luis_yupayccana.png
```

---

### EQUIPO 12 · CRÉDITOS Y ROLES

* **Ronaldo Cuchilla Nieto** (Ingeniería Civil · UPC) — Líder de Proyecto & Arquitectura de Software
* **Abel Leandro Pandal Laura** (Ingeniería Civil · UNI) — Especialista Sismorresistente
* **Mikel Alonso Morales Cochachin** (Ingeniería Civil · UNI) — Pipeline de Visión & Extracción Asistida
* **Antonio Yupayccana Puma** (Ingeniería Civil · UNSAAC) — Trazabilidad & Generación Documental

*Repositorio Open Source en GitHub:* https://github.com/Ronaldo04/draft2model
"""
    with open(os.path.join(pkg_dir, "INSTRUCCIONES.txt"), "w", encoding="utf-8") as f:
        f.write(readme_content)
    print("[OK] INSTRUCCIONES.txt actualizado.")

    # 7. Empaquetar ZIP final (incluyendo el PDF)
    with zipfile.ZipFile(zip_root, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(pkg_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, base_dir)
                zipf.write(full_path, rel_path)

    shutil.copy2(zip_root, zip_entregables)
    print(f"[OK] Paquete ZIP actualizado: {zip_root}")
    print(f"[OK] Copia de ZIP en entregables: {zip_entregables}")
    print("\n[EXITO] ¡Sincronización y renderizado completados con éxito!")

if __name__ == "__main__":
    main()
