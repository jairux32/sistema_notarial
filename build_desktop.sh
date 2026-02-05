#!/bin/bash
echo "📦 Iniciando Empaquetado con PyInstaller..."

# Activar entorno
source desktop_app/venv/bin/activate

# Limpiar builds anteriores
rm -rf build dist *.spec

# Instalar dependencias de build si faltan
pip install pyinstaller

# Obtener ruta de customtkinter para incluir datos
CTK_PATH=$(python -c "import customtkinter; print(customtkinter.__path__[0])")

echo "📍 CustomTkinter Path: $CTK_PATH"

# Ejecutar PyInstaller
# --noconfirm: Sobrescribir sin preguntar
# --onedir: Crear carpeta (más rápido de iniciar que --onefile)
# --windowed: No mostrar consola (desactivar para debug)
# --name: Nombre del ejecutable
# --add-data: Incluir temas de CustomTkinter
# --hidden-import: Asegurar que se incluyen librerias dinámicas

pyinstaller --noconfirm --onedir --windowed \
    --name "EscanerNotarial" \
    --add-data "$CTK_PATH:customtkinter/" \
    --hidden-import "PIL._tkinter_finder" \
    --hidden-import "customtkinter" \
    --hidden-import "requests" \
    desktop_app/main.py

echo "✅ Empaquetado completado."
echo "📂 Ejecutable en: dist/EscanerNotarial/EscanerNotarial"
