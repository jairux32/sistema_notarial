@echo off
echo 📦 Iniciando Empaquetado para Windows...

:: Activar entorno (asumiendo que se corre desde la raiz del proyecto)
call desktop_app\venv\Scripts\activate

:: Instalar dependencias
pip install pyinstaller customtkinter pillow requests python-sane packaging

:: Obtener ruta de customtkinter (truco para Windows batch)
for /f "delims=" %%i in ('python -c "import customtkinter; print(customtkinter.__path__[0])"') do set CTK_PATH=%%i

echo 📍 CustomTkinter Path: %CTK_PATH%

:: Limpiar
rmdir /s /q build dist
del *.spec

:: Ejecutar PyInstaller
:: --noconfirm: Sobrescribir
:: --onedir: Carpeta (mas rapido arranque)
:: --windowed: Sin consola negra
:: --icon: Icono (opcional, si tienes uno .ico)
:: --add-data: Formato Windows es origen;destino

pyinstaller --noconfirm --onedir --windowed ^
    --name "EscanerNotarial" ^
    --add-data "%CTK_PATH%;customtkinter/" ^
    --hidden-import "PIL._tkinter_finder" ^
    --hidden-import "customtkinter" ^
    --hidden-import "requests" ^
    desktop_app/main.py

echo ✅ Empaquetado completado.
echo 📂 Ejecutable en: dist\EscanerNotarial\EscanerNotarial.exe
pause
