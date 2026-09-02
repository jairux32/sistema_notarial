@echo off
chcp 65001 >nul
echo ==========================================
echo  ESCANER NOTARIAL - Instalador Windows
echo ==========================================
echo.

echo [1/5] Verificando Python...
python --version
if errorlevel 1 (
    echo ERROR: Python no encontrado
    echo Descarga desde: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo.

echo [2/5] Verificando Tesseract...
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
    echo Tesseract encontrado
) else (
    echo ADVERTENCIA: Tesseract no encontrado
    echo Descarga desde: https://github.com/UB-Mannheim/tesseract/wiki
)
echo.

echo [3/5] Instalando Flask...
pip install Flask
echo.

echo [4/5] Instalando otras dependencias...
pip install Flask-Login Flask-SQLAlchemy pytesseract Pillow PyMuPDF
pip install reportlab werkzeug flask-cors requests python-dotenv
echo.

echo [5/5] Creando base de datos...
python init_database.py
echo.

echo ==========================================
echo  INSTALACION COMPLETADA
echo ==========================================
echo.
echo Ahora ejecuta: iniciar_windows.bat
echo.
pause
