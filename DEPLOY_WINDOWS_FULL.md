# Guía de Despliegue Completo en Windows (Servidor + Cliente)

Esta guía te permitirá ejecutar **todo el sistema** (el Servidor Web y la Aplicación de Escritorio) en una única máquina con Windows.

## 1. Preparación del Entorno
1.  **Copiar Proyecto**: Copia la carpeta `sistema_notarial` a tu PC Windows.
2.  **Instalar Python**: Descarga [Python 3.10+](https://www.python.org/downloads/) y marca **"Add Python to PATH"** al instalar.
3.  **Instalar Dependencias de Python**:
    Abrir `CMD` o `PowerShell` en la carpeta del proyecto y ejecutar:
    ```cmd
    python -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt
    ```

## 2. Instalar Herramientas de Procesamiento (OCR y PDF)
El servidor necesita estas herramientas para leer los documentos escaneados. Sin ellas, la subida fallará.

### A. Tesseract OCR (Lectura de Texto)
1.  Descarga el instalador: [Tesseract-OCR w64 Setup](https://github.com/UB-Mannheim/tesseract/wiki).
2.  Ejecuta el instalador.
3.  **IMPORTANTE**: En la selección de componentes, despliega "Additional language data" y marca **Spanish**.
4.  Copia la ruta de instalación (ej: `C:\Program Files\Tesseract-OCR`).
5.  Añade esa ruta a las **Variables de Entorno (PATH)** de Windows.

### B. Poppler (Manipulación de PDF)
1.  Descarga el ZIP de [Poppler for Windows](https://github.com/oschwartz10612/poppler-windows/releases/).
2.  Descomprime y mueve la carpeta a una ruta segura, ej: `C:\Program Files\Poppler`.
3.  Entra a la carpeta `bin` dentro de Poppler.
4.  Copia esa ruta (ej: `C:\Program Files\Poppler\Library\bin`).
5.  Añade esa ruta a las **Variables de Entorno (PATH)** de Windows.

*(Nota: Después de editar el PATH, cierra y abre las terminales para aplicar cambios).*

## 3. Ejecutar el Servidor
En una terminal (con `venv` activado):
```cmd
python app.py
```
Verás que dice `Running on http://127.0.0.1:5000`. **Deja esta ventana abierta.**

## 4. Ejecutar la Aplicación de Escritorio
Abre una **nueva terminal** (activa `venv` de nuevo si hace falta):
```cmd
python desktop_app/main.py
```
O, si ya creaste el ejecutable con `build_windows.bat`, simplemente dale doble clic al archivo `.exe`.

---
## Solución de Problemas Comunes
*   **Error "Tesseract not found"**: Verifica que `tesseract.exe` esté en tu PATH o reinicia el PC.
*   **Error "Poppler not found"**: Verifica que la carpeta `bin` de Poppler esté en tu PATH.
*   **Firewall**: Si te pide permiso, dale "Permitir acceso" tanto a Python como al ejecutable.
